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
import sqlite3
import sys
import threading
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from execution_contract import (  # noqa: E402
    BrokerError, ErrorCode, ExecutionStatus, InstrumentRef,
    OrderDraft, OrderState, Resolution, SessionState, Side, redact,
)
from execution_easytrader import (  # noqa: E402
    ADAPTER_NAME, WIRE_BASE_URL, WIRE_HYPOTHESIS, WIRE_PATH_ORDER_CREATE,
    WIRE_PATH_ORDER_LIST, WIRE_PATH_QUEUE, EasyTraderAdapter,
    RequestsTransport, TransportNetwork, TransportTimeout, WireResponse,
    easytrader_payload, interpret_easytrader_response, map_order_state,
)
from execution_ledger import ARMED, ExecutionLedger  # noqa: E402
from execution_service import ExecutionError, ExecutionService, Limits  # noqa: E402
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
        if oc == "accepted_not_listed":
            # سرور پذیرفت و شناسه داد، ولی درِ فهرستِ بعدی ردیفی ازِ ما نیست.
            # همین دو چیز را از هم جدا می‌کند: «پذیرش» با «دیدنِ ردیفِ سرور».
            return 200, {"isSuccessful": True, "id": row["id"], "message": "ok"}
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
    posts = [w for w in a.wire_calls if str(w).startswith("submit:POST")]
    ck(len(posts) == 1, "یکِ POST — آداپتور خودش retry نمی‌کند", str(a.wire_calls))
    ck(str(a.wire_calls[0]).startswith("authenticate")
       and str(a.wire_calls[-1]).startswith("submit:POST"),
       "پیش ازِ هر POST یکِ پرسشِ فقط‌خواندنیِ راستی‌آزمایی می‌آید (P0-۱)",
       str(a.wire_calls))
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
def _instrument_bank() -> str:
    """یکِ `market.db`ِ موقتیِ تنها-در جدولِ instruments.

    چرا: `market.db` درِ گیت نیست، پس درِ CI `_resolve_instrument` هیچ ردیفی
    نمی‌بیند ⇒ `UNRESOLVED` ⇒ `NOT_ORDERABLE` ⇒ تمامِ سنجه‌هایِ درِ HTTP با
    `KeyError: wire_preview` می‌شکستند (دقیقاً همان چیزی که رانِ guards داشت و
    محلی نبود). بانکِ ساختگیِ کوچک همان مسیرِ *واقعی* (`SELECT … FROM instruments`)
    را می‌دهد، بی‌وابستگی به بانکِ ۹۸ مگابایتیِ رویِ این ماشین — و سنجهٔ «ISIN از
    بانکِ محلی می‌آید، نه حدسِ آداپتور» همچنان معنی‌دار است.
    """
    p = os.path.join(ROOT, "_audit", "et_guard_bank_%s.db" % uuid.uuid4().hex[:8])
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE instruments (ins_code TEXT, isin TEXT, l_val18 TEXT,"
              " updated_at TEXT)")
    c.execute("INSERT INTO instruments VALUES (?,?,?,?)",
              (FOOLAD.ins_code, FOOLAD.isin, "فولاد", "2026-10-15T09:00:00"))
    c.commit()
    c.close()
    return p


def _with_easytrader(fn):
    """درِ واقعی را با آداپتورِ EasyTrader + ترافیکِ بدیل جایگزین می‌کند."""
    saved = (EX.ADAPTER_KIND, EX.LIVE_REQUESTED, EX.TRAFFIC_ALLOWED, EX.DRY_RUN,
             EX._ACTIVE_ADAPTER,
             EX._SERVICE, EX._AUDIT, EX.DB_PATH)
    broker = ScriptedBroker()
    adapter = EasyTraderAdapter(transport=ScriptedTransport(broker), token=SECRET)
    broker.adapter = adapter
    tmp = os.path.join(ROOT, "_audit", "easytrader_guard_%s.db" % uuid.uuid4().hex[:8])
    bank = _instrument_bank()
    os.environ["BORS_EXECUTION_DB"] = tmp
    ledger = ExecutionLedger(tmp)
    try:
        EX.DB_PATH = bank
        EX.ADAPTER_KIND = ADAPTER_NAME
        EX.LIVE_REQUESTED = True
        # ترافیکِ واقعیِ همین fixture است: ScriptedTransport. ماژول این سه را با هم
        # می‌سازد (TRAFFIC_ALLOWED از LIVE_REQUESTED ⇒ می‌آید)؛ پس اینجا هم با هم.
        EX.TRAFFIC_ALLOWED = True
        EX.DRY_RUN = False
        EX._ACTIVE_ADAPTER = adapter
        EX._EASYTRADER = adapter
        EX._AUDIT = ledger
        # سقفِ ریسک *باید* تنظیم شده باشد، وگرنه دروازۀ تازه (`_risk_gate`) اجرایِ
        # زنده را می‌بندد. بسته بودنِ دروازه هم پایین باِ همین fixture سنجیده
        # می‌شود (`no_risk_config_blocks_live`)؛ این سطرِ کانفیگ دروازه را رد
        # نمی‌کند، فقط مسیرِ درستِ کانفیگ را نشان می‌دهد.
        EX._SERVICE = ExecutionService(
            adapter, dry_run=False,
            limits=Limits(require_confirmation=False, max_order_value=50_000_000.0,
                          max_total_orders_per_window=20),
            audit=ledger, scheduler=Scheduler(TimeSource()))
        fn(adapter, broker, ledger)
    finally:
        (EX.ADAPTER_KIND, EX.LIVE_REQUESTED, EX.TRAFFIC_ALLOWED, EX.DRY_RUN,
         EX._ACTIVE_ADAPTER) = saved[:5]
        EX._SERVICE, EX._AUDIT, EX.DB_PATH = saved[5], saved[6], saved[7]
        ledger.close()
        os.environ.pop("BORS_EXECUTION_DB", None)
        for f in (tmp, bank):
            try:
                os.remove(f)
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
                              "confirmed": True, "confirm_phrase": EX._confirm_phrase()})
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
                                "confirmed": True, "confirm_phrase": EX._confirm_phrase()})
        ck(prep["status"] == "success" and prep["wire_preview"],
           "پیش‌نمایشِ *بدنۀِ واقعی* به UI می‌رسد", str(prep)[:120])
        ck((prep["wire_preview"] or {}).get("order", {}).get("symbolIsin")
           == (EX._resolve_instrument("فولاد").isin or "—"),
           "پیش‌نمایش همان ISINِ بانکِ محلی را می‌برد (نه حدسِ آداپتور)",
           str(prep["wire_preview"])[:110])
        d = EX.post_dispatch({"symbol": "فولاد", "price": 12610, "quantity": 1000,
                              "confirmed": True, "confirm_phrase": EX._confirm_phrase(), "execution_id": "door-1"})
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

    def no_risk_config_blocks_live(adapter, broker, ledger):
        """§۵ مأموریت (گیتِ System 2): نبودِ پیکربندیِ الزامیِ ریسک
        باید اجرایِ واقعی را متوقف کند. باِ همان نشستِ واقعیِ بدیل، فقط
        سقف‌ها را برمی‌داریم."""
        saved_limits = EX._SERVICE.limits
        posts_before = len([w for w in adapter.wire_calls
                            if str(w).startswith("submit:")])
        EX._SERVICE.limits = Limits(require_confirmation=False)     # بی‌هیچ سقف
        try:
            d = EX.post_dispatch({"symbol": "فولاد", "price": 12610, "quantity": 1000,
                                  "confirmed": True, "confirm_phrase": EX._confirm_phrase(), "execution_id": "door-nocfg"})
            ck(d.get("status") == "error"
               and d.get("code") == ErrorCode.RISK_LIMIT.value
               and d.get("risk_gate") == "not_configured",
               "بی‌سقفِ ریسک، dispatchِ زنده باِ دلیل رد می‌شود", str(d)[:130])
            ck(len([w for w in adapter.wire_calls if str(w).startswith("submit:")])
               == posts_before,
               "و هیچ سفارشی به سرور نمی‌رود (رد پیش ازِ هر ترافیک)")
        finally:
            EX._SERVICE.limits = saved_limits

    def halt_aborts_schedule(adapter, broker, ledger):
        # فاصلۀ زمانی باید * روشن* بالایِ IMMEDIATE_WINDOW_MS (۲۵۰ms) باشد:
        # بینِ ساختنِ target و تصمیمِ دروازۀ «فوری»، preflight و شمارشِ ردِّپا هم
        # زمان می‌برند، و باِ ۳۲۰ms این سنجه رویِ ماشینِ شلوغ بهِ ارسالِ فوری
        # می‌لزی‌د (خودِ سنجه را سنجیدم، نه محصول را).
        target = int(time.time() * 1000) + 1200
        d = EX.post_dispatch({"symbol": "فولاد", "price": 12610, "quantity": 1000,
                              "confirmed": True, "confirm_phrase": EX._confirm_phrase(), "execution_id": "door-sched",
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
                                             "quantity": 1000, "confirmed": True, "confirm_phrase": EX._confirm_phrase()})),
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

    def scheduled_unknown_stays_open(adapter, broker, ledger):
        """ackِ گم‌شده درِ مسیرِ زمان‌بندی باید «باز» بماند تا بعدِ restart هم
        رفعِ ابهام شود. یکِ سطرِ «done» ازِ در بیرون‌اندازنده‌اش می‌کرد — همان
        چیزی که این سنجه now نگهبانش است."""
        broker.script("door-unk", ["timeout"])
        target = int(time.time() * 1000) + 1200   # همان دلیلِ بالا
        d = EX.post_dispatch({"symbol": "فولاد", "price": 12610, "quantity": 1000,
                              "confirmed": True, "confirm_phrase": EX._confirm_phrase(), "execution_id": "door-unk",
                              "target_wall_ms": target})
        ck(d["status"] == "scheduled", "زمان‌بندیِ بی‌ack رویِ راه افتاد", str(d)[:90])
        s = {}
        for _ in range(120):
            s = EX.get_schedule("door-unk")
            if s.get("state") not in (None, "waiting", "scheduled", "sending"):
                break
            time.sleep(0.05)
        ck(s.get("state") == "unknown", "نتیجه: نامعلوم، نه رد و نه پذیرش", str(s)[:110])
        ids = EX.get_ledger()["open_ids"]
        ck("door-unk" in ids, "ردِّپا آن را باز می‌شمارد (فهرستِ reconcile پسِ restart)",
           str(ids)[:120])
        trail = EX._AUDIT.trail("door-unk")
        ck(not [e for e in trail if e["kind"] == "schedule"],
           "هیچ سطرِ بستنِ اضافه ازِ درِ زمان‌بندی نوشته نشد",
           str([(e["kind"], e["status"]) for e in trail])[:150])
        rec = EX._SERVICE.record("door-unk")
        ck(rec is not None and rec.status is ExecutionStatus.UNKNOWN_RESULT,
           "و رکوردِ حافظه هم UNKNOWN است", str(rec.status if rec else None))
        # و تکرارِ همان execution_id هر دو مسیر رد می‌شود: هم preflightِ پایدار
        second = EX.post_dispatch({"symbol": "فولاد", "price": 12610, "quantity": 1000,
                                   "confirmed": True, "confirm_phrase": EX._confirm_phrase(), "execution_id": "door-unk"})
        ck(second["status"] == "error"
           and second.get("code") == ErrorCode.DUPLICATE_GUARD.value,
           "ارسالِ دوبارهٔ همان شناسه رد شد — حتی پسِ نامعلوم بودن", str(second)[:110])

    def concurrent_same_id(adapter, broker, ledger):
        """بندِ ۴-ج: دوبارِ کلیک، دو worker و race نباید سفارشِ تکراری بسازد."""
        errs: list = []

        responses: list = []

        def fire(eid, target_ms=None):
            try:
                body = {"symbol": "فولاد", "price": 12610, "quantity": 1000,
                        "confirmed": True, "confirm_phrase": EX._confirm_phrase(), "execution_id": eid}
                if target_ms is not None:
                    body["target_wall_ms"] = int(time.time() * 1000) + target_ms
                responses.append(EX.post_dispatch(body))
            except Exception as e:                                # noqa: BLE001
                errs.append(repr(e)[:120])

        def race(eid, target_ms, expect_orders, refuse_in_response=True,
                 max_submits=1):
            del responses[:]
            before = len(broker.orders)
            submits_before = len([w for w in adapter.wire_calls
                                  if str(w).startswith("submit:")])
            ts = [threading.Thread(target=fire, args=(eid, target_ms)) for _ in range(2)]
            for t in ts:
                t.start()
            for t in ts:
                t.join(25)
            # مسیرِ زمان‌بندی‌شده ممکن است پسِ join هنوز آتش نزده باشد (زیرِ بارِ
            # CPU این دقیقاً رخ داد و «got 0» داد). پس اول سفارشِ انتظاری را
            # منتظر می‌مانیم و بعد یکِ پنجرۀ ۱٫۵ ثانیه‌ای «بی‌سفارشِ تازه» باز
            # می‌کنیم تا سفارشِ دومی که دیر می‌رسد هم دیده شود — سنجه سخت‌تر
            # می‌ماند، فقط نمونه‌برداریِ تک‌لحظه‌ای حذف می‌شود.
            deadline = time.time() + 20.0
            got = len(broker.orders) - before
            while got < expect_orders and time.time() < deadline:
                time.sleep(0.05)
                got = len(broker.orders) - before
            settle = time.time() + 1.5
            while time.time() < settle:
                time.sleep(0.05)
                got = len(broker.orders) - before
            refused = [r for r in responses if r and r.get("status") == "error"]
            ck(not errs, "هیچ threadی بیرون نپرید (%s)" % eid, str(errs)[:150])
            ck(got == expect_orders,
               "%s ⇒ %d سفارش درِ دفترِ بروکر" % (eid, expect_orders),
               "got %d" % got)
            if refuse_in_response:
                # مسیرِ فوری زیرِ قفلِ سرویس است: دومین prepare *همیشه* سطرِ
                # dispatchِ اول را می‌بیند ⇒ رد درِ همان پاسخ.
                ck(len(responses) == 2 and len(refused) == 1,
                   "تلاشِ دوم درِ پاسخِ HTTP صریح رد شد، نه بی‌صدا",
                   str([r.get("code") for r in responses if r])[:120])
            submits = len([w for w in adapter.wire_calls
                           if str(w).startswith("submit:")]) - submits_before
            ck(submits <= max_submits,
               "%s ⇒ حداکثر %d POST به آداپتور" % (eid, max_submits),
               "%d submits" % submits)
            return got

        # زمان‌بندی‌شده: هر دو ممکن است «زمان‌بندی شد» بگیرند و دومیشان درِ
        # threadِ پس‌زمینه به DUPLICATE_GUARD بخورد — چیزی که ممنوع است
        # سفارشِ *دوم* است، نه تلاشِ دومِ بی‌اثر.
        race("race-sched", 260, 1, refuse_in_response=False, max_submits=2)
        race("race-now", None, 1)
        ids = sorted({e["execution_id"] for e in
                      EX._AUDIT.events(kinds=("dispatch",), limit=50)})
        ck(ids == ["race-now", "race-sched"],
           "ردِّپا هر دو قصدِ سفارش را دارد، حتی آن که رد شد", str(ids)[:120])

    def claim_blocks_second_prepare(adapter, broker, ledger):
        """دومینِ prepareِ همان شناسه پیشِ هر execute رد می‌شود (رقابتِ TOCTOU).

        `api/execution.py` قفل را میانِ prepare و execute رها می‌کند (توقفِ
        اضطراری نباید پشتِ یکِ POSTِ طولانی گیر کند)، پس «سطرِ dispatch درِ
        ردِّپا هست» تنها نگهبانِ دومینِ درخواست نیست. این سنجه همان رزرو را
        می‌سنجد، و کنترلِ منفی‌اش ثابت می‌کند سنسور به رزرو نگاه می‌کند نه به
        شانسِ زمان‌بندی.
        """
        svc = EX._SERVICE
        d = draft("claim-1")
        svc.prepare(d)
        try:
            svc.prepare(draft("claim-1"))
            ck(False, "دومینِ prepareِ همان شناسه رد شد ( DUPLICATE_GUARD)")
        except ExecutionError as e:
            ck(e.code is ErrorCode.DUPLICATE_GUARD,
               "دومینِ prepareِ همان شناسه رد شد (DUPLICATE_GUARD)", e.code.value)
            failed = sorted(k for k, v in e.checks.items() if v == "FAIL")
            ck(failed == ["duplicate"],
               "و پاسخ دقیقاً همان یکِ نگهبانِ شکست‌خورده را نام می‌برد", str(e.checks)[:150])
        # کنترلِ منفی: بیِ رزرو (رفتارِ پیشین) همان درخواست باید رد نشود —
        # یعنی نگهبانِ این سنجه خودِ `_prepared` است، نه ردِّپا.
        svc._prepared.pop("claim-1", None)
        try:
            svc.prepare(draft("claim-1"))
            ck(True, "کنترلِ منفی: با برداشتنِ رزرو، preflight رد نمی‌کند "
                     "(پس سنسور به رزرو نگاه می‌کند)")
        except ExecutionError as e:
            ck(False, "کنترلِ منفیِ رزرو نباید رد کند", e.code.value)
        # و رزروِ تهی هیچ‌وقت سفارشِ دوم را به آداپتور نمی‌رساند
        ck(not [w for w in adapter.wire_calls if str(w).startswith("submit:")],
           "هیچ POSTی ازِ این سنجه بیرون نرفت", str(adapter.wire_calls)[:110])

    _with_easytrader(no_session)
    _with_easytrader(happy)
    _with_easytrader(no_risk_config_blocks_live)
    _with_easytrader(halt_aborts_schedule)
    _with_easytrader(scheduled_unknown_stays_open)
    _with_easytrader(concurrent_same_id)
    _with_easytrader(claim_blocks_second_prepare)
    _with_easytrader(secrets)
    _with_easytrader(restart)

    # درِ پیش‌فرض (بدونِ هیچ متغیرِ محیطی) باید همان مسیرِ آزموده‌شده بماند
    ck(EX.ADAPTER_KIND == "mock" or EX._configured_adapter({}) == "mock",
       "پیش‌فرضِ بی‌env و بی‌تنظیمِ ذخیره‌شده: mock", EX._configured_adapter({}))
    ck(EX.DRY_RUN is True, "پیش‌فرض: dry_run=true", str(EX.DRY_RUN))
    os.environ["BORS_EXECUTION_ADAPTER"] = "easytrader"
    try:
        ck(EX._configured_adapter({"adapter": "mock"}) == "easytrader",
           "env بر تنظیمِ ذخیره‌شده مقدم است (بدنهٔ درخواست رأی ندارد)")
    finally:
        os.environ.pop("BORS_EXECUTION_ADAPTER", None)
    os.environ["BORS_EXECUTION_ADAPTER"] = "titan"
    try:
        ck(EX._configured_adapter({"adapter": "easytrader"}) == "mock",
           "مقدارِ نامعلومِ محیط ⇒ mock (پیش‌فرضِ ایمن، و بر تنظیمِ دیسک هم پیشی می‌گیرد)",
           EX._configured_adapter({"adapter": "easytrader"}))
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


# ── ۱۳) فهرستِ مجازِ میزبانِ سیمی ──────────────────────────────────────────────
# هر پرسشِ این آداپتور هدرِ `Authorization`ِ نشستِ کاربر را حمل می‌کند. بی‌نگهبان،
# یکِ `base_url`ِ اشتباه همان توکن را به میزبانِ بیگانه (یا باِ http، درِ رده) می‌برد.
def part_wire_host_allowlist():
    print("── ۱۳ میزبانِ سیمی: فقط دامنهٔ تأییدشده")
    import execution_easytrader as ET
    ck(ET._validated_base_url(None) == "https://api-mts.orbis.easytrader.ir",
       "پیش‌فرضِ بی‌`base_url` همان میزبانِ دیدہ‌شدہ است")
    bad = [
        "http://api-mts.orbis.easytrader.ir",
        "https://evil.com",
        "https://api-mts.orbis.easytrader.ir.evil.com",
        "https://api-mts.orbis.easytrader.ir:8443",
        "https://user@api-mts.orbis.easytrader.ir",
        "https://api-mts.orbis.easytrader.ir/core",
    ]
    refused = []
    for u in bad:
        try:
            ET._validated_base_url(u)
        except ValueError:
            refused.append(u)
    ck(len(refused) == len(bad),
       "هر ششِ شکلِ نادرِ میزبان/طرح/بندر/userinfo/مسیر رد می‌شود",
       "accepted: %s" % [u for u in bad if u not in refused])
    try:
        EasyTraderAdapter(transport=ET.RefusingTransport(), token=SECRET,
                          base_url="https://evil.com")
        ck(False, "ساختِ آداپتور باِ میزبانِ بیگانه باید پیش ازِ هر چیز رد شود")
    except ValueError as e:
        ck("مجاز" in str(e) or "https" in str(e),
           "ساختِ آداپتورِ بیگانه باِ دلیل رد می‌شود (نه ترافیک، نه توکنِ بیرون‌رفته)",
           str(e)[:90])
    os.environ["BORS_EXECUTION_WIRE_HOSTS"] = "api-mts.example-region.ir"
    try:
        ck(ET._validated_base_url("https://api-mts.example-region.ir").endswith(
               "example-region.ir"),
           "میزبانِ منطقه‌ای فقط باِ فهرستِ صریحِ محیطی پذیرفته می‌شود")
    finally:
        os.environ.pop("BORS_EXECUTION_WIRE_HOSTS", None)
    try:
        ET._validated_base_url("https://api-mts.example-region.ir")
        ck(False, "پس ازِ برداشتنِ env، همان میزبان باید دوباره رد شود")
    except ValueError:
        ck(True, "بی‌envِ صریح، میزبانِ افزوده رد می‌ماند (فهرستِ مجاز واقعی است)")

def part_server_clock():
    """ساعتِ کارگزاری ازِ درِ *مستندشده*، نه ازِ حدسِ مسیر.

    شاهدِ این دور: capture عمومیِ مرجعِ ۲ (`mofid/docs/archive/d.easytrader.ir.har`)
    `GET /easy/api/account/server-time/<clientEpochMs>` را باِ پاسخِ
    `{"diff":45,"serverTimestamp":1767700032066}` نشان می‌دهد. دو چیز اینجا سنجیده
    می‌شود: (الف) همان مسیر و همان دو فیلد، (ب) «diff» به‌تنهایی ادعا نیست — اگر دو
    فیلد باِ رفت‌وبرگشتِ اندازه‌گرفته‌شده نخوانند، ساعت تأیید *نمی‌شود* و رفتارِ
    ارسال دست‌نخورده می‌ماند. بی‌اینها، منبعِ ساعت فقط یکِ عددِ دیگر درِ UI بود.
    """
    print("── ۱۲ ساعتِ سرور: مسیرِ دیدہ‌شدہ، دو فیلدِ سازگار")
    seen: list[str] = []

    class ClockTransport:
        name = "clock"
        is_live = True

        def __init__(self, mode):
            self.mode = mode

        def request(self, *, method, url, headers=None, payload=None, timeout_s=7.0):
            seen.append("%s %s" % (method, url))
            if url.rstrip("/").endswith("/core/api/order"):
                return WireResponse(200, {}, _js({"orders": []}))
            try:
                client_ms = int(url.rsplit("/", 1)[1])
            except ValueError:
                # نشانیِ بی‌پارامترِ عددی یعنی آداپتر مسیرِ شاهد را رها کرده؛
                # صبر کن تا سنجه‌ها این را قرمز کنند، بی‌کرَش کردنِ کلِ گارد.
                return WireResponse(200, {}, _js({"diff": 0, "serverTimestamp": 0}))
            if self.mode == "ok":
                return WireResponse(200, {}, _js({"diff": 45,
                                                  "serverTimestamp": client_ms + 45}))
            if self.mode == "lie":
                return WireResponse(200, {}, _js({"diff": 900,
                                                  "serverTimestamp": client_ms + 45}))
            if self.mode == "huge":
                return WireResponse(200, {}, _js({"diff": 20 * 60 * 1000,
                                                  "serverTimestamp": client_ms}))
            return WireResponse(200, {}, "<html><body>login</body></html>")

    del seen[:]
    ok = EasyTraderAdapter(transport=ClockTransport("ok"), token=SECRET)
    sc = ok.server_clock() or {}
    ck(sc.get("verified") is True and sc.get("delta_ms") == 45.0
       and sc.get("quality") == "trusted",
       "پاسخِ سازگار ⇒ ساعتِ تأییدشده باِ آفستِ ۴۵ms", str(sc)[:130])
    ck(any("/easy/api/account/server-time/" in u for u in seen)
       and not any("/core/api/account/server-time" in u for u in seen),
       "مسیرِ پرسش همان مسیرِ شاهد است، نه حدسِ پیشین", str(seen)[:130])
    ck(all(not u.startswith("POST") for u in seen)
       and not any("/core/api/v2/order" in u for u in seen),
       "سنجشِ ساعت هرگز سفارش نمی‌فرستد", str(seen)[:130])

    lie = EasyTraderAdapter(transport=ClockTransport("lie"), token=SECRET)
    sl = lie.server_clock() or {}
    ck(sl.get("verified") is False and sl.get("delta_ms") is None
       and sl.get("quality") == "unavailable",
       "دو فیلدِ ناهمخوان ⇒ هیچ ادعایی (verified False، آفست None)", str(sl)[:130])
    huge = EasyTraderAdapter(transport=ClockTransport("huge"), token=SECRET)
    ck((huge.server_clock() or {}).get("verified") is False,
       "آفستِ بی‌کران (۲۰ دقیقه) باور نمی‌شود")
    html = EasyTraderAdapter(transport=ClockTransport("html"), token=SECRET)
    ck(html.server_clock() is None,
       "۲۰۰ با بدنهٔ HTMLِ صفحۀ ورود ⇒ ساعتی درِ کار نیست")
    before = len(seen)
    silent = EasyTraderAdapter(transport=ClockTransport("ok"))
    ck(silent.server_clock() is None and len(seen) == before,
       "بی‌نشست هیچ پرسشی زده نمی‌شود و None می‌آید، نه «ساعت درست است»")
    pr = ok.probe()
    ck(pr.get("clock") is not None and pr.get("order_endpoint_touched") is False,
       "probe ساعت را درِ پاسخ می‌آورد و درِ سفارش را لمس نمی‌کند", str(pr)[:150])


def part_session_hardening():
    """۴۲۲ِ FastAPI مقدارِ ورودیِ بی‌شکل را درِ `input` برمی‌گرداند — درِ این در
    یعنی tokenِ مالک درِ پاسخِ خطا و هر لاگِ استثنا می‌نشیند. بدنه را خودمان
    می‌خوانیم، پس هیچ پیامی مقدارِ نشانی را ندارد."""
    print("── ۱۰ بدنهٔ نامعتبر، نشانی را برنمی‌گرداند")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    saved = (EX.ADAPTER_KIND, EX.LIVE_REQUESTED, EX.TRAFFIC_ALLOWED, EX._ACTIVE_ADAPTER)
    broker = ScriptedBroker()
    adapter = EasyTraderAdapter(transport=ScriptedTransport(broker), token=None)
    broker.adapter = adapter
    EX.ADAPTER_KIND = ADAPTER_NAME
    EX.LIVE_REQUESTED = True
    # TRAFFIC_ALLOWED درِ ماژول ازِ LIVE_REQUESTED ساخته می‌شود؛ اگر اینجا ست نشود،
    # fixture وضعیتی می‌سازد که خودِ برنامه هرگز در آن نیست (live و بی‌ترافیک) و
    # در /session نشانی را رد می‌کند — نه به‌خاطرِ باگ، به‌خاطرِ سناریویِ ناممکن.
    EX.TRAFFIC_ALLOWED = True
    EX._ACTIVE_ADAPTER = adapter
    try:
        app = FastAPI()
        app.include_router(EX.router)
        c = TestClient(app)
        r = c.post("/api/execution/session", content='["%s"]' % SECRET,
                   headers={"Content-Type": "application/json"})
        ck(r.status_code == 200 and SECRET not in r.text,
           "بدنۀِ واژه‌نامه‌نشدنش نشست را باز نمی‌کند و token را برنمی‌گرداند",
           str(r.text)[:120])
        ck(not adapter.has_token(), "و بی‌شکل بودنِ بدنه token را ذخیره نمی‌کند")
        r2 = c.post("/api/execution/session", content='{"token": "%s"}' % SECRET,
                    headers={"Content-Type": "application/json"})
        ck(r2.status_code == 200 and SECRET not in r2.text and adapter.has_token(),
           "بدنۀِ درست نشست را باز می‌کند و باز هم مقدار را برنمی‌گرداند",
           str(r2.text)[:120])
        ck(SECRET not in repr(adapter) and SECRET not in _js(adapter.session_status().__dict__),
           "هیچ repr/وضعیتی نشانی را ندارد")
        src = open(os.path.join(ROOT, "api", "execution.py"), encoding="utf-8").read()
        ck("await request.body()" in src,
           "درِ نشست با Request خام خوانده می‌شود (نه Bodyِ pydantic)")
    finally:
        (EX.ADAPTER_KIND, EX.LIVE_REQUESTED, EX.TRAFFIC_ALLOWED,
         EX._ACTIVE_ADAPTER) = saved


def part_ack_not_observed():
    """۱۴) پذیرشِ POST مدرکِ «دیده‌شدن درِ فهرستِ سرور» نیست.

    پیش ازِ این اصلاح، `submit_order` رکوردِ خودِ خودش را درِ `server_orders`
    می‌گذاشت و `refresh()` همان را به‌عنوانِ «refreshed from broker» برمی‌داشت —
    یعنی RECONCILED بی‌هیچ ردیفِ سرور. حالا «شناخته‌شده» و «دیده‌شده» دو دفترند.
    """
    print("── ۱۴ پذیرش ≠ دیدنِ ردیف درِ فهرستِ سرور")
    a = et_build(script={"EX-ECHO": ["accepted_not_listed"]})
    rec = a.submit_order(draft("EX-ECHO"))
    rid = rec.broker_order_id
    ck(bool(rid) and len(a.server_orders) == 1,
       "پذیرش درِ «شناخته‌شده‌ها» می‌ماند (همان چیزی که قراردادِ مشترک می‌خواهد)",
       str(rid))
    remote = a.get_orders()
    ck([r for r in remote if r.execution_id == "EX-ECHO"] == [],
       "فهرستِ سرور ما را ندارد ⇒ get_orders آن را «دیده‌شده» گزارش نمی‌کند",
       str([r.broker_order_id for r in remote])[:90])
    ck(a.get_order(rid) is None,
       "get_order بی‌ردیفِ دیده‌شده None می‌دهد، نه رکوردِ خودِ خودمان", str(rid))
    b = et_build(script={"EX-SAW": ["ok"]})
    r2 = b.submit_order(draft("EX-SAW"))
    ck(b.get_order(r2.broker_order_id) is not None,
       "کنترلِ منفی: اگر ردیف درِ فهرست باشد، دیده و برگردانده می‌شود", "")
    c = et_build(script={"EX-TIMEOUT": ["timeout"]})
    try:
        c.submit_order(draft("EX-TIMEOUT"))
        ck(False, "timeout باید BrokerError بدهد")
    except BrokerError:
        pass
    ck(c.get_orders() and c.get_orders()[0].execution_id == "EX-TIMEOUT",
       "مسیرِ timeout (تطبیقِ ردیفِ سرور به قصدِ بی‌ack) دست‌نخورده باقی می‌ماند",
       str([r.execution_id for r in c.get_orders()])[:90])


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
    part_wire_host_allowlist()
    part_server_clock()
    part_session_hardening()
    part_ack_not_observed()
    part_spec()
    print(f"\neasytrader_adapter_v1113: {PASS} passed / {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
