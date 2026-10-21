"""api/execution.py — درِ محلیِ موتورِ اجرای سرخطی (Stage K — رابطِ نازک).

چیزی که این در **نیست**: تصمیم‌گیرندهٔ «کجا وصل شویم». انتخابِ آداپتور فقط از
دو متغیرِ محیطیِ صریح خوانده می‌شود و از هیچ بدنهٔ درخواستی نه:

  BORS_EXECUTION_ADAPTER = mock | easytrader     (پیش‌فرض: mock)
  BORS_EXECUTION_LIVE    = 1                     (پیش‌فرض: خاموش)

تا «mock» یا تا LIVE نخورده باشد، `DRY_RUN` ثابتِ True می‌ماند و هیچ درخواستِ
برون‌سازمانی ساخته نمی‌شود. رأیِ مالک در ۱۴۰۵-۰۷-۲۴ سکوی هدف را تعیین کرد
(EasyTrader/Orbis-MTS، نه Mofid Online-Plus/Titan) — این همان D8 بسته‌شده است.
اما **D1 باز است**: نشستنِ به حسابِ واقعی دستِ خودِ مالک است (ورودِ تعاملی،
بی‌دورزدنِ CAPTCHA/MFA) و هیچ سفارشِ واقعی بی‌تأییدِ روشنِ او رویِ فرمِ نهایی
انجام نمی‌شود.

چیزی که این در هست: همان سرویسِ `execution_service` که گاردهایِ `dev/execution_*`
می‌آزمایند — پیش‌فرود، آماده‌سازی، ارسال، reconcile، صفِ سه‌حالته، قفلِ توقفِ
ماندگار و بازیابی پسِ restart. رابطِ نازکِ UI قضاوتِ تازه‌ای نمی‌سازد و عددِ
جعلی نمی‌بیند: نبودِ نگاشتِ کارگزاری درِ `instrument` به‌شکلِ FAIL خوانده
می‌شود، نه صفر؛ و `live_enabled` ازِ وضعیتِ واقعیِ آداپتور خوانده می‌شود، نه
ازِ یکِ ثابت.

token درِ همین پروسه و درِ حافظه می‌ماند (`POST /api/execution/session`، یا
`POST /api/execution/connection/capture-session` که فقط با کلیکِ صریحِ مالک
نشست را از مرورگرِ مدیریت‌شده می‌خواند) و پس از restart، فقط اگر ترافیک مجاز
باشد، از مخزنِ امنِ ویندوز بازیابی می‌شود؛ هیچ مسیری آن را درِ فایل، دیتابیس،
لاگ یا پاسخِ HTTP نمی‌نویسد.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from typing import Any, Mapping
from urllib.parse import urlparse

from fastapi import APIRouter, Body, HTTPException, Query, Request

from bors_config import APP_VERSION, DB_PATH, WORK_DIR
from execution_contract import (
    BrokerAdapter, BrokerError, Capabilities, ErrorCode, ExecutionRecord,
    ExecutionStatus, InstrumentRef, OrderDraft, OrderMode, OrderState, Resolution, Side,
    UNRESOLVED_CODES, redact,
)
from execution_easytrader import (
    EasyTraderAdapter, RefusingTransport, RequestsTransport, WIRE_BASE_URL,
    WIRE_HYPOTHESIS, WIRE_PROBE_HOST_HEALTH, WIRE_SESSION_PROBE_CANDIDATES,
    easytrader_payload,
)
import execution_connect as EXC                            # noqa: E402
import execution_connection as ECONN                       # noqa: E402
import execution_browser_host as BH                        # noqa: E402
import execution_cockpit as CK                             # noqa: E402
import execution_offerings as OF                           # noqa: E402
import execution_readiness as RD                           # noqa: E402
import execution_schedule as SCH                           # noqa: E402
import execution_session_store as SESS                     # noqa: E402
import execution_strategy_core as SC                       # noqa: E402
import execution_strategy_engine as SE                     # noqa: E402
from execution_ledger import ARMED, HALT, TRIPPED, default_ledger
from execution_mock import MockBrokerAdapter
from execution_service import ExecutionError, ExecutionService, Limits
from execution_timing import Scheduler, TimeSource, percentile

router = APIRouter()

#: وضعیت‌هایِ مستقلِ منابع (Round 10). هر کدام فقط از شاهدِ خودش ساخته می‌شود.
WATCHLIST_VERIFIED = "WATCHLIST_VERIFIED"
WATCHLIST_UNAVAILABLE = "WATCHLIST_UNAVAILABLE"
PORTFOLIO_VERIFIED = "PORTFOLIO_VERIFIED"
PORTFOLIO_PARTIALLY_VERIFIED = "PORTFOLIO_PARTIALLY_VERIFIED"
PORTFOLIO_UNAVAILABLE = "PORTFOLIO_UNAVAILABLE"
BUYING_POWER_VERIFIED = "BUYING_POWER_VERIFIED"
BUYING_POWER_UNAVAILABLE = "BUYING_POWER_UNAVAILABLE"
ACCOUNT_SOURCE_BLOCKED = "ACCOUNT_SOURCE_BLOCKED"
ORDER_WRITE_UNVERIFIED = "ORDER_WRITE_UNVERIFIED"

_LOCK = threading.Lock()
ADAPTER_ENV = "BORS_EXECUTION_ADAPTER"
LIVE_ENV = "BORS_EXECUTION_LIVE"
ALLOWED_ADAPTERS = ("mock", "easytrader")
#: آستانهٔ «فوری»: اگر مهلتِ هدف از این نزدیک‌تر باشد، درِ همان درخواست
#: می‌نشینیم و threadِ تازه‌ای نمی‌سازیم — هزینهٔ یکِ خوابِ کوتاه کمتر از یکِ
#: اجرایِ هم‌زمان است.
IMMEDIATE_WINDOW_MS = 250.0


def _env_flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _settings_snapshot() -> dict[str, Any]:
    """تنظیمِ غیرمحرمانۀ ذخیره‌شده. خرابیِ بانک هرگز انتخابِ آداپتور را نمی‌شکند."""
    try:
        import execution_settings as ES
        return ES.read()
    except Exception as e:                       # noqa: BLE001 - بانک/دیسک/قفل
        return {"adapter": "", "source": "unavailable", "read_only": False,
                "live_env": _env_flag(LIVE_ENV), "error": type(e).__name__}


def _configured_adapter(settings: dict[str, Any]) -> str:
    """انتخابِ آداپتور: اول محیط، بعد تنظیمِ درون‌برنامه، وگرنه mock.

    پیش از این **فقط** env بود؛ درِ بیلدِ منجمدِ دسکتاپ هیچ راهی برای ست‌کردنش
    نبود، پس «اتصال به مفید» برایِ کاربرِ واقعی عملاً خاموش می‌ماند (سنجشِ
    v1.0.93 رویِ همین ماشین: adapter=mock). env همچنان مقدم است، چون گاردها و CI
    به آن تکیه می‌کنند.
    """
    got = (os.environ.get(ADAPTER_ENV) or "").strip().lower()
    if got:
        return got if got in ALLOWED_ADAPTERS else "mock"
    got = str(settings.get("adapter") or "").strip().lower()
    return got if got in ALLOWED_ADAPTERS else "mock"


_CFG = _settings_snapshot()
# تنها adapterهایِ ممکن. بی‌ترافیک، `RefusingTransport` می‌نشیند.
ADAPTER_KIND = _configured_adapter(_CFG)
LIVE_REQUESTED = ADAPTER_KIND == "easytrader" and _env_flag(LIVE_ENV)
# حالتِ فقط‌خواندنی: GETها مجازند تا نشست *واقعاً* تأیید شود و فهرست‌ها خوانده
# شوند. ارسالِ سفارش همچنان فقط با `BORS_EXECUTION_LIVE=1` — دو گیتِ جدا.
READ_ONLY_REQUESTED = (ADAPTER_KIND == "easytrader" and bool(_CFG.get("read_only"))
                       and not LIVE_REQUESTED)
TRAFFIC_ALLOWED = bool(LIVE_REQUESTED or READ_ONLY_REQUESTED)
DRY_RUN = not LIVE_REQUESTED

#: ردِّپایِ ماندگار رویِ `user.db` + قفلِ توقفِ اضطراری. بی‌این، هر restart
#: «چه فرستادم و چه شد» را می‌سوزاند (بندِ ۵-۳ و ۶-۴ مأموریتِ ۱۴۰۵-۰۷-۲۳).
_AUDIT = default_ledger()

#: ساعتِ dispatch: فقط ساعتِ سیستم. محدودیتش درِ `/status` اعلام می‌شود —
#: ادعایِ دقتِ NTP اینجا نوشته نمی‌شود (بندِ ۴-د مأموریت: «اگر فقط ساعت سیستم
#: در دسترس است، محدودیت آن را گزارش کن»).
_CLOCK_SOURCE = "system"
_CLOCK_LIMIT = ("ساعتِ سیستم بدونِ آفستِ NTP؛ زمان‌بندی رویِ monotonic است پس پرشِ "
                "ساعتِ دیواری dispatch را جابه‌جا نمی‌کند، ولی خودِ هدفِ دیواری "
                "قابلِ ادعایِ دقتِ میلی‌ثانیه نیست")
_SCHEDULER = Scheduler(TimeSource())

_EASYTRADER: EasyTraderAdapter | None = None


def _adapter() -> BrokerAdapter:
    global _EASYTRADER
    if ADAPTER_KIND == "easytrader":
        _EASYTRADER = EasyTraderAdapter(
            transport=RequestsTransport() if TRAFFIC_ALLOWED else RefusingTransport(),
            writes_allowed=bool(LIVE_REQUESTED))
        return _EASYTRADER
    # صف/وضعیت/لیست را بدل «می‌دهد» تا مسیرِ reconcile و پایشِ صف قابلِ دیدن
    # باشد؛ `balances` عمداً False است تا پیش‌فرود «بی‌داده» را از «صفر» جدا
    # نگه دارد (§۱۶ دستورِ کار).
    return MockBrokerAdapter(capabilities=Capabilities(
        place=True, list_orders=True, order_state=True,
        queue_position=True, cancel=True, best_bid_ask=False, balances=False))


def _env_int(name: str) -> int | None:
    """عددِ محیط یا None. بی‌مقدارِ نامعتبرِ بی‌صدا: «تعریف‌نشده» با «صفر» یکی نیست."""
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return None
    try:
        n = int(raw)
    except ValueError:
        return None
    return n if n > 0 else None


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return default
    return v if v > 0 else default


#: سقف‌هایِ ریسکِ دروازۀ HTTP. `BORS_EXECUTION_MAX_ORDERS_PER_SYMBOL` و
#: `BORS_EXECUTION_MAX_ORDERS_TOTAL` هر دو اختیاری‌اند؛ ولی اگر *هیچ‌کدام* و
#: هیچ سقفِ ارزشی هم تنظیم نشده باشد، اجرایِ زنده متوقف می‌شود (`_risk_gate`).
_LIMITS = Limits(
    max_orders_per_window=_env_int("BORS_EXECUTION_MAX_ORDERS_PER_SYMBOL"),
    max_total_orders_per_window=_env_int("BORS_EXECUTION_MAX_ORDERS_TOTAL"),
    max_order_value=_env_float("BORS_EXECUTION_MAX_ORDER_VALUE", 0.0) or None,
    window_seconds=_env_float("BORS_EXECUTION_RATE_WINDOW_S", 60.0))

_ACTIVE_ADAPTER = _adapter()
_SERVICE = ExecutionService(_ACTIVE_ADAPTER, dry_run=DRY_RUN, limits=_LIMITS,
                            audit=_AUDIT, scheduler=_SCHEDULER)

# ── زمان‌بندیِ ماندگار (execution_schedule.py) ─────────────────────────────
#: store جدا از market.db است؛ live executor این‌جا عمداً وصل نیست.
_SCHEDULE_STORE: SCH.ScheduleStore | None = None
_SCHEDULE_RUNNER: SCH.ScheduleRunner | None = None
_SCHEDULE_STORE_LOCK = threading.Lock()
_SCHEDULE_RUNNER_LOCK = threading.Lock()
SCHEDULE_DB_ENV = "BORS_SCHEDULE_DB"
SCHEDULE_RUNNER_ENV = "BORS_SCHEDULE_RUNNER"
OFFERINGS_DB_ENV = "BORS_OFFERINGS_DB"
_OFFERING_STORE: OF.OfferingStore | None = None
_OFFERING_LOCK = threading.Lock()
COCKPIT_DB_ENV = "BORS_COCKPIT_DB"
_COCKPIT_STORE: CK.CockpitStore | None = None
_COCKPIT_LOCK = threading.Lock()


def _offering_store() -> OF.OfferingStore:
    global _OFFERING_STORE
    with _OFFERING_LOCK:
        if _OFFERING_STORE is None:
            path = (os.environ.get(OFFERINGS_DB_ENV) or "").strip() \
                or os.path.join(WORK_DIR, "execution_offerings.db")
            _OFFERING_STORE = OF.OfferingStore(path)
        return _OFFERING_STORE


def _cockpit_store() -> CK.CockpitStore:
    global _COCKPIT_STORE
    with _COCKPIT_LOCK:
        if _COCKPIT_STORE is None:
            path = (os.environ.get(COCKPIT_DB_ENV) or "").strip() \
                or os.path.join(WORK_DIR, "execution_cockpit.db")
            _COCKPIT_STORE = CK.CockpitStore(path)
        return _COCKPIT_STORE


def _schedule_store() -> SCH.ScheduleStore:
    global _SCHEDULE_STORE
    with _SCHEDULE_STORE_LOCK:
        if _SCHEDULE_STORE is None:
            path = (os.environ.get(SCHEDULE_DB_ENV) or "").strip() \
                or SCH.default_store_path(WORK_DIR)
            _SCHEDULE_STORE = SCH.ScheduleStore(path)
        return _SCHEDULE_STORE


def _schedule_calendar() -> SCH.LocalTradingCalendar:
    return SCH.LocalTradingCalendar(DB_PATH)


def _schedule_facts(rec: SCH.ScheduleRecord, at_ms: int | None = None) -> SCH.DarvandFacts:
    facts = SCH.local_identity_facts(DB_PATH, rec.symbol)
    facts.now_ms = SCH.now_ms() if at_ms is None else int(at_ms)
    return facts


def _schedule_runner() -> SCH.ScheduleRunner:
    global _SCHEDULE_RUNNER
    with _SCHEDULE_RUNNER_LOCK:
        if _SCHEDULE_RUNNER is None:
            _SCHEDULE_RUNNER = SCH.ScheduleRunner(
                _schedule_store(), SCH.LocalFactsProvider(DB_PATH, _schedule_calendar()),
                calendar=_schedule_calendar(), executor=SCH.DryRunExecutor(),
                halted=lambda: _SERVICE.halted(),
                live_enabled=False, contract_verified=False)
        return _SCHEDULE_RUNNER


def start_schedule_runner() -> dict[str, Any]:
    """هوکِ startup؛ در تست‌ها با BORS_SCHEDULE_RUNNER=0 خاموش می‌شود."""
    if (os.environ.get(SCHEDULE_RUNNER_ENV) or "1").strip().lower() in ("0", "false", "no", "off"):
        return {"started": False, "reason": "disabled by env"}
    runner = _schedule_runner()
    runner.start()
    return {"started": True, "recovered": runner.last_tick,
            "readiness": SCH.readiness()}


def _recover_session() -> dict[str, Any]:
    """بازیابیِ توکنِ ذخیره‌شده پس از restart — فقط وقتی ترافیک مجاز است.

    هیچ درخواستی به کارگزاری نمی‌زند؛ فقط مخزنِ امن را می‌خواند. بی‌ترافیک،
    خواندن هم انجام نمی‌شود تا رازِ بی‌مصرف درِ حافظه ننشیند. انقضا داخلِ
    `execution_session_store` بررسی می‌شود و توکنِ منقضی هرگز ست نمی‌شود.
    """
    off = {"attempted": False, "loaded": False, "code": "NOT_APPLICABLE",
           "source": "none", "present": False, "exp": None, "exp_iso": None}
    if ADAPTER_KIND != "easytrader":
        return off
    if not TRAFFIC_ALLOWED or not isinstance(_ACTIVE_ADAPTER, EasyTraderAdapter):
        return {**off, "code": "TRAFFIC_OFF"}
    return SESS.restore_session(_ACTIVE_ADAPTER)


_SESSION_RECOVERY: dict[str, Any] = _recover_session()


def _strategy_server_clock() -> dict[str, Any] | None:
    if not isinstance(_ACTIVE_ADAPTER, EasyTraderAdapter):
        return None
    try:
        return _ACTIVE_ADAPTER.server_clock()
    except Exception:
        return None


#: موتورِ Strategyها رویِ همان آداپتور/سرویس می‌نشیند. live_allowed اینجا
#: ثابت نیست؛ در هر درخواست از گیت‌های env/تأیید/ترافیک گرفته می‌شود.
_STRATEGY_ENGINE = SE.StrategyEngine(
    _ACTIVE_ADAPTER, scheduler=_SCHEDULER, server_clock=_strategy_server_clock,
    live_allowed=False, halted=lambda: _SERVICE.halted())


#: عبارتِ تأییدِ انسانی برایِ اجرایِ زنده. مقدارِ پیش‌فرض *اختراع نشده*: همان
#: برچسبِ دکمهٔ پنلِ اجرا است (`ExecutionPanel.tsx`: «تأییدِ نهایی») تا کاربر
#: چیزی را تایپ کند که رویِ صفحه می‌بیند. `BORS_EXECUTION_CONFIRM_PHRASE` برایِ
#: عوض کردنش؛ بی‌اجرایِ زنده این گیت بی‌اثر است (تمرین/پیش‌نمایش نمی‌شکند).
CONFIRM_PHRASE_ENV = "BORS_EXECUTION_CONFIRM_PHRASE"
DEFAULT_CONFIRM_PHRASE = "تأییدِ نهایی"


def _confirm_phrase() -> str:
    return (os.environ.get(CONFIRM_PHRASE_ENV) or DEFAULT_CONFIRM_PHRASE).strip()


def _confirm_gate(body: dict[str, Any]) -> tuple[bool, str]:
    """`confirmed: true` تنها یعنی «یکِ boolean فرستادند». برایِ ارسالِ واقعی،
    عبارتِ تأیید باید *خوانده* و باِ چیزی که UI نشان می‌دهد برابری کند."""
    if DRY_RUN or not _live_now():
        return True, ""
    return (str(body.get("confirm_phrase") or "").strip() == _confirm_phrase(),
            _confirm_phrase())


def _risk_gate() -> tuple[bool, str]:
    """دروازۀ System 2: اجرایِ زنده بی‌پیکربندیِ ریسک مجاز نیست.

    چرا این‌جا و نه داخلِ `ExecutionService`: سرویس واحدِ لایه‌هایِ بسیاری است و
    آزمون‌هایِ واحدِ آن باِ سقفِ پیش‌فرضِ خاموش کار می‌کنند؛ چیزی که باید بسته
    باشد، *دروازۀ HTTPِ ارسال* است، آن هم فقط وقتی ترافیکِ زنده واقعاً روشن است.
    """
    if DRY_RUN or not _live_now():
        return True, ""
    lim = _SERVICE.limits
    if (lim.max_order_value is None and lim.max_orders_per_window is None
            and lim.max_total_orders_per_window is None):
        return False, ("هیچ سقفِ ریسکی تنظیم نشده (ارزشِ هر سفارش، یا سقفِ تعدادِ "
                       "هر-نماد، یا سقفِ جمعی) — اجرایِ زنده متوقف است. "
                       "BORS_EXECUTION_MAX_ORDER_VALUE / "
                       "BORS_EXECUTION_MAX_ORDERS_PER_SYMBOL / "
                       "BORS_EXECUTION_MAX_ORDERS_TOTAL")
    return True, ""


def _recover() -> int:
    """ردِّپا را به دفترِ حافظه برمی‌گرداند. چندتا؟ همین را /status اعلام می‌کند.

    چرا بی‌ساختنِ وضعیت: رکوردِ بازیابی‌شده همان آخرینِ حالتِ *دیده‌شده* را
    دارد. سفارشی که UNKNOWN_RESULT مانده، UNKNOWN می‌ماند و باید `reconcile`
    شود — نه اینکه restart خودش را «پذیرفته شد» جا بزند.
    """
    n = 0
    for eid in _AUDIT.open_ids():
        last = _AUDIT.latest_status(eid)
        if not last:
            continue
        try:
            side = Side(last["side"]) if last.get("side") else Side.BUY
            mode = OrderMode(last["mode"]) if last.get("mode") else OrderMode.SAFE
        except ValueError:
            continue
        rec = ExecutionRecord(
            execution_id=eid, broker=last.get("broker") or ADAPTER_KIND,
            account=None, symbol=last.get("symbol") or "", isin=None,
            side=side, price=last.get("price"), quantity=last.get("quantity"),
            mode=mode)
        st = (last.get("status") or "").lower()
        rec.status = next((s for s in ExecutionStatus if s.value == st),
                          ExecutionStatus.UNKNOWN_RESULT)
        rec.error_code = next((c for c in ErrorCode
                               if c.value == (last.get("error_code") or "")), None)
        rec.error_detail = last.get("detail") or ""
        rec.note("recovered from durable ledger after restart")
        _SERVICE.adopt(rec)
        n += 1
    if n:
        _AUDIT.record(execution_id="-", kind="recovery", status=ARMED,
                      detail="%d order(s) re-adopted from durable ledger" % n)
    return n


_RECOVERED = _recover()


def _draft_from(body: dict[str, Any]) -> OrderDraft:
    symbol = str(body.get("symbol") or "").strip()
    if not symbol:
        raise HTTPException(400, "نماد داده نشده")
    side_s = str(body.get("side") or "buy").strip().lower()
    try:
        side = Side(side_s)
    except ValueError:
        raise HTTPException(400, f"جهتِ نامعلوم: {side_s}") from None
    try:
        mode = OrderMode(str(body.get("mode") or "safe").strip().lower())
    except ValueError:
        raise HTTPException(400, "حالتِ نامعلوم") from None

    ref = _resolve_instrument(symbol)
    if body.get("mock_instrument") is True:
        # نگاشتِ کارگزاری عمداً «نیست» (§۱-ج). برایِ دیدنِ کلِ مسیر، درخواستِ
        # صریحِ mock یک شناسهٔ بدل می‌چسباند و درِ پاسخِ همان را هم اعلام می‌کند.
        ref = dataclasses.replace(
            ref, broker_instrument=f"MOCK:{symbol}",
            resolution=Resolution.EXACT if ref.isin else ref.resolution)
        if isinstance(_ACTIVE_ADAPTER, MockBrokerAdapter):
            _ACTIVE_ADAPTER.add_instrument(ref)
    elif ADAPTER_KIND == "easytrader" and ref.isin:
        # درِ این سکو شناسۀِ قابلِ سفارش **خودِ ISIN** است (مخزن ۲: `symbolIsin`،
        # نه ins_code). پس نگاشتِ کارگزاری حدس نیست، برداشتنِ همان ISIN است.
        # برایِ mock این شاخه اجرا نمی‌شود تا رفتارِ آزموده‌شده‌یِ پیشین دست‌نخورده
        # بماند (§۱-ج: بی‌`mock_instrument` هیچ نگاشتی ساخته نمی‌شود).
        ref = dataclasses.replace(ref, broker_instrument=ref.isin)
    price = body.get("price")
    qty = body.get("quantity")
    return OrderDraft(
        execution_id=str(body.get("execution_id") or f"x-{uuid.uuid4().hex[:12]}"),
        instrument=ref, side=side,
        price=float(price) if price is not None else None,
        quantity=float(qty) if qty is not None else None,
        mode=mode,
        price_source=str(body.get("price_source") or "unspecified"),
        price_as_of=body.get("price_as_of"),
    )


def _instrument_by_isin(isin: str) -> dict[str, Any]:
    """ISIN ← نماد/ins_code از همان `instruments`؛ مبهم و بی‌نگاشت جدا می‌مانند."""
    want = str(isin or "").strip().upper()
    if not want:
        return {"resolved": False, "isin": isin, "symbol": None, "ins_code": None,
                "ambiguous": False, "reason": "EMPTY_ISIN"}
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=15)
    except sqlite3.Error:
        return {"resolved": False, "isin": isin, "symbol": None, "ins_code": None,
                "ambiguous": False, "reason": "LOCAL_DB_UNAVAILABLE"}
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT ins_code, isin, l_val18 FROM instruments "
            "WHERE UPPER(TRIM(isin)) = ? ORDER BY updated_at DESC LIMIT 2",
            (want,)).fetchall()
    except sqlite3.OperationalError:
        return {"resolved": False, "isin": isin, "symbol": None, "ins_code": None,
                "ambiguous": False, "reason": "LOCAL_DB_UNAVAILABLE"}
    finally:
        conn.close()
    if not rows:
        return {"resolved": False, "isin": isin, "symbol": None, "ins_code": None,
                "ambiguous": False, "reason": "ISIN_NOT_MAPPED"}
    if len(rows) > 1:
        return {"resolved": False, "isin": isin, "symbol": None, "ins_code": None,
                "ambiguous": True, "reason": "ISIN_AMBIGUOUS"}
    r = rows[0]
    sym = str(r["l_val18"] or "").strip() or None
    if not sym:
        return {"resolved": False, "isin": isin, "symbol": None, "ins_code": None,
                "ambiguous": False, "reason": "ISIN_NO_SYMBOL"}
    return {"resolved": True, "isin": isin, "symbol": sym,
            "ins_code": (str(r["ins_code"] or "").strip() or None),
            "ambiguous": False, "reason": ""}


def _source_block() -> tuple[str, str] | None:
    if not TRAFFIC_ALLOWED:
        return (ACCOUNT_SOURCE_BLOCKED,
                "ارتباط با کارگزاری خاموش است — هیچ منبعی خوانده نمی‌شود")
    if not bool(getattr(_ACTIVE_ADAPTER, "has_token", lambda: False)()):
        return (ACCOUNT_SOURCE_BLOCKED,
                "دسترسی به حساب در حافظه نیست — اول در پنجرهٔ مرورگر وارد شوید")
    if not bool(getattr(_ACTIVE_ADAPTER, "session_proven", lambda: False)()):
        return (ACCOUNT_SOURCE_BLOCKED,
                "دسترسی هنوز با پرسش فقط‌خواندنی تأیید نشده است")
    if not isinstance(_ACTIVE_ADAPTER, EasyTraderAdapter):
        return (ACCOUNT_SOURCE_BLOCKED,
                "روش اتصال واقعی فعال نیست؛ منبع حساب در دسترس نیست")
    return None


def _resolve_instrument(symbol: str) -> InstrumentRef:
    """شناسه‌هایِ canonical از همان بانکِ محلی — بی‌حدس، بی‌ساختنِ ISIN."""
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=15)
    except sqlite3.Error:
        return InstrumentRef(symbol=symbol)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT ins_code, isin FROM instruments WHERE TRIM(l_val18) = ? "
            "ORDER BY updated_at DESC LIMIT 1", (symbol,)).fetchall()
    except sqlite3.OperationalError:
        return InstrumentRef(symbol=symbol)
    finally:
        conn.close()
    if not rows:
        return InstrumentRef(symbol=symbol)
    r = rows[0]
    isin = (r["isin"] or "").strip() or None
    return InstrumentRef(symbol=symbol, ins_code=(r["ins_code"] or "").strip() or None,
                         isin=isin,
                         resolution=Resolution.EXACT if isin else Resolution.UNRESOLVED)


def _record_dict(rec: ExecutionRecord) -> dict[str, Any]:
    d = dataclasses.asdict(rec)
    # `events` نامِ فیلدِ ردِّپایِ داخلی است (`execution_contract.py:263`)؛
    # `notes` هرگز وجود نداشت و `getattr(..., ())` بی‌صدا فهرستِ رویدادها را
    # از پاسخِ HTTP حذف می‌کرد — یعنی همان چیزی که برایِ «چرا این سفارش رد
    # شد» لازم است، درِ UI هیچ‌وقت نمی‌رسید.
    d["events"] = list(rec.events)
    return d


def _live_now() -> bool:
    """وضعیتِ *الانِ* اتصال، از خودِ آداپتور — نه ازِ یکِ ثابت.

    سه چیز لازم است: آداپتورِ درست، ترافیکِ وصل‌شده، و tokenِ مالک. نبودِ هرکدام
    یعنی `live_enabled: false` و UI همان را می‌بیند.
    """
    return bool(getattr(_ACTIVE_ADAPTER, "live", False))


def _session_dict() -> dict[str, Any]:
    """حالتِ نشست + **منشأش**. «connected» ازِ بدل با «connected» ازِ کارگزاری یکی نیست.

    `proven` فقط با یکِ پرسشِ فقط‌خواندنیِ واقعی true می‌شود؛ حضورِ رشته هرگز.
    """
    st = _ACTIVE_ADAPTER.session_status()
    return {"state": st.state.value, "account_label": st.account_label,
            "checked_at": st.checked_at,
            "origin": ADAPTER_KIND,
            "proven": bool(getattr(_ACTIVE_ADAPTER, "session_proven", lambda: False)()),
            "verified_by": dict(getattr(_ACTIVE_ADAPTER, "session_proof", {}) or {})}


# ── زمان‌بندیِ سرخطی: توقف‌پذیر، بی‌بلوکه‌کردنِ درِ halt ───────────────────────
#: دفترِ زمان‌بندی‌ها درِ حافظه است. بی‌عمد: restart نباید سفارشی را که کاربر
#: «لغو شد» نمی‌داند آتش بزند. سطرِ dispatchِ نوشته‌شده رویِ دیسک می‌ماند و
#: `_recover()` آن را درِ `open_ids` برمی‌گرداند ⇒ حالتش درِ UI معلوم است و
#: رفعِ ابهام باقی می‌مانَد؛ هیچ چیزی بی‌صدا فرستاده نمی‌شود.
_SCHEDULES: dict[str, dict[str, Any]] = {}
_SCHEDULE_LOCK = threading.Lock()


class ScheduleAborted(RuntimeError):
    """توقف پیش ازِ آتش — هیچ درخواستی ساخته نشد."""


#: هر تغییرِ token/نشست یک «دورۀ تأیید» تازه می‌سازد (§۴: «هر تغییر token یا
#: session حساس باید confirmation قبلی را باطل کند»). بی‌این، سفارشِ
#: زمان‌بندی‌شدّه پیش ازِ تعویضِ credential در صفِ حافظه می‌ماند و بعداً با
#: نشستِ *دیگری* آتش می‌زند. تأیید فقط درِ دورۀ خودش اعتبار دارد.
_CONFIRM_EPOCH = 0


def _confirm_epoch() -> int:
    with _SCHEDULE_LOCK:
        return _CONFIRM_EPOCH


def _confirm_still_valid(epoch: int) -> bool:
    with _SCHEDULE_LOCK:
        return _CONFIRM_EPOCH == int(epoch)


def _void_confirmations(reason: str) -> int:
    """دورۀ تأیید را بالا می‌برد و هر صفِ منتظرِ با تأییدِ کهنه را باطل می‌کند.

    ورودیِ بی‌`confirm_epoch` هم باطل می‌شود (fail-closed): اگر ثبتِ تأیید را
    ندیده‌ایم، حقِ آتش زدن نداریم.
    """
    global _CONFIRM_EPOCH
    with _SCHEDULE_LOCK:
        _CONFIRM_EPOCH += 1
        epoch = _CONFIRM_EPOCH
        voided = 0
        for entry in _SCHEDULES.values():
            if entry.get("state") not in ("waiting", "scheduled"):
                continue
            # مقایسهٔ مستقیم: `_SCHEDULE_LOCK` برگشت‌ناپذیر است، پس اینجا نباید
            # `_confirm_still_valid()` صدا زده شود (دقۀِ واقعیِ قفل را خودمان می‌دهیم).
            if int(entry.get("confirm_epoch", -1) or -1) != epoch:
                ev = entry.get("abort")
                if ev is not None:
                    ev.set()
                entry["state"] = "aborted"
                entry["cancelled_by"] = "confirmation voided: %s" % reason
                entry["detail"] = "تأییدِ پیشین با تغییرِ نشست باطل شد — هیچ " \
                                  "درخواستی ساخته نشد"
                voided += 1
        return voided


#: نمونه‌هایِ مدتِ هر فاز رویِ monotonic (§۵: latencyها جدا اندازه گرفته شوند و
#: p50/p95/p99 ثبت شوند). این حلقۀ در-حافظه تنها چیزی است که *واقعاً* اندازه
#: گرفته شده را نگه می‌دارد؛ بی‌نمونۀ کافی `None` می‌دهد، نه صفرِ بدل یا عددی
#: از ریلِ دیسک. ساعتِ دیواری برایِ برچسبِ زمان مصرف شده، نه برایِ مدت.
_TIMINGS = deque(maxlen=400)
_TIMING_LOCK = threading.Lock()


def _note_timing(phase: str, ms: Any) -> None:
    try:
        v = float(ms)
    except (TypeError, ValueError):
        return
    if v < 0.0:
        return
    with _TIMING_LOCK:
        _TIMINGS.append((str(phase), v))


def _timing_summary() -> dict[str, Any]:
    with _TIMING_LOCK:
        pairs = list(_TIMINGS)
    out: dict[str, Any] = {"samples": len(pairs), "clock": "monotonic",
                           "phases": {}}
    for phase in sorted({p for p, _ in pairs}):
        xs = [v for p, v in pairs if p == phase]
        out["phases"][phase] = {
            "n": len(xs),
            "p50": round(percentile(xs, 50.0), 2),
            "p95": round(percentile(xs, 95.0), 2) if len(xs) >= 2 else None,
            "p99": round(percentile(xs, 99.0), 2) if len(xs) >= 5 else None,
            "min": round(min(xs), 2), "max": round(max(xs), 2),
            "thin": len(xs) < 5}
    return out


def _abort_gate(execution_id: str) -> threading.Event:
    with _SCHEDULE_LOCK:
        entry = _SCHEDULES.get(execution_id) or {}
        ev = entry.get("abort")
        if ev is None:
            ev = threading.Event()
            entry.update({"abort": ev, "state": "waiting"})
            _SCHEDULES[execution_id] = entry
        return ev


#: قفلِ «لغو» ردیف‌به‌ردیف. دو درخواستِ هم‌زمانِ لغو رویِ یکِ سفارش نباید دو بار
#: «لغو شد» بنویسند — همان اشتباهی که درِ `delete_schedule` باِ قفلِ اتمی گرفته
#: شد (§۴-د: «هر عملِ لغو یکِ صاحب دارد»). دومی بی‌انتظار رد می‌شود، چون
#: ایستادنِ پشتِ قفلِ لغو یعنی دو اثرِ عملی از یکِ خواست.
_CANCEL_LOCKS: dict[str, threading.Lock] = {}
_CANCEL_LOCKS_GUARD = threading.Lock()


def _cancel_lock(execution_id: str) -> threading.Lock:
    with _CANCEL_LOCKS_GUARD:
        lk = _CANCEL_LOCKS.get(execution_id)
        if lk is None:
            lk = _CANCEL_LOCKS[execution_id] = threading.Lock()
        return lk


def _gate_sleep(seconds: float, ev: threading.Event) -> None:
    """خوابِ تکه‌تکه، با بازرسیِ پرچمِ توقف درِ هر تکه.

    چرا تکه‌تکه: `Scheduler` تا آستانۀِ spin یکِ خوابِ درشت می‌کند؛ اگر آن خواب
    بی‌بازگشت باشد، «توقف» تا مهلت هیچ اثری ندارد و این همان چیزی است که درِ
    پنج مخزنِ مرجع نبود (پرچمِ در-حافظه که فقط پیشِ خرید خوانده می‌شود).
    """
    remaining = float(seconds)
    while remaining > 0:
        if ev.is_set():
            raise ScheduleAborted("توقفِ دستوری پیش ازِ آتش")
        step = min(0.2, remaining)
        time.sleep(step)
        remaining -= step


def _gate_spin(ev: threading.Event) -> None:
    if ev.is_set():
        raise ScheduleAborted("توقفِ دستوری پیش ازِ آتش")
    time.sleep(0.0005)


def _scheduled_send(prepared: Any, ev: threading.Event) -> None:
    """اجرا درِ threadِ پس‌زمینه؛ قفلِ سرویس فقط دورِ خودِ dispatch گرفته می‌شود.

    ردِّپا درِ این مسیر فقط برایِ «اتفاقِ خودش» نوشته می‌شود (لغو/رد): سطرهایِ
    خودِ سرویس (dispatch/ack/error) مرجعِ وضعیت‌اند، و یکِ سطرِ بستنِ اضافه ازِ ما
    نمی‌باید سفارشِ ناشناخته را از `open_ids()` بیرون بیندازد — آن فهرست تنها
    جایی است که بعدِ restart یادمان می‌آورد این را رفعِ ابهام کنیم.
    """
    eid = prepared.draft.execution_id
    out: dict[str, Any] = {"execution_id": eid, "state": "sending"}
    try:
        if ev.is_set():
            raise ScheduleAborted("توقفِ دستوری پیش ازِ آتش")
        with _SCHEDULE_LOCK:
            armed_epoch = (_SCHEDULES.get(eid) or {}).get("confirm_epoch")
        if armed_epoch is None or _CONFIRM_EPOCH != int(armed_epoch):
            raise ScheduleAborted("تأییدِ این زمان‌بندی باطل شده (نشست/token عوض "
                                  "شد) — هیچ درخواستی ساخته نشد")
        with _LOCK:
            rec = _SERVICE.execute(prepared,
                                   sleep=lambda s: _gate_sleep(s, ev),
                                   yield_cpu=lambda: _gate_spin(ev))
        unresolved = rec.status in (ExecutionStatus.UNKNOWN_RESULT,
                                    ExecutionStatus.DISPATCHED,
                                    ExecutionStatus.ACKNOWLEDGED,
                                    ExecutionStatus.SCHEDULED,
                                    ExecutionStatus.RECONCILED)
        out.update({"state": "unknown" if rec.status is ExecutionStatus.UNKNOWN_RESULT
                    else "done",
                    "record": _record_dict(rec),
                    "still_open": unresolved})
    except ScheduleAborted as e:
        out.update({"state": "aborted", "detail": str(e)})
        _AUDIT.record(execution_id=eid, kind="schedule", status="failed",
                      error_code=ErrorCode.HALTED.value,
                      detail="aborted before fire (halt or explicit cancel) — "
                             "هیچ درخواستی ساخته نشد")
    except ExecutionError as e:
        out.update({"state": "refused", "code": e.code.value, "detail": e.detail,
                    "checks": e.checks})
        _AUDIT.record(execution_id=eid, kind="schedule", status="refused",
                      error_code=e.code.value, detail=e.detail)
    except BrokerError as e:
        # سطرِ «error» را خودِ سرویس زده؛ اینجا فقط حالتِ رابط عوض می‌شود.
        out.update({"state": "unknown" if e.is_unknown_result else "error",
                    "code": e.code.value, "detail": e.detail,
                    "unknown_result": e.is_unknown_result})
    except Exception as e:                                      # noqa: BLE001
        out.update({"state": "error", "code": ErrorCode.UNKNOWN_RESULT.value,
                    "detail": "%s: %s" % (type(e).__name__, e)})
        # هیچ چیز دیگری نوشته نشده ⇒ سطرِ ما تنها شاهدِ ماندن است و باید
        # «ناشناخته» بخوانده شود، نه بسته.
        _AUDIT.record(execution_id=eid, kind="schedule",
                      status=ExecutionStatus.UNKNOWN_RESULT.value,
                      error_code=ErrorCode.UNKNOWN_RESULT.value,
                      detail="%s: %s" % (type(e).__name__, e))
    finally:
        with _SCHEDULE_LOCK:
            entry = _SCHEDULES.get(eid) or {"abort": ev}
            entry.update(out)
            _SCHEDULES[eid] = entry
            # دفترِ زمان‌بندی درِ حافظه است (نتیجه رویِ دیسک است)؛ بی‌سقف، هر
            # سفارشِ زمان‌بندی‌شده یکِ ورودی تا ابد درِ پروسه نگه می‌داشت.
            done = [k for k, v in _SCHEDULES.items()
                    if v.get("state") not in ("waiting", "scheduled")]
            for old in done[:-40]:
                _SCHEDULES.pop(old, None)


def _schedule_status(execution_id: str) -> dict[str, Any]:
    with _SCHEDULE_LOCK:
        got = _SCHEDULES.get(execution_id)
    if not got:
        return {"execution_id": execution_id, "state": "none"}
    return {k: v for k, v in got.items() if k != "abort"}


def _halt_pending(reason: str) -> int:
    """پرچمِ توقف را به همهٔ زمان‌بندی‌هایِ درِ انتظار می‌دهد. تعدادِ لغوشده‌ها."""
    with _SCHEDULE_LOCK:                     # ادعا هم مثلِ پرچم یک‌بار نوشته می‌شود
        pending = [e for e in _SCHEDULES.values()
                   if e.get("state") in ("waiting", "scheduled") and e.get("abort")]
        for e in pending:
            e["abort"].set()
            e["state"] = "aborted"
            e["cancelled_by"] = "halt"
    return len(pending)


def _wire_preview(draft: OrderDraft) -> dict[str, Any] | None:
    """پیش‌نمایشِ *بدنۀِ واقعی* که به کارگزاری می‌رود — برایِ تأییدِ آگاهانه.

    درِ mock چیزی اینجا نیست (بدل بدنۀِ سیم ندارد) و `None` برمی‌گردد؛ UI «بی‌
    پیش‌نمایش» نشان می‌دهد نه یکِ بدنهٔ جعلی.
    """
    if ADAPTER_KIND != "easytrader":
        return None
    return easytrader_payload(draft)


def _mode_matrix(live: bool) -> dict[str, Any]:
    """وضعیتِ هر چهار حالت، از زبانِ کد، نه از ادعا (§۴).

    کاغذی و بک‌تست **هستند**، ولی درِ دیگری: `api/bot.py` ← `PaperSession` که
    سازنده‌اش `PaperBroker` را بی‌راهِ تزریق می‌سازد. چون آن دروازه هیچ‌وقت
    آداپتورِ کارگزاری نمی‌بیند، «کاغذی» نمی‌تواند «واقعی» شود — و برچسبِ «واقعی»
    درِ ربات عمداً بسته شد (کدِ BOT_LIVE_NOT_WIRED).
    """
    def _mod(name: str) -> bool:
        try:
            import importlib.util
            return importlib.util.find_spec(name) is not None
        except (ImportError, ValueError, AttributeError):
            return False

    return {
        "mock": {"implemented": True, "active": ADAPTER_KIND == "mock",
                 "door": "/api/execution/*",
                 "proves": "گردشِ منطقِ مرکزی باِ ترافیکِ بدل؛ هیچ شاهدی ازِ "
                           "کارگزاری نیست"},
        "dry_run": {"implemented": True, "active": DRY_RUN,
                    "door": "/api/execution/*",
                    "proves": "مسیرِ HTTP، گیت‌ها و ردِّپا بی‌هیچ درخواستِ بیرونی"},
        "live": {"implemented": ADAPTER_KIND == "easytrader", "active": bool(live),
                 "door": "/api/execution/*",
                 "proves": ("تنها دروازه‌ای که سوکت می‌زند؛ سیمِ سفارش هنوز "
                            "WIRE_HYPOTHESIS است و بی‌نشستِ تأییدشده آتش نمی‌زند"
                            if ADAPTER_KIND == "easytrader" else
                            "آداپتورِ واقعی انتخاب نشده (BORS_EXECUTION_ADAPTER)")},
        "paper": {"implemented": _mod("paper_trading"), "active": False,
                  "door": "/api/bot/*", "can_reach_broker": False,
                  "proves": "پرشدنِ شبیه‌سازی‌شده رویِ ردیفِ تابلو باِ سرمایهٔ "
                            "نمایشی؛ به‌هیچ‌وجه سفارشِ بازار نیست"},
        "backtest": {"implemented": _mod("backtest_engine"), "active": False,
                     "door": None, "can_reach_broker": False,
                     "proves": "موتورِ آفلاینِ سنجشِ استراتژی؛ اندپوینتِ HTTP ندارد "
                               "و درِ کنترل‌کنندۀ مرکزی نیست"},
    }

@router.get("/api/execution/status")
def get_status() -> dict[str, Any]:
    caps = _ACTIVE_ADAPTER.capabilities()
    stopped, kstate = _SERVICE.halted()
    live = _live_now()
    # «ارسالِ سفارش آزاد است» با «ترافیک وصل است» دو چیز است. درِ فقط‌خواندنی
    # ترافیک هست ولی نوشتن نه.
    writes_open = bool(getattr(_ACTIVE_ADAPTER, "writes_allowed", live))
    blocked: list[str] = []
    if ADAPTER_KIND == "mock":
        if str(_CFG.get("adapter") or "").lower() == "easytrader":
            blocked.append("تنظیمِ «easytrader» ذخیره شده ولی نشستِ جاری بدل است — "
                           "restart لازم است تا اعمال شود")
        else:
            blocked.append("آداپتورِ واقعی انتخاب نشده (تنظیمِ اتصال یا "
                           "BORS_EXECUTION_ADAPTER=easytrader)")
    if ADAPTER_KIND == "easytrader" and not LIVE_REQUESTED:
        # سنجشِ زندهٔ 2026-10-18: این متن درِ حالتِ «فقط‌خواندنی روشن، بی‌نشست» فرستادنِ
        # `BORS_EXECUTION_LIVE=1` را کمبودِ اصلی می‌گفت — یعنی همان کاری که کاربر
        # نباید بکند. چیزی که واقعاً کم است نشانیِ نشست است.
        if READ_ONLY_REQUESTED:
            if live:
                blocked.append("حالتِ فقط‌خواندنی: ترافیکِ خواندن مجاز است، ارسال نه")
            else:
                blocked.append("حالتِ فقط‌خواندنی روشن است: ترافیکِ خواندن مجاز، ارسال نه — "
                               "کمبود، نشستِ شماست (ورود درِ پنجرۀ کارگزاری، سپس نشانی به "
                               "POST /api/execution/session)")
                if _SESSION_RECOVERY.get("code") in ("MISSING", "EXPIRED", "NO_EXP",
                                                     "MALFORMED", "DENIED"):
                    blocked.append("بازیابیِ خودکارِ نشست از مخزنِ امن: %s — ورود/استخراجِ "
                                   "تازه لازم است" % _SESSION_RECOVERY.get("code"))
        else:
            blocked.append("ترافیک خاموش است — «تنظیمِ اتصال» را رویِ فقط‌خواندنی بگذارید "
                           "(یا BORS_EXECUTION_LIVE=1 برایِ ارسالِ سفارش) و restart کنید")
    if ADAPTER_KIND == "easytrader" and LIVE_REQUESTED and not live:
        blocked.append("D1: نشستِ مالک درِ حافظه نیست — ورودِ تعاملی با خودِ مالک")
    # گیتِ عبارتِ تأیید (§۲-۲): فقط وقتی که اجرایِ زنده واقعاً روشن است ازِ UI
    # چیزی می‌خواهد؛ درِ dry-run تمرین و پیش‌نمایش نباید بشکند. «required»
    # را UI می‌خواند تا بداند چه چیزی تایپ شود، نه اینکه حدس بزند.
    confirm_required = bool(not DRY_RUN and live and writes_open)
    if confirm_required:
        blocked.append("اجرایِ زنده: عبارتِ تأیید لازم است («%s»)" % _confirm_phrase())
    return {
        "status": "success",
        "adapter": ADAPTER_KIND,
        "dry_run": DRY_RUN,
        "experimental": True,
        # وضعیتِ واقعی، نه ثابت: live یعنی آداپتورِ درست + ترافیکِ وصل + tokenِ مالک.
        "live_enabled": writes_open,
        # «هیچ درخواستی به کارگزاری نمی‌رود» = ترافیک بسته است. درِ فقط‌خواندنی
        # یک GET بیرون می‌رود، پس این صادقانه false است؛ «ارسالِ سفارش» را
        # `live_enabled` جدا می‌گوید.
        "nothing_will_leave_the_machine": bool(not live),
        "live_requested": LIVE_REQUESTED,
        # سه گیتِ جدا و *بی‌وابستگی به نشانی*: «آیا فقط‌خواندنی پیکربندی شده» با
        # «آیا نشستی درِ حافظه هست» یکی نیست. `and live` این را درِ حالتِ تازه‌کانفیگ
        # false می‌کرد، و رابط را به پیامِ «ارسال لازم است» می‌انداخت (سنجشِ زنده).
        "read_only": bool(READ_ONLY_REQUESTED),
        "session_live": bool(live),
        # بازیابیِ پس از restart: فقط metadata؛ توکن هیچ‌جا درِ این پاسخ نیست.
        "session_recovery": dict(_SESSION_RECOVERY),
        "traffic_allowed": bool(TRAFFIC_ALLOWED),
        # تنظیمِ مؤثر + چه چیزی با restart عوض می‌شود. بی‌این «ذخیره شد» با
        # «اعمال شد» یکی خوانده می‌شود.
        "connection_config": {"adapter": ADAPTER_KIND,
                              "adapter_source": str(_CFG.get("source") or "default"),
                              "read_only": bool(READ_ONLY_REQUESTED),
                              "writes_gate": "env:BORS_EXECUTION_LIVE",
                              "applies_on_restart": True,
                              "secrets_stored": False},
        # سیم حتی وقتی آزموده نشده، فرضیه است؛ «آزموده‌نشده» را با «تأییدشده»
        # یکی نکن. آزمون‌شدن از mode_matrix/live می‌آید، نه از این پرچم.
        "wire_hypothesis": WIRE_HYPOTHESIS,
        # منشأِ هر مسیرِ سیم (§۳-۲): «فقط درِ کدِ شخصِ ثالث» از «پیکربندیِ
        # انتشاریافتۀِ خودِ کارگزاری» و «رفتارِ دیده‌شده» جداست. بی‌این تفکیک،
        # نامِ یکِ میدان درِ مرجع، مدرکِ قراردادِ زنده شمرده می‌شود.
        "wire_provenance": {
            "host": {"value": WIRE_BASE_URL, "kind": "first-party-config",
                     "evidence": "d.easytrader.ir/app-version.json gives apiPath"},
            "order_create": {"value": "/core/api/v2/order",
                             "kind": "third-party-code-only",
                             "official_docs": "absent (swagger/openapi = 403)",
                             "hypothesis": WIRE_HYPOTHESIS},
            "order_list": {"value": "/core/api/order",
                           "kind": "third-party-code-only",
                           "hypothesis": WIRE_HYPOTHESIS},
            "host_health": {"value": WIRE_PROBE_HOST_HEALTH,
                            "kind": "first-party-config",
                            "proves_session": False},
            "session_probe_candidates": {
                "value": list(WIRE_SESSION_PROBE_CANDIDATES),
                "kind": "observed-read-only",
                "observed": "401 + www-authenticate: Bearer",
                "body_semantics": "unverified"},
        },
        "session": _session_dict(),
        "blocked_on": blocked,
        "confirm_gate": {"required": confirm_required, "phrase": _confirm_phrase()},
        "capabilities": dataclasses.asdict(caps),
        "limits": dataclasses.asdict(_SERVICE.limits),
        "ledger_size": len(_SERVICE.ledger()),
        # حالتِ قفلِ توقف و شمارشِ ماندگار: UI باید «متوقف» را از «هیچ سفارشی
        # نبوده» جدا ببیند، نه اینکه بی‌داده را صفر بخواند.
        "kill_switch": kstate,
        "halted": stopped,
        "kill_reason": _AUDIT.kill_reason(),
        "durable_events": len(_AUDIT.events(limit=1000)),
        "recovered_after_restart": _RECOVERED,
        "audit_db": _AUDIT.db_path,
        "clock_source": _CLOCK_SOURCE,
        "clock_limit": _CLOCK_LIMIT,
        "scheduled_pending": sum(1 for e in _schedule_all()
                                 if e.get("state") in ("waiting", "scheduled")),
        # §۴: تأیید درِ دورۀِ خودش اعتبار دارد — UI و آزمون باید ببینند آن دورۀ
        # عوض شده یا نه (هر token/نشستِ تازه یک دورۀ تازه است).
        "confirm_epoch": _confirm_epoch(),
        "mode_matrix": _mode_matrix(live),
        # §۵-۶: هیچ ادعایِ «اولِ صف» نمی‌کنیم مگر دادهٔ رسمیِ رتبه باشد.
        "queue_rank": {"claims_first": False,
                       "official_rank_source": None,
                       "why": "رتبهٔ صف فقط ازِ دادهٔ رسمیِ کارگزاری خوانده می‌شود؛ "
                              "بی‌آن، رابط محدود می‌ماند به «زمانِ ارسال» و "
                              "«زمانِ پذیرش»"},
        "timings": _timing_summary(),
    }


@router.get("/api/execution/timings")
def get_timings() -> dict[str, Any]:
    """مدتِ جداگانهٔ هر فاز، رویِ monotonic، با p50/p95/p99ِ نمونه‌هایِ واقعی.

    نمونه کم باشد `p95`/`p99` `None` است (`thin: true`) — عددِ بدلِ کم‌نمونه
    منتشر نمی‌کنیم. این اندپوینت هیچ درخواستی به کارگزاری نمی‌فرستد.
    """
    return {"status": "success", "dry_run": DRY_RUN, "adapter": ADAPTER_KIND,
            **_timing_summary()}


def _schedule_all() -> list[dict[str, Any]]:
    with _SCHEDULE_LOCK:
        return [{k: v for k, v in e.items() if k != "abort"} for e in _SCHEDULES.values()]


@router.get("/api/execution/session")
def get_session() -> dict[str, Any]:
    """وضعیتِ نشست — هیچ‌وقت مقدارِ token نه. UI فقط *حالت* می‌بیند."""
    return {"status": "success", "adapter": ADAPTER_KIND, "live": _live_now(),
            "dry_run": DRY_RUN, "session": _session_dict(),
            "token_present": _has_token(),
            "session_recovery": dict(_SESSION_RECOVERY)}


def _has_token() -> bool:
    check = getattr(_ACTIVE_ADAPTER, "has_token", None)
    return bool(check()) if callable(check) else False


@router.post("/api/execution/session")
async def post_session(request: Request) -> dict[str, Any]:
    """نشست را درِ حافظه می‌گذارد. هیچ مسیرِ دیگری token نمی‌نویسد.

    چرا `Request` و نه `Body(...)`: جزئیاتِ خطایِ ۴۲۲ِ FastAPI مقدارِ ورودیِ
    بی‌شکل را درِ `input` بازمی‌گرداند — یعنی بدنه‌ای با شکلِ غلط همان token را
    درِ پاسخ و درِ هر لاگِ استثنا می‌اندازد. اینجا بدنه را خودمان می‌خوانیم و هیچ
    پیامِ خطایی مقدارِ نشانی را ندارد.

    ورودِ تعاملی کارگزاری (CAPTCHA/MFA/پیامک) درِ حیطۀِ این برنامه نیست و دور
    زده نمی‌شود؛ مالک خودش درِ مرورگر وارد می‌شود و نشانی‌ای که خودش در دسترس
    دارد را اینجا می‌گذارد. بی‌`BORS_EXECUTION_LIVE=1` این کار فقط وضعیت را
    «آماده‌به‌آزمون» می‌کند، نه متصل.
    """
    raw = await request.body()
    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else {}
    except (ValueError, UnicodeDecodeError):
        parsed = {}
    token = str(parsed.get("token") or "").strip() if isinstance(parsed, dict) else ""
    refused = {"status": "error", "code": ErrorCode.UNSUPPORTED.value,
               "session": _session_dict()}
    if ADAPTER_KIND != "easytrader":
        return {**refused, "detail": "آداپتورِ فعال token نمی‌پذیرد (adapter=%s)"
                % ADAPTER_KIND}
    if not TRAFFIC_ALLOWED or not isinstance(_ACTIVE_ADAPTER, EasyTraderAdapter):
        # نگه‌داشتنِ credential درِ حافظه برایِ مسیری که هیچ‌وقت ترافیک نمی‌زند
        # فقط سطحِ نشتی را بالا می‌برد، نه قابلیت را.
        return {**refused, "detail": "هیچ ترافیکی مجاز نیست — token ذخیره نمی‌شود. "
                "اول «تنظیمِ اتصال» را رویِ easytrader + فقط‌خواندنی بگذارید "
                "(یا BORS_EXECUTION_LIVE=1 برایِ ارسالِ سفارش) و برنامه را "
                "restart کنید"}
    if not token:
        return {"status": "error", "code": "MISSING_TOKEN", "session": _session_dict(),
                "detail": "هیچ نشانی داده نشد — نشست پاک نمانده"}
    _ACTIVE_ADAPTER.set_token(token)
    voided = _void_confirmations("token replaced")
    return {"status": "success", "live": _live_now(), "dry_run": DRY_RUN,
            "session": _session_dict(),
            "confirmations_voided": voided,
            "capabilities": dataclasses.asdict(_ACTIVE_ADAPTER.capabilities()),
            "detail": ("token فقط درِ حافظه ماند؛ با restart می‌میرد و هیچ‌جا "
                      "نوشته/لاگ نمی‌شود. تأییدِ نشست باِ «ذخیره‌شدن» یکی نیست: "
                      "POST /api/execution/connect/verify بپرسید.")}


@router.delete("/api/execution/session")
def delete_session() -> dict[str, Any]:
    if isinstance(_ACTIVE_ADAPTER, EasyTraderAdapter):
        _ACTIVE_ADAPTER.clear_token()
    voided = _void_confirmations("token cleared")
    return {"status": "success", "live": _live_now(), "session": _session_dict(),
            "confirmations_voided": voided}


# ── ۲.۵) Strategyهای چندروشی (Direct/AutoClicker/DOM/JS/Keyboard/Selenium) ──
@router.get("/api/execution/strategies")
def get_strategies() -> dict[str, Any]:
    _STRATEGY_ENGINE.live_allowed = bool(LIVE_REQUESTED and _live_now())
    st = _STRATEGY_ENGINE.status()
    st.update({"status": "success", "adapter": ADAPTER_KIND, "dry_run": DRY_RUN,
               "live_requested": LIVE_REQUESTED,
               "read_only": bool(READ_ONLY_REQUESTED),
               "traffic_allowed": bool(TRAFFIC_ALLOWED),
               "session": _session_dict(),
               "wire_hypothesis": WIRE_HYPOTHESIS})
    return st


@router.post("/api/execution/strategies/preflight")
def post_strategy_preflight_all(body: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Probeِ موازیِ فقط‌خواندنی؛ هیچ prepare/trigger/dispatch ایجاد نمی‌شود."""
    got = (body or {}).get("strategies")
    if got is not None and not isinstance(got, list):
        return {"status": "error", "code": "BAD_REQUEST",
                "detail": "strategies باید فهرست باشد"}
    ids = [str(x) for x in got] if isinstance(got, list) else None
    try:
        result = _STRATEGY_ENGINE.parallel_probe(ids)
    except Exception as e:                       # noqa: BLE001
        return {"status": "error", "code": "PREFLIGHT_FAILED",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:180])}
    return {"status": "success", "preflight": result,
            "dry_run": True, "live": False, "live_send": False}


@router.post("/api/execution/strategies/{strategy_id}/settings")
def post_strategy_settings(strategy_id: str,
                           body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        SC.spec(strategy_id)
        saved = _STRATEGY_ENGINE.settings_store.save(
            strategy_id,
            enabled=body.get("enabled") if "enabled" in body else None,
            mode=body.get("mode") if "mode" in body else None,
            priority=body.get("priority") if "priority" in body else None,
            options=body.get("options") if "options" in body else None)
    except ValueError as e:
        return {"status": "error", "code": "INVALID_SETTINGS",
                "detail": str(e)[:200]}
    return {"status": "success", "settings": saved.public()}


@router.post("/api/execution/strategies/prepare")
def post_strategy_prepare(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        draft = _draft_from(body)
    except HTTPException as e:
        return {"status": "error", "code": "BAD_DRAFT", "detail": str(e.detail)}
    sid = str(body.get("strategy") or SC.DIRECT_API)
    target = body.get("target_wall_ms")
    try:
        order = _STRATEGY_ENGINE.prepare(
            draft, sid, target_wall_ms=int(target) if target is not None else None,
            live_intent=False)
    except SE.StrategyError as e:
        return {"status": "error", "code": e.code, "detail": e.detail,
                "strategy": sid, "evidence": dict(e.evidence)}
    except Exception as e:                           # noqa: BLE001
        return {"status": "error", "code": "PREPARE_FAILED", "strategy": sid,
                "detail": "%s: %s" % (type(e).__name__, str(e)[:180])}
    _note_timing("strategy_prepare_ms", float(order.preparation_ms or 0.0))
    return {"status": "success", "strategy": sid, "prepared_id": order.prepared_id,
            "order": order.public(), "dry_run": DRY_RUN,
            "live": _live_now(),
            "wire_preview": _wire_preview(draft),
            "wire_hypothesis": WIRE_HYPOTHESIS}


@router.post("/api/execution/strategies/trigger")
def post_strategy_trigger(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """همیشه dry-run: درخواستِ سفارش در مرورگر/ترابری ساخته نمی‌شود.

    مسیرِ زنده عمداً یک درِ جدا دارد (`/strategies/dispatch`) تا یک فیلدِ
    بدنه نتواند dry-run را به ارسالِ واقعی بدل کند.
    """
    prepared_id = str(body.get("prepared_id") or "").strip()
    if not prepared_id:
        return {"status": "error", "code": "MISSING_PREPARED_ID"}
    order = _STRATEGY_ENGINE.get_order(prepared_id)
    if order is None:
        return {"status": "error", "code": "INVALID_EXECUTION_ID",
                "detail": "no such prepared order"}
    target = order.target_wall_ms
    wait_ms = (int(target) - int(time.time() * 1000)) if target else None
    if wait_ms is not None and wait_ms > IMMEDIATE_WINDOW_MS:
        def _run_dry() -> None:
            try:
                _STRATEGY_ENGINE.trigger(prepared_id, live=False)
            except Exception:
                return
        threading.Thread(target=_run_dry,
                         name="bors-strategy-dry-%s" % prepared_id[:40],
                         daemon=True).start()
        return {"status": "scheduled", "prepared_id": prepared_id,
                "send_at_wall_ms": int(target), "wait_ms": wait_ms,
                "dry_run": True, "live": False}
    try:
        result = _STRATEGY_ENGINE.trigger(prepared_id, live=False)
    except SE.StrategyError as e:
        return {"status": "error", "code": e.code, "detail": e.detail}
    except Exception as e:                           # noqa: BLE001
        return {"status": "error", "code": "TRIGGER_FAILED",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:180])}
    return {"status": "success", "result": result.public(),
            "dry_run": True, "live": False}


@router.post("/api/execution/strategies/dispatch")
def post_strategy_dispatch(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """مسیرِ زندهٔ Strategyها — فقط با env، نشست، عبارتِ تأیید و دروازهٔ ریسک.

    این در با `/trigger` یکی نیست: `/trigger` حتی وقتی live روشن است هم
    dry-run می‌ماند. ارسالِ زنده فقط از اینجا و فقط پس از تأییدِ صریح.
    """
    prepared_id = str(body.get("prepared_id") or "").strip()
    if not prepared_id:
        return {"status": "error", "code": "MISSING_PREPARED_ID"}
    ok_cf, want_cf = _confirm_gate(body)
    if not ok_cf:
        return {"status": "error",
                "code": ErrorCode.CONFIRM_PHRASE_REQUIRED.value,
                "detail": "برایِ اجرایِ زنده عبارتِ تأیید لازم است",
                "expected_phrase": want_cf}
    ok_gate, why_gate = _risk_gate()
    if not ok_gate:
        return {"status": "error", "code": ErrorCode.RISK_LIMIT.value,
                "detail": why_gate}
    if not LIVE_REQUESTED or not _live_now():
        return {"status": "error", "code": "LIVE_GATED",
                "detail": "ارسالِ زنده خاموش است (env/ترافیک/نشست)"}
    order = _STRATEGY_ENGINE.get_order(prepared_id)
    if order is None:
        return {"status": "error", "code": "INVALID_EXECUTION_ID",
                "detail": "no such prepared order"}
    confirm_epoch = _confirm_epoch()
    target = order.target_wall_ms
    wait_ms = (int(target) - int(time.time() * 1000)) if target else None

    def _run_live() -> None:
        if not _confirm_still_valid(confirm_epoch):
            return
        if not (LIVE_REQUESTED and _live_now()):
            return
        try:
            _STRATEGY_ENGINE.trigger(prepared_id, live=True, live_allowed=True)
        except Exception:
            return

    if wait_ms is not None and wait_ms > IMMEDIATE_WINDOW_MS:
        threading.Thread(target=_run_live,
                         name="bors-strategy-live-%s" % prepared_id[:40],
                         daemon=True).start()
        return {"status": "scheduled", "prepared_id": prepared_id,
                "send_at_wall_ms": int(target), "wait_ms": wait_ms,
                "dry_run": False, "live": True}
    if not _confirm_still_valid(confirm_epoch):
        return {"status": "error",
                "code": ErrorCode.CONFIRM_PHRASE_REQUIRED.value,
                "detail": "تأیید میانِ درخواست و ارسال کهنه شد — تأییدِ تازه لازم است"}
    try:
        result = _STRATEGY_ENGINE.trigger(prepared_id, live=True,
                                          live_allowed=True)
    except SE.StrategyError as e:
        return {"status": "error", "code": e.code, "detail": e.detail}
    except Exception as e:                           # noqa: BLE001
        return {"status": "error", "code": "DISPATCH_FAILED",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:180])}
    return {"status": "success", "result": result.public(),
            "dry_run": False, "live": True,
            "confirm_epoch": confirm_epoch}


@router.post("/api/execution/strategies/abort")
def post_strategy_abort(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    prepared_id = str(body.get("prepared_id") or "").strip()
    try:
        return {"status": "success",
                "order": _STRATEGY_ENGINE.abort(prepared_id)}
    except SE.StrategyError as e:
        return {"status": "error", "code": e.code, "detail": e.detail}


@router.post("/api/execution/strategies/reconcile")
def post_strategy_reconcile(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    prepared_id = str(body.get("prepared_id") or "").strip()
    try:
        return {"status": "success",
                "result": _STRATEGY_ENGINE.reconcile(prepared_id).public()}
    except SE.StrategyError as e:
        return {"status": "error", "code": e.code, "detail": e.detail}


@router.get("/api/execution/strategies/order/{prepared_id}")
def get_strategy_order(prepared_id: str) -> dict[str, Any]:
    order = _STRATEGY_ENGINE.get_order(prepared_id)
    if order is None:
        return {"status": "error", "code": "INVALID_EXECUTION_ID"}
    return {"status": "success", "order": order.public()}


@router.post("/api/execution/strategies/{strategy_id}/probe")
def post_strategy_probe(strategy_id: str) -> dict[str, Any]:
    try:
        return {"status": "success", "probe": _STRATEGY_ENGINE.probe(strategy_id)}
    except SE.StrategyError as e:
        return {"status": "error", "code": e.code, "detail": e.detail,
                "evidence": dict(e.evidence)}
    except Exception as e:                           # noqa: BLE001
        return {"status": "error", "code": "PROBE_FAILED",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:180])}


# ── ۲.۴) زمان‌بندیِ ماندگار: ذخیره، اعتبارسنجی، مسلح‌کردن، لغو ───────────────
def _schedule_error(e: SCH.ScheduleError) -> dict[str, Any]:
    return {"status": "error", "code": e.code, "detail": e.detail or e.code}


@router.get("/api/execution/schedules/readiness")
def get_schedule_readiness() -> dict[str, Any]:
    try:
        rows = _schedule_store().list(500)
    except Exception as e:                       # noqa: BLE001
        return {"status": "error", "code": "SCHEDULE_STORE_UNAVAILABLE",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:160]),
                "readiness": SCH.readiness()}
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.state] = counts.get(r.state, 0) + 1
    runner = _schedule_runner()
    return {"status": "success", "readiness": SCH.readiness(),
            "counts": counts,
            "browser_host": BH.read_status(check=True),
            "runner": {"live_enabled": runner.live_enabled,
                       "contract_verified": runner.contract_verified,
                       "last_error": runner.last_error,
                       "last_tick": runner.last_tick}}


@router.get("/api/execution/schedules/instrument")
def get_schedule_instrument(symbol: str = Query(...)) -> dict[str, Any]:
    sym = (symbol or "").strip()
    facts = SCH.local_identity_facts(DB_PATH, sym)
    if not facts.isin:
        return {"status": "error", "code": "IDENTITY_UNVERIFIED",
                "detail": "این نماد در دادهٔ محلی با ISIN پیدا نشد؛ شناسه حدس زده نمی‌شود"}
    return {"status": "success",
            "instrument": {"symbol": facts.symbol, "isin": facts.isin,
                           "full_name": facts.full_name,
                           "source": facts.identity_source}}


@router.get("/api/execution/schedules")
def get_schedules(limit: int = 100) -> dict[str, Any]:
    try:
        rows = [r.public() for r in _schedule_store().list(limit)]
    except Exception as e:                       # noqa: BLE001
        return {"status": "error", "code": "SCHEDULE_STORE_UNAVAILABLE",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:160])}
    return {"status": "success", "schedules": rows, "readiness": SCH.readiness()}


@router.post("/api/execution/schedules")
def post_schedule(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    symbol = str(body.get("symbol") or "").strip()
    if symbol != SCH.DEFAULT_SYMBOL:
        return {"status": "error", "code": "SYMBOL_NOT_SUPPORTED",
                "detail": "این نسخه فقط داروند را اعتبارسنجی می‌کند"}
    facts = SCH.local_identity_facts(DB_PATH, symbol)
    if not facts.isin:
        return {"status": "error", "code": "IDENTITY_UNVERIFIED",
                "detail": "شناسهٔ مستقل نماد در دادهٔ محلی پیدا نشد"}
    got_isin = str(body.get("isin") or "").strip().upper()
    if not got_isin or got_isin != facts.isin.upper():
        return {"status": "error", "code": "IDENTITY_MISMATCH",
                "detail": "ISIN با هویتِ محلی نماد یکی نیست",
                "expected_isin": facts.isin}
    try:
        rec = _schedule_store().create(
            symbol=symbol, isin=facts.isin, full_name=facts.full_name or "",
            side=str(body.get("side") or "").strip().lower(),
            price=body.get("price"), quantity=body.get("quantity"),
            target_ms=(int(body["target_ms"]) if body.get("target_ms") is not None else None),
            target_local=str(body.get("target_local") or ""),
            mode=str(body.get("mode") or "dry_run").strip().lower(),
            order_type=str(body.get("order_type") or "normal").strip().lower(),
            validity=str(body.get("validity") or "day").strip().lower(),
            strategy=str(body.get("strategy") or SC.PLAYWRIGHT_DOM),
            execution_id=str(body.get("execution_id") or ""),
            settings_version=int(body.get("settings_version") or 1))
    except SCH.ScheduleError as e:
        return _schedule_error(e)
    except (TypeError, ValueError) as e:
        return {"status": "error", "code": "BAD_REQUEST",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:160])}
    report = SCH.validate_darvand(rec, _schedule_facts(rec), check_target_future=True)
    rec = _schedule_store().set_validation(
        rec.id, report.to_dict(), report.ok_for_arm(rec.mode),
        "" if report.ok_for_arm(rec.mode) else "; ".join(report.blockers[:4]))
    return {"status": "success", "schedule": rec.public(),
            "validation": report.to_dict(), "readiness": SCH.readiness()}


@router.post("/api/execution/schedules/{sid}/arm")
def post_schedule_arm(sid: str) -> dict[str, Any]:
    store = _schedule_store()
    rec = store.get(sid)
    if rec is None:
        return {"status": "error", "code": "NOT_FOUND"}
    report = SCH.validate_darvand(rec, _schedule_facts(rec), check_target_future=True)
    if rec.mode == "live":
        store.set_validation(sid, report.to_dict(), False, "live not verified")
        return {"status": "error", "code": "LIVE_NOT_VERIFIED",
                "detail": "مسیر زنده تا تأیید قرارداد/نشست/مجوز فعال نمی‌شود",
                "validation": report.to_dict(), "readiness": SCH.readiness()}
    if not report.ok_for_arm(rec.mode):
        store.set_validation(sid, report.to_dict(), False,
                             "; ".join(report.blockers[:4]))
        return {"status": "error", "code": "VALIDATION_FAILED",
                "detail": "کنترل‌های حیاتیِ داروند تأیید نشد",
                "validation": report.to_dict()}
    try:
        rec = store.arm(sid, report.to_dict(), ok_for_arm=True,
                        at_ms=SCH.now_ms())
    except SCH.ScheduleError as e:
        return _schedule_error(e)
    return {"status": "success", "schedule": rec.public(),
            "validation": report.to_dict(), "readiness": SCH.readiness()}


@router.post("/api/execution/schedules/{sid}/cancel")
def post_schedule_cancel(sid: str, body: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    try:
        rec = _schedule_store().cancel(sid, str((body or {}).get("reason") or "user"))
    except SCH.ScheduleError as e:
        return _schedule_error(e)
    return {"status": "success", "schedule": rec.public()}


@router.post("/api/execution/schedules/{sid}/reset")
def post_schedule_reset(sid: str) -> dict[str, Any]:
    try:
        rec = _schedule_store().reset_to_prepared(sid, at_ms=SCH.now_ms())
    except SCH.ScheduleError as e:
        return _schedule_error(e)
    return {"status": "success", "schedule": rec.public()}


@router.get("/api/execution/schedules/{sid}")
def get_schedule(sid: str) -> dict[str, Any]:
    store = _schedule_store()
    rec = store.get(sid)
    if rec is None:
        return {"status": "error", "code": "NOT_FOUND"}
    return {"status": "success", "schedule": rec.public(),
            "events": store.events(sid), "readiness": SCH.readiness()}


# ── ۲.۴.۴) عرضه‌های اولیه: داده، بودجه، Preflight، Timing ──────────────────
def _offering_error(e: OF.OfferingsError) -> dict[str, Any]:
    return {"status": "error", "code": e.code, "detail": e.detail or e.code}


@router.get("/api/execution/offerings")
def get_offerings(limit: int = 100) -> dict[str, Any]:
    try:
        store = _offering_store()
        capital = store.capital()
        reserved = round(store.active_reserved(), 2)
        available = None
        if capital.get("total_cap") is not None:
            available = round(max(0.0, float(capital["total_cap"])
                                  - float(capital.get("cash_reserve") or 0.0)
                                  - reserved), 2)
        return {"status": "success", "offerings": [r.public() for r in store.list(limit)],
                "capital": capital, "reserved_total": reserved,
                "available": available,
                "reservations": store.reservations(), "live_send": False}
    except Exception as e:                       # noqa: BLE001
        return {"status": "error", "code": "OFFERINGS_STORE_UNAVAILABLE",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:160])}


@router.post("/api/execution/offerings")
def post_offering(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    def _ms(key: str, local_key: str) -> int | None:
        if body.get(key) is not None:
            return int(body[key])
        if body.get(local_key):
            try:
                return SCH.parse_local(str(body[local_key]))
            except SCH.ScheduleError as e:
                raise OF.OfferingsError("INVALID_TIME", e.detail) from None
        return None
    try:
        rec = _offering_store().upsert(
            symbol=str(body.get("symbol") or ""), isin=str(body.get("isin") or ""),
            method=str(body.get("method") or "UNKNOWN"),
            market=str(body.get("market") or "UNKNOWN"),
            start_ms=_ms("start_ms", "start_local"),
            end_ms=_ms("end_ms", "end_local"),
            price_min=(float(body["price_min"]) if body.get("price_min") is not None else None),
            price_max=(float(body["price_max"]) if body.get("price_max") is not None else None),
            price_source=str(body.get("price_source") or ""),
            price_step=(float(body["price_step"])
                        if body.get("price_step") is not None else None),
            min_qty=(float(body["min_qty"]) if body.get("min_qty") is not None else None),
            max_qty=(float(body["max_qty"]) if body.get("max_qty") is not None else None),
            per_code_quota=(float(body["per_code_quota"])
                            if body.get("per_code_quota") is not None else None),
            fee_rate=(float(body["fee_rate"]) if body.get("fee_rate") is not None else None),
            fee_source=str(body.get("fee_source") or ""),
            source=str(body.get("source") or ""),
            source_url=str(body.get("source_url") or ""),
            verified_at_ms=_ms("verified_at_ms", "verified_at_local"),
            data_as_of_ms=_ms("data_as_of_ms", "data_as_of_local"),
            note=str(body.get("note") or ""),
            offering_id=str(body.get("offering_id") or ""))
    except OF.OfferingsError as e:
        return _offering_error(e)
    except (TypeError, ValueError) as e:
        return {"status": "error", "code": "BAD_REQUEST",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:160])}
    return {"status": "success", "offering": rec.public()}


@router.get("/api/execution/offerings/budget")
def get_offering_budget() -> dict[str, Any]:
    store = _offering_store()
    return {"status": "success", "capital": store.capital(),
            "reserved_total": round(store.active_reserved(), 2)}


@router.post("/api/execution/offerings/budget")
def post_offering_budget(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        got = _offering_store().set_capital(
            total_cap=float(body.get("total_cap")),
            cash_reserve=float(body.get("cash_reserve") or 0.0),
            max_per_offering=float(body.get("max_per_offering")),
            priorities=(body.get("priorities") or {}))
    except OF.OfferingsError as e:
        return _offering_error(e)
    except (TypeError, ValueError) as e:
        return {"status": "error", "code": "INVALID_BUDGET",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:160])}
    return {"status": "success", "capital": got,
            "reserved_total": round(_offering_store().active_reserved(), 2)}


@router.get("/api/execution/offerings/reservations")
def get_offering_reservations(offering_id: str = "") -> dict[str, Any]:
    store = _offering_store()
    return {"status": "success", "reservations": store.reservations(offering_id or None),
            "reserved_total": round(store.active_reserved(), 2)}


@router.post("/api/execution/offerings/plan")
def post_offering_plan(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    plans = body.get("plans")
    if not isinstance(plans, list) or not plans:
        return {"status": "error", "code": "BAD_REQUEST",
                "detail": "plans باید فهرستِ غیرخالی باشد"}
    try:
        got = _offering_store().plan(plans, max_age_s=float(body.get("max_age_s") or 3600.0))
    except OF.OfferingsError as e:
        return _offering_error(e)
    except (TypeError, ValueError) as e:
        return {"status": "error", "code": "BAD_REQUEST",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:160])}
    return {"status": "success", **got, "live_send": False}


@router.post("/api/execution/offerings/timing/sample")
def post_timing_sample(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        _offering_store().record_timing(
            adapter=str(body.get("adapter") or ""),
            method=str(body.get("method") or "UNKNOWN"),
            value_ms=float(body.get("value_ms")),
            network=str(body.get("network") or "unknown"),
            phase=str(body.get("phase") or "http_rtt"),
            source=str(body.get("source") or ""),
            observed_at=(float(body["observed_at"]) if body.get("observed_at") is not None else None),
            note=str(body.get("note") or ""))
    except OF.OfferingsError as e:
        return _offering_error(e)
    except (TypeError, ValueError) as e:
        return {"status": "error", "code": "BAD_REQUEST",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:160])}
    return {"status": "success"}


@router.get("/api/execution/offerings/timing")
def get_timing(adapter: str, method: str, network: str = "",
               phase: str = "http_rtt", target_ms: int = 0,
               margin_ms: float = 0.0) -> dict[str, Any]:
    try:
        stats = _offering_store().timing_stats(adapter=adapter, method=method,
                                               network=network or None, phase=phase)
        suggestion = OF.timing_suggestion(stats, target_ms=int(target_ms or 0),
                                          method=method,
                                          margin_ms=float(margin_ms or 0.0))
    except OF.OfferingsError as e:
        return _offering_error(e)
    return {"status": "success", "stats": stats, "suggestion": suggestion,
            "live_send": False}


@router.get("/api/execution/offerings/discover")
def discover_offerings(limit: int = 20) -> dict[str, Any]:
    try:
        rows = OF.discover_codal(DB_PATH, limit=limit)
    except OF.OfferingsError as e:
        return _offering_error(e)
    return {"status": "success", "candidates": rows, "structured": False,
            "note": "متنِ CODAL تفسیر نشده؛ method/price/qty ساختگی ساخته نمی‌شود"}


@router.get("/api/execution/offerings/{oid}")
def get_offering(oid: str) -> dict[str, Any]:
    store = _offering_store()
    rec = store.get(oid)
    if rec is None:
        return {"status": "error", "code": "NOT_FOUND"}
    return {"status": "success", "offering": rec.public(),
            "capital": store.capital(),
            "reserved_total": round(store.active_reserved(), 2),
            "reservations": store.reservations(oid)}


@router.post("/api/execution/offerings/{oid}/preflight")
def post_offering_preflight(oid: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    store = _offering_store()
    rec = store.get(oid)
    if rec is None:
        return {"status": "error", "code": "NOT_FOUND"}
    try:
        rep = OF.preflight(rec, at=SCH.now_ms(),
                           price=float(body.get("price")),
                           quantity=float(body.get("quantity")),
                           max_age_s=float(body.get("max_age_s") or 3600.0),
                           capital=store.capital(),
                           reserved=store.active_reserved())
    except (TypeError, ValueError) as e:
        return {"status": "error", "code": "INVALID_ORDER",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:160])}
    return {"status": "success", "preflight": rep, "live_send": False}


@router.post("/api/execution/offerings/{oid}/reservation/{intent_id}/state")
def post_reservation_state(oid: str, intent_id: str,
                           body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        got = _offering_store().set_reservation(
            oid, intent_id, str(body.get("state") or ""),
            note=str(body.get("note") or ""))
    except OF.OfferingsError as e:
        return _offering_error(e)
    return {"status": "success", **got}


# ── ۲.۴.۵) cockpit: وضعیت، Preflight و Mock درونِ برنامه ─────────────────────
def _db_meta(path: str) -> dict[str, Any]:
    meta: dict[str, Any] = {"path": path, "readable": False, "mtime_ms": None,
                            "mtime_iso": None}
    try:
        meta["mtime_ms"] = int(os.path.getmtime(path) * 1000)
        meta["mtime_iso"] = time.strftime("%Y-%m-%dT%H:%M:%S",
                                          time.localtime(meta["mtime_ms"] / 1000.0))
    except OSError:
        pass
    try:
        con = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"),
                              uri=True, timeout=2)
        try:
            con.execute("SELECT 1").fetchone()
            meta["readable"] = True
        finally:
            con.close()
    except Exception:                            # noqa: BLE001
        pass
    return meta


def _cockpit_context() -> dict[str, Any]:
    store = _offering_store()
    sched = _schedule_store()
    offers = [r.public() for r in store.list(200)]
    capital = store.capital()
    reservations = store.reservations()
    execution = get_status()
    host = BH.read_status(check=True)
    db = {"market": _db_meta(DB_PATH), "offerings": _db_meta(store.path),
          "schedules": _db_meta(sched.path),
          "cockpit": _db_meta(_cockpit_store().path)}
    reserved = store.active_reserved()
    status = CK.build_status(
        app_version=str(APP_VERSION), offerings=offers, capital=capital,
        reserved=reserved, reservations=reservations,
        readiness=SCH.readiness(), host=host, execution=execution, db=db)
    return {"offers": offers, "capital": capital, "reserved": reserved,
            "reservations": reservations, "execution": execution, "host": host,
            "db": db, "status": status}


@router.get("/api/execution/cockpit/status")
def get_cockpit_status() -> dict[str, Any]:
    try:
        got = _cockpit_context()
        return {"status": "success", **got["status"], "live_send": False}
    except Exception as e:                       # noqa: BLE001
        return {"status": "error", "code": "COCKPIT_STATUS_UNAVAILABLE",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:200])}


@router.get("/api/execution/cockpit/runs")
def get_cockpit_runs(limit: int = 30, run_id: str = "") -> dict[str, Any]:
    try:
        store = _cockpit_store()
        runs = store.runs(limit)
        selected = run_id or (runs[0]["id"] if runs else "")
        events = store.events(selected) if selected else []
        return {"status": "success", "mode": "MOCK", "runs": runs,
                "selected_run": selected, "events": events,
                "scenarios": list(CK.SCENARIO_INFO), "live_send": False}
    except CK.CockpitError as e:
        return {"status": "error", "code": e.code, "detail": e.detail}
    except Exception as e:                       # noqa: BLE001
        return {"status": "error", "code": "COCKPIT_STORE_UNAVAILABLE",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:200])}


@router.get("/api/execution/cockpit/runs/{run_id}")
def get_cockpit_run(run_id: str) -> dict[str, Any]:
    try:
        got = _cockpit_store().run(run_id)
    except Exception as e:                       # noqa: BLE001
        return {"status": "error", "code": "COCKPIT_STORE_UNAVAILABLE",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:200])}
    if got is None:
        return {"status": "error", "code": "RUN_NOT_FOUND"}
    return {"status": "success", "run": got, "live_send": False}


@router.post("/api/execution/cockpit/runs")
def post_cockpit_run(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    scenario = str(body.get("scenario") or "")
    try:
        context = _cockpit_context()
    except Exception as e:                       # noqa: BLE001
        return {"status": "error", "code": "COCKPIT_CONTEXT_UNAVAILABLE",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:200])}
    offers = context["offers"]
    offering = None
    oid = str(body.get("offering_id") or "")
    if oid:
        offering = next((o for o in offers if str(o.get("id")) == oid), None)
    if scenario == "unverified_offering":
        offering = next((o for o in offers if str(o.get("status")) != "VERIFIED"), offering)
    try:
        got = CK.start_scenario(_cockpit_store(), scenario, offering=offering,
                                price=body.get("price"), quantity=body.get("quantity"))
    except CK.CockpitError as e:
        return {"status": "error", "code": e.code, "detail": e.detail}
    except Exception as e:                       # noqa: BLE001
        return {"status": "error", "code": "COCKPIT_RUN_FAILED",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:200])}
    return {"status": "success", "mode": "MOCK", "run": got,
            "live_send": False, "acceptance_time_observed": False}


@router.post("/api/execution/cockpit/runs/{run_id}/stop")
def stop_cockpit_run(run_id: str) -> dict[str, Any]:
    try:
        got = _cockpit_store().stop(run_id)
    except CK.CockpitError as e:
        return {"status": "error", "code": e.code, "detail": e.detail}
    return {"status": "success", "run_id": run_id, "run_status": got.get("status"),
            "unchanged": bool(got.get("unchanged")), "live_send": False}


@router.post("/api/execution/cockpit/preflight")
def post_cockpit_preflight(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        context = _cockpit_context()
    except Exception as e:                       # noqa: BLE001
        return {"status": "error", "code": "COCKPIT_CONTEXT_UNAVAILABLE",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:200])}
    oid = str(body.get("offering_id") or "")
    offering = next((o for o in context["offers"] if str(o.get("id")) == oid), None)
    try:
        price = float(body["price"]) if body.get("price") not in (None, "") else None
        qty = float(body["quantity"]) if body.get("quantity") not in (None, "") else None
        max_age = float(body.get("max_age_s") or 3600.0)
    except (TypeError, ValueError):
        return {"status": "error", "code": "INVALID_ORDER",
                "detail": "قیمت/تعداد/پنجرهٔ تازگی نامعتبر است"}
    return CK.preflight_snapshot(offering=offering, price=price, quantity=qty,
                                 status=context["status"], max_age_s=max_age,
                                 capital=context["capital"], reserved=context["reserved"])


@router.get("/api/execution/cockpit/report")
def get_cockpit_report(run_id: str = "") -> dict[str, Any]:
    try:
        context = _cockpit_context()
        store = _cockpit_store()
        runs = store.runs(30)
        selected = run_id or (runs[0]["id"] if runs else "")
        events = store.events(selected) if selected else []
        return CK.build_report(status=context["status"], runs=runs, events=events)
    except Exception as e:                       # noqa: BLE001
        return {"status": "error", "code": "COCKPIT_REPORT_UNAVAILABLE",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:200])}


# ── ۲.۴.۶) browser session host (نشستِ پایدارِ مالک؛ CDPِ محلی) ───────────────
def _host_status() -> dict[str, Any]:
    return BH.read_status(check=True)


@router.get("/api/execution/browser-host")
def get_browser_host() -> dict[str, Any]:
    got = _host_status()
    return {"status": "success", "host": got,
            "live_requires_host": True,
            "note": "ورود دستی در پنجرهٔ host؛ هیچ token/cookie ذخیره نمی‌شود"}


@router.post("/api/execution/browser-host")
def post_browser_host() -> dict[str, Any]:
    got = BH.read_status(check=True)
    if got.get("healthy"):
        os.environ["BORS_EXECUTION_CDP_URL"] = str(got.get("cdp_url") or "")
        return {"status": "success", "host": got, "started": False}
    if bool(getattr(sys, "frozen", False)):
        cmd = [sys.executable, "--browser-host"]
        cwd = os.path.dirname(sys.executable)
    else:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cmd = [sys.executable, os.path.join(root, "execution_browser_host.py")]
        cwd = root
    flags = 0
    if os.name == "nt":
        flags = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                 | getattr(subprocess, "DETACHED_PROCESS", 0))
    try:
        subprocess.Popen(cmd, cwd=cwd, env=dict(os.environ),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=flags)
    except Exception as e:                       # noqa: BLE001
        return {"status": "error", "code": "HOST_START_FAILED",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:160])}
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        got = BH.read_status(check=True)
        if got.get("healthy"):
            os.environ["BORS_EXECUTION_CDP_URL"] = str(got.get("cdp_url") or "")
            return {"status": "success", "host": got, "started": True}
        time.sleep(0.25)
    got = BH.read_status(check=True)
    return {"status": "error", "code": "HOST_NOT_READY", "host": got,
            "detail": "پنجرهٔ host در ۳۰ ثانیه آماده نشد؛ مرورگر/پروفایل را بررسی کنید"}


@router.delete("/api/execution/browser-host")
def delete_browser_host() -> dict[str, Any]:
    got = BH.stop_host()
    if got.get("status") == "closed":
        os.environ.pop("BORS_EXECUTION_CDP_URL", None)
    return {"status": "success" if got.get("status") == "closed" else "error",
            "host": got}


# ── ۲.۵) تنظیمِ اتصال و پرتفویِ فقط‌خواندنی ─────────────────────────────────
@router.get("/api/execution/config")
def get_config() -> dict[str, Any]:
    """تنظیمِ اتصال (هیچ مقدارِ محرمانه‌ای نیست) + آنچه **همین حالا** مؤثر است.

    دو چیز جدا نگه داشته می‌شوند: «ذخیره شد» و «اعمال شد». آداپتور و نوعِ
    ترافیک درِ `import` خوانده می‌شوند، پس تا restart پاسخِ همین نشست عوض
    نمی‌شود — بی‌این تفکیک، کاربر «ذخیره» را «متصل» می‌خواند.
    """
    cfg = _settings_snapshot()
    return {"status": "success",
            "stored": {"adapter": str(cfg.get("adapter") or ""),
                       "read_only": bool(cfg.get("read_only")),
                       "source": str(cfg.get("source") or "default"),
                       "updated_at": cfg.get("updated_at")},
            "effective": {"adapter": ADAPTER_KIND,
                          "traffic_allowed": bool(TRAFFIC_ALLOWED),
                          "read_only": bool(READ_ONLY_REQUESTED),
                          "live_requested": bool(LIVE_REQUESTED),
                          "session_live": bool(_live_now()),
                          "writes_gate": "env:BORS_EXECUTION_LIVE"},
            "applies_on_restart": True,
            "secrets_stored": False,
            "detail": "token/رمز/کوکی هیچ‌جا درِ این تنظیم نمی‌نشیند؛ نشانیِ نشست "
                      "فقط باِ POST /api/execution/session درِ حافظه می‌آید و با "
                      "restart می‌میرد"}


@router.post("/api/execution/config")
async def post_config(request: Request) -> dict[str, Any]:
    """انتخابِ آداپتور و حالتِ فقط‌خواندنی. نوشتنِ سفارش از این مسیر باز نمی‌شود."""
    raw = await request.body()
    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else {}
    except (ValueError, UnicodeDecodeError):
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    wanted = {k: v for k, v in parsed.items() if k in ("adapter", "read_only")}
    unknown = [k for k in parsed if k not in ("adapter", "read_only")]
    if unknown:
        return {"status": "error", "code": "UNKNOWN_KEY",
                "detail": "کلیدهایِ مجاز فقط adapter و read_only هستند: "
                          + ", ".join(sorted(unknown)),
                "config": get_config()}
    if not wanted:
        return {"status": "error", "code": "EMPTY_CONFIG",
                "detail": "هیچ تنظیمی داده نشد", "config": get_config()}
    import execution_settings as ES
    try:
        for k, v in wanted.items():
            cfg = ES.set_value(k, v)
    except ValueError as e:
        return {"status": "error", "code": "BAD_VALUE", "detail": str(e),
                "config": get_config()}
    except Exception as e:                        # noqa: BLE001 - بانک/دیسک
        return {"status": "error", "code": "STORE_FAILED",
                "detail": "نوشتنِ تنظیم ممکن نشد: %s" % type(e).__name__,
                "config": get_config()}
    _AUDIT.record(execution_id="-", kind="config", status="stored",
                  detail="adapter=%s read_only=%s (env مقدم است)"
                         % (cfg.get("adapter"), bool(cfg.get("read_only"))))
    out = get_config()
    out["applied_now"] = bool(str(cfg.get("adapter") or "") == ADAPTER_KIND)
    return out


@router.get("/api/execution/portfolio")
def get_portfolio() -> dict[str, Any]:
    """دارایی‌هایِ پرتفوی از گزارشِ عملکردِ وب‌اپِ رسمی؛ فقط‌خواندنی.

    تعداد/آزاد/قابل‌فروش در این منبع نیست: آن سه فیلد صریحاً غایب گزارش
    می‌شوند و با صفر یا برآورد پر نمی‌شوند. قدرتِ خرید منبعِ جدا دارد.
    """
    fetched_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    base: dict[str, Any] = {
        "status": "blocked", "adapter": ADAPTER_KIND, "live": bool(_live_now()),
        "session_proven": bool(getattr(_ACTIVE_ADAPTER, "session_proven", lambda: False)()),
        "state": ACCOUNT_SOURCE_BLOCKED, "as_of": None, "source": "none",
        "rows": None, "positions": [], "cached_at": None, "fetched_at": None,
        "raw_count": 0, "resolved_count": 0, "unresolved_count": 0,
        "duplicate_count": 0, "unresolved": [], "missing_fields": [],
        "buying_power": None, "error": None,
    }
    block = _source_block()
    if block:
        base["state"], base["error"] = block
        return base
    if not hasattr(_ACTIVE_ADAPTER, "get_portfolio_performance"):
        base.update({"status": "no_source", "state": PORTFOLIO_UNAVAILABLE,
                     "error": "این روش اتصال منبع پرتفوی ندارد"})
        return base
    try:
        raw_rows = _ACTIVE_ADAPTER.get_portfolio_performance()
    except Exception as e:                        # noqa: BLE001
        base.update({"status": "error", "state": PORTFOLIO_UNAVAILABLE,
                     "error": "%s: %s" % (type(e).__name__, str(e)[:160])})
        return base
    if not isinstance(raw_rows, list):
        base.update({"status": "error", "state": PORTFOLIO_UNAVAILABLE,
                     "error": "پاسخ پرتفوی فهرست نبود"})
        return base
    missing = ["quantity", "free_quantity", "sellable_quantity"]
    rows: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_count = 0
    for it in raw_rows:
        if not isinstance(it, Mapping):
            continue
        isin = str(it.get("symbolIsin") or "").strip()
        if isin in seen:
            duplicate_count += 1
        seen.add(isin)
        mapped = _instrument_by_isin(isin)
        row = {
            "isin": isin, "symbol": mapped.get("symbol"),
            "ins_code": mapped.get("ins_code"), "resolved": mapped.get("resolved"),
            "ambiguous": mapped.get("ambiguous"), "mapping_error": mapped.get("reason"),
            "broker_name": it.get("symbolName"),
            "asset": it.get("asset"),
            "avg_buy": it.get("totalBuyAveragePrice"),
            "periodic_avg_buy": it.get("periodicBuyAveragePrice"),
            "realized_pnl": it.get("totalRealizedProfitAndLoss"),
            "realized_pnl_without_dps": it.get("totalRealizedProfitAndLossWithoutDps"),
            "date": it.get("date"), "persian_date": it.get("persianDate"),
            "source": "portfolio", "missing_fields": missing,
        }
        rows.append(row)
        if not mapped.get("resolved"):
            unresolved.append({"isin": isin, "reason": mapped.get("reason"),
                               "ambiguous": mapped.get("ambiguous")})
    state = PORTFOLIO_PARTIALLY_VERIFIED if rows else PORTFOLIO_VERIFIED
    bp: dict[str, Any] = {"state": BUYING_POWER_UNAVAILABLE, "error": ""}
    if hasattr(_ACTIVE_ADAPTER, "get_money"):
        try:
            m = _ACTIVE_ADAPTER.get_money()
            bp = {"state": BUYING_POWER_VERIFIED, "value": m.get("buying_power"),
                  "raw": m.get("raw"), "unit": m.get("unit"),
                  "formula": m.get("formula"), "source": m.get("source"),
                  "fetched_at": m.get("fetched_at")}
        except Exception as e:                    # noqa: BLE001
            bp = {"state": BUYING_POWER_UNAVAILABLE,
                  "error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    resolved_count = sum(1 for r in rows if r.get("resolved"))
    base.update({
        "status": "success", "state": state,
        "source": "easytrader:/assetmodule/api/performance (first-party web app)",
        "rows": rows, "positions": rows, "as_of": fetched_at,
        "fetched_at": fetched_at, "raw_count": len(raw_rows),
        "resolved_count": resolved_count,
        "unresolved_count": len(unresolved), "duplicate_count": duplicate_count,
        "unresolved": unresolved, "missing_fields": missing,
        "buying_power": bp, "error": None,
    })
    return base


@router.get("/api/execution/watchlist")
def get_easytrader_watchlist() -> dict[str, Any]:
    """دیده‌بانِ شخصیِ EasyTrader؛ هرگز با دیده‌بانِ محلیِ بازار یکی نمی‌شود."""
    fetched_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    base: dict[str, Any] = {
        "status": "blocked", "adapter": ADAPTER_KIND, "live": bool(_live_now()),
        "session_proven": bool(getattr(_ACTIVE_ADAPTER, "session_proven", lambda: False)()),
        "state": ACCOUNT_SOURCE_BLOCKED, "source": "none", "fetched_at": None,
        "categories": [], "rows": [], "raw_count": 0, "resolved_count": 0,
        "unresolved_count": 0, "duplicate_count": 0, "unresolved": [], "error": None,
    }
    block = _source_block()
    if block:
        base["state"], base["error"] = block
        return base
    if not hasattr(_ACTIVE_ADAPTER, "get_watchlist"):
        base.update({"status": "no_source", "state": WATCHLIST_UNAVAILABLE,
                     "error": "این روش اتصال دیده‌بان ندارد"})
        return base
    try:
        raw_categories = _ACTIVE_ADAPTER.get_watchlist()
    except Exception as e:                        # noqa: BLE001
        base.update({"status": "error", "state": WATCHLIST_UNAVAILABLE,
                     "error": "%s: %s" % (type(e).__name__, str(e)[:160])})
        return base
    if not isinstance(raw_categories, list):
        base.update({"status": "error", "state": WATCHLIST_UNAVAILABLE,
                     "error": "پاسخ دیده‌بان فهرست نبود"})
        return base
    categories: list[dict[str, Any]] = []
    flat: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_count = 0
    raw_count = 0
    for cat in raw_categories:
        if not isinstance(cat, Mapping):
            continue
        cat_id = str(cat.get("id") or "")
        cat_name = str(cat.get("name") or "")
        cat_rows: list[dict[str, Any]] = []
        for isin in (cat.get("isins") or []):
            isin = str(isin or "").strip()
            if not isin:
                continue
            raw_count += 1
            if isin in seen:
                duplicate_count += 1
            seen.add(isin)
            mapped = _instrument_by_isin(isin)
            row = {"isin": isin, "symbol": mapped.get("symbol"),
                   "ins_code": mapped.get("ins_code"),
                   "resolved": mapped.get("resolved"),
                   "ambiguous": mapped.get("ambiguous"),
                   "mapping_error": mapped.get("reason"),
                   "category_id": cat_id, "category_name": cat_name,
                   "source": "watchlist"}
            cat_rows.append(row)
            flat.append(row)
            if not mapped.get("resolved"):
                unresolved.append({"isin": isin, "reason": mapped.get("reason"),
                                   "ambiguous": mapped.get("ambiguous"),
                                   "category_id": cat_id})
        categories.append({"id": cat_id, "name": cat_name,
                           "order": cat.get("order"),
                           "is_default": bool(cat.get("is_default")),
                           "created_at": cat.get("created_at"),
                           "count": len(cat_rows), "symbols": cat_rows})
    resolved_count = sum(1 for r in flat if r.get("resolved"))
    base.update({
        "status": "success", "state": WATCHLIST_VERIFIED,
        "source": "easytrader:/easy/api/MarketWatch (first-party web app)",
        "fetched_at": fetched_at, "categories": categories, "rows": flat,
        "raw_count": raw_count, "resolved_count": resolved_count,
        "unresolved_count": len(unresolved), "duplicate_count": duplicate_count,
        "unresolved": unresolved, "empty": not bool(flat), "error": None,
    })
    return base


@router.get("/api/execution/readiness")
def get_readiness(symbol: str = "", side: str = "buy",
                  price: float | None = None,
                  quantity: float | None = None) -> dict[str, Any]:
    """دروازهٔ متمرکز: داده/ریسک از نوشتن جدا؛ live_ready فقط با همهٔ شروط.

    این در فقط‌خواندنی است؛ برایِ سنجشِ داده ممکن است یک GET قدرت خرید بزند.
    هیچ سفارشی نمی‌سازد و «live_ready=true» را از هیچ ورودیِ UI نمی‌پذیرد.
    """
    sym = (symbol or "").strip()
    symbol_ready: bool | None = None
    checks: dict[str, str] | None = None
    if sym:
        try:
            ref = _draft_from({"symbol": sym}).instrument
            symbol_ready = ref.orderable()[0]
        except HTTPException:
            symbol_ready = False
        if price is not None and quantity is not None:
            try:
                draft = _draft_from({"symbol": sym, "side": side,
                                     "price": price, "quantity": quantity,
                                     "execution_id": "readiness-" + uuid.uuid4().hex[:10],
                                     "price_source": "readiness"})
                checks = dict(_SERVICE.preflight(draft).checks)
            except (HTTPException, ExecutionError, ValueError, TypeError):
                checks = None
    try:
        bp = get_buying_power()
    except Exception:                             # noqa: BLE001 - منبعِ بیرونی
        bp = None
    rep = RD.build_readiness(
        session_proven=bool(getattr(_ACTIVE_ADAPTER, "session_proven",
                                    lambda: False)()),
        read_only=bool(READ_ONLY_REQUESTED),
        buying_power=bp,
        symbol_ready=symbol_ready,
        preflight_checks=checks,
        contract_operational=False,
        owner_approved=False,
        lifecycle_tests=None,
        full_gate=None,
    )
    rep.update({"adapter": ADAPTER_KIND, "symbol": sym or None,
                "side": side, "price": price, "quantity": quantity})
    return rep


@router.get("/api/execution/buying-power")
def get_buying_power() -> dict[str, Any]:
    """قدرتِ خریدِ خواندنی؛ واحد ریال و فرمول از خودِ وب‌اپِ رسمی سنجیده شد."""
    base: dict[str, Any] = {
        "status": "blocked", "adapter": ADAPTER_KIND, "live": bool(_live_now()),
        "session_proven": bool(getattr(_ACTIVE_ADAPTER, "session_proven", lambda: False)()),
        "state": ACCOUNT_SOURCE_BLOCKED, "source": "none", "unit": "IRR",
        "value": None, "raw": None, "formula": None, "fetched_at": None,
        "order_write_state": ORDER_WRITE_UNVERIFIED, "error": None,
    }
    block = _source_block()
    if block:
        base["state"], base["error"] = block
        return base
    if not hasattr(_ACTIVE_ADAPTER, "get_money"):
        base.update({"status": "no_source", "state": BUYING_POWER_UNAVAILABLE,
                     "error": "این روش اتصال قدرت خرید ندارد"})
        return base
    try:
        money = _ACTIVE_ADAPTER.get_money()
    except Exception as e:                        # noqa: BLE001
        base.update({"status": "error", "state": BUYING_POWER_UNAVAILABLE,
                     "error": "%s: %s" % (type(e).__name__, str(e)[:160])})
        return base
    base.update({
        "status": "success", "state": BUYING_POWER_VERIFIED,
        "source": money.get("source"), "unit": money.get("unit"),
        "value": money.get("buying_power"), "raw": money.get("raw"),
        "formula": money.get("formula"), "fetched_at": money.get("fetched_at"),
        "error": None,
    })
    return base



# ── ۳) اتصالِ کاربر: پنجرۀ مرورگری و داوریِ حالتِ نشست ──────────────────────
# لایه درِ `execution_connect.py` است. سه چیز عمداً اینجا *نیست*: هیچ نشانیِ
# حدسی برایِ صفحۀ ورود، هیچ ذخیره‌ای ازِ رمز/کوکی/توکن رویِ دیسک، و هیچ
# «متصل شد» که ازِ HTMLِ صفحه آمده باشد.
_CONNECT_LAST: dict[str, Any] = {}


@router.get("/api/execution/connect")
def get_connect() -> dict[str, Any]:
    return EXC.status_dict(_ACTIVE_ADAPTER, _CONNECT_LAST)


@router.post("/api/execution/connect/browser")
async def post_connect_browser(request: Request) -> dict[str, Any]:
    raw = await request.body()
    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else {}
    except (ValueError, UnicodeDecodeError):
        parsed = {}
    url = str(parsed.get("url") or "").strip() if isinstance(parsed, dict) else ""
    if not url:
        hosts = EXC.login_hosts()
        if not hosts:
            return {"status": "error", "code": "NO_LOGIN_HOST",
                    "detail": "هیچ دامنه‌ای برایِ ورودِ کاربر تأیید نشده — "
                              "BORS_EXECUTION_CONNECT_HOSTS را بگذارید",
                    "connect": EXC.status_dict(_ACTIVE_ADAPTER, _CONNECT_LAST)}
        url = "https://%s/" % hosts[0]
    h, why = EXC.open_login_window(url)
    if h is None:
        return {"status": "error", "code": "BROWSER_REFUSED", "detail": why,
                "connect": EXC.status_dict(_ACTIVE_ADAPTER, _CONNECT_LAST)}
    return {"status": "success", "opened": why != "already-open",
            "note": why, "connect": EXC.status_dict(_ACTIVE_ADAPTER, _CONNECT_LAST)}


@router.delete("/api/execution/connect/browser")
def delete_connect_browser() -> dict[str, Any]:
    _ok, note = EXC.close_login_window()
    return {"status": "success", "note": note,
            "connect": EXC.status_dict(_ACTIVE_ADAPTER, _CONNECT_LAST)}


@router.get("/api/execution/connection/diagnose")
def get_connection_diagnose() -> dict[str, Any]:
    """تشخیصِ مرحله‌به‌مرحله؛ فقط host/CDP/status محلی را می‌خواند."""
    try:
        got = ECONN.diagnose(
            app_version=str(APP_VERSION), host=BH.read_status(check=True),
            execution=get_status(), portfolio=get_portfolio())
    except Exception as e:                       # noqa: BLE001
        return {"status": "error", "code": "CONNECTION_DIAGNOSE_FAILED",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:200])}
    return {"status": "success", **got}


@router.post("/api/execution/connection/verify")
def post_connection_verify() -> dict[str, Any]:
    return get_connection_diagnose()


def _same_origin(origin: str, host_header: str) -> bool:
    try:
        o = urlparse(origin)
        h = urlparse("//" + str(host_header or ""))
    except ValueError:
        return False
    loopback = ("127.0.0.1", "localhost", "::1")
    return (o.hostname in loopback and h.hostname in loopback
            and (o.port or 80) == (h.port or 80))


@router.post("/api/execution/connection/capture-session")
def post_connection_capture_session(request: Request) -> dict[str, Any]:
    """نشستِ OIDC را از مرورگرِ مدیریت‌شده فقط در حافظه می‌گذارد.

    این در هیچ سفارشی نمی‌فرستد و مقدارِ نشست را نه برمی‌گرداند، نه ذخیره
    می‌کند و نه لاگ. فقط از همان originِ محلیِ خودِ برنامه پذیرفته می‌شود.
    """
    origin = request.headers.get("origin") or ""
    if origin and not _same_origin(origin, request.headers.get("host") or ""):
        return {"status": "error", "code": "CROSS_ORIGIN_BLOCKED",
                "detail": "این در فقط از خودِ رابطِ محلی پذیرفته می‌شود",
                "secrets_returned": False, "secrets_stored": False}
    if ADAPTER_KIND != "easytrader":
        return {"status": "error", "code": "ADAPTER_NOT_EASYTRADER",
                "detail": "آداپتورِ واقعی فعال نیست؛ ابتدا EasyTrader + فقط‌خواندنی را ذخیره و restart کنید",
                "secrets_returned": False, "secrets_stored": False}
    if not TRAFFIC_ALLOWED:
        return {"status": "error", "code": "TRAFFIC_OFF",
                "detail": "هیچ ترافیکی مجاز نیست؛ نشست در حافظه نگه داشته نمی‌شود",
                "secrets_returned": False, "secrets_stored": False}
    got = BH.read_status(check=True)
    if not got.get("healthy"):
        return {"status": "error", "code": "HOST_DOWN",
                "detail": "پنجرهٔ host باز/سالم نیست",
                "secrets_returned": False, "secrets_stored": False}
    try:
        import execution_session_capture as ESC
        token, meta = ESC.capture_from_host(str(got.get("cdp_url") or ""))
    except Exception as e:                       # noqa: BLE001
        return {"status": "error", "code": str(getattr(e, "code", "CAPTURE_FAILED")),
                "detail": str(getattr(e, "detail", "") or
                              "خواندنِ نشست از مرورگر ممکن نشد")[:200],
                "secrets_returned": False, "secrets_stored": False}
    try:
        _ACTIVE_ADAPTER.set_token(token)
    except Exception as e:                       # noqa: BLE001
        return {"status": "error", "code": "TOKEN_SET_FAILED",
                "detail": "آداپتور توکن را نپذیرفت (%s)" % type(e).__name__,
                "secrets_returned": False, "secrets_stored": False}
    finally:
        token = ""
    return {"status": "success", "code": "CAPTURED", "token_present": True,
            "page_host": meta.get("page_host"), "token_type": meta.get("token_type"),
            "expires_at": meta.get("expires_at"), "scope": meta.get("scope"),
            "has_refresh_token": bool(meta.get("has_refresh_token")),
            "secrets_returned": False, "secrets_stored": False,
            "detail": "نشست از مرورگر خوانده و فقط در حافظهٔ پروسه گذاشته شد؛ "
                      "حالا «بررسی وضعیت» را بزنید."}


@router.get("/api/execution/connection/report")
def get_connection_report() -> dict[str, Any]:
    got = get_connection_diagnose()
    if got.get("status") != "success":
        return got
    return ECONN.report(diagnosis=got)


@router.post("/api/execution/connect/verify")
def post_connect_verify() -> dict[str, Any]:
    global _CONNECT_LAST
    _CONNECT_LAST = EXC.verify(_ACTIVE_ADAPTER)
    # اگر پرسیدنیِ واقعی نشست را تأیید نکرد، هیچ تأییدِ سفارشی از پیش نباید
    # بماند: «متصل نبودن» و «تأییدِ معتبر» با هم زنده نمی‌مانند (§۴).
    if str(_CONNECT_LAST.get("state") or "").strip().lower() != \
            EXC.STATE_CONNECTED.lower():
        _void_confirmations("verify: session not proven")
    return {"status": "success", "verify": _CONNECT_LAST,
            "connect": EXC.status_dict(_ACTIVE_ADAPTER, _CONNECT_LAST)}


@router.delete("/api/execution/connect")
def delete_connect() -> dict[str, Any]:
    EXC.close_login_window()
    if isinstance(_ACTIVE_ADAPTER, EasyTraderAdapter):
        _ACTIVE_ADAPTER.clear_token()
    _CONNECT_LAST = {}
    _void_confirmations("connect reset")
    return {"status": "success", "detail": "نشستِ حافظه‌ای و پنجره بسته شد",
            "connect": EXC.status_dict(_ACTIVE_ADAPTER, _CONNECT_LAST)}


@router.post("/api/execution/probe")
def post_probe() -> dict[str, Any]:
    """آزمونِ اتصالِ کم‌خطر: فقط پرسیدنی‌هایِ خواندنی، صفرِ سفارش.

    درِ `/order` هرگز برایِ سنجشِ سرعت یا «آیا وصلیم» زده نمی‌شود؛ مرجع‌ها همین
    کار را می‌کردند (مخزن ۲ با سفارشِ واقعی) و ما ردش کردیم.
    """
    probe = getattr(_ACTIVE_ADAPTER, "probe", None)
    if probe is None:
        return {"status": "error", "code": ErrorCode.UNSUPPORTED.value,
                "detail": "این adapter آزمونِ اتصال ندارد (adapter=%s)" % ADAPTER_KIND,
                "read_only": True, "order_endpoint_touched": False}
    with _LOCK:
        got = probe()
    return {"status": "success" if got.get("ok") else "error", **got}


@router.post("/api/execution/preflight")
def post_preflight(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    t0 = time.monotonic()
    draft = _draft_from(body)
    p = _SERVICE.preflight(draft)
    _note_timing("preflight_ms", (time.monotonic() - t0) * 1000.0)
    return {"status": "success", "adapter": ADAPTER_KIND, "dry_run": DRY_RUN,
            "live": _live_now(), "execution_id": draft.execution_id,
            "instrument": dataclasses.asdict(draft.instrument),
            "checks": p.checks, "reasons": p.reasons, "ok": p.ok,
            "unknown": list(p.unknown)}


@router.post("/api/execution/prepare")
def post_prepare(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    t0 = time.monotonic()
    draft = _draft_from(body)
    try:
        with _LOCK:
            prepared = _SERVICE.prepare(
                draft,
                target_wall_ms=body.get("target_wall_ms"),
                one_way_ms=float(body.get("one_way_ms") or 0.0),
                margin_ms=float(body.get("margin_ms") or 0.0),
                confirmed=bool(body.get("confirmed")))
    except ExecutionError as e:
        return {"status": "error", "code": e.code.value, "detail": e.detail,
                "checks": e.checks, "execution_id": draft.execution_id}
    _note_timing("prepare_ms", (time.monotonic() - t0) * 1000.0)
    return {"status": "success", "execution_id": draft.execution_id,
            "mode": prepared.mode.value, "dry_run": prepared.dry_run,
            "sendable": prepared.sendable,
            "checks": prepared.preflight.checks,
            "plan": dataclasses.asdict(prepared.plan) if prepared.plan else None,
            "payload_preview": prepared.payload_preview,
            # بدنهٔ واقعیِ سیم — چیزی که اگر اتصال وصل باشد می‌رود. ثابتِ
            # `WIRE_HYPOTHESIS` درِ `/status` می‌گوید این هنوز فرضیه است.
            "wire_preview": _wire_preview(draft),
            "wire_hypothesis": (ADAPTER_KIND == "easytrader") and WIRE_HYPOTHESIS,
            "timings": {"prepared_ms": round((time.monotonic() - t0) * 1000, 1),
                        "dispatch_ms": None, "response_ms": None,
                        "observed_ms": None}}


@router.post("/api/execution/dispatch")
def post_dispatch(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    t0 = time.monotonic()
    ok_cf, want_cf = _confirm_gate(body if isinstance(body, dict) else {})
    if not ok_cf:
        return {"status": "error",
                "code": ErrorCode.CONFIRM_PHRASE_REQUIRED.value,
                "detail": "برایِ اجرایِ زنده عبارتِ تأیید لازم است، نه فقطِ یکِ "
                          "true — همان چیزی که رویِ دکمه می‌بینید را تایپ کنید",
                "expected_phrase": want_cf,
                "execution_id": str(body.get("execution_id") or ""),
                "confirm_gate": "phrase_required", "dry_run": DRY_RUN,
                "live": _live_now()}
    ok_gate, why_gate = _risk_gate()
    if not ok_gate:
        return {"status": "error", "code": ErrorCode.RISK_LIMIT.value,
                "detail": why_gate, "execution_id": str(body.get("execution_id") or ""),
                "risk_gate": "not_configured", "dry_run": DRY_RUN, "live": _live_now()}
    #: دورۀِ تأیید *پس از*ِ گذشتنِ دو گیت خوانده می‌شود تا اگر نشست همین حالا
    #: عوض شد، همین درخواست با تأییدِ کهنه رأی نگیرد.
    confirm_epoch = _confirm_epoch()
    draft = _draft_from(body)
    target = body.get("target_wall_ms")
    try:
        with _LOCK:
            prepared = _SERVICE.prepare(
                draft,
                target_wall_ms=target,
                one_way_ms=float(body.get("one_way_ms") or 0.0),
                margin_ms=float(body.get("margin_ms") or 0.0),
                confirmed=bool(body.get("confirmed")))
    except ExecutionError as e:
        return {"status": "error", "code": e.code.value, "detail": e.detail,
                "checks": e.checks, "execution_id": draft.execution_id}

    wait_ms = None
    if prepared.plan is not None:
        wait_ms = prepared.plan.send_at_wall_ms - int(time.time() * 1000)
    if wait_ms is not None and wait_ms > IMMEDIATE_WINDOW_MS:
        # زمان‌بندی‌شده: درِ همان درخواست نمی‌خوابیم، چون «توقف» باید همان لحظه
        # پاسخ‌گو باشد. نتیجه را UI ازِ /schedule و /ledger می‌خواند.
        ev = _abort_gate(draft.execution_id)
        with _SCHEDULE_LOCK:
            if _CONFIRM_EPOCH != confirm_epoch:
                stale = True
            else:
                stale = False
                entry = _SCHEDULES[draft.execution_id]
                entry.update({"state": "scheduled", "confirm_epoch": confirm_epoch,
                              "send_at_wall_ms":
                              prepared.plan.send_at_wall_ms, "target_wall_ms":
                              prepared.plan.target_wall_ms})
        if stale:
            ev.set()
            return {"status": "error",
                    "code": ErrorCode.CONFIRM_PHRASE_REQUIRED.value,
                    "detail": "بینِ تأییدِ شما و این لحظه نشست/token عوض شد — "
                              "زمان‌بندی ثبت نشد و تأییدِ تازه لازم است",
                    "execution_id": draft.execution_id,
                    "confirm_gate": "stale_confirmation", "dry_run": DRY_RUN,
                    "live": _live_now()}
        threading.Thread(target=_scheduled_send, args=(prepared, ev),
                         name="bors-schedule-%s" % draft.execution_id,
                         daemon=True).start()
        return {"status": "scheduled", "adapter": ADAPTER_KIND, "dry_run": DRY_RUN,
                "kill_switch": _AUDIT.kill_state(),
                "execution_id": draft.execution_id,
                "send_at_wall_ms": prepared.plan.send_at_wall_ms,
                "wait_ms": wait_ms,
                "payload_preview": prepared.payload_preview,
                "timings": {"prepared_ms": round((time.monotonic() - t0) * 1000, 1),
                            "dispatch_ms": None, "response_ms": None,
                            "observed_ms": None}}

    if not _confirm_still_valid(confirm_epoch):
        return {"status": "error",
                "code": ErrorCode.CONFIRM_PHRASE_REQUIRED.value,
                "detail": "بینِ تأییدِ شما و این لحظه نشست/token عوض شد — ارسال "
                          "نشد و تأییدِ تازه لازم است",
                "execution_id": draft.execution_id,
                "confirm_gate": "stale_confirmation", "dry_run": DRY_RUN,
                "live": _live_now()}
    try:
        with _LOCK:
            rec = _SERVICE.execute(prepared)
    except ExecutionError as e:
        return {"status": "error", "code": e.code.value, "detail": e.detail,
                "checks": e.checks, "execution_id": draft.execution_id}
    except BrokerError as e:
        return {"status": "error", "code": e.code.value, "detail": e.detail,
                "unknown_result": e.is_unknown_result,
                "execution_id": draft.execution_id}
    dispatch_ms = round((time.monotonic() - t0) * 1000, 1)
    _note_timing("dispatch_ms", dispatch_ms)
    if getattr(rec, "rtt_ms", None) is not None:
        _note_timing("response_ms", rec.rtt_ms)
    return {"status": "success", "adapter": ADAPTER_KIND, "dry_run": DRY_RUN,
            "live": _live_now(),
            "kill_switch": _AUDIT.kill_state(),
            "record": _record_dict(rec),
            "timings": {"prepared_ms": None, "dispatch_ms": dispatch_ms,
                        "response_ms": rec.rtt_ms,
                        # «مشاهدهٔ سفارش» با «پذیرش» یکی نیست (§۴-ج): تا
                        # reconcile/queue آن را اندازه نگیرد، None است.
                        "observed_ms": None}}


@router.get("/api/execution/schedule/{execution_id}")
def get_schedule(execution_id: str) -> dict[str, Any]:
    return {"status": "success", **_schedule_status(execution_id)}


@router.delete("/api/execution/schedule/{execution_id}")
def delete_schedule(execution_id: str) -> dict[str, Any]:
    """لغوِ یکِ زمان‌بندی پیش ازِ آتش. پس ازِ POST هیچ‌چیز لغو نمی‌شود و این
     «لغو شد» را ادعا نمی‌کند."""
    # خواندنِ حالت و گذاشتنِ پرچم *یکِ کارِ اتمی* است. بی‌این، دو درخواستِ
    # هم‌زمانِ «لغو» هر دو حالتِ waiting را دیدند و هر دو «لغو شد» برگرداندند؛
    # اثرِ عملی یکی بود اما ادعا دو بار نوشته می‌شد — و ادعایِ دوتایی درِ
    # لغوِ سفارش همان چیزی است که بعداً تعیینِ تکلیف را گمراه می‌کند.
    with _SCHEDULE_LOCK:
        entry = _SCHEDULES.get(execution_id)
        if not entry:
            raise HTTPException(404, "no such schedule: %s" % execution_id)
        ev = entry.get("abort")
        state = entry.get("state")
        mine = False
        if state in ("waiting", "scheduled") and ev is not None:
            ev.set()
            entry["state"] = "aborted"
            entry["cancelled_by"] = "explicit cancel"
            mine = True
    if mine:
        return {"status": "success", "execution_id": execution_id,
                "aborted": True, "note": "پیش ازِ آتش لغو شد"}
    return {"status": "success", "execution_id": execution_id, "aborted": False,
            "state": state,
            "note": "زمان‌بندی دیگر درِ انتظار نیست — وضعیت از /ledger خوانده می‌شود"}


@router.post("/api/execution/reconcile/{execution_id}")
def post_reconcile(execution_id: str) -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        with _LOCK:
            rec = _SERVICE.reconcile(execution_id)
    except ExecutionError as e:
        raise HTTPException(404, f"{e.code.value}: {e.detail}") from None
    _note_timing("reconcile_ms", (time.monotonic() - t0) * 1000.0)
    return {"status": "success", "record": _record_dict(rec)}


@router.post("/api/execution/refresh/{execution_id}")
def post_refresh(execution_id: str) -> dict[str, Any]:
    """نظرِ تازهٔ سرور دربارهٔ سفارشِ *موجود*. هیچ ارسالی نمی‌سازد."""
    t0 = time.monotonic()
    try:
        with _LOCK:
            rec = _SERVICE.refresh(execution_id)
    except ExecutionError as e:
        raise HTTPException(404, f"{e.code.value}: {e.detail}") from None
    return {"status": "success", "record": _record_dict(rec),
            "observed_ms": round((time.monotonic() - t0) * 1000, 1)}


@router.get("/api/execution/queue/{execution_id}")
def get_queue(execution_id: str) -> dict[str, Any]:
    try:
        v = _SERVICE.queue(execution_id)
    except ExecutionError as e:
        raise HTTPException(404, f"{e.code.value}: {e.detail}") from None
    return {"status": "success", "execution_id": v.execution_id,
            "supported": v.supported, "known": v.known, "reason": v.reason,
            "terminal": v.terminal,
            "snapshot": dataclasses.asdict(v.snapshot) if v.snapshot else None}


@router.post("/api/execution/cancel/{execution_id}")
def post_cancel(execution_id: str, body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """لغوِ سفارشی که به کارگزاری رفته — باِ تأییدِ صریح و باِ قفلِ ردیف‌به‌ردیف.

    بی‌`confirm=true` هیچ درخواستی نمی‌رود (همان قاعدۀ `/resume`: «دکمه زده شد»
    مجوزِ عملِ حساس نیست). تواناییِ لغو ازِ `capabilities` خودِ آداپتور خوانده
    می‌شود؛ درِ EasyTrader صریح `false` است، پس این در «لغو نشد» را باِ دلیل
    برمی‌گرداند و هیچ سوکتی نمی‌زند.
    """
    caps = _ACTIVE_ADAPTER.capabilities()
    if body.get("confirm") is not True:
        return {"status": "refused", "code": ErrorCode.CONFIRM_PHRASE_REQUIRED.value,
                "detail": "لغو یک عملِ حساس است — صریحاً `confirm: true` لازم است",
                "execution_id": execution_id, "confirm_gate": "explicit_confirm_required",
                "cancel_supported": caps.cancel, "dry_run": DRY_RUN, "live": _live_now()}
    lk = _cancel_lock(execution_id)
    if not lk.acquire(blocking=False):
        return {"status": "refused", "code": ErrorCode.DUPLICATE_GUARD.value,
                "detail": "یکِ درخواستِ لغو همین حالا رویِ این سفارش در جریان است",
                "execution_id": execution_id, "in_flight": True,
                "cancel_supported": caps.cancel, "dry_run": DRY_RUN, "live": _live_now()}
    t0 = time.monotonic()
    try:
        with _LOCK:
            rec = _SERVICE.cancel(execution_id, reason=str(body.get("reason") or "کاربر"))
    except ExecutionError as e:
        _note_timing("cancel_ms", (time.monotonic() - t0) * 1000.0)
        return {"status": "error", "code": e.code.value, "detail": e.detail,
                "execution_id": execution_id, "cancel_supported": caps.cancel,
                "unknown_result": e.code in UNRESOLVED_CODES,
                "dry_run": DRY_RUN, "live": _live_now()}
    finally:
        lk.release()
    _note_timing("cancel_ms", (time.monotonic() - t0) * 1000.0)
    state = rec.order_state.value
    confirmed = state == OrderState.CANCELLED.value
    return {"status": "success", "execution_id": execution_id,
            "order_state": state, "cancel_accepted": True,
            "cancelled_confirmed": confirmed,
            "note": ("لغو تأیید شد — بازخوانیِ وضعیت همان را نشان داد" if confirmed
                     else "لغو پذیرفته شد ولی بازخوانی تأییدش نکرد — «تأییدِ لغو» "
                          "ادعا نمی‌شود"),
            "record": _record_dict(rec), "dry_run": DRY_RUN, "live": _live_now()}


@router.get("/api/execution/ledger")
def get_ledger() -> dict[str, Any]:
    return {"status": "success", "adapter": ADAPTER_KIND, "dry_run": DRY_RUN,
            "live": _live_now(),
            "kill_switch": _AUDIT.kill_state(),
            # سفارش‌هایی که هنوز بسته نشده‌اند و باید بعدِ restart دیده/تطبیق شوند
            "open_ids": _AUDIT.open_ids(),
            "scheduled": _schedule_all(),
            "records": [_record_dict(r) for r in _SERVICE.ledger()]}


@router.get("/api/execution/limits")
def get_limits() -> dict[str, Any]:
    return {"status": "success", "limits": dataclasses.asdict(_SERVICE.limits),
            "codes": [c.value for c in ErrorCode]}


@router.post("/api/execution/halt")
def post_halt(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """قفلِ توقفِ اضطراری: از همین لحظه هیچ سفارشِ تازه‌ای ساخته نمی‌شود.

    رویِ دیسک می‌نشیند، نه درِ حافظه — چون «متوقفم» نباید با یک restart پاک
    شود و برنامه دوباره با حالتِ «آماده» بالا بیاید (بندِ ۶-۴). زمان‌بندی‌هایِ
    درِ انتظار هم همین‌جا لغو می‌شوند: توقفی که فقط جلویِ «بعدی‌ها» را بگیرد و
    آن یکی که درِ صفِ خواب است را رها کند، توقف نیست.
    """
    reason = str(body.get("reason") or "دستوری")
    state = TRIPPED if body.get("auto") is True else HALT
    # عمداً بی‌`_LOCK`: قفلِ سرویس ممکن است موقعِ یکِ POSTِ ۷ ثانیه‌ای گرفته شده
    # باشد و «توقف» نباید پشتِ آن بایستد. خودِ ledger قفلِ رشته‌ایِ دارد.
    _AUDIT.set_kill(state, reason, actor=str(body.get("actor") or "user"))
    aborted = _halt_pending(reason)
    durable_review = 0
    try:
        if _SCHEDULE_STORE is not None:
            durable_review = _SCHEDULE_STORE.set_kill(reason)
    except Exception:                       # noqa: BLE001 - halt نباید بشکند
        durable_review = 0
    return {"status": "success", "kill_switch": _AUDIT.kill_state(),
            "halted": _AUDIT.halted(), "reason": reason,
            "aborted_schedules": aborted,
            "durable_schedules_needs_review": durable_review,
            "dry_run": DRY_RUN, "adapter": ADAPTER_KIND}


@router.post("/api/execution/resume")
def post_resume(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """بازکردنِ قفل. صریح و با ردِّپا — بی‌این هیچ مسیری «خاموش» را «آماده» نمی‌کند.

    حالتِ `TRIPPED` (خودکار: ضرر روزانه، دادهٔ کهنه) بی‌`confirm=True` باز نمی‌شود:
    توقفی که موتورِ ریسک انداخته باید دستِ انسان لازم باشد، نه یک درخواستِ GET.
    """
    state = _AUDIT.kill_state()
    if state == TRIPPED and body.get("confirm") is not True:
        return {"status": "error", "code": "HALTED",
                "detail": "توقفِ خودکارِ ریسک بی‌confirm=True باز نمی‌شود",
                "kill_switch": state}
    reason = str(body.get("reason") or "ادامهٔ دستوری")
    _AUDIT.set_kill(ARMED, reason, actor=str(body.get("actor") or "user"))
    return {"status": "success", "kill_switch": _AUDIT.kill_state(),
            "halted": _AUDIT.halted(), "reason": reason,
            "open_ids": _AUDIT.open_ids()}


@router.get("/api/execution/audit/{execution_id}")
def get_audit(execution_id: str) -> dict[str, Any]:
    """ردِّپایِ کاملِ یکِ سفارش، از کهنه به تازه — بی‌secret (redact رویِ دیسک)."""
    ev = _AUDIT.trail(execution_id)
    return {"status": "success", "execution_id": execution_id,
            "found": bool(ev), "events": ev,
            "latest": ev[-1] if ev else None}


def _when_to_epoch(value: str) -> float | None:
    """`epoch`ِ ثانیه یا `YYYY-MM-DD` (همان روز، ساعتِ محلی) — بی‌حدسِ منطقه‌ای."""
    v = (value or "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(v, fmt).timestamp()
        except ValueError:
            continue
    return None


@router.get("/api/execution/events")
def get_events(execution_id: str = Query(""), symbol: str = Query(""),
               status: str = Query(""), order_state: str = Query(""),
               kind: str = Query(""), since: str = Query(""), until: str = Query(""),
               limit: int = Query(200)) -> dict[str, Any]:
    """سابقۀِ رخدادها، فقط‌خواندنی و بی‌راز — فیلترها همه رویِ ستون‌هایِ ردِّپا.

    `payload` درِ این فهرست نمی‌آید (ردِّپایِ کاملِ یکِ سفارش ازِ `/audit/{id}`
    خوانده می‌شود) و `detail` از همان `redact`ِ خودِ قراردادِ اجرا می‌گذرد، پس
    اگر روزی رشته‌ای ازِ کارگزاری اینجا بنشیند، نامِ کلیدِ حساس ردِّپا را
    نمی‌شکند.
    """
    kinds = [k.strip() for k in kind.split(",") if k.strip()] or None
    since_e, until_e = _when_to_epoch(since), _when_to_epoch(until)
    bad = [name for name, raw, parsed in (("since", since, since_e), ("until", until, until_e))
           if raw.strip() and parsed is None]
    if bad:
        return {"status": "error", "code": "INVALID_FILTER",
                "detail": "قالبِ تاریخ نامعتبر: %s (مثالِ درست 2026-10-17)" % "، ".join(bad)}
    rows = _AUDIT.events(execution_id=(execution_id.strip() or None),
                         symbol=(symbol.strip() or None),
                         status=(status.strip() or None),
                         order_state=(order_state.strip() or None),
                         kinds=kinds, since_epoch=since_e, until_epoch=until_e,
                         limit=max(1, min(int(limit or 200), 500)))
    out = []
    for r in rows:
        r = dict(r)
        r.pop("payload", None)
        if r.get("detail"):
            r["detail"] = redact(str(r["detail"]))
        out.append(r)
    return {"status": "success", "adapter": ADAPTER_KIND, "dry_run": DRY_RUN,
            "count": len(out), "events": out,
            "filters": {"execution_id": execution_id or None, "symbol": symbol or None,
                        "status": status or None, "order_state": order_state or None,
                        "kind": kinds, "since": since_e, "until": until_e},
            "note": "فقطِ ردِّپایِ ماندگارِ خودِ برنامه؛ هیچ داده‌ای ازِ کارگزاری "
                    "اینجا ساخته نمی‌شود"}
