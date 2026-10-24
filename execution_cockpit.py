# -*- coding: utf-8 -*-
"""execution_cockpit.py — وضعیت، Preflight و اجرای Mock درونِ برنامه.

این ماژول عمداً به هیچ آداپتور/سفارش/شبکه‌ای وصل نیست. تنها نوشتنی‌اش
`execution_cockpit.db` است: runها و رویدادهایِ آزمونِ Mock. وضعیت‌های واقعی
(DB، عرضه، بودجه، host، نشست) از بیرون تزریق می‌شوند و این‌جا فقط داوری و
نمایش می‌شوند؛ هیچ Gateی برای سبزکردنِ صفحه ساخته نمی‌شود.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
import uuid
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = 1
PASS = "PASS"
FAIL = "FAIL"
BLOCKED = "BLOCKED"
UNVERIFIED = "UNVERIFIED"
NOT_RUN = "NOT_RUN"
STOPPED = "STOPPED"
UNKNOWN = "UNKNOWN"
UNKNOWN_HOLD = "UNKNOWN_HOLD"
INTERRUPTED = "INTERRUPTED"
IDEMPOTENT = "IDEMPOTENT"
SKIPPED_BUDGET = "SKIPPED_BUDGET"

ACTIVE_HOLD_STATES = ("RESERVED", "COMMITTED", "UNKNOWN_HOLD")

SCENARIO_INFO: tuple[dict[str, str], ...] = (
    {"id": "success", "label": "اجرای آزمایشی موفق",
     "detail": "چرخهٔ Mock تا گزارشِ نهایی؛ سفارشِ واقعی نیست"},
    {"id": "stale_data", "label": "دادهٔ کهنه",
     "detail": "همان چرخه با data_as_of قدیمی‌تر از max_age"},
    {"id": "missing_source", "label": "نبودِ منبع معتبر",
     "detail": "رکورد بدونِ منبع/نشانیِ قابلِ استناد"},
    {"id": "insufficient_budget", "label": "بودجهٔ ناکافی",
     "detail": "هزینهٔ شبیه‌سازی از سقفِ قابلِ استفاده بیشتر است"},
    {"id": "unverified_offering", "label": "عرضهٔ UNVERIFIED",
     "detail": "عرضهٔ تأییدنشده واردِ Preflight می‌شود"},
    {"id": "backend_error", "label": "خطای Backend/شبکه",
     "detail": "خطای شبیه‌سازی‌شده؛ هیچ درخواستِ واقعی ارسال نمی‌شود"},
    {"id": "duplicate_request", "label": "تکرارِ درخواست",
     "detail": "همان intent دو بار؛ رزروِ دوم باید IDEMPOTENT باشد"},
    {"id": "unknown_result", "label": "نتیجهٔ نامعلوم",
     "detail": "UNKNOWN بدونِ retry؛ تا reconcile دستی"},
    {"id": "unknown_hold", "label": "باقی‌ماندن UNKNOWN_HOLD",
     "detail": "بودجه نگه داشته می‌شود و رزرو عادی نمی‌شود"},
    {"id": "restart_recovery", "label": "restart و بازیابی",
     "detail": "گزارشِ شبیه‌سازی‌شدهٔ توقف؛ هیچ ازسرگیریِ خودکار نیست"},
    {"id": "host_error", "label": "خطای browser host",
     "detail": "host/نشستِ غیرقابلِ تأیید؛ اجرای زنده مسدود"},
)
SCENARIOS = {s["id"]: s for s in SCENARIO_INFO}
STOP_EVENTS: dict[str, threading.Event] = {}
STOP_LOCK = threading.Lock()
_SECRET_KEY = re.compile(r"(token|cookie|password|passwd|authorization|secret|session)", re.I)
_SECRET_VALUE = re.compile(r"(bearer\s+[a-z0-9._\-]{12,}|eyJ[a-zA-Z0-9_\-]{16,}\.[a-zA-Z0-9_\-]{8,})", re.I)


class CockpitError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__("%s: %s" % (code, detail) if detail else code)
        self.code = code
        self.detail = detail


def now_ms() -> int:
    return int(time.time() * 1000)


def _iso(ms: int | None) -> str | None:
    if ms is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ms / 1000.0))


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)[:20000]


def _dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class CockpitStore:
    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        self._lock = threading.Lock()
        con = self._conn()
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=FULL")
            con.executescript("""
            CREATE TABLE IF NOT EXISTS cockpit_runs(
              id TEXT PRIMARY KEY, scenario TEXT NOT NULL, mode TEXT NOT NULL,
              status TEXT NOT NULL, started_at REAL NOT NULL, finished_at REAL,
              stop_requested INTEGER NOT NULL DEFAULT 0,
              summary_json TEXT NOT NULL DEFAULT '{}', error TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS cockpit_events(
              seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
              at REAL NOT NULL, phase TEXT NOT NULL, status TEXT NOT NULL,
              detail TEXT NOT NULL DEFAULT '', duration_ms REAL
            );
            CREATE INDEX IF NOT EXISTS ix_cockpit_events_run
              ON cockpit_events(run_id, seq);
            CREATE TABLE IF NOT EXISTS cockpit_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            con.execute("INSERT OR REPLACE INTO cockpit_meta(key,value) VALUES('schema_version',?)",
                        (str(SCHEMA_VERSION),))
        finally:
            con.close()
        self.recover_interrupted()

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=5000")
        return con

    def _event_in(self, con: sqlite3.Connection, run_id: str, phase: str,
                  status: str, detail: str = "", duration_ms: float | None = None,
                  at: float | None = None) -> None:
        con.execute("INSERT INTO cockpit_events(run_id,at,phase,status,detail,duration_ms) "
                    "VALUES(?,?,?,?,?,?)",
                    (run_id, time.time() if at is None else at, phase, status,
                     detail[:1200], duration_ms))

    def append_event(self, run_id: str, phase: str, status: str, detail: str = "",
                     duration_ms: float | None = None) -> None:
        con = self._conn()
        try:
            self._event_in(con, run_id, phase, status, detail, duration_ms)
        finally:
            con.close()

    def start_run(self, scenario: str) -> dict[str, Any]:
        if scenario not in SCENARIOS:
            raise CockpitError("INVALID_SCENARIO", "سناریوی آزمون ناشناخته است")
        rid = "run-%s" % uuid.uuid4().hex[:14]
        at = time.time()
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute("INSERT INTO cockpit_runs(id,scenario,mode,status,started_at) "
                        "VALUES(?,?,?,?,?)", (rid, scenario, "MOCK", "RUNNING", at))
            self._event_in(con, rid, "start", "RUNNING",
                           "MOCK %s — هیچ سفارش/درخواستِ بیرونی ساخته نمی‌شود" % scenario, at=at)
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        return {"id": rid, "scenario": scenario, "mode": "MOCK", "status": "RUNNING",
                "started_at": at}

    def finish(self, run_id: str, status: str, summary: Mapping[str, Any] | None = None,
               error: str = "") -> None:
        at = time.time()
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute("UPDATE cockpit_runs SET status=?, finished_at=?, summary_json=?, "
                        "error=? WHERE id=?",
                        (status, at, _json(dict(summary or {})), error[:1000], run_id))
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def stop(self, run_id: str) -> dict[str, Any]:
        con = self._conn()
        try:
            row = con.execute("SELECT status FROM cockpit_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise CockpitError("RUN_NOT_FOUND", "اجرای آزمون پیدا نشد")
            if row["status"] != "RUNNING":
                return {"id": run_id, "status": str(row["status"]), "unchanged": True}
            con.execute("BEGIN IMMEDIATE")
            con.execute("UPDATE cockpit_runs SET stop_requested=1 WHERE id=?", (run_id,))
            self._event_in(con, run_id, "stop", "STOPPED", "درخواستِ توقفِ آزمونِ Mock ثبت شد")
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        with STOP_LOCK:
            ev = STOP_EVENTS.get(run_id)
            if ev is not None:
                ev.set()
        return {"id": run_id, "status": "STOPPING", "unchanged": False}

    def _stopped(self, run_id: str) -> bool:
        with STOP_LOCK:
            ev = STOP_EVENTS.get(run_id)
            return bool(ev and ev.is_set())

    def recover_interrupted(self) -> list[str]:
        con = self._conn()
        recovered: list[str] = []
        try:
            rows = con.execute("SELECT id FROM cockpit_runs WHERE status='RUNNING'").fetchall()
            if rows:
                con.execute("BEGIN IMMEDIATE")
                for row in rows:
                    rid = str(row["id"])
                    con.execute("UPDATE cockpit_runs SET status=?, finished_at=?, error=? "
                                "WHERE id=?", (INTERRUPTED, time.time(),
                                               "process ended during MOCK run", rid))
                    self._event_in(con, rid, "recovery", INTERRUPTED,
                                   "پس از restart: هیچ ازسرگیریِ خودکار/نتیجهٔ موفق ساخته نشد")
                    recovered.append(rid)
                con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        return recovered

    def run(self, run_id: str) -> dict[str, Any] | None:
        con = self._conn()
        try:
            row = con.execute("SELECT * FROM cockpit_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                return None
            events = [dict(r) for r in con.execute(
                "SELECT seq,at,phase,status,detail,duration_ms FROM cockpit_events "
                "WHERE run_id=? ORDER BY seq", (run_id,)).fetchall()]
        finally:
            con.close()
        out = _dict(row) or {}
        out["summary"] = json.loads(out.pop("summary_json", "{}") or "{}")
        out["events"] = events
        return out

    def runs(self, limit: int = 30) -> list[dict[str, Any]]:
        con = self._conn()
        try:
            rows = con.execute("SELECT * FROM cockpit_runs ORDER BY started_at DESC LIMIT ?",
                               (max(1, min(int(limit), 100)),)).fetchall()
            out = []
            for row in rows:
                item = _dict(row) or {}
                item["summary"] = json.loads(item.pop("summary_json", "{}") or "{}")
                item["event_count"] = int(con.execute(
                    "SELECT COUNT(*) FROM cockpit_events WHERE run_id=?",
                    (item["id"],)).fetchone()[0])
                out.append(item)
            return out
        finally:
            con.close()

    def events(self, run_id: str, limit: int = 500) -> list[dict[str, Any]]:
        con = self._conn()
        try:
            return [dict(r) for r in con.execute(
                "SELECT seq,at,phase,status,detail,duration_ms FROM cockpit_events "
                "WHERE run_id=? ORDER BY seq LIMIT ?",
                (run_id, max(1, min(int(limit), 1000)))).fetchall()]
        finally:
            con.close()


def _mock_offering(now: int) -> dict[str, Any]:
    return {
        "symbol": "MOCK", "isin": "MOCK-ISIN", "method": "BOOK_BUILDING",
        "market": "MOCK", "status": "VERIFIED",
        "start_ms": now - 3_600_000, "end_ms": now + 3_600_000,
        "price_min": 100.0, "price_max": 110.0, "price_source": "MOCK",
        "price_step": 1.0, "min_qty": 1.0, "max_qty": 1000.0,
        "per_code_quota": 500.0, "fee_rate": 0.0012, "fee_source": "MOCK",
        "source": "MOCK", "source_url": "mock://cockpit", "verified_at_ms": now - 1_000,
        "data_as_of_ms": now - 2_000,
    }


def _steps(scenario: str, *, offering: Mapping[str, Any] | None,
           price: float | None, quantity: float | None) -> tuple[list[tuple[str, str, str]], str, dict[str, Any]]:
    now = now_ms()
    mock = _mock_offering(now)
    offer = dict(offering) if offering else mock
    try:
        p = float(price) if price is not None and float(price) > 0 else 105.0
    except (TypeError, ValueError):
        p = 105.0
    try:
        q = float(quantity) if quantity is not None and float(quantity) > 0 else 10.0
    except (TypeError, ValueError):
        q = 10.0
    base = [
        ("health", PASS, "SIMULATED health — هیچ شبکه‌ای صدا زده نشد"),
        ("data", PASS, "MOCK data — منبع/سن: fixture محلی"),
        ("provenance", PASS, "MOCK provenance — source_url و timestamps علامت‌گذاری‌شده"),
    ]
    summary: dict[str, Any] = {"mock": True, "order_sent": False, "live_send": False,
                               "acceptance_time_observed": False, "retry_performed": False,
                               "evidence_level": "SIMULATED"}
    if scenario == "success":
        steps = base + [
            ("offering", PASS, "MOCK %s/%s؛ price=%s qty=%s" % (mock["symbol"], mock["isin"], p, q)),
            ("budget", PASS, "MOCK بودجه؛ رزرو شبیه‌سازی‌شده"),
            ("intent", PASS, "MOCK intent؛ یک مسیر"),
            ("state_machine", PASS, "SIMULATED ACK accepted؛ FILLED ادعا نمی‌شود"),
            ("result", PASS, "SIMULATED result؛ هیچ سفارش واقعی ارسال نشد"),
        ]
        return steps, PASS, summary
    if scenario == "stale_data":
        steps = base[:1] + [
            ("data", FAIL, "data_as_of=7200s؛ max_age=3600s — Preflight مسدود"),
            ("offering", BLOCKED, "دادهٔ کهنه اجازهٔ رزرو نمی‌دهد"),
            ("result", BLOCKED, "SIMULATED: هیچ اقدامی انجام نشد"),
        ]
        summary["reason"] = "STALE_DATA"
        return steps, BLOCKED, summary
    if scenario == "missing_source":
        steps = base[:2] + [
            ("provenance", BLOCKED, "source_url خالی است؛ UNVERIFIED"),
            ("offering", BLOCKED, "بدونِ منبعِ معتبر قابلِ تخصیص نیست"),
            ("result", BLOCKED, "SIMULATED: مسدود"),
        ]
        summary["reason"] = "MISSING_SOURCE"
        return steps, BLOCKED, summary
    if scenario == "insufficient_budget":
        steps = base + [
            ("offering", PASS, "MOCK %s/%s" % (mock["symbol"], mock["isin"])),
            ("budget", SKIPPED_BUDGET, "MOCK بودجهٔ ناکافی؛ هیچ رزروی ساخته نشد"),
            ("result", BLOCKED, "SIMULATED: SKIPPED_BUDGET"),
        ]
        summary["reason"] = "INSUFFICIENT_BUDGET"
        return steps, BLOCKED, summary
    if scenario == "unverified_offering":
        actual = offer if str(offer.get("status") or "") != "VERIFIED" else mock
        label = "%s/%s (%s)" % (actual.get("symbol", "?"), actual.get("isin", "?"),
                                 actual.get("status", "UNVERIFIED"))
        steps = base[:2] + [
            ("provenance", BLOCKED, "%s؛ منبع تأییدشده نیست" % label),
            ("offering", BLOCKED, "UNVERIFIED در Preflight مسدود است"),
            ("result", BLOCKED, "SIMULATED: هیچ رزروی ساخته نشد"),
        ]
        summary["reason"] = "UNVERIFIED_OFFERING"
        return steps, BLOCKED, summary
    if scenario == "backend_error":
        steps = [
            ("health", FAIL, "SIMULATED backend/network error — هیچ درخواستی ارسال نشد"),
            ("result", FAIL, "SIMULATED failure؛ retry پنهان وجود ندارد"),
        ]
        summary["reason"] = "BACKEND_ERROR"
        return steps, FAIL, summary
    if scenario == "duplicate_request":
        steps = base + [
            ("offering", PASS, "MOCK عرضه"),
            ("intent", PASS, "intent=MOCK-DUP"),
            ("duplicate_request", IDEMPOTENT, "تلاشِ دوم: رزروِ دوم ساخته نشد"),
            ("result", PASS, "SIMULATED: یک intent، یک رزرو"),
        ]
        summary["reason"] = "IDEMPOTENT"
        return steps, PASS, summary
    if scenario == "unknown_result":
        steps = base + [
            ("offering", PASS, "MOCK عرضه"),
            ("state_machine", UNKNOWN, "SIMULATED timeout/قطع پس از آغاز ارسال"),
            ("retry_suppressed", PASS, "retry خودکار انجام نشد؛ reconcile لازم است"),
            ("result", UNKNOWN, "SIMULATED UNKNOWN؛ هیچ نتیجهٔ موفقی ساخته نشد"),
        ]
        summary["reason"] = "UNKNOWN_RESULT"
        return steps, UNKNOWN, summary
    if scenario == "unknown_hold":
        steps = base + [
            ("offering", PASS, "MOCK عرضه"),
            ("state_machine", UNKNOWN_HOLD, "SIMULATED: بودجه نگه داشته شد"),
            ("retry_suppressed", PASS, "رزرو تازه/retry ساخته نشد"),
            ("result", UNKNOWN_HOLD, "SIMULATED UNKNOWN_HOLD؛ نیازمند شاهد"),
        ]
        summary["reason"] = "UNKNOWN_HOLD"
        return steps, UNKNOWN_HOLD, summary
    if scenario == "restart_recovery":
        steps = [
            ("health", PASS, "SIMULATED health"),
            ("recovery", INTERRUPTED, "SIMULATED restart؛ هیچ ازسرگیریِ خودکار"),
            ("result", INTERRUPTED, "SIMULATED: نیازمند بررسی، نه موفق"),
        ]
        summary["reason"] = "INTERRUPTED_NO_AUTO_RESUME"
        return steps, INTERRUPTED, summary
    if scenario == "host_error":
        steps = base[:1] + [
            ("browser_host", BLOCKED, "SIMULATED host/session error؛ نشست تأیید نشده"),
            ("result", BLOCKED, "SIMULATED: مسیرِ زنده بسته ماند"),
        ]
        summary["reason"] = "HOST_ERROR"
        return steps, BLOCKED, summary
    raise CockpitError("INVALID_SCENARIO", "سناریوی آزمون ناشناخته است")


def _execute_run(store: CockpitStore, rid: str, scenario: str, *,
                 offering: Mapping[str, Any] | None, price: float | None,
                 quantity: float | None, step_delay_s: float) -> dict[str, Any]:
    try:
        steps, final, summary = _steps(scenario, offering=offering, price=price,
                                       quantity=quantity)
        for phase, status, detail in steps:
            if store._stopped(rid):
                store.append_event(rid, "stop", STOPPED, "آزمون پیش از پایان متوقف شد")
                store.finish(rid, STOPPED, {**summary, "reason": "STOPPED"})
                return store.run(rid) or {}
            t0 = time.time()
            time.sleep(max(0.0, float(step_delay_s)))
            store.append_event(rid, phase, status, detail,
                               round((time.time() - t0) * 1000, 1))
            if store._stopped(rid):
                store.append_event(rid, "stop", STOPPED, "آزمون پس از این مرحله متوقف شد")
                store.finish(rid, STOPPED, {**summary, "reason": "STOPPED"})
                return store.run(rid) or {}
        store.append_event(rid, "report", "PASS", "گزارشِ Mock آماده است؛ live_send=false")
        store.finish(rid, final, summary)
        return store.run(rid) or {}
    except Exception as e:                       # noqa: BLE001
        store.append_event(rid, "error", FAIL, "%s: %s" % (type(e).__name__, str(e)[:300]))
        store.finish(rid, FAIL, {}, "%s: %s" % (type(e).__name__, str(e)[:300]))
        return store.run(rid) or {}


def _register_stop(store: CockpitStore, scenario: str) -> tuple[dict[str, Any], str, threading.Event]:
    if scenario not in SCENARIOS:
        raise CockpitError("INVALID_SCENARIO", "سناریوی آزمون ناشناخته است")
    run = store.start_run(scenario)
    rid = str(run["id"])
    ev = threading.Event()
    with STOP_LOCK:
        STOP_EVENTS[rid] = ev
    return run, rid, ev


def _clear_stop(rid: str) -> None:
    with STOP_LOCK:
        STOP_EVENTS.pop(rid, None)


def run_scenario(store: CockpitStore, scenario: str, *, offering: Mapping[str, Any] | None = None,
                 price: float | None = None, quantity: float | None = None,
                 step_delay_s: float = 0.02) -> dict[str, Any]:
    """اجرای هم‌زمان برای گارد؛ مسیر API از start_scenario استفاده می‌کند."""
    run, rid, _ev = _register_stop(store, scenario)
    try:
        return _execute_run(store, rid, scenario, offering=offering, price=price,
                            quantity=quantity, step_delay_s=step_delay_s)
    finally:
        _clear_stop(rid)


def start_scenario(store: CockpitStore, scenario: str, *,
                   offering: Mapping[str, Any] | None = None,
                   price: float | None = None, quantity: float | None = None,
                   step_delay_s: float = 0.25) -> dict[str, Any]:
    """run را می‌سازد و در پس‌زمینه اجرا می‌کند تا stop/UI واقعاً ممکن باشد."""
    run, rid, _ev = _register_stop(store, scenario)

    def worker() -> None:
        try:
            _execute_run(store, rid, scenario, offering=offering, price=price,
                         quantity=quantity, step_delay_s=step_delay_s)
        finally:
            _clear_stop(rid)

    threading.Thread(target=worker, name="cockpit-%s" % rid, daemon=True).start()
    return store.run(rid) or run


# ── وضعیت و Gateها ──────────────────────────────────────────────────────────
def _gate(gate_id: str, label: str, status: str, evidence: str, reason: str,
          action: str = "", source: str = "", observed_at: float | None = None,
          age_s: float | None = None) -> dict[str, Any]:
    return {"id": gate_id, "label": label, "status": status, "evidence": evidence,
            "reason": reason, "action": action, "source": source,
            "observed_at": observed_at, "age_s": age_s}


def _age_ms(ms: int | None, now: int) -> float | None:
    if ms is None:
        return None
    return max(0.0, (now - int(ms)) / 1000.0)


def build_status(*, app_version: str, offerings: Iterable[Mapping[str, Any]],
                 capital: Mapping[str, Any], reserved: float,
                 reservations: Iterable[Mapping[str, Any]],
                 readiness: Mapping[str, Any], host: Mapping[str, Any],
                 execution: Mapping[str, Any], db: Mapping[str, Mapping[str, Any]],
                 now: int | None = None) -> dict[str, Any]:
    at = now_ms() if now is None else int(now)
    offers = [dict(o) for o in offerings]
    verified = [o for o in offers if str(o.get("status")) == "VERIFIED"]
    latest = max(verified, key=lambda o: int(o.get("data_as_of_ms") or 0), default=None)
    holds = [r for r in reservations if str(r.get("state")) == "UNKNOWN_HOLD"]
    mode = str(execution.get("adapter") or "?")
    live = bool(execution.get("live_enabled"))
    session = execution.get("session") or {}
    proven = bool(session.get("proven")) and mode != "mock"
    host_ok = bool(host.get("healthy"))
    readiness_blockers = list(readiness.get("blockers") or [])
    readiness_codes = {str(b.get("code") or "") for b in readiness_blockers}

    gates: list[dict[str, Any]] = []
    gates.append(_gate(
        "frontend", "Frontend/نسخه", UNVERIFIED,
        "پنل در حالِ اجراست؛ نسخهٔ برنامه %s" % app_version,
        "رندرِ فرانت از سمتِ سرور قابلِ اثبات نیست", source="panel"))
    gates.append(_gate(
        "backend", "Backend/API", PASS,
        "GET /api/execution/cockpit/status پاسخ داد",
        "APIهای ضروری همین حالا پاسخ می‌دهند", source="cockpit"))
    bad_db = [k for k, v in db.items() if not bool(v.get("readable"))]
    gates.append(_gate(
        "database", "پایگاه داده/ماندگاری", PASS if not bad_db else FAIL,
        "offerings/schedules/cockpit/market: " + ", ".join(
            "%s=%s" % (k, "ok" if v.get("readable") else "missing") for k, v in db.items()),
        "همهٔ DBهای لازم خوانا هستند" if not bad_db else "DB خوانا نیست: " + ", ".join(bad_db),
        action="" if not bad_db else "مسیر/دسترسیِ DB را بررسی کنید",
        source="sqlite"))
    gates.append(_gate(
        "browser_host", "Browser host", PASS if host_ok else BLOCKED,
        "host=%s" % ("healthy" if host_ok else "unavailable"),
        "host سالم است" if host_ok else "host/CDP سالم نیست؛ ورودِ دستی و host لازم است",
        action="" if host_ok else "host را باز کنید و نشست را دستی برقرار کنید",
        source="execution_browser_host"))
    gates.append(_gate(
        "session", "نشست EasyTrader", PASS if (live and proven) else BLOCKED,
        "adapter=%s live=%s proven=%s" % (mode, live, proven),
        "نشست با شاهد تأیید شده" if (live and proven) else
        "نشستِ کارگزاریِ تأییدشده نداریم؛ باز بودنِ صفحه اثبات نیست",
        action="" if (live and proven) else "ورود دستی در host و بررسی read-only",
        source="execution/status"))
    market = db.get("market", {})
    market_age = _age_ms(market.get("mtime_ms"), at)
    gates.append(_gate(
        "market_data", "منبع داده/تازگی", UNVERIFIED,
        "market=%s mtime=%s age=%s" % (
            "readable" if market.get("readable") else "missing",
            market.get("mtime_iso") or "—",
            "—" if market_age is None else "%ds" % int(market_age)),
        "دادهٔ محلی خوانا است، اما همان‌روز بودنش اثبات نشده",
        action="منبعِ رسمیِ همان روز و زمانِ داده را ثبت کنید",
        source="market.db", observed_at=market.get("mtime_ms"), age_s=market_age))
    if latest is None:
        gates.append(_gate(
            "offering", "عرضه/هویت", BLOCKED, "هیچ عرضهٔ VERIFIED نیست",
            "بدونِ عرضهٔ تأییدشده Preflight/رزرو مسدود است",
            action="عرضهٔ رسمی را با منبع و زمان داده ثبت کنید", source="offerings"))
    else:
        age = _age_ms(latest.get("data_as_of_ms"), at)
        gates.append(_gate(
            "offering", "عرضه/هویت", PASS,
            "%s · %s · data_age=%ss" % (latest.get("symbol"), latest.get("isin"),
                                        "—" if age is None else int(age)),
            "عرضهٔ VERIFIED با منبع/زمان داده موجود است",
            source=str(latest.get("source") or ""), observed_at=latest.get("data_as_of_ms"),
            age_s=age))
    term_bits = []
    if latest:
        for key in ("price_min", "price_max", "price_source", "price_step",
                    "min_qty", "max_qty", "per_code_quota", "fee_rate", "fee_source"):
            term_bits.append("%s=%s" % (key, latest.get(key)))
    terms_ok = bool(latest and latest.get("price_min") is not None
                    and latest.get("price_max") is not None
                    and latest.get("price_source") and latest.get("price_step")
                    and latest.get("per_code_quota") is not None
                    and latest.get("fee_rate") is not None and latest.get("fee_source"))
    gates.append(_gate(
        "terms", "قیمت/گام/سهمیه/کارمزد",
        PASS if terms_ok else UNVERIFIED,
        " · ".join(term_bits) if term_bits else "بدونِ عرضهٔ تأییدشده",
        "شرایطِ سفارش از رکوردِ تأییدشده خوانده می‌شود" if terms_ok
        else "قیمت/گام/سهمیه/کارمزد هنوز کامل نیست",
        action="" if terms_ok else
        "قیمت/گام/سهمیه/کارمزد را از منبع رسمی وارد کنید",
        source=str((latest or {}).get("source") or "")))
    latest_age = _age_ms((latest or {}).get("data_as_of_ms"), at)
    gates.append(_gate(
        "data_fresh", "تازگی دادهٔ عرضه",
        (PASS if latest_age is not None and latest_age <= 3600 else
         FAIL if latest is not None else UNVERIFIED),
        "age=%s max=3600s" % ("—" if latest_age is None else int(latest_age)),
        "داده در پنجرهٔ ۳۶۰۰ ثانیه است" if latest_age is not None and latest_age <= 3600
        else "دادهٔ عرضه تازه نیست یا data_as_of ندارد",
        action="" if latest_age is not None and latest_age <= 3600
        else "زمان دادهٔ منبع را تازه/معتبر کنید",
        source=str((latest or {}).get("source") or ""),
        observed_at=(latest or {}).get("data_as_of_ms"), age_s=latest_age))
    gates.append(_gate(
        "calendar", "تقویم/پنجرهٔ سفارش",
        BLOCKED if "CALENDAR" in readiness_codes else UNVERIFIED,
        "schedule readiness: " + (", ".join(sorted(readiness_codes)) or "—"),
        "تقویمِ همان روز تأیید نشده",
        action="وضعیت روز معاملاتی را از منبع رسمی تأیید کنید",
        source="execution_schedule.readiness"))
    total = capital.get("total_cap")
    avail = None if total is None else max(0.0, float(total) - float(capital.get("cash_reserve") or 0) - float(reserved))
    gates.append(_gate(
        "budget", "بودجه/رزرو", PASS if total is not None else NOT_RUN,
        "cap=%s reserved=%s available=%s" % (total, round(float(reserved), 2),
                                              None if avail is None else round(avail, 2)),
        "سقف تنظیم شده و رزروها خوانده شد" if total is not None else "سقف بودجه تنظیم نشده",
        action="" if total is not None else "بودجه/ذخیره/سقف هر عرضه را تنظیم کنید",
        source="offerings"))
    gates.append(_gate(
        "unknown_hold", "UNKNOWN_HOLD", FAIL if holds else PASS,
        "%d رزروِ UNKNOWN_HOLD" % len(holds),
        "رزروِ نامعلومِ فعال وجود دارد؛ تا شاهد، رزرو/ارسال تازه ممنوع" if holds
        else "رزروِ UNKNOWN_HOLD فعال نیست",
        action="با شاهد، UNKNOWN_HOLD را تعیین تکلیف کنید" if holds else "",
        source="reservations"))
    gates.append(_gate(
        "buying_power", "قدرت خرید/موجودی", BLOCKED,
        "منبع read-only تأییدشده در دسترس نیست",
        "بدونِ منبعِ معتبر، عددی ساخته نمی‌شود",
        action="منبعِ read-only قدرت خرید را تأیید/وصل کنید", source="external"))
    gates.append(_gate(
        "live_contract", "قرارداد write", BLOCKED,
        "WIRE_HYPOTHESIS و هیچ پاسخِ واقعیِ ثبت سفارش",
        "قرارداد کارگزاری تأیید نشده", action="پس از Gateهای قبلی، آزمونِ مجازِ سفارش",
        source="execution"))
    gates.append(_gate(
        "live_ready", "آمادگی Live", BLOCKED,
        "live_ready=false",
        "همهٔ Gateهای بیرونی/قرارداد/نشست هنوز بسته‌اند",
        action="Round 8: تأیید مالک و آزمونِ تحتِ نظارت", source="readiness"))

    failing = [g for g in gates if g["status"] != PASS]
    next_action = next((g["action"] for g in failing if g["action"]), "")
    return {
        "status": "success", "mode": "MOCK", "live_ready": False,
        "live_send": False, "secrets_stored": False,
        "app_version": app_version, "observed_at": at / 1000.0,
        "observed_iso": _iso(at), "gates": gates,
        "next_action": next_action, "failing_count": len(failing),
        "components": {
            "frontend": "panel-loaded", "backend": "responding",
            "db": {k: bool(v.get("readable")) for k, v in db.items()},
            "browser_host": "healthy" if host_ok else "unavailable",
            "session": "proven" if (live and proven) else "unverified",
            "offerings": len(offers), "verified_offerings": len(verified),
            "unknown_holds": len(holds),
        },
        "readiness": {"live_ready": False, "blockers": readiness_blockers},
    }


def preflight_snapshot(*, offering: Mapping[str, Any] | None,
                       price: float | None, quantity: float | None,
                       status: Mapping[str, Any], max_age_s: float = 3600.0,
                       capital: Mapping[str, Any] | None = None,
                       reserved: float = 0.0) -> dict[str, Any]:
    if offering is None:
        return {"status": "success", **status, "preflight": {
            "ok": False, "state": NOT_RUN, "checks": [],
            "reason": "عرضه‌ای انتخاب نشده؛ Preflight سفارش آغاز نشد",
            "action": "یک عرضهٔ VERIFIED انتخاب و قیمت/تعداد را وارد کنید",
        }}
    try:
        from execution_offerings import OfferingRecord, preflight
        rec = OfferingRecord(**{k: offering.get(k) for k in OfferingRecord.__dataclass_fields__})
        if price is None or quantity is None:
            return {"status": "success", **status, "preflight": {
                "ok": False, "state": NOT_RUN, "checks": [],
                "reason": "قیمت/تعداد وارد نشده؛ Preflight سفارش آغاز نشد",
                "action": "قیمت و تعداد را وارد و دوباره اجرا کنید",
            }}
        rep = preflight(rec, at=now_ms(), price=float(price), quantity=float(quantity),
                        max_age_s=max_age_s, capital=capital, reserved=reserved)
    except Exception as e:                       # noqa: BLE001
        return {"status": "error", "code": "PREFLIGHT_INVALID",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:200])}
    checks = [{"name": name, "state": c.get("state"), "detail": c.get("detail"),
               "source": str(offering.get("source") or ""),
               "observed_at": offering.get("data_as_of_ms")}
              for name, c in (rep.get("checks") or {}).items()]
    return {"status": "success", **status, "preflight": {
        "ok": bool(rep.get("ok")), "state": PASS if rep.get("ok") else BLOCKED,
        "checks": checks, "blockers": rep.get("blockers") or [],
        "amount": rep.get("amount"), "fee": rep.get("fee"),
        "source": str(offering.get("source") or ""),
        "observed_at": offering.get("data_as_of_ms"),
    }}


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        out = {}
        for k, v in value.items():
            sensitive = _SECRET_KEY.search(str(k)) and not isinstance(v, (bool, int, float))
            out[str(k)] = "***" if sensitive else redact(v)
        return out
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return _SECRET_VALUE.sub("***", value)
    return value


def build_report(*, status: Mapping[str, Any], runs: Iterable[Mapping[str, Any]],
                 events: Iterable[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    return redact({
        "status": "success", "generated_at": time.time(),
        "mode": "MOCK", "live_ready": False, "secrets_stored": False,
        "order_sent": False, "acceptance_time_observed": False,
        "system": status, "runs": list(runs), "events": list(events or []),
    })


__all__ = ["CockpitError", "CockpitStore", "SCENARIO_INFO", "SCENARIOS",
           "build_report", "build_status", "preflight_snapshot", "redact",
           "run_scenario", "now_ms"]
