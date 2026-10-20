# -*- coding: utf-8 -*-
"""execution_schedule.py — ذخیره‌سازیِ ماندگارِ سفارشِ آماده و زمان‌بندیِ سرخطی.

قفل‌های این لایه:
  ۱) هیچ قیمت/تعداد/شناسه‌ای پیش‌فرض یا حدس زده نمی‌شود؛ مالک می‌دهد.
  ۲) claim و تغییرِ وضعیت اتمیک است (SQLite، BEGIN IMMEDIATE، UPDATE شرطی).
  ۳) پس از restart هیچ سفارشِ آماده/مسلح خودکار اجرا نمی‌شود؛ به NEEDS_REVIEW می‌رود.
  ۴) هدفِ ازدست‌رفته MISSED_TARGET می‌شود؛ اجرای فوریِ جبرانی وجود ندارد.
  ۵) UNKNOWN ترمینال است؛ ارسال دوباره/fallback در این لایه ممکن نیست.
  ۶) live executor عمداً وصل نیست؛ فقط dry-run اجرا می‌شود.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Iterable, Mapping

try:                                      # pragma: no cover - tzdata روی ویندوز
    from zoneinfo import ZoneInfo
    TEHRAN = ZoneInfo("Asia/Tehran")
except Exception:                         # pragma: no cover
    TEHRAN = timezone(timedelta(hours=3, minutes=30), "Asia/Tehran")

TZ_NAME = "Asia/Tehran"
SCHEMA_VERSION = 1
DEFAULT_SYMBOL = "داروند"
DEFAULT_FULL_NAME = "زیست اروند فارمد"
PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"


def now_ms() -> int:
    return int(time.time() * 1000)


def to_local(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, TEHRAN).isoformat(timespec="minutes")


def norm_text(value: str | None) -> str:
    """حروفِ عربیِ ی/ک را با شکلِ فارسی یکی می‌کند؛ مقایسهٔ نامِ محلی با نامِ UI."""
    return " ".join(str(value or "").replace("\u064a", "\u06cc")
                    .replace("\u0643", "\u06a9").split()).casefold()


def parse_local(text: str) -> int:
    """ISO محلیِ Asia/Tehran → epoch ms. مقدارِ بی‌منطقه/نامعتبر رد می‌شود."""
    raw = (text or "").strip()
    if not raw:
        raise ScheduleError("INVALID_TARGET", "زمانِ هدف خالی است")
    try:
        got = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise ScheduleError("INVALID_TARGET", "قالبِ زمانِ هدف نامعتبر است") from None
    if got.tzinfo is None:
        got = got.replace(tzinfo=TEHRAN)
    return int(got.timestamp() * 1000)


class ResultState(str, Enum):
    """نتیجهٔ canonical از دیدِ سفارش؛ جدا از وضعیتِ اجرای زمان‌بند."""
    NOT_SENT = "NOT_SENT"
    REJECTED = "REJECTED"
    ACCEPTED = "ACCEPTED"
    UNKNOWN = "UNKNOWN"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


def canonical_result(rec: "ScheduleRecord") -> str:
    """نگاشت‌ِ صریح؛ FILLED فقط با شاهدِ صریحِ filled، نه از ACK."""
    state = rec.state
    if state == ScheduleState.CANCELLED.value:
        return ResultState.CANCELLED.value
    if state == ScheduleState.REJECTED.value:
        return ResultState.REJECTED.value
    if state == ScheduleState.UNKNOWN.value:
        return ResultState.UNKNOWN.value
    if state == ScheduleState.SUBMITTING.value:
        return ResultState.UNKNOWN.value
    if state == ScheduleState.ACKNOWLEDGED.value:
        result = rec.result or {}
        os_ = str(result.get("order_state") or "").lower()
        try:
            filled = float(result.get("filled_quantity") or 0.0)
        except (TypeError, ValueError):
            filled = 0.0
        if os_ == "filled" or filled > 0:
            return ResultState.FILLED.value
        return ResultState.ACCEPTED.value
    return ResultState.NOT_SENT.value


class ScheduleError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__("%s: %s" % (code, detail) if detail else code)
        self.code = code
        self.detail = detail


class ScheduleState(str, Enum):
    PREPARED = "PREPARED"
    ARMED = "ARMED"
    RUNNING = "RUNNING"
    SUBMITTING = "SUBMITTING"
    DRY_RUN = "DRY_RUN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    MISSED_TARGET = "MISSED_TARGET"
    NEEDS_REVIEW = "NEEDS_REVIEW"


ACTIVE_STATES = (ScheduleState.PREPARED.value, ScheduleState.ARMED.value,
                 ScheduleState.RUNNING.value, ScheduleState.SUBMITTING.value,
                 ScheduleState.NEEDS_REVIEW.value)
TERMINAL_STATES = (ScheduleState.DRY_RUN.value, ScheduleState.ACKNOWLEDGED.value,
                   ScheduleState.REJECTED.value, ScheduleState.UNKNOWN.value,
                   ScheduleState.CANCELLED.value, ScheduleState.EXPIRED.value,
                   ScheduleState.MISSED_TARGET.value)


@dataclass
class ScheduleRecord:
    id: str
    execution_id: str
    symbol: str
    isin: str
    ins_code: str | None
    full_name: str | None
    side: str
    price: float
    quantity: float
    order_type: str
    validity: str
    strategy: str
    mode: str
    target_ms: int
    target_local: str
    tz: str
    state: str
    dedupe_key: str
    settings_version: int
    attempts: int
    created_at: float
    updated_at: float
    armed_at: float | None
    claimed_at: float | None
    claim_token: str | None
    last_validation: dict | None
    validation_ok: bool | None
    result: dict | None
    last_error: str

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id, "execution_id": self.execution_id,
            "symbol": self.symbol, "isin": self.isin, "ins_code": self.ins_code,
            "full_name": self.full_name, "side": self.side,
            "price": self.price, "quantity": self.quantity,
            "order_type": self.order_type, "validity": self.validity,
            "strategy": self.strategy, "mode": self.mode,
            "target_ms": self.target_ms, "target_local": self.target_local,
            "tz": self.tz, "state": self.state,
            "settings_version": self.settings_version, "attempts": self.attempts,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "armed_at": self.armed_at, "claimed_at": self.claimed_at,
            "validation_ok": self.validation_ok,
            "last_validation": self.last_validation,
            "result": self.result, "result_state": canonical_result(self),
            "last_error": self.last_error,
        }


def _row(r: sqlite3.Row) -> ScheduleRecord:
    return ScheduleRecord(
        id=r["id"], execution_id=r["execution_id"], symbol=r["symbol"],
        isin=r["isin"], ins_code=r["ins_code"], full_name=r["full_name"],
        side=r["side"], price=float(r["price"]), quantity=float(r["quantity"]),
        order_type=r["order_type"], validity=r["validity"],
        strategy=r["strategy"], mode=r["mode"], target_ms=int(r["target_ms"]),
        target_local=r["target_local"], tz=r["tz"], state=r["state"],
        dedupe_key=r["dedupe_key"], settings_version=int(r["settings_version"]),
        attempts=int(r["attempts"]), created_at=float(r["created_at"]),
        updated_at=float(r["updated_at"]), armed_at=r["armed_at"],
        claimed_at=r["claimed_at"], claim_token=r["claim_token"],
        last_validation=json.loads(r["last_validation"]) if r["last_validation"] else None,
        validation_ok=(None if r["validation_ok"] is None else bool(r["validation_ok"])),
        result=json.loads(r["result"]) if r["result"] else None,
        last_error=r["last_error"] or "")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS schedule_meta (
  key TEXT PRIMARY KEY, value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS schedules (
  id TEXT PRIMARY KEY,
  execution_id TEXT NOT NULL UNIQUE,
  symbol TEXT NOT NULL,
  isin TEXT NOT NULL,
  ins_code TEXT,
  full_name TEXT,
  side TEXT NOT NULL,
  price REAL NOT NULL,
  quantity REAL NOT NULL,
  order_type TEXT NOT NULL,
  validity TEXT NOT NULL,
  strategy TEXT NOT NULL,
  mode TEXT NOT NULL,
  target_ms INTEGER NOT NULL,
  target_local TEXT NOT NULL,
  tz TEXT NOT NULL,
  state TEXT NOT NULL,
  dedupe_key TEXT NOT NULL,
  settings_version INTEGER NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  armed_at REAL,
  claimed_at REAL,
  claim_token TEXT,
  last_validation TEXT,
  validation_ok INTEGER,
  result TEXT,
  last_error TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_schedule_dedupe
  ON schedules(dedupe_key)
  WHERE state IN ('PREPARED','ARMED','RUNNING','SUBMITTING','NEEDS_REVIEW',
                  'UNKNOWN','ACKNOWLEDGED');
CREATE TABLE IF NOT EXISTS schedule_events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  schedule_id TEXT NOT NULL,
  at_epoch REAL NOT NULL,
  kind TEXT NOT NULL,
  detail TEXT,
  state TEXT
);
"""


class ScheduleStore:
    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        self._schema_lock = threading.Lock()
        self._init()

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=5000")
        return con

    def _init(self) -> None:
        with self._schema_lock:
            con = self._conn()
            try:
                con.execute("PRAGMA journal_mode=WAL")
                con.execute("PRAGMA synchronous=FULL")
                con.executescript(_SCHEMA)
                con.execute("INSERT OR IGNORE INTO schedule_meta(key,value) VALUES('schema_version',?)",
                            (str(SCHEMA_VERSION),))
            finally:
                con.close()

    @staticmethod
    def _event(con: sqlite3.Connection, sid: str, kind: str, detail: str,
               state: str, at: float) -> None:
        con.execute("INSERT INTO schedule_events(schedule_id,at_epoch,kind,detail,state) "
                    "VALUES(?,?,?,?,?)", (sid, at, kind, detail[:500], state))

    def create(self, *, symbol: str, isin: str, price: float, quantity: float,
               side: str, target_ms: int | None = None, target_local: str = "",
               full_name: str = "", ins_code: str = "", strategy: str = "playwright_dom",
               mode: str = "dry_run", order_type: str = "normal",
               validity: str = "day", execution_id: str = "",
               settings_version: int = 1, at_ms: int | None = None) -> ScheduleRecord:
        at = now_ms() if at_ms is None else int(at_ms)
        sym = (symbol or "").strip()
        ident = (isin or "").strip().upper()
        if not sym:
            raise ScheduleError("INVALID_SYMBOL", "نماد خالی است")
        if not ident:
            raise ScheduleError("INVALID_ISIN", "شناسهٔ نماد (ISIN) لازم است")
        if side not in ("buy", "sell"):
            raise ScheduleError("INVALID_SIDE", "سمت باید buy یا sell باشد")
        try:
            price_f = float(price)
            qty_f = float(quantity)
        except (TypeError, ValueError):
            raise ScheduleError("INVALID_ORDER", "قیمت/تعداد عدد نیست") from None
        if not (price_f > 0 and qty_f > 0):
            raise ScheduleError("INVALID_ORDER", "قیمت و تعداد باید مثبت باشند")
        if qty_f != int(qty_f):
            raise ScheduleError("INVALID_QUANTITY", "تعداد باید صحیح باشد")
        if mode not in ("dry_run", "live"):
            raise ScheduleError("INVALID_MODE", "حالت باید dry_run یا live باشد")
        if order_type not in ("normal", "smart"):
            raise ScheduleError("INVALID_ORDER_TYPE", "نوع سفارش نامعتبر است")
        if validity not in ("day", "valid_to_date"):
            raise ScheduleError("INVALID_VALIDITY", "اعتبار سفارش نامعتبر است")
        target = int(target_ms) if target_ms is not None else parse_local(target_local)
        if target <= at:
            raise ScheduleError("TARGET_IN_PAST", "زمانِ هدف باید در آینده باشد")
        eid = (execution_id or "").strip() or "sched-%s" % uuid.uuid4().hex[:16]
        # کلید در دقتِ دقیقه: دو زمان‌بندیِ یک نماد/سمت در همان دقیقه تکراری‌اند،
        # حتی اگر چند میلی‌ثانیه با هم فاصله داشته باشند.
        dedupe = hashlib.sha256(("%s|%s|%d|%s" % (sym, side, target // 60000, mode))
                                .encode("utf-8")).hexdigest()[:32]
        local = to_local(target)
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute(
                "INSERT INTO schedules(id,execution_id,symbol,isin,ins_code,full_name,side,"
                "price,quantity,order_type,validity,strategy,mode,target_ms,target_local,tz,"
                "state,dedupe_key,settings_version,created_at,updated_at,last_error) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (eid, eid, sym, ident, (ins_code or "").strip() or None,
                 (full_name or "").strip() or None, side, price_f, qty_f,
                 order_type, validity, strategy, mode, target, local, TZ_NAME,
                 ScheduleState.PREPARED.value, dedupe, int(settings_version),
                 at / 1000.0, at / 1000.0, ""))
            self._event(con, eid, "created", "schedule stored", ScheduleState.PREPARED.value, at / 1000.0)
            con.execute("COMMIT")
        except sqlite3.IntegrityError as e:
            con.execute("ROLLBACK")
            raise ScheduleError("DUPLICATE_SCHEDULE",
                                "یک زمان‌بندیِ فعال با همین نماد/سمت/هدف/حالت وجود دارد") from e
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        got = self.get(eid)
        if got is None:                          # pragma: no cover
            raise ScheduleError("STORE_ERROR", "سطر پس از درج پیدا نشد")
        return got

    def get(self, sid: str) -> ScheduleRecord | None:
        con = self._conn()
        try:
            r = con.execute("SELECT * FROM schedules WHERE id=?", (sid,)).fetchone()
            return _row(r) if r else None
        finally:
            con.close()

    def list(self, limit: int = 100) -> list[ScheduleRecord]:
        con = self._conn()
        try:
            rows = con.execute("SELECT * FROM schedules ORDER BY created_at DESC LIMIT ?",
                               (max(1, min(int(limit), 500)),)).fetchall()
            return [_row(r) for r in rows]
        finally:
            con.close()

    def events(self, sid: str) -> list[dict[str, Any]]:
        con = self._conn()
        try:
            rows = con.execute("SELECT seq,at_epoch,kind,detail,state FROM schedule_events "
                               "WHERE schedule_id=? ORDER BY seq", (sid,)).fetchall()
            return [{"seq": r["seq"], "at": r["at_epoch"], "kind": r["kind"],
                     "detail": r["detail"] or "", "state": r["state"] or ""} for r in rows]
        finally:
            con.close()

    def set_validation(self, sid: str, report: Mapping[str, Any], ok: bool,
                       error: str = "") -> ScheduleRecord:
        at = time.time()
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT state FROM schedules WHERE id=?", (sid,)).fetchone()
            if row is None:
                con.execute("ROLLBACK")
                raise ScheduleError("NOT_FOUND", "زمان‌بندی پیدا نشد")
            con.execute("UPDATE schedules SET last_validation=?, validation_ok=?, "
                        "last_error=?, updated_at=? WHERE id=?",
                        (json.dumps(dict(report), ensure_ascii=False),
                         1 if ok else 0, error[:500], at, sid))
            self._event(con, sid, "validation", error or ("ok" if ok else "failed"),
                        row["state"], at)
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        got = self.get(sid)
        if got is None:                          # pragma: no cover
            raise ScheduleError("NOT_FOUND", "زمان‌بندی پیدا نشد")
        return got

    def arm(self, sid: str, report: Mapping[str, Any], *, ok_for_arm: bool,
            at_ms: int | None = None) -> ScheduleRecord:
        at = (now_ms() if at_ms is None else int(at_ms)) / 1000.0
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            if not ok_for_arm:
                con.execute("UPDATE schedules SET last_validation=?, validation_ok=0, "
                            "last_error=?, updated_at=? WHERE id=?",
                            (json.dumps(dict(report), ensure_ascii=False),
                             "validation failed; not armed", at, sid))
                self._event(con, sid, "arm_refused", "validation failed", "PREPARED", at)
                con.execute("COMMIT")
                con.close()
                got = self.get(sid)
                if got is None:
                    raise ScheduleError("NOT_FOUND", "زمان‌بندی پیدا نشد")
                return got
            cur = con.execute(
                "UPDATE schedules SET state=?, armed_at=?, updated_at=?, last_validation=?, "
                "validation_ok=1, last_error='' WHERE id=? AND state=?",
                (ScheduleState.ARMED.value, at, at,
                 json.dumps(dict(report), ensure_ascii=False), sid,
                 ScheduleState.PREPARED.value))
            if cur.rowcount != 1:
                con.execute("ROLLBACK")
                raise ScheduleError("INVALID_TRANSITION", "فقط PREPARED را می‌توان مسلح کرد")
            self._event(con, sid, "armed", "owner armed the schedule", ScheduleState.ARMED.value, at)
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        got = self.get(sid)
        if got is None:                          # pragma: no cover
            raise ScheduleError("NOT_FOUND", "زمان‌بندی پیدا نشد")
        return got

    def cancel(self, sid: str, reason: str = "user", at_ms: int | None = None) -> ScheduleRecord:
        at = (now_ms() if at_ms is None else int(at_ms)) / 1000.0
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            cur = con.execute(
                "UPDATE schedules SET state=?, updated_at=?, last_error=? "
                "WHERE id=? AND state IN (?,?)",
                (ScheduleState.CANCELLED.value, at, ("cancelled: %s" % reason)[:500], sid,
                 ScheduleState.PREPARED.value, ScheduleState.ARMED.value))
            if cur.rowcount != 1:
                con.execute("ROLLBACK")
                raise ScheduleError("INVALID_TRANSITION",
                                    "لغو فقط پیش از اجرا (PREPARED/ARMED) مجاز است")
            self._event(con, sid, "cancelled", reason, ScheduleState.CANCELLED.value, at)
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        got = self.get(sid)
        if got is None:                          # pragma: no cover
            raise ScheduleError("NOT_FOUND", "زمان‌بندی پیدا نشد")
        return got

    def due_armed(self, at_ms: int) -> list[ScheduleRecord]:
        con = self._conn()
        try:
            rows = con.execute("SELECT * FROM schedules WHERE state=? AND target_ms<=? "
                               "ORDER BY target_ms LIMIT 50",
                               (ScheduleState.ARMED.value, int(at_ms))).fetchall()
            return [_row(r) for r in rows]
        finally:
            con.close()

    def claim(self, sid: str, token: str, at_ms: int) -> bool:
        at = int(at_ms) / 1000.0
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            cur = con.execute(
                "UPDATE schedules SET state=?, claim_token=?, claimed_at=?, updated_at=?, "
                "attempts=attempts+1 WHERE id=? AND state=? AND target_ms<=?",
                (ScheduleState.RUNNING.value, token, at, at, sid,
                 ScheduleState.ARMED.value, int(at_ms)))
            ok = cur.rowcount == 1
            if ok:
                self._event(con, sid, "claimed", "runner claimed the schedule",
                            ScheduleState.RUNNING.value, at)
            con.execute("COMMIT")
            return ok
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def begin_submit(self, sid: str, token: str, at_ms: int) -> bool:
        at = int(at_ms) / 1000.0
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            cur = con.execute(
                "UPDATE schedules SET state=?, updated_at=? "
                "WHERE id=? AND state=? AND claim_token=?",
                (ScheduleState.SUBMITTING.value, at, sid,
                 ScheduleState.RUNNING.value, token))
            ok = cur.rowcount == 1
            if ok:
                self._event(con, sid, "submitting", "one-shot submission claim",
                            ScheduleState.SUBMITTING.value, at)
            con.execute("COMMIT")
            return ok
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def finish(self, sid: str, token: str, state: str, result: Mapping[str, Any],
               at_ms: int | None = None, error: str = "") -> ScheduleRecord:
        target = state if state in (ScheduleState.DRY_RUN.value,
                                    ScheduleState.ACKNOWLEDGED.value,
                                    ScheduleState.REJECTED.value,
                                    ScheduleState.UNKNOWN.value,
                                    ScheduleState.NEEDS_REVIEW.value) else None
        if target is None:
            raise ScheduleError("INVALID_TRANSITION", "وضعیتِ پایانیِ نامعتبر")
        at = (now_ms() if at_ms is None else int(at_ms)) / 1000.0
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            cur = con.execute(
                "UPDATE schedules SET state=?, result=?, last_error=?, updated_at=? "
                "WHERE id=? AND state IN (?,?) AND claim_token=?",
                (target, json.dumps(dict(result), ensure_ascii=False), error[:500], at, sid,
                 ScheduleState.RUNNING.value, ScheduleState.SUBMITTING.value, token))
            if cur.rowcount != 1:
                con.execute("ROLLBACK")
                raise ScheduleError("INVALID_TRANSITION", "نتیجه فقط با claimِ همین اجرا ثبت می‌شود")
            self._event(con, sid, "finished", error or target, target, at)
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        got = self.get(sid)
        if got is None:                          # pragma: no cover
            raise ScheduleError("NOT_FOUND", "زمان‌بندی پیدا نشد")
        return got

    def needs_review(self, sid: str, reason: str, at_ms: int | None = None) -> ScheduleRecord:
        at = (now_ms() if at_ms is None else int(at_ms)) / 1000.0
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            cur = con.execute(
                "UPDATE schedules SET state=?, last_error=?, updated_at=? "
                "WHERE id=? AND state IN (?,?,?,?)",
                (ScheduleState.NEEDS_REVIEW.value, reason[:500], at, sid,
                 ScheduleState.PREPARED.value, ScheduleState.ARMED.value,
                 ScheduleState.RUNNING.value, ScheduleState.SUBMITTING.value))
            if cur.rowcount != 1:
                con.execute("ROLLBACK")
                raise ScheduleError("INVALID_TRANSITION", "این وضعیت نیازمند بازبینی نیست")
            self._event(con, sid, "needs_review", reason, ScheduleState.NEEDS_REVIEW.value, at)
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        got = self.get(sid)
        if got is None:                          # pragma: no cover
            raise ScheduleError("NOT_FOUND", "زمان‌بندی پیدا نشد")
        return got

    def mark_missed(self, sid: str, reason: str, at_ms: int | None = None) -> ScheduleRecord:
        at = (now_ms() if at_ms is None else int(at_ms)) / 1000.0
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            cur = con.execute(
                "UPDATE schedules SET state=?, last_error=?, updated_at=? "
                "WHERE id=? AND state IN (?,?)",
                (ScheduleState.MISSED_TARGET.value, reason[:500], at, sid,
                 ScheduleState.ARMED.value, ScheduleState.RUNNING.value))
            if cur.rowcount != 1:
                con.execute("ROLLBACK")
                raise ScheduleError("INVALID_TRANSITION", "این وضعیت قابل MISSED_TARGET نیست")
            self._event(con, sid, "missed_target", reason, ScheduleState.MISSED_TARGET.value, at)
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        got = self.get(sid)
        if got is None:                          # pragma: no cover
            raise ScheduleError("NOT_FOUND", "زمان‌بندی پیدا نشد")
        return got

    def expire(self, sid: str, reason: str, at_ms: int | None = None) -> ScheduleRecord:
        at = (now_ms() if at_ms is None else int(at_ms)) / 1000.0
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            cur = con.execute(
                "UPDATE schedules SET state=?, last_error=?, updated_at=? "
                "WHERE id=? AND state IN (?,?)",
                (ScheduleState.EXPIRED.value, reason[:500], at, sid,
                 ScheduleState.ARMED.value, ScheduleState.RUNNING.value))
            if cur.rowcount != 1:
                con.execute("ROLLBACK")
                raise ScheduleError("INVALID_TRANSITION", "این وضعیت قابل EXPIRED نیست")
            self._event(con, sid, "expired", reason, ScheduleState.EXPIRED.value, at)
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        got = self.get(sid)
        if got is None:                          # pragma: no cover
            raise ScheduleError("NOT_FOUND", "زمان‌بندی پیدا نشد")
        return got

    def reset_to_prepared(self, sid: str, at_ms: int | None = None) -> ScheduleRecord:
        at = (now_ms() if at_ms is None else int(at_ms))
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT target_ms FROM schedules WHERE id=?", (sid,)).fetchone()
            if row is None:
                con.execute("ROLLBACK")
                raise ScheduleError("NOT_FOUND", "زمان‌بندی پیدا نشد")
            if int(row["target_ms"]) <= at:
                con.execute("ROLLBACK")
                raise ScheduleError("TARGET_IN_PAST", "هدف گذشته است؛ زمان‌بندیِ تازه بسازید")
            cur = con.execute(
                "UPDATE schedules SET state=?, claim_token=NULL, claimed_at=NULL, "
                "last_error='', updated_at=? WHERE id=? AND state=?",
                (ScheduleState.PREPARED.value, at / 1000.0, sid,
                 ScheduleState.NEEDS_REVIEW.value))
            if cur.rowcount != 1:
                con.execute("ROLLBACK")
                raise ScheduleError("INVALID_TRANSITION", "فقط NEEDS_REVIEW قابل بازنشانی است")
            self._event(con, sid, "reset", "owner reviewed and reset to PREPARED",
                        ScheduleState.PREPARED.value, at / 1000.0)
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        got = self.get(sid)
        if got is None:                          # pragma: no cover
            raise ScheduleError("NOT_FOUND", "زمان‌بندی پیدا نشد")
        return got

    def recover(self, at_ms: int, max_lateness_ms: int) -> dict[str, Any]:
        """پس از restart: هیچ چیز خودکار اجرا نمی‌شود؛ ARMEDِ دیرشده MISSED_TARGET."""
        at = int(at_ms)
        counts = {"needs_review": 0, "missed": 0}
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            rows = con.execute("SELECT id,state,target_ms FROM schedules WHERE state IN (?,?,?,?)",
                               (ScheduleState.PREPARED.value, ScheduleState.ARMED.value,
                                ScheduleState.RUNNING.value, ScheduleState.SUBMITTING.value)).fetchall()
            for r in rows:
                sid = r["id"]
                missed = (r["state"] == ScheduleState.ARMED.value
                          and int(r["target_ms"]) + int(max_lateness_ms) < at)
                new_state = ScheduleState.MISSED_TARGET.value if missed else ScheduleState.NEEDS_REVIEW.value
                why = ("missed target during restart" if missed
                       else "recovered after restart; not auto-sent")
                con.execute("UPDATE schedules SET state=?, last_error=?, updated_at=? WHERE id=?",
                            (new_state, why, at / 1000.0, sid))
                self._event(con, sid, "recovered", why, new_state, at / 1000.0)
                counts["missed" if missed else "needs_review"] += 1
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        return counts

    def set_kill(self, reason: str) -> int:
        """قفلِ توقف: همهٔ ARMEDها به NEEDS_REVIEW می‌روند؛ RUNNING/SUBMITTING دست‌نخورده
        می‌مانند تا نتیجه‌شان از بین نرود (ستونِ halt خودِ سرویس جدا است)."""
        at = time.time()
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            rows = con.execute("SELECT id FROM schedules WHERE state=?",
                               (ScheduleState.ARMED.value,)).fetchall()
            for r in rows:
                con.execute("UPDATE schedules SET state=?, last_error=?, updated_at=? WHERE id=?",
                            (ScheduleState.NEEDS_REVIEW.value,
                             ("halt: %s" % reason)[:500], at, r["id"]))
                self._event(con, r["id"], "halted", reason, ScheduleState.NEEDS_REVIEW.value, at)
            con.execute("COMMIT")
            return len(rows)
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()


# ── تقویم معاملاتی ──────────────────────────────────────────────────────────
class CalendarStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class LocalTradingCalendar:
    """تاریخ‌های واقعیِ price_history = باز؛ پنجشنبه/جمعه = بسته؛ آیندهٔ نامعلوم = unknown.

    برای آیندهٔ نامعلوم عمداً «باز» حدس زده نمی‌شود؛ کنترلِ پیش از اجرا با unknown
    متوقف می‌شود.
    """
    def __init__(self, market_db: str) -> None:
        self.path = market_db

    def status(self, day: date) -> tuple[CalendarStatus, str]:
        if day.weekday() in (3, 4):
            return CalendarStatus.CLOSED, "weekday (Thu/Fri) closed locally"
        try:
            con = sqlite3.connect("file:%s?mode=ro" % self.path.replace("\\", "/"),
                                  uri=True, timeout=3)
            try:
                got = con.execute("SELECT 1 FROM price_history WHERE date=? LIMIT 1",
                                  (day.isoformat(),)).fetchone()
            finally:
                con.close()
            if got:
                return CalendarStatus.OPEN, "local price_history"
            return CalendarStatus.UNKNOWN, "future/unseen date; no verified calendar"
        except Exception as e:                  # noqa: BLE001
            return CalendarStatus.UNKNOWN, "calendar source unavailable: %s" % type(e).__name__


# ── facts و validator ──────────────────────────────────────────────────────
@dataclass
class DarvandFacts:
    symbol: str | None = None
    isin: str | None = None
    full_name: str | None = None
    identity_source: str = ""
    form_symbol: str | None = None
    form_opened_after_switch: bool | None = None
    price_min: float | None = None
    price_max: float | None = None
    tick: float | None = None
    price_source: str = ""
    price_as_of_ms: int | None = None
    qty_min: float | None = None
    qty_max: float | None = None
    buying_power_ok: bool | None = None
    buying_power_source: str = ""
    commission: float | None = None
    commission_source: str = ""
    session_ok: bool | None = None
    calendar_open: bool | None = None
    max_data_age_s: float = 300.0
    now_ms: int | None = None


@dataclass
class ValidationReport:
    static_ok: bool
    live_ready: bool
    checks: dict[str, dict[str, str]] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)

    def add(self, name: str, state: str, detail: str = "") -> None:
        self.checks[name] = {"state": state, "detail": detail[:300]}
        if state != PASS:
            self.blockers.append("%s: %s" % (name, detail or state))

    def ok_for_arm(self, mode: str) -> bool:
        return bool(self.static_ok and (mode != "live" or self.live_ready))

    def to_dict(self) -> dict[str, Any]:
        return {"static_ok": self.static_ok, "live_ready": self.live_ready,
                "checks": dict(self.checks), "blockers": list(self.blockers),
                "facts": dict(self.facts)}


def _state(ok: bool | None) -> str:
    return UNKNOWN if ok is None else (PASS if ok else FAIL)


def validate_darvand(rec: ScheduleRecord, facts: DarvandFacts, *,
                     now: int | None = None, require_live: bool = True,
                     check_target_future: bool = False,
                     expected_symbol: str = DEFAULT_SYMBOL,
                     expected_name: str = DEFAULT_FULL_NAME) -> ValidationReport:
    at = now_ms() if now is None else int(now)
    report = ValidationReport(static_ok=True, live_ready=False)
    static_ok = True

    def static(name: str, ok: bool, detail: str = "") -> None:
        nonlocal static_ok
        report.add(name, PASS if ok else FAIL, detail)
        if not ok:
            static_ok = False

    static("record_symbol", rec.symbol == expected_symbol,
           "symbol=%r expected=%r" % (rec.symbol, expected_symbol))
    static("record_isin", bool((rec.isin or "").strip()), "ISIN required")
    static("record_price", rec.price > 0, "price must be positive")
    static("record_quantity", rec.quantity > 0 and rec.quantity == int(rec.quantity),
           "quantity must be a positive integer")
    if check_target_future:
        static("record_target", rec.target_ms > at, "target must be in the future")
    else:
        static("record_target", True, "execution context; runner owns lateness")
    static("identity_symbol", facts.symbol == rec.symbol,
           "live identity symbol=%r" % (facts.symbol,))
    static("identity_isin", (facts.isin or "").upper() == rec.isin.upper(),
           "live identity isin=%r" % (facts.isin,))
    static("identity_name", norm_text(expected_name) in norm_text(facts.full_name),
           "full name=%r" % (facts.full_name,))

    # کنترل‌های زنده (برای live لازم، برای dry-run شفاف اما غیرمسدودکننده)
    report.add("form_symbol", _state(None if facts.form_symbol is None
                                     else facts.form_symbol == rec.symbol),
               "form header=%r" % (facts.form_symbol,))
    report.add("form_reopened", _state(facts.form_opened_after_switch),
               "form opened after symbol switch")
    band_ok = None
    if None not in (facts.price_min, facts.price_max):
        band_ok = float(facts.price_min) <= rec.price <= float(facts.price_max)
    report.add("price_band", _state(band_ok),
               "range=%r..%r price=%r" % (facts.price_min, facts.price_max, rec.price))
    tick_ok = None
    if facts.tick is not None and facts.tick > 0 and facts.price_min is not None:
        tick_ok = abs((rec.price - float(facts.price_min)) % float(facts.tick)) < 1e-9
    report.add("price_tick", _state(tick_ok), "tick=%r" % (facts.tick,))
    qty_ok = None
    if facts.qty_min is not None and facts.qty_max is not None:
        qty_ok = float(facts.qty_min) <= rec.quantity <= float(facts.qty_max)
    report.add("quantity_limit", _state(qty_ok),
               "range=%r..%r" % (facts.qty_min, facts.qty_max))
    value_ok = None
    if facts.commission is not None and facts.buying_power_ok is not None:
        value_ok = bool(facts.buying_power_ok)
    report.add("buying_power", _state(value_ok),
               "source=%r" % (facts.buying_power_source,))
    report.add("commission", _state(None if facts.commission is None
                                    else facts.commission >= 0),
               "source=%r" % (facts.commission_source,))
    report.add("session", _state(facts.session_ok), "session must be verified")
    report.add("calendar", _state(facts.calendar_open), "trading calendar")
    fresh_ok = None
    if facts.price_as_of_ms is not None:
        age_s = max(0.0, (at - int(facts.price_as_of_ms)) / 1000.0)
        fresh_ok = age_s <= float(facts.max_data_age_s)
    report.add("data_fresh", _state(fresh_ok),
               "age<=%ss" % (facts.max_data_age_s,))

    live_ready = static_ok and all(
        report.checks.get(k, {}).get("state") == PASS
        for k in ("form_symbol", "form_reopened", "price_band", "price_tick",
                  "quantity_limit", "buying_power", "commission", "session",
                  "calendar", "data_fresh"))
    report.static_ok = static_ok
    report.live_ready = bool(live_ready)
    report.facts = {
        "symbol": facts.symbol, "isin": facts.isin, "full_name": facts.full_name,
        "identity_source": facts.identity_source,
        "form_symbol": facts.form_symbol,
        "price_min": facts.price_min, "price_max": facts.price_max,
        "tick": facts.tick, "price_source": facts.price_source,
        "qty_min": facts.qty_min, "qty_max": facts.qty_max,
        "buying_power_source": facts.buying_power_source,
        "commission": facts.commission,
        "session_ok": facts.session_ok, "calendar_open": facts.calendar_open,
        "data_age_s": (None if facts.price_as_of_ms is None
                       else max(0.0, (at - int(facts.price_as_of_ms)) / 1000.0)),
    }
    # در dry-run، ناشناخته‌های زنده «blocker» گزارش می‌شوند ولی ارسال زنده ممنوع است.
    if require_live and not live_ready:
        report.blockers = [b for b in report.blockers if b]
    return report


def local_identity_facts(market_db: str, symbol: str) -> DarvandFacts:
    """شناسهٔ مستقل از UI: symbol/name/ISIN از بانکِ محلی (فقط‌خواندنی)."""
    try:
        con = sqlite3.connect("file:%s?mode=ro" % market_db.replace("\\", "/"),
                              uri=True, timeout=3)
        con.row_factory = sqlite3.Row
        try:
            row = con.execute(
                "SELECT symbol,name,isin,ins_code FROM pipeline_instrument WHERE symbol=?",
                (symbol,)).fetchone()
            if row is None:
                row = con.execute(
                    "SELECT l_val18 AS symbol,l_val30 AS name,isin,ins_code "
                    "FROM instruments WHERE l_val18=?", (symbol,)).fetchone()
        finally:
            con.close()
        if row is None:
            return DarvandFacts(symbol=symbol, identity_source="market.db:not-found")
        return DarvandFacts(symbol=row["symbol"], isin=row["isin"],
                            full_name=row["name"],
                            identity_source="market.db:pipeline_instrument/instruments")
    except Exception as e:                      # noqa: BLE001
        return DarvandFacts(symbol=symbol,
                            identity_source="market.db:unavailable:%s" % type(e).__name__)


class LocalFactsProvider:
    """تنها factsِ موجود در محصولِ امروز: هویتِ محلی؛ بقیه UNKNOWN تا منبعِ معتبر بیاید."""
    def __init__(self, market_db: str, calendar: LocalTradingCalendar | None = None) -> None:
        self.market_db = market_db
        self.calendar = calendar

    def __call__(self, rec: ScheduleRecord, at_ms: int | None = None) -> DarvandFacts:
        facts = local_identity_facts(self.market_db, rec.symbol)
        if self.calendar is not None:
            day = datetime.fromtimestamp(rec.target_ms / 1000.0, TEHRAN).date()
            status, _why = self.calendar.status(day)
            facts.calendar_open = (True if status is CalendarStatus.OPEN else
                                   (False if status is CalendarStatus.CLOSED else None))
        facts.now_ms = now_ms() if at_ms is None else int(at_ms)
        return facts


# ── اجرا ───────────────────────────────────────────────────────────────────
@dataclass
class ExecutionOutcome:
    state: str
    detail: str = ""
    result: dict[str, Any] = field(default_factory=dict)


class DryRunExecutor:
    """هیچ شبکه/مرورگری صدا نمی‌زند؛ فقط زمان‌بندی و کنترل‌ها را ثبت می‌کند."""
    def __call__(self, rec: ScheduleRecord, report: ValidationReport) -> ExecutionOutcome:
        return ExecutionOutcome(
            ScheduleState.DRY_RUN.value,
            "dry-run: no order request was sent",
            {"dry_run": True, "live": False, "validation": report.to_dict()})


class ScheduleRunner:
    def __init__(self, store: ScheduleStore, facts_provider: Callable[..., DarvandFacts],
                 calendar: LocalTradingCalendar | None = None,
                 executor: Callable[[ScheduleRecord, ValidationReport], ExecutionOutcome] | None = None,
                 clock_ms: Callable[[], int] = now_ms,
                 clock_ok: Callable[[], tuple[bool, str]] | None = None,
                 halted: Callable[[], tuple[bool, str]] | None = None,
                 max_lateness_s: float = 60.0, poll_s: float = 0.5,
                 live_enabled: bool = False, contract_verified: bool = False) -> None:
        self.store = store
        self.facts_provider = facts_provider
        self.calendar = calendar
        self.executor = executor or DryRunExecutor()
        self.clock_ms = clock_ms
        self.clock_ok = clock_ok
        self.halted = halted or (lambda: (False, ""))
        self.max_lateness_ms = int(max(1.0, max_lateness_s) * 1000)
        self.poll_s = max(0.05, float(poll_s))
        self.live_enabled = bool(live_enabled)
        self.contract_verified = bool(contract_verified)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error = ""
        self.last_tick: dict[str, Any] = {}

    def _halt_pair(self) -> tuple[bool, str]:
        got = self.halted()
        if isinstance(got, tuple) and len(got) == 2:
            return bool(got[0]), str(got[1])
        return bool(got), ""

    def recover(self) -> dict[str, Any]:
        return self.store.recover(self.clock_ms(), self.max_lateness_ms)

    def start(self) -> None:
        if self._thread is not None:
            return
        self.recover()
        self._thread = threading.Thread(target=self._loop, name="bors-schedule-runner",
                                        daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as e:              # noqa: BLE001
                self.last_error = "%s: %s" % (type(e).__name__, str(e)[:200])
            self._stop.wait(self.poll_s)

    def tick(self, at_ms: int | None = None) -> dict[str, Any]:
        at = self.clock_ms() if at_ms is None else int(at_ms)
        out: dict[str, Any] = {"at": at, "processed": [], "skipped": []}
        stopped, why = self._halt_pair()
        for rec in self.store.due_armed(at):
            if stopped:
                self.store.needs_review(rec.id, "halt: %s" % why, at)
                out["processed"].append({"id": rec.id, "state": ScheduleState.NEEDS_REVIEW.value})
                continue
            if at - rec.target_ms > self.max_lateness_ms:
                self.store.mark_missed(rec.id,
                                       "late by %dms > %dms; no catch-up"
                                       % (at - rec.target_ms, self.max_lateness_ms), at)
                out["processed"].append({"id": rec.id, "state": ScheduleState.MISSED_TARGET.value})
                continue
            token = uuid.uuid4().hex
            if not self.store.claim(rec.id, token, at):
                out["skipped"].append({"id": rec.id, "reason": "claim lost"})
                continue
            stopped, why = self._halt_pair()
            if stopped:
                self.store.needs_review(rec.id, "halt after claim: %s" % why, at)
                out["processed"].append({"id": rec.id, "state": ScheduleState.NEEDS_REVIEW.value})
                continue
            try:
                facts = self.facts_provider(rec, at)
                report = validate_darvand(rec, facts, now=at,
                                          require_live=(rec.mode == "live"))
                if not report.static_ok:
                    self.store.needs_review(rec.id, "validation: " +
                                            "; ".join(report.blockers[:4]), at)
                    out["processed"].append({"id": rec.id, "state": ScheduleState.NEEDS_REVIEW.value})
                    continue
                if rec.mode == "live":
                    ok_clock, clock_why = (self.clock_ok() if self.clock_ok
                                           else (False, "clock source unknown"))
                    blockers = []
                    if not self.live_enabled:
                        blockers.append("live executor disabled")
                    if not self.contract_verified:
                        blockers.append("order contract not verified")
                    if not report.live_ready:
                        blockers.extend(report.blockers[:4])
                    if not ok_clock:
                        blockers.append("clock: %s" % clock_why)
                    if self.calendar is not None:
                        day = datetime.fromtimestamp(rec.target_ms / 1000.0, TEHRAN).date()
                        cst, cwhy = self.calendar.status(day)
                        if cst is CalendarStatus.CLOSED:
                            self.store.expire(rec.id, "calendar: %s (%s)" % (cst.value, cwhy), at)
                            out["processed"].append({"id": rec.id, "state": ScheduleState.EXPIRED.value})
                            continue
                        if cst is CalendarStatus.UNKNOWN:
                            blockers.append("calendar: %s (%s)" % (cst.value, cwhy))
                    if blockers:
                        self.store.needs_review(rec.id, "live blocked: " + "; ".join(blockers), at)
                        out["processed"].append({"id": rec.id, "state": ScheduleState.NEEDS_REVIEW.value})
                        continue
                    stopped2, why2 = self._halt_pair()
                    if stopped2:
                        self.store.needs_review(rec.id, "halt before submit: %s" % why2, at)
                        out["processed"].append({"id": rec.id, "state": ScheduleState.NEEDS_REVIEW.value})
                        continue
                    if not self.store.begin_submit(rec.id, token, at):
                        out["skipped"].append({"id": rec.id, "reason": "submit claim lost"})
                        continue
                    outcome = self.executor(rec, report)
                    state = outcome.state if outcome.state in (
                        ScheduleState.ACKNOWLEDGED.value, ScheduleState.REJECTED.value,
                        ScheduleState.UNKNOWN.value, ScheduleState.NEEDS_REVIEW.value) else ScheduleState.UNKNOWN.value
                    self.store.finish(rec.id, token, state, outcome.result,
                                      at_ms=at, error=outcome.detail)
                else:
                    outcome = self.executor(rec, report)
                    state = outcome.state if outcome.state in (
                        ScheduleState.DRY_RUN.value, ScheduleState.REJECTED.value,
                        ScheduleState.UNKNOWN.value, ScheduleState.NEEDS_REVIEW.value) else ScheduleState.DRY_RUN.value
                    self.store.finish(rec.id, token, state, outcome.result,
                                      at_ms=at, error=outcome.detail)
                out["processed"].append({"id": rec.id, "state": state})
            except Exception as e:              # noqa: BLE001
                self.store.needs_review(rec.id, "runner error: %s" % type(e).__name__, at)
                out["processed"].append({"id": rec.id, "state": ScheduleState.NEEDS_REVIEW.value,
                                         "error": type(e).__name__})
        self.last_tick = out
        return out


def default_store_path(work_dir: str) -> str:
    return os.path.join(work_dir, "execution_schedules.db")


def readiness() -> dict[str, Any]:
    """وضعیتِ صادقانهٔ مسیرِ زنده؛ dry-run جداست و «آمادهٔ ارسال» نیست."""
    blockers = [
        {"code": "SESSION_PERSISTENCE",
         "detail": "نشست EasyTrader در sessionStorage است؛ بستن/restart آن را از بین می‌برد"},
        {"code": "SESSION_PROVIDER",
         "detail": "هیچ providerِ احرازِ هویتِ پایدار و مجاز وصل نیست"},
        {"code": "ORDER_CONTRACT",
         "detail": "WIRE_HYPOTHESIS=True؛ هیچ پاسخِ ثبتِ واقعی مشاهده نشده"},
        {"code": "LIVE_EXECUTOR",
         "detail": "executorِ زنده عمداً وصل نیست"},
        {"code": "BALANCE_SOURCE",
         "detail": "قدرت خرید از کارگزاری در دسترس نیست"},
        {"code": "FORM_SELECTORS",
         "detail": "selectorهای پایدارِ هدر/فرم هنوز تأیید نشده‌اند"},
        {"code": "CALENDAR",
         "detail": "تقویمِ آینده فقط از price_history محلی؛ روزهای آینده unknown"},
    ]
    return {"live_ready": False, "dry_run_scheduling": True,
            "executor": "dry_run", "blockers": blockers}


__all__ = [
    "TEHRAN", "TZ_NAME", "ScheduleState", "ScheduleStore", "ScheduleRecord",
    "ScheduleError", "CalendarStatus", "LocalTradingCalendar", "DarvandFacts",
    "ValidationReport", "validate_darvand", "local_identity_facts",
    "LocalFactsProvider", "DryRunExecutor", "ScheduleRunner", "ExecutionOutcome",
    "default_store_path", "readiness", "parse_local", "to_local", "now_ms",
    "ResultState", "canonical_result",
]
