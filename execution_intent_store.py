# -*- coding: utf-8 -*-
"""execution_intent_store.py — قفلِ پایدارِ «یک قصد، یک کلیک» (Round 14).

`IntentArbiter` فقط در حافظه و بر اساسِ `execution_id` قفل می‌گذاشت؛ UI برایِ هر
prepare یک ID تازه می‌ساخت و همان قصد می‌توانست دوباره اجرا شود. این store کلیدِ
منطقیِ قصد را در `user.db` نگه می‌دارد تا تکرار با ID تازه و restart هم مسدود
شود. هیچ token/cookie/payload اینجا نوشته نمی‌شود.

حالات:
  prepared → scheduled → clicking → submitted/confirmed/rejected/unknown
  failed_pre_click (تنها حالتی که همان قصد می‌تواند دوباره prepare شود)
  aborted / dry_run / stale
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from typing import Any, Mapping, Optional

_TABLE = "execution_intents"
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS %s("
    " intent_key TEXT PRIMARY KEY,"
    " execution_id TEXT NOT NULL,"
    " strategy_id TEXT NOT NULL,"
    " state TEXT NOT NULL,"
    " prepared_id TEXT,"
    " target_wall_ms INTEGER,"
    " symbol TEXT, isin TEXT, side TEXT, price REAL, quantity REAL,"
    " clicked INTEGER NOT NULL DEFAULT 0,"
    " detail TEXT NOT NULL DEFAULT '',"
    " result_json TEXT,"
    " created_at INTEGER NOT NULL,"
    " updated_at INTEGER NOT NULL)" % _TABLE)
_INDEX = ("CREATE INDEX IF NOT EXISTS idx_execution_intents_state "
          "ON %s(state)" % _TABLE)

#: حالت‌هایی که همان کلید را قفل می‌کنند. فقط failed_pre_click قابلِ تلاشِ دوباره است.
BLOCKING_STATES = frozenset({
    "prepared", "scheduled", "clicking", "submitted", "confirmed",
    "rejected", "unknown", "aborted", "dry_run", "stale",
    "needs_review", "missed",
})
TERMINAL_STATES = frozenset({
    "submitted", "confirmed", "rejected", "unknown", "aborted", "dry_run",
    "stale", "needs_review", "missed",
})


class IntentBlocked(RuntimeError):
    def __init__(self, state: str, detail: str = "") -> None:
        super().__init__("%s: %s" % (state, detail) if detail else state)
        self.state = str(state)
        self.detail = str(detail)[:200]


def derive_key(draft: Any, target_wall_ms: Optional[int], explicit: str = "") -> str:
    """کلیدِ منطقی؛ بدونِ کلیدِ صریح، هویتِ همان execution_id است.

    UI باید برایِ یک قصدِ منطقی (حتی با prepare دوباره) ``intent_key`` پایدار
    بفرستد؛ آن‌وقت دو ID متفاوت با کلیدِ یکسان قفل می‌شوند. فراخواننده‌ای که
    کلید نمی‌فرستد، رفتارِ پیشین (هر execution_id یک قصد) را نگه می‌دارد تا دو
    سفارشِ مستقلِ هم‌مقدار به‌اشتباه deduplicate نشوند.
    """
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    eid = str(getattr(draft, "execution_id", "") or "").strip()
    if eid:
        return "exec:" + hashlib.sha256(eid.encode("utf-8")).hexdigest()[:32]
    inst = getattr(draft, "instrument", None)
    side = getattr(draft, "side", "")
    parts = [
        str(getattr(inst, "symbol", "") or "").strip().upper(),
        str(getattr(inst, "isin", "") or "").strip().upper(),
        str(getattr(side, "value", side) or "").strip().lower(),
        str(getattr(draft, "price", "") or ""),
        str(getattr(draft, "quantity", "") or ""),
        "" if target_wall_ms is None else str(int(target_wall_ms)),
    ]
    blob = "|".join(parts).encode("utf-8")
    return "auto:" + hashlib.sha256(blob).hexdigest()[:32]


class IntentStore:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or self._default_path()
        self._lock = threading.Lock()

    @staticmethod
    def _default_path() -> str:
        # تست/ابزارهایِ ایزوله می‌توانند مسیرِ جدا بدهند؛ Production = user.db.
        raw = (os.environ.get("BORS_INTENT_DB") or "").strip()
        if raw:
            return raw
        import bors_config
        return bors_config.USER_DB_PATH

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=30000")
        con.execute(_SCHEMA)
        con.execute(_INDEX)
        return con

    def _now(self) -> int:
        return int(time.time())

    def begin(self, *, intent_key: str, execution_id: str, strategy_id: str,
              draft: Any, target_wall_ms: Optional[int]) -> dict[str, Any]:
        """رزروِ قصد. فقط failed_pre_click اجازهٔ شروعِ دوباره دارد."""
        inst = getattr(draft, "instrument", None)
        side = getattr(draft, "side", "")
        now = self._now()
        with self._lock:
            con = self._conn()
            try:
                con.execute("BEGIN IMMEDIATE")
                row = con.execute(
                    "SELECT state, detail, clicked, strategy_id FROM %s"
                    " WHERE intent_key=?" % _TABLE, (intent_key,)).fetchone()
                # چند Strategy می‌توانند یک قصد را prepare کنند (shadow/benchmark)،
                # ولی همان Strategy با execution_id تازه = قصدِ تکراری. تنها
                # استثنا: خطایِ پیش از کلیک که با همان Strategy قابلِ تلاش است.
                if row is not None:
                    same_strategy = str(row["strategy_id"]) == str(strategy_id)
                    allowed = (not int(row["clicked"] or 0)) and (
                        row["state"] == "failed_pre_click"
                        or (row["state"] == "prepared" and not same_strategy))
                    if not allowed:
                        raise IntentBlocked(row["state"], row["detail"])
                fields = (
                    execution_id, strategy_id,
                    int(target_wall_ms) if target_wall_ms is not None else None,
                    str(getattr(inst, "symbol", "") or ""),
                    str(getattr(inst, "isin", "") or ""),
                    str(getattr(side, "value", side) or ""),
                    float(getattr(draft, "price", 0) or 0),
                    float(getattr(draft, "quantity", 0) or 0),
                )
                if row is None:
                    con.execute(
                        "INSERT INTO %s(intent_key, execution_id, strategy_id,"
                        " state, target_wall_ms, symbol, isin, side, price,"
                        " quantity, clicked, detail, created_at, updated_at)"
                        " VALUES(?,?,?,?,?,?,?,?,?,?,0,'',?,?)" % _TABLE,
                        (intent_key, fields[0], fields[1], "prepared",
                         fields[2], fields[3], fields[4], fields[5], fields[6],
                         fields[7], now, now))
                else:
                    # state را عوض نکن: failed_pre_click باید تا bindِ موفق،
                    # اجازهٔ همان قصد را بدهد؛ bind_prepared آن را prepared می‌کند.
                    con.execute(
                        "UPDATE %s SET execution_id=?, strategy_id=?,"
                        " target_wall_ms=?, symbol=?, isin=?, side=?, price=?,"
                        " quantity=?, prepared_id=NULL, updated_at=?"
                        " WHERE intent_key=?" % _TABLE,
                        (*fields, now, intent_key))
                con.commit()
            except IntentBlocked:
                con.rollback()
                raise
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()
        return {"intent_key": intent_key, "state": "prepared"}

    def bind_prepared(self, intent_key: str, prepared_id: str) -> None:
        with self._lock:
            con = self._conn()
            try:
                con.execute(
                    "UPDATE %s SET prepared_id=?, state='prepared',"
                    " updated_at=? WHERE intent_key=?" % _TABLE,
                    (str(prepared_id), self._now(), intent_key))
                con.commit()
            finally:
                con.close()

    def mark_scheduled(self, intent_key: str) -> None:
        with self._lock:
            con = self._conn()
            try:
                con.execute("BEGIN IMMEDIATE")
                row = con.execute("SELECT state FROM %s WHERE intent_key=?" % _TABLE,
                                  (intent_key,)).fetchone()
                if row is None or row["state"] != "prepared":
                    raise IntentBlocked(row["state"] if row else "none",
                                        "intent is not prepared")
                con.execute("UPDATE %s SET state='scheduled', updated_at=?"
                            " WHERE intent_key=?" % _TABLE, (self._now(), intent_key))
                con.commit()
            except IntentBlocked:
                con.rollback()
                raise
            finally:
                con.close()

    def claim_click(self, intent_key: str) -> None:
        """گذارِ اتمیک به clicking؛ فقط یک بار و فقط پیش از هر کلیک."""
        with self._lock:
            con = self._conn()
            try:
                con.execute("BEGIN IMMEDIATE")
                cur = con.execute(
                    "UPDATE %s SET state='clicking', clicked=1, updated_at=?"
                    " WHERE intent_key=? AND state IN ('prepared','scheduled')"
                    " AND clicked=0" % _TABLE,
                    (self._now(), intent_key))
                if cur.rowcount != 1:
                    row = con.execute(
                        "SELECT state, detail FROM %s WHERE intent_key=?" % _TABLE,
                        (intent_key,)).fetchone()
                    con.rollback()
                    raise IntentBlocked(row["state"] if row else "none",
                                        (row["detail"] if row else "no intent"))
                con.commit()
            except IntentBlocked:
                raise
            finally:
                con.close()

    def finish(self, intent_key: str, state: str, detail: str = "",
               *, result: Optional[Mapping[str, Any]] = None) -> None:
        with self._lock:
            con = self._conn()
            try:
                con.execute(
                    "UPDATE %s SET state=?, detail=?, result_json=?, updated_at=?"
                    " WHERE intent_key=?" % _TABLE,
                    (str(state), str(detail)[:200],
                     json.dumps(dict(result), ensure_ascii=False)[:12000]
                     if result is not None else None,
                     self._now(), intent_key))
                con.commit()
            finally:
                con.close()

    def mark_prepare_failed(self, intent_key: str, strategy_id: str,
                            detail: str = "") -> None:
        """خطایِ prepare پیش از bind؛ اگر prepare موفقِ دیگری bind نشده باشد."""
        with self._lock:
            con = self._conn()
            try:
                con.execute(
                    "UPDATE %s SET state='failed_pre_click', clicked=0,"
                    " detail=?, updated_at=? WHERE intent_key=? AND clicked=0"
                    " AND prepared_id IS NULL AND strategy_id=?" % _TABLE,
                    (str(detail)[:200], self._now(), intent_key,
                     str(strategy_id)))
                con.commit()
            finally:
                con.close()

    def fail_pre_click(self, intent_key: str, detail: str = "") -> None:
        with self._lock:
            con = self._conn()
            try:
                con.execute(
                    "UPDATE %s SET state='failed_pre_click', clicked=0, detail=?,"
                    " updated_at=? WHERE intent_key=?" % _TABLE,
                    (str(detail)[:200], self._now(), intent_key))
                con.commit()
            finally:
                con.close()

    def abort(self, intent_key: str) -> None:
        with self._lock:
            con = self._conn()
            try:
                row = con.execute(
                    "SELECT state, clicked FROM %s WHERE intent_key=?" % _TABLE,
                    (intent_key,)).fetchone()
                if row is None:
                    return
                # اگر کلیک شروع شده، «aborted» ادعایِ بی‌کلیک نیست.
                state = "unknown" if int(row["clicked"] or 0) else "aborted"
                con.execute("UPDATE %s SET state=?, updated_at=? WHERE intent_key=?"
                            % _TABLE, (state, self._now(), intent_key))
                con.commit()
            finally:
                con.close()

    def get(self, intent_key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            con = self._conn()
            try:
                row = con.execute("SELECT * FROM %s WHERE intent_key=?" % _TABLE,
                                  (intent_key,)).fetchone()
            finally:
                con.close()
        if row is None:
            return None
        out = dict(row)
        try:
            out["result"] = json.loads(out["result_json"]) if out["result_json"] else None
        except Exception:
            out["result"] = None
        return out

    def recover_stale(self) -> dict[str, int]:
        """پس از restart: clicking⇒unknown؛ scheduled/prepared⇒needs_review/missed.

        هیچ‌چیز خودکار اجرا نمی‌شود؛ کارِ زمان‌بندی‌شدهٔ درون‌حافظه‌ای با
        restart از بین رفته و «اجرایِ دوباره» مجاز نیست. intentِ آینده برایِ
        بررسیِ صریح می‌ماند و intentِ منقضی «missed» می‌شود.
        """
        counts: dict[str, int] = {"unknown": 0, "needs_review": 0, "missed": 0,
                                  "aborted": 0}
        now_ms = int(time.time() * 1000)
        with self._lock:
            con = self._conn()
            try:
                cur = con.execute(
                    "UPDATE %s SET state='unknown', detail=?, updated_at=?"
                    " WHERE state='clicking'" % _TABLE,
                    ("recovered after restart: click may have happened",
                     self._now()))
                counts["unknown"] += int(cur.rowcount or 0)
                rows = con.execute(
                    "SELECT intent_key, target_wall_ms FROM %s"
                    " WHERE state IN ('scheduled','prepared')" % _TABLE).fetchall()
                for row in rows:
                    target = row["target_wall_ms"]
                    if target is not None and int(target) <= now_ms:
                        new, detail = "missed", "target expired during restart"
                    else:
                        new, detail = "needs_review", (
                            "schedule was in memory; review before any retry")
                    con.execute(
                        "UPDATE %s SET state=?, detail=?, updated_at=?"
                        " WHERE intent_key=?" % _TABLE,
                        (new, detail, self._now(), row["intent_key"]))
                    counts[new] += 1
                con.commit()
            finally:
                con.close()
        return counts


__all__ = ["IntentStore", "IntentBlocked", "derive_key", "BLOCKING_STATES",
           "TERMINAL_STATES"]
