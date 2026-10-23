# -*- coding: utf-8 -*-
"""execution_autoclick_executor.py — اقدامِ واقعی رویِ فرمِ مرورگر، با شاهد.

این «اتوکلیکر» است: در لحظۀ هدف، دکمۀ ثبتِ سفارشِ همان فرم را که مالک خودش
پر کرده می‌بیند و رویش کلیک می‌کند. هیچ HTTP جایگزینِ کلیک نمی‌شود و هیچ
مقداری در فرم نوشته نمی‌شود (قیمت/تعداد فقط خوانده و مقایسه می‌شوند).

سه حالتِ اجرا که با هم قاطی نمی‌شوند:

  • dry_run=true (پیش‌فرض): گاردِ catch-all رویِ همان صفحه سوار می‌شود؛ کلیک
    واقعی است و درخواستِ سفارش درِ مرورگر abort می‌شود. پس «دکمه پیدا شد و
    کلیک شد و درخواست ساخته شد» قابلِ اثبات است بی‌رسیدنِ سفارش به کارگزاری.
    عبورِ نوشتن از گارد ⇒ UNKNOWN (ادعای dry رد می‌شود).
  • live: فقط با تأییدِ صریحِ مالک؛ intercept با abort=false تا پاسخِ واقعی
    دیده شود؛ پذیرش از مفسرِ سیمِ کارگزاری می‌آید، نه از HTTP 200.
  • warm: پیش از هدف، فقط خوانش و داوری؛ هیچ کلیک/نگاشتِ مسیر.

تأخیرها جدا ثبت می‌شوند: قضاوتِ فرم، لحظۀ کلیک، کلیک→درخواست، درخواست→پاسخ.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping, Optional
from urllib.parse import urlparse

import execution_rate_limiter as RL
import execution_ui_state as UIS
from execution_telemetry import ExecutionTelemetry

def _now_ms_wall() -> int:
    return int(time.time() * 1000)


#: سقفِ شمارۀ اقدامِ بی‌درخواستِ دیده‌شده؛ بعد از آن اجرا متوقف می‌شود.
DEFAULT_REQUEST_TIMEOUT_MS = 1200
DEFAULT_RESPONSE_TIMEOUT_MS = 4000

#: کلیدهایی که زمان‌بند و rate limiter می‌خوانند؛ باید سطح-بالِ نتیجه باشند،
#: نه پنهان در evidence (وگرنه شاهدِ ۴۲۹ به قفلِ موقت تبدیل نمی‌شود).
CONTROL_KEYS = ("stop_run", "http_status", "response_body", "response_headers",
                "broker_order_id", "error_code", "ambiguous", "retry_after_ms",
                "dry_run_escape", "click_without_request", "verdict",
                "click_error", "dom_error")


@dataclass
class ExecutorContext:
    """چیزهایی که executor از بیرون می‌گیرد؛ همه تزریق‌پذیرند تا تست‌پذیر بماند."""
    driver: Any
    ui: UIS.UIOptions
    dry_run: bool = True
    order_paths: tuple[str, ...] = ("/core/api/v2/order",)
    order_method: str = "POST"
    intercept_pattern: str = "**/core/api/v2/order*"
    allowed_hosts: tuple[str, ...] = ("d.easytrader.ir",)
    request_timeout_ms: int = DEFAULT_REQUEST_TIMEOUT_MS
    response_timeout_ms: int = DEFAULT_RESPONSE_TIMEOUT_MS
    clock_probe: Optional[Callable[[], Mapping[str, Any]]] = None
    session_ok: Optional[Callable[[], tuple[bool, str]]] = None
    keep_warm_resolution: bool = True
    #: ساعتِ دیواری از همان منبعِ زمان‌بند؛ درِ تست ساختگی است تا شاهدِ زمانیِ
    #: شلیک با زمانِ برنامهٔ ساختگی یکی بماند.
    wall_ms: Callable[[], int] = _now_ms_wall
    #: انتظار تا لحظۀ هدف (claimِ زودهنگام). فقط مسیرِ زنده/واقعی؛ با ساعتِ
    #: ساختگی خاموش می‌ماند تا تست‌ها بی‌پایان نشوند.
    wait_for_target: bool = False


@dataclass
class WarmCache:
    """نتیجۀ ارزیابیِ پیش‌از‌هدف؛ فقط برایِ کوتاه‌کردنِ مسیرِ بحرانی، نه برایِ بی‌چک."""
    resolution: dict[str, Any] = field(default_factory=dict)
    signature: dict[str, Any] = field(default_factory=dict)
    page_path: str = ""
    at_ms: int = 0
    ok: bool = False
    reason: str = ""

    def public(self) -> dict[str, Any]:
        return {"ok": bool(self.ok), "reason": self.reason[:200],
                "at_ms": self.at_ms, "verdict": self.resolution.get("verdict"),
                "button_index": (self.resolution.get("button") or {}).get("index"),
                "checks": dict(self.resolution.get("checks") or {})}


def _origin_ok(url: str, allowed: tuple[str, ...]) -> tuple[bool, str]:
    host = (urlparse(str(url or "")).hostname or "").lower()
    if not host:
        return False, "no host on the page url"
    for a in allowed:
        if host == a or host.endswith("." + a):
            return True, host
    return False, host


class AutoClickExecutor:
    """یک اقدام = یک کلیکِ قابلِ ردیابی رویِ دکمه‌ای که قضاوت شده است."""

    def __init__(self, ctx_provider: Callable[[], ExecutorContext]) -> None:
        self._ctx_provider = ctx_provider
        self.warm = WarmCache()
        self.last_resolution: dict[str, Any] = {}
        self.last_outcome: dict[str, Any] = {}
        #: شمارشِ داخلی برایِ ادعاهایِ «چند کلیک شد» — هرگز جای شمارندۀ store را نمی‌گیرد.
        self.clicks = 0

    # ---- warm ----
    def run_warm(self) -> dict[str, Any]:
        """ارزیابیِ فرم/دکمه پیش از هدف. هیچ کلیک، هیچ نگاشتِ مسیرِ نوشتن."""
        ctx = self._ctx_provider()
        t0 = time.monotonic()
        out: dict[str, Any] = {"ok": False, "reason": "", "elapsed_ms": 0.0}
        try:
            page_url = str(ctx.driver.url() or "")
            ok_host, host = _origin_ok(page_url, ctx.allowed_hosts)
            if not ok_host:
                out["reason"] = "صفحه در میزبانِ مجاز نیست (%s)" % host
                return out
            state = UIS.read_ui_state(ctx.driver, ctx.ui)
            res = UIS.judge(state, ctx.ui)
            self.warm = WarmCache(resolution=res.public(),
                                  signature=dict(res.evidence.get("dom_signature") or {}),
                                  page_path=(urlparse(page_url).path or "/"),
                                  at_ms=_now_ms_wall(), ok=bool(res.ok),
                                  reason=res.reason)
            self.last_resolution = res.public()
            out.update({"ok": bool(res.ok), "reason": res.reason,
                        "verdict": res.verdict, "checks": res.checks,
                        "button": res.button})
        except Exception as e:                       # noqa: BLE001
            out["reason"] = "warm failed: %s" % type(e).__name__
        finally:
            out["elapsed_ms"] = round((time.monotonic() - t0) * 1000.0, 3)
        return out

    # ---- یک اقدام ----
    def __call__(self, run: Any, action: Any, hooks: Any) -> dict[str, Any]:
        ctx = self._ctx_provider()
        wall = ctx.wall_ms
        tel = ExecutionTelemetry()
        t_start = time.monotonic()
        tel.execution_start_mono_ms = round(t_start * 1000.0, 3)
        tel.execution_start_wall_ms = wall()
        tel.scheduled_target_wall_ms = int(run.config.planned_action_at_ms(action.idx))
        evidence: dict[str, Any] = {"action_idx": int(action.idx),
                                    "dry_run": bool(ctx.dry_run)}

        def outcome(state: str, reason: str, *, fired: bool = False,
                    stop: Optional[bool] = None, **extra: Any) -> dict[str, Any]:
            out = {"state": state, "reason": reason[:300], "fired": bool(fired),
                    "telemetry": tel.to_dict(), "metrics": tel.latencies(),
                    "evidence": {**evidence, **extra},
                    "validation_ms": round((time.monotonic() - t_start) * 1000.0, 3),
                    "at_wall_ms": wall()}
            for key in CONTROL_KEYS:
                if key in extra:
                    out[key] = extra[key]
            if stop is not None:
                out["stop_run"] = bool(stop)
            self.last_outcome = out
            return out

        # ۱) نشستِ مرورگر و نشانیِ صفحه — چکِ تازه، ارزان
        if not getattr(ctx.driver, "is_alive", lambda: False)():
            return outcome("BROWSER_LOST", "اتصالِ مرورگر برقرار نیست", stop=True)
        try:
            url = str(ctx.driver.url() or "")
        except Exception:                            # noqa: BLE001
            return outcome("BROWSER_LOST", "صفحهٔ مرورگر خوانده نشد (تب بسته یا ناوبری)",
                           stop=True)
        ok_host, host = _origin_ok(url, ctx.allowed_hosts)
        evidence["page_host"] = host
        if not ok_host:
            return outcome("SESSION_LOST",
                           "صفحه از میزبانِ مجاز رفته است (%s)" % host, stop=True)
        if ctx.session_ok is not None:
            try:
                sess_ok, sess_why = ctx.session_ok()
            except Exception as e:                   # noqa: BLE001
                sess_ok, sess_why = False, "session check failed: %s" % type(e).__name__
            evidence["session_check"] = ("OK" if sess_ok else str(sess_why)[:120])
            if not sess_ok:
                return outcome("SESSION_LOST", "ورودِ کاربر تأیید نشده: %s" % sess_why,
                               stop=True)
        if hooks.should_stop():
            return outcome("STOPPED", "توقف پیش از اجرا ثبت شد", stop=True)

        # ۲) خوانش + داوریِ فرم (فقط‌خواندنی)
        t_val = time.monotonic()
        try:
            state = UIS.read_ui_state(ctx.driver, ctx.ui)
        except Exception as e:                       # noqa: BLE001
            return outcome("UNKNOWN", "خوانشِ DOM ممکن نشد (%s)" % type(e).__name__,
                           dom_error=type(e).__name__, stop=True)
        res = UIS.judge(state, ctx.ui)
        now_path = (urlparse(url).path or "/")
        dom_path = str(state.get("url_path") or "")
        evidence["window_path"] = now_path
        evidence["dom_path"] = dom_path
        if self.warm.page_path and now_path != self.warm.page_path:
            return outcome("PAGE_CHANGED",
                           "صفحه از زمانِ ارزیابیِ اولیه جابه‌جا شده است (%s → %s)"
                           % (self.warm.page_path, now_path), stop=True)
        if dom_path and dom_path.rstrip("/") != now_path.rstrip("/"):
            #: خوانشِ DOM با نشانیِ پنجره نمی‌خواند: ناوبریِ میانی، فریمِ دیگر، یا
            #: شاهدِ کهنه. در هر سه حالت کلیک رویِ «همان» فرم اثبات نشده است.
            return outcome("PAGE_CHANGED",
                           "خوانشِ DOM (%s) با نشانیِ پنجره (%s) یکی نیست"
                           % (dom_path, now_path), stop=True)
        evidence["form"] = {"symbol_text": res.evidence.get("form_symbol_text"),
                            "price": res.evidence.get("form_price"),
                            "quantity": res.evidence.get("form_quantity"),
                            "counts": res.evidence.get("counts"),
                            "tabs": res.evidence.get("tabs")}
        evidence["resolution"] = {"verdict": res.verdict, "checks": res.checks,
                                  "reasons": res.reasons[:4],
                                  "button": res.button}
        self.last_resolution = res.public()
        signature = dict(res.evidence.get("dom_signature") or {})
        if self.warm.ok and UIS.signature_changed(self.warm.signature, signature):
            return outcome("MISMATCH",
                           "DOM بینِ ارزیابیِ اولیه و لحظۀ اجرا تغییر کرده است؛ "
                           "اقدام نمی‌شود", stop=True,
                           warm_signature=self.warm.signature, now_signature=signature)
        if not res.ok:
            #: نامِ وضعیت از همان داوری می‌آید؛ «مبهم» را «نامطابقت» ننویس.
            state_name = {"AMBIGUOUS": "AMBIGUOUS",
                          "NO_BUTTON": "NO_BUTTON",
                          "NO_USABLE_BUTTON": "NO_USABLE_BUTTON",
                          "WRONG_SIDE_ONLY": "WRONG_SIDE_ONLY"}.get(
                              res.verdict, "MISMATCH")
            return outcome(state_name, res.reason, stop=True, verdict=res.verdict)
        button = dict(res.button or {})
        evidence["button_before_click"] = {k: button.get(k) for k in
                                           ("index", "text", "aria", "path", "rect")}
        evidence["validation_checks"] = res.checks
        # ساعتِ کارگزاری فقط در حالتِ زنده گیت است (در dry-run مانعِ اثباتِ کلیک نیست)
        if ctx.clock_probe is not None:
            try:
                clk = dict(ctx.clock_probe() or {})
            except Exception:                        # noqa: BLE001
                clk = {}
            if clk.get("delta_ms") is not None:
                tel.clock_offset_ms = float(clk.get("delta_ms") or 0.0)
                tel.clock_quality = "broker-server-time"
            evidence["clock"] = {"verified": bool(clk.get("verified")),
                                 "delta_ms": clk.get("delta_ms"),
                                 "rtt_ms": clk.get("rtt_ms")}
            if not ctx.dry_run and clk and not clk.get("verified"):
                return outcome("BLOCKED", "ساعتِ کارگزاری تأیید نشد؛ اجرایِ زنده ممنوع",
                               stop=True)
        evidence["form_validation_ms"] = round((time.monotonic() - t_val) * 1000.0, 3)

        # ۳) گارد/intercept پیش از انتظارِ هدف؛ هزینهٔ setup بیرونِ لحظهٔ شلیک
        try:
            if ctx.dry_run:
                ctx.driver.dry_run_guard(order_paths=list(ctx.order_paths),
                                        order_method=ctx.order_method)
                evidence["dry_run_guard"] = True
            else:
                ctx.driver.intercept(ctx.intercept_pattern, abort=False)
                evidence["intercept"] = ctx.intercept_pattern
        except Exception as e:                       # noqa: BLE001
            return outcome("UNKNOWN",
                           "گاردِ مسیرِ نوشتن بسته نشد؛ کلیک نمی‌کنیم (%s)"
                           % type(e).__name__, stop=True)

        # ۴) انتظار تا لحظۀ هدف. scheduler با CLAIM_LEAD_MS زودتر claim می‌کند
        #    تا اعتبارسنجی همین‌جا تمام شود و کلیک رویِ هدف بیفتد.
        target = int(tel.scheduled_target_wall_ms or 0)
        now_ms = wall()
        if (ctx.wait_for_target and target > now_ms
                and (target - now_ms) <= 5000):
            deadline_mono = time.monotonic() + (target - now_ms) / 1000.0 + 0.05
            while wall() < target and time.monotonic() < deadline_mono:
                left = target - wall()
                if left > 25:
                    time.sleep((left - 15) / 1000.0)
                else:
                    time.sleep(0.002)

        # ۵) کلیک رویِ لحظۀ هدف؛ ثبتِ شمارنده بعد از شروعِ کلیک (نه قبل از آن).
        #    نوشتنِ SQLite رویِ همان دیسک ۴۰–۲۳۰ms طول می‌کشد (سنجش ۲۰۲۶-۱۰-۲۴)
        #    و اگر قبل از کلیک بیفتد، شلیک را از هدف عقب می‌انداخت.
        fire_at = wall()
        tel.send_started_mono_ms = round(time.monotonic() * 1000.0, 3)
        tel.send_started_wall_ms = wall()
        try:
            got = ctx.driver.click_nth(ctx.ui.submit_selector, int(button.get("index", 0)),
                                       expect={"aria": button.get("aria") or "",
                                               "text": button.get("text") or ""},
                                       timeout_ms=ctx.request_timeout_ms)
        except Exception as e:                       # noqa: BLE001
            code = str(e).split(":")[0][:30]
            return outcome("BLOCKED",
                           "کلیک انجام نشد: %s" % str(e)[:180], stop=True,
                           click_error=code)
        t_mark = time.monotonic()
        marked = hooks.mark_fired(fire_at)
        evidence["mark_fired_ms"] = round((time.monotonic() - t_mark) * 1000.0, 3)
        evidence["fired_marked"] = bool(marked)
        self.clicks += 1
        tel.browser_click_started_mono_ms = float(got.get("start_ms") or
                                                 tel.send_started_mono_ms)
        evidence["click"] = {"start_ms": got.get("start_ms"), "end_ms": got.get("end_ms"),
                             "checks": got.get("checks"), "index": got.get("index")}

        # ۵) شاهدِ شبکه و نتیجه
        req = None
        try:
            req = ctx.driver.wait_for_request(ctx.request_timeout_ms)
        except Exception:                            # noqa: BLE001
            req = None
        if req is not None:
            tel.request_started_mono_ms = float(req.get("mono_ms") or 0.0) or None
            tel.request_started_wall_ms = wall()
            evidence["request"] = {"path": urlparse(str(req.get("url") or "")).path,
                                   "method": req.get("method"),
                                   "blocked": bool(req.get("blocked")),
                                   "classification": req.get("classification")}
        resp = None
        if req is not None and not ctx.dry_run:
            try:
                resp = ctx.driver.wait_for_response(ctx.response_timeout_ms)
            except Exception:                        # noqa: BLE001
                resp = None
            if resp is not None:
                tel.response_received_mono_ms = float(resp.get("mono_ms") or 0.0) or None
                evidence["response"] = {"status": resp.get("status"),
                                        "keys": sorted((resp.get("body") or {}).keys())
                                        if isinstance(resp.get("body"), dict) else None,
                                        "content_type": str(resp.get("content_type") or "")[:40],
                                        "retry_after": resp.get("retry_after")}
        net: dict[str, Any] = {}
        try:
            net = dict(ctx.driver.network() or {})
        except Exception:                            # noqa: BLE001
            net = {}
        evidence["network"] = {"requests": net.get("requests"), "writes": net.get("writes"),
                               "blocked_writes": net.get("blocked_writes"),
                               "escaped_writes": net.get("escaped_writes"),
                               "order_writes": net.get("order_writes"),
                               "other_writes": net.get("other_writes"),
                               "order_posts": net.get("order_posts"),
                               "source": net.get("source")}
        out_state, out_reason, extra = self._verdict(ctx, req, resp, net, evidence)
        return outcome(out_state, out_reason, fired=True, **extra)

    # ---- تفسیر ----
    def _verdict(self, ctx: ExecutorContext, req: Optional[Mapping[str, Any]],
                 resp: Optional[Mapping[str, Any]], net: Mapping[str, Any],
                 evidence: Mapping[str, Any]) -> tuple[str, str, dict[str, Any]]:
        escaped = int(net.get("escaped_writes") or 0)
        blocked = int(net.get("blocked_writes") or 0)
        writes = int(net.get("writes") or 0)
        order_writes = int(net.get("order_writes") or 0)
        if ctx.dry_run:
            if escaped or (writes > 0 and blocked < writes):
                return ("UNKNOWN",
                        "نوشتن از گاردِ dry-run عبور کرد؛ ممکن است به کارگزاری رسیده "
                        "باشد — ادامه نمی‌دهیم",
                        {"stop_run": True, "dry_run_escape": True,
                         "escaped_writes": escaped, "writes": writes})
            if req is None or order_writes == 0:
                return ("NOT_SENT",
                        "کلیک انجام شد ولی هیچ درخواستِ سفارشی دیده نشد؛ "
                        "بررسی می‌خواهد", {"stop_run": True, "click_without_request": True})
            return ("DRY_RUN",
                    "دکمه پیدا و کلیک شد و درخواستِ سفارش درِ مرورگر دیده و abort شد؛ "
                    "هیچ POSTی به کارگزاری نرسید", {"stop_run": False})
        if req is None:
            return ("NOT_SENT", "کلیک شد ولی هیچ درخواستِ سفارشی دیده نشد",
                    {"stop_run": True, "click_without_request": True})
        if resp is None:
            return ("UNKNOWN", "درخواست رفت ولی پاسخی دیده نشد؛ نتیجه نامعلوم",
                    {"stop_run": True})
        from execution_easytrader import interpret_easytrader_response
        status = int(resp.get("status") or 0)
        body = resp.get("body")
        verdict = interpret_easytrader_response(status, body, where="autoclick")
        extra = {"http_status": status, "response_body": body,
                 "response_headers": ({"Retry-After": resp.get("retry_after")}
                                      if resp.get("retry_after") else {}),
                 "broker_order_id": verdict.broker_order_id,
                 "oms_errors": [dict(x) for x in (verdict.oms_errors or ())][:4],
                 "ambiguous": bool(verdict.ambiguous),
                 "retry_after_ms": verdict.retry_after_ms}
        if verdict.accepted is True:
            return ("ACCEPTED",
                    "کارگزاری پذیرش را صریح گفت (کدپیگیری=%s)" % (verdict.broker_order_id or "-"),
                    {**extra, "stop_run": False})
        if verdict.accepted is False:
            #: توقف وقتی شاهدِ نرخ باشد: کدِ OMSِ شناخته‌شده، ۴۲۹، Retry-After، یا
            #: متنِ پیامِ محدودیت. متن مستقل از املایِ کلیدِ envelope خوانده می‌شود؛
            #: وابستنِ داوری به شکلِ بدنه نشانهٔ شکنندگی است.
            codes = {str((e or {}).get("code", "")) for e in (verdict.oms_errors or ())}
            stop = bool(verdict.retry_after_ms) or status == 429 or bool(
                codes & set(RL.OMS_THROTTLE_CODES)) or RL.looks_like_throttle(
                    status=status, body=body,
                    headers=(dict(resp or {}).get("headers") or {}))
            return ("REJECTED", verdict.detail or verdict.message or "رد شد",
                    {**extra, "stop_run": stop,
                     "error_code": verdict.error.value if verdict.error else "BROKER_REJECTED"})
        return ("UNKNOWN", "پاسخ مبهم است؛ reconcile لازم است و ادامه نمی‌دهیم",
                {**extra, "stop_run": True})

    def status(self) -> dict[str, Any]:
        return {"warm": self.warm.public(),
                "last_resolution": self.last_resolution,
                "last_outcome": {k: v for k, v in self.last_outcome.items()
                                 if k not in ("evidence", "telemetry")},
                "clicks_recorded_by_executor": self.clicks}


__all__ = ["AutoClickExecutor", "ExecutorContext", "WarmCache",
           "DEFAULT_REQUEST_TIMEOUT_MS", "DEFAULT_RESPONSE_TIMEOUT_MS"]
