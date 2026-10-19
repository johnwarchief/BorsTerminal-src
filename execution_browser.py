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
        return True

    def fill(self, selector: str, value: Any, timeout_ms: int = 2000) -> dict[str, Any]:
        key = str(selector).split("=")[-1].strip("[]'\"")
        self.form[key] = str(value)
        self.events.append({"kind": "fill", "selector": selector,
                            "value_len": len(str(value))})
        return {"ok": True}

    def read_value(self, selector: str) -> str:
        key = str(selector).split("=")[-1].strip("[]'\"")
        return str(self.form.get(key, ""))

    def read_text(self, selector: str) -> str:
        key = str(selector).split("=")[-1].strip("[]'\"")
        return str(self.form.get(key, ""))

    def is_enabled(self, selector: str) -> bool:
        return True

    def intercept(self, pattern: str, *, abort: bool = True) -> dict[str, Any]:
        self.intercept_pattern = pattern
        self.abort_request = bool(abort)
        self.last_request = None
        self.last_response = None
        return {"pattern": pattern, "abort": bool(abort)}

    def request_hosts(self) -> list[str]:
        return [urlparse(self.order_url).netloc]

    def _request(self, payload: Optional[dict] = None) -> dict[str, Any]:
        self.last_request = {"mono_ms": _now_ms(), "payload": dict(payload or self.form),
                             "url": self.order_url, "method": "POST"}
        self.events.append({"kind": "request", "mono_ms": self.last_request["mono_ms"]})
        if self.abort_request:
            self.last_response = {"aborted": True, "mono_ms": _now_ms(),
                                  "status": None, "body": None,
                                  "url": self.order_url, "method": "POST"}
            self.events.append({"kind": "request_aborted"})
            return self.last_response
        response = self.on_submit(dict(self.last_request["payload"])) if self.on_submit else {
            "status": 200, "body": {"isSuccessful": True, "id": "MOCK-1"}}
        self.last_response = {
            "mono_ms": _now_ms(),
            "status": response.get("status") if isinstance(response, dict) else None,
            "body": response.get("body") if isinstance(response, dict) else None,
            "url": self.order_url, "method": "POST",
        }
        self.events.append({"kind": "response", "status": self.last_response["status"]})
        return self.last_response

    def click(self, selector: str, timeout_ms: int = 1200,
              force: bool = True) -> dict[str, Any]:
        start = _now_ms()
        self.click_count += 1
        self.events.append({"kind": "click", "selector": selector,
                            "start_ms": start, "count": self.click_count})
        response = self._request()
        return {"start_ms": start, "end_ms": _now_ms(), "response": response}

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
        return {"url": self.order_url, "title": "mock-order",
                "inputs": [{"selector": s, "tag": "input"}
                           for s in (selectors or {}).values() if s],
                "buttons": [], "login_present": False}

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
        self.action_timeout_ms = int(settings.options.get("action_timeout_ms") or 1200)
        self.navigation_timeout_ms = int(settings.options.get("navigation_timeout_ms") or 20000)
        self._q: queue.Queue[_Cmd] = queue.Queue()
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_error: Optional[str] = None
        self._pw = None
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
            while not self._stop.is_set():
                try:
                    cmd = self._q.get(timeout=0.2)
                except queue.Empty:
                    continue
                try:
                    fn = getattr(self, "_do_" + cmd.name)
                    cmd.reply.put(("ok", fn(**cmd.kwargs)))
                except Exception as e:               # noqa: BLE001
                    cmd.reply.put(("err", "%s: %s" % (type(e).__name__, str(e)[:180])))
        except Exception as e:                       # noqa: BLE001
            self._start_error = "%s: %s" % (type(e).__name__, str(e)[:180])
            self._ready.set()
        finally:
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

    def _route_handler(self, route) -> None:
        with self._lock:
            self._last_request = {"mono_ms": _now_ms(), "url": route.request.url,
                                  "method": route.request.method}
            self._events.append({"kind": "request", **self._last_request})
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
        self._intercept_pattern = str(pattern)
        self._current_route_pattern = str(pattern)
        self._abort_request = bool(abort)
        try:
            self._page.route(pattern, self._route_handler)
        except Exception as e:
            raise BrowserCommandError("route failed: %s" % str(e)[:120]) from None
        return {"pattern": pattern, "abort": bool(abort)}

    def _do_click(self, selector: str, timeout_ms: int = 0,
                  force: bool = True) -> dict[str, Any]:
        start = _now_ms()
        loc = self._page.locator(selector).first
        loc.click(force=bool(force), timeout=timeout_ms or self.action_timeout_ms)
        return {"start_ms": start, "end_ms": _now_ms()}

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

    def _do_probe(self, selectors: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
        js = """() => {
          const clean = (s, n) => String(s || '').replace(/\\s+/g, ' ').trim().slice(0, n);
          const inputs = Array.from(document.querySelectorAll('input,select,textarea')).slice(0, 60).map(el => ({
            tag: el.tagName.toLowerCase(), type: clean(el.getAttribute('type'), 24),
            name: clean(el.getAttribute('name'), 60), id: clean(el.id, 60),
            testid: clean(el.getAttribute('data-testid'), 60),
            aria: clean(el.getAttribute('aria-label'), 80),
            placeholder: clean(el.getAttribute('placeholder'), 80)
          }));
          const buttons = Array.from(document.querySelectorAll('button,[role=button],a')).slice(0, 80).map(el => ({
            tag: el.tagName.toLowerCase(), text: clean(el.innerText, 60),
            id: clean(el.id, 60), testid: clean(el.getAttribute('data-testid'), 60),
            aria: clean(el.getAttribute('aria-label'), 80)
          })).filter(x => x.text || x.id || x.testid || x.aria);
          return {url: location.href, title: document.title, inputs, buttons};
        }"""
        got = self._page.evaluate(js)
        return got if isinstance(got, dict) else {"url": self._page.url, "title": self._page.title(),
                                                  "inputs": [], "buttons": []}

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

    def is_enabled(self, selector: str) -> bool:
        return bool(self._call("is_enabled", selector=selector))

    def intercept(self, pattern: str, *, abort: bool = True) -> dict[str, Any]:
        return self._call("intercept", pattern=pattern, abort=abort)

    def click(self, selector: str, timeout_ms: int = 0,
              force: bool = True) -> dict[str, Any]:
        return self._call("click", selector=selector, timeout_ms=timeout_ms,
                          force=force)

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

    def probe(self, selectors: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
        return self._call("probe", selectors=selectors)

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
