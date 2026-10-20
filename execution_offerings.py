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
import math
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

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
TIMING_PHASES = ("http_rtt", "trigger", "preparation", "end_to_end")
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

#: UNKNOWN_HOLD فقط با شاهد به COMMITTED یا RELEASED می‌رود؛ هرگز به RESERVED
#: برنمی‌گردد، چون برگشتِ بی‌شاهد یعنی «نامعلوم» دوباره قابلِ اقدام می‌شود.
RESERVATION_TRANSITIONS = {
    ReservationState.RESERVED.value: {
        ReservationState.COMMITTED.value, ReservationState.UNKNOWN_HOLD.value,
        ReservationState.RELEASED.value},
    ReservationState.COMMITTED.value: {
        ReservationState.UNKNOWN_HOLD.value, ReservationState.RELEASED.value},
    ReservationState.UNKNOWN_HOLD.value: {
        ReservationState.COMMITTED.value, ReservationState.RELEASED.value},
    ReservationState.RELEASED.value: set(),
}


class OfferingsError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__("%s: %s" % (code, detail) if detail else code)
        self.code = code
        self.detail = detail


#: اختلافِ کوچکِ ساعتِ کلاینت/سرور هنگامِ ثبت، نه مجوزِ دادهٔ آینده.
FUTURE_TOLERANCE_MS = 120_000
#: فاصلهٔ چندمیلی‌ثانیه‌ایِ ساخت/خواندن در همان فرایند، دادهٔ آینده نیست.
DATA_SKEW_TOLERANCE_MS = 1_000
#: نرخِ کارمزد باید کسریِ معقول باشد؛ ۱۰۰٪ یا بیشتر قطعاً دادهٔ معیوب است.
MAX_FEE_RATE = 1.0


def _finite(value: Any, *, code: str = "INVALID_NUMBER",
            label: str = "عدد") -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        raise OfferingsError(code, "%s نامعتبر است" % label) from None
    if not math.isfinite(out):
        raise OfferingsError(code, "%s بی‌کران/NaN است" % label)
    return out


def _opt_finite(value: Any, *, code: str, label: str) -> float | None:
    return None if value is None else _finite(value, code=code, label=label)


def _valid_source_url(value: str) -> bool:
    try:
        p = urlparse(str(value or "").strip())
    except ValueError:
        return False
    return p.scheme in ("http", "https") and bool(p.netloc)


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
        src = str(source or "").strip()
        src_url = str(source_url or "").strip()
        if src_url and not _valid_source_url(src_url):
            raise OfferingsError("INVALID_SOURCE_URL",
                                 "نشانی منبع باید http(s) باشد")
        has_verify_ts = verified_at_ms is not None or data_as_of_ms is not None
        if has_verify_ts and (verified_at_ms is None or data_as_of_ms is None):
            raise OfferingsError("INVALID_PROVENANCE",
                                 "verified_at و data_as_of هر دو لازم‌اند")
        now = now_ms()
        if verified_at_ms is not None:
            verified_at_ms = int(verified_at_ms)
        if data_as_of_ms is not None:
            data_as_of_ms = int(data_as_of_ms)
        if verified_at_ms is not None:
            if verified_at_ms <= 0 or verified_at_ms > now + FUTURE_TOLERANCE_MS:
                raise OfferingsError("INVALID_TIME",
                                     "verified_at در آینده یا نامعتبر است")
            if data_as_of_ms is not None and data_as_of_ms > verified_at_ms:
                raise OfferingsError("INVALID_PROVENANCE",
                                     "data_as_of از verified_at جدیدتر است")
        if data_as_of_ms is not None and (
                data_as_of_ms <= 0 or data_as_of_ms > now + FUTURE_TOLERANCE_MS):
            raise OfferingsError("INVALID_TIME",
                                 "data_as_of در آینده یا نامعتبر است")
        if has_verify_ts and not (src and src_url):
            raise OfferingsError("INVALID_PROVENANCE",
                                 "برای تأیید، منبع و نشانی منبع لازم است")
        price_min = _opt_finite(price_min, code="INVALID_RANGE", label="کف قیمت")
        price_max = _opt_finite(price_max, code="INVALID_RANGE", label="سقف قیمت")
        if price_min is not None and price_min <= 0:
            raise OfferingsError("INVALID_RANGE", "کف قیمت باید مثبت باشد")
        if price_max is not None and price_max <= 0:
            raise OfferingsError("INVALID_RANGE", "سقف قیمت باید مثبت باشد")
        if price_min is not None and price_max is not None and price_min > price_max:
            raise OfferingsError("INVALID_RANGE", "کف قیمت از سقف بیشتر است")
        min_qty = _opt_finite(min_qty, code="INVALID_RANGE", label="حداقل تعداد")
        max_qty = _opt_finite(max_qty, code="INVALID_RANGE", label="حداکثر تعداد")
        if min_qty is not None and min_qty < 0:
            raise OfferingsError("INVALID_RANGE", "حداقل تعداد منفی است")
        if max_qty is not None and max_qty <= 0:
            raise OfferingsError("INVALID_RANGE", "حداکثر تعداد باید مثبت باشد")
        if min_qty is not None and max_qty is not None and min_qty > max_qty:
            raise OfferingsError("INVALID_RANGE", "حداقل تعداد از حداکثر بیشتر است")
        per_code_quota = _opt_finite(per_code_quota, code="INVALID_RANGE",
                                     label="سهمیهٔ هر کد")
        if per_code_quota is not None and per_code_quota < 0:
            raise OfferingsError("INVALID_RANGE", "سهمیهٔ هر کد منفی است")
        fee_rate = _opt_finite(fee_rate, code="INVALID_FEE", label="نرخ کارمزد")
        if fee_rate is not None and not (0.0 <= fee_rate < MAX_FEE_RATE):
            raise OfferingsError("INVALID_FEE",
                                 "نرخ کارمزد باید بین صفر و یک باشد")
        if start_ms is not None:
            start_ms = int(start_ms)
        if end_ms is not None:
            end_ms = int(end_ms)
        if start_ms is not None and end_ms is not None and start_ms >= end_ms:
            raise OfferingsError("INVALID_WINDOW", "پنجرهٔ عرضه نامعتبر است")
        relevance, timing_note = METHOD_TIMING[method]
        status = ("VERIFIED" if (src and src_url and verified_at_ms and data_as_of_ms)
                  else "UNVERIFIED")
        at = now / 1000.0
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
                 price_min, price_max, str(price_source or ""), min_qty, max_qty,
                 per_code_quota, fee_rate, str(fee_source or ""), src, src_url,
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
        cap = _finite(total_cap, code="INVALID_BUDGET", label="سقف کل")
        reserve = _finite(cash_reserve, code="INVALID_BUDGET", label="ذخیرهٔ نقدی")
        per = _finite(max_per_offering, code="INVALID_BUDGET", label="سقف هر عرضه")
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
            active = float(con.execute(
                "SELECT COALESCE(SUM(amount),0) FROM reservations "
                "WHERE state IN (?,?,?)", ACTIVE_RESERVATION_STATES).fetchone()[0] or 0.0)
            if cap - reserve < active - 1e-9:
                raise OfferingsError(
                    "BUDGET_BELOW_RESERVED",
                    "سقفِ جدید از رزروهایِ فعال (%.2f) کمتر است" % active)
            biggest = float(con.execute(
                "SELECT COALESCE(MAX(amount),0) FROM reservations "
                "WHERE state IN (?,?,?)", ACTIVE_RESERVATION_STATES).fetchone()[0] or 0.0)
            if per < biggest - 1e-9:
                raise OfferingsError(
                    "BUDGET_BELOW_RESERVED",
                    "سقفِ هر عرضه از بزرگ‌ترین رزروِ فعال (%.2f) کمتر است" % biggest)
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
        """رزروِ چند عرضه در یک تراکنش؛ اولویت‌ها از capital_settings.

        تنظیماتِ سرمایه و موجودیِ رزروها داخلِ همان تراکنشِ BEGIN IMMEDIATE
        خوانده می‌شوند تا تغییرِ هم‌زمانِ سقف نتواند بینِ خواندن و رزرو جا شود.
        """
        at = now_ms() if now is None else int(now)
        items = [dict(p) for p in plans]
        if not items:
            raise OfferingsError("INVALID_PLAN", "فهرستِ رزرو خالی است")
        decisions: list[dict[str, Any]] = []
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            crow = con.execute("SELECT * FROM capital_settings WHERE id=1").fetchone()
            if crow is None:
                raise OfferingsError("BUDGET_UNSET", "سقف بودجه تنظیم نشده است")
            cap = {"total_cap": float(crow["total_cap"]),
                   "cash_reserve": float(crow["cash_reserve"]),
                   "max_per_offering": float(crow["max_per_offering"]),
                   "priorities": json.loads(crow["priorities_json"] or "{}"),
                   "version": int(crow["version"]),
                   "updated_at": crow["updated_at"]}
            pri = cap.get("priorities") or {}

            def pkey(p: Mapping[str, Any]) -> int:
                for key in (str(p.get("offering_id") or ""),
                            str(p.get("symbol") or "")):
                    raw = pri.get(key)
                    if raw is None:
                        continue
                    try:
                        return int(raw)
                    except (TypeError, ValueError):
                        continue
                return 100

            items.sort(key=pkey)
            used = float(con.execute(
                "SELECT COALESCE(SUM(amount),0) FROM reservations "
                "WHERE state IN (?,?,?)", ACTIVE_RESERVATION_STATES).fetchone()[0] or 0.0)
            available = max(0.0, cap["total_cap"] - cap["cash_reserve"] - used)
            for p in items:
                oid = str(p.get("offering_id") or "")
                intent = str(p.get("intent_id") or "")
                if not intent:
                    decisions.append(self._decision_in_tx(
                        con, oid, intent, "BLOCKED", None, "INTENT_REQUIRED", at))
                    continue
                r = con.execute("SELECT * FROM offerings WHERE id=?", (oid,)).fetchone()
                offer = _row(r) if r else None
                if offer is None:
                    decisions.append(self._decision_in_tx(con, oid, intent, "BLOCKED",
                                                          None, "OFFERING_NOT_FOUND", at))
                    continue
                try:
                    price = _finite(p.get("price"), code="INVALID_ORDER",
                                    label="قیمت")
                    qty = _finite(p.get("quantity"), code="INVALID_ORDER",
                                  label="تعداد")
                except OfferingsError:
                    decisions.append(self._decision_in_tx(con, oid, intent, "BLOCKED",
                                                          None, "INVALID_ORDER", at))
                    continue
                prior = con.execute(
                    "SELECT state, amount FROM reservations "
                    "WHERE offering_id=? AND intent_id=?", (oid, intent)).fetchone()
                if prior is not None:
                    if prior["state"] in ACTIVE_RESERVATION_STATES:
                        decisions.append(self._decision_in_tx(
                            con, oid, intent, "RESERVED", float(prior["amount"]),
                            "IDEMPOTENT", at))
                    else:
                        decisions.append(self._decision_in_tx(
                            con, oid, intent, "BLOCKED", float(prior["amount"]),
                            "INTENT_ALREADY_USED", at))
                    continue
                rep = preflight(offer, at=at, price=price, quantity=qty,
                                max_age_s=max_age_s, capital=None, reserved=0.0)
                if not rep["ok"]:
                    decisions.append(self._decision_in_tx(
                        con, oid, intent, "BLOCKED", rep.get("amount"),
                        "; ".join(rep["blockers"][:4]), at))
                    continue
                amount = rep.get("amount")
                if amount is None or float(amount) <= 0:
                    decisions.append(self._decision_in_tx(
                        con, oid, intent, "BLOCKED", amount,
                        "INVALID_AMOUNT", at))
                    continue
                amount = float(amount)
                if amount > cap["max_per_offering"] + 1e-9:
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
            reserved_total = round(float(con.execute(
                "SELECT COALESCE(SUM(amount),0) FROM reservations "
                "WHERE state IN (?,?,?)", ACTIVE_RESERVATION_STATES).fetchone()[0] or 0.0), 2)
            final_available = round(max(0.0, cap["total_cap"] - cap["cash_reserve"]
                                        - reserved_total), 2)
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        return {"decisions": decisions, "reserved_total": reserved_total,
                "available": final_available, "capital": cap}

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
        allowed = tuple(s.value for s in ReservationState if s is not ReservationState.SKIPPED_BUDGET)
        if state not in allowed:
            raise OfferingsError("INVALID_STATE", "وضعیت رزرو نامعتبر است")
        clean_note = str(note or "").strip()
        if state in (ReservationState.UNKNOWN_HOLD.value, ReservationState.RELEASED.value) \
                and not clean_note:
            raise OfferingsError("NOTE_REQUIRED",
                                 "برای UNKNOWN_HOLD/RELEASED شاهد یا دلیل لازم است")
        at = (now_ms() if at_ms is None else int(at_ms)) / 1000.0
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT id, state, note FROM reservations "
                "WHERE offering_id=? AND intent_id=?",
                (offering_id, intent_id)).fetchone()
            if row is None:
                raise OfferingsError("INVALID_TRANSITION", "رزرو پیدا نشد")
            current = str(row["state"])
            if current == state:                     # retry همان درخواست، بی‌تغییر
                if (current in ACTIVE_RESERVATION_STATES and clean_note
                        and clean_note != str(row["note"] or "")):
                    con.execute("UPDATE reservations SET note=?, updated_at=? "
                                "WHERE id=?", (clean_note[:400], at, int(row["id"])))
                con.execute("COMMIT")
                return {"offering_id": offering_id, "intent_id": intent_id,
                        "state": state, "note": clean_note, "unchanged": True}
            if current not in ACTIVE_RESERVATION_STATES:
                raise OfferingsError("INVALID_TRANSITION",
                                     "رزروِ بسته‌شده دوباره فعال نمی‌شود")
            if state not in RESERVATION_TRANSITIONS.get(current, set()):
                raise OfferingsError("INVALID_TRANSITION",
                                     "گذارِ %s → %s مجاز نیست" % (current, state))
            cur = con.execute(
                "UPDATE reservations SET state=?, note=?, updated_at=? "
                "WHERE id=? AND state=?",
                (state, clean_note[:400], at, int(row["id"]), current))
            if cur.rowcount != 1:
                raise OfferingsError("INVALID_TRANSITION", "رزرو هم‌زمان تغییر کرد")
            con.execute("COMMIT")
        except Exception:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        return {"offering_id": offering_id, "intent_id": intent_id,
                "state": state, "note": clean_note}

    def record_timing(self, *, adapter: str, method: str, value_ms: float,
                      network: str = "unknown", phase: str = "http_rtt",
                      source: str = "", observed_at: float | None = None,
                      note: str = "") -> None:
        method = str(method or "UNKNOWN").upper()
        if method not in METHODS:
            raise OfferingsError("INVALID_METHOD", "روش عرضه نامعتبر است")
        adapter = str(adapter or "").strip()
        if not adapter:
            raise OfferingsError("INVALID_ADAPTER", "نام آداپتور لازم است")
        if phase not in TIMING_PHASES:
            raise OfferingsError("INVALID_PHASE", "فاز زمان‌سنجی نامعتبر است")
        if not str(source or "").strip():
            raise OfferingsError("SOURCE_REQUIRED", "منبعِ نمونهٔ زمان لازم است")
        value = _finite(value_ms, code="INVALID_SAMPLE", label="مقدار زمان")
        if value < 0:
            raise OfferingsError("INVALID_SAMPLE", "زمان نمی‌تواند منفی باشد")
        now_s = time.time()
        at = now_s if observed_at is None else _finite(
            observed_at, code="INVALID_SAMPLE", label="observed_at")
        if at <= 0 or at > now_s + 60.0:
            raise OfferingsError("INVALID_SAMPLE",
                                 "observed_at در آینده یا نامعتبر است")
        con = self._conn()
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute("INSERT INTO timing_samples(adapter,method,network,phase,"
                        "value_ms,source,observed_at,note) VALUES(?,?,?,?,?,?,?,?)",
                        (adapter, method, str(network), phase, value,
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
        if phase not in TIMING_PHASES:
            raise OfferingsError("INVALID_PHASE", "فاز زمان‌سنجی نامعتبر است")
        con = self._conn()
        try:
            q = ("SELECT value_ms FROM timing_samples WHERE adapter=? AND method=? AND phase=?")
            args: list[Any] = [str(adapter), method.upper(), phase]
            if network:
                q += " AND network=?"
                args.append(network)
            vals = [float(r[0]) for r in con.execute(q, args).fetchall()]
        finally:
            con.close()
        vals.sort()
        n = len(vals)
        base = {"adapter": str(adapter), "method": method.upper(),
                "network": network or "all", "phase": phase,
                "source": phase, "percentile_method": "nearest_rank",
                "acceptance_time_observed": False}
        if not vals:
            return {**base, "n": 0, "p50": None, "p95": None, "p99": None,
                    "confidence": "INSUFFICIENT", "thin": True,
                    "note": "نمونهٔ کافی نیست؛ هیچ زمانِ بهینه‌ای پیشنهاد نمی‌شود"}
        med = percentile(vals, 50.0)
        mad = percentile(sorted(abs(v - med) for v in vals), 50.0) if n >= 2 else None
        p25 = percentile(vals, 25.0) if n >= 2 else None
        p75 = percentile(vals, 75.0) if n >= 2 else None
        conf = ("INSUFFICIENT" if n < 5 else "LOW" if n < 20
                else "MEDIUM" if n < 100 else "HIGH")
        note = ("HTTP RTT؛ زمانِ پذیرشِ کارگزاری مشاهده نشده"
                if phase == "http_rtt" else
                "فازِ %s؛ این عدد زمانِ پذیرشِ کارگزاری نیست" % phase)
        return {**base, "n": n, "p50": round(med, 3),
                "p95": round(percentile(vals, 95.0), 3) if n >= 20 else None,
                "p99": round(percentile(vals, 99.0), 3) if n >= 100 else None,
                "mad": None if mad is None else round(mad, 3),
                "iqr": None if p75 is None else round(p75 - p25, 3),
                "confidence": conf, "thin": n < 20, "note": note}


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

    def num(value: Any) -> float | None:
        try:
            out = float(value)
        except (TypeError, ValueError):
            return None
        return out if math.isfinite(out) else None

    add("identity", bool(offer.symbol and offer.isin), "symbol/ISIN")
    add("source_verified", offer.status == "VERIFIED",
        "status=%s" % offer.status)
    method_ok = offer.method != "UNKNOWN"
    add("method", method_ok, "method=%s%s" % (
        offer.method, "" if method_ok else "؛ روشِ UNKNOWN قابل تخصیص نیست"))
    in_window = None
    if offer.start_ms is not None and offer.end_ms is not None:
        in_window = int(offer.start_ms) < int(offer.end_ms) \
            and int(offer.start_ms) <= at <= int(offer.end_ms)
    add("window", in_window, "start/end نسبت به زمان اجرا")
    fresh = None
    if offer.data_as_of_ms is not None and max_age_s > 0:
        skew_ms = int(at) - int(offer.data_as_of_ms)
        age = max(0.0, skew_ms / 1000.0)
        fresh = (-skew_ms) <= DATA_SKEW_TOLERANCE_MS and age <= float(max_age_s)
        add("data_fresh", fresh,
            "age=%.0fs max=%.0fs skew=%dms" % (age, max_age_s, -skew_ms))
    else:
        add("data_fresh", None, "data_as_of نامعلوم است")

    px = num(price)
    qty = num(quantity)
    pmin, pmax = num(offer.price_min), num(offer.price_max)
    if pmin is None or pmax is None:
        price_band = None
    elif px is None or px <= 0:
        price_band = False
    else:
        price_band = pmin <= px <= pmax
    add("price", price_band,
        "range=%r..%r price=%r" % (offer.price_min, offer.price_max, price))
    add("price_source", bool(str(offer.price_source or "").strip()),
        "price_source خالی است")

    qmin, qmax = num(offer.min_qty), num(offer.max_qty)
    if qmin is None or qmax is None:
        qty_ok = None
    elif qty is None or qty <= 0:
        qty_ok = False
    else:
        qty_ok = qty.is_integer() and qmin <= qty <= qmax
    add("quantity", qty_ok, "min/max/integer/positive")

    quota = num(offer.per_code_quota)
    if quota is None:
        quota_ok = None
    elif qty is None or qty <= 0:
        quota_ok = False
    else:
        quota_ok = qty <= quota
    add("quota", quota_ok, "per-code=%r" % (offer.per_code_quota,))

    fee_rate = num(offer.fee_rate)
    fee_ok = (fee_rate is not None and 0.0 <= fee_rate < MAX_FEE_RATE
              and bool(str(offer.fee_source or "").strip()))
    add("fee", fee_ok, "fee_rate/source")

    amount = None
    fee_value = None
    if fee_ok and price_band and qty_ok is not None and qty_ok:
        gross = float(px) * float(qty)
        fee_value = round(gross * float(fee_rate), 2)
        amount = round(gross + fee_value, 2)

    if capital is not None:
        total = num(capital.get("total_cap"))
        reserve = num(capital.get("cash_reserve") or 0.0)
        held = num(reserved)
        max_per = num(capital.get("max_per_offering"))
        cap_ok = None
        avail = None
        if total is not None and reserve is not None and held is not None:
            avail = total - reserve - held
            cap_ok = (amount is not None and amount <= avail + 1e-9)
        add("capital", cap_ok,
            "amount=%r available=%r" % (amount, None if avail is None else round(avail, 2)))
        per_ok = None
        if max_per is not None and max_per > 0:
            per_ok = amount is not None and amount <= max_per + 1e-9
        add("per_offering", per_ok,
            "amount=%r max=%r" % (amount, capital.get("max_per_offering")))
    return {"ok": not blockers, "checks": checks, "blockers": blockers,
            "amount": amount, "fee": fee_value,
            "timing_relevance": offer.timing_relevance,
            "timing_note": offer.timing_note}


def timing_suggestion(stats: Mapping[str, Any], *, target_ms: int,
                      method: str, margin_ms: float = 0.0) -> dict[str, Any]:
    p95 = stats.get("p95")
    lead = None if p95 is None else round(float(p95) + max(0.0, float(margin_ms)), 3)
    relevance, note = METHOD_TIMING.get(str(method or "UNKNOWN").upper(),
                                        METHOD_TIMING["UNKNOWN"])
    src = str(stats.get("source") or "http_rtt")
    suggestion = None if lead is None or int(target_ms) <= 0 else int(target_ms - lead)
    return {"target_wall_ms": int(target_ms),
            "suggested_send_wall_ms": suggestion,
            "lead_ms": lead, "stats": dict(stats),
            "timing_relevance": relevance, "timing_note": note,
            "acceptance_time_observed": False,
            "note": "زمانِ پیشنهادی از فازِ %s است، نه زمانِ پذیرشِ کارگزاری؛ "
                    "برایِ روش‌هایِ قاعده‌محور مزیتِ زمانی ادعا نمی‌شود" % src}


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
