# -*- coding: utf-8 -*-
"""execution_browser.py — درایورِ مرورگر برای Strategyهای سرخطی.

دو پیاده‌سازی:
  • PlaywrightBrowserDriver — Playwright در یک threadِ اختصاصی. دلیل: APIِ sync
    از یک thread به threadِ دیگر قابلِ استفاده نیست؛ prepare در درخواستِ HTTP و
    trigger در threadِ زمان‌بند اجرا می‌شوند. همهٔ فراخوانی‌های Playwright درِ
    همان thread می‌مانند.
  • MockBrowserDriver — برای گاردها و benchmarkِ بدونِ مرورگر.

قفل‌های امنیتی:
  ۱) هیچ توکن/کوکی/مقدارِ input خوانده یا چاپ نمی‌شود. probe فقط ساختار
     (tag/type/name/id/data-testid/aria-label/متنِ کوتاه) برمی‌گرداند.
  ۲) در حالتِ dry-run، routeِ درخواستِ سفارش abort می‌شود؛ هیچ POSTی به
     کارگزاری نمی‌رسد. این لایه مستقل از Dry-runِ سرویس است.
  ۳) پروفایلِ مرورگر یک مسیرِ کاربریِ محلی است، نه فایلِ تنظیمات/گیت.
"""
from __future__ import annotations

import glob
import os
import queue
import tempfile
import threading
import time
from typing import Any, Callable, Mapping, Optional
from urllib.parse import urlparse

from execution_strategy_core import StrategySettings


class BrowserUnavailable(RuntimeError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class BrowserCommandError(RuntimeError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def _now_ms() -> float:
    return time.monotonic() * 1000.0


def _safe_text(value: Any, limit: int = 120) -> str:
    s = " ".join(str(value or "").split())
    return s[:limit]


def browser_candidates(browser_path: str = "") -> list[str]:
    raw = str(browser_path or "").strip()
    out: list[str] = []
    if raw:
        out.append(raw)
    local = os.environ.get("LOCALAPPDATA", "")
    for pat in (os.path.join(local, "ms-playwright", "chromium-*", "chrome-win64", "chrome.exe"),
                os.path.join(local, "ms-playwright", "chromium-*", "chrome-win", "chrome.exe")):
        for p in sorted(glob.glob(pat), reverse=True):
            if p not in out:
                out.append(p)
    for p in (
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    ):
        if p and p not in out:
            out.append(p)
    return out


def _browser_candidates(settings: StrategySettings) -> list[str]:
    return browser_candidates(str(settings.options.get("browser_path") or ""))


def browser_runtime_available(settings: Optional[StrategySettings] = None) -> tuple[bool, str]:
    """آیا یک مرورگرِ اجراییِ Chromium رویِ این ماشین هست؟ بدونِ اجرا/network."""
    raw = str(settings.options.get("browser_path") or "") if settings else ""
    for cand in browser_candidates(raw):
        if cand and os.path.isfile(cand):
            return True, cand
    return False, ("no Chromium browser executable found; set browser_path or "
                   "install Edge/Chrome/Brave")


def active_cdp_url() -> str:
    """CDPِ hostِ پایدارِ مالک، فقط اگر همین حالا سالم باشد."""
    env = (os.environ.get("BORS_EXECUTION_CDP_URL") or "").strip()
    if env:
        return env
    try:
        import json as _json
        import urllib.request as _ur
        import bors_config
        path = (os.environ.get("BORS_BROWSER_HOST_STATUS") or
                os.path.join(bors_config.WORK_DIR, "bors_browser_host.json"))
        with open(path, encoding="utf-8") as f:
            data = _json.load(f)
        url = str((data or {}).get("cdp_url") or "").strip()
        if not url:
            return ""
        with _ur.urlopen(url.rstrip("/") + "/json/version", timeout=0.6) as r:
            return url if int(getattr(r, "status", 0) or 0) == 200 else ""
    except Exception:
        return ""


def default_profile_dir(strategy_id: str) -> str:
    base = os.path.join(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir(),
                        "BorsTerminal_Ultimate", "browser_profiles", strategy_id)
    os.makedirs(base, exist_ok=True)
    return base


# ── ۱) Mock driver ──────────────────────────────────────────────────────────
class MockBrowserDriver:
    """درایورِ بدونِ مرورگر برای گارد/benchmarkِ سریع.

    `on_submit` می‌تواند یک تابعِ محلی باشد که پاسخِ دِروازهٔ mock را برمی‌گرداند؛
    هیچ درخواستِ شبکه‌ای درِ این کلاس نیست.
    """
    name = "mock-browser"

    def __init__(self, *, order_url: str = "http://mock.local/order",
                 intercept_pattern: str = "**/mock/order*",
                 on_submit: Optional[Callable[[dict], dict]] = None,
                 initial_form: Optional[dict] = None,
                 headless: bool = True, **_: Any) -> None:
        self.order_url = order_url
        self.intercept_pattern = intercept_pattern
        self.on_submit = on_submit
        self.form = dict(initial_form or {"symbol": "", "price": "", "quantity": ""})
        self.events: list[dict[str, Any]] = []
        self.abort_request = False
        self.started = False
        self.closed = False
        self.last_request: Optional[dict] = None
        self.last_response: Optional[dict] = None
        self.click_count = 0
        self.form_open_count = 0
        # ── Round 14: dry-run guard و ردگیری نوشتن‌ها ──────────────────────
        self.dry_run_armed = False
        self.order_paths = ["/core/api/v2/order"]
        self.order_method = "POST"
        self.request_method = "POST"
        self.request_url = ""
        self.selector_counts: dict[str, int] = {}
        self.before_click: Optional[Callable[[], None]] = None
        self.before_wait: Optional[Callable[[], None]] = None
        self.observed_requests: list[dict[str, Any]] = []
        self.observed_writes: list[dict[str, Any]] = []
        self.blocked_writes: list[dict[str, Any]] = []
        self.escaped_writes: list[dict[str, Any]] = []
        self.order_endpoint_hits = 0
        self.suppress_response = False
        self.submit_visible = True
        self.submit_enabled = True
        self.submit_text = "ارسال خرید"
        self.side_text = "خرید"
        self.isin_text = ""
        self.closed_at: Optional[float] = None

    def start(self) -> None:
        self.started = True

    def goto(self, url: str, timeout_ms: int = 20000) -> dict[str, Any]:
        self.events.append({"kind": "goto", "url": url, "mono_ms": _now_ms()})
        return {"url": url}

    def url(self) -> str:
        return self.order_url

    def title(self) -> str:
        return "mock-order"

    def wait_for(self, selector: str, timeout_ms: int = 2000) -> bool:
        if self.before_wait is not None:
            self.before_wait()
        if "submit" in str(selector):
            return bool(self.submit_visible)
        return True

    def fill(self, selector: str, value: Any, timeout_ms: int = 2000) -> dict[str, Any]:
        key = str(selector).split("=")[-1].strip("[]'\"")
        self.form[key] = str(value)
        self.events.append({"kind": "fill", "selector": selector,
                            "value_len": len(str(value))})
        return {"ok": True}

    def read_value(self, selector: str) -> str:
        key = str(selector).split("=")[-1].strip("[]'\"")
        if "isin" in str(selector):
            return str(self.isin_text or self.form.get("isin", ""))
        return str(self.form.get(key, ""))

    def read_text(self, selector: str) -> str:
        if "submit" in str(selector):
            return str(self.submit_text)
        if "side" in str(selector):
            return str(self.side_text)
        key = str(selector).split("=")[-1].strip("[]'\"")
        return str(self.form.get(key, ""))

    def read_attr(self, selector: str, attr: str) -> str:
        if "submit" in str(selector) and str(attr).lower() == "aria-label":
            # در Mock، side_text همان شاهدِ سمت است؛ submit_text برچسبِ دکمه.
            return str(self.side_text or self.submit_text)
        if "side" in str(selector) and str(attr).lower() == "aria-label":
            return str(self.side_text)
        return ""

    def count(self, selector: str) -> int:
        return int(self.selector_counts.get(str(selector), 1))

    def is_enabled(self, selector: str) -> bool:
        if "submit" in str(selector):
            return bool(self.submit_enabled)
        return True

    def intercept(self, pattern: str, *, abort: bool = True) -> dict[str, Any]:
        self.dry_run_armed = False
        self.intercept_pattern = pattern
        self.abort_request = bool(abort)
        self.last_request = None
        self.last_response = None
        return {"pattern": pattern, "abort": bool(abort)}

    def dry_run_guard(self, order_paths: Optional[list[str]] = None,
                      order_method: str = "POST") -> dict[str, Any]:
        """گاردِ پیش‌فرضِ dry-run: همهٔ نوشتن‌ها abort می‌شوند، نه فقط الگویِ کاربر."""
        self.dry_run_armed = True
        self.abort_request = True
        self.order_paths = [str(p or "") for p in (order_paths or []) if str(p or "")]
        if not self.order_paths:
            self.order_paths = ["/core/api/v2/order"]
        self.order_method = str(order_method or "POST").upper()
        self.last_request = None
        self.last_response = None
        self.observed_requests = []
        self.observed_writes = []
        self.blocked_writes = []
        self.escaped_writes = []
        return {"dry_run_guard": True, "order_paths": list(self.order_paths),
                "order_method": self.order_method}

    def request_hosts(self) -> list[str]:
        return [urlparse(self.order_url).netloc]

    def _classify_write(self, method: str, path: str) -> str:
        norm = (path or "/").rstrip("/") or "/"
        known = {(str(p or "/").rstrip("/") or "/") for p in self.order_paths}
        if norm not in known:
            return "other_write"
        return ("order" if str(method).upper() == self.order_method
                else "order_method_mismatch")

    def _request(self, payload: Optional[dict] = None) -> Optional[dict[str, Any]]:
        method = str(self.request_method or "POST").upper()
        url = str(self.request_url or self.order_url)
        path = urlparse(url).path or "/"
        is_write = method not in ("GET", "HEAD", "OPTIONS", "TRACE")
        entry = {"mono_ms": _now_ms(), "payload": dict(payload or self.form),
                 "url": url, "method": method, "path": path}
        self.observed_requests.append(entry)
        if not is_write:
            # Mockِ خواندن: هیچ درخواستِ سفارشی ساخته نمی‌شود.
            self.last_request = None
            return None
        self.observed_writes.append(entry)
        if self.dry_run_armed:
            classification = self._classify_write(method, path)
            blocked = {**entry, "classification": classification, "blocked": True}
            self.blocked_writes.append(blocked)
            self.last_request = blocked
            self.last_response = {"aborted": True, "mono_ms": _now_ms(),
                                  "status": None, "body": None,
                                  "url": url, "method": method,
                                  "classification": classification}
            self.events.append({"kind": "request_blocked",
                                "classification": classification})
            return self.last_response
        self.last_request = entry
        self.events.append({"kind": "request", "mono_ms": entry["mono_ms"]})
        if self.abort_request:
            self.last_response = {"aborted": True, "mono_ms": _now_ms(),
                                  "status": None, "body": None,
                                  "url": url, "method": method}
            self.events.append({"kind": "request_aborted"})
            return self.last_response
        if self._classify_write(method, path) == "order":
            self.order_endpoint_hits += 1
        if self.suppress_response:
            self.last_response = None
            self.events.append({"kind": "request_no_response"})
            return None
        response = self.on_submit(dict(entry["payload"])) if self.on_submit else {
            "status": 200, "body": {"isSuccessful": True, "id": "MOCK-1"}}
        self.last_response = {
            "mono_ms": _now_ms(),
            "status": response.get("status") if isinstance(response, dict) else None,
            "body": response.get("body") if isinstance(response, dict) else None,
            "url": url, "method": method,
        }
        self.events.append({"kind": "response", "status": self.last_response["status"]})
        return self.last_response

    def open_form(self, selector: str, timeout_ms: int = 1200) -> dict[str, Any]:
        """بازکردنِ فرم در Mock: هیچ درخواستِ سفارشی ساخته نمی‌شود."""
        self.form_open_count += 1
        self.events.append({"kind": "open_form", "selector": selector,
                            "mono_ms": _now_ms()})
        return {"ok": True, "opened": True}

    def click(self, selector: str, timeout_ms: int = 1200,
              force: bool = False) -> dict[str, Any]:
        start = _now_ms()
        self.click_count += 1
        self.events.append({"kind": "click", "selector": selector,
                            "start_ms": start, "count": self.click_count})
        if self.before_click is not None:
            self.before_click()
        response = self._request()
        return {"start_ms": start, "end_ms": _now_ms(), "response": response,
                "clicked": True}

    def press(self, key: str, selector: str = "", timeout_ms: int = 1200) -> dict[str, Any]:
        start = _now_ms()
        self.events.append({"kind": "key", "key": key, "selector": selector,
                            "start_ms": start})
        response = None
        if str(key).strip().lower() in ("enter", "return", "space", " "):
            response = self._request()
        return {"start_ms": start, "end_ms": _now_ms(), "response": response}

    def evaluate(self, js: str, arg: Any = None) -> Any:
        start = _now_ms()
        self.events.append({"kind": "evaluate", "start_ms": start})
        if "fetch" in str(js):
            response = self._request(arg if isinstance(arg, dict) else None)
            return response
        return {"ok": True}

    def wait_for_request(self, timeout_ms: int = 2000) -> Optional[dict[str, Any]]:
        return self.last_request

    def wait_for_response(self, timeout_ms: int = 2000) -> Optional[dict[str, Any]]:
        return self.last_response

    def probe(self, selectors: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
        sel = {str(k): str(v) for k, v in (selectors or {}).items() if v}
        return {
            "url": urlparse(self.order_url).path or "/",
            "title": "mock-order",
            "inputs": [{"tag": "input", "type": "text", "name": k,
                        "visible": True, "enabled": True, "readonly": False}
                       for k in sel],
            "buttons": [{"tag": "button", "text": "send",
                         "visible": True, "enabled": True}],
            "selectors": {k: {"count": 1, "first_visible": True,
                              "first_enabled": True} for k in sel},
            "login_candidates": [],
        }

    def network(self) -> dict[str, Any]:
        by_host: dict[str, dict[str, int]] = {}
        for r in self.observed_requests:
            host = str(r.get("url") or "").split("/")[2] if "//" in str(r.get("url") or "") else ""
            bucket = by_host.setdefault(host or "(none)", {})
            m = str(r.get("method") or "").upper()
            bucket[m] = bucket.get(m, 0) + 1
        order_writes = sum(1 for r in self.blocked_writes
                           if r.get("classification") == "order")
        other_writes = sum(1 for r in self.blocked_writes
                           if r.get("classification") == "other_write")
        mismatch = sum(1 for r in self.blocked_writes
                       if r.get("classification") == "order_method_mismatch")
        return {
            "requests": len(self.observed_requests),
            "writes": len(self.observed_writes),
            "blocked_writes": len(self.blocked_writes),
            "escaped_writes": len(self.escaped_writes),
            "order_writes": order_writes,
            "other_writes": other_writes,
            "order_method_mismatch": mismatch,
            "order_endpoint_hits": self.order_endpoint_hits,
            "by_host": by_host,
            "order_posts": order_writes,
            "truncated": False,
            "source": "mock-dry-run-guard" if self.dry_run_armed else "mock-no-network",
        }

    def screenshot(self, path: str) -> str:
        return path

    def close(self) -> None:
        self.closed = True

    def is_alive(self) -> bool:
        return self.started and not self.closed


# ── ۲) Playwright driver ────────────────────────────────────────────────────
class _Cmd:
    __slots__ = ("name", "kwargs", "reply")

    def __init__(self, name: str, kwargs: dict[str, Any], reply: queue.Queue):
        self.name = name
        self.kwargs = kwargs
        self.reply = reply


class PlaywrightBrowserDriver:
    """همهٔ فراخوانی‌های Playwright درِ یک threadِ اختصاصی می‌مانند."""
    name = "playwright"

    def __init__(self, settings: StrategySettings, *, strategy_id: str,
                 profile_dir: Optional[str] = None) -> None:
        self.settings = settings
        self.strategy_id = strategy_id
        self.profile_dir = (profile_dir or str(settings.options.get("profile_dir") or "")
                            or default_profile_dir(strategy_id))
        self.headless = bool(settings.options.get("headless", False))
        self.cdp_url = str(settings.options.get("cdp_url") or active_cdp_url() or "").strip()
        self._cdp = bool(self.cdp_url)
        self.action_timeout_ms = int(settings.options.get("action_timeout_ms") or 1200)
        self.navigation_timeout_ms = int(settings.options.get("navigation_timeout_ms") or 20000)
        self._q: queue.Queue[_Cmd] = queue.Queue()
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_error: Optional[str] = None
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._intercept_pattern = str(settings.options.get("intercept_pattern") or "")
        self._current_route_pattern = ""
        self._abort_request = True
        self._events: list[dict[str, Any]] = []
        self._all_requests: list[dict[str, Any]] = []
        self._last_request: Optional[dict[str, Any]] = None
        self._last_response: Optional[dict[str, Any]] = None
        self._lock = threading.Lock()
        # ── Round 14: گاردِ dry-run مستقل از الگویِ کاربر ─────────────────
        self._dry_run_guard = False
        self._order_paths = ["/core/api/v2/order"]
        self._order_method = "POST"
        self._observed_writes: list[dict[str, Any]] = []
        self._blocked_writes: list[dict[str, Any]] = []
        self._escaped_writes: list[dict[str, Any]] = []

    # ---- lifecycle ----
    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="bors-browser-%s" % self.strategy_id,
                                        daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=30):
            raise BrowserUnavailable("browser start timed out")
        if self._start_error:
            raise BrowserUnavailable(self._start_error)

    def _loop(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:                       # noqa: BLE001
            self._start_error = "playwright unavailable: %s" % type(e).__name__
            self._ready.set()
            return
        try:
            self._pw = sync_playwright().start()
            if self._cdp:
                # اتصال به hostِ مالک؛ همان context/صفحه را استفاده می‌کنیم و
                # هرگز مرورگر را نمی‌بندیم (فقط اتصال را قطع می‌کنیم).
                self._browser = self._pw.chromium.connect_over_cdp(self.cdp_url)
                contexts = self._browser.contexts
                self._context = contexts[0] if contexts else self._browser.new_context()
                wanted = urlparse(str(self.settings.options.get("order_url") or "")).netloc.lower()
                pages = [p for p in self._context.pages
                         if not str(p.url).startswith("about:")]
                matched = [p for p in pages
                           if wanted and urlparse(p.url).netloc.lower() == wanted]
                # صفحهٔ همان دامنه را برمی‌گزینیم؛ دیالوگ‌هایِ اولیهٔ مرورگر
                # (مثلِ sync-confirmation) نباید به‌جایِ تبِ مالک انتخاب شوند.
                self._page = (matched[0] if matched else
                              (pages[0] if pages else
                               (self._context.pages[0] if self._context.pages
                                else self._context.new_page())))
                self._page.set_default_timeout(self.action_timeout_ms)
                self._page.set_default_navigation_timeout(self.navigation_timeout_ms)
                self._page.on("request", self._request_handler)
                self._attach_response_listener()
                self._ready.set()
                self._serve_loop()
                return
            exe = ""
            for cand in _browser_candidates(self.settings):
                if cand and os.path.isfile(cand):
                    exe = cand
                    break
            if not exe:
                try:
                    cand = self._pw.chromium.executable_path
                    exe = cand if cand and os.path.isfile(cand) else ""
                except Exception:
                    exe = ""
            if not exe:
                raise BrowserUnavailable("no Chromium browser executable found")
            args = ["--no-first-run", "--no-default-browser-check",
                    "--disable-extensions", "--disable-background-networking"]
            if bool(self.settings.options.get("no_proxy")):
                args.append("--no-proxy-server")
            ignore_tls = bool(self.settings.options.get("ignore_https_errors"))
            user_dir = self.profile_dir or None
            if user_dir:
                os.makedirs(user_dir, exist_ok=True)
                self._context = self._pw.chromium.launch_persistent_context(
                    user_data_dir=user_dir, headless=self.headless,
                    executable_path=exe, args=args,
                    ignore_https_errors=ignore_tls,
                    viewport={"width": 1366, "height": 900})
                self._page = (self._context.pages[0] if self._context.pages
                              else self._context.new_page())
            else:
                self._browser = self._pw.chromium.launch(
                    headless=self.headless, executable_path=exe, args=args)
                self._context = self._browser.new_context(
                    ignore_https_errors=ignore_tls,
                    viewport={"width": 1366, "height": 900})
                self._page = self._context.new_page()
            self._page.set_default_timeout(self.action_timeout_ms)
            self._page.set_default_navigation_timeout(self.navigation_timeout_ms)
            self._page.on("request", self._request_handler)
            self._attach_response_listener()
            self._ready.set()
            self._serve_loop()
        except Exception as e:                       # noqa: BLE001
            self._start_error = "%s: %s" % (type(e).__name__, str(e)[:180])
            self._ready.set()
        finally:
            if not self._cdp:
                try:
                    if self._context is not None:
                        self._context.close()
                except Exception:
                    pass
            try:
                if self._pw is not None:
                    self._pw.stop()
            except Exception:
                pass

    def _serve_loop(self) -> None:
        while not self._stop.is_set():
            try:
                cmd = self._q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                fn = getattr(self, "_do_" + cmd.name)
                cmd.reply.put(("ok", fn(**cmd.kwargs)))
            except Exception as e:                   # noqa: BLE001
                cmd.reply.put(("err", "%s: %s" % (type(e).__name__, str(e)[:180])))

    def _call(self, name: str, **kwargs: Any) -> Any:
        if self._thread is None:
            self.start()
        if self._start_error:
            raise BrowserUnavailable(self._start_error)
        rq: queue.Queue = queue.Queue(maxsize=1)
        self._q.put(_Cmd(name, kwargs, rq))
        try:
            status, payload = rq.get(timeout=self.action_timeout_ms / 1000.0 + 30)
        except queue.Empty:
            raise BrowserCommandError("browser command timed out: %s" % name) from None
        if status == "err":
            raise BrowserCommandError(str(payload))
        return payload

    def _request_handler(self, req: Any) -> None:
        try:
            p = urlparse(req.url)
            entry = {"host": p.netloc, "path": (p.path or "/")[:160],
                     "method": str(getattr(req, "method", "") or "")}
            with self._lock:
                if len(self._all_requests) < 500:
                    self._all_requests.append(entry)
        except Exception:
            return

    def _attach_response_listener(self) -> None:
        page = self._page

        def on_response(resp):
            try:
                pattern = self._intercept_pattern or ""
                needle = pattern.replace("**/", "").rstrip("*")
                if needle and needle not in resp.url:
                    return
                entry = {"mono_ms": _now_ms(), "status": int(resp.status),
                         "url": resp.url,
                         "method": str(getattr(resp.request, "method", "") or ""),
                         "content_type": str(resp.headers.get("content-type") or "")[:60]}
                if entry["method"] == "POST":
                    try:
                        raw = resp.body()
                        entry["body"] = raw.decode("utf-8", "replace")[:4000]
                    except Exception:
                        entry["body"] = None
                with self._lock:
                    self._last_response = entry
                    self._events.append({"kind": "response", **entry})
            except Exception:
                return

        page.on("response", on_response)

    @staticmethod
    def _classify_guard_write(method: str, path: str,
                              order_paths: list[str],
                              order_method: str) -> str:
        norm = (path or "/").rstrip("/") or "/"
        known = {(str(p or "/").rstrip("/") or "/") for p in order_paths}
        if norm not in known:
            return "other_write"
        return ("order" if str(method).upper() == order_method
                else "order_method_mismatch")

    def _route_handler(self, route) -> None:
        req = route.request
        method = str(getattr(req, "method", "") or "").upper()
        url = str(req.url or "")
        path = urlparse(url).path or "/"
        is_write = method not in ("GET", "HEAD", "OPTIONS", "TRACE")
        entry = {"mono_ms": _now_ms(), "url": url, "method": method,
                 "path": path}
        with self._lock:
            # `_request_handler` قبلاً همین request را در `_all_requests` ثبت
            # می‌کند؛ ثبتِ دوباره اینجا writes را دوبرابر و dry-run را کاذب
            # escape می‌کرد.
            if is_write:
                self._observed_writes.append(entry)
        if self._dry_run_guard:
            if not is_write:
                # خواندن‌ها می‌توانند ادامه پیدا کنند؛ گارد فقط نوشتن را می‌بندد.
                try:
                    route.continue_()
                except Exception:
                    pass
                return
            classification = self._classify_guard_write(
                method, path, list(self._order_paths), self._order_method)
            blocked = {**entry, "classification": classification,
                       "blocked": True}
            with self._lock:
                self._last_request = blocked
                self._blocked_writes.append(blocked)
                self._events.append({"kind": "request_blocked",
                                     "classification": classification})
            try:
                route.abort()
            except Exception:
                with self._lock:
                    self._escaped_writes.append(blocked)
                    self._events.append({"kind": "request_escape",
                                         "classification": classification})
            return
        with self._lock:
            self._last_request = entry
            self._events.append({"kind": "request", **entry})
        try:
            if self._abort_request:
                self._events.append({"kind": "request_aborted", "mono_ms": _now_ms()})
                route.abort()
            else:
                route.continue_()
        except Exception:
            try:
                route.abort()
            except Exception:
                pass

    # ---- commands (executed on the browser thread) ----
    def _do_goto(self, url: str, timeout_ms: int = 0) -> dict[str, Any]:
        if self._cdp:
            try:
                if urlparse(self._page.url).netloc.lower() == urlparse(url).netloc.lower():
                    return {"url": self._page.url, "title": self._page.title()}
            except Exception:
                pass
        self._page.goto(url, wait_until="domcontentloaded",
                        timeout=timeout_ms or self.navigation_timeout_ms)
        return {"url": self._page.url, "title": self._page.title()}

    def _do_url(self) -> str:
        return self._page.url

    def _do_title(self) -> str:
        return self._page.title()

    def _do_wait_for(self, selector: str, timeout_ms: int = 2000) -> bool:
        try:
            self._page.locator(selector).first.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def _do_fill(self, selector: str, value: Any, timeout_ms: int = 0) -> dict[str, Any]:
        loc = self._page.locator(selector).first
        loc.fill(str(value), timeout=timeout_ms or self.action_timeout_ms)
        return {"ok": True}

    def _do_read_value(self, selector: str) -> str:
        try:
            return self._page.locator(selector).first.input_value(timeout=self.action_timeout_ms)
        except Exception:
            return ""

    def _do_read_text(self, selector: str) -> str:
        try:
            return _safe_text(self._page.locator(selector).first.inner_text(
                timeout=self.action_timeout_ms))
        except Exception:
            return ""

    def _do_read_attr(self, selector: str, attr: str) -> str:
        try:
            return _safe_text(self._page.locator(selector).first.get_attribute(
                str(attr), timeout=self.action_timeout_ms))
        except Exception:
            return ""

    def _do_count(self, selector: str) -> int:
        try:
            return int(self._page.locator(selector).count())
        except Exception:
            return 0

    def _do_is_enabled(self, selector: str) -> bool:
        try:
            return bool(self._page.locator(selector).first.is_enabled())
        except Exception:
            return False

    def _do_intercept(self, pattern: str, abort: bool = True) -> dict[str, Any]:
        if self._page is None:
            return {"ok": False}
        # driverِ keep-alive بینِ سفارش‌ها زنده می‌ماند؛ routeِ قبلی و آخرین
        # request/response باید پاک شوند تا wait_for_request پاسخِ کهنه ندهد.
        with self._lock:
            self._last_request = None
            self._last_response = None
        if self._current_route_pattern:
            try:
                self._page.unroute(self._current_route_pattern)
            except Exception:
                pass
        self._dry_run_guard = False
        self._intercept_pattern = str(pattern)
        self._current_route_pattern = str(pattern)
        self._abort_request = bool(abort)
        with self._lock:
            self._observed_writes = []
            self._blocked_writes = []
            self._escaped_writes = []
            self._all_requests = []
        try:
            self._page.route(pattern, self._route_handler)
        except Exception as e:
            raise BrowserCommandError("route failed: %s" % str(e)[:120]) from None
        return {"pattern": pattern, "abort": bool(abort)}

    def _do_dry_run_guard(self, order_paths: list[str] | None = None,
                          order_method: str = "POST") -> dict[str, Any]:
        """گاردِ catch-all: هر نوشتن abort می‌شود، بی‌توجه به الگویِ کاربر."""
        if self._page is None:
            return {"ok": False}
        with self._lock:
            self._last_request = None
            self._last_response = None
            self._observed_writes = []
            self._blocked_writes = []
            self._escaped_writes = []
            # شمارشِ شبکه فقط برایِ همین action باشد؛ درایورِ keep-alive
            # نباید نوشتن‌هایِ اجرایِ قبلی را در dry-runِ تازه بشمارد.
            self._all_requests = []
        if self._current_route_pattern:
            try:
                self._page.unroute(self._current_route_pattern)
            except Exception:
                pass
        paths = [str(p or "") for p in (order_paths or []) if str(p or "")]
        self._order_paths = paths or ["/core/api/v2/order"]
        self._order_method = str(order_method or "POST").upper()
        self._dry_run_guard = True
        self._abort_request = True
        self._current_route_pattern = "**/*"
        self._intercept_pattern = "**/*"
        try:
            self._page.route("**/*", self._route_handler)
        except Exception as e:
            raise BrowserCommandError("dry-run guard route failed: %s" % str(e)[:120]) from None
        return {"dry_run_guard": True, "order_paths": list(self._order_paths),
                "order_method": self._order_method}

    def _do_click(self, selector: str, timeout_ms: int = 0,
                  force: bool = False) -> dict[str, Any]:
        start = _now_ms()
        # بدونِ .first: تطبیقِ چندگانه باید strict-mode خطا بدهد، نه کلیکِ کور.
        loc = self._page.locator(selector)
        loc.click(force=bool(force), timeout=timeout_ms or self.action_timeout_ms)
        return {"start_ms": start, "end_ms": _now_ms(), "clicked": True}

    def _do_press(self, key: str, selector: str = "",
                  timeout_ms: int = 0) -> dict[str, Any]:
        start = _now_ms()
        if selector:
            self._page.locator(selector).first.focus(timeout=timeout_ms or self.action_timeout_ms)
        self._page.keyboard.press(key)
        return {"start_ms": start, "end_ms": _now_ms()}

    def _do_evaluate(self, js: str, arg: Any = None) -> Any:
        return self._page.evaluate(js, arg)

    def _do_last_request(self) -> Optional[dict[str, Any]]:
        with self._lock:
            return dict(self._last_request) if self._last_request else None

    def _do_last_response(self) -> Optional[dict[str, Any]]:
        with self._lock:
            return dict(self._last_response) if self._last_response else None

    def _pump(self, ms: int = 2) -> None:
        """Playwright eventها را فقط با یک فراخوانیِ API dispatch می‌کند؛
        `time.sleep` خالص یعنی eventِ response هرگز نمی‌رسد (سنجش 2026-10-20)."""
        self._page.wait_for_timeout(max(1, int(ms)))

    def _do_wait_request(self, timeout_ms: int = 2000) -> Optional[dict[str, Any]]:
        deadline = time.monotonic() + max(0.0, timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            with self._lock:
                if self._last_request:
                    return dict(self._last_request)
            self._pump()
        return None

    def _do_wait_response(self, timeout_ms: int = 2000) -> Optional[dict[str, Any]]:
        deadline = time.monotonic() + max(0.0, timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            with self._lock:
                if self._last_response:
                    return dict(self._last_response)
            self._pump()
        return None

    def _do_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)

    def _do_request_hosts(self) -> list[str]:
        with self._lock:
            return sorted({r["host"] for r in self._all_requests
                           if r.get("host") and r["host"] not in ("", "about:blank")})

    def _do_network(self) -> dict[str, Any]:
        """شمارشِ متد/میزبان برای شواهدِ فقط‌خواندنی؛ مسیرها برنمی‌گردند.

        `order_posts` هر POSTِ منطبق با الگویِ interception است (پیش‌فرض:
        مسیرِ سفارش)؛ در Probe باید صفر بماند.
        """
        with self._lock:
            reqs = list(self._all_requests)
            truncated = len(self._all_requests) >= 500
            blocked = list(self._blocked_writes)
            escaped = list(self._escaped_writes)
        by_host: dict[str, dict[str, int]] = {}
        for r in reqs:
            host = str(r.get("host") or urlparse(str(r.get("url") or "")).netloc or "(none)")
            method = (str(r.get("method") or "").upper() or "(none)")
            bucket = by_host.setdefault(host, {})
            bucket[method] = bucket.get(method, 0) + 1
        needle = (self._intercept_pattern or "").replace("**/", "").rstrip("*")
        writes = [r for r in reqs
                  if str(r.get("method") or "").upper() not in
                  ("GET", "HEAD", "OPTIONS", "TRACE")]
        order_writes = sum(1 for r in blocked
                           if r.get("classification") == "order")
        other_writes = sum(1 for r in blocked
                           if r.get("classification") == "other_write")
        mismatch = sum(1 for r in blocked
                       if r.get("classification") == "order_method_mismatch")
        order_posts = order_writes if self._dry_run_guard else sum(
            1 for r in reqs
            if (str(r.get("method") or "").upper() == "POST"
                and needle and needle in str(r.get("path") or "")))
        return {"requests": len(reqs), "by_host": by_host,
                "writes": len(writes), "blocked_writes": len(blocked),
                "escaped_writes": len(escaped),
                "order_writes": order_writes, "other_writes": other_writes,
                "order_method_mismatch": mismatch,
                "order_posts": order_posts, "truncated": truncated,
                "source": ("browser-dry-run-guard" if self._dry_run_guard
                           else "browser-events"),
                "order_path_matched": bool(needle)}

    def _do_probe(self, selectors: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
        """فقط‌خواندنی؛ SPAهایی که پس از load به صفحهٔ ورود می‌روند را هم می‌پذیرد.

        EasyTrader پس از `goto` یک ریدایرکتِ سمتِ کلاینت می‌زند و
        `Execution context was destroyed` می‌دهد. این‌جا فقط همان خطا با
        انتظارِ کوتاه و تلاشِ دوباره پاسخ داده می‌شود؛ هیچ کلیک/ارسال/مقداری
        خوانده نمی‌شود.
        """
        js = """(selectors) => {
          const clean = (s, n) => String(s || '')
            .replace(/[0-9\\u06F0-\\u06F9\\u0660-\\u0669]/g, '•')
            .replace(/\\s+/g, ' ').trim().slice(0, n);
          const vis = el => { try {
            const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
            return !!(r.width || r.height) && s.visibility !== 'hidden'
              && s.display !== 'none' && Number(s.opacity) !== 0;
          } catch (e) { return false; } };
          const inputs = Array.from(document.querySelectorAll('input,select,textarea')).slice(0, 60).map(el => ({
            tag: el.tagName.toLowerCase(), type: clean(el.getAttribute('type'), 24),
            name: clean(el.getAttribute('name'), 60), id: clean(el.id, 60),
            testid: clean(el.getAttribute('data-testid'), 60),
            aria: clean(el.getAttribute('aria-label'), 80),
            placeholder: clean(el.getAttribute('placeholder'), 80),
            visible: vis(el), enabled: !el.disabled, readonly: !!el.readOnly
          }));
          const buttons = Array.from(document.querySelectorAll('button,[role=button],a')).slice(0, 80).map(el => ({
            tag: el.tagName.toLowerCase(), text: clean(el.innerText, 60),
            id: clean(el.id, 60), testid: clean(el.getAttribute('data-testid'), 60),
            aria: clean(el.getAttribute('aria-label'), 80),
            visible: vis(el), enabled: !el.disabled
          })).filter(x => x.text || x.id || x.testid || x.aria);
          const matches = {};
          for (const [k, s] of Object.entries(selectors || {})) {
            if (!s) continue;
            let nodes = []; try { nodes = Array.from(document.querySelectorAll(s)); } catch (e) {}
            matches[k] = {count: nodes.length, first_visible: nodes.some(vis),
                          first_enabled: nodes.some(el => !el.disabled)};
          }
          const loginCandidates = buttons.filter(b => /ورود|login|sign\\s*in|ثبت\\s*نام/i.test(b.text || '')).slice(0, 10);
          return {url: location.pathname, title: clean(document.title, 80),
                  inputs, buttons, selectors: matches,
                  login_candidates: loginCandidates};
        }"""
        try:
            self._page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass
        arg = dict(selectors or {})
        last: Optional[str] = None
        for _ in range(3):
            before = self._page.url
            try:
                got = self._page.evaluate(js, arg)
            except Exception as e:                   # noqa: BLE001
                msg = str(e)
                if "Execution context was destroyed" not in msg:
                    raise
                last = msg[:160]
                try:
                    self._page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass
                try:
                    self._page.wait_for_timeout(300)
                except Exception:
                    pass
                continue
            if self._page.url != before:
                # ریدایرکتِ SPA در حینِ سنجش؛ نتیجهٔ صفحهٔ قبلی معتبر نیست.
                self._page.wait_for_timeout(300)
                continue
            if isinstance(got, dict):
                return got
            break
        if last:
            raise BrowserCommandError("probe: صفحه مدام در حالِ ناوبری است (%s)" % last)
        return {"url": urlparse(self._page.url).path or "/",
                "title": self._page.title(), "inputs": [], "buttons": [],
                "selectors": {}, "login_candidates": []}

    def _do_screenshot(self, path: str) -> str:
        self._page.screenshot(path=path, full_page=False)
        return path

    def _do_close(self) -> None:
        self._stop.set()

    # ---- public API (thread-safe via queue) ----
    def goto(self, url: str, timeout_ms: int = 0) -> dict[str, Any]:
        return self._call("goto", url=url, timeout_ms=timeout_ms)

    def url(self) -> str:
        return self._call("url")

    def title(self) -> str:
        return self._call("title")

    def wait_for(self, selector: str, timeout_ms: int = 2000) -> bool:
        return bool(self._call("wait_for", selector=selector, timeout_ms=timeout_ms))

    def fill(self, selector: str, value: Any, timeout_ms: int = 0) -> dict[str, Any]:
        return self._call("fill", selector=selector, value=value, timeout_ms=timeout_ms)

    def read_value(self, selector: str) -> str:
        return str(self._call("read_value", selector=selector))

    def read_text(self, selector: str) -> str:
        return str(self._call("read_text", selector=selector))

    def read_attr(self, selector: str, attr: str) -> str:
        return str(self._call("read_attr", selector=selector, attr=attr))

    def count(self, selector: str) -> int:
        return int(self._call("count", selector=selector))

    def is_enabled(self, selector: str) -> bool:
        return bool(self._call("is_enabled", selector=selector))

    def intercept(self, pattern: str, *, abort: bool = True) -> dict[str, Any]:
        return self._call("intercept", pattern=pattern, abort=abort)

    def dry_run_guard(self, order_paths: Optional[list[str]] = None,
                      order_method: str = "POST") -> dict[str, Any]:
        return self._call("dry_run_guard", order_paths=list(order_paths or []),
                          order_method=order_method)

    def click(self, selector: str, timeout_ms: int = 0,
              force: bool = False) -> dict[str, Any]:
        return self._call("click", selector=selector, timeout_ms=timeout_ms,
                          force=force)

    def open_form(self, selector: str, timeout_ms: int = 0) -> dict[str, Any]:
        """کلیکِ «بازکردن فرم»؛ در صفحهٔ واقعی یک کلیک است، نه ارسال."""
        return self.click(selector, timeout_ms=timeout_ms, force=True)

    def press(self, key: str, selector: str = "", timeout_ms: int = 0) -> dict[str, Any]:
        return self._call("press", key=key, selector=selector, timeout_ms=timeout_ms)

    def evaluate(self, js: str, arg: Any = None) -> Any:
        return self._call("evaluate", js=js, arg=arg)

    def last_request(self) -> Optional[dict[str, Any]]:
        return self._call("last_request")

    def last_response(self) -> Optional[dict[str, Any]]:
        return self._call("last_response")

    def wait_for_request(self, timeout_ms: int = 2000) -> Optional[dict[str, Any]]:
        return self._call("wait_request", timeout_ms=timeout_ms)

    def wait_for_response(self, timeout_ms: int = 2000) -> Optional[dict[str, Any]]:
        return self._call("wait_response", timeout_ms=timeout_ms)

    def events(self) -> list[dict[str, Any]]:
        return list(self._call("events"))

    def request_hosts(self) -> list[str]:
        try:
            return list(self._call("request_hosts"))
        except Exception:
            return []

    def network(self) -> dict[str, Any]:
        try:
            return dict(self._call("network"))
        except Exception:
            return {"requests": None, "by_host": {}, "order_posts": None,
                    "truncated": None, "source": "unavailable"}

    def probe(self, selectors: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
        return self._call("probe", selectors=dict(selectors or {}))

    def screenshot(self, path: str) -> str:
        return str(self._call("screenshot", path=path))

    def close(self) -> None:
        if self._thread is None:
            return
        try:
            self._call("close")
        except Exception:
            pass
        self._stop.set()
        self._thread.join(timeout=10)
        self._thread = None

    def is_alive(self) -> bool:
        return bool(self._thread is not None and self._thread.is_alive()
                    and not self._start_error)


def make_driver(settings: StrategySettings, *, strategy_id: str,
                mock: bool = False, **mock_kwargs: Any):
    if mock:
        return MockBrowserDriver(**mock_kwargs)
    return PlaywrightBrowserDriver(settings, strategy_id=strategy_id)


__all__ = ["BrowserUnavailable", "BrowserCommandError", "MockBrowserDriver",
           "PlaywrightBrowserDriver", "make_driver", "default_profile_dir"]
