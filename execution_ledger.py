# -*- coding: utf-8 -*-
"""execution_ledger.py — دفترِ ماندگارِ اجرا: ردِّپایِ سفارش، قفلِ توقف، و شمارشِ ریسک.

چرا این فایل (مأموریتِ ۱۴۰۵-۰۷-۲۳، بندِ ۵-۳ و ۶-۴): تا پیشِ این، تمامِ ردِّپایِ
اجرا یک dict درِ حافظه بود (`execution_service.py:146`) — یعنی با هر restart
همهٔ «چه فرستادم، چه شد» می‌مرد. برایِ حالتی که نتیجه‌اش UNKNOWN است این
فاجعه است: سفارشی که سرور پذیرفت و ما ندیدیم، بعدِ restart «هرگز ارسال نشده»
به‌نظر می‌آید و تنها راهِ درستش (reconcile) گم می‌شود. همین‌جا قفلِ توقفِ اضطراری
هم زندگی می‌کند، چون «توقف» هم نباید با restart پاک شود.

سه حکمِ این فایل:

۱) **append-only.** هیچ UPDATE و هیچ DELETE رویِ `execution_event` نیست؛ حالتِ
   تازه‌ترِ همان سفارش یکِ رُکوردِ تازه است. دلیلش: ردِّپایی که بازنویسی شود
   دیگر ردِّپا نیست — و «چرا این سفارش رد شد» دقیقاً همان چیزی است که باید
   بعدِ اتفاق قابلِ بازخوانی باشد.

۲) **بی‌secret.** تنها راهِ نوشتنِ هرچه از درخواست/پاسخ، `redact()` خودِ
   قرارداد است (`execution_contract.py:281`). payload قبلِ رسیدن به دیسک از
   همان می‌گذرد، پس حتی یکِ لاگِ بد‌نیت هم token نمی‌نویسد.

۳) **نبود ⇒ None، نه صفر.** شمارش‌هایِ ریسک اگر ردِّپایی نباشد `None`
   می‌دهند؛ مصرف‌کننده (دروازۀ ریسکِ سرویس) با None باید fail-closed تصمیم
   بگیرد، نه اینکه «پس صفر سفارش فرستاده‌ایم» را عددِ واقعی بداند.

محلِ ذخیره `user.db` است نه `market.db`: این بانکِ دادهٔ بازار نیست، دادهٔ
خودِ کاربر است — و `MARKET_DB_USER_TABLES` در `bors_config.py:235` نشان می‌دهد
چیزهایِ کاربرنویس باید از نوشتنِ baseline در امان بمانند.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from execution_contract import redact

#: تنها جدول‌هایی که این فایل می‌سازد/می‌خواند.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS execution_event (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT    NOT NULL,
    -- زمانِ نوشتنِ رُکورد (UTC ISO). با `attempts` و `status` مقایسه می‌شود تا
    -- «اولِ این یا آن آمد» قابلِ بازسازی باشد، نه حدسِ ترتیبِ آرایه.
    written_at   TEXT    NOT NULL,
    -- source_from_event هر دو ساعت را نگه می‌دارد: epochِ خودِ رخداد (mono-ness
    -- برایِ پنجرۀ شمارش) و برچسبِ خوانا. نبودِ رخداد ⇒ None.
    at_epoch     REAL,
    kind         TEXT    NOT NULL,
    status       TEXT,
    order_state  TEXT,
    error_code   TEXT,
    detail       TEXT,
    broker       TEXT,
    symbol       TEXT,
    side         TEXT,
    price        REAL,
    quantity     REAL,
    filled       REAL,
    mode         TEXT,
    payload      TEXT
);
CREATE INDEX IF NOT EXISTS idx_exec_event_id ON execution_event(execution_id);
CREATE INDEX IF NOT EXISTS idx_exec_event_kind ON execution_event(kind, at_epoch);
CREATE INDEX IF NOT EXISTS idx_exec_event_sym ON execution_event(symbol, at_epoch);

CREATE TABLE IF NOT EXISTS execution_flag (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT NOT NULL
);
"""

#: کلیدِ قفلِ توقف. مقدارِ سه‌حالته، نه boolean: «خاموش» با «نمی‌دانیم» یکی نیست.
KILL_KEY = "kill_switch"
HALT = "HALTED"
ARMED = "ARMED"
#: حالتِ سوم: قفلی که خودِ سیستم انداخته (ضرر روزانه، دادهٔ کهنه) و بی‌اقدامِ
#: صریحِ انسان برنمی‌گردد.
TRIPPED = "TRIPPED"
KILL_STATES = (ARMED, HALT, TRIPPED)

_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _connect(path: str) -> sqlite3.Connection:
    # `check_same_thread=False` لازم است، نه لوکس: FastAPI هر endpointِ sync را در
    # threadpool اجرا می‌کند، پس اتصالِ ساخته‌شده درِ `import` (رشتۀ اصلی) درِ
    # اولین `/api/execution/status` با `ProgrammingError` می‌ترکد. آزمونِ واحدِ
    # تک‌رشته این را هیچ‌وقت نمی‌بیند؛ گاردِ HTTPِ سطحِ TestClient دید
    # (dev/execution_ledger_v1108.py، بندِ «از رشتۀ دیگر»). تمامِ دسترسی‌ها
    # زیرِ `_LOCK` سراسری همین ماژولند، پس یک اتصالِ مشترک بی‌رقابت است.
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


class ExecutionLedger:
    """ردِّپا + قفلِ توقفِ رویِ دیسک.

    `db_path=None` یعنی همان `user.db` برنامه. برایِ آزمون، مسیرِ یک فایلِ
    موقت می‌دهند؛ هیچ نوشتنی رویِ بانکِ بازار درِ این کلاس ممکن نیست (هیچ
    مسیرِ market.db ندارد).
    """

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            import bors_config
            db_path = bors_config.USER_DB_PATH
        self.db_path = db_path
        self._conn = _connect(db_path)
        with _LOCK:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    # ---- ۱) نوشتنِ رُکورد -------------------------------------------------
    def record(self, *, execution_id: str, kind: str, at_epoch: float | None = None,
               status: str | None = None, order_state: str | None = None,
               error_code: str | None = None, detail: str = "",
               broker: str | None = None, symbol: str | None = None,
               side: str | None = None, price: float | None = None,
               quantity: float | None = None, filled: float | None = None,
               mode: str | None = None,
               payload: Mapping[str, Any] | None = None) -> int:
        """یک رُکوردِ تازه برمی‌گرداند id آن. `payload` بی‌redact نوشته نمی‌شود."""
        safe = redact(dict(payload)) if payload else None
        with _LOCK:
            cur = self._conn.execute(
                "INSERT INTO execution_event(execution_id, written_at, at_epoch, kind,"
                " status, order_state, error_code, detail, broker, symbol, side, price,"
                " quantity, filled, mode, payload) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (str(execution_id), _now_iso(),
                 time.time() if at_epoch is None else float(at_epoch), str(kind),
                 status, order_state, error_code, detail, broker, symbol, side,
                 price, quantity, filled, mode,
                 json.dumps(safe, ensure_ascii=False, default=str) if safe is not None else None))
            self._conn.commit()
        return int(cur.lastrowid)

    # ---- ۲) خواندن --------------------------------------------------------
    def events(self, execution_id: str | None = None, *, kinds: Iterable[str] | None = None,
               limit: int = 500) -> list[dict]:
        q = "SELECT * FROM execution_event"
        cond, args = [], []
        if execution_id is not None:
            cond.append("execution_id = ?")
            args.append(execution_id)
        if kinds:
            k = list(kinds)
            cond.append("kind IN (%s)" % ",".join("?" * len(k)))
            args.extend(k)
        if cond:
            q += " WHERE " + " AND ".join(cond)
        q += " ORDER BY id DESC LIMIT ?"
        args.append(int(limit))
        with _LOCK:
            rows = self._conn.execute(q, args).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            p = d.get("payload")
            d["payload"] = json.loads(p) if p else None
            out.append(d)
        return out

    def trail(self, execution_id: str) -> list[dict]:
        """ردِّپایِ یکِ سفارش، مرتب از کهنه به تازه — همان چیزی که برایِ
        «بعدِ restart چه بدانم» لازم است.
        """
        ev = self.events(execution_id=execution_id, limit=1000)
        return sorted(ev, key=lambda e: int(e["id"]))

    def latest_status(self, execution_id: str) -> dict | None:
        ev = self.trail(execution_id)
        return ev[-1] if ev else None

    def open_ids(self) -> list[str]:
        """سفارش‌هایی که آخرینِ رُکوردشان حالتِ *نبسته* دارد.

        این فهرست باید پسِ restart به `reconcile()` برود؛ هیچ وضعیتی از خودِ
        این فایل ساخته نمی‌شود.
        """
        with _LOCK:
            rows = self._conn.execute(
                "SELECT execution_id, status, order_state, id FROM execution_event"
                " WHERE id IN (SELECT MAX(id) FROM execution_event GROUP BY execution_id)"
                " ORDER BY id").fetchall()
        out = []
        for r in rows:
            if (r["status"] or "") in ("unknown_result", "dispatched", "acknowledged",
                                       "scheduled", "reconciled") and \
               (r["order_state"] or "unknown") not in ("filled", "cancelled", "rejected"):
                out.append(r["execution_id"])
        return out

    # ---- ۳) شمارش‌هایِ ریسک (None یعنی «نمی‌دانیم») ----------------------
    def orders_in_window(self, seconds: float, *, symbol: str | None = None,
                         now: float | None = None) -> int | None:
        """چند dispatch درِ پنجرۀ زمانیِ اخیر.

        نبودِ هیچ ردِّپایی صفر است (واقعاً هیچ نفرستادیم)، ولی اگر خودِ شمارش
        نپرسیدنی باشد None — مصرف‌کننده با None باید جلویِ ارسال را بگیرد.
        """
        if seconds is None:
            return None
        t = time.time() if now is None else float(now)
        q = "SELECT COUNT(*) n FROM execution_event WHERE kind='dispatch' AND at_epoch >= ?"
        args: list[Any] = [t - float(seconds)]
        if symbol is not None:
            q += " AND symbol = ?"
            args.append(symbol)
        with _LOCK:
            row = self._conn.execute(q, args).fetchone()
        return int(row["n"]) if row is not None else None

    def traded_value(self, since_epoch: float, *, symbol: str | None = None) -> float | None:
        """ارزشِ پرشده (filled×price) از ردِّپا. هیچ پرشدنی را حدس نمی‌زند:
        رُکوردی که `filled` ندارد درِ جمع نمی‌آید.
        """
        q = ("SELECT SUM(COALESCE(filled,0.0)*COALESCE(price,0.0)) v FROM execution_event"
             " WHERE kind IN ('ack','state','fill') AND at_epoch >= ?")
        args: list[Any] = [float(since_epoch)]
        if symbol is not None:
            q += " AND symbol = ?"
            args.append(symbol)
        with _LOCK:
            row = self._conn.execute(q, args).fetchone()
        if row is None or row["v"] is None:
            return None
        return float(row["v"])

    # ---- ۴) قفلِ توقف ----------------------------------------------------
    def kill_state(self) -> str:
        """سه حالتِ صریح، و پیش‌فرضِ محافظه‌کارانۀ ARMED.

        چرا ARMED پیش‌فرض: «هیچ ردِّپایی نیست» یعنی نه توقفی اعلام شده و نه
        سفری رفته؛ درِ هر دو حالت، سفارشِ بعدی باید راه داشته باشد، وگرنه یک
        restart بی‌گناه کلِ مسیر را می‌بندد. حالتِ نامعلومِ واقعی با نوشتنِ
        صریحِ مقدارِ ناشناخته ساخته می‌شود (`set_kill(..., 'UNKNOWN')`).
        """
        with _LOCK:
            row = self._conn.execute(
                "SELECT value FROM execution_flag WHERE key = ?", (KILL_KEY,)).fetchone()
        if row is None or row["value"] is None:
            return ARMED
        v = str(row["value"]).strip().upper()
        return v if v in KILL_STATES or v == "UNKNOWN" else ARMED

    def set_kill(self, state: str, reason: str = "", *, actor: str = "system") -> None:
        s = str(state).strip().upper()
        if s not in KILL_STATES and s != "UNKNOWN":
            raise ValueError("kill state must be one of %s" % (KILL_STATES + ("UNKNOWN",)))
        with _LOCK:
            self._conn.execute(
                "INSERT INTO execution_flag(key, value, updated_at) VALUES (?,?,?)"
                " ON CONFLICT(key) DO UPDATE SET value=excluded.value,"
                " updated_at=excluded.updated_at", (KILL_KEY, s, _now_iso()))
            self._conn.commit()
        self.record(execution_id="-", kind="kill", status=s, detail=reason,
                    payload={"actor": actor, "reason": reason})

    def halted(self) -> bool:
        """True یعنی «سفارشِ تازه ممنوع». UNKNOWN هم توقف است: درِ وضعیتِ
        نامطمئن پیش‌فرضِ امن، ایستادن است نه فرستادن.
        """
        return self.kill_state() in (HALT, TRIPPED, "UNKNOWN")

    def kill_reason(self) -> str:
        ev = self.events(kinds=("kill",), limit=1)
        return (ev[0]["detail"] or "") if ev else ""

    # ---- ۵) وضعیتِ حسابِ شبیه‌سازی‌شده (بازیابی پسِ restart) -------------
    def save_state(self, key: str, value: Mapping[str, Any]) -> None:
        with _LOCK:
            self._conn.execute(
                "INSERT INTO execution_flag(key, value, updated_at) VALUES (?,?,?)"
                " ON CONFLICT(key) DO UPDATE SET value=excluded.value,"
                " updated_at=excluded.updated_at",
                (key, json.dumps(redact(dict(value)), ensure_ascii=False,
                                 default=str), _now_iso()))
            self._conn.commit()

    def load_state(self, key: str) -> dict | None:
        with _LOCK:
            row = self._conn.execute(
                "SELECT value FROM execution_flag WHERE key = ?", (key,)).fetchone()
        if row is None or not row["value"]:
            return None
        try:
            got = json.loads(row["value"])
        except (ValueError, TypeError):
            return None
        return got if isinstance(got, dict) else None

    def has_any(self) -> bool:
        with _LOCK:
            row = self._conn.execute("SELECT COUNT(*) n FROM execution_event").fetchone()
        return bool(row and int(row["n"]) > 0)


#: یک نمونهٔ ارزان برایِ مسیرهایی که فقطِ قفل/ردِّپا می‌خواهند.
_PATH_ENV = "BORS_EXECUTION_DB"


def default_ledger() -> ExecutionLedger:
    """مسیرِ بانکِ ردِّپا: متغیرِ محیطی (آزمون/چندنشست)، وگرنه `user.db` برنامه."""
    override = (os.environ.get(_PATH_ENV) or "").strip()
    if override:
        return ExecutionLedger(override)
    return ExecutionLedger()
