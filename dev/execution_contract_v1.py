# -*- coding: utf-8 -*-
# dev/execution_contract_v1.py — گاردِ قراردادِ اجرا (Stage D)
#
# این سوئیت «تستِ Mock» نیست: قراردادِ `BrokerAdapter` را می‌آزماید و هر
# adapterِ واقعیِ آینده (مفیض/ایزی‌تریدر، آنلاین‌پلاس، و بعداً بقیه) باید از
# همان `run_contract()` سبز بیرون بیاید (§۲۹ دستورِ کار). برایِ همین با
# قراردادِ عمومی حرف می‌زنیم، نه با جزئیاتِ بدل.
#
# چهار حکمی که نگهبانش است (docs/execution/SARKHATI-ARCHITECTURE.md §۹):
#   • بی‌ISIN ⇒ NOT_ORDERABLE، و **هیچ درخواستی بیرون نمی‌رود** (§۷-ب).
#   • timeout ⇒ UNKNOWN_RESULT سپس reconcile؛ هرگز ارسالِ دوباره (§۷-الف).
#   • capabilityِ نبود ⇒ UNSUPPORTED یا UNKNOWN، نه صفرِ جعلی (§۱۸).
#   • هیچ secret درِ خروجیِ قابلِ لاگ (§۱-ط).
#
# کنترلِ منفی: `SloppyAdapter` سه باگِ واقعیِ مراجع را دارد (retry رویِ
# نتیجهٔ نامعلوم، fallback به ISINِ «زر» درِ symbolHelper.ts:18، و صفرِ جعلیِ
# صف). اگر سوئیت او را سبز بگذارد، خودِ سوئیت کور است و گارد همین را فریاد
# می‌زند.
#
# آفلاین است: هیچ شبکه، هیچ کارگزاری، هیچ سفارشِ واقعی.
# اجرا:  python dev/execution_contract_v1.py

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from execution_contract import (  # noqa: E402
    BrokerError, Capabilities, ErrorCode, ExecutionStatus, InstrumentRef,
    OrderDraft, QueueSnapshot, Resolution, SessionState, Side, redact,
)
from execution_mock import MockBrokerAdapter  # noqa: E402

PASS = FAIL = 0

FOOLAD = InstrumentRef(symbol="فولاد", ins_code="46348559193224090",
                       isin="IRO1IKCO0001", broker_instrument="IRO1IKCO0001",
                       resolution=Resolution.EXACT)
NO_ISIN = InstrumentRef(symbol="پارسان", ins_code="999", isin=None,
                        broker_instrument=None, resolution=Resolution.EXACT)


def draft(execution_id="EX-1", instrument=FOOLAD, side=Side.BUY,
          price=12610.0, quantity=1000.0) -> OrderDraft:
    return OrderDraft(execution_id=execution_id, instrument=instrument, side=side,
                      price=price, quantity=quantity,
                      price_source="board.p_last", price_as_of="2026-10-06T09:00:00")


def builder(cls=MockBrokerAdapter):
    """`build(**kw)` هر بار یک adapterِ تازه می‌سازد؛ هر case هرچه لازم دارد
    می‌دهد (script، capabilities، …)."""
    def build(**kw):
        kw.setdefault("instruments", (FOOLAD, NO_ISIN))
        kw.setdefault("capabilities", Capabilities(list_orders=True, order_state=True,
                                                  queue_position=True))
        kw.setdefault("script", {})
        return cls(**kw)
    return build


def _raises(fn, code):
    """(آیا BrokerError با کدِ خواسته‌شده داد؟، خودِ خطا یا None)"""
    try:
        fn()
    except BrokerError as e:
        return e.code is code, e
    except Exception as e:                                    # noqa: BLE002
        return False, e
    return False, None


# ── قراردادِ قابلِ استفادهٔ مجدد ─────────────────────────────────────────────
def run_contract(build, label="adapter"):
    """نتیجه فهرستِ `(نامِ case، سبز؟، توضیح)` است."""
    out = []

    def case(name, fn):
        try:
            ok, got = fn()
        except Exception as e:                                # noqa: BLE002
            ok, got = False, f"exception {type(e).__name__}: {e}"
        out.append((f"{label}/{name}", bool(ok), str(got)))

    def c_success():
        a = build()
        r = a.submit_order(draft())
        return (r.status is ExecutionStatus.ACKNOWLEDGED and r.broker_order_id
                and r.actual_send_at is not None), f"status={r.status} id={r.broker_order_id}"
    case("success_acknowledges_one_order", c_success)

    def c_price():
        a = build(script={"EX-1": ["reject_price"]})
        hit, e = _raises(lambda: a.submit_order(draft()), ErrorCode.INVALID_PRICE)
        return (hit and not e.is_unknown_result and not a.server_orders,
                f"hit={hit} unknown={getattr(e, 'is_unknown_result', None)} "
                f"server={len(a.server_orders)}")
    case("validation_error_is_not_unknown_result", c_price)

    def c_auth():
        a = build(script={"EX-1": ["auth"]})
        hit, e = _raises(lambda: a.submit_order(draft()), ErrorCode.AUTH_FAILED)
        return (hit and not e.is_unknown_result and not a.server_orders, f"hit={hit}")
    case("auth_failure_is_terminal_not_retryable", c_auth)

    def c_expired():
        a = build(script={"EX-1": ["expired"]})
        hit, _ = _raises(lambda: a.submit_order(draft()), ErrorCode.SESSION_EXPIRED)
        still = a.session_status().state is SessionState.EXPIRED
        return (hit and still, f"hit={hit} state={a.session_status().state}")
    case("session_expiry_is_reported_back", c_expired)

    def c_timeout():
        a = build(script={"EX-1": ["timeout"]})
        hit, e = _raises(lambda: a.submit_order(draft()), ErrorCode.TIMEOUT)
        found = a.get_orders()
        return (hit and e.is_unknown_result and len(found) == 1,
                f"hit={hit} unknown={getattr(e, 'is_unknown_result', None)} "
                f"server_orders={len(found)}")
    case("timeout_becomes_unknown_result_with_server_side_order", c_timeout)

    def c_reconcile():
        a = build(script={"EX-1": ["timeout"]})
        _raises(lambda: a.submit_order(draft()), ErrorCode.TIMEOUT)
        remote = a.get_orders()
        rec = remote[0] if remote else None
        reconciled = rec is not None and rec.execution_id == "EX-1"
        # و اگر کسی باز هم بخواهد همان execution_id را بفرستد، قرارداد باید
        # *رد* کند، نه سفارشِ دوم بسازد.
        refused, _ = _raises(lambda: a.submit_order(draft("EX-1")),
                             ErrorCode.DUPLICATE_GUARD)
        return (reconciled and refused and len(a.server_orders) == 1,
                f"reconciled={reconciled} refused={refused} "
                f"server_orders={len(a.server_orders)}")
    case("after_timeout_reconcile_resolves_without_resubmit", c_reconcile)

    def c_retry_trap():
        a = build(script={"EX-1": ["timeout"]})
        _raises(lambda: a.submit_order(draft("EX-1")), ErrorCode.TIMEOUT)
        a.submit_order(draft("EX-2"))          # ارسالِ دوباره با شناسۀِ تازه
        return (len(a.server_orders) == 2,
                f"server_orders={len(a.server_orders)} (باید ۲ باشد تا خطر ثابت شود)")
    case("blind_retry_after_timeout_really_duplicates", c_retry_trap)

    def c_5xx():
        a = build(script={"EX-1": ["http5xx"]})
        hit, e = _raises(lambda: a.submit_order(draft()), ErrorCode.NETWORK_ERROR)
        found = a.get_orders()
        return (hit and e.is_unknown_result and len(found) == 0,
                f"hit={hit} server_orders={len(found)}")
    case("http5xx_is_unknown_result_and_reconcile_finds_nothing", c_5xx)

    def c_duplicate():
        a = build()
        a.submit_order(draft("EX-DUP"))
        hit, _ = _raises(lambda: a.submit_order(draft("EX-DUP")), ErrorCode.DUPLICATE_GUARD)
        return (hit and len(a.server_orders) == 1,
                f"hit={hit} server_orders={len(a.server_orders)}")
    case("duplicate_execution_id_is_guarded", c_duplicate)

    def c_not_orderable():
        a = build()
        hit, _ = _raises(lambda: a.submit_order(draft(instrument=NO_ISIN)),
                         ErrorCode.NOT_ORDERABLE)
        submits = [w for w in a.wire_calls if w.startswith("submit:")]
        return (hit and not submits and not a.server_orders,
                f"hit={hit} wire_submits={len(submits)} server_orders={len(a.server_orders)}")
    case("missing_isin_is_not_orderable_and_never_hits_the_wire", c_not_orderable)

    def c_unresolved():
        a = build()
        ref = a.resolve_instrument("نمادِ-نبوده")
        ok_flag, reason = ref.orderable()
        return (ref.resolution is Resolution.UNRESOLVED and not ok_flag
                and reason.startswith("NOT_ORDERABLE"),
                f"res={ref.resolution} reason={reason}")
    case("unknown_symbol_resolves_to_unresolved_not_a_guess", c_unresolved)

    def c_cancel():
        a = build(capabilities=Capabilities(list_orders=True, cancel=False))
        r = a.submit_order(draft())
        hit, _ = _raises(lambda: a.cancel_order(r.broker_order_id), ErrorCode.UNSUPPORTED)
        return (hit, f"unsupported_raised={hit}")
    case("cancel_without_capability_raises_unsupported", c_cancel)

    def c_queue_unknown():
        a = build(capabilities=Capabilities(list_orders=True, queue_position=False))
        r = a.submit_order(draft())
        q = a.get_queue_position(r.broker_order_id)
        return (q is None or not q.known, f"queue={q}")
    case("queue_without_capability_is_unknown_not_zero", c_queue_unknown)

    def c_queue_no_data():
        a = build()
        r = a.submit_order(draft())
        q = a.get_queue_position(r.broker_order_id)
        return (q is None or q.position is None, f"queue={q}")
    case("queue_with_no_server_data_stays_unknown", c_queue_no_data)

    def c_rejected():
        a = build(script={"EX-1": ["reject_broker"]})
        hit, e = _raises(lambda: a.submit_order(draft()), ErrorCode.BROKER_REJECTED)
        return (hit and not e.is_unknown_result and e.retry_forbidden
                and bool(e.broker_message),
                f"hit={hit} msg={getattr(e, 'broker_message', None)!r}")
    case("broker_rejection_carries_its_own_message", c_rejected)

    def c_times():
        a = build()
        r = a.submit_order(draft())
        return (r.scheduled_at is not None and r.actual_send_at is not None
                and r.execution_id == "EX-1" and r.attempts == 1,
                f"sched={r.scheduled_at} attempts={r.attempts}")
    case("record_keeps_scheduled_and_send_times_with_one_attempt", c_times)

    def c_redact():
        a = build()
        a.submit_order(draft())
        blob = repr(getattr(a, "redacted_log", []))
        clean = ("super-secret-token-value" not in blob
                 and "session=abcdef" not in blob
                 and "<redacted>" in blob)
        probe = redact({"Authorization": "Bearer abcdef123456", "path": "Order/send"})
        return (clean and "abcdef123456" not in repr(probe),
                f"clean={clean} probe={probe}")
    case("no_secret_survives_redaction", c_redact)

    return out


# ── کنترلِ منفی: adapterِ بدقلق باید بیفتد ───────────────────────────────────
class SloppyAdapter(MockBrokerAdapter):
    """سه باگِ واقعیِ مراجع، یک‌جا (§۷-الف و §۷-ب)."""

    def submit_order(self, dr):
        try:
            return MockBrokerAdapter.submit_order(self, dr)
        except BrokerError as e:
            # باگ ۱: retryِ کور رویِ نتیجهٔ نامعلوم — همان کاری که مرجعِ اول
            # بعدِ 408/5xx می‌کند و سفارشِ تکراریِ واقعی می‌سازد.
            if e.is_unknown_result:
                again = OrderDraft(execution_id=dr.execution_id + "-R",
                                   instrument=dr.instrument, side=dr.side,
                                   price=dr.price, quantity=dr.quantity,
                                   mode=dr.mode)
                return MockBrokerAdapter.submit_order(self, again)
            raise

    def resolve_instrument(self, symbol):
        ref = MockBrokerAdapter.resolve_instrument(self, symbol)
        if ref.resolution is Resolution.UNRESOLVED:
            # باگ ۲: fallback به ISINِ «زر» (symbolHelper.ts:18)
            return InstrumentRef(symbol=symbol, ins_code="0", isin="IRTKZARF0001",
                                 broker_instrument="IRTKZARF0001",
                                 resolution=Resolution.EXACT)
        return ref

    def get_queue_position(self, broker_order_id):
        # باگ ۳: صفرِ جعلی — یعنی «اولِ صف شدید»، بی‌آنکه سرور چیزی گفته باشد
        return QueueSnapshot(position=0, volume_ahead=0.0, source="sloppy")


MUST_CATCH = ("timeout_becomes_unknown_result_with_server_side_order",
              "unknown_symbol_resolves_to_unresolved_not_a_guess",
              "queue_without_capability_is_unknown_not_zero")


def main() -> int:
    global PASS, FAIL
    print("execution_contract_v1 — قراردادِ BrokerAdapter رویِ MockBrokerAdapter")
    for name, ok, got in run_contract(builder(), "mock"):
        if ok:
            PASS += 1
            print(f"  ok   {name}")
        else:
            FAIL += 1
            print(f"  FAIL {name}  -> {got}")

    print("\nکنترلِ منفی — adapterِ بدقلق باید درِ همین موارد بیفتد:")
    bad = {n.split("/", 1)[1] for n, ok, _ in run_contract(builder(SloppyAdapter), "sloppy")
           if not ok}
    for n in MUST_CATCH:
        if n in bad:
            PASS += 1
            print(f"  ok   caught: {n}")
        else:
            FAIL += 1
            print(f"  FAIL missed: {n} — سوئیت این باگ را نمی‌بیند، پس کور است")
    print(f"  (sloppy در {len(bad)} case افتاد)")

    print(f"\nexecution_contract_v1: {PASS} passed / {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
