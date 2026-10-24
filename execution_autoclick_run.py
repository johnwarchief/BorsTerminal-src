# -*- coding: utf-8 -*-
"""execution_autoclick_run.py — اجرایِ زمان‌بندی‌شدهٔ چنداقدامیِ AutoClicker.

چرا این لایه جدا از شمارندۀ فرانت است: «تعداد کلیک» و «فاصله» باید درِ لایه‌ای
نگه‌داری و اجرا شوند که lifecycle و سقف‌ها را کنترل می‌کند. شمارندۀ frontend با
بسته‌شدن پنل، رفرش، یا قطعِ مرورگر می‌میرد؛ اینجا نمی‌میرد.

قفل‌هایِ طراحی (بند ۶ و ۹ مأموریت):

  ۱) هر اقدام یک ردیفِ مستقل است با زمانِ برنامه‌ریزی‌شده، زمانِ واقعی، شاهد و
     نتیجه. «تکرار کلیک» با retry عادی یکی نیست؛ هر کلیکِ موفق می‌تواند یک
     سفارشِ تازه بسازد، پس سقفِ تعداد درِ همین‌جا سخت‌گیرانه است.
  ۲) ادعایِ claim با `UPDATE ... WHERE claimed_at_ms IS NULL` یک‌برنده است؛
     دو زمان‌بند هم‌زمان، یک اقدام را دو بار اجرا نمی‌کنند.
  ۳) restart هیچ اقدامی را خودکار اجرا نمی‌کند: اجرایِ نیمه‌تمام به
     `NEEDS_REVIEW` می‌رود و باید دوباره بررسی/تأیید شود.
  ۴) نتیجهٔ UNKNOWN ادامه نمی‌دهد. دکمهٔ مبهم‌بودن، قطعِ مرورگر، تغییرِ نماد،
     نامطابقتِ قیمت/تعداد، و ردِ محدودیت همه «توقف»اند، نه «تلاشِ دوباره».
  ۵) توقفِ اضطراری به شبکه وابسته نیست: یک Eventِ محلی + لغوِ ردیف‌هایِ مانده.
  ۶) دقتِ میلی‌ثانیه‌ای: آخرینِ فاصله با spinِ کوتاهِ monotonic بسته می‌شود؛
     pollingِ صرف، خودِ منبعِ تأخیر است.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Optional

from execution_rate_limiter import OrderRateLimiter
from execution_ui_state import UIOptions

TIMEZONE_NAME = "Asia/Tehran"
#: ایران از ۱۴۰۱ تغییرِ ساعتِ تابستانی ندارد؛ پس fallback ثابت، ادعا نیست.
FIXED_TEHRAN = timezone(timedelta(hours=3, minutes=30), "Asia/Tehran")

#: سقفِ مطلقِ تعدادِ اقدام در هر اجرا — حتی اگر کاربر عددِ بزرگ‌تری بخواهد.
#: این عددِ ایمنیِ خودِ برنامه است، نه قانونِ کارگزاری.
HARD_MAX_ACTIONS = 20
#: کفِ فاصله (ms) = ۳۰۰؛ این کفِ مقرراتی است (تعهدنامۀ برخط + کد OMS 13021)،
#: نه انتخابِ داخلی. با قاعدۀ official_min_spacing در rate limiter یکی است.
MIN_INTERVAL_MS = 300.0
#: اگر زمانِ هدف بیشتر از این مقدار گذشته باشد و هیچ اقدامی نرفته باشد، اجرا
#: «از دست رفته» است و بی‌مهرهٔ catch-up متوقف می‌شود.
DEFAULT_MISSED_GRACE_MS = 2000
#: spinِ پایانی برایِ کاهشِ خطایِ زمان‌بندی (ms). pollingِ خالص ~۱۰ms خطا داشت.
DEFAULT_SPIN_MS = 12.0

# ── وضعیت‌هایِ اجرا ──────────────────────────────────────────────────────────
DRAFT = "DRAFT"
VALIDATED = "VALIDATED"
ARMED = "ARMED"
WARMING = "WARMING"
RUNNING = "RUNNING"
COMPLETED = "COMPLETED"
STOPPED = "STOPPED"
CANCELLED = "CANCELLED"
NEEDS_REVIEW = "NEEDS_REVIEW"
MISSED_TARGET = "MISSED_TARGET"
EXPIRED = "EXPIRED"
BLOCKED = "BLOCKED"

RUN_STATES = (DRAFT, VALIDATED, ARMED, WARMING, RUNNING, COMPLETED, STOPPED,
              CANCELLED, NEEDS_REVIEW, MISSED_TARGET, EXPIRED, BLOCKED)
#: وضعیتی که بعدِ restart باید بازبینی شود و هرگز خودکار ادامه ندهد.
RECOVER_TO_REVIEW = (ARMED, WARMING, RUNNING)

# ── وضعیت‌هایِ یک اقدام ─────────────────────────────────────────────────────
A_PENDING = "PENDING"
A_CLAIMED = "CLAIMED"
A_FIRED = "FIRED"
A_DONE = "DONE"
A_BLOCKED = "BLOCKED"
A_SKIPPED = "SKIPPED"
A_CANCELLED = "CANCELLED"
#: نتیجه‌هایِ پایانیِ اقدام که اجازهٔ ادامه نمی‌دهند.
TERMINAL_NO_RETRY = ("UNKNOWN", "BLOCKED", "AMBIGUOUS")


class RunError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = str(code)
        self.detail = str(detail or code)[:300]
        super().__init__(self.detail or self.code)


def tehran_tz() -> tuple[Any, str]:
    """ZoneInfo در دسترس باشد همان، وگرنه ثابتِ +03:30 با منبعِ صریح."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(TIMEZONE_NAME), "zoneinfo:Asia/Tehran"
    except Exception:                                       # noqa: BLE001
        return FIXED_TEHRAN, "fixed+03:30 (no tzdata on this machine)"


def parse_tehran_wall(text: str) -> int:
    """«۲۰۲۶-۱۰-۲۴T۰۹:۰۰:۰۰» محلیِ تهران → epoch ms. بی‌منطقه یعنی تهران."""
    raw = str(text or "").strip()
    if not raw:
        raise RunError("INVALID_TARGET", "زمانِ هدف خالی است")
    raw = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
                                      "01234567890123456789"))
    tz, _src = tehran_tz()
    try:
        got = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise RunError("INVALID_TARGET", "قالبِ زمانِ هدف نامعتبر است: %s" % raw[:40]) from None
    if got.tzinfo is None:
        got = got.replace(tzinfo=tz)
    return int(got.timestamp() * 1000.0)


def format_tehran(ms: int) -> Optional[str]:
    """epoch ms → ISO تهران. مقدارِ بی‌محتوا None می‌شود، نه انحرافِ درخواستِ API."""
    try:
        tz, _src = tehran_tz()
        return datetime.fromtimestamp(int(ms) / 1000.0, tz).isoformat(
            timespec="milliseconds")
    except (OSError, OverflowError, ValueError, TypeError):
        return None


# ── پیکربندیِ اجرا ──────────────────────────────────────────────────────────
@dataclass
class RunConfig:
    """همه‌چیز از پنل می‌آید؛ هیچ تعداد یا فاصله‌ای درِ کد ثابت نیست."""
    run_id: str = ""
    symbol: str = ""
    isin: str = ""
    side: str = "buy"
    expected_price: Optional[float] = None
    expected_quantity: Optional[float] = None
    #: رشتهٔ زمانِ محلیِ تهران؛ تبدیلش صریح و قابلِ تست است.
    target_at: str = ""
    mode: str = "single"                 # single | repeat
    total_actions: int = 1
    interval_ms: float = 1000.0
    account: str = "easytrader"
    dry_run: bool = True
    live_confirmed: bool = False
    confirm_phrase: str = ""
    #: ارزیابیِ پیش‌از‌هدف (resolve + fingerprint) تا در لحظه فقط چک‌هایِ تازه بماند.
    prewarm_ms: int = 1500
    spin_ms: float = DEFAULT_SPIN_MS
    missed_grace_ms: int = DEFAULT_MISSED_GRACE_MS
    ui: dict[str, Any] = field(default_factory=dict)
    note: str = ""

    def planned_first_at_ms(self) -> int:
        return parse_tehran_wall(self.target_at)

    def planned_action_at_ms(self, idx: int) -> int:
        """زمانِ برنامه‌ریزی‌شدۀ اقدامِ idxام: اولی + i*فاصله."""
        return int(self.planned_first_at_ms() + (max(0, int(idx)) * self.interval_ms))

    def planned_last_at_ms(self) -> int:
        return self.planned_action_at_ms(self.total_actions - 1)

    def normalized(self) -> "RunConfig":
        """اعتبارسنجیِ سخت در ورودی؛ هیچ مقدارِ پنهان یا بی‌سقفی ساخته نمی‌شود."""
        side = str(self.side or "").strip().lower()
        if side not in ("buy", "sell"):
            raise RunError("INVALID_SIDE", "سمتِ سفارش فقط خرید یا فروش است")
        mode = str(self.mode or "single").strip().lower()
        if mode not in ("single", "repeat"):
            raise RunError("INVALID_MODE", "حالت فقط تک‌اقدام یا تکرارِ محدود است")
        want = 1 if mode == "single" else int(self.total_actions or 1)
        if want < 1:
            raise RunError("INVALID_ACTION_COUNT", "تعدادِ اقدام باید ۱ یا بیشتر باشد")
        if want > HARD_MAX_ACTIONS:
            raise RunError("ACTION_COUNT_ABOVE_CEILING",
                           "سقفِ ایمنیِ برنامه %d اقدام است؛ درخواستِ %d رد شد"
                           % (HARD_MAX_ACTIONS, want))
        interval = float(self.interval_ms or 0.0)
        if mode == "repeat" and interval < MIN_INTERVAL_MS:
            raise RunError("INTERVAL_BELOW_FLOOR",
                           "کمینۀ فاصله %dms است (سقفِ ایمنیِ خودِ برنامه، نه عددِ "
                           "کارگزاری)" % int(MIN_INTERVAL_MS))
        price = self.expected_price
        qty = self.expected_quantity
        if price is None or float(price) <= 0:
            raise RunError("INVALID_PRICE", "قیمتِ موردِ انتظار لازم است")
        if qty is None or float(qty) <= 0 or abs(float(qty) - round(float(qty))) > 1e-9:
            raise RunError("INVALID_QUANTITY", "تعدادِ موردِ انتظار باید عددِ صحیحِ مثبت باشد")
        if not str(self.symbol or "").strip():
            raise RunError("INVALID_SYMBOL", "نماد لازم است")
        try:
            self.planned_first_at_ms()
        except RunError:
            raise
        if mode == "single":
            interval = 0.0
        return RunConfig(**{**asdict(self), "side": side, "mode": mode,
                            "total_actions": want, "interval_ms": interval,
                            "expected_price": float(price),
                            "expected_quantity": float(round(float(qty))),
                            "prewarm_ms": max(0, int(self.prewarm_ms or 0)),
                            "spin_ms": max(0.0, min(float(self.spin_ms or 0.0), 50.0)),
                            "missed_grace_ms": max(0, int(self.missed_grace_ms or 0))})

    def ui_options(self) -> UIOptions:
        u = dict(self.ui or {})
        return UIOptions(
            submit_selector=str(u.get("submit_selector") or ""),
            price_selector=str(u.get("price_selector") or ""),
            quantity_selector=str(u.get("quantity_selector") or ""),
            symbol_selector=str(u.get("symbol_selector") or ""),
            isin_selector=str(u.get("isin_selector") or ""),
            side_selector=str(u.get("side_selector") or ""),
            form_scope_selector=str(u.get("form_scope_selector") or ""),
            side=self.side,
            expected_price=self.expected_price,
            expected_quantity=self.expected_quantity,
            expected_symbol=self.symbol,
            expected_isin=self.isin)

    def preview(self) -> dict[str, Any]:
        """خلاصه‌ای که کاربر پیش از اجرا می‌بیند: حداکثرِ سفارش/سهم/ارزش."""
        gross = round(float(self.expected_price or 0.0) *
                      float(self.expected_quantity or 0.0) *
                      int(self.total_actions or 0), 2)
        total_shares = round(float(self.expected_quantity or 0.0) *
                             int(self.total_actions or 0), 2)
        return {
            "symbol": self.symbol, "isin": self.isin, "side": self.side,
            "expected_price": self.expected_price,
            "expected_quantity": self.expected_quantity,
            "mode": self.mode, "total_actions": int(self.total_actions),
            "interval_ms": float(self.interval_ms),
            "timezone": TIMEZONE_NAME,
            "target_at_local": self.target_at,
            "planned_first_at_ms": self.planned_first_at_ms(),
            "planned_first_at_local": format_tehran(self.planned_first_at_ms()),
            "planned_last_at_ms": self.planned_last_at_ms(),
            "planned_last_at_local": format_tehran(self.planned_last_at_ms()),
            "max_orders_possible": int(self.total_actions),
            "total_shares_possible": total_shares,
            "max_gross_value_rial": gross,
            "dry_run": bool(self.dry_run),
            "live_confirmed": bool(self.live_confirmed),
            "hard_ceiling": HARD_MAX_ACTIONS,
            "warning": ("هر کلیکِ موفق رویِ دکمهٔ ثبتِ سفارش می‌تواند یک سفارشِ "
                        "مستقل بسازد"),
        }


@dataclass
class ActionRecord:
    run_id: str = ""
    idx: int = 0
    planned_at_ms: int = 0
    claimed_at_ms: Optional[int] = None
    fired_at_ms: Optional[int] = None
    completed_at_ms: Optional[int] = None
    state: str = A_PENDING
    result: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        sched_error = (int(self.fired_at_ms) - int(self.planned_at_ms)
                       if self.fired_at_ms is not None and self.planned_at_ms else None)
        return {"idx": self.idx, "planned_at_ms": self.planned_at_ms,
                "planned_at_local": (format_tehran(self.planned_at_ms)
                                     if self.planned_at_ms else None),
                "claimed_at_ms": self.claimed_at_ms, "fired_at_ms": self.fired_at_ms,
                "fired_at_local": (format_tehran(self.fired_at_ms)
                                   if self.fired_at_ms else None),
                "completed_at_ms": self.completed_at_ms, "state": self.state,
                "schedule_error_ms": sched_error, "result": dict(self.result)}


@dataclass
class RunRecord:
    run_id: str
    state: str
    config: RunConfig
    created_at_ms: int
    updated_at_ms: int
    fired_actions: int = 0
    stop_reason: str = ""
    validation: dict[str, Any] = field(default_factory=dict)
    actions: list[ActionRecord] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        remaining = max(0, int(self.config.total_actions) - int(self.fired_actions))
        nxt = None
        for a in self.actions:
            if a.state in (A_PENDING, A_CLAIMED):
                nxt = a.planned_at_ms
                break
        return {"run_id": self.run_id, "state": self.state,
                "config": asdict(self.config), "preview": self.config.preview(),
                "created_at_ms": self.created_at_ms,
                "updated_at_ms": self.updated_at_ms,
                "updated_at_local": format_tehran(self.updated_at_ms),
                "fired_actions": int(self.fired_actions),
                "total_actions": int(self.config.total_actions),
                "remaining_actions": remaining,
                "next_action_at_ms": nxt,
                "next_action_at_local": (format_tehran(nxt) if nxt else None),
                "stop_reason": self.stop_reason,
                "validation": dict(self.validation),
                "actions": [a.public() for a in self.actions]}


Executor = Callable[[RunRecord, ActionRecord], dict[str, Any]]


class AutoClickRunStore:
    """انبارِ SQLiteِ مستقل (بی‌market.db؛ بی‌user.dbِ عملیاتی)."""

    def __init__(self, path: str) -> None:
        self.path = str(path)
        d = os.path.dirname(os.path.abspath(self.path))
        if d:
            os.makedirs(d, exist_ok=True)
        self._lock = threading.Lock()
        self._init()

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=5.0)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=5000")
        return con

    def _init(self) -> None:
        with self._lock, self._conn() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS runs(
              run_id TEXT PRIMARY KEY, account TEXT, symbol TEXT, side TEXT,
              state TEXT, dry_run INTEGER, live_confirmed INTEGER,
              config_json TEXT, planned_first_at_ms INTEGER, interval_ms REAL,
              total_actions INTEGER, fired_actions INTEGER,
              stop_reason TEXT, validation_json TEXT,
              created_at_ms INTEGER, updated_at_ms INTEGER, recovery_token TEXT);
            CREATE TABLE IF NOT EXISTS actions(
              run_id TEXT, idx INTEGER, planned_at_ms INTEGER,
              claimed_at_ms INTEGER, fired_at_ms INTEGER, completed_at_ms INTEGER,
              state TEXT, result_json TEXT,
              PRIMARY KEY(run_id, idx));
            CREATE TABLE IF NOT EXISTS events(
              run_id TEXT, at_ms INTEGER, kind TEXT, detail TEXT);
            CREATE INDEX IF NOT EXISTS runs_due ON runs(state, planned_first_at_ms);
            """)

    # ---- نوشتن ----
    def create(self, cfg: RunConfig) -> RunRecord:
        cfg = cfg.normalized()
        now = int(time.time() * 1000)
        run_id = str(cfg.run_id or "ac-%d" % now)
        cfg = RunConfig(**{**asdict(cfg), "run_id": run_id})
        with self._lock, self._conn() as con:
            con.execute("BEGIN IMMEDIATE")
            busy = con.execute(
                "SELECT run_id FROM runs WHERE account=? AND state IN "
                "('ARMED','WARMING','RUNNING')", (cfg.account,)).fetchone()
            if busy is not None:
                raise RunError("ALREADY_RUNNING",
                               "اجرایِ %s برایِ همین حساب درِ حالتِ فعال است؛ دو "
                               "اجرایِ هم‌زمان نداریم" % str(busy["run_id"]))
            con.execute(
                "INSERT INTO runs(run_id, account, symbol, side, state, dry_run, "
                "live_confirmed, config_json, planned_first_at_ms, interval_ms, "
                "total_actions, fired_actions, stop_reason, validation_json, "
                "created_at_ms, updated_at_ms, recovery_token) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, cfg.account, cfg.symbol, cfg.side, DRAFT,
                 1 if cfg.dry_run else 0, 1 if cfg.live_confirmed else 0,
                 json.dumps(asdict(cfg), ensure_ascii=False),
                 cfg.planned_first_at_ms(), cfg.interval_ms, cfg.total_actions,
                 0, "", "{}", now, now, ""))
            for i in range(cfg.total_actions):
                con.execute(
                    "INSERT INTO actions(run_id, idx, planned_at_ms, state) "
                    "VALUES(?,?,?,?)", (run_id, i, cfg.planned_action_at_ms(i),
                                       A_PENDING))
            self._event(con, run_id, "created", cfg.symbol, now)
        return self.get(run_id)

    def set_state(self, run_id: str, state: str, *, reason: str = "",
                  validation: Optional[Mapping[str, Any]] = None) -> RunRecord:
        if state not in RUN_STATES:
            raise RunError("INVALID_STATE", state)
        now = int(time.time() * 1000)
        with self._lock, self._conn() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None:
                raise RunError("NOT_FOUND", run_id)
            cur = str(row["state"])
            if cur in (COMPLETED, CANCELLED) and state != NEEDS_REVIEW:
                raise RunError("STATE_LOCKED",
                               "اجرایِ %s در وضعیتِ %s تمام شده؛ بازنویسی نشود"
                               % (run_id, cur))
            live_confirmed = int(row["live_confirmed"] or 0)
            val_json = (json.dumps(dict(validation), ensure_ascii=False)
                        if validation is not None else str(row["validation_json"] or "{}"))
            con.execute(
                "UPDATE runs SET state=?, stop_reason=?, validation_json=?, "
                "live_confirmed=?, updated_at_ms=? WHERE run_id=?",
                (state, str(reason or "")[:300], val_json, live_confirmed, now, run_id))
            self._event(con, run_id, "state", "%s%s" % (state,
                                                        ("|" + reason) if reason else ""), now)
        return self.get(run_id)

    def set_confirmation(self, run_id: str, *, live: bool, dry_run: bool,
                         phrase: str = "") -> RunRecord:
        """تأییدِ صریحِ اجرایِ زنده؛ بی‌این هیچ اقدامی رویِ دکمهٔ واقعی نمی‌رود."""
        now = int(time.time() * 1000)
        with self._lock, self._conn() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None:
                raise RunError("NOT_FOUND", run_id)
            if not dry_run and phrase != LIVE_PHRASE:
                raise RunError("CONFIRMATION_PHRASE",
                               "برایِ اجرایِ زنده باید عبارتِ «%s» وارد شود" % LIVE_PHRASE)
            cfg = json.loads(str(row["config_json"] or "{}"))
            cfg["dry_run"] = bool(dry_run)
            cfg["live_confirmed"] = bool(live and not dry_run)
            cfg["confirm_phrase"] = ""
            con.execute("UPDATE runs SET config_json=?, dry_run=?, live_confirmed=?, "
                        "updated_at_ms=? WHERE run_id=?",
                        (json.dumps(cfg, ensure_ascii=False), 1 if dry_run else 0,
                         1 if (live and not dry_run) else 0, now, run_id))
            self._event(con, run_id, "confirmation",
                        "dry_run=%s live=%s" % (dry_run, live), now)
        return self.get(run_id)

    def arm(self, run_id: str, *, validation: Mapping[str, Any],
            ok_for_arm: bool) -> RunRecord:
        if not ok_for_arm:
            got = self.set_state(run_id, BLOCKED, validation=dict(validation),
                                 reason="پیش‌شرط‌ها کامل نیستند")
            return got
        return self.set_state(run_id, ARMED, validation=dict(validation))

    def start(self, run_id: str) -> RunRecord:
        with self._lock, self._conn() as con:
            row = con.execute("SELECT state, dry_run, live_confirmed FROM runs "
                              "WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise RunError("NOT_FOUND", run_id)
        if str(row["state"]) not in (ARMED, WARMING):
            raise RunError("NOT_ARMED",
                           "اجرا باید اول «بررسی و arm» شده باشد؛ وضعیت فعلی %s"
                           % str(row["state"]))
        if int(row["dry_run"] or 0) == 0 and int(row["live_confirmed"] or 0) != 1:
            raise RunError("LIVE_NOT_CONFIRMED",
                           "این اجرا dry-run نیست ولی تأییدِ صریحِ اجرایِ زنده ندارد")
        return self.set_state(run_id, RUNNING, reason="شروعِ دستی")

    def claim_next(self, run_id: str, *, at_ms: int, token: str,
                   lead_ms: int = 0) -> Optional[ActionRecord]:
        """یک‌برنده: فقط یک فراخوانی می‌تواند یک ردیف را claim کند.

        `lead_ms` اجازهٔ claimِ پیش‌از‌موعد را می‌دهد تا اجراکننده بتواند
        اعتبارسنجی/گارد را قبل از لحظهٔ هدف انجام دهد و دقیقاً رویِ هدف کلیک
        کند؛ زمانِ ثبتِ claim همچنان «اکنون» است.
        """
        with self._lock, self._conn() as con:
            con.execute("BEGIN IMMEDIATE")
            run = con.execute("SELECT state FROM runs WHERE run_id=?",
                              (run_id,)).fetchone()
            if run is None or str(run["state"]) not in (WARMING, RUNNING):
                return None
            row = con.execute(
                "SELECT * FROM actions WHERE run_id=? AND state=? AND planned_at_ms<=? "
                "AND claimed_at_ms IS NULL ORDER BY idx LIMIT 1",
                (run_id, A_PENDING, int(at_ms) + max(0, int(lead_ms)))).fetchone()
            if row is None:
                return None
            got = con.execute(
                "UPDATE actions SET claimed_at_ms=?, state=? "
                "WHERE run_id=? AND idx=? AND state=? AND claimed_at_ms IS NULL",
                (int(at_ms), A_CLAIMED, run_id, int(row["idx"]), A_PENDING))
            if int(got_rowcount(got) or 0) != 1:
                return None
            con.execute("UPDATE runs SET updated_at_ms=? WHERE run_id=?",
                        (int(at_ms), run_id))
            self._event(con, run_id, "claim", "action %s by %s" % (row["idx"], token[:12]),
                        int(at_ms))
        return self.action(run_id, int(row["idx"]))

    def mark_fired(self, run_id: str, idx: int, *, at_ms: int) -> bool:
        """لحظهٔ واقعیِ کلیک. شمارندهٔ «انجام‌شده» همین‌جا زیاد می‌شود، نه در claim."""
        with self._lock, self._conn() as con:
            con.execute("BEGIN IMMEDIATE")
            got = con.execute(
                "UPDATE actions SET fired_at_ms=?, state=? WHERE run_id=? AND idx=? "
                "AND state=? AND fired_at_ms IS NULL",
                (int(at_ms), A_FIRED, run_id, int(idx), A_CLAIMED))
            if int(got_rowcount(got) or 0) != 1:
                return False
            con.execute("UPDATE runs SET fired_actions=fired_actions+1, updated_at_ms=? "
                        "WHERE run_id=?", (int(at_ms), run_id))
            self._event(con, run_id, "fire", "action %s at %s" % (idx, at_ms), int(at_ms))
        return True

    def finish_action(self, run_id: str, idx: int, *, state: str,
                      result: Optional[Mapping[str, Any]] = None) -> RunRecord:
        now = int(time.time() * 1000)
        with self._lock, self._conn() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute(
                "UPDATE actions SET state=?, completed_at_ms=?, result_json=? "
                "WHERE run_id=? AND idx=?",
                (str(state), now, json.dumps(dict(result or {}), ensure_ascii=False),
                 run_id, int(idx)))
            self._event(con, run_id, "action_%s" % state, "action %s" % idx, now)
        return self.get(run_id)

    def cancel_pending(self, run_id: str, reason: str = "cancel") -> int:
        now = int(time.time() * 1000)
        with self._lock, self._conn() as con:
            con.execute("BEGIN IMMEDIATE")
            # ردیفِ claim‌شده‌ای که هرگز شلیک نشده هم باید لغو شود، وگرنه توقفِ
            # اضطراری یک ردیفِ معلق می‌گذارد که بعداً شمارنده را گم می‌کند.
            cur = con.execute("SELECT idx FROM actions WHERE run_id=? AND state IN (?,?) "
                              "AND fired_at_ms IS NULL", (run_id, A_PENDING, A_CLAIMED))
            ids = [int(r[0]) for r in cur.fetchall()]
            for i in ids:
                con.execute("UPDATE actions SET state=?, completed_at_ms=?, "
                            "result_json=? WHERE run_id=? AND idx=?",
                            (A_CANCELLED, now,
                             json.dumps({"reason": str(reason)[:200]},
                                        ensure_ascii=False), run_id, i))
            if ids:
                self._event(con, run_id, "cancel_pending",
                            "%d ردیف | %s" % (len(ids), str(reason)[:120]), now)
        return len(ids)

    def stop(self, run_id: str, reason: str = "stop") -> RunRecord:
        cancelled = self.cancel_pending(run_id, reason)
        rec = self.set_state(run_id, STOPPED, reason="%s (لغوِ %d اقدامِ مانده)"
                             % (str(reason or "stop")[:200], cancelled))
        return rec

    def cancel(self, run_id: str, reason: str = "user") -> RunRecord:
        self.cancel_pending(run_id, reason)
        return self.set_state(run_id, CANCELLED, reason=reason)

    def reset_for_restart(self, run_id: str, reason: str = "controlled restart") -> RunRecord:
        """شروعِ دوبارهٔ کنترل‌شده: ردیف‌هایِ مانده از نو PENDING، بازموتِ وضعیت به VALIDATED.

        هیچ اقدامی که FIRED/UNKNOWN بوده پاک نمی‌شود؛ شمارشِ واقعی حفظ است.
        """
        with self._lock, self._conn() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None:
                raise RunError("NOT_FOUND", run_id)
            cur = str(row["state"])
            if cur in (RUNNING, WARMING, ARMED):
                raise RunError("STILL_ACTIVE",
                               "اجرا هنوز فعال است؛ اول توقف/لغو کن بعد شروعِ دوباره")
            if cur in (COMPLETED, CANCELLED):
                raise RunError("FINISHED", "اجرا تمام شده؛ برایِ کارِ تازه اجرا بساز")
            con.execute("UPDATE actions SET state=?, claimed_at_ms=NULL, fired_at_ms=NULL, "
                        "completed_at_ms=NULL, result_json='{}' "
                        "WHERE run_id=? AND state IN (?,?,?,?,?)",
                        (A_PENDING, run_id, A_CANCELLED, A_BLOCKED, A_SKIPPED,
                         A_CLAIMED, A_FIRED))
            fired = int(con.execute("SELECT COUNT(*) FROM actions WHERE run_id=? AND "
                                    "state=?", (run_id, A_DONE)).fetchone()[0] or 0)
            con.execute("UPDATE runs SET state=?, fired_actions=?, updated_at_ms=? "
                        "WHERE run_id=?", (VALIDATED, fired, int(time.time() * 1000),
                                           run_id))
            self._event(con, run_id, "reset", "%s | fired=%d" % (reason[:120], fired),
                        int(time.time() * 1000))
        return self.get(run_id)

    def set_kill(self, reason: str) -> int:
        """توقفِ اضطراری: هر اجرایِ فعال به NEEDS_REVIEW و ردیف‌هایِ مانده لغو."""
        changed = 0
        with self._lock, self._conn() as con:
            rows = con.execute("SELECT run_id FROM runs WHERE state IN (?,?,?)",
                               (ARMED, WARMING, RUNNING)).fetchall()
        for r in rows:
            rid = str(r["run_id"])
            self.cancel_pending(rid, "kill-switch")
            self.set_state(rid, NEEDS_REVIEW, reason="توقفِ اضطراری: %s" % str(reason)[:160])
            changed += 1
        return changed

    def recover(self, *, at_ms: Optional[int] = None,
                max_lateness_ms: int = DEFAULT_MISSED_GRACE_MS) -> dict[str, Any]:
        """بعدِ restart هیچ اقدامی خودکار اجرا نمی‌شود؛ اجرا به NEEDS_REVIEW می‌رود."""
        at = int(at_ms if at_ms is not None else time.time() * 1000)
        out: dict[str, Any] = {"needs_review": [], "missed": [], "restored": 0}
        with self._lock, self._conn() as con:
            rows = con.execute("SELECT run_id FROM runs WHERE state IN (?,?,?)",
                               RECOVER_TO_REVIEW).fetchall()
        for r in rows:
            rid = str(r["run_id"])
            self.cancel_pending(rid, "restart")
            self.set_state(rid, NEEDS_REVIEW,
                           reason="برنامه بعدِ restart هیچ اقدامی را خودکار اجرا نمی‌کند")
            out["needs_review"].append(rid)
        with self._lock, self._conn() as con:
            due = con.execute("SELECT run_id, planned_first_at_ms FROM runs WHERE state=? "
                              "AND planned_first_at_ms < ?", (DRAFT, at - 3600_000)).fetchall()
            for d in due:
                con.execute("UPDATE runs SET state=?, stop_reason=?, updated_at_ms=? "
                            "WHERE run_id=?",
                            (EXPIRED, "بیش از یک ساعت از زمانِ هدف گذشته بود", at,
                             str(d["run_id"])))
                out["missed"].append(str(d["run_id"]))
        out["restored"] = len(out["needs_review"])
        return out

    # ---- خواندن ----
    def get(self, run_id: str) -> RunRecord:
        with self._lock, self._conn() as con:
            row = con.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None:
                raise RunError("NOT_FOUND", run_id)
            acts = con.execute("SELECT * FROM actions WHERE run_id=? ORDER BY idx",
                               (run_id,)).fetchall()
        return self._record(row, acts)

    def list(self, *, limit: int = 50, account: str = "") -> list[RunRecord]:
        lim = max(1, min(int(limit), 200))
        with self._lock, self._conn() as con:
            if account:
                rows = con.execute("SELECT * FROM runs WHERE account=? "
                                   "ORDER BY created_at_ms DESC LIMIT ?",
                                   (account, lim)).fetchall()
            else:
                rows = con.execute("SELECT * FROM runs ORDER BY created_at_ms DESC "
                                   "LIMIT ?", (lim,)).fetchall()
            out = []
            for r in rows:
                acts = con.execute("SELECT * FROM actions WHERE run_id=? ORDER BY idx",
                                   (str(r["run_id"]),)).fetchall()
                out.append(self._record(r, acts))
        return out

    def action(self, run_id: str, idx: int) -> Optional[ActionRecord]:
        with self._lock, self._conn() as con:
            row = con.execute("SELECT * FROM actions WHERE run_id=? AND idx=?",
                              (run_id, int(idx))).fetchone()
        return self._action(row) if row is not None else None

    def events(self, run_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock, self._conn() as con:
            rows = con.execute("SELECT * FROM events WHERE run_id=? "
                               "ORDER BY at_ms DESC, rowid DESC LIMIT ?",
                               (run_id, max(1, min(int(limit), 500)))).fetchall()
        return [{"at_ms": int(r["at_ms"]), "kind": str(r["kind"]),
                 "detail": str(r["detail"] or "")[:300],
                 "at_local": format_tehran(int(r["at_ms"]))} for r in rows]

    def active_run(self, account: str = "easytrader") -> Optional[RunRecord]:
        with self._lock, self._conn() as con:
            row = con.execute("SELECT run_id FROM runs WHERE account=? AND state IN "
                              "(?,?,?) ORDER BY updated_at_ms DESC LIMIT 1",
                              (account, ARMED, WARMING, RUNNING)).fetchone()
        return self.get(str(row["run_id"])) if row is not None else None

    @staticmethod
    def _action(row: sqlite3.Row) -> ActionRecord:
        try:
            res = json.loads(str(row["result_json"] or "{}"))
        except ValueError:
            res = {}
        return ActionRecord(
            run_id=str(row["run_id"]), idx=int(row["idx"]),
            planned_at_ms=int(row["planned_at_ms"] or 0),
            claimed_at_ms=(int(row["claimed_at_ms"]) if row["claimed_at_ms"] is not None
                           else None),
            fired_at_ms=(int(row["fired_at_ms"]) if row["fired_at_ms"] is not None else None),
            completed_at_ms=(int(row["completed_at_ms"])
                             if row["completed_at_ms"] is not None else None),
            state=str(row["state"] or A_PENDING),
            result=res if isinstance(res, dict) else {})

    @staticmethod
    def _record(row: sqlite3.Row, acts: list[sqlite3.Row]) -> RunRecord:
        try:
            cfg = json.loads(str(row["config_json"] or "{}"))
        except ValueError:
            cfg = {}
        try:
            val = json.loads(str(row["validation_json"] or "{}"))
        except ValueError:
            val = {}
        keep = {f for f in RunConfig.__dataclass_fields__}
        cfg = RunConfig(**{k: v for k, v in dict(cfg).items() if k in keep})
        return RunRecord(run_id=str(row["run_id"]), state=str(row["state"]),
                         config=cfg, created_at_ms=int(row["created_at_ms"] or 0),
                         updated_at_ms=int(row["updated_at_ms"] or 0),
                         fired_actions=int(row["fired_actions"] or 0),
                         stop_reason=str(row["stop_reason"] or ""),
                         validation=val if isinstance(val, dict) else {},
                         actions=[AutoClickRunStore._action(a) for a in acts])

    @staticmethod
    def _event(con: sqlite3.Connection, run_id: str, kind: str, detail: str,
               at_ms: int) -> None:
        con.execute("INSERT INTO events(run_id, at_ms, kind, detail) VALUES(?,?,?,?)",
                    (run_id, int(at_ms), kind, str(detail or "")[:300]))


def got_rowcount(cur: sqlite3.Cursor) -> int:
    """جدا شده تا در تستِ قابلِ خواندن ماند: تعدادِ ردیفِ تغییرکرده."""
    return int(cur.rowcount)


#: عبارتِ تأییدِ صریحِ اجرایِ زنده؛ بی‌این هیچ کلیکِ واقعی ساخته نمی‌شود.
LIVE_PHRASE = "کلیکِ واقعی را اجرا کن"


__all__ = ["RunConfig", "RunRecord", "ActionRecord", "AutoClickRunStore",
           "RunError", "parse_tehran_wall", "format_tehran", "tehran_tz",
           "LIVE_PHRASE", "HARD_MAX_ACTIONS", "MIN_INTERVAL_MS", "TIMEZONE_NAME",
           "DRAFT", "VALIDATED", "ARMED", "WARMING", "RUNNING", "COMPLETED",
           "STOPPED", "CANCELLED", "NEEDS_REVIEW", "MISSED_TARGET", "EXPIRED",
           "BLOCKED", "A_PENDING", "A_CLAIMED", "A_FIRED", "A_DONE", "A_BLOCKED",
           "A_SKIPPED", "A_CANCELLED", "TERMINAL_NO_RETRY"]
