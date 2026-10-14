# -*- coding: utf-8 -*-
# dev/easytrader_adapter_v1113.py — گاردِ آداپتورِ EasyTrader + تفسیرِ پاسخِ سیم
#
# مأموریتِ ۱۴۰۵-۰۷-۲۴ §۶ و دست‌نویسِ تحویل §۴-۵. این سوئیت «تستِ Mockِ دوم» نیست:
# آداپتورِ واقعی (`execution_easytrader.py`) را رویِ یکِ **بروکرِ بدیلِ سمتِ سرور**
# می‌چرخاند — همان پاسخ‌هایی که پنج مخزن گزارش کرده‌اند، با همان قالب. هیچ
# درخواستی به کارگزاری نمی‌رود و هیچ سفارشِ واقعی ساخته نمی‌شود.
#
# چهار چیزی که نگهبانش است (و همه با کنترلِ منفیِ خودش):
#
#   ۱) ۲xx هیچ حکمی نیست. ۲۰۰ + `isSuccessful:false` **باید** رد شود — و پاسخِ
#      ردشده درِ مرجع `id` هم دارد، پس «id داشت» هرگز پذیرش نیست.
#      کنترلِ منفی: `SloppyWire` که ۲xx را پذیرش می‌خواند باید درِ همین سنجه بیفتد.
#   ۲) timeout ⇒ UNKNOWN و **ممنوعیتِ ارسالِ دوباره** تا رفعِ ابهام از
#      `GET /core/api/order`. کنترلِ منفی: ترافیکی که خودش retry می‌کند باید دو
#      سفارشِ واقعی درِ دفترِ بروک بسازد و گارد همین را ببیند.
#   ۳) هیچ secret درِ لاگ، ردِّپا، پاسخِ HTTP یا `repr()` نمی‌ماند.
#   ۴) بی‌نشست، capabilities «هیچ» است و `live_enabled` false — نه Connectedِ ظاهری.
#
# قراردادِ عمومیِ `BrokerAdapter` هم دوباره استفاده می‌شود: `run_contract` از
# گاردِ `execution_contract_v1` رویِ همین آداپتور اجرا می‌شود (بندِ ۲۹ دستورِ کار:
# «هر adapterِ واقعی باید از همان سوئیت سبز بیرون بیاید»). فقط **یک** case از آن
# معنایش با این آداپتور فرق دارد و درِ §۴ صریح بیرون کشیده و *بازنویسی* شده
# — نه خاموش.
#
# آفلاین است: هیچ شبکه، هیچ کارگزاری، هیچ سفارشِ واقعی. بی‌خوابِ بلند (چرخۀِ
# زمان‌بندی با ساعتِ تزریق‌شده و آستانهٔ میلی‌ثانیه‌ای می‌چرخد).
# اجرا:  python dev/easytrader_adapter_v1113.py

import os
import socket
import sys
import threading
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from execution_contract import (  # noqa: E402
    BrokerError, Capabilities, ErrorCode, ExecutionStatus, InstrumentRef,
    OrderDraft, OrderState, Resolution, SessionState, Side, redact,
)
from execution_easytrader import (  # noqa: E402
    ADAPTER_NAME, WIRE_BASE_URL, WIRE_HYPOTHESIS, WIRE_PATH_ORDER_CREATE,
    WIRE_PATH_ORDER_LIST, WIRE_PATH_QUEUE, EasyTraderAdapter, RefusingTransport,
    RequestsTransport, Timeouts, TransportNetwork, TransportTimeout, WireResponse,
    client_clock_label, easytrader_payload, interpret_easytrader_response,
    map_order_state,
)
from execution_ledger import ARMED, HALT, ExecutionLedger  # noqa: E402
from execution_service import ExecutionService, Limits  # noqa: E402
from execution_timing import Scheduler, TimeSource  # noqa: E402

import api.execution as EX  # noqa: E402

PASS = FAIL = 0

#: tokenِ آزمون — عمداً همان رشته‌ای که سوئیتِ قرارداد دنبالش می‌گردد تا
#: پاک‌سازیِ واقعی سنجیده شود، نه غیبتِ تصادفیِ آن.
SECRET = "super-secret-token-value"

FOOLAD = InstrumentRef(symbol="فولاد", ins_code="46348559193224090",
                       isin="IRO1IKCO0001", broker_instrument="IRO1IKCO0001",
                       resolution=Resolution.EXACT)
NO_ISIN = InstrumentRef(symbol="پارسان", ins_code="999", isin=None,
                        broker_instrument=None, resolution=Resolution.EXACT)


def ck(cond, what, got=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {what}")
    else:
        FAIL += 1
        print(f"  FAIL {what}" + (f"  -> {got}" if got else ""))


def draft(execution_id="EX-1", instrument=FOOLAD, side=Side.BUY,
          price=12610.0, quantity=1000.0) -> OrderDraft:
    return OrderDraft(execution_id=execution_id, instrument=instrument, side=side,
                      price=price, quantity=quantity, price_source="board.p_last",
                      price_as_of="2026-10-15T09:00:00")


def _js(d) -> str:
    import json
    return json.dumps(d, ensure_ascii=False)


# ── بروکرِ بدیلِ سمتِ سرور (فقط درِ همین گارد) ──────────────────────────────
class ScriptedBroker:
    """دفترِ سفارش‌هایی که «سرور» ساخته — حتی وقتی کلاینت پاسخ ندیده است.

    این تنها جایی است که می‌توان ثابت کرد timeout واقعاً «شاید قبول شد» است، و
    اینکه retryِ کور چند سفارش می‌سازد.
    """

    def __init__(self) -> None:
        self.orders: list[dict] = []
        self.outcomes: dict[str, list] = {}
        self.calls: list[str] = []
        self.expired = False
        self.queue_rows: dict[str, list] = {}
        self.server_time = "2026/10/15 09:00:00"
        self._next = 1
        self._sent = 0
        self.adapter = None            # برایِ ترتیبِ قصد‌ها

    def script(self, execution_id: str, outcome) -> None:
        self.outcomes[execution_id] = list(outcome) if isinstance(outcome, list) else [outcome]

    def next_outcome(self) -> str:
        """qصدِ i-ام ازِ خودِ آداپتور: `submit_order` intent را *پیش ازِ* POST می‌گذارد."""
        order = list(self.adapter._intents.keys()) if self.adapter else []
        eid = order[self._sent] if self._sent < len(order) else ""
        self._sent += 1
        seq = self.outcomes.get(eid)
        if not seq:
            return "ok"
        return seq.pop(0) if len(seq) > 1 else seq[0]

    def create(self, payload: dict):
        oc = self.next_outcome()
        inner = payload.get("order") or {}
        row = {"id": "BR-%05d" % self._next, WIRE_ID: inner.get("symbolIsin"),
               "symbolIsin": inner.get("symbolIsin"),
               "symbolName": inner.get("symbolName"), "side": inner.get("side"),
               "price": inner.get("price"), "quantity": inner.get("quantity"),
               "orderStateStr": "Waiting", "executedQuantity": 0}
        self._next += 1
        if oc == "ok":
            self.orders.append(row)
            return 200, {"isSuccessful": True, "id": row["id"], "message": "ok"}
        if oc == "timeout":
            self.orders.append(row)              # سرور پذیرفت، کلاینت ندید
            raise TransportTimeout("scripted timeout")
        if oc == "retry_trap":                    # ترافیکِ بدقلق: دوباره می‌فرستد
            self.orders.append(row)
            second = dict(row, id="BR-%05d" % self._next)
            self._next += 1
            self.orders.append(second)
            raise TransportNetwork("scripted network error after two creates")
        if oc == "http5xx":
            return 500, {"raw": "internal error"}
        if oc == "html200":
            return 200, None                      # ۲۰۰ با بدنۀِ غیرِ JSON
        if oc == "no_flag":
            return 200, {"id": row["id"], "message": "در حالِ بررسی"}
        if oc == "reject_price":
            # پاسخِ ردشده درِ مرجع `id` هم دارد — و همان چیزی است که «id داشت» را
            # از «پذیرفته شد» جدا می‌کند. عمداً درِ دفترِ سفارش‌ها رد نمی‌شود.
            return 200, {"isSuccessful": False, "id": row["id"],
                         "message": "INVALID_PRICE :: قیمت خارج از بازهٔ مجاز",
                         "omsError": [{"name": "price", "error": "خارج از بازه",
                                       "code": "INVALID_PRICE"}]}
        if oc == "reject_quantity":
            return 200, {"isSuccessful": False, "message": "حجمِ کمتر از حدِ مجاز",
                         "omsError": [{"name": "quantity", "code": "Q_MIN"}]}
        if oc == "reject_broker":
            return 200, {"isSuccessful": False, "message": "سفارش درِ وضعیتِ فعلی "
                         "پذیرفته نشد", "omsError": [{"name": "state",
                         "error": "mismatch", "code": "OMS_51"}]}
        if oc == "auth":
            return 403, {"isSuccessful": False, "message": "forbidden"}
        if oc == "expired":
            self.expired = True
            return 401, {"isSuccessful": False, "message": "token expired"}
        if oc == "rate_limited":
            return 429, {"isSuccessful": False, "message": "too many"}
        if oc == "market_closed":
            return 400, {"isSuccessful": False, "message": "خارج از بازهٔ معاملاتی"}
        raise AssertionError("unknown outcome: " + oc)


WIRE_ID = "id"


class ScriptedTransport:
    """ترافیکِ بدیلِ سمتِ سرور. `is_live=True` — ولی هیچ سوکتی نمی‌زند."""
    name = "scripted"
    is_live = True

    def __init__(self, broker: ScriptedBroker) -> None:
        self.broker = broker

    def request(self, *, method: str, url: str, headers, payload=None,
                timeout_s: float = 7.0) -> WireResponse:
        path = url.replace(WIRE_BASE_URL, "")
        self.broker.calls.append("%s %s" % (method, path))
        if path == WIRE_PATH_ORDER_CREATE and method == "POST":
            status, body = self.broker.create(payload or {})
            if body is None:
                return WireResponse(status, {}, "<html><body>login</body></html>")
            hdr = {"Retry-After": "0.5"} if status == 429 else {}
            return WireResponse(status, hdr, _js(body) if body is not None else "")
        if self.broker.expired:
            return WireResponse(401, {}, _js({"isSuccessful": False,
                                             "message": "token expired"}))
        if path == WIRE_PATH_ORDER_LIST:
            return WireResponse(200, {}, _js({"orders": self.broker.orders}))
        if path.startswith(WIRE_PATH_QUEUE):
            oid = (headers or {}).get("order-id", "")
            return WireResponse(200, {}, _js({"orderPlaces":
                                             self.broker.queue_rows.get(oid, [])}))
        return WireResponse(404, {}, _js({"isSuccessful": False, "message": "no path"}))


def et_build(**kw) -> EasyTraderAdapter:
    """سازندۀِ هم‌امضایِ `execution_contract_v1.builder` برایِ آداپتورِ واقعی."""
    broker = ScriptedBroker()
    for eid, outs in (kw.get("script") or {}).items():
        broker.script(eid, outs)
    a = EasyTraderAdapter(transport=ScriptedTransport(broker), token=SECRET,
                          instruments=kw.get("instruments") or (),
                          capabilities=kw.get("capabilities"))
    broker.adapter = a
    a._broker = broker                    # فقط برایِ سنجه‌هایِ خودِ این گارد
    return a


# ── ۱) هیچ شبکه‌ای درِ ساخت و درِ مسیرِ بی‌نشست ──────────────────────────────
def part_no_network():
    print("── ۱ بی‌سوکت تا نشستِ مالک نباشد")
    real = socket.socket
    blows = []

    def trip(*a, **k):
        blows.append("socket")
        raise AssertionError("هیچ سوکتی نباید باز شود")

    socket.socket = trip                      # type: ignore[assignment]
    try:
        a = EasyTraderAdapter()
        ck(True, "ساختِ آداپتور بی‌ترافیک ممکن است (درِ import هم همین مسیر است)")
        caps = a.capabilities()
        ck(caps.place is False and caps.list_orders is False,
           "بی‌نشست capabilities «هیچ» است، نه «صفر مجاز»", str(caps))
        ck(a.session_status().state is SessionState.DISCONNECTED,
           "بی‌token وضعیتِ نشست disconnected است", str(a.session_status()))
        try:
            a.submit_order(draft())
            ck(False, "بی‌نشست submit_order باید رد شود")
        except BrokerError as e:
            ck(e.code is ErrorCode.UNSUPPORTED and not e.is_unknown_result,
               "ارسالِ بی‌نشست ردِ *قطعی* می‌دهد، نه ابهام", e.code.value)
        try:
            a.get_orders()
            ck(False, "خواندنِ بی‌نشست هم باید رد شود")
        except BrokerError as e:
            ck(e.code is ErrorCode.UNSUPPORTED, "خواندنِ بی‌نشست UNSUPPORTED",
               e.code.value)
        p = a.probe()
        ck(p.get("ok") is False and p.get("order_endpoint_touched") is False,
           "probe بی‌نشست هیچ درِ نمی‌زند و همان را می‌گوید", str(p)[:90])
        ck(not blows, "هیچ سوکتی باز نشد", str(blows))
    finally:
        socket.socket = real                  # type: ignore[assignment]

    tr = RequestsTransport()
    ck(tr.is_live is True, "ترافیکِ واقعی تزریق‌پذیر است (ولی اینجا هرگز صدا زده نشد)")
    src = open(os.path.join(ROOT, "execution_easytrader.py"), encoding="utf-8").read()
    ck("max_retries=0" in src, "لایۀِ HTTP با max_retries=0 — retryِ پنهانِ urllib3 ممنوع")
    ck("allow_redirects=False" in src, "بازارسالِ 3xx رویِ POST ممنوع")
    ck("verify=self._verify" in src and "verify=True" in src,
       "بررسیِ TLS پیش‌فرضِ روشن است (برخلافِ ignoreHTTPSErrorsِ مرجع)")
    ck(getattr(tr._s, "verify", None) is True,
       "بررسیِ TLS درِ نشستِ واقعی روشَن است (نه ignoreHTTPSErrorsِ مرجع)",
       str(getattr(tr._s, "verify", None)))
    mad = tr._s.adapters.get("https://")
    mtotal = getattr(getattr(mad, "max_retries", None), "total",
                     getattr(mad, "max_retries", None))
    ck(mtotal == 0,
       "retryِ پنهانِ urllib3 درِ آداپتورِ mounted خاموش است (total=0)",
       str(mtotal))


# ── ۲) تفسیرِ پاسخ — قلبِ قفلِ ۱ و ۳ ────────────────────────────────────────
def part_interpret():
    print("── ۲ تفسیرِ پاسخ: ۲xx هیچ حکمی نیست")
    v = interpret_easytrader_response(200, _js({"isSuccessful": True, "id": "BR-1"}))
    ck(v.accepted is True and v.broker_order_id == "BR-1" and not v.is_unknown_result,
       "۲۰۰ + isSuccessful:true ⇒ پذیرش", str(v)[:90])

    # ★ کنترلِ منفیِ اصلی: ۲۰۰ با isSuccessful:false — و `id` هم دارد.
    rej = {"isSuccessful": False, "id": "BR-2",
           "message": "INVALID_PRICE :: خارج از بازه",
           "omsError": [{"name": "price", "error": "خارج از بازه",
                         "code": "INVALID_PRICE"}]}
    v = interpret_easytrader_response(200, _js(rej))
    ck(v.accepted is False and v.error is ErrorCode.INVALID_PRICE
       and v.broker_order_id is None and not v.is_unknown_result,
       "۲۰۰ + isSuccessful:false ⇒ ردِ *قطعی* با کدِ OMS، و idِ پاسخِ ردشده "
       "نگه نمی‌ماند", str(v)[:130])
    ck(bool(v.oms_errors) and v.oms_errors[0].get("code") == "INVALID_PRICE",
       "omsError[{name,error,code}] عیناً منتقل می‌شود", str(v.oms_errors)[:90])

    class SloppyWire:
        """همان باگی که چهار از پنج مخزن دارند: ۲xx ⇒ موفق، و id ⇒ پذیرش."""
        def accepted(self, status, body):
            return 200 <= status < 300

    sloppy_ok = SloppyWire().accepted(200, rej)
    ck(sloppy_ok is True,
       "کنترلِ منفی: تفسیرِ بدقلق همین پاسخِ ردشده را «پذیرش» می‌خواند "
       "(پس سنسور زنده است)")
    ck(interpret_easytrader_response(200, _js(rej)).accepted is False,
       "کنترلِ منفی: تفسیرِ درست همان پاسخ را رد می‌کند")

    for status, code in ((408, ErrorCode.TIMEOUT), (500, ErrorCode.NETWORK_ERROR),
                         (502, ErrorCode.NETWORK_ERROR), (503, ErrorCode.NETWORK_ERROR)):
        v = interpret_easytrader_response(status, _js({"x": 1}))
        ck(v.accepted is None and v.error is code and v.is_unknown_result,
           "%d ⇒ ابهام، نه ردِ قطعی" % status, str(v)[:80])
    v = interpret_easytrader_response(401, _js({"isSuccessful": False}))
    ck(v.error is ErrorCode.SESSION_EXPIRED and v.accepted is False,
       "۴۰۱ ⇒ نشستِ باطل‌شده (بی‌retry)")
    v = interpret_easytrader_response(403, _js({"isSuccessful": False}))
    ck(v.error is ErrorCode.AUTH_FAILED and v.accepted is False,
       "۴۰۳ ⇒ اجازه‌ای نبود — از «منقضی» جداست")
    v = interpret_easytrader_response(429, _js({"isSuccessful": False}),
                                      headers={"Retry-After": "0.5"})
    ck(v.error is ErrorCode.RATE_LIMITED and v.retry_after_ms == 500,
       "۴۲۹ ⇒ مسیرِ صریحِ RATE_LIMITED با Retry-After (درِ هر پنج مخزن نبود)",
       str(v.retry_after_ms))
    v = interpret_easytrader_response(200, "<html>login</html>")
    ck(v.accepted is None and v.error is ErrorCode.UNKNOWN_RESULT,
       "۲۰۰ با بدنۀِ HTML ⇒ نامعلوم، نه موفق", str(v)[:80])
    v = interpret_easytrader_response(200, _js({"id": "BR-3", "message": "در حال"}))
    ck(v.accepted is None and v.error is ErrorCode.UNKNOWN_RESULT,
       "۲۰۰ بی‌isSuccessful ⇒ نامعلوم (مرجع نبودش را «موفق» می‌شمرد)")
    ck(SloppyWire().accepted(200, {"id": "BR-3"}) is True,
       "کنترلِ منفی: «id داشت» درِ تفسیرِ بدقلق پذیرش است")
    v = interpret_easytrader_response(302, _js({"x": 1}))
    ck(v.accepted is None, "۳xx ⇒ نامعلوم؛ بدنِ سفارش را به جایِ دیگری نمی‌فرستیم")
    v = interpret_easytrader_response(200, _js({"isSuccessful": True, "id": "B",
                                               "orderStateStr": "Partial",
                                               "quantity": 1000,
                                               "executedQuantity": 400}))
    ck(v.accepted is True and v.state is OrderState.PARTIAL,
       "وضعیتِ سفارش ازِ متنِ سرور خوانده می‌شود", str(v.state))
    ck(map_order_state("نامعلومِ فارسی", quantity=None, executed=None) is OrderState.UNKNOWN,
       "واژۀِ ناشناخته ⇒ UNKNOWN، نه «پذیرفته/پر شده»")
    ck(map_order_state("Executed", quantity=500, executed=500) is OrderState.FILLED,
       "executed == quantity ⇒ پرشده")


# ── ۳) بدنۀِ سیم ─────────────────────────────────────────────────────────────
def part_payload():
    print("── ۳ بدنۀِ سیم — با برچسبِ فرضیه")
    p = easytrader_payload(draft(side=Side.SELL))
    inner = p.get("order") or {}
    ck(list(p.keys()) == ["order"], "بدنه درهم‌پیچِ {\"order\":{…}} است نه تخت", str(p)[:80])
    ck(inner.get("side") == 1 and easytrader_payload(draft())["order"]["side"] == 0,
       "جهت عددی: ۰=خرید، ۱=فروش")
    ck(inner.get("symbolIsin") == "IRO1IKCO0001", "شناسه، ISIN است نه ins_code")
    ck(inner.get("orderFrom") == 34 and inner.get("orderModelType") == 1
       and inner.get("validityType") == 0, "مقدارهایِ enum ازِ مرجع، بی‌ادعایِ صحت")
    created = inner.get("createDateTime") or ""
    import re
    ck(bool(re.match(r"^\d{1,2}/\d{1,2}/\d{4}, \d{1,2}:\d{2}:\d{2} (AM|PM)$", created)),
       "قالبِ createDateTime رویِ ویندوز درست ساخته می‌شود (نه %-mِ نشکسته)", created)
    ck("Authorization" not in str(p) and SECRET not in str(p),
       "هیچ token درِ پیش‌نمایشِ بدنه نیست")
    ck(WIRE_HYPOTHESIS is True, "WIRE_HYPOTHESIS روشن است — هیچ ثابتی تأییدشده نیست")


# ── ۴) قراردادِ عمومی رویِ آداپتورِ واقعی ────────────────────────────────────
# تنها case‌ای که معنایش با این آداپتور فرق دارد: «blind retry …». درِ بدل،
# `server_orders` حقیقتِ سمتِ سرور است؛ درِ آداپتورِ واقعی «آنچه ما از سرور
# *دیده‌ایم*». پس درِ §۵ همان خطر رویِ دفترِ خودِ بروکر سنجیده می‌شود — که
# ادعایِ قویّتری است، نه سنجه‌ای ضعیف‌تر.
EXCLUDED = ("blind_retry_after_timeout_really_duplicates",)


def part_contract():
    print("── ۴ سوئیتِ قراردادِ مخزنِ اول، رویِ آداپتورِ واقعی")
    from dev.execution_contract_v1 import run_contract
    results = run_contract(et_build, "easytrader")
    got = {n.split("/", 1)[1]: (ok, msg) for n, ok, msg in results}
    for name, (ok, msg) in got.items():
        if name in EXCLUDED:
            continue
        ck(ok, "قرارداد/%s" % name, msg[:110])
    ck(EXCLUDED[0] in got and not got[EXCLUDED[0]][0],
       "caseِ استثناشده *واقعاً* می‌افتد (پس استثنا بی‌خیالی نیست)",
       str(got.get(EXCLUDED[0], ""))[:90])
    ck(len(got) == 17, "هر ۱۷ case سوئیتِ قرارداد اجرا شد", str(len(got)))
    ck(len([n for n, ok, _ in results if ok]) == 16,
       "۱۶ سبز + یکِ استثنایِ ثبت‌شده", str(len([n for n, ok, _ in results if ok])))


# ── ۵) ابهام، تکرار، recovery ────────────────────────────────────────────────
def part_unknown():
    print("── ۵ timeout ⇒ UNKNOWN، بازیابی، و ممنوعیتِ تکرار")
    a = et_build(script={"EX-1": ["timeout"]})
    try:
        a.submit_order(draft("EX-1"))
        ck(False, "timeout باید BrokerError بدهد")
    except BrokerError as e:
        ck(e.code is ErrorCode.TIMEOUT and e.is_unknown_result and e.retry_forbidden,
           "timeout ⇒ نامعلومِ غیرقابلِ‌تکرار", e.code.value)
    ck(len(a.wire_calls) == 1, "یکِ POST — آداپتور خودش retry نمی‌کند", str(a.wire_calls))
    remote = a.get_orders()
    hit = [r for r in remote if r.execution_id == "EX-1"]
    ck(len(hit) == 1 and hit[0].broker_order_id,
       "reconcile ازِ فهرستِ سرور پیدایش می‌کند (تطبیقِ تنها)", str(hit)[:110])
    try:
        a.submit_order(draft("EX-1"))
        ck(False, "تکرارِ همان execution_id باید رد شود")
    except BrokerError as e:
        ck(e.code is ErrorCode.DUPLICATE_GUARD,
           "تکرارِ همان شناسه ⇒ DUPLICATE_GUARD", e.code.value)

    # ★ کنترلِ منفیِ caseِ استثناشده: خطرِ واقعی رویِ دفترِ خودِ بروکر.
    b = ScriptedBroker()
    b.script("EX-1", ["timeout"])
    ab = EasyTraderAdapter(transport=ScriptedTransport(b), token=SECRET)
    b.adapter = ab
    try:
        ab.submit_order(draft("EX-1"))
    except BrokerError:
        pass
    try:
        ab.submit_order(draft("EX-2"))          # همان قصد با شناسۀِ تازه — کاری که
        pass                                    # مرجع‌ها می‌کنند
    except BrokerError:
        pass
    ck(len(b.orders) == 2,
       "«ارسالِ دوباره با شناسۀِ تازه» دو سفارشِ واقعی می‌سازد (خطر ثابت شد)",
       str(len(b.orders)))

    # retry درِ لایۀِ ترافیک — باید دو سفارش بسازد و ما آن را نداریم
    class RetryingTransport(ScriptedTransport):
        def request(self, **kw):
            try:
                return ScriptedTransport.request(self, **kw)
            except (TransportTimeout, TransportNetwork):
                return ScriptedTransport.request(self, **kw)

    c = ScriptedBroker()
    c.script("EX-1", ["retry_trap"])
    ac = EasyTraderAdapter(transport=RetryingTransport(c), token=SECRET)
    c.adapter = ac
    try:
        ac.submit_order(draft("EX-1"))
    except BrokerError:
        pass
    ck(len(c.orders) >= 2,
       "کنترلِ منفی: retry درِ لایۀِ ترافیک ≥ دو سفارش می‌سازد و ممکن است «موفق» "
       "هم برگردد (پس max_retries=0 لازم است)",
       "%d orders / %d calls" % (len(c.orders), len(ac.wire_calls)))

    # مبهم: دو ردیفِ همسان ⇒ هیچ ادعایِ «پیدایش کردیم»
    d = ScriptedBroker()
    d.script("EX-1", ["timeout"])
    ad = EasyTraderAdapter(transport=ScriptedTransport(d), token=SECRET)
    d.adapter = ad
    try:
        ad.submit_order(draft("EX-1"))
    except BrokerError:
        pass
    twin = dict(d.orders[0], id="BR-99999")
    d.orders.append(twin)
    got = ad.get_orders()
    amb = [r for r in got if r.execution_id == "EX-1"]
    ck(len(amb) == 1 and amb[0].order_state is OrderState.UNKNOWN
       and amb[0].status is ExecutionStatus.UNKNOWN_RESULT,
       "دو ردیفِ همسان ⇒ مبهم می‌ماند، نه پذیرش", str(amb)[:120])

    # نشستِ منقضی: ۴۰۱ باید خودِ وضعیتِ نشست را عوض کند
    e = et_build(script={"EX-1": ["expired"]})
    try:
        e.submit_order(draft("EX-1"))
    except BrokerError as br:
        ck(br.code is ErrorCode.SESSION_EXPIRED, "۴۰۱ ⇒ SESSION_EXPIRED", br.code.value)
    ck(e.session_status().state is SessionState.EXPIRED,
       "پسِ ۴۰۱ وضعیتِ نشست *واقعاً* expired شد (نه Connectedِ باقی‌مانده)",
       str(e.session_status()))
    f = et_build(script={"EX-1": ["auth"]})
    try:
        f.submit_order(draft("EX-1"))
    except BrokerError:
        pass
    ck(f.session_status().state is SessionState.AUTH_FAILED,
       "۴۰۳ ⇒ AUTH_FAILED، جدا از انقضا — شش‌مقداریِ واقعی", str(f.session_status()))
    ck(len(SessionState) == 6, "SessionState شش مقدار دارد", str(len(SessionState)))


# ── ۶) صف — هرگز «اولِ صف» جعلی ──────────────────────────────────────────────
def part_queue():
    print("── ۶ جایِ صف فقط با دادهٔ واقعی")
    a = et_build()
    r = a.submit_order(draft())
    q = a.get_queue_position(r.broker_order_id)
    ck(q is None, "پاسخِ خالی ⇒ None (QUEUE_UNAVAILABLE)، نه صفر", str(q))
    b = et_build()
    rb = b.submit_order(draft())
    b._broker.queue_rows[rb.broker_order_id] = [
        {"orderId": rb.broker_order_id, "orderPlace": 3, "volumeAhead": 1200}]
    q2 = b.get_queue_position(rb.broker_order_id)
    ck(q2 is not None and q2.position == 3 and q2.known,
       "عددِ واقعی همان عدد است", str(q2))
    ck(q2 is not None and "UNVERIFIED" in q2.source,
       "واحدِ volumeAhead درِ منبع علامت خورده است", str(q2.source if q2 else "")[:70])
    c = et_build()
    rc = c.submit_order(draft())
    c._broker.queue_rows[rc.broker_order_id] = [
        {"orderId": rc.broker_order_id, "orderPlace": None, "volumeAhead": None}]
    q3 = c.get_queue_position(rc.broker_order_id)
    ck(q3 is not None and q3.position is None and not q3.known,
       "ردیفِ بی‌عدد ⇒ known=False، نه «اولِ صف»", str(q3))
    try:
        EasyTraderAdapter(transport=ScriptedTransport(ScriptedBroker()),
                          token=SECRET).cancel_order("BR-1")
        ck(False, "لغو نباید ممکن باشد")
    except BrokerError as e2:
        ck(e2.code is ErrorCode.UNSUPPORTED,
           "لغو: مسیرِ مستندنشده ادعا نمی‌شود", e2.code.value)
    ck(EasyTraderAdapter(transport=ScriptedTransport(ScriptedBroker()),
                         token=SECRET).get_balances() is None,
       "موجودی ⇒ None، نه صفر")


# ── ۷) درِ HTTP: وضعیتِ صادق، haltِ پاسخ‌گو، بازیابی پسِ restart ─────────────
def _with_easytrader(fn):
    """درِ واقعی را با آداپتورِ EasyTrader + ترافیکِ بدیل جایگزین می‌کند."""
    saved = (EX.ADAPTER_KIND, EX.LIVE_REQUESTED, EX.DRY_RUN, EX._ACTIVE_ADAPTER,
             EX._SERVICE, EX._AUDIT)
    broker = ScriptedBroker()
    adapter = EasyTraderAdapter(transport=ScriptedTransport(broker), token=SECRET)
    broker.adapter = adapter
    tmp = os.path.join(ROOT, "_audit", "easytrader_guard_%s.db" % uuid.uuid4().hex[:8])
    os.environ["BORS_EXECUTION_DB"] = tmp
    ledger = ExecutionLedger(tmp)
    try:
        EX.ADAPTER_KIND = ADAPTER_NAME
        EX.LIVE_REQUESTED = True
        EX.DRY_RUN = False
        EX._ACTIVE_ADAPTER = adapter
        EX._EASYTRADER = adapter
        EX._AUDIT = ledger
        EX._SERVICE = ExecutionService(adapter, dry_run=False,
                                       limits=Limits(require_confirmation=False),
                                       audit=ledger, scheduler=Scheduler(TimeSource()))
        fn(adapter, broker, ledger)
    finally:
        EX.ADAPTER_KIND, EX.LIVE_REQUESTED, EX.DRY_RUN, EX._ACTIVE_ADAPTER = saved[:4]
        EX._SERVICE, EX._AUDIT = saved[4], saved[5]
        ledger.close()
        os.environ.pop("BORS_EXECUTION_DB", None)
        try:
            os.remove(tmp)
        except OSError:
            pass


def part_door():
    print("── ۷ درِ HTTP رویِ آداپتورِ واقعی")

    def no_session(adapter, broker, ledger):
        adapter.clear_token()
        st = EX.get_status()
        ck(st["live_enabled"] is False and st["nothing_will_leave_the_machine"] is True,
           "بی‌token: live false و «چیزی بیرون نمی‌رود» — ازِ وضعیتِ واقعی", str(st)[:110])
        ck(all(v is False for v in st["capabilities"].values()),
           "بی‌token: همهٔ capabilities false ⇒ UI هیچ دکمه‌ای را باز نمی‌کند",
           str(st["capabilities"]))
        ck(st["adapter"] == ADAPTER_NAME and st["wire_hypothesis"] is True,
           "درِ واقعی انتخاب شد و «فرضیه بودنِ سیم» اعلام می‌شود", str(st)[:90])
        ck(bool(st["blocked_on"]), "دلیلِ بلوکم بودن درِ پاسخ هست", str(st["blocked_on"]))
        d = EX.post_dispatch({"symbol": "فولاد", "price": 100, "quantity": 2,
                              "confirmed": True})
        ck(d["status"] == "error" and d.get("code") in (ErrorCode.UNSUPPORTED.value,
                                                        ErrorCode.NOT_ORDERABLE.value),
           "dispatch بی‌نشست رد می‌شود و چیزی بیرون نمی‌رود", str(d)[:110])
        ck(not [w for w in adapter.wire_calls if str(w).startswith("submit:")],
           "هیچ POSTِ سفارشی ساخته نشد", str(adapter.wire_calls)[:90])
        pr = EX.post_probe()
        ck(pr["status"] == "error" and pr["order_endpoint_touched"] is False,
           "probe بی‌نشست درِ سفارش را نمی‌زند", str(pr)[:110])

    def happy(adapter, broker, ledger):
        st = EX.get_status()
        ck(st["live_enabled"] is True and st["capabilities"]["place"] is True,
           "با نشست: live و capabilities ازِ خودِ آداپتور خوانده می‌شود", str(st)[:110])
        prep = EX.post_prepare({"symbol": "فولاد", "price": 12610, "quantity": 1000,
                                "confirmed": True})
        ck(prep["status"] == "success" and prep["wire_preview"],
           "پیش‌نمایشِ *بدنۀِ واقعی* به UI می‌رسد", str(prep)[:120])
        ck((prep["wire_preview"] or {}).get("order", {}).get("symbolIsin")
           == (EX._resolve_instrument("فولاد").isin or "—"),
           "پیش‌نمایش همان ISINِ بانکِ محلی را می‌برد (نه حدسِ آداپتور)",
           str(prep["wire_preview"])[:110])
        d = EX.post_dispatch({"symbol": "فولاد", "price": 12610, "quantity": 1000,
                              "confirmed": True, "execution_id": "door-1"})
        rec = d.get("record") or {}
        ck(d["status"] == "success" and rec.get("status") == "reconciled",
           "پذیرش و *بازخوانی* درِ فهرستِ سرور: SAFE پیش ازِ تأییدِ مسدودکننده "
           "سفارش را رویِ سرور می‌بیند", str(rec)[:120])
        ck(rec.get("broker_order_id") and rec.get("rtt_ms") is not None
           and rec.get("response_at") is not None,
           "شناسۀِ کارگزاری و زمانِ پاسخ درِ رکورد است", str(rec)[:120])
        ck((d.get("timings") or {}).get("dispatch_ms") is not None,
           "زمانِ dispatch ازِ زمانِ پاسخ جدا اعلام می‌شود", str(d.get("timings"))[:90])
        led = EX.get_ledger()
        ck(any(r["execution_id"] == "door-1" for r in led["records"]),
           "دفترِ اجرا رکورد را دارد", str([r["execution_id"] for r in led["records"]]))
        rf = EX.post_refresh("door-1")
        ck(rf["status"] == "success" and rf["observed_ms"] is not None,
           "مشاهدهٔ سفارش جدا ازِ پذیرش اندازه می‌شود", str(rf)[:90])

    def halt_aborts_schedule(adapter, broker, ledger):
        target = int(time.time() * 1000) + 700
        d = EX.post_dispatch({"symbol": "فولاد", "price": 12610, "quantity": 1000,
                              "confirmed": True, "execution_id": "door-sched",
                              "target_wall_ms": target})
        ck(d["status"] == "scheduled" and d.get("wait_ms", 0) > 0,
           "زمان‌بندی درِ همان درخواست نمی‌خوابد — فوراً پاسخ می‌دهد", str(d)[:110])
        h = EX.post_halt({"reason": "توقفِ آزمون"})
        ck(h["status"] == "success" and h["aborted_schedules"] >= 1,
           "halt زمان‌بندیِ درِ انتظار را لغو می‌کند", str(h)[:110])
        for _ in range(60):
            s = EX.get_schedule("door-sched")
            if s["state"] in ("aborted", "done", "error", "refused"):
                break
            time.sleep(0.05)
        s = EX.get_schedule("door-sched")
        ck(s["state"] == "aborted", "نتیجه: پیش ازِ آتش ایستاد", str(s)[:110])
        ck(not [w for w in adapter.wire_calls if str(w).startswith("submit:")],
           "و هیچ سفارشی بیرون نرفت", str(adapter.wire_calls)[:110])
        ck(h["halted"] is True and EX.get_status()["halted"] is True,
           "قفلِ توقف رویِ دیسک ماند", str(h)[:90])
        r = EX.post_resume({"reason": "ادامه"})
        ck(r["status"] == "success" and EX._AUDIT.kill_state() == ARMED,
           "resume دستی قفل را برمی‌گرداند", str(r)[:90])

    def secrets(adapter, broker, ledger):
        try:
            adapter.submit_order(draft("sec-1"))
        except Exception:
            pass
        blob = repr(adapter.redacted_log) + repr(adapter) + repr(adapter.last_verdict)
        ck(SECRET not in blob and "<redacted>" in blob,
           "token درِ لاگِ ترافیک/repr زنده نمی‌ماند", blob[:80])
        ck(SECRET not in str(redact({"authorization": "Bearer " + SECRET})),
           "redact خودِ مقدارِ bearer را هم می‌بلعد")
        # کنترلِ منفی: اگر redactِ ledger خاموش باشد، همین رُکورد token را رویِ
        # دیسک می‌گذارد — پس نبودنش رویِ دیسک سکوتِ تصادفی نیست.
        ledger.record(execution_id="-", kind="probe",
                      payload={"authorization": "Bearer " + SECRET, "token": SECRET})
        disk = open(ledger.db_path, "rb").read()
        ck(SECRET.encode() not in disk, "ردِّپایِ رویِ دیسک token ندارد", str(len(disk)))
        ck(b"<redacted>" in disk, "و رُکوردِ حاویِ secret واقعاً رویِ دیسک نوشته شد")
        st = EX.get_status()
        ck(SECRET not in _js(st), "پاسخِ status token ندارد")
        ses = EX.get_session()
        ck(SECRET not in _js(ses) and ses["token_present"] is True,
           "session فقط «هست/نیست» را می‌گوید", str(ses)[:90])
        ck(SECRET not in _js(EX.post_prepare({"symbol": "فولاد", "price": 12610,
                                             "quantity": 1000, "confirmed": True})),
           "پیش‌نمایشِ بدنه token ندارد")

    def restart(adapter, broker, ledger):
        ledger.record(execution_id="rec-after-restart", kind="dispatch",
                      status="unknown_result", symbol="فولاد", side="buy",
                      price=10.0, quantity=1.0, mode="safe", broker=ADAPTER_NAME)
        saved_service = EX._SERVICE
        try:
            n = EX._recover()
            ck(n >= 1, "بازیابی پسِ restart رکوردهایِ باز را برمی‌دارد", str(n))
            rec = EX._SERVICE.record("rec-after-restart")
            ck(rec is not None and rec.status is ExecutionStatus.UNKNOWN_RESULT,
               "بازیابی‌شده UNKNOWN می‌ماند؛ restart خودش را «پذیرفته» جا نمی‌زند",
               str(rec.status if rec else None))
            ids = EX.get_ledger()["open_ids"]
            ck("rec-after-restart" in ids, "فهرستِ باز پسِ restart اعلام می‌شود",
               str(ids)[:90])
        finally:
            EX._SERVICE = saved_service

    _with_easytrader(no_session)
    _with_easytrader(happy)
    _with_easytrader(halt_aborts_schedule)
    _with_easytrader(secrets)
    _with_easytrader(restart)

    # درِ پیش‌فرض (بدونِ هیچ متغیرِ محیطی) باید همان مسیرِ آزموده‌شده بماند
    ck(EX.ADAPTER_KIND == "mock" or EX._configured_adapter() == "mock",
       "پیش‌فرضِ بی‌متغیرِ محیطی: mock", EX._configured_adapter())
    ck(EX.DRY_RUN is True, "پیش‌فرض: dry_run=true", str(EX.DRY_RUN))
    os.environ["BORS_EXECUTION_ADAPTER"] = "easytrader"
    try:
        ck(EX._configured_adapter() == "easytrader",
           "انتخابِ آداپتور فقط ازِ محیط (نه ازِ بدنهٔ درخواست)")
    finally:
        os.environ.pop("BORS_EXECUTION_ADAPTER", None)
    os.environ["BORS_EXECUTION_ADAPTER"] = "titan"
    try:
        ck(EX._configured_adapter() == "mock",
           "مقدارِ نامعلومِ محیط ⇒ mock (پیش‌فرضِ ایمن)", EX._configured_adapter())
    finally:
        os.environ.pop("BORS_EXECUTION_ADAPTER", None)
    body = open(os.path.join(ROOT, "api", "execution.py"), encoding="utf-8").read()
    ck('body.get("dry_run")' not in body and "body.get(\"live\")" not in body,
       "هیچ بدنه‌ای dry_run/live را عوض نمی‌کند")
    ck("execution_easytrader" in body, "درِ execution آداپتورِ واقعی را وارد می‌کند")


# ── ۸) کنترلِ منفیِ کلی: آداپتوری که ۲xx را پذیرش بخواند باید بیفتد ──────────
def part_negative_control():
    print("── ۸ کنترلِ منفیِ سنسور")
    from dev.execution_contract_v1 import run_contract

    class GullibleAdapter(EasyTraderAdapter):
        """همان باگِ مخزن ۱: `status.is_success()` ⇒ موفق، بی‌خواندنِ پاکت."""
        def submit_order(self, dr):
            try:
                return EasyTraderAdapter.submit_order(self, dr)
            except BrokerError as e:
                if e.code in (ErrorCode.BROKER_REJECTED, ErrorCode.INVALID_PRICE,
                              ErrorCode.INVALID_QUANTITY, ErrorCode.UNKNOWN_RESULT):
                    rec = self._new_record(dr)
                    rec.status = ExecutionStatus.ACKNOWLEDGED
                    rec.broker_order_id = "FAKE-2XX"
                    return rec
                raise

    def gullible_build(**kw):
        """همان ترافیکِ بدیل، رویِ آداپتوری که ۲xx را پذیرش می‌خواند."""
        honest = et_build(**kw)
        g = GullibleAdapter(transport=honest.transport, token=SECRET,
                            instruments=kw.get("instruments") or (),
                            capabilities=kw.get("capabilities"))
        honest._broker.adapter = g
        return g

    bad = {n.split("/", 1)[1] for n, ok, _ in run_contract(gullible_build, "gullible")
           if not ok}
    ck("validation_error_is_not_unknown_result" in bad
       or "broker_rejection_carries_its_own_message" in bad,
       "سنسور، آداپتورِ «۲xx=پذیرش» را می‌بیند", str(sorted(bad))[:140])
    ck("timeout_becomes_unknown_result_with_server_side_order" not in bad,
       "و خطایِ نامعلوم را که بدقلق هم درست می‌کند، اشتباهاً قرمز نمی‌کند")


def part_spec():
    print("── ۹ spec: آداپتور درِ بیلدِ منجمد گم نمی‌شود")
    import re
    for spec in ("fts_terminal.spec", "bors_setup.spec"):
        t = open(os.path.join(ROOT, spec), encoding="utf-8").read()
        hid = t[t.index("hiddenimports"):]
        ck("'execution_easytrader'" in hid,
           "%s درِ hiddenimports آداپتورِ تازه را دارد" % spec)
    body = open(os.path.join(ROOT, "api", "execution.py"), encoding="utf-8").read()
    ck(re.search(r"^from execution_easytrader import", body, re.M) is not None,
       "ایمپورت درِ سطحِ api/execution.py است (نه درونِ تابع) — اسکنِ ایستا هم می‌بیند")
    # وابستگیِ تازه‌ای اضافه نشده باشد: requests از پیش درِ requirements.txt است
    req = open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8").read()
    ck("requests" in req,
       "ترافیکِ واقعی رویِ requests است — بستهٔ تازه‌ای به مخزن اضافه نشد")


def main():
    print("easytrader_adapter_v1113 — آداپتورِ واقعی، بی‌شبکه، با کنترلِ منفی")
    os.makedirs(os.path.join(ROOT, "_audit"), exist_ok=True)
    part_no_network()
    part_interpret()
    part_payload()
    part_contract()
    part_unknown()
    part_queue()
    part_door()
    part_negative_control()
    part_spec()
    print(f"\neasytrader_adapter_v1113: {PASS} passed / {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
