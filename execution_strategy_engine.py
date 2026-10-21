# -*- coding: utf-8 -*-
"""execution_strategy_engine.py — Strategyهای واقعیِ سرخطی و موتورِ مقایسه.

پیاده‌سازی‌ها:
  • DirectApiStrategy    — همان آداپتورِ HTTPِ موجود؛ dry-run = صفر درخواست.
  • AutoClickerStrategy  — فرمِ ازپیش‌آماده، یک کلیک در T0.
  • DomStrategy          — پرکردن و کلیک با locatorهای DOM.
  • JavaScriptStrategy   — fetch در بافتِ صفحه؛ پاسخ با همان مفسرِ سیم داوری می‌شود.
  • KeyboardStrategy     — ارسال با توالیِ کلیدِ مرورگر.
  • SeleniumStrategy     — فقط اگر selenium نصب باشد؛ در غیرِ این UNAVAILABLE.

قفل‌ها:
  ۱) هیچ Strategy در حالتِ dry-run درخواستِ سفارش را نمی‌فرستد؛ لایهٔ route آن را
     abort می‌کند. Direct API در dry-run حتی ترابری را صدا نمی‌زند.
  ۲) arbiter هر intent را فقط به یک submitter می‌دهد؛ بعد از UNKNOWN هیچ fallbackی
     نیست.
  ۳) هیچ کلیکِ تکراری/حلقهٔ کور وجود ندارد: یک action، بعد انتظارِ کوتاه برایِ
     مشاهدهٔ درخواست، بعد نتیجه؛ بی‌درخواست ⇒ failed، نه تلاشِ دوباره.
  ۴) هیچ توکن/کوکی/بدنهٔ پاسخ درِ evidence نمی‌نشیند.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout, as_completed
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional
from urllib.parse import urlparse

import execution_browser as EB
import execution_intent_store as IS
import execution_strategy_core as SC
from execution_contract import (
    BrokerError, ErrorCode, ExecutionRecord, ExecutionStatus, OrderDraft, Side,
)
from execution_easytrader import (
    WIRE_PATH_ORDER_CREATE, easytrader_payload, interpret_easytrader_response,
)
from execution_timing import ClockQuality, ClockState, Scheduler, TimeSource


def now_ms() -> float:
    return time.monotonic() * 1000.0


_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def ascii_digits(value: Any) -> str:
    return str(value or "").translate(_DIGITS)


def norm_text(value: Any) -> str:
    return " ".join(ascii_digits(value).split()).strip()


def parse_number(value: Any) -> Optional[float]:
    s = norm_text(value).replace(",", "").replace("٬", "").replace("،", "")
    if not s:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(f)) if f.is_integer() else ("%.6f" % f).rstrip("0").rstrip(".")


def _path_only(url: str) -> str:
    try:
        p = urlparse(url)
        return (p.path or "/")[:160]
    except Exception:
        return ""


class StrategyError(RuntimeError):
    def __init__(self, code: str, detail: str = "",
                 evidence: Optional[Mapping[str, Any]] = None) -> None:
        super().__init__("%s: %s" % (code, detail) if detail else code)
        self.code = code
        self.detail = detail
        self.evidence = dict(evidence or {})


@dataclass
class StrategyContext:
    adapter: Any
    settings: SC.StrategySettings
    metrics: SC.StrategyMetrics
    dry_run: bool
    driver_factory: Callable[..., Any]
    live_intent: bool = False
    reuse_driver: Any = None
    mock_browser: bool = False
    mock_driver_kwargs: dict[str, Any] = field(default_factory=dict)
    server_clock: Optional[Callable[[], Optional[dict[str, Any]]]] = None
    direct_submit: Optional[Callable[[OrderDraft], ExecutionRecord]] = None
    event: Optional[Callable[[str], None]] = None
    #: Round 14: claimِ اتمیکِ intent دقیقاً پیش از عملِ ارسال/کلیک.
    before_action: Optional[Callable[[], None]] = None


@dataclass
class PreparedHandle:
    strategy_id: str
    draft: OrderDraft
    payload: Optional[dict[str, Any]] = None
    driver: Any = None
    evidence: dict[str, Any] = field(default_factory=dict)
    prepared_ms: float = 0.0


# ── ۱) Direct API ───────────────────────────────────────────────────────────
class DirectApiStrategy:
    spec = SC.spec(SC.DIRECT_API)

    def available(self, ctx: StrategyContext) -> tuple[bool, str]:
        if not callable(getattr(ctx.adapter, "submit_order", None)):
            return False, "adapter has no submit_order"
        return True, ""

    def probe(self, ctx: StrategyContext) -> dict[str, Any]:
        return {"strategy": SC.DIRECT_API, "kind": "http",
                "note": "no browser page; use /api/execution/probe for host health"}

    def prepare(self, ctx: StrategyContext, draft: OrderDraft,
                target_wall_ms: Optional[int] = None) -> PreparedHandle:
        t0 = now_ms()
        ok, why = draft.instrument.orderable()
        if not ok:
            raise StrategyError("NOT_ORDERABLE", why)
        if draft.price is None or draft.price <= 0:
            raise StrategyError("INVALID_PRICE", "price must be positive")
        if draft.quantity is None or draft.quantity <= 0:
            raise StrategyError("INVALID_QUANTITY", "quantity must be positive")
        payload = easytrader_payload(draft)
        return PreparedHandle(
            SC.DIRECT_API, draft, payload=payload,
            evidence={"payload_keys": sorted(payload.keys()),
                      "envelope_keys": sorted((payload.get("order") or {}).keys()),
                      "path": WIRE_PATH_ORDER_CREATE},
            prepared_ms=round(now_ms() - t0, 3))

    def trigger(self, ctx: StrategyContext, order: "StrategyOrder") -> SC.StrategyResult:
        h = order.prepared
        t0 = now_ms()
        timings: dict[str, Any] = {"prepare": order.preparation_ms}
        target_host = urlparse(str(getattr(ctx.adapter, "base_url", "") or "")).netloc
        if ctx.dry_run:
            timings.update({"trigger": 0.0, "action": 0.0, "send": None,
                            "response": None, "total": round(now_ms() - t0, 3),
                            "dispatch_mono_ms": round(t0, 3),
                            "response_mono_ms": None})
            return SC.StrategyResult(
                order.execution_id, SC.DIRECT_API, "dry_run",
                detail="dry-run: ترابری صدا زده نشد؛ هیچ درخواستی ساخته نشد",
                request_aborted=False, live=False, timings=timings,
                evidence={"payload_keys": h.evidence.get("payload_keys", []),
                          "transport_calls": 0,
                          "hosts": [target_host] if target_host else []})
        submit = ctx.direct_submit or getattr(ctx.adapter, "submit_order", None)
        if not callable(submit):
            raise StrategyError("UNSUPPORTED", "no submit_order")
        try:
            if ctx.before_action is not None:
                ctx.before_action()
            rec = submit(h.draft)
        except BrokerError as e:
            unknown = bool(e.is_unknown_result)
            t1 = now_ms()
            timings.update({"trigger": round(t1 - t0, 3), "action": 0.0,
                            "send": None, "response": None,
                            "total": round(t1 - t0, 3),
                            "dispatch_mono_ms": round(t0, 3),
                            "response_mono_ms": round(t1, 3)})
            return SC.StrategyResult(
                order.execution_id, SC.DIRECT_API,
                "unknown" if unknown else "failed",
                detail=str(e.detail)[:200], error_code=e.code.value,
                unknown=unknown, live=True, timings=timings,
                evidence={"error": e.code.value, "transport_calls": 1,
                          "hosts": [target_host] if target_host else []})
        status = "unknown"
        accepted = False
        unknown = False
        error_code = None
        if rec.status is ExecutionStatus.UNKNOWN_RESULT:
            status = "unknown"
            unknown = True
        elif rec.status in (ExecutionStatus.ACKNOWLEDGED, ExecutionStatus.RECONCILED):
            accepted = True
            status = "accepted" if rec.status is ExecutionStatus.RECONCILED else "submitted"
        elif rec.status is ExecutionStatus.FAILED:
            status = "failed"
            error_code = rec.error_code.value if rec.error_code else None
        t1 = now_ms()
        timings.update({"trigger": round(t1 - t0, 3), "action": 0.0,
                        "send": None,
                        "response": rec.rtt_ms,
                        "total": round(t1 - t0, 3),
                        "dispatch_mono_ms": round(t0, 3),
                        "response_mono_ms": round(t1, 3)})
        return SC.StrategyResult(
            order.execution_id, SC.DIRECT_API, status,
            detail=("پذیرشِ صریحِ کارگزاری" if accepted else
                    ("نتیجه نامعلوم؛ reconcile لازم است" if unknown else
                     (rec.error_detail or "بدونِ پذیرشِ صریح"))),
            broker_order_id=rec.broker_order_id, error_code=error_code,
            accepted=accepted, unknown=unknown, live=True, timings=timings,
            evidence={"order_state": rec.order_state.value,
                      "transport_calls": 1,
                      "hosts": [target_host] if target_host else []})


# ── ۲) پایهٔ مرورگری ────────────────────────────────────────────────────────
class BrowserStrategyBase:
    spec: Any = None
    autofill_default = True
    require_prefilled_default = False

    def available(self, ctx: StrategyContext) -> tuple[bool, str]:
        if self.spec.id == SC.SELENIUM:
            if importlib.util.find_spec("selenium") is None:
                return False, "selenium package not installed"
            return False, "selenium driver is not implemented in this build"
        if ctx.mock_browser:
            return True, ""
        if importlib.util.find_spec("playwright") is None:
            return False, "playwright package not installed"
        ok, why = EB.browser_runtime_available(ctx.settings)
        if not ok:
            return False, why
        return True, ""

    def _autofill(self, ctx: StrategyContext) -> bool:
        return bool(ctx.settings.options.get("autofill", self.autofill_default))

    def _require_prefilled(self, ctx: StrategyContext) -> bool:
        return bool(ctx.settings.options.get("require_prefilled",
                                             self.require_prefilled_default))

    def _sel(self, ctx: StrategyContext) -> dict[str, str]:
        o = ctx.settings.options
        keys = ("order_url", "symbol_selector", "form_symbol_selector",
                "open_form_selector", "open_form_selector_buy",
                "open_form_selector_sell", "price_selector", "quantity_selector",
                "submit_selector", "submit_selector_buy", "submit_selector_sell",
                "form_selector", "side_selector", "isin_selector",
                "login_selector", "clock_selector",
                "symbol_confirm_selector", "focus_selector", "intercept_pattern",
                "api_path")
        out = {k: str(o.get(k) or "") for k in keys}
        out["order_url"] = out["order_url"] or "https://d.easytrader.ir/"
        out["intercept_pattern"] = out["intercept_pattern"] or "**/core/api/v2/order*"
        out["api_path"] = out["api_path"] or WIRE_PATH_ORDER_CREATE
        return out

    @staticmethod
    def _side_value(draft: OrderDraft) -> str:
        side = getattr(draft, "side", "")
        return str(getattr(side, "value", side) or "").lower()

    def _side_sel(self, ctx: StrategyContext, draft: OrderDraft) -> dict[str, str]:
        """انتخابگرهایِ همان سمت؛ فروش هرگز به دکمهٔ خرید برنمی‌گردد."""
        base = self._sel(ctx)
        side = self._side_value(draft)
        specific_submit = base.get("submit_selector_%s" % side) or ""
        generic_submit = base.get("submit_selector") or ""
        if side == "sell":
            if not specific_submit:
                raise StrategyError(
                    "CONFIG_MISSING",
                    "submit_selector_sell لازم است؛ انتخابگرِ خرید برایِ فروش استفاده نمی‌شود")
            submit = specific_submit
        else:
            # انتخابگرِ عمومیِ کاربر بر پیش‌فرضِ buy مقدم است.
            submit = generic_submit or specific_submit
        specific_open = base.get("open_form_selector_%s" % side) or ""
        generic_open = base.get("open_form_selector") or ""
        if side == "sell":
            if not specific_open and generic_open:
                raise StrategyError(
                    "CONFIG_MISSING",
                    "open_form_selector_sell لازم است؛ دکمهٔ خرید برایِ فرمِ فروش باز نمی‌شود")
            opener = specific_open
        else:
            opener = generic_open or specific_open
        scope = base.get("form_selector") or ""

        def scoped(value: str) -> str:
            if scope and value and value != opener:
                return "%s %s" % (scope, value)
            return value

        out = dict(base)
        out["submit_selector"] = scoped(submit)
        out["open_form_selector"] = opener
        out["symbol_selector"] = scoped(base["symbol_selector"])
        out["form_symbol_selector"] = scoped(base["form_symbol_selector"])
        out["price_selector"] = scoped(base["price_selector"])
        out["quantity_selector"] = scoped(base["quantity_selector"])
        out["side_selector"] = scoped(base["side_selector"])
        out["isin_selector"] = scoped(base["isin_selector"])
        out["_side"] = side
        return out

    def _order_paths(self, ctx: StrategyContext) -> list[str]:
        raw = ctx.settings.options.get("order_paths")
        if isinstance(raw, str):
            got = [x.strip() for x in raw.split(",") if x.strip()]
        elif isinstance(raw, (list, tuple)):
            got = [str(x).strip() for x in raw if str(x).strip()]
        else:
            got = []
        return got or [WIRE_PATH_ORDER_CREATE]

    def _order_method(self, ctx: StrategyContext) -> str:
        return str(ctx.settings.options.get("order_method") or "POST").upper()

    def _check_origin(self, driver: Any, ctx: StrategyContext) -> None:
        allow = ctx.settings.options.get("origin_allowlist") or []
        if isinstance(allow, str):
            allow = [allow]
        url = str(driver.url() or "")
        host = urlparse(url).netloc.lower()
        allowed = {urlparse(str(a)).netloc.lower() for a in allow if a}
        if not host or host not in allowed:
            raise StrategyError("ORIGIN_MISMATCH",
                                "origin %r not in %s" % (host, sorted(allowed)),
                                {"url": _path_only(url)})

    def _check_login(self, driver: Any, sel: Mapping[str, str]) -> None:
        if sel.get("login_selector") and driver.wait_for(sel["login_selector"], 600):
            raise StrategyError("LOGIN_REQUIRED",
                                "صفحهٔ ورود دیده شد؛ مالک باید در همین پنجره وارد شود")

    def _selector_map(self, ctx: StrategyContext) -> dict[str, str]:
        o = ctx.settings.options
        keys = ("symbol_selector", "form_symbol_selector", "open_form_selector",
                "open_form_selector_buy", "open_form_selector_sell",
                "price_selector", "quantity_selector", "submit_selector",
                "submit_selector_buy", "submit_selector_sell", "form_selector",
                "side_selector", "isin_selector", "login_selector",
                "clock_selector", "focus_selector", "symbol_confirm_selector")
        return {k: str(o.get(k) or "") for k in keys if str(o.get(k) or "")}

    def probe(self, ctx: StrategyContext) -> dict[str, Any]:
        """Probe فقط‌خواندنی: ساختار، login/selector/visibility و profile.

        برخلافِ prepare، دیدنِ صفحهٔ ورود اینجا خطا نیست؛ وضعیت گزارش می‌شود
        تا مالک بتواند تصمیم بگیرد. هیچ مقدارِ input خوانده/برگردانده نمی‌شود.
        """
        sel = self._sel(ctx)
        driver = ctx.driver_factory(
            ctx.settings, strategy_id=self.spec.id, mock=ctx.mock_browser,
            **ctx.mock_driver_kwargs)
        driver.start()
        t0 = now_ms()
        try:
            driver.goto(sel["order_url"])
            structure = driver.probe(self._selector_map(ctx))
            try:
                network = driver.network()
            except Exception:
                network = {"requests": None, "by_host": {}, "order_posts": None,
                           "truncated": None, "source": "unavailable"}
            final_url = str(driver.url() or "")
            host = urlparse(final_url).netloc.lower()
            allow = ctx.settings.options.get("origin_allowlist") or []
            if isinstance(allow, str):
                allow = [allow]
            allowed = {urlparse(str(a)).netloc.lower() for a in allow if a}
            # ریدایرکتِ SPA به صفحهٔ ورود برای Probe خطا نیست؛ فقط مقصد گزارش
            # می‌شود. مسیرِ trigger همچنان _check_origin سخت‌گیرانه را دارد.
            origin_ok = bool(host and host in allowed)
            login = "UNKNOWN"
            login_source = "unconfigured"
            visible_password = any(
                str(i.get("type") or "").lower() == "password" and i.get("visible")
                for i in (structure.get("inputs") or []))
            if sel.get("login_selector"):
                login_source = "configured-login-selector"
                login = ("LOGIN_REQUIRED" if driver.wait_for(sel["login_selector"], 600)
                         else "NOT_VISIBLE")
            elif visible_password:
                # فیلدِ رمزِ نمایان یک شاهدِ ساختاری است، نه selectorِ حدسی؛
                # صفحهٔ سفارش هیچ‌گاه رمز نمی‌خواهد.
                login, login_source = "LOGIN_REQUIRED", "password-input-visible"
            browser = {
                "driver": str(getattr(driver, "name", "") or ""),
                "headless": bool(ctx.settings.options.get("headless", False)),
                "profile_source": ("settings"
                                   if str(ctx.settings.options.get("profile_dir") or "")
                                   else "default"),
                "profile_configured": bool(
                    str(ctx.settings.options.get("profile_dir") or "")),
                "alive": bool(driver.is_alive()),
            }
            return {
                "strategy": self.spec.id, "kind": "browser",
                "url": _path_only(final_url), "host": host,
                "origin_ok": origin_ok,
                "title": str(driver.title() or "")[:80],
                "login": login, "login_source": login_source,
                "browser": browser,
                "network": network,
                "selectors": structure.get("selectors") or {},
                "structure": {
                    "inputs": structure.get("inputs") or [],
                    "buttons": structure.get("buttons") or [],
                    "login_candidates": structure.get("login_candidates") or [],
                },
                "elapsed_ms": round(now_ms() - t0, 1),
                "read_only": True,
            }
        finally:
            try:
                driver.close()
            except Exception:
                pass

    def _check_clock(self, ctx: StrategyContext, evidence: dict[str, Any]) -> None:
        if not ctx.server_clock:
            evidence["clock"] = {"source": "none", "verified": False}
            return
        try:
            got = ctx.server_clock() or {}
        except Exception as e:                       # noqa: BLE001
            got = {"verified": False, "error": type(e).__name__}
        evidence["clock"] = {
            "source": "broker-server-time",
            "verified": bool(got.get("verified")),
            "delta_ms": got.get("delta_ms"),
            "rtt_ms": got.get("rtt_ms"),
            "broker_time": got.get("broker_time"),
        }
        if not ctx.live_intent:
            return
        if not got.get("verified"):
            raise StrategyError("CLOCK_UNAVAILABLE",
                                "ساعتِ کارگزاری تأیید نشد؛ ارسالِ زنده ممنوع")
        limit = float(ctx.settings.options.get("max_clock_delta_ms") or 1500.0)
        try:
            delta = abs(float(got.get("delta_ms") or 0.0))
        except (TypeError, ValueError):
            delta = limit + 1
        if delta > limit:
            raise StrategyError("CLOCK_MISMATCH",
                                "اختلافِ ساعت %.0fms از سقفِ %.0fms بیشتر است"
                                % (delta, limit), {"delta_ms": delta})

    def _verify_form(self, driver: Any, sel: Mapping[str, str],
                     draft: OrderDraft, ctx: StrategyContext,
                     evidence: dict[str, Any]) -> None:
        sym_sel = sel.get("form_symbol_selector") or sel.get("symbol_selector") or ""
        price_sel = sel.get("price_selector") or ""
        qty_sel = sel.get("quantity_selector") or ""
        submit_sel = sel.get("submit_selector") or ""
        if not (sym_sel and price_sel and qty_sel and submit_sel):
            raise StrategyError("CONFIG_MISSING",
                                "symbol/price/quantity/submit selector لازم است")

        def unique(selector: str, label: str) -> int:
            try:
                n = int(driver.count(selector))
            except Exception:
                n = -1
            if n != 1:
                raise StrategyError(
                    "FORM_NOT_UNIQUE",
                    "%s باید دقیقاً یک تطبیق داشته باشد (count=%s)" % (label, n),
                    {"selector": selector[:120], "count": n})
            return n

        for label, selector in (("symbol", sym_sel), ("price", price_sel),
                                ("quantity", qty_sel), ("submit", submit_sel)):
            unique(selector, label)
        sym_raw = driver.read_value(sym_sel) or driver.read_text(sym_sel)
        sym = norm_text(sym_raw)
        targets = [draft.instrument.symbol, draft.instrument.isin,
                   draft.instrument.broker_instrument]
        if not sym or not any(t and norm_text(t) in sym for t in targets):
            raise StrategyError("SYMBOL_MISMATCH",
                                "نمادِ فرم با قصد یکی نیست", {"form_symbol": sym[:80]})
        want_isin = norm_text(draft.instrument.isin).upper()
        isin_sel = sel.get("isin_selector") or ""
        isin_checked = False
        if isin_sel:
            unique(isin_sel, "isin")
            form_isin = norm_text(
                driver.read_value(isin_sel) or driver.read_text(isin_sel)).upper()
            isin_checked = True
            if not want_isin or form_isin != want_isin:
                raise StrategyError("ISIN_MISMATCH",
                                    "ISINِ فرم با قصد یکی نیست",
                                    {"form_isin": form_isin[:40],
                                     "want": want_isin[:40]})
        price = parse_number(driver.read_value(price_sel) or driver.read_text(price_sel))
        qty = parse_number(driver.read_value(qty_sel) or driver.read_text(qty_sel))
        want_price = float(draft.price or 0.0)
        want_qty = float(draft.quantity or 0.0)
        if price is None or abs(price - want_price) > max(0.01, abs(want_price) * 1e-6):
            raise StrategyError("PRICE_MISMATCH",
                                "قیمتِ فرم با قصد یکی نیست",
                                {"form_price": price, "want": want_price})
        if qty is None or abs(qty - want_qty) > 1e-6:
            raise StrategyError("QUANTITY_MISMATCH",
                                "حجمِ فرم با قصد یکی نیست",
                                {"form_quantity": qty, "want": want_qty})
        side = self._side_value(draft)
        side_sel = sel.get("side_selector") or ""
        side_text = ""
        if side_sel:
            unique(side_sel, "side")
            side_text = (driver.read_text(side_sel)
                         or driver.read_value(side_sel) or "")
        if not side_text:
            reader = getattr(driver, "read_attr", None)
            if callable(reader):
                side_text = reader(submit_sel, "aria-label") or ""
        if not side_text:
            side_text = driver.read_text(submit_sel) or ""
        side_norm = norm_text(side_text).lower()
        tokens = (("خرید", "buy") if side == "buy" else
                  ("فروش", "sell", "فروش") if side == "sell" else ())
        if not tokens or not any(t in side_norm for t in tokens):
            raise StrategyError(
                "SIDE_UNVERIFIED",
                "سمتِ فرم از متن/aria قابلِ اثبات نیست؛ side_selector را تنظیم کنید",
                {"side": side, "evidence": side_norm[:80]})
        if not driver.is_enabled(submit_sel):
            raise StrategyError("SUBMIT_DISABLED", "دکمهٔ ارسال فعال نیست")
        evidence.update({
            "symbol": sym[:80], "price": price, "quantity": qty,
            "side": side, "side_text": side_norm[:80],
            "isin_checked": isin_checked,
            "submit_enabled": True,
            "submit_text": (driver.read_text(submit_sel) or "")[:60],
        })

    def prepare(self, ctx: StrategyContext, draft: OrderDraft,
                target_wall_ms: Optional[int] = None) -> PreparedHandle:
        sel = (self._sel(ctx) if self.spec.id == SC.JAVASCRIPT
               else self._side_sel(ctx, draft))
        if self.spec.id != SC.JAVASCRIPT and not sel["submit_selector"]:
            raise StrategyError("CONFIG_MISSING", "submit_selector لازم است")
        if self.spec.id == SC.JAVASCRIPT:
            ok, why = draft.instrument.orderable()
            if not ok:
                raise StrategyError("NOT_ORDERABLE", why)
            if not draft.price or draft.price <= 0 or not draft.quantity or draft.quantity <= 0:
                raise StrategyError("INVALID_ORDER", "price/quantity must be positive")
        driver = ctx.reuse_driver
        if driver is not None and not driver.is_alive():
            driver = None
        try:
            if driver is None:
                driver = ctx.driver_factory(
                    ctx.settings, strategy_id=self.spec.id, mock=ctx.mock_browser,
                    **ctx.mock_driver_kwargs)
                driver.start()
            t0 = now_ms()
            driver.goto(sel["order_url"])
            self._check_origin(driver, ctx)
            self._check_login(driver, sel)
            if sel.get("open_form_selector") and self.spec.id != SC.JAVASCRIPT:
                # فرمِ بازمانده از نمادِ قبلی stale است؛ پیش از هر خواندنی،
                # فرم را برایِ نمادِ فعال دوباره باز می‌کنیم (کلیکِ بازکردن، نه ارسال).
                opener = getattr(driver, "open_form", None)
                if callable(opener):
                    opener(sel["open_form_selector"], timeout_ms=int(
                        ctx.settings.options.get("action_timeout_ms") or 1200))
                else:
                    driver.click(sel["open_form_selector"], timeout_ms=int(
                        ctx.settings.options.get("action_timeout_ms") or 1200))
                if sel.get("price_selector"):
                    driver.wait_for(sel["price_selector"], 1500)
            evidence: dict[str, Any] = {
                "url": _path_only(driver.url()),
                "title": str(driver.title() or "")[:80],
                "autofill": self._autofill(ctx),
                "requires_prefilled": self._require_prefilled(ctx),
                "selectors_configured": {
                    "symbol": bool(sel["form_symbol_selector"] or sel["symbol_selector"]),
                    "price": bool(sel["price_selector"]),
                    "quantity": bool(sel["quantity_selector"]),
                    "submit": bool(sel["submit_selector"]),
                    "open_form": bool(sel.get("open_form_selector") or ""),
                    "side_selector": bool(sel.get("side_selector") or ""),
                    "isin": bool(sel.get("isin_selector") or ""),
                },
            }
            if self.spec.id != SC.JAVASCRIPT:
                if self._autofill(ctx):
                    if sel.get("symbol_selector"):
                        driver.fill(sel["symbol_selector"], draft.instrument.symbol)
                        if sel.get("symbol_confirm_selector"):
                            driver.click(sel["symbol_confirm_selector"], timeout_ms=600)
                    # فرمِ EasyTrader فیلدِ نماد ندارد؛ هویت با هدرِ فرم و
                    # انتخابِ صفحه تأیید می‌شود، نه با پرکردنِ فیلد.
                    driver.fill(sel["price_selector"], _fmt(draft.price))
                    driver.fill(sel["quantity_selector"], _fmt(draft.quantity))
                self._verify_form(driver, sel, draft, ctx, evidence)
            self._check_clock(ctx, evidence)
            return PreparedHandle(
                self.spec.id, draft, driver=driver, evidence=evidence,
                prepared_ms=round(now_ms() - t0, 3))
        except Exception:
            if driver is not None:
                try:
                    driver.close()
                except Exception:
                    pass
            raise

    def _action(self, ctx: StrategyContext, order: "StrategyOrder",
                driver: Any, sel: Mapping[str, str]) -> dict[str, Any]:
        raise NotImplementedError

    def trigger(self, ctx: StrategyContext, order: "StrategyOrder") -> SC.StrategyResult:
        h = order.prepared
        driver = getattr(h, "driver", None)
        if driver is None:
            raise StrategyError("BROWSER_NOT_READY", "prepared driver missing")
        if order.abort_event.is_set():
            try:
                driver.close()
            except Exception:
                pass
            return SC.StrategyResult(order.execution_id, self.spec.id, "aborted",
                                     detail="Stopped before trigger", timings={})
        sel = (self._sel(ctx) if self.spec.id == SC.JAVASCRIPT
               else self._side_sel(ctx, order.draft))
        if not driver.is_alive():
            raise StrategyError("BROWSER_NOT_READY", "browser is not alive")
        if not ctx.dry_run:
            clk = h.evidence.get("clock") or {}
            if not clk.get("verified"):
                try:
                    driver.close()
                except Exception:
                    pass
                raise StrategyError("CLOCK_UNVERIFIED",
                                    "ساعتِ کارگزاری در مرحلهٔ آماده‌سازی تأیید نشد")
            try:
                delta = abs(float(clk.get("delta_ms") or 0.0))
            except (TypeError, ValueError):
                delta = 1e9
            limit = float(ctx.settings.options.get("max_clock_delta_ms") or 1500.0)
            if delta > limit:
                try:
                    driver.close()
                except Exception:
                    pass
                raise StrategyError("CLOCK_MISMATCH",
                                    "اختلافِ ساعتِ ذخیره‌شده %.0fms از سقف بیشتر است"
                                    % delta, {"delta_ms": delta})
        if self.spec.id != SC.JAVASCRIPT:
            # مقادیر async فرم می‌توانند بین prepare و trigger عوض شوند؛ پیش از
            # هر کلیک/ارسال یک بازخوانیِ تازه، همان قصد را دوباره می‌سنجد.
            try:
                self._verify_form(driver, sel, order.draft, ctx, {})
            except Exception:
                try:
                    driver.close()
                except Exception:
                    pass
                raise
        try:
            if ctx.dry_run:
                # گاردِ catch-all: حتی الگویِ غلط/بیش‌ازحد محدود هم POST را رد نمی‌کند.
                driver.dry_run_guard(order_paths=self._order_paths(ctx),
                                     order_method=self._order_method(ctx))
            else:
                driver.intercept(sel["intercept_pattern"], abort=False)
        except Exception as e:                       # noqa: BLE001
            try:
                driver.close()
            except Exception:
                pass
            raise StrategyError("INTERCEPT_FAILED", str(e)[:120]) from None

        t_send = now_ms()
        action: dict[str, Any] = {}
        action_error = ""
        action_code = ""
        action_evidence: dict[str, Any] = {}
        try:
            if ctx.before_action is not None:
                ctx.before_action()
            action = self._action(ctx, order, driver, sel) or {}
        except StrategyError as e:
            action_error = str(e.detail or e.code)[:160]
            action_code = e.code
            action_evidence = dict(e.evidence)
            action = {"start_ms": t_send, "end_ms": now_ms()}
        except Exception as e:                       # noqa: BLE001
            action_error = "%s: %s" % (type(e).__name__, str(e)[:160])
            action = {"start_ms": t_send, "end_ms": now_ms()}
        t_end = now_ms()
        timeout_ms = int(ctx.settings.options.get("action_timeout_ms") or 1200)
        try:
            req = driver.wait_for_request(timeout_ms)
        except Exception:
            req = None
        resp = None
        if req is not None and not ctx.dry_run:
            try:
                resp = driver.wait_for_response(int(
                    ctx.settings.options.get("response_timeout_ms") or 3000))
            except Exception:
                resp = None
        net: dict[str, Any] = {}
        if ctx.dry_run:
            try:
                net = dict(driver.network() or {})
            except Exception:
                net = {}

        a_start = float(action.get("start_ms") or t_send)
        a_end = float(action.get("end_ms") or t_end)
        req_ms = (float(req["mono_ms"]) if req and req.get("mono_ms") is not None
                  else None)
        resp_ms = (float(resp["mono_ms"]) if resp and resp.get("mono_ms") is not None
                   else None)
        click_to_request = (round(max(0.0, req_ms - a_start), 3)
                            if req_ms is not None else None)
        response_wait = (round(max(0.0, resp_ms - req_ms), 3)
                         if resp_ms is not None and req_ms is not None else None)
        timings = {
            "prepare": order.preparation_ms,
            "trigger": round(max(0.0, a_start - t_send), 3),
            "action": round(max(0.0, a_end - a_start), 3),
            # نامِ صریح: این عدد latency یک‌طرفهٔ شبکه نیست؛ فقط کلیک→شروع request.
            "send": click_to_request,
            "click_to_request_ms": click_to_request,
            "response": response_wait,
            "response_wait_ms": response_wait,
            "one_way_ms": None,
            "rtt_ms": None,
            "target_wall_ms": order.target_wall_ms,
            "total": round(max(0.0, t_end - t_send), 3),
            "action_start_mono_ms": round(a_start, 3),
            "request_mono_ms": round(req_ms, 3) if req_ms is not None else None,
            "response_mono_ms": round(resp_ms, 3) if resp_ms is not None else None,
        }
        hosts: list[str] = []
        try:
            hosts = list(driver.request_hosts() or [])
        except Exception:
            hosts = []
        evidence = {
            "action_method": action.get("method") or self.spec.id,
            "click_attempted": bool(action.get("clicked")),
            "request_seen": req is not None,
            "request_path": _path_only(str(req.get("url") or "")) if req else None,
            "request_method": (req or {}).get("method"),
            "intercepted": True,
            "aborted": bool(ctx.dry_run and req is not None),
            "http_status": (resp or {}).get("status"),
            "action_error": action_error,
            "hosts": hosts,
            "dry_run_guard": bool(ctx.dry_run),
            "writes": net.get("writes"),
            "blocked_writes": net.get("blocked_writes"),
            "escaped_writes": net.get("escaped_writes"),
            "order_writes": net.get("order_writes"),
            "other_writes": net.get("other_writes"),
            "order_method_mismatch": net.get("order_method_mismatch"),
            "order_paths": self._order_paths(ctx) if ctx.dry_run else None,
        }
        if not bool(ctx.settings.options.get("keep_driver_alive")):
            try:
                driver.close()
            except Exception:
                pass

        if order.abort_event.is_set() and req is None:
            return SC.StrategyResult(
                order.execution_id, self.spec.id, "aborted",
                detail="Stop پیش از دیده‌شدنِ درخواستِ سفارش رسید",
                live=False, timings=timings, evidence=evidence)
        if order.abort_event.is_set() and req is not None:
            evidence["stop_after_request"] = True

        if ctx.dry_run:
            writes = int(net.get("writes") or 0)
            blocked = int(net.get("blocked_writes") or 0)
            escaped = int(net.get("escaped_writes") or 0)
            order_writes = int(net.get("order_writes") or 0)
            other_writes = int(net.get("other_writes") or 0)
            mismatch = int(net.get("order_method_mismatch") or 0)
            if order.abort_event.is_set():
                return SC.StrategyResult(
                    order.execution_id, self.spec.id, "aborted",
                    detail="Stop در حینِ dry-run رسید؛ هیچ درخواستی ادامه نیافت",
                    request_aborted=bool(blocked), live=False, timings=timings,
                    evidence=evidence)
            if escaped or (writes > 0 and blocked < writes):
                # نوشتنِ رهاشده ممکن است به کارگزاری رسیده باشد؛ ادعای «dry» ممنوع.
                return SC.StrategyResult(
                    order.execution_id, self.spec.id, "unknown",
                    detail="نوشتن از گاردِ dry-run عبور کرد؛ نتیجه نامعلوم و نیازمندِ بررسی",
                    error_code="DRY_RUN_ESCAPE", unknown=True, live=False,
                    timings=timings, evidence=evidence)
            if writes == 0:
                if action_code:
                    return SC.StrategyResult(
                        order.execution_id, self.spec.id, "blocked",
                        detail=action_error, error_code=action_code,
                        live=False, timings=timings,
                        evidence={**evidence, **action_evidence})
                return SC.StrategyResult(
                    order.execution_id, self.spec.id, "failed",
                    detail=("کلیک انجام شد ولی هیچ درخواستِ نوشتنی دیده نشد"
                            if not action_error else action_error),
                    error_code="NO_ORDER_REQUEST", live=False,
                    timings=timings, evidence=evidence)
            if mismatch:
                return SC.StrategyResult(
                    order.execution_id, self.spec.id, "blocked",
                    detail="متدِ درخواست با قراردادِ سفارش یکی نیست (dry-run)",
                    error_code="ORDER_METHOD_MISMATCH", live=False,
                    timings=timings, evidence=evidence)
            if other_writes:
                return SC.StrategyResult(
                    order.execution_id, self.spec.id, "blocked",
                    detail="نوشتنِ غیرِسفارش در dry-run مسدود شد",
                    error_code="NON_ORDER_WRITE_BLOCKED", live=False,
                    timings=timings, evidence=evidence)
            if order_writes:
                return SC.StrategyResult(
                    order.execution_id, self.spec.id, "dry_run",
                    detail="درخواستِ سفارش در مرورگر دیده و abort شد؛ هیچ POSTی نرفت",
                    request_aborted=True, live=False, timings=timings,
                    evidence=evidence)
            return SC.StrategyResult(
                order.execution_id, self.spec.id, "blocked",
                detail="نوشتنِ طبقه‌بندی‌نشده در dry-run مسدود شد",
                error_code="DRY_RUN_UNCLASSIFIED_WRITE", live=False,
                timings=timings, evidence=evidence)
        if req is None:
            if action_code:
                return SC.StrategyResult(
                    order.execution_id, self.spec.id, "blocked",
                    detail=action_error, error_code=action_code,
                    live=True, timings=timings,
                    evidence={**evidence, **action_evidence})
            return SC.StrategyResult(
                order.execution_id, self.spec.id, "failed",
                detail=("کلیک انجام شد ولی هیچ درخواستِ سفارشی دیده نشد"
                        if not action_error else action_error),
                error_code="NO_ORDER_REQUEST", live=True,
                timings=timings, evidence=evidence)
        # Live: همان مفسرِ سیمِ Direct API داور است؛ HTTP 2xx به‌تنهایی پذیرش نیست.
        accepted = False
        unknown = True
        detail = "درخواست رفت ولی پاسخی دیده نشد — نتیجه نامعلوم"
        http_status = (resp or {}).get("status")
        broker_order_id = None
        error_code = None
        if resp is not None:
            body = resp.get("body")
            verdict = interpret_easytrader_response(
                int(http_status or 0), body, where="browser-%s" % self.spec.id)
            if verdict.accepted is True:
                accepted = True
                unknown = False
                broker_order_id = verdict.broker_order_id
                detail = "پاسخِ صریحِ کارگزاری؛ پذیرش ادعا شد"
            elif verdict.accepted is False:
                accepted = False
                unknown = False
                error_code = verdict.error.value if verdict.error else "BROKER_REJECTED"
                detail = verdict.detail
            else:
                detail = "پاسخِ مبهم؛ reconcile لازم است"
            evidence["response_seen"] = True
            evidence["response_keys"] = sorted(
                body.keys()) if isinstance(body, dict) else []
        return SC.StrategyResult(
            order.execution_id, self.spec.id,
            "accepted" if accepted else ("unknown" if unknown else "failed"),
            detail=detail, http_status=http_status, accepted=accepted,
            unknown=unknown, broker_order_id=broker_order_id,
            error_code=error_code, live=True, timings=timings, evidence=evidence)

    def abort(self, ctx: StrategyContext, order: "StrategyOrder") -> None:
        order.abort_event.set()
        h = order.prepared
        drv = getattr(h, "driver", None)
        if drv is not None:
            try:
                drv.close()
            except Exception:
                pass


class AutoClickerStrategy(BrowserStrategyBase):
    spec = SC.spec(SC.AUTOCLICKER)
    autofill_default = False
    require_prefilled_default = True

    def _action(self, ctx, order, driver, sel):
        # یک بازرسیِ ارزان پیش از کلیک: دکمه باید همان‌جا باشد؛ کلیکِ کور روی
        # دکمهٔ ناپایدار یکی از راه‌های «بدونِ درخواست» بود. قابلِ خاموش‌کردن
        # برایِ سنجشِ هزینه/فایده، نه پیش‌فرض.
        if bool(ctx.settings.options.get("preclick_check", True)):
            if not driver.wait_for(sel["submit_selector"], 400):
                raise StrategyError("SUBMIT_NOT_READY", "دکمهٔ ارسال دیده نشد")
        # بازخوانیِ نهایی پس از انتظارِ preclick: فرم می‌تواند در همین فاصله عوض شود.
        self._verify_form(driver, sel, order.draft, ctx, {})
        got = driver.click(sel["submit_selector"], timeout_ms=int(
            ctx.settings.options.get("action_timeout_ms") or 1200), force=False)
        got["clicked"] = True
        got["method"] = "single-click"
        return got


class DomStrategy(BrowserStrategyBase):
    spec = SC.spec(SC.PLAYWRIGHT_DOM)
    autofill_default = True

    def _action(self, ctx, order, driver, sel):
        got = driver.click(sel["submit_selector"], timeout_ms=int(
            ctx.settings.options.get("action_timeout_ms") or 1200), force=False)
        got["clicked"] = True
        got["method"] = "dom-click"
        return got


class KeyboardStrategy(BrowserStrategyBase):
    spec = SC.spec(SC.KEYBOARD)
    autofill_default = True

    def _action(self, ctx, order, driver, sel):
        keys = ctx.settings.options.get("key_sequence") or ["Enter"]
        if isinstance(keys, str):
            keys = [keys]
        submits = [k for k in keys if str(k).strip().lower() in
                   ("enter", "return", "space", " ")]
        if len(submits) > 1:
            raise StrategyError("MULTIPLE_SUBMIT_KEYS",
                                "توالیِ کلید بیش از یک کلیدِ ارسال دارد")
        focus = sel.get("focus_selector") or sel["submit_selector"]
        start = now_ms()
        for key in keys:
            driver.press(str(key), selector=focus)
        return {"start_ms": start, "end_ms": now_ms(), "method": "keyboard",
                "clicked": bool(submits)}


class JavaScriptStrategy(BrowserStrategyBase):
    spec = SC.spec(SC.JAVASCRIPT)

    _JS = """async (arg) => {
      try {
        const r = await fetch(arg.url, {method: 'POST', credentials: 'include',
          headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
          body: JSON.stringify(arg.body)});
        let text = '';
        try { text = await r.text(); } catch (e) {}
        return {status: r.status, body: text.slice(0, 4000)};
      } catch (e) {
        return {error: String(e && e.message || e).slice(0, 200)};
      }
    }"""

    def _action(self, ctx, order, driver, sel):
        start = now_ms()
        payload = easytrader_payload(order.draft)
        got = driver.evaluate(self._JS, {"url": sel["api_path"], "body": payload})
        end = now_ms()
        try:
            order.prepared.evidence["js_response"] = dict(got) if isinstance(got, dict) else {"raw": str(got)[:80]}
        except Exception:
            pass
        return {"start_ms": start, "end_ms": end, "method": "js-fetch",
                "response": got, "clicked": True}

    def trigger(self, ctx, order):
        result = super().trigger(ctx, order)
        if not (result.live and result.status == "unknown"):
            return result
        got = (order.prepared.evidence or {}).get("js_response") or {}
        status = got.get("status")
        body = got.get("body")
        if not isinstance(status, int) or body is None:
            result.detail = ("JS fetch پاسخی با status/body قابلِ تفسیر برنگرداند — "
                             "نتیجه نامعلوم")
            return result
        verdict = interpret_easytrader_response(status, body, where="browser-js")
        result.http_status = status
        result.evidence["response_keys"] = sorted(
            (json.loads(body).keys() if isinstance(body, str) and body.strip().startswith("{")
             else []))
        if verdict.accepted is True:
            result.status = "accepted"
            result.accepted = True
            result.unknown = False
            result.broker_order_id = verdict.broker_order_id
            result.detail = "پاسخِ صریحِ کارگزاری؛ پذیرش ادعا شد"
        elif verdict.accepted is False:
            result.status = "failed"
            result.accepted = False
            result.unknown = False
            result.error_code = verdict.error.value if verdict.error else "BROKER_REJECTED"
            result.detail = verdict.detail
        else:
            result.detail = "پاسخِ مبهم؛ reconcile لازم است"
        return result


class SeleniumStrategy(BrowserStrategyBase):
    spec = SC.spec(SC.SELENIUM)

    def available(self, ctx):
        if importlib.util.find_spec("selenium") is None:
            return False, "selenium package not installed"
        return False, "selenium driver is not implemented in this build"


def build_strategies() -> dict[str, BrowserStrategyBase | DirectApiStrategy]:
    return {
        SC.DIRECT_API: DirectApiStrategy(),
        SC.AUTOCLICKER: AutoClickerStrategy(),
        SC.PLAYWRIGHT_DOM: DomStrategy(),
        SC.JAVASCRIPT: JavaScriptStrategy(),
        SC.KEYBOARD: KeyboardStrategy(),
        SC.SELENIUM: SeleniumStrategy(),
    }


# ── ۳) موتور ────────────────────────────────────────────────────────────────
class StrategyEngine:
    def __init__(self, adapter: Any, *,
                 settings_store: Optional[SC.StrategySettingsStore] = None,
                 metrics: Optional[SC.StrategyMetrics] = None,
                 scheduler: Optional[Scheduler] = None,
                 time_source: Optional[TimeSource] = None,
                 server_clock: Optional[Callable[[], Optional[dict[str, Any]]]] = None,
                 driver_factory: Optional[Callable[..., Any]] = None,
                 mock_browser: bool = False,
                 mock_driver_kwargs: Optional[dict[str, Any]] = None,
                 direct_submit: Optional[Callable[[OrderDraft], ExecutionRecord]] = None,
                 live_allowed: bool = False,
                 halted: Optional[Callable[[], tuple[bool, str]]] = None,
                 intent_store: Optional[IS.IntentStore] = None,
                 preflight_gate: Optional[Callable[[OrderDraft], Any]] = None,
                 recover_intents: bool = True) -> None:
        self.adapter = adapter
        self.settings_store = settings_store or SC.StrategySettingsStore()
        self.metrics = metrics or SC.StrategyMetrics()
        self.arbiter = SC.IntentArbiter()
        self.limiter = SC.AccountWindowLimiter(
            max_events=(int(os.environ.get("BORS_EXECUTION_MAX_ORDERS_TOTAL") or 0) or None),
            window_s=float(os.environ.get("BORS_EXECUTION_RATE_WINDOW_S") or 60.0))
        self.time_source = time_source or TimeSource()
        self.scheduler = scheduler
        self.server_clock = server_clock
        self.driver_factory = driver_factory or EB.make_driver
        self.mock_browser = bool(mock_browser)
        self.mock_driver_kwargs = dict(mock_driver_kwargs or {})
        self.direct_submit = direct_submit
        self.live_allowed = bool(live_allowed)
        self.halted = halted or (lambda: (False, "no halt source"))
        self.intent_store = intent_store or IS.IntentStore()
        self.preflight_gate = preflight_gate
        self.recovered_intents = (self.intent_store.recover_stale()
                                  if recover_intents else {"unknown": 0, "aborted": 0})
        self.strategies = build_strategies()
        self._orders: dict[str, SC.StrategyOrder] = {}
        self._outcomes: dict[str, Counter] = {}
        self._browser_drivers: dict[str, Any] = {}
        self._lock = threading.Lock()

    def _ctx(self, settings: SC.StrategySettings, *, dry_run: bool,
             live_intent: Optional[bool] = None,
             reuse_driver: Any = None) -> StrategyContext:
        li = (bool(self.live_allowed and settings.mode == SC.MODE_LIVE)
              if live_intent is None else bool(live_intent))
        return StrategyContext(
            adapter=self.adapter, settings=settings, metrics=self.metrics,
            dry_run=dry_run, driver_factory=self.driver_factory,
            live_intent=li, reuse_driver=reuse_driver,
            mock_browser=self.mock_browser,
            mock_driver_kwargs=self.mock_driver_kwargs,
            server_clock=self.server_clock, direct_submit=self.direct_submit)

    def get_order(self, prepared_id: str) -> Optional[SC.StrategyOrder]:
        with self._lock:
            return self._orders.get(prepared_id)

    def probe(self, strategy_id: str) -> dict[str, Any]:
        settings = self._settings(strategy_id)
        ctx = self._ctx(settings, dry_run=True)
        strategy = self.strategies[strategy_id]
        available, why = strategy.available(ctx)
        if not available:
            raise StrategyError("UNAVAILABLE", why)
        fn = getattr(strategy, "probe", None)
        if not callable(fn):
            raise StrategyError("UNSUPPORTED", "probe not implemented")
        t0 = now_ms()
        result = fn(ctx)
        if isinstance(result, dict):
            result.setdefault("available", True)
            result.setdefault("read_only", True)
            result.setdefault("elapsed_ms", round(now_ms() - t0, 1))
        return result

    def parallel_probe(self, strategy_ids=None, *, max_workers: int = 4,
                       timeout_s: float = 25.0) -> dict[str, Any]:
        """پیش‌فرودِ موازیِ فقط‌خواندنی روی چند Strategy.

        این متد هیچ prepare/trigger/dispatch صدا نمی‌زند؛ فقط Probe. انتخابِ
        «dry-run» بر اساسِ موفقیت و زمانِ Probe است، نه مجوزِ ارسالِ زنده.
        """
        ids = [s for s in (strategy_ids or list(SC.ALL_STRATEGIES))
               if s in self.strategies]
        if not ids:
            return {"strategies": [], "ready": [], "ranked_dry_run": [],
                    "recommended_dry_run": None, "live_send": False}

        def one(sid: str) -> dict[str, Any]:
            t0 = now_ms()
            try:
                got = self.probe(sid)
                return {"strategy": sid, "status": "success",
                        "elapsed_ms": round(now_ms() - t0, 1),
                        "available": bool(got.get("available", True)),
                        "probe": got}
            except StrategyError as e:
                return {"strategy": sid, "status": "unavailable",
                        "code": e.code, "detail": str(e.detail)[:200],
                        "elapsed_ms": round(now_ms() - t0, 1)}
            except Exception as e:               # noqa: BLE001
                return {"strategy": sid, "status": "error",
                        "code": "PREFLIGHT_FAILED",
                        "detail": "%s: %s" % (type(e).__name__, str(e)[:160]),
                        "elapsed_ms": round(now_ms() - t0, 1)}

        rows: list[dict[str, Any]] = []
        ex = ThreadPoolExecutor(max_workers=max(1, min(int(max_workers), len(ids))))
        futs = {ex.submit(one, sid): sid for sid in ids}
        try:
            for fut in as_completed(futs, timeout=timeout_s):
                try:
                    rows.append(fut.result())
                except Exception as e:           # noqa: BLE001
                    rows.append({"strategy": futs[fut], "status": "error",
                                 "code": "PREFLIGHT_FAILED",
                                 "detail": type(e).__name__, "elapsed_ms": None})
        except FuturesTimeout:
            done = {r["strategy"] for r in rows}
            for sid in ids:
                if sid not in done:
                    rows.append({"strategy": sid, "status": "timeout",
                                 "code": "PREFLIGHT_TIMEOUT",
                                 "detail": "probe exceeded timeout", "elapsed_ms": None})
        finally:
            ex.shutdown(wait=False, cancel_futures=True)
        order = {sid: i for i, sid in enumerate(ids)}
        rows.sort(key=lambda r: order.get(r["strategy"], 999))
        ready = [r["strategy"] for r in rows
                 if r["status"] == "success" and r.get("available")]
        ranked = sorted((r for r in rows if r["strategy"] in ready),
                        key=lambda r: (r.get("elapsed_ms") is None,
                                       r.get("elapsed_ms") or 1e18))
        return {"strategies": rows, "ready": ready,
                "ranked_dry_run": [r["strategy"] for r in ranked],
                "recommended_dry_run": ranked[0]["strategy"] if ranked else None,
                "live_send": False}

    def _settings(self, strategy_id: str) -> SC.StrategySettings:
        return self.settings_store.load()[strategy_id]

    @staticmethod
    def _configured(strategy_id: str, sp: SC.StrategySpec,
                    settings: SC.StrategySettings) -> bool:
        if not sp.requires_browser:
            return True
        if strategy_id == SC.JAVASCRIPT:
            # JS در بافتِ صفحه اجرا می‌شود؛ بی‌پروفایلِ واردشده یا login
            # selector، «تنظیم‌شده» نیست — حتی اگر URLِ پیش‌فرض باشد.
            return bool(settings.options.get("order_url")) and bool(
                settings.options.get("login_selector") or settings.options.get("profile_dir"))
        sym = settings.options.get("form_symbol_selector") or settings.options.get("symbol_selector")
        required = ("submit_selector", "price_selector", "quantity_selector")
        return bool(sym) and all(bool(settings.options.get(k)) for k in required)

    def list(self) -> list[dict[str, Any]]:
        settings = self.settings_store.load()
        out = []
        ctx = self._ctx(SC.default_settings(SC.DIRECT_API), dry_run=True)
        for sid in SC.ALL_STRATEGIES:
            sp = SC.spec(sid)
            st = settings[sid]
            sctx = StrategyContext(**{**ctx.__dict__, "settings": st})
            strategy = self.strategies[sid]
            try:
                available, why = strategy.available(sctx)
            except Exception as e:                   # noqa: BLE001
                available, why = False, "%s: %s" % (type(e).__name__, str(e)[:120])
            live_ready = bool(self.live_allowed and st.mode == SC.MODE_LIVE
                              and sp.supports_live
                              and bool(getattr(self.adapter, "writes_allowed", False)))
            configured = self._configured(sid, sp, st)
            last = None
            with self._lock:
                rows = [o for o in self._orders.values() if o.strategy_id == sid
                        and o.result is not None]
                if rows:
                    last = max(rows, key=lambda o: o.created_at).result.public()
            out.append({
                "id": sid, "label": sp.label, "kind": sp.kind,
                "description": sp.description,
                "requires_browser": sp.requires_browser,
                "supports_dry_run": sp.supports_dry_run,
                "supports_live": sp.supports_live,
                "available": available, "unavailable_reason": why,
                "configured": configured,
                "live_ready": live_ready,
                "settings": st.public(),
                "metrics": self.metrics.summary(sid),
                "outcomes": dict(self._outcomes.get(sid, {})),
                "last_result": last,
            })
        out.sort(key=lambda r: (not r["settings"]["enabled"],
                                r["settings"]["priority"], r["id"]))
        return out

    def prepare(self, draft: OrderDraft, strategy_id: str,
                target_wall_ms: Optional[int] = None, *,
                live_intent: Optional[bool] = None,
                intent_key: Optional[str] = None) -> SC.StrategyOrder:
        if target_wall_ms is not None and int(target_wall_ms) <= self.time_source.wall_ms():
            raise StrategyError("TARGET_IN_PAST",
                                "زمانِ هدف گذشته یا منقضی است؛ هدفِ آینده لازم است")
        key = IS.derive_key(draft, target_wall_ms, intent_key or "")
        try:
            self.intent_store.begin(
                intent_key=key, execution_id=draft.execution_id,
                strategy_id=strategy_id, draft=draft,
                target_wall_ms=target_wall_ms)
        except IS.IntentBlocked as e:
            raise StrategyError(
                "DUPLICATE_GUARD",
                "این قصد قبلاً ثبت شده است (state=%s)؛ برایِ قصدِ تازه کلیدِ تازه لازم است"
                % e.state) from None
        pre_row = self.intent_store.get(key) or {}
        if (pre_row.get("state") == "failed_pre_click"
                and not int(pre_row.get("clicked") or 0)):
            # خطایِ پیش از کلیک، claimِ قبلیِ arbiter را مصرف نکرده است.
            self.arbiter.release(draft.execution_id)
        settings = self._settings(strategy_id)
        if not settings.enabled or settings.mode == SC.MODE_OFF:
            self.intent_store.mark_prepare_failed(key, strategy_id,
                                                  "strategy disabled or off")
            raise StrategyError("STRATEGY_OFF", "strategy disabled or off")
        strategy = self.strategies[strategy_id]
        reuse = None
        if (isinstance(strategy, BrowserStrategyBase)
                and bool(settings.options.get("keep_driver_alive"))):
            cand = self._browser_drivers.get(strategy_id)
            if cand is not None and getattr(cand, "is_alive", lambda: False)():
                reuse = cand
        ctx = self._ctx(settings, dry_run=True, live_intent=live_intent,
                        reuse_driver=reuse)
        available, why = strategy.available(ctx)
        if not available:
            self.intent_store.mark_prepare_failed(key, strategy_id, why)
            raise StrategyError("UNAVAILABLE", why)
        if isinstance(strategy, BrowserStrategyBase) and not self._configured(
                strategy_id, strategy.spec, settings):
            self.intent_store.mark_prepare_failed(
                key, strategy_id, "selectors/profile incomplete")
            raise StrategyError(
                "CONFIG_MISSING",
                "این Strategy تا پیکربندیِ selector/پروفایلِ ورود prepare نمی‌شود")
        ok, why = self.arbiter.reserve(draft.execution_id, strategy_id)
        if not ok:
            self.intent_store.mark_prepare_failed(key, strategy_id, why)
            raise StrategyError("DUPLICATE_GUARD", why)
        order = SC.StrategyOrder(draft.execution_id, strategy_id, draft,
                                 target_wall_ms, intent_key=key)
        with self._lock:
            existing = self._orders.get(order.prepared_id)
        if existing is not None:
            row = self.intent_store.get(key) or {}
            if not (row.get("state") == "failed_pre_click"
                    and not int(row.get("clicked") or 0)):
                raise StrategyError("DUPLICATE_GUARD",
                                    "this intent+strategy is already prepared")
            old_driver = getattr(existing.prepared, "driver", None)
            if old_driver is not None:
                try:
                    old_driver.close()
                except Exception:
                    pass
            with self._lock:
                self._orders.pop(order.prepared_id, None)
            self.arbiter.release(draft.execution_id)
            ok2, why2 = self.arbiter.reserve(draft.execution_id, strategy_id)
            if not ok2:
                raise StrategyError("DUPLICATE_GUARD", why2)
        try:
            handle = strategy.prepare(ctx, draft, target_wall_ms)
        except Exception as e:
            self._browser_drivers.pop(strategy_id, None)
            self.arbiter.abort(draft.execution_id)
            self.intent_store.mark_prepare_failed(key, strategy_id, str(e)[:180])
            raise
        order.prepared = handle
        order.preparation_ms = getattr(handle, "prepared_ms", None)
        if (isinstance(handle, PreparedHandle) and handle.driver is not None
                and bool(settings.options.get("keep_driver_alive"))):
            self._browser_drivers[strategy_id] = handle.driver
        self.metrics.record(strategy_id, "prepare", order.preparation_ms,
                            ok=True)
        self.intent_store.bind_prepared(key, order.prepared_id)
        with self._lock:
            self._orders[order.prepared_id] = order
        return order

    def trigger(self, prepared_id: str, *, live: bool = False,
                confirmed: bool = False,
                live_allowed: Optional[bool] = None) -> SC.StrategyResult:
        with self._lock:
            order = self._orders.get(prepared_id)
        if order is None:
            raise StrategyError("INVALID_EXECUTION_ID", "no such prepared order")
        eid = order.execution_id
        if order.abort_event.is_set():
            return SC.StrategyResult(eid, order.strategy_id, "aborted",
                                     detail="Stopped before trigger")
        settings = self._settings(order.strategy_id)
        allowed = (self.live_allowed if live_allowed is None
                   else bool(live_allowed))
        live_wanted = bool(live)
        live_ok = bool(live_wanted and allowed
                       and settings.mode == SC.MODE_LIVE
                       and bool(getattr(self.adapter, "writes_allowed", False)))
        if live_wanted and not live_ok:
            raise StrategyError("LIVE_GATED",
                                "live submission is gated (env/setting/writes_allowed)")
        if live_ok and self.preflight_gate is not None:
            try:
                gate = self.preflight_gate(order.draft)
            except Exception as e:                   # noqa: BLE001
                raise StrategyError(
                    "PREFLIGHT_BLOCKED",
                    "پیش‌فرودِ ریسک اجرا نشد: %s: %s"
                    % (type(e).__name__, str(e)[:140])) from None
            if isinstance(gate, Mapping):
                gate_ok = bool(gate.get("ok"))
                checks = dict(gate.get("checks") or {})
            else:
                gate_ok = bool(getattr(gate, "ok", False))
                checks = dict(getattr(gate, "checks", {}) or {})
            if not gate_ok:
                raise StrategyError(
                    "PREFLIGHT_BLOCKED",
                    "پیش‌فرود/سقفِ ریسک اجازهٔ کلیک نمی‌دهد",
                    {"checks": checks})
        strategy = self.strategies[order.strategy_id]
        if (live_ok and isinstance(strategy, BrowserStrategyBase)
                and not self.mock_browser
                and not (settings.options.get("cdp_url") or EB.active_cdp_url())):
            raise StrategyError(
                "AUTH_REQUIRED",
                "برایِ اجرایِ زندهٔ مرورگری، پنجرهٔ پایدارِ مالک (browser host) لازم است")
        stopped, why = self.halted()
        if stopped and live_ok:
            raise StrategyError("HALTED", why or "kill switch is on")
        ok, why = self.arbiter.claim(eid, order.strategy_id)
        if not ok:
            raise StrategyError("DUPLICATE_GUARD", why)
        try:
            if order.target_wall_ms is not None:
                self.intent_store.mark_scheduled(order.intent_key)
        except IS.IntentBlocked as e:
            self.arbiter.complete(eid, order.strategy_id, "blocked", str(e))
            order.state = "blocked"
            return SC.StrategyResult(
                eid, order.strategy_id, "blocked",
                detail="قصد قبلاً در وضعیتِ %s است" % e.state,
                error_code="DUPLICATE_GUARD")
        if live_ok:
            can, retry = self.limiter.try_acquire("easytrader")
            if not can:
                self.arbiter.complete(eid, order.strategy_id, "blocked",
                                      "rate limit: retry in %.1fs" % retry)
                order.state = "blocked"
                return SC.StrategyResult(
                    eid, order.strategy_id, "blocked",
                    detail="rate limit: retry in %.1fs" % retry,
                    error_code="RATE_LIMITED")
        ctx = self._ctx(settings, dry_run=not live_ok, live_intent=live_ok)

        def _claim_click() -> None:
            try:
                self.intent_store.claim_click(order.intent_key)
            except IS.IntentBlocked as e:
                raise StrategyError("DUPLICATE_GUARD", str(e)) from None

        # claimِ اتمیک دقیقاً پیش از action؛ اگر کلیک انجام شد، دیگر تکرار ممنوع.
        ctx.before_action = _claim_click
        try:
            if order.target_wall_ms is not None and self.scheduler is not None:
                plan = self.scheduler.plan(order.target_wall_ms)
                holder: dict[str, Any] = {}

                def _send() -> str:
                    holder["result"] = self._trigger_now(order, ctx)
                    return holder["result"].broker_order_id or ""

                tel = self.scheduler.dispatch(plan, send=_send,
                                              abort_event=order.abort_event)
                result = holder.get("result")
                if tel.aborted:
                    result = SC.StrategyResult(
                        eid, order.strategy_id, "aborted",
                        detail="زمان‌بندی پیش از ارسال لغو شد",
                        timings={})
                elif result is None:
                    result = SC.StrategyResult(
                        eid, order.strategy_id, "failed",
                        detail="scheduler returned without a result")
                result.timings.update({
                    "drift_us": tel.drift_us,
                    "actual_send_wall_ms": tel.actual_send_wall_ms,
                    "clock_offset_ms": tel.clock_offset_ms,
                    "send_mono_ms": round(tel.send_mono * 1000.0, 3),
                })
            else:
                result = self._trigger_now(order, ctx)
        except StrategyError as e:
            result = SC.StrategyResult(
                eid, order.strategy_id, "blocked",
                detail=str(e.detail)[:200], error_code=e.code,
                evidence=dict(e.evidence))
        except Exception as e:                       # noqa: BLE001
            result = SC.StrategyResult(
                eid, order.strategy_id, "failed",
                detail="%s: %s" % (type(e).__name__, str(e)[:160]),
                error_code="UNEXPECTED")
        with self._lock:
            order.result = result
            order.state = result.status
            oc = self._outcomes.setdefault(order.strategy_id, Counter())
            oc[result.status] += 1
        self.metrics.record_result(order.strategy_id, result.timings)
        state = {"accepted": "submitted", "submitted": "submitted",
                 "dry_run": "dry_run", "unknown": "unknown",
                 "failed": "failed", "blocked": "blocked",
                 "aborted": "aborted"}.get(result.status, result.status)
        if result.unknown:
            self.arbiter.mark_unknown(eid, order.strategy_id, result.detail)
        else:
            self.arbiter.complete(eid, order.strategy_id, state, result.detail)
        self._finish_intent(order, result)
        return result

    def _finish_intent(self, order: SC.StrategyOrder,
                       result: SC.StrategyResult) -> None:
        key = order.intent_key
        if not key:
            return
        clicked = bool(result.evidence.get("click_attempted"))
        if result.status == "dry_run":
            state = "dry_run"
        elif result.status == "aborted":
            state = "aborted"
        elif result.status in ("accepted", "submitted", "reconciled"):
            state = "submitted"
        elif result.status == "unknown" or result.unknown:
            state = "unknown"
        elif result.status == "failed":
            state = ("rejected" if result.evidence.get("response_seen")
                     else ("unknown" if clicked else "failed_pre_click"))
        elif result.status == "blocked":
            if result.error_code == "DUPLICATE_GUARD":
                return
            state = "unknown" if clicked else "failed_pre_click"
        else:
            state = "unknown" if clicked else "failed_pre_click"
        if state == "failed_pre_click":
            self.intent_store.fail_pre_click(key, result.detail)
        else:
            self.intent_store.finish(key, state, result.detail, result=result.public())

    def _trigger_now(self, order: SC.StrategyOrder,
                     ctx: StrategyContext) -> SC.StrategyResult:
        strategy = self.strategies[order.strategy_id]
        return strategy.trigger(ctx, order)

    def abort(self, prepared_id: str) -> dict[str, Any]:
        with self._lock:
            order = self._orders.get(prepared_id)
        if order is None:
            raise StrategyError("INVALID_EXECUTION_ID", "no such prepared order")
        # Stop برایِ «پیش از ارسال» است؛ نتیجهٔ تمام‌شده را بازنویسی نمی‌کند.
        if order.result is not None and order.state not in ("prepared", "submitting"):
            return order.public()
        order.abort_event.set()
        settings = self._settings(order.strategy_id)
        ctx = self._ctx(settings, dry_run=True)
        try:
            self.strategies[order.strategy_id].abort(ctx, order)
        except Exception:
            pass
        self.arbiter.abort(order.execution_id)
        self.intent_store.abort(order.intent_key)
        order.state = "aborted"
        return order.public()

    def reconcile(self, prepared_id: str) -> SC.StrategyResult:
        with self._lock:
            order = self._orders.get(prepared_id)
        if order is None:
            raise StrategyError("INVALID_EXECUTION_ID", "no such prepared order")
        eid = order.execution_id
        result = order.result or SC.StrategyResult(
            eid, order.strategy_id, "unknown", detail="no result")
        if not result.unknown:
            return result
        t0 = now_ms()
        caps = getattr(self.adapter, "capabilities", lambda: None)()
        if not getattr(caps, "list_orders", False):
            result.detail = "reconcile impossible: broker exposes no order list"
            return result
        try:
            remote = self.adapter.get_orders()
        except Exception as e:                       # noqa: BLE001
            result.detail = "reconcile read failed: %s" % type(e).__name__
            return result
        d = order.draft
        want_isin = str(d.instrument.isin or "")
        want_side = d.side
        want_price = float(d.price or 0.0)
        want_qty = float(d.quantity or 0.0)
        cands = []
        for r in remote or []:
            try:
                if str(r.isin or "") != want_isin or r.side != want_side:
                    continue
                if abs(float(r.price or 0.0) - want_price) > max(0.01, abs(want_price) * 1e-6):
                    continue
                if abs(float(r.quantity or 0.0) - want_qty) > 1e-6:
                    continue
                cands.append(r)
            except Exception:
                continue
        result.timings["reconcile"] = round(now_ms() - t0, 3)
        if len(cands) == 1:
            hit = cands[0]
            result.status = "reconciled"
            result.unknown = False
            result.broker_order_id = hit.broker_order_id
            result.detail = "یک ردیفِ منطبق در فهرستِ کارگزاری پیدا شد"
            result.evidence["reconcile_match"] = "unique_fields"
            result.evidence["order_state"] = hit.order_state.value
            self.arbiter.complete(eid, order.strategy_id, "submitted",
                                  result.detail)
            self.intent_store.finish(order.intent_key, "confirmed",
                                     result.detail, result=result.public())
        elif not cands:
            result.detail = ("هیچ ردیفِ منطبقی در فهرست نیست؛ غیبت اثباتِ شکست نیست — "
                             "نتیجه نامعلوم می‌ماند")
            result.evidence["reconcile_match"] = "none"
        else:
            result.detail = "چند ردیفِ منطبق؛ سفارشِ درست قابلِ تعیین نیست"
            result.evidence["reconcile_match"] = "ambiguous"
            result.evidence["candidates"] = len(cands)
        self.metrics.record(order.strategy_id, "reconcile",
                            result.timings["reconcile"], ok=not result.unknown)
        return result

    def _selection(self) -> list[dict[str, Any]]:
        """رتبه‌بندیِ شواهد: dry و live جدا؛ live فقط با پذیرشِ دیده‌شده.

        Direct API در dry-run هیچ send ندارد و با مرورگرها هم‌شرط نیست؛ در آن
        حالت قابلِ انتخاب نیست. در live، فقط Strategyای که دستِ‌کم یک پذیرشِ
        واقعیِ همین پروسه دارد valid است؛ unknown یعنی reconcile، نه سرعت.
        """
        rows: list[dict[str, Any]] = []
        for r in self.list():
            sid = r["id"]
            if not r["settings"]["enabled"] or not r["available"]:
                continue
            m = (r["metrics"] or {}).get("total") or {}
            count = int(m.get("count") or 0)
            p50, p95, p99 = m.get("p50"), m.get("p95"), m.get("p99")
            outcomes = r.get("outcomes") or {}
            # Direct API پذیرشِ صریح را در وضعیتِ submitted گزارش می‌کند؛ هر دو
            # نشانهٔ «پاسخِ معناییِ پذیرش» هستند و در انتخابِ زنده یکی‌اند.
            accepted = int(outcomes.get("accepted") or 0) + int(outcomes.get("submitted") or 0)
            unknown = int(outcomes.get("unknown") or 0)
            dry_ok = count >= 5 and p95 is not None
            dry_reason = "" if dry_ok else "insufficient samples"
            if sid == SC.DIRECT_API and not self.live_allowed:
                dry_ok = False
                dry_reason = "direct dry-run has no send; compare in mock-live/live"
            live_ok = bool(dry_ok and accepted > 0 and self.live_allowed
                           and r["settings"]["mode"] == SC.MODE_LIVE)
            live_reason = ""
            if not live_ok:
                if not self.live_allowed:
                    live_reason = "live is gated"
                elif r["settings"]["mode"] != SC.MODE_LIVE:
                    live_reason = "strategy mode is not live"
                elif accepted == 0:
                    live_reason = "no accepted live sample yet"
                elif not dry_ok:
                    live_reason = dry_reason
            rows.append({
                "strategy": sid, "count": count, "p50": p50, "p95": p95,
                "p99": p99, "accepted": accepted, "unknown": unknown,
                "usable_dry": dry_ok, "usable_live": live_ok,
                "reason_dry": dry_reason, "reason_live": live_reason,
            })
        rows.sort(key=lambda x: (not x["usable_live"], not x["usable_dry"],
                                 x["p95"] if x["p95"] is not None else 1e18,
                                 x["p50"] if x["p50"] is not None else 1e18,
                                 x["strategy"]))
        return rows

    def status(self) -> dict[str, Any]:
        with self._lock:
            orders = [o.public() for o in self._orders.values()]
        strategies = self.list()
        return {"strategies": strategies,
                "rate_limiter": self.limiter.status(),
                "orders": sorted(orders, key=lambda o: -float(o.get("created_at") or 0))[:50],
                "live_allowed": self.live_allowed,
                "selection": self._selection()}

    def close(self) -> None:
        with self._lock:
            orders = list(self._orders.values())
        for o in orders:
            if o.state == "prepared":
                try:
                    self.abort(o.prepared_id)
                except Exception:
                    continue
            else:
                drv = getattr(o.prepared, "driver", None)
                if drv is not None:
                    try:
                        drv.close()
                    except Exception:
                        pass
        for _sid, drv in list(self._browser_drivers.items()):
            try:
                drv.close()
            except Exception:
                pass
        self._browser_drivers.clear()


__all__ = ["StrategyError", "StrategyContext", "PreparedHandle",
           "DirectApiStrategy", "AutoClickerStrategy", "DomStrategy",
           "JavaScriptStrategy", "KeyboardStrategy", "SeleniumStrategy",
           "StrategyEngine", "build_strategies"]
