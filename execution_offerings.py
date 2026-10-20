# -*- coding: utf-8 -*-
"""execution_offerings.py — چند عرضهٔ اولیه: داده، بودجه، Preflight و زمان.

قفل‌ها:
  ۱) هیچ نماد/روش/قیمت/سهمیه‌ای از نامِ نماد حدس زده نمی‌شود؛ هر رکورد منبع،
     زمانِ تأیید و زمانِ داده دارد و نبودشان UNKNOWN است.
  ۲) رزرو بودجه اتمیک است (SQLite BEGIN IMMEDIATE)؛ مجموعِ رزروهایِ فعال هرگز
     از سقفِ مجاز/ذخیرهٔ نقدی بیشتر نمی‌شود.
  ۳) هر عرضه حداکثر یک رزروِ فعال دارد؛ intent تکراری رزرو دوم نمی‌سازد.
  ۴) UNKNOWN رزرو را به UNKNOWN_HOLD نگه می‌دارد؛ آزادسازی خودکار/retry نیست.
  ۵) Timing از نمونه‌هایِ واقعی است؛ HTTP RTT جایِ زمانِ پذیرشِ کارگزاری نیست و
     برای BOOK_BUILDING/TWO_STAGE مزیتِ زمانی ادعا نمی‌شود.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from execution_timing import percentile

SCHEMA_VERSION = 1
PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"


def now_ms() -> int:
    return int(time.time() * 1000)


class OfferingMethod(str, Enum):
    BOOK_BUILDING = "BOOK_BUILDING"
    TWO_STAGE = "TWO_STAGE"
    AUCTION = "AUCTION"
    FIRST_LISTING_QUEUE = "FIRST_LISTING_QUEUE"
    UNKNOWN = "UNKNOWN"


METHODS = tuple(m.value for m in OfferingMethod)
METHOD_TIMING = {
    "BOOK_BUILDING": ("NOT_PROVEN", "تخصیص بر قاعدهٔ دورهٔ عرضه است؛ مزیتِ چند میلی‌ثانیه اثبات نشده"),
    "TWO_STAGE": ("NOT_PROVEN", "تخصیص دومرحله‌ای است؛ مزیتِ ارسالِ زودتر اثبات نشده"),
    "AUCTION": ("UNPROVEN", "حراج ممکن است حساس باشد، ولی آستانه/مزیت اندازه‌گیری نشده"),
    "FIRST_LISTING_QUEUE": ("QUEUE_SENSITIVE_UNPROVEN", "صف محتمل حساس است؛ جایگاه/اول‌شدن تضمین نمی‌شود"),
    "UNKNOWN": ("UNKNOWN", "روشِ عرضه تأیید نشده؛ هیچ ادعای زمانی مجاز نیست"),
}


class ReservationState(str, Enum):
    RESERVED = "RESERVED"
    COMMITTED = "COMMITTED"
    RELEASED = "RELEASED"
    UNKNOWN_HOLD = "UNKNOWN_HOLD"
    SKIPPED_BUDGET = "SKIPPED_BUDGET"


ACTIVE_RESERVATION_STATES = (
    ReservationState.RESERVED.value, ReservationState.COMMITTED.value,
    ReservationState.UNKNOWN_HOLD.value)


class OfferingsError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__("%s: %s" % (code, detail) if detail else code)
        self.code = code
        self.detail = detail


def _norm_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u064a", "\u06cc")
                    .replace("\u0643", "\u06a9").split()).casefold()


@dataclass
class OfferingRecord:
    id: str
    symbol: str
    isin: str
    market: str
    method: str
    start_ms: int | None
    end_ms: int | None
    price_min: float | None
    price_max: float | None
    price_source: str
    min_qty: float | None
    max_qty: float | None
    per_code_quota: float | None
    fee_rate: float | None
    fee_source: str
    source: str
    source_url: str
    verified_at_ms: int | None
    data_as_of_ms: int | None
    status: str
    timing_relevance: str
    timing_note: str
    note: str
    created_at: float
    updated_at: float

    def public(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in (
            "id", "symbol", "isin", "market", "method", "start_ms", "end_ms",
            "price_min", "price_max", "price_source", "min_qty", "max_qty",
            "per_code_quota", "fee_rate", "fee_source", "source", "source_url",
            "verified_at_ms", "data_as_of_ms", "status", "timing_relevance",
            "timing_note", "note", "created_at", "updated_at")}


def _row(r: sqlite3.Row) -> OfferingRecord:
    return OfferingRecord(
        id=r["id"], symbol=r["symbol"], isin=r["isin"], market=r["market"],
        method=r["method"], start_ms=r["start_ms"], end_ms=r["end_ms"],
        price_min=r["price_min"], price_max=r["price_max"],
        price_source=r["price_source"] or "", min_qty=r["min_qty"],
        max_qty=r["max_qty"], per_code_quota=r["per_code_quota"],
        fee_rate=r["fee_rate"], fee_source=r["fee_source"] or "",
        source=r["source"] or "", source_url=r["source_url"] or "",
        verified_at_ms=r["verified_at_ms"], data_as_of_ms=r["data_as_of_ms"],
        status=r["status"] or "UNKNOWN", timing_relevance=r["timing_relevance"] or "UNKNOWN",
        timing_note=r["timing_note"] or "", note=r["note"] or "",
        created_at=float(r["created_at"]), updated_at=float(r["updated_at"]))


_SCHEMA = """
CREATE TABLE IF NOT EXISTS offerings (
  id TEXT PRIMARY KEY, symbol TEXT NOT NULL, isin TEXT NOT NULL,
  market TEXT NOT NULL DEFAULT 'UNKNOWN', method TEXT NOT NULL DEFAULT 'UNKNOWN',
  start_ms INTEGER, end_ms INTEGER, price_min REAL, price_max REAL,
  price_source TEXT DEFAULT '', min_qty REAL, max_qty REAL, per_code_quota REAL,
  fee_rate REAL, fee_source TEXT DEFAULT '', source TEXT NOT NULL DEFAULT '',
  source_url TEXT DEFAULT '', verified_at_ms INTEGER, data_as_of_ms INTEGER,
  status TEXT NOT NULL DEFAULT 'UNKNOWN', timing_relevance TEXT NOT NULL DEFAULT 'UNKNOWN',
  timing_note TEXT DEFAULT '', note TEXT DEFAULT '', created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_offerings_symbol_isin
  ON offerings(symbol, isin);
CREATE TABLE IF NOT EXISTS capital_settings (
  id INTEGER PRIMARY KEY CHECK (id=1),
  total_cap REAL NOT NULL, cash_reserve REAL NOT NULL DEFAULT 0,
  max_per_offering REAL NOT NULL, priorities_json TEXT NOT NULL DEFAULT '{}',
  version INTEGER NOT NULL DEFAULT 1, updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS reservations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  offering_id TEXT NOT NULL, intent_id TEXT NOT NULL,
  amount REAL NOT NULL, price REAL NOT NULL, quantity REAL NOT NULL,
  fee REAL NOT NULL DEFAULT 0, state TEXT NOT NULL,
  note TEXT DEFAULT '', created_at REAL NOT NULL, updated_at REAL NOT NULL,
  UNIQUE(offering_id, intent_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_reservation_active_offering
  ON reservations(offering_id)
  WHERE state IN ('RESERVED','COMMITTED','UNKNOWN_HOLD');
CREATE TABLE IF NOT EXISTS allocation_decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, offering_id TEXT NOT NULL,
  intent_id TEXT NOT NULL, state TEXT NOT NULL, amount REAL,
  reason TEXT DEFAULT '', at_epoch REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS timing_samples (
  id INTEGER PRIMARY KEY AUTOINCREMENT, adapter TEXT NOT NULL,
  method TEXT NOT NULL, network TEXT NOT NULL DEFAULT 'unknown',
  phase TEXT NOT NULL DEFAULT 'http_rtt', value_ms REAL NOT NULL,
  source TEXT NOT NULL, observed_at REAL NOT NULL, note TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS offering_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class OfferingStore:
    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        self._lock = threading.Lock()
        con = self._conn()
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=FULL")
            con.executescript(_SCHEMA)
            con.execute("INSERT OR IGNORE INTO offering_meta(key,value) "
                        "VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
        finally:
            con.close()

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=5000")
        return con

    def upsert(self, *, symbol: str, isin: str, method: str = "UNKNOWN",
               market: str = "UNKNOWN", start_ms: int | None = None,
               end_ms: int | None = None, price_min: float | None = None,
               price_max: float | None = None, price_source: str = "",
               min_qty: float | None = None, max_qty: float | None = None,
               per_code_quota: float | None = None, fee_rate: float | None = None,
               fee_source: str = "", source: str = "", source_url: str = "",
               verified_at_ms: int | None = None, data_as_of_ms: int | None = None,
               note: str = "", offering_id: str = "") -> OfferingRecord:
        sym, ident = (symbol or "").strip(), (isin or "").strip().upper()
        if not sym or not ident:
            raise OfferingsError("INVALID_IDENTITY", "نماد و ISIN لازم‌اند")
        method = str(method or "UNKNOWN").upper()
        if method not in METHODS:
            raise OfferingsError("INVALID_METHOD", "روش عرضه نامعتبر است")
        relevance, timing_note = METHOD_TIMING[method]
        status = ("VERIFIED" if (source and verified_at_ms and data_as_of_ms)
                  else "UNVERIFIED")
        at = now_ms() / 1000.0
        oid = (offering_id or "").strip() or "off-%s-%s" % (sym, ident[-4:].lower())
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute(
                "INSERT INTO offerings(id,symbol,isin,market,method,start_ms,end_ms,"
                "price_min,price_max,price_source,min_qty,max_qty,per_code_quota,"
                "fee_rate,fee_source,source,source_url,verified_at_ms,data_as_of_ms,"
                "status,timing_relevance,timing_note,note,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(symbol,isin) DO UPDATE SET market=excluded.market,"
                "method=excluded.method,start_ms=excluded.start_ms,end_ms=excluded.end_ms,"
                "price_min=excluded.price_min,price_max=excluded.price_max,"
                "price_source=excluded.price_source,min_qty=excluded.min_qty,"
                "max_qty=excluded.max_qty,per_code_quota=excluded.per_code_quota,"
                "fee_rate=excluded.fee_rate,fee_source=excluded.fee_source,"
                "source=excluded.source,source_url=excluded.source_url,"
                "verified_at_ms=excluded.verified_at_ms,data_as_of_ms=excluded.data_as_of_ms,"
                "status=excluded.status,timing_relevance=excluded.timing_relevance,"
                "timing_note=excluded.timing_note,note=excluded.note,updated_at=excluded.updated_at",
                (oid, sym, ident, str(market or "UNKNOWN"), method, start_ms, end_ms,
                 price_min, price_max, price_source or "", min_qty, max_qty,
                 per_code_quota, fee_rate, fee_source or "", source or "", source_url or "",
                 verified_at_ms, data_as_of_ms, status, relevance, timing_note,
                 note or "", at, at))
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        got = self.get_by_identity(sym, ident)
        if got is None:                          # pragma: no cover
            raise OfferingsError("STORE_ERROR", "عرضه پس از درج پیدا نشد")
        return got

    def get(self, oid: str) -> OfferingRecord | None:
        con = self._conn()
        try:
            r = con.execute("SELECT * FROM offerings WHERE id=?", (oid,)).fetchone()
            return _row(r) if r else None
        finally:
            con.close()

    def get_by_identity(self, symbol: str, isin: str) -> OfferingRecord | None:
        con = self._conn()
        try:
            r = con.execute("SELECT * FROM offerings WHERE symbol=? AND isin=?",
                            (symbol, isin.upper())).fetchone()
            return _row(r) if r else None
        finally:
            con.close()

    def list(self, limit: int = 100) -> list[OfferingRecord]:
        con = self._conn()
        try:
            rows = con.execute("SELECT * FROM offerings ORDER BY start_ms, symbol "
                               "LIMIT ?", (max(1, min(int(limit), 500)),)).fetchall()
            return [_row(r) for r in rows]
        finally:
            con.close()

    def capital(self) -> dict[str, Any]:
        con = self._conn()
        try:
            r = con.execute("SELECT * FROM capital_settings WHERE id=1").fetchone()
        finally:
            con.close()
        if r is None:
            return {"total_cap": None, "cash_reserve": None, "max_per_offering": None,
                    "priorities": {}, "version": 0, "updated_at": None}
        return {"total_cap": float(r["total_cap"]), "cash_reserve": float(r["cash_reserve"]),
                "max_per_offering": float(r["max_per_offering"]),
                "priorities": json.loads(r["priorities_json"] or "{}"),
                "version": int(r["version"]), "updated_at": r["updated_at"]}

    def set_capital(self, *, total_cap: float, cash_reserve: float,
                    max_per_offering: float, priorities: Mapping[str, Any] | None = None,
                    at_ms: int | None = None) -> dict[str, Any]:
        try:
            cap, reserve, per = float(total_cap), float(cash_reserve), float(max_per_offering)
        except (TypeError, ValueError):
            raise OfferingsError("INVALID_BUDGET", "اعداد بودجه نامعتبرند") from None
        if cap <= 0 or reserve < 0 or reserve >= cap or per <= 0:
            raise OfferingsError("INVALID_BUDGET", "سقف/ذخیره/سقفِ هر عرضه نامعتبر است")
        if per > cap:
            raise OfferingsError("INVALID_BUDGET", "سقفِ هر عرضه از سقف کل بیشتر است")
        pri = dict(priorities or {})
        for k, v in pri.items():
            try:
                int(v)
            except (TypeError, ValueError):
                raise OfferingsError("INVALID_PRIORITY", "اولویت باید عدد باشد") from None
        at = (now_ms() if at_ms is None else int(at_ms)) / 1000.0
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute(
                "INSERT INTO capital_settings(id,total_cap,cash_reserve,max_per_offering,"
                "priorities_json,version,updated_at) VALUES(1,?,?,?,?,1,?) "
                "ON CONFLICT(id) DO UPDATE SET total_cap=excluded.total_cap,"
                "cash_reserve=excluded.cash_reserve,max_per_offering=excluded.max_per_offering,"
                "priorities_json=excluded.priorities_json,"
                "version=capital_settings.version+1,updated_at=excluded.updated_at",
                (cap, reserve, per, json.dumps(pri, ensure_ascii=False), at))
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        return self.capital()

    def active_reserved(self) -> float:
        con = self._conn()
        try:
            r = con.execute("SELECT COALESCE(SUM(amount),0) FROM reservations "
                            "WHERE state IN (?,?,?)", ACTIVE_RESERVATION_STATES).fetchone()
            return float(r[0] or 0.0)
        finally:
            con.close()

    def reservations(self, offering_id: str | None = None) -> list[dict[str, Any]]:
        con = self._conn()
        try:
            if offering_id:
                rows = con.execute("SELECT * FROM reservations WHERE offering_id=? "
                                   "ORDER BY id DESC", (offering_id,)).fetchall()
            else:
                rows = con.execute("SELECT * FROM reservations ORDER BY id DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def decide(self, offering_id: str, intent_id: str, state: str,
               amount: float | None, reason: str, at_ms: int | None = None) -> None:
        at = (now_ms() if at_ms is None else int(at_ms)) / 1000.0
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute("INSERT INTO allocation_decisions(offering_id,intent_id,state,"
                        "amount,reason,at_epoch) VALUES(?,?,?,?,?,?)",
                        (offering_id, intent_id, state, amount, reason[:400], at))
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def plan(self, plans: Iterable[Mapping[str, Any]], *, now: int | None = None,
             max_age_s: float = 3600.0) -> dict[str, Any]:
        """رزروِ چند عرضه در یک تراکنش؛ اولویت‌ها از capital_settings."""
        at = now_ms() if now is None else int(now)
        cap = self.capital()
        if cap.get("total_cap") is None:
            raise OfferingsError("BUDGET_UNSET", "سقف بودجه تنظیم نشده است")
        items = [dict(p) for p in plans]
        pri = cap.get("priorities") or {}
        def pkey(p):
            try:
                return int(pri.get(str(p.get("offering_id") or ""))
                           or pri.get(str(p.get("symbol") or "")) or 100)
            except (TypeError, ValueError):
                return 100
        items.sort(key=pkey)
        decisions: list[dict[str, Any]] = []
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            used = float(con.execute(
                "SELECT COALESCE(SUM(amount),0) FROM reservations "
                "WHERE state IN (?,?,?)", ACTIVE_RESERVATION_STATES).fetchone()[0] or 0.0)
            available = max(0.0, float(cap["total_cap"]) - float(cap["cash_reserve"]) - used)
            for p in items:
                oid = str(p.get("offering_id") or "")
                intent = str(p.get("intent_id") or "")
                offer = None
                r = con.execute("SELECT * FROM offerings WHERE id=?", (oid,)).fetchone()
                if r:
                    offer = _row(r)
                if offer is None:
                    decisions.append(self._decision_in_tx(con, oid, intent, "BLOCKED",
                                                          None, "OFFERING_NOT_FOUND", at))
                    continue
                try:
                    price = float(p.get("price"))
                    qty = float(p.get("quantity"))
                except (TypeError, ValueError):
                    decisions.append(self._decision_in_tx(con, oid, intent, "BLOCKED",
                                                          None, "INVALID_ORDER", at))
                    continue
                rep = preflight(offer, at=at, price=price, quantity=qty,
                                max_age_s=max_age_s, capital=None, reserved=0.0)
                if not rep["ok"]:
                    decisions.append(self._decision_in_tx(
                        con, oid, intent, "BLOCKED", rep.get("amount"),
                        "; ".join(rep["blockers"][:4]), at))
                    continue
                amount = float(rep["amount"])
                if amount > float(cap["max_per_offering"]):
                    decisions.append(self._decision_in_tx(
                        con, oid, intent, "SKIPPED_BUDGET", amount,
                        "MAX_PER_OFFERING", at))
                    continue
                if amount > available + 1e-9:
                    decisions.append(self._decision_in_tx(
                        con, oid, intent, "SKIPPED_BUDGET", amount,
                        "INSUFFICIENT_CAPITAL", at))
                    continue
                exists = con.execute(
                    "SELECT 1 FROM reservations WHERE offering_id=? AND state IN (?,?,?)",
                    (oid,) + ACTIVE_RESERVATION_STATES).fetchone()
                if exists:
                    decisions.append(self._decision_in_tx(
                        con, oid, intent, "SKIPPED_BUDGET", amount,
                        "OFFERING_ALREADY_RESERVED", at))
                    continue
                ts = at / 1000.0
                con.execute(
                    "INSERT INTO reservations(offering_id,intent_id,amount,price,quantity,"
                    "fee,state,note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (oid, intent, amount, price, qty, float(rep.get("fee") or 0.0),
                     ReservationState.RESERVED.value, "", ts, ts))
                decisions.append(self._decision_in_tx(
                    con, oid, intent, "RESERVED", amount, "", at))
                used += amount
                available = max(0.0, available - amount)
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        return {"decisions": decisions, "reserved_total": round(self.active_reserved(), 2),
                "available": round(max(0.0, float(cap["total_cap"]) - float(cap["cash_reserve"])
                                       - self.active_reserved()), 2),
                "capital": cap}

    @staticmethod
    def _decision_in_tx(con: sqlite3.Connection, oid: str, intent: str,
                        state: str, amount: float | None, reason: str,
                        at: int) -> dict[str, Any]:
        con.execute("INSERT INTO allocation_decisions(offering_id,intent_id,state,"
                    "amount,reason,at_epoch) VALUES(?,?,?,?,?,?)",
                    (oid, intent, state, amount, reason[:400], at / 1000.0))
        return {"offering_id": oid, "intent_id": intent, "state": state,
                "amount": None if amount is None else round(float(amount), 2),
                "reason": reason}

    def set_reservation(self, offering_id: str, intent_id: str, state: str,
                        note: str = "", at_ms: int | None = None) -> dict[str, Any]:
        if state not in tuple(s.value for s in ReservationState):
            raise OfferingsError("INVALID_STATE", "وضعیت رزرو نامعتبر است")
        at = (now_ms() if at_ms is None else int(at_ms)) / 1000.0
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            cur = con.execute(
                "UPDATE reservations SET state=?, note=?, updated_at=? "
                "WHERE offering_id=? AND intent_id=? AND state IN (?,?,?)",
                (state, note[:400], at, offering_id, intent_id) + ACTIVE_RESERVATION_STATES)
            if cur.rowcount != 1:
                con.execute("ROLLBACK")
                raise OfferingsError("INVALID_TRANSITION", "رزروِ فعال پیدا نشد")
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        return {"offering_id": offering_id, "intent_id": intent_id,
                "state": state, "note": note}

    def record_timing(self, *, adapter: str, method: str, value_ms: float,
                      network: str = "unknown", phase: str = "http_rtt",
                      source: str = "", observed_at: float | None = None,
                      note: str = "") -> None:
        method = str(method or "UNKNOWN").upper()
        if method not in METHODS:
            raise OfferingsError("INVALID_METHOD", "روش عرضه نامعتبر است")
        if phase not in ("http_rtt", "trigger", "preparation", "end_to_end"):
            raise OfferingsError("INVALID_PHASE", "فاز زمان‌سنجی نامعتبر است")
        if not str(source or "").strip():
            raise OfferingsError("SOURCE_REQUIRED", "منبعِ نمونهٔ زمان لازم است")
        try:
            value = float(value_ms)
        except (TypeError, ValueError):
            raise OfferingsError("INVALID_SAMPLE", "مقدار زمان نامعتبر است") from None
        if value < 0:
            raise OfferingsError("INVALID_SAMPLE", "زمان نمی‌تواند منفی باشد")
        at = time.time() if observed_at is None else float(observed_at)
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute("INSERT INTO timing_samples(adapter,method,network,phase,"
                        "value_ms,source,observed_at,note) VALUES(?,?,?,?,?,?,?,?)",
                        (str(adapter), method, str(network), phase, value,
                         str(source), at, note[:300]))
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def timing_stats(self, *, adapter: str, method: str, network: str | None = None,
                     phase: str = "http_rtt") -> dict[str, Any]:
        con = self._conn()
        try:
            q = ("SELECT value_ms FROM timing_samples WHERE adapter=? AND method=? AND phase=?")
            args: list[Any] = [adapter, method.upper(), phase]
            if network:
                q += " AND network=?"
                args.append(network)
            vals = [float(r[0]) for r in con.execute(q, args).fetchall()]
        finally:
            con.close()
        vals.sort()
        n = len(vals)
        if not vals:
            return {"n": 0, "p50": None, "p95": None, "p99": None,
                    "confidence": "INSUFFICIENT", "source": "http_rtt",
                    "acceptance_time_observed": False, "thin": True}
        med = percentile(vals, 50.0)
        mad = percentile(sorted(abs(v - med) for v in vals), 50.0) if n >= 2 else None
        p25 = percentile(vals, 25.0) if n >= 2 else None
        p75 = percentile(vals, 75.0) if n >= 2 else None
        conf = ("INSUFFICIENT" if n < 5 else "LOW" if n < 20
                else "MEDIUM" if n < 100 else "HIGH")
        return {"n": n, "p50": round(med, 3),
                "p95": round(percentile(vals, 95.0), 3) if n >= 20 else None,
                "p99": round(percentile(vals, 99.0), 3) if n >= 100 else None,
                "mad": None if mad is None else round(mad, 3),
                "iqr": None if p75 is None else round(p75 - p25, 3),
                "confidence": conf, "thin": n < 20,
                "source": "http_rtt", "acceptance_time_observed": False,
                "note": "HTTP RTT؛ زمانِ پذیرشِ کارگزاری مشاهده نشده"}


def preflight(offer: OfferingRecord, *, at: int, price: float, quantity: float,
              max_age_s: float, capital: Mapping[str, Any] | None = None,
              reserved: float = 0.0) -> dict[str, Any]:
    checks: dict[str, dict[str, str]] = {}
    blockers: list[str] = []

    def add(name: str, ok: bool | None, detail: str = "") -> None:
        state = UNKNOWN if ok is None else (PASS if ok else FAIL)
        checks[name] = {"state": state, "detail": detail[:300]}
        if state != PASS:
            blockers.append("%s: %s" % (name, detail or state))

    add("identity", bool(offer.symbol and offer.isin), "symbol/ISIN")
    add("source_verified", offer.status == "VERIFIED",
        "status=%s" % offer.status)
    add("method", offer.method != "UNKNOWN",
        "method=%s؛ روشِ UNKNOWN قابل تخصیص نیست" % offer.method)
    in_window = None
    if offer.start_ms is not None and offer.end_ms is not None:
        in_window = offer.start_ms <= at <= offer.end_ms
    add("window", in_window, "start/end نسبت به زمان اجرا")
    fresh = None
    if offer.data_as_of_ms is not None and max_age_s > 0:
        age = max(0.0, (at - int(offer.data_as_of_ms)) / 1000.0)
        fresh = age <= float(max_age_s)
        add("data_fresh", fresh, "age=%.0fs max=%.0fs" % (age, max_age_s))
    else:
        add("data_fresh", None, "data_as_of نامعلوم است")
    band = None
    if offer.price_min is not None and offer.price_max is not None:
        band = float(offer.price_min) <= float(price) <= float(offer.price_max)
    add("price", band, "range=%r..%r price=%r" % (offer.price_min, offer.price_max, price))
    qty_ok = None
    if offer.min_qty is not None and offer.max_qty is not None:
        qty_ok = (float(quantity) == int(quantity)
                  and float(offer.min_qty) <= float(quantity) <= float(offer.max_qty))
    add("quantity", qty_ok, "min/max/integer")
    quota_ok = None
    if offer.per_code_quota is not None:
        quota_ok = float(quantity) <= float(offer.per_code_quota)
    add("quota", quota_ok, "per-code=%r" % (offer.per_code_quota,))
    fee_ok = offer.fee_rate is not None and bool(offer.fee_source)
    add("fee", fee_ok, "fee_rate/source")
    amount = None
    if fee_ok and band is not None:
        gross = float(price) * float(quantity)
        fee = gross * float(offer.fee_rate)
        amount = round(gross + fee, 2)
    if capital is not None:
        cap_ok = None
        if capital.get("total_cap") is not None:
            avail = (float(capital["total_cap"]) - float(capital.get("cash_reserve") or 0.0)
                     - float(reserved))
            cap_ok = amount is not None and amount <= avail + 1e-9
            add("capital", cap_ok, "amount=%r available=%r" % (amount, round(avail, 2)))
            if amount is not None and amount > float(capital.get("max_per_offering") or 0):
                add("per_offering", False, "amount=%r max=%r" % (
                    amount, capital.get("max_per_offering")))
            elif amount is not None:
                add("per_offering", True, "")
    return {"ok": not blockers, "checks": checks, "blockers": blockers,
            "amount": amount, "fee": None if amount is None else round(amount - price * quantity, 2),
            "timing_relevance": offer.timing_relevance,
            "timing_note": offer.timing_note}


def timing_suggestion(stats: Mapping[str, Any], *, target_ms: int,
                      method: str, margin_ms: float = 0.0) -> dict[str, Any]:
    p95 = stats.get("p95")
    lead = None if p95 is None else round(float(p95) + max(0.0, float(margin_ms)), 3)
    relevance, note = METHOD_TIMING.get(str(method or "UNKNOWN").upper(),
                                        METHOD_TIMING["UNKNOWN"])
    return {"target_wall_ms": int(target_ms),
            "suggested_send_wall_ms": None if lead is None else int(target_ms - lead),
            "lead_ms": lead, "stats": dict(stats),
            "timing_relevance": relevance, "timing_note": note,
            "acceptance_time_observed": False,
            "note": "زمانِ پیشنهادی از HTTP RTT است، نه زمانِ پذیرشِ کارگزاری؛ "
                    "برایِ روش‌هایِ قاعده‌محور مزیتِ زمانی ادعا نمی‌شود"}


__all__ = ["OfferingMethod", "OfferingRecord", "OfferingStore", "OfferingsError",
           "ReservationState", "preflight", "timing_suggestion", "METHODS",
           "discover_codal"]


def discover_codal(db_path: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """کشفِ فقط‌خواندنی از آینهٔ محلیِ CODAL؛ متنِ اطلاعیه تفسیر نمی‌شود.

    خروجی «کاندیدِ نیازمند بازبینی» است، نه عرضهٔ ساختاریافته: method/price/qty
    این‌جا ساخته نمی‌شوند.
    """
    try:
        con = sqlite3.connect("file:%s?mode=ro" % db_path.replace("\\", "/"),
                              uri=True, timeout=3)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                "SELECT symbol, company_name, title, publish_date, url "
                "FROM codal_notices WHERE title LIKE ? AND "
                "(title LIKE ? OR title LIKE ?) "
                "ORDER BY publish_date DESC LIMIT ?",
                ("%عرضه%", "%اولیه%", "%عرضه سهام%",
                 max(1, min(int(limit), 100)))).fetchall()
        finally:
            con.close()
    except Exception as e:                       # noqa: BLE001
        raise OfferingsError("DISCOVERY_UNAVAILABLE",
                             "%s: %s" % (type(e).__name__, str(e)[:120])) from None
    return [{"symbol": r["symbol"], "company_name": r["company_name"],
             "title": r["title"], "publish_date": r["publish_date"],
             "url": r["url"], "structured": False,
             "status": "UNVERIFIED",
             "reason": "متنِ اطلاعیه تفسیر نشده؛ قیمت/روش/سهمیه باید از منبع رسمی وارد شود"}
            for r in rows]
