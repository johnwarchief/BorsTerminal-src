#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sarkhati_fast_order_v1170 — Round 21: ثبتِ سریع، یک‌بار، و بی‌ادعا.

هیچ شبکه/سفارشِ واقعی. سه چیز سنجیده می‌شود:

  ۱) پیش‌نمایش، همهٔ کارِ کند (تأییدِ نشست، موجودی، preflight) را انجام می‌دهد؛
     لحظهٔ تأیید فقط گیت‌هایِ محلی + یک POST است.
  ۲) توکنِ پیش‌نمایش یک‌بارمصرف است: دو تأییدِ هم‌زمان/پشتِ‌سرهم یک POST می‌دهد.
  ۳) timeout/UNKNOWN به «ارسالِ دوباره» تبدیل نمی‌شود؛ فقط reconcile.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = FAIL = 0


def ck(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   " + label)
    else:
        FAIL += 1
        print("FAIL " + label + "  -> " + str(detail)[:320])


class FakeAdapter:
    """آداپتورِ شمارنده: هر تماسِ شبکه‌ای را می‌شمارد و تأخیرِ مصنوعی می‌گذارد."""
    name = "fake"
    live = True
    writes_allowed = True

    def __init__(self, *, submit_error=None, order_id="BR-9001", delay=0.0,
                 balances=True, proven=True):
        from execution_contract import (Capabilities, ExecutionRecord,
                                        ExecutionStatus, OrderState, SessionState,
                                        SessionStatus)
        self._C = (Capabilities, ExecutionRecord, ExecutionStatus, OrderState,
                   SessionState, SessionStatus)
        self._caps = Capabilities(place=True, list_orders=True, order_state=True,
                                  queue_position=True, cancel=False,
                                  best_bid_ask=False, balances=balances)
        self._session = SessionStatus(SessionState.CONNECTED, "fake-account")
        self._proven = proven
        self._order_id = order_id
        self._submit_error = submit_error
        self.delay = delay
        self.authenticate_calls = 0
        self.balance_calls = 0
        self.submit_calls = 0
        self.get_orders_calls = 0
        self.get_order_calls = 0
        self.queue_calls = 0
        self.last_draft = None
        self.rows = []
        self._seen = set()

    # -- کمینهٔ قرارداد -----------------------------------------------------
    def capabilities(self):
        return self._caps

    def session_status(self):
        return self._session

    def session_proven(self):
        return self._proven

    def authenticate(self):
        self.authenticate_calls += 1
        if self.delay:
            time.sleep(self.delay)
        if not self._proven:
            from execution_contract import BrokerError, ErrorCode
            raise BrokerError(ErrorCode.AUTH_FAILED, "fake: auth failed")
        return self._session

    def set_token(self, _value):
        self._proven = False

    def has_token(self):
        return True

    def get_balances(self):
        self.balance_calls += 1
        if self.delay:
            time.sleep(self.delay)
        return {"buying_power": 10_000_000_000.0, "unit": "IRR",
                "source": "fake"}

    def submit_order(self, draft):
        self.submit_calls += 1
        self.last_draft = draft
        if self.delay:
            time.sleep(self.delay)
        if self._submit_error is not None:
            raise self._submit_error
        if draft.execution_id in self._seen:
            from execution_contract import BrokerError, ErrorCode
            raise BrokerError(ErrorCode.DUPLICATE_GUARD, "fake duplicate")
        self._seen.add(draft.execution_id)
        C, R, S, O, _SS, _ST = self._C
        rec = R(execution_id=draft.execution_id, broker=self.name,
                account="fake-account", symbol=draft.instrument.symbol,
                isin=draft.instrument.isin, side=draft.side,
                price=draft.price, quantity=draft.quantity, mode=draft.mode,
                status=S.ACKNOWLEDGED,
                broker_order_id=self._order_id, order_state=O.UNKNOWN)
        rec.rtt_ms = 1.0
        self.rows.append(rec)
        return rec

    def get_orders(self):
        self.get_orders_calls += 1
        if self.delay:
            time.sleep(self.delay)
        return list(self.rows)

    def get_order(self, broker_order_id):
        self.get_order_calls += 1
        return next((r for r in self.rows
                     if r.broker_order_id == broker_order_id), None)

    def get_queue_position(self, broker_order_id):
        self.queue_calls += 1
        return None

    def resolve_instrument(self, symbol):
        from execution_contract import InstrumentRef, Resolution
        return InstrumentRef(symbol=symbol, isin="IRO1FAKE0001",
                             broker_instrument="IRO1FAKE0001",
                             resolution=Resolution.EXACT)

    def validate_order(self, _draft):
        return None


class FakeTransport:
    """ترافیکِ بدیلِ EasyTrader؛ مسیرِ هر درخواست را ثبت می‌کند."""
    name = "scripted"
    is_live = True

    def __init__(self):
        self.calls = []          # (method, path)
        self.post_payload = None
        self._lock = threading.Lock()

    def request(self, *, method, url, headers, payload=None, timeout_s=7.0):
        from urllib.parse import urlparse
        path = urlparse(url).path or ""
        with self._lock:
            self.calls.append((method, path))
            if method == "POST":
                self.post_payload = payload
        from execution_easytrader import WireResponse
        if path.endswith("/core/api/order") and method == "GET":
            return WireResponse(200, {}, json.dumps(
                {"isSuccessful": True, "data": []}))
        if path.endswith("/easy/api/money"):
            return WireResponse(200, {}, json.dumps(
                {"buyPowerT2": 10_000_000_000, "credit": 0,
                 "avandCredit": 0}))
        if path.endswith("/core/api/v2/order") and method == "POST":
            return WireResponse(200, {}, json.dumps(
                {"isSuccessful": True, "id": "BR-4242"}))
        return WireResponse(404, {}, "{}")

    def paths(self):
        return [p for _m, p in self.calls]


def _setup_api(adapter, *, dry_run=False):
    import api.execution as EX
    from execution_service import ExecutionService, Limits
    from execution_contract import InstrumentRef, Resolution
    old = (EX._ACTIVE_ADAPTER, EX._SERVICE, EX.DRY_RUN, EX._live_now,
           EX._risk_gate, EX._resolve_instrument)
    EX._ACTIVE_ADAPTER = adapter
    EX.DRY_RUN = dry_run
    EX._live_now = lambda: not dry_run
    EX._risk_gate = lambda: (True, "")

    def resolve(symbol):
        return InstrumentRef(symbol=symbol, isin="IRO1FAKE0001",
                             broker_instrument="IRO1FAKE0001",
                             resolution=Resolution.EXACT)

    EX._resolve_instrument = resolve
    EX._SERVICE = ExecutionService(adapter, dry_run=dry_run,
                                   limits=Limits(require_confirmation=True),
                                   audit=None)
    return EX, old


def _restore(EX, old):
    (EX._ACTIVE_ADAPTER, EX._SERVICE, EX.DRY_RUN, EX._live_now, EX._risk_gate,
     EX._resolve_instrument) = old
    EX._FAST_ORDERS.reset()


def part_gateway():
    print("\n── ۱) دروازهٔ پیش‌نمایش: یک‌بارمصرف، انقضا، دورهٔ تأیید ──")
    from execution_fast_order import FastOrderError, FastOrderGateway
    from execution_contract import OrderDraft, Side, InstrumentRef, Resolution
    draft = OrderDraft(execution_id="e-gw", side=Side.BUY, price=1000.0,
                       quantity=10.0,
                       instrument=InstrumentRef(symbol="TEST", isin="IRO1TEST0001",
                                                broker_instrument="IRO1TEST0001",
                                                resolution=Resolution.EXACT))
    now = [100.0]
    gw = FastOrderGateway(ttl_s=5.0, clock=lambda: now[0],
                          token_factory=lambda: "TOK-1")

    class _P:
        class draft:
            execution_id = "e-gw"

    snap = gw.create(prepared=_P(), payload={"order": {}}, epoch=3,
                     token_ref=object(), summary={"symbol": "TEST"})
    got = gw.claim("TOK-1", epoch=3, token_ref=snap.token_ref, halted=False)
    ck(got.execution_id == "e-gw" and got.phase == "sending",
       "الف) اولین claim توکن را مصرف می‌کند", got.phase)
    try:
        gw.claim("TOK-1", epoch=3, token_ref=snap.token_ref, halted=False)
        ck(False, "پ) claim دوم باید رد شود")
    except FastOrderError as e:
        ck(e.code == "ALREADY_USED", "پ) claim دوم ALREADY_USED است", e.code)

    gw2 = FastOrderGateway(ttl_s=5.0, clock=lambda: now[0],
                           token_factory=lambda: "TOK-2")
    s2 = gw2.create(prepared=object(), payload={}, epoch=1,
                    token_ref=object(), summary={})
    now[0] = 106.0
    try:
        gw2.claim("TOK-2", epoch=1, token_ref=s2.token_ref, halted=False)
        ck(False, "ت) توکنِ منقضی باید رد شود")
    except FastOrderError as e:
        ck(e.code == "EXPIRED", "ت) توکنِ منقضی EXPIRED است", e.code)

    gw3 = FastOrderGateway(clock=lambda: now[0], token_factory=lambda: "TOK-3")
    ref = object()
    s3 = gw3.create(prepared=object(), payload={}, epoch=7,
                    token_ref=ref, summary={})
    try:
        gw3.claim("TOK-3", epoch=8, token_ref=ref, halted=False)
        ck(False, "ث) دورهٔ تأییدِ کهنه باید رد شود")
    except FastOrderError as e:
        ck(e.code == "STALE_CONFIRMATION", "ث) دورهٔ کهنه رد می‌شود", e.code)

    gw4 = FastOrderGateway(clock=lambda: now[0], token_factory=lambda: "TOK-4")
    ref4 = object()
    gw4.create(prepared=object(), payload={}, epoch=2,
               token_ref=ref4, summary={})
    try:
        gw4.claim("TOK-4", epoch=2, token_ref=ref4, halted=True)
        ck(False, "ج) توقف باید claim را رد کند")
    except FastOrderError as e:
        ck(e.code == "HALTED", "ج) توقف HALTED است", e.code)
    got4 = gw4.claim("TOK-4", epoch=2, token_ref=ref4, halted=False)
    ck(got4.phase == "sending", "چ) HALTED توکن را نسوزاند", got4.phase)


def part_inputs(EX):
    print("\n── ۲) اعتبارسنجیِ ورودی پیش از هر تماس ──")
    bad = [
        ({"symbol": "", "side": "buy", "price": 1000, "quantity": 10},
         "symbol"),
        ({"symbol": "TEST", "side": "hold", "price": 1000, "quantity": 10},
         "side"),
        ({"symbol": "TEST", "side": "buy", "price": 0, "quantity": 10},
         "price"),
        ({"symbol": "TEST", "side": "buy", "price": 1000, "quantity": 0},
         "quantity"),
        ({"symbol": "TEST", "side": "buy", "price": 1000, "quantity": 10.5},
         "quantity_integer"),
        ({"symbol": "TEST", "side": "buy", "price": float("nan"),
          "quantity": 10}, "price"),
    ]
    for body, field in bad:
        got = EX.post_order_preview(body)
        ck(got.get("status") == "error" and got.get("field") == field,
           "ردِ ورودیِ نامعتبر: %s" % field, got)

    good = EX.post_order_preview(
        {"symbol": "TEST", "side": "buy", "price": 1000, "quantity": 10})
    ck(good.get("status") == "success"
       and good.get("prepared_token")
       and good.get("summary", {}).get("quantity") == 10,
       "ورودیِ درست پیش‌نمایش می‌سازد", good)


def part_fast_path(EX):
    print("\n── ۳) مسیرِ تأیید: فقط یک POST؛ پیش‌خوانی قبلی دوباره نمی‌شود ──")
    from execution_contract import ErrorCode
    body = {"symbol": "TEST", "side": "buy", "price": 1000, "quantity": 10,
            "price_source": "test", "price_as_of": "2026-10-22T10:00:00"}
    adapter = EX._ACTIVE_ADAPTER
    before_auth, before_bal = (adapter.authenticate_calls,
                               adapter.balance_calls)
    pv = EX.post_order_preview(body)
    ck(pv.get("status") == "success", "الف) پیش‌نمایش ساخته شد", pv)
    tok = pv.get("prepared_token")
    a_auth, a_bal = adapter.authenticate_calls, adapter.balance_calls
    ck(a_auth == before_auth and a_bal == before_bal + 1,
       "پ) موجودی یک‌بار در پیش‌نمایش خوانده شد؛ نشستِ اثبات‌شده دوباره پرسیده نشد",
       (before_auth, a_auth, before_bal, a_bal))
    ck(adapter.submit_calls == 0, "ت) پیش‌نمایش صفر POST دارد",
       adapter.submit_calls)
    pv2 = EX.post_order_preview(body)
    ck(pv2.get("status") == "success"
       and adapter.authenticate_calls == a_auth,
       "ث) پیش‌نمایش دوم نشستِ اثبات‌شده را دوباره نمی‌پرسد",
       adapter.authenticate_calls)

    pre_send_wall = time.monotonic()
    confirm_auth, confirm_bal = (adapter.authenticate_calls,
                                 adapter.balance_calls)
    got = EX.post_order_confirm({"prepared_token": tok, "confirmed": True,
                                 "confirm_phrase": EX.DEFAULT_CONFIRM_PHRASE})
    elapsed = (time.monotonic() - pre_send_wall) * 1000.0
    ck(got.get("status") in ("success", "acknowledged")
       and got.get("record", {}).get("broker_order_id") == "BR-9001",
       "ج) تأیید یک پاسخِ واقعیِ کارگزاری برگرداند", got)
    ck(adapter.submit_calls == 1 and adapter.get_orders_calls == 0
       and adapter.queue_calls == 0,
       "چ) فقط یک POST؛ بی read-back و بی queue در مسیر",
       (adapter.submit_calls, adapter.get_orders_calls, adapter.queue_calls))
    ck(adapter.authenticate_calls == confirm_auth
       and adapter.balance_calls == confirm_bal,
       "ح) تأیید هیچ پرسشِ شبکه‌ایِ دیگری نزد",
       (adapter.authenticate_calls, adapter.balance_calls))
    t = got.get("timings") or {}
    ck(t.get("pre_send_ms") is not None and t.get("rtt_ms") is not None
       and t.get("total_ms") is not None,
       "خ) زمان‌هایِ جدا ثبت شدند", t)
    ck(t.get("pre_send_ms", 9999) < 500,
       "د) گیت‌هایِ محلیِ تأیید زیر ۵۰۰ms (بی‌شبکه)", t.get("pre_send_ms"))
    ck(elapsed < 1000, "ذ) کلِ پاسخِ تأیید زیر ۱ ثانیه در محیطِ بدیل",
       round(elapsed, 1))
    ck(got.get("read_back") == "deferred",
       "ر) read-back صریحاً به بعد سپرده شد", got.get("read_back"))
    ck((got.get("record") or {}).get("status") == "acknowledged"
       and (got.get("record") or {}).get("order_state") == "unknown",
       "ز) ACKNOWLEDGED با وضعیتِ سفارشِ UNKNOWN — پذیرش ادعا نشد",
       got.get("record"))

    again = EX.post_order_confirm({"prepared_token": tok, "confirmed": True,
                                   "confirm_phrase": EX.DEFAULT_CONFIRM_PHRASE})
    ck(again.get("status") == "error"
       and again.get("code") == "ALREADY_USED"
       and adapter.submit_calls == 1,
       "ژ) تأیید دوم همان توکن، سفارشِ دوم نمی‌سازد", again.get("code"))


def part_concurrent(EX):
    print("\n── ۴) تأییدِ هم‌زمانِ همان توکن: یک POST ──")
    pv = EX.post_order_preview(
        {"symbol": "TEST", "side": "buy", "price": 1000, "quantity": 10})
    tok = pv.get("prepared_token")
    adapter = EX._ACTIVE_ADAPTER
    before = adapter.submit_calls
    out = []
    barrier = threading.Barrier(6)

    def worker():
        barrier.wait()
        out.append(EX.post_order_confirm(
            {"prepared_token": tok, "confirmed": True,
             "confirm_phrase": EX.DEFAULT_CONFIRM_PHRASE}).get("status"))

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ok_n = out.count("success") + out.count("acknowledged")
    ck(adapter.submit_calls - before == 1 and ok_n == 1,
       "الف) شش تأییدِ هم‌زمان یک POST و یک پاسخِ موفق",
       (adapter.submit_calls - before, out))


def part_phrase_and_epoch(EX):
    print("\n── ۵) عبارتِ تأیید و دورهٔ نشست ──")
    from execution_contract import ErrorCode
    pv = EX.post_order_preview(
        {"symbol": "TEST", "side": "buy", "price": 1000, "quantity": 10})
    tok = pv.get("prepared_token")
    adapter = EX._ACTIVE_ADAPTER
    before = adapter.submit_calls
    wrong = EX.post_order_confirm({"prepared_token": tok, "confirmed": True,
                                   "confirm_phrase": "غلط"})
    ck(wrong.get("status") == "error"
       and wrong.get("code") == ErrorCode.CONFIRM_PHRASE_REQUIRED.value
       and adapter.submit_calls == before,
       "الف) عبارتِ نادرست هیچ POSTی نمی‌سازد", wrong.get("code"))
    right = EX.post_order_confirm({"prepared_token": tok, "confirmed": True,
                                   "confirm_phrase": EX.DEFAULT_CONFIRM_PHRASE})
    ck(right.get("status") in ("success", "acknowledged")
       and adapter.submit_calls == before + 1,
       "پ) توکن با عبارتِ نادرست نسوخت", right.get("status"))

    pv2 = EX.post_order_preview(
        {"symbol": "TEST", "side": "buy", "price": 1000, "quantity": 10})
    EX._void_confirmations("test: token replaced")
    stale = EX.post_order_confirm(
        {"prepared_token": pv2.get("prepared_token"), "confirmed": True,
         "confirm_phrase": EX.DEFAULT_CONFIRM_PHRASE})
    ck(stale.get("status") == "error"
       and stale.get("code") in ("STALE_CONFIRMATION",
                                 ErrorCode.CONFIRM_PHRASE_REQUIRED.value),
       "ت) تغییرِ دورهٔ نشست پیش‌نمایش را باطل می‌کند", stale)


def part_unknown(EX):
    print("\n── ۶) timeout/UNKNOWN: بی‌retry، فقط reconcile ──")
    from execution_contract import BrokerError, ErrorCode
    pv = EX.post_order_preview(
        {"symbol": "TEST", "side": "buy", "price": 1000, "quantity": 10})
    tok = pv.get("prepared_token")
    adapter = EX._ACTIVE_ADAPTER
    adapter._submit_error = BrokerError(ErrorCode.TIMEOUT, "fake timeout")
    got = EX.post_order_confirm({"prepared_token": tok, "confirmed": True,
                                 "confirm_phrase": EX.DEFAULT_CONFIRM_PHRASE})
    ck(got.get("status") == "unknown_result"
       and got.get("unknown_result") is True
       and got.get("retry_forbidden") is True,
       "الف) timeout ⇒ UNKNOWN_RESULT و retry_forbidden", got)
    ck((got.get("record") or {}).get("broker_order_id") in (None, ""),
       "پ) بی‌شناسهٔ جعلی", (got.get("record") or {}).get("broker_order_id"))
    before = adapter.submit_calls
    again = EX.post_order_confirm({"prepared_token": tok, "confirmed": True,
                                   "confirm_phrase": EX.DEFAULT_CONFIRM_PHRASE})
    ck(again.get("status") == "error" and adapter.submit_calls == before,
       "ت) تأیید دوم پس از UNKNOWN هیچ ارسالی نمی‌کند", again.get("code"))
    adapter._submit_error = None


def part_wire():
    print("\n── ۷) سیمِ واقعیِ EasyTrader: یک POST با بدنهٔ قرارداد ──")
    from execution_contract import (ExecutionStatus, OrderMode, OrderDraft, Side,
                                    InstrumentRef, Resolution)
    from execution_easytrader import EasyTraderAdapter
    from execution_service import ExecutionService, Limits
    tr = FakeTransport()
    ad = EasyTraderAdapter(transport=tr, token="fixture-token",
                           base_url="https://api-mts.orbis.easytrader.ir")
    draft = OrderDraft(execution_id="wire-1", side=Side.BUY, price=12345.0,
                       quantity=100.0, mode=OrderMode.SAFE,
                       instrument=InstrumentRef(symbol="TEST",
                                                isin="IRO1TEST0001",
                                                broker_instrument="IRO1TEST0001",
                                                resolution=Resolution.EXACT))
    svc = ExecutionService(ad, dry_run=False, limits=Limits(),
                           audit=None)
    ad.authenticate()
    prepared = svc.prepare(draft)
    ck(prepared.sendable, "الف) preflight قبول شد", prepared.preflight.checks)
    rec = svc.execute(prepared, verify=False)
    ck(rec.status is ExecutionStatus.ACKNOWLEDGED
       and rec.broker_order_id == "BR-4242",
       "پ) ack با شناسهٔ واقعی", (rec.status, rec.broker_order_id))
    ck(tr.paths() == ["/core/api/order", "/easy/api/money",
                      "/core/api/v2/order"],
       "ت) ترتیب: نشست، موجودی، سپس یک POST — بی queue",
       tr.paths())
    body = (tr.post_payload or {}).get("order") or {}
    ck(body.get("symbolIsin") == "IRO1TEST0001"
       and body.get("symbolName") == "TEST"
       and body.get("side") == 0 and body.get("price") == 12345
       and body.get("quantity") == 100 and body.get("orderModelType") == 1
       and body.get("orderFrom") == 34 and body.get("validityType") == 0
       and str(body.get("createDateTime") or "").strip(),
       "ث) بدنهٔ سیم کامل و بی‌فیلدِ جعلی", body)
    ck("commission" not in body and "totalValue" not in body,
       "ج) خلاصهٔ کلاینتِ نامعلوم فرستاده نشد", list(body))


def part_dry_run():
    print("\n── ۸) dry-run: اعتبارسنجی بله، ارسال نه ──")
    ad = FakeAdapter()
    EX, old = _setup_api(ad, dry_run=True)
    try:
        pv = EX.post_order_preview(
            {"symbol": "TEST", "side": "buy", "price": 1000, "quantity": 10})
        ck(pv.get("status") == "success" and pv.get("send_ready") is False,
           "الف) پیش‌نمایش در dry-run ساخته می‌شود ولی ارسال‌پذیر نیست", pv)
        got = EX.post_order_confirm(
            {"prepared_token": pv.get("prepared_token"), "confirmed": True,
             "confirm_phrase": EX.DEFAULT_CONFIRM_PHRASE})
        ck(got.get("status") in ("success", "validated")
           and got.get("dry_run") is True
           and (got.get("record") or {}).get("broker_order_id") in (None, "")
           and ad.submit_calls == 0,
           "پ) dry-run هیچ POSTی نمی‌زند و شناسه نمی‌سازد", got)
    finally:
        _restore(EX, old)


def main() -> int:
    os.environ.setdefault("BORS_EXECUTION_DB", os.path.join(
        tempfile.mkdtemp(prefix="fast21_"), "execution.db"))
    os.environ.setdefault("BORS_SCHEDULE_DB", os.path.join(
        tempfile.mkdtemp(prefix="fast21_sched_"), "schedules.db"))
    part_gateway()

    ad = FakeAdapter()
    EX, old = _setup_api(ad)
    try:
        part_inputs(EX)
        part_fast_path(EX)
        part_concurrent(EX)
        part_phrase_and_epoch(EX)
        part_unknown(EX)
    finally:
        _restore(EX, old)
    part_wire()
    part_dry_run()

    print("\n%d pass / %d fail" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
