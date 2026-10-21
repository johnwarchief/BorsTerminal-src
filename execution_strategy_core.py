# -*- coding: utf-8 -*-
"""execution_strategy_core.py — قراردادِ Strategyهای اجرای سرخطی.

هدف: هر روشِ اجرا (Direct API، AutoClicker، Playwright/DOM، JavaScript،
Keyboard، Selenium) یک Strategy مستقل با تنظیماتِ غیرمحرمانه، وضعیت، معیارهای
زمانی و نتیجهٔ قابل‌اندازه‌گیری باشد. این فایل فقط core است: هیچ network و هیچ
مرورگری اینجا نیست.

قفل‌های ثابت:
  ۱) تنظیمات فقط غیرمحرمانه‌اند. کلیدِ token/cookie/password/authorization رد
     می‌شود؛ مقدارِ محرمانه درِ این جدول نمی‌نشیند.
  ۲) هر execution_id حداکثر یک submitterِ زنده دارد. چند Strategy می‌توانند
     prepare کنند (shadow/benchmark)، ولی claimِ ارسال یک‌بار است.
  ۳) بعد از نتیجهٔ نامعلوم، هیچ Strategy دیگری مجاز به ارسال نیست؛ اول reconcile.
  ۴) معیارها فقط از نمونه‌های واقعیِ همان پروسه ساخته می‌شوند؛ نبودِ نمونه ⇒
     p95/p99 = None، نه صفر.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional

from execution_timing import percentile

# ── ۱) شناسه‌ها و مشخصات ────────────────────────────────────────────────────
DIRECT_API = "direct_api"
AUTOCLICKER = "autoclicker"
PLAYWRIGHT_DOM = "playwright_dom"
JAVASCRIPT = "javascript"
KEYBOARD = "keyboard"
SELENIUM = "selenium"
ALL_STRATEGIES = (DIRECT_API, AUTOCLICKER, PLAYWRIGHT_DOM, JAVASCRIPT,
                  KEYBOARD, SELENIUM)

MODE_OFF = "off"
MODE_SHADOW = "shadow"
MODE_LIVE = "live"
MODES = (MODE_OFF, MODE_SHADOW, MODE_LIVE)


@dataclass(frozen=True)
class StrategySpec:
    id: str
    label: str
    kind: str
    description: str
    requires_browser: bool
    supports_dry_run: bool
    supports_live: bool
    default_mode: str
    default_priority: int
    default_options: Mapping[str, Any] = field(default_factory=dict)


_COMMON_BROWSER = {
    "order_url": "https://d.easytrader.ir/",
    "origin_allowlist": ["https://d.easytrader.ir"],
    #: selectorهای خریدِ عادیِ EasyTrader؛ قیمت/تعداد و دکمهٔ بازکردن در UI
    #: زنده دیده شدند و هدرِ فرم در باندلِ خودِ EasyTrader (`data-cy`) هست.
    #: برایِ فروش یا نسخهٔ دیگرِ UI باید override شوند.
    "submit_selector": "button[aria-label='ارسال خرید']",
    #: Round 14: انتخابگرهایِ همان سمت. دکمهٔ فروش در UI زنده دیده نشده؛
    #: عمداً خالی می‌ماند تا فروش به‌جای کلیکِ اشتباه، CONFIG_MISSING بگیرد.
    "submit_selector_buy": "button[aria-label='ارسال خرید']",
    "submit_selector_sell": "",
    "symbol_selector": "",
    "form_symbol_selector": "[data-cy='order-form-header-symbol-name']",
    "open_form_selector": "button.order-buy-btn",
    "open_form_selector_buy": "button.order-buy-btn",
    "open_form_selector_sell": "",
    "form_selector": "",
    "side_selector": "",
    "isin_selector": "",
    "price_selector": "#price",
    "quantity_selector": "#quantity",
    "login_selector": "",
    "clock_selector": "",
    "intercept_pattern": "**/core/api/v2/order*",
    "order_paths": ["/core/api/v2/order"],
    "order_method": "POST",
    "action_timeout_ms": 1200,
    "navigation_timeout_ms": 20000,
    "headless": False,
    "browser_path": "",
    "profile_dir": "",
    #: CDPِ hostِ مالک؛ در Production برایِ نشستِ پایدار استفاده می‌شود.
    "cdp_url": "",
    "autofill": True,
    "require_prefilled": False,
    #: بازرسیِ ارزانِ «دکمه همان‌جا و آماده است» پیش از کلیک. خاموش‌کردنش
    #: latency را کم می‌کند ولی یک نمونهٔ «کلیک بی‌درخواست» را محتمل‌تر می‌کند.
    "preclick_check": True,
    #: فقط برای Mockِ محلی در بنچمارک؛ Production پیش‌فرض false است.
    "ignore_https_errors": False,
    "no_proxy": False,
    #: پیش‌فرض false: هر سفارش مرورگر تازه می‌سازد. بنچمارک true می‌کند تا
    #: هزینهٔ ساختِ مرورگر را از مسیرِ trigger جدا کند (cold جدا گزارش می‌شود).
    "keep_driver_alive": False,
}

_SPECS: dict[str, StrategySpec] = {
    DIRECT_API: StrategySpec(
        DIRECT_API, "Direct API", "http",
        "درخواستِ HTTPِ مستقیم به APIِ کارگزاری (مسیرِ رسمیِ برنامه).",
        False, True, True, MODE_LIVE, 0, {}),
    AUTOCLICKER: StrategySpec(
        AUTOCLICKER, "AutoClicker", "browser",
        "فرمِ ازپیش‌آماده؛ در زمان هدف فقط یک کلیک روی دکمهٔ ارسال.",
        True, True, True, MODE_SHADOW, 10,
        {**_COMMON_BROWSER, "autofill": False, "require_prefilled": True}),
    PLAYWRIGHT_DOM: StrategySpec(
        PLAYWRIGHT_DOM, "Playwright / DOM", "browser",
        "پرکردنِ فرم با locatorهای DOM و کلیکِ همان locator در زمان هدف.",
        True, True, True, MODE_SHADOW, 20, dict(_COMMON_BROWSER)),
    JAVASCRIPT: StrategySpec(
        JAVASCRIPT, "JavaScript", "browser",
        "اجرای fetch در بافتِ خودِ صفحه با نشستِ مرورگر؛ بدونِ فرم.",
        True, True, True, MODE_SHADOW, 30,
        {**_COMMON_BROWSER, "api_path": "/core/api/v2/order"}),
    KEYBOARD: StrategySpec(
        KEYBOARD, "Keyboard", "browser",
        "پرکردنِ فرم و ارسال با توالیِ کلید (در صورتِ نیاز ورودیِ OS).",
        True, True, True, MODE_SHADOW, 40,
        {**_COMMON_BROWSER, "key_sequence": ["Enter"], "focus_selector": ""}),
    SELENIUM: StrategySpec(
        SELENIUM, "Selenium", "browser",
        "مسیرِ سازگاری با Selenium؛ فقط اگر بستهٔ selenium نصب باشد.",
        True, True, True, MODE_SHADOW, 50,
        {**_COMMON_BROWSER, "driver_path": ""}),
}

#: کلیدهایی که هرگز درِ تنظیماتِ روی‌دیسک نمی‌نشینند.
_SECRET_WORDS = ("token", "cookie", "password", "passwd", "secret",
                 "authorization", "credential", "session", "har")
#: سقفِ اندازهٔ options برای جلوگیری از دامپِ دادهٔ بزرگ در user.db.
_MAX_OPTIONS_BYTES = 16 * 1024


def specs() -> dict[str, StrategySpec]:
    return dict(_SPECS)


def spec(strategy_id: str) -> StrategySpec:
    got = _SPECS.get(str(strategy_id))
    if got is None:
        raise ValueError("unknown strategy: %s" % strategy_id)
    return got


def _is_secret_key(key: str) -> bool:
    low = str(key).lower()
    return any(w in low for w in _SECRET_WORDS)


def _options_safe(options: Mapping[str, Any]) -> dict[str, Any]:
    """کپیِ JSON-پذیر با ردِ کلیدِ رازدار و سقفِ اندازه."""
    if not isinstance(options, Mapping):
        raise ValueError("options must be an object")
    out: dict[str, Any] = {}
    for k, v in options.items():
        key = str(k)
        if _is_secret_key(key):
            raise ValueError("secret-shaped option rejected: %s" % key)
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[key] = v
        elif isinstance(v, (list, tuple)) and all(
                isinstance(x, (str, int, float, bool)) for x in v):
            out[key] = list(v)
        else:
            raise ValueError("option must be scalar/list: %s" % key)
    blob = json.dumps(out, ensure_ascii=False)
    if len(blob.encode("utf-8")) > _MAX_OPTIONS_BYTES:
        raise ValueError("options too large")
    return out


@dataclass
class StrategySettings:
    strategy_id: str
    enabled: bool
    mode: str
    priority: int
    options: dict[str, Any]
    updated_at: int = 0

    def public(self) -> dict[str, Any]:
        return {"strategy": self.strategy_id, "enabled": self.enabled,
                "mode": self.mode, "priority": self.priority,
                "options": dict(self.options), "updated_at": self.updated_at}


def default_settings(strategy_id: str) -> StrategySettings:
    sp = spec(strategy_id)
    return StrategySettings(strategy_id, True, sp.default_mode,
                            sp.default_priority, dict(sp.default_options), 0)


# ── ۲) ذخیرهٔ تنظیمات (user.db، غیرمحرمانه) ─────────────────────────────────
_TABLE = "execution_strategy_settings"
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS %s("
    " strategy_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL,"
    " mode TEXT NOT NULL, priority INTEGER NOT NULL,"
    " options_json TEXT NOT NULL, updated_at INTEGER NOT NULL)" % _TABLE)
_LOCK = threading.Lock()


def _db_path() -> str:
    import bors_config
    return bors_config.USER_DB_PATH


class StrategySettingsStore:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or _db_path()

    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute(_SCHEMA)
        return conn

    def load(self) -> dict[str, StrategySettings]:
        out = {sid: default_settings(sid) for sid in ALL_STRATEGIES}
        try:
            con = self._conn()
        except Exception:
            return out
        try:
            rows = con.execute(
                "SELECT strategy_id, enabled, mode, priority, options_json, updated_at "
                "FROM %s" % _TABLE).fetchall()
        except Exception:
            rows = []
        finally:
            con.close()
        for sid, enabled, mode, priority, raw, updated in rows:
            if sid not in out:
                continue
            try:
                opts = json.loads(raw) if raw else {}
                opts = _options_safe(opts)
            except Exception:
                opts = dict(out[sid].options)
            out[sid] = StrategySettings(
                str(sid), bool(enabled), str(mode) if mode in MODES else MODE_OFF,
                int(priority), opts, int(updated or 0))
        return out

    def save(self, strategy_id: str, *, enabled: Optional[bool] = None,
             mode: Optional[str] = None, priority: Optional[int] = None,
             options: Optional[Mapping[str, Any]] = None) -> StrategySettings:
        # ادغام با تنظیمِ *ذخیره‌شده*، نه با پیش‌فرض؛ وگرنه یک به‌روزرسانیِ
        # key_sequence بقیهٔ selectorها را بی‌صدا به پیش‌فرض برمی‌گرداند.
        cur = self.load().get(strategy_id) or default_settings(strategy_id)
        merged = dict(cur.options)
        if options is not None:
            merged.update(_options_safe(options))
        new = StrategySettings(
            strategy_id,
            cur.enabled if enabled is None else bool(enabled),
            cur.mode if mode is None else str(mode),
            cur.priority if priority is None else int(priority),
            merged, int(time.time()))
        if new.mode not in MODES:
            raise ValueError("invalid mode: %s" % new.mode)
        if not (0 <= new.priority <= 100):
            raise ValueError("priority must be 0..100")
        with _LOCK:
            con = self._conn()
            try:
                con.execute(
                    "INSERT OR REPLACE INTO %s(strategy_id, enabled, mode, priority, "
                    "options_json, updated_at) VALUES(?,?,?,?,?,?)" % _TABLE,
                    (new.strategy_id, int(new.enabled), new.mode, new.priority,
                     json.dumps(new.options, ensure_ascii=False), new.updated_at))
                con.commit()
            finally:
                con.close()
        return new

    def reset(self, strategy_id: str) -> StrategySettings:
        with _LOCK:
            con = self._conn()
            try:
                con.execute("DELETE FROM %s WHERE strategy_id=?" % _TABLE,
                            (strategy_id,))
                con.commit()
            finally:
                con.close()
        return default_settings(strategy_id)


# ── ۳) معیارهای زمانی ───────────────────────────────────────────────────────
PHASES = ("prepare", "trigger", "action", "send", "response", "reconcile", "total")


@dataclass
class PhaseStats:
    count: int = 0
    ok: int = 0
    failed: int = 0
    last_ms: Optional[float] = None
    last_error: str = ""
    last_at: Optional[int] = None
    p50: Optional[float] = None
    p95: Optional[float] = None
    p99: Optional[float] = None


class StrategyMetrics:
    """حلقهٔ نمونه‌های در حافظه؛ p95/p99 با نمونهٔ کم = None، نه صفرِ جعلی."""

    def __init__(self, max_samples: int = 500) -> None:
        self.max_samples = int(max_samples)
        self._samples: dict[str, dict[str, deque]] = defaultdict(
            lambda: {p: deque(maxlen=self.max_samples) for p in PHASES})
        self._errors: dict[str, dict[str, str]] = defaultdict(dict)
        self._fails: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._lock = threading.Lock()

    def record(self, strategy_id: str, phase: str, ms: Optional[float],
               *, ok: bool = True, error: str = "") -> None:
        if phase not in PHASES or ms is None:
            return
        with self._lock:
            self._samples[strategy_id][phase].append(float(ms))
            if not ok:
                self._fails[strategy_id][phase] += 1
                if error:
                    self._errors[strategy_id][phase] = str(error)[:160]

    def summary(self, strategy_id: str) -> dict[str, dict[str, Any]]:
        with self._lock:
            data = {p: list(self._samples[strategy_id][p]) for p in PHASES}
            errs = dict(self._errors[strategy_id])
            fails = dict(self._fails[strategy_id])
        out: dict[str, dict[str, Any]] = {}
        for phase, values in data.items():
            failed = int(fails.get(phase, 0))
            st = PhaseStats(count=len(values), ok=len(values) - failed,
                            failed=failed,
                            last_ms=round(values[-1], 2) if values else None,
                            last_error=errs.get(phase, ""),
                            last_at=int(time.time()) if values else None)
            if values:
                st.p50 = round(percentile(values, 50), 2)
                st.p95 = round(percentile(values, 95), 2) if len(values) >= 5 else None
                st.p99 = round(percentile(values, 99), 2) if len(values) >= 20 else None
            out[phase] = {
                "count": st.count, "ok": st.ok, "failed": st.failed,
                "p50": st.p50, "p95": st.p95, "p99": st.p99,
                "last_ms": st.last_ms, "last_error": st.last_error,
                "last_at": st.last_at, "thin": len(values) < 5,
            }
        return out

    def record_result(self, strategy_id: str, timings: Mapping[str, Any]) -> None:
        # prepare در StrategyEngine.prepare یک‌بار ثبت شده؛ اینجا دوباره نشمار.
        for phase, value in (timings or {}).items():
            if phase in PHASES and phase != "prepare" and value is not None:
                try:
                    self.record(strategy_id, phase, float(value))
                except (TypeError, ValueError):
                    continue


# ── ۴) arbiterِ یک intent / یک ثبت ──────────────────────────────────────────
class IntentArbiter:
    """چند prepare مجاز، یک claimِ ارسال. بعد از UNKNOWN هیچ claimی نه."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, dict[str, Any]] = {}

    def _entry(self, execution_id: str) -> dict[str, Any]:
        return self._state.setdefault(execution_id, {
            "prepared": set(), "submitter": None, "state": "prepared",
            "reason": "", "updated_at": time.time()})

    def reserve(self, execution_id: str, strategy_id: str) -> tuple[bool, str]:
        with self._lock:
            e = self._entry(execution_id)
            if e["state"] in ("submitting", "submitted", "unknown"):
                return False, "intent already %s" % e["state"]
            e["prepared"].add(strategy_id)
            return True, ""

    def claim(self, execution_id: str, strategy_id: str) -> tuple[bool, str]:
        with self._lock:
            e = self._entry(execution_id)
            # فقط یک گذارِ prepared -> submitting. هر وضعیتِ دیگر (dry_run،
            # failed، blocked، submitted، unknown) یعنی این intent قبلاً یک
            # مسیر را مصرف کرده و تکرار ممنوع است؛ intent تازه = شناسهٔ تازه.
            if e["state"] != "prepared":
                if e["state"] == "unknown":
                    return False, "previous result unknown: reconcile before any fallback"
                return False, "intent already %s" % e["state"]
            if e["submitter"] not in (None, strategy_id):
                return False, "another strategy owns this intent: %s" % e["submitter"]
            if strategy_id not in e["prepared"]:
                return False, "strategy did not prepare this intent"
            e["submitter"] = strategy_id
            e["state"] = "submitting"
            e["updated_at"] = time.time()
            return True, ""

    def complete(self, execution_id: str, strategy_id: str, result: str,
                 reason: str = "") -> None:
        with self._lock:
            e = self._entry(execution_id)
            if e["submitter"] not in (None, strategy_id):
                return
            e["state"] = str(result)
            e["reason"] = str(reason)[:200]
            e["updated_at"] = time.time()

    def mark_unknown(self, execution_id: str, strategy_id: str, reason: str = "") -> None:
        self.complete(execution_id, strategy_id, "unknown", reason)

    def abort(self, execution_id: str) -> None:
        with self._lock:
            e = self._entry(execution_id)
            if e["state"] == "prepared":
                e["state"] = "aborted"
                e["updated_at"] = time.time()

    def release(self, execution_id: str) -> None:
        with self._lock:
            self._state.pop(execution_id, None)

    def state(self, execution_id: str) -> dict[str, Any]:
        with self._lock:
            e = self._state.get(execution_id)
            if e is None:
                return {"state": "none", "submitter": None, "prepared": []}
            return {"state": e["state"], "submitter": e["submitter"],
                    "prepared": sorted(e["prepared"]), "reason": e["reason"],
                    "updated_at": e["updated_at"]}


# ── ۵) rate limiterِ سطح حساب ────────────────────────────────────────────────
class AccountWindowLimiter:
    """پنجرهٔ لغزانِ سراسری برای یک حساب/کارگزاری، مشترک بین همهٔ Strategyها.

    فقط ارسالِ زنده acquire می‌کند؛ prepare/benchmark بودجه مصرف نمی‌کند.
    """

    def __init__(self, *, max_events: Optional[int] = None,
                 window_s: float = 60.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.max_events = None if max_events is None else int(max_events)
        self.window_s = float(window_s)
        self.clock = clock
        self._events: dict[str, deque] = defaultdict(deque)
        self._blocked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def try_acquire(self, account: str = "easytrader") -> tuple[bool, float]:
        now = self.clock()
        with self._lock:
            until = self._blocked_until.get(account)
            if until is not None and now < until:
                return False, round(until - now, 3)
            q = self._events[account]
            while q and now - q[0] >= self.window_s:
                q.popleft()
            if self.max_events is not None and len(q) >= self.max_events:
                retry = max(0.0, self.window_s - (now - q[0]))
                return False, round(retry, 3)
            q.append(now)
            return True, 0.0

    def block_for(self, account: str, seconds: float) -> None:
        with self._lock:
            until = self.clock() + max(0.0, float(seconds))
            self._blocked_until[account] = max(
                until, self._blocked_until.get(account, 0.0))

    def status(self) -> dict[str, Any]:
        now = self.clock()
        with self._lock:
            out = {}
            for account, q in self._events.items():
                while q and now - q[0] >= self.window_s:
                    q.popleft()
                out[account] = {
                    "events_in_window": len(q),
                    "max_events": self.max_events,
                    "window_s": self.window_s,
                    "blocked_for_s": max(0.0, round(self._blocked_until.get(account, 0.0) - now, 3)),
                }
            return out


# ── ۶) نتیجه ────────────────────────────────────────────────────────────────
@dataclass
class StrategyResult:
    execution_id: str
    strategy_id: str
    status: str                       # dry_run|submitted|accepted|unknown|failed|aborted|blocked
    detail: str = ""
    broker_order_id: Optional[str] = None
    error_code: Optional[str] = None
    http_status: Optional[int] = None
    accepted: bool = False
    unknown: bool = False
    request_aborted: bool = False
    live: bool = False
    timings: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id, "strategy": self.strategy_id,
            "status": self.status, "detail": self.detail,
            "broker_order_id": self.broker_order_id,
            "error_code": self.error_code, "http_status": self.http_status,
            "accepted": self.accepted, "unknown": self.unknown,
            "request_aborted": self.request_aborted, "live": self.live,
            "timings": dict(self.timings), "evidence": dict(self.evidence),
        }


@dataclass
class StrategyOrder:
    execution_id: str
    strategy_id: str
    draft: Any
    target_wall_ms: Optional[int]
    intent_key: str = ""
    prepared_id: str = ""
    prepared: Any = None
    state: str = "prepared"
    created_at: float = field(default_factory=time.time)
    preparation_ms: Optional[float] = None
    result: Optional[StrategyResult] = None
    abort_event: threading.Event = field(default_factory=threading.Event)

    def __post_init__(self) -> None:
        if not self.prepared_id:
            self.prepared_id = "%s:%s" % (self.execution_id, self.strategy_id)

    def public(self) -> dict[str, Any]:
        return {
            "prepared_id": self.prepared_id,
            "execution_id": self.execution_id, "strategy": self.strategy_id,
            "state": self.state, "target_wall_ms": self.target_wall_ms,
            "created_at": self.created_at,
            "preparation_ms": self.preparation_ms,
            "result": self.result.public() if self.result else None,
        }


# ── ۷) انتخابِ خودکار بر اساس شواهد ─────────────────────────────────────────
def rank_strategies(metrics: StrategyMetrics,
                    candidates: list[str],
                    *, min_samples: int = 5,
                    phase: str = "total") -> list[dict[str, Any]]:
    """رتبه‌بندیِ صادقانه: فقط Strategyهایی با نمونهٔ کافی و بدونِ خطایِ اخیر.

    هیچ سرعتی از README یا ادعایِ بیرونی وارد نمی‌شود؛ فقط نمونه‌هایِ همین پروسه.
    """
    rows = []
    for sid in candidates:
        s = metrics.summary(sid).get(phase, {})
        count = int(s.get("count") or 0)
        failed = int(s.get("failed") or 0)
        usable = count >= min_samples and failed == 0 and s.get("p95") is not None
        rows.append({"strategy": sid, "usable": usable, "count": count,
                     "failed": failed, "p50": s.get("p50"),
                     "p95": s.get("p95"), "p99": s.get("p99"),
                     "last_ms": s.get("last_ms")})
    rows.sort(key=lambda r: (not r["usable"], r["p95"] if r["p95"] is not None else 1e18,
                             r["p50"] if r["p50"] is not None else 1e18,
                             r["strategy"]))
    return rows


__all__ = [
    "DIRECT_API", "AUTOCLICKER", "PLAYWRIGHT_DOM", "JAVASCRIPT", "KEYBOARD",
    "SELENIUM", "ALL_STRATEGIES", "MODE_OFF", "MODE_SHADOW", "MODE_LIVE",
    "StrategySpec", "specs", "spec", "default_settings", "StrategySettings",
    "StrategySettingsStore", "StrategyMetrics", "IntentArbiter",
    "AccountWindowLimiter", "StrategyResult", "StrategyOrder", "rank_strategies",
]
