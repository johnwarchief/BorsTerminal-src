# -*- coding: utf-8 -*-
"""execution_owner_approval.py — مجوزِ صریح و قابلِ‌ردیابیِ مالک.

پیش‌فرض هیچ ردیفی ندارد ⇒ approved=False. این ماژول هیچ‌وقت خودکار تأیید
نمی‌کند و هیچ توکن/کوکی‌ای ذخیره نمی‌کند. live flags جدایند و این جدول
فقط ورودیِ گیتِ readiness است.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from typing import Any, Optional

_TABLE = "execution_owner_approval"
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS %s("
    " scope TEXT PRIMARY KEY, approved INTEGER NOT NULL,"
    " phrase TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',"
    " approved_at INTEGER NOT NULL)" % _TABLE)


class OwnerApprovalStore:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or self._default_path()
        self._lock = threading.Lock()

    @staticmethod
    def _default_path() -> str:
        raw = (os.environ.get("BORS_OWNER_APPROVAL_DB") or "").strip()
        if raw:
            return raw
        import bors_config
        return bors_config.USER_DB_PATH

    def _conn(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=30000")
        con.execute(_SCHEMA)
        return con

    def state(self, scope: str = "live-order") -> dict[str, Any]:
        # فقط‌خواندنی: نبودِ جدول یعنی «تأییدی نیست»، نه ساختِ جدول در GET.
        row = None
        try:
            con = sqlite3.connect(
                "file:%s?mode=ro" % os.path.abspath(self.path).replace(chr(92), '/'),
                uri=True, timeout=10)
            con.row_factory = sqlite3.Row
            try:
                row = con.execute(
                    "SELECT * FROM %s WHERE scope=?" % _TABLE,
                    (str(scope),)).fetchone()
            finally:
                con.close()
        except sqlite3.Error:
            row = None
        if row is None:
            return {"scope": str(scope), "approved": False, "phrase": "",
                    "note": "", "approved_at": None,
                    "source": "execution_owner_approval/none"}
        return {"scope": str(scope), "approved": bool(row["approved"]),
                "phrase": str(row["phrase"] or ""), "note": str(row["note"] or ""),
                "approved_at": int(row["approved_at"] or 0),
                "source": "execution_owner_approval"}

    def approve(self, phrase: str, *, scope: str = "live-order",
                note: str = "", expected_phrase: Optional[str] = None) -> dict[str, Any]:
        expected = (expected_phrase or os.environ.get(
            "BORS_OWNER_APPROVAL_PHRASE") or "").strip()
        if not expected:
            raise ValueError("OWNER_APPROVAL_PHRASE_UNCONFIGURED")
        if str(phrase or "").strip() != expected:
            raise ValueError("OWNER_APPROVAL_PHRASE_MISMATCH")
        now = int(time.time())
        with self._lock:
            con = self._conn()
            try:
                con.execute(
                    "INSERT OR REPLACE INTO %s(scope, approved, phrase, note,"
                    " approved_at) VALUES(?,1,?,?,?)" % _TABLE,
                    (str(scope), str(phrase)[:120], str(note)[:200], now))
                con.commit()
            finally:
                con.close()
        return self.state(scope)

    def revoke(self, scope: str = "live-order", note: str = "") -> dict[str, Any]:
        now = int(time.time())
        with self._lock:
            con = self._conn()
            try:
                con.execute(
                    "INSERT OR REPLACE INTO %s(scope, approved, phrase, note,"
                    " approved_at) VALUES(?,0,'',?,?)" % _TABLE,
                    (str(scope), str(note)[:200], now))
                con.commit()
            finally:
                con.close()
        return self.state(scope)


__all__ = ["OwnerApprovalStore"]
