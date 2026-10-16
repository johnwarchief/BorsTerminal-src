"""ردِّپا درِ عبورِ restart — آنچه محافظت می‌شود وِ آنچه عمداً نمی‌شود.

سناریوِ ۱۰ مأموریتِ System 2 («refresh/restart بی‌اجرایِ دوبارهٔ سفارش») درِ
سنجشِ زنده دوِ چیزِ متفاوت نشان داد که درِ مستندات نباید یکی جا زده شوند:

  • درِ یکِ پروسه، هرِ `execution_id` که یکِ بار dispatch شده بود باِ
    `DUPLICATE_GUARD` رد می‌شود (۲۰ شناسه، ۲۰ سطر، صفرِ تکرار).
  • پسِ restartِ پروسه رویِ همانِ دیسک، شناسه‌هایی که فقطِ **dry-run** بودند
    (`status: validated`) برنمی‌گردند وِ ارسالِ دوباره‌شان می‌گذرد — چون
    `ExecutionLedger.open_ids()` فقطِ حالت‌هایِ *نبسته* را می‌شمارد
    (`unknown_result`/`dispatched`/`acknowledged`/`scheduled`/`reconciled`).

اینِ دومی ضعفِ طراحی نیست، ولیِ یکِ تکیه‌گاهِ ایمنی هم نیست: چیزی که ازِ اینِ
پروسه بیرون نرفته، پسِ restart هم «سفارشِ باز» نیست. خطرِ واقعیِ restart مالِ
ارسالِ *واقعی* است وِ آنِ مسیر باِ نوعِ `dispatch` ثبت می‌شود وِ درِ `open_ids()`
می‌ماند. آزمون‌هایِ همینِ فایل همینِ دوِ خط را ثابت می‌کنند تاِ روزی که آداپتورِ
واقعی بنشیند، کسی «دوبارهِ ارسال درِ mock» را با «محافظتِ پسِ restart» اشتباه
نکند.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from execution_ledger import ExecutionLedger  # noqa: E402

OPEN_STATES = ("unknown_result", "dispatched", "acknowledged", "scheduled", "reconciled")


def _ledger():
    fd, path = tempfile.mkstemp(prefix="bors-ledger-test-", suffix=".db")
    os.close(fd)
    os.unlink(path)          # ExecutionLedger خود فایل می‌سازد
    return ExecutionLedger(path), path


def test_dry_run_validated_record_is_not_open_after_restart():
    led, path = _ledger()
    try:
        led.record(execution_id="x-dry-1", kind="dispatch_dry", status="validated",
                   order_state="unknown", broker="mock", symbol="فولاد", side="buy",
                   price=5170.0, quantity=50.0, mode="safe")
        assert led.open_ids() == [], "ردِّپایِ بدلِ بسته نباید «سفارشِ باز» شمرده شود"
        # وِ همینِ دلیل: شمارشِ نرخِ ارسال فقطِ `dispatch` واقعی را می‌شمارد
        assert led.events(execution_id="x-dry-1", kinds=("dispatch",), limit=1) == []
    finally:
        led.close()
        if os.path.exists(path):
            os.unlink(path)


def test_real_dispatch_with_unknown_result_survives_as_open():
    led, path = _ledger()
    try:
        led.record(execution_id="x-live-1", kind="dispatch", status="unknown_result",
                   order_state="unknown", broker="easytrader", symbol="فولاد", side="buy",
                   price=5170.0, quantity=50.0, mode="safe")
        assert led.open_ids() == ["x-live-1"], "نتیجهٔ نامعلومِ واقعی باید پسِ restart بماند"
        assert len(led.events(execution_id="x-live-1", kinds=("dispatch",), limit=1)) == 1, \
            "همینِ سطر کلیدِ `duplicate` درِ preflight پسِ restart است"
        last = led.latest_status("x-live-1")
        assert last["status"] == "unknown_result", last
    finally:
        led.close()
        if os.path.exists(path):
            os.unlink(path)


def test_closed_order_state_leaves_the_open_set():
    led, path = _ledger()
    try:
        led.record(execution_id="x-live-2", kind="dispatch", status="acknowledged",
                   order_state="unknown", broker="easytrader", symbol="شپنا", side="buy",
                   price=1040.0, quantity=100.0, mode="safe")
        assert led.open_ids() == ["x-live-2"], "acknowledgedِ بی‌order_state باز است"
        led.record(execution_id="x-live-2", kind="order_state", status="acknowledged",
                   order_state="filled", symbol="شپنا")
        assert led.open_ids() == [], "رُکوردِ آخرِ بسته (filled) سفارش را ازِ فهرستِ باز بیرون می‌برد"
        for st in OPEN_STATES:
            assert st in ("unknown_result", "dispatched", "acknowledged", "scheduled",
                          "reconciled"), st
    finally:
        led.close()
        if os.path.exists(path):
            os.unlink(path)
