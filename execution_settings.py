# -*- coding: utf-8 -*-
"""execution_settings.py — تنظیماتِ **غیرمحرمانۀ** راهِ اتصال، رویِ `user.db`.

چرا رویِ دیسک و نه متغیر محیطی: بیلدِ منجمدِ دسکتاپ هیچ env ای از کاربر نمی‌گیرد،
پس درِ v1.0.93 راهی برای رسیدن به آداپتور واقعی نبود — سنجشِ همین ماشین:
`adapter="mock"` و تنها کلیدِ خروج `BORS_EXECUTION_ADAPTER=easytrader|mofid` که فقط
درِ اجرایِ منبعی ست می‌شود. این فایل همان کلید را به خودِ برنامه می‌آورد، با سه قفل:

  ۱) اینجا **هیچ** مقدارِ محرمانه‌ای ذخیره نمی‌شود. token/رمز/کوکی/Authorization
     هرگز به این جدول نمی‌آید و هر کلیدِ ناشناخته رد می‌شود (`ALLOWED_KEYS`).
  ۲) `writes_allowed` هرگز از این مسیر روشن نمی‌شود. نوشتنِ سفارش فقط با
     با `BORS_EXECUTION_LIVE=1` ممکن است — همان گامِ D1ِ ماتریس که رأیِ مالک است:
     ورودِ تعاملی و آتش‌زدنِ سفارش، تصمیمِ جدا و آگاهانۀ خودِ کاربر.
  ۳) متغیر محیطی بر تنظیمِ دیسک مقدم است؛ تنظیمِ دیسک فقط وقتی خوانده می‌شود که
     env ست نشده باشد (`source` همان را گزارش می‌دهد، تا هیچ‌کس حدس نزند).

`read_only` یعنی چه؟ ترافیکِ **فقط‌خواندنی** به کارگزاری مجاز است تا وجودِ نشست
راستی‌آزمایی شود و فهرست‌ها خوانده شوند. بی‌این، «تأییدِ نشست» هرگز ممکن نبود:
`_call()` همه‌چیز را به `live` گره می‌زد و `live` به envِ نوشتن.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from typing import Any

ADAPTER_MOCK = "mock"
ADAPTER_EASYTRADER = "easytrader"
#: پروتکلِ جدا (Titan). تا Round 15.5 عمداً به easytrader alias می‌شد چون آداپتور
#: واقعی نداشت؛ از Round 16 مسیرهایِ فقط‌خواندنیِ خودش را دارد.
ADAPTER_MOFID = "mofid"
ADAPTERS = (ADAPTER_MOCK, ADAPTER_EASYTRADER, ADAPTER_MOFID)

ENV_ADAPTER = "BORS_EXECUTION_ADAPTER"
ENV_LIVE = "BORS_EXECUTION_LIVE"

#: تنها کلیدهایی که نوشتنشان مجاز است. افزودنِ کلیدِ تازه = افزودنِ سطحِ حمله؛
#: هیچ «yaml/json دلخواه» اینجا پذیرفته نمی‌شود.
ALLOWED_KEYS = ("adapter", "read_only")

_TABLE = "execution_settings"
_SCHEMA = (f"CREATE TABLE IF NOT EXISTS {_TABLE}("
           " key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at INTEGER NOT NULL)")
_LOCK = threading.Lock()


def _db_path() -> str:
    import bors_config
    return bors_config.USER_DB_PATH


def _connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or _db_path(), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _env_flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip() in ("1", "true", "yes", "on")


def _normalise(key: str, value: Any) -> str:
    """تنظیمِ ناشناخته و مقدارِ ناشناخته هر دو `ValueError` — بی‌سکوت."""
    if key not in ALLOWED_KEYS:
        raise ValueError(f"کلیدِ ناشناخته: {key}")
    v = str(value or "").strip().lower()
    if key == "adapter":
        v = {"orbis": ADAPTER_EASYTRADER}.get(v, v)
        if v not in ADAPTERS:
            raise ValueError(f"آداپتورِ ناشناخته: {value}")
        return v
    if v in ("1", "true", "yes", "on", "read_only", "readonly"):
        return "1"
    if v in ("0", "false", "no", "off", ""):
        return "0"
    raise ValueError(f"مقدارِ ناشناخته برایِ read_only: {value}")


def read(db_path: str | None = None) -> dict[str, Any]:
    """تنظیمِ مؤثر، با منشأِ هر تصمیم. هیچ مقداری غیر از دو کلیدِ مجاز خوانده نمی‌شود."""
    out: dict[str, Any] = {"adapter": ADAPTER_MOCK, "source": "default",
                           "read_only": False, "read_only_source": "default",
                           "live_env": _env_flag(ENV_LIVE), "updated_at": None}
    stored: dict[str, str] = {}
    try:
        conn = _connect(db_path)
        try:
            # خواندن هیچ جدولی نمی‌سازد؛ ساختنِ جدول فقط وقتی است که چیزی واقعاً
            # نوشته می‌شود. بی‌این، هر `import api.execution` (گاردها از جمله) یک
            # جدول رویِ user.dbِ واقعی می‌افزود.
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                "AND name=?", (_TABLE,)).fetchone():
                rows = []
            else:
                rows = conn.execute(
                    f"SELECT key, value, updated_at FROM {_TABLE} "
                    f"WHERE key IN ('adapter', 'read_only')").fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        rows = []
    for key, value, updated_at in rows:
        stored[str(key)] = str(value)
        out["updated_at"] = max(int(out["updated_at"] or 0), int(updated_at or 0)) or None

    env_adapter = (os.environ.get(ENV_ADAPTER) or "").strip().lower()
    if env_adapter:
        out["adapter"] = _normalise("adapter", env_adapter)
        out["source"] = "env"
    elif stored.get("adapter"):
        out["adapter"] = _normalise("adapter", stored["adapter"])
        out["source"] = "settings"
    if stored.get("read_only") is not None:
        out["read_only"] = stored["read_only"] == "1"
        out["read_only_source"] = "settings"
    # نوشتن فقط با envِ نوشتن؛ تنظیمِ دیسک هرگز این را روشن نمی‌کند (§۲).
    real = out["adapter"] in (ADAPTER_EASYTRADER, ADAPTER_MOFID)
    out["writes_allowed"] = bool(out["live_env"]) and real
    out["traffic_allowed"] = bool(out["writes_allowed"] or (real and out["read_only"]))
    return out


def set_value(key: str, value: Any, db_path: str | None = None) -> dict[str, Any]:
    """یک کلیدِ مجاز را می‌نویسد و وضعیتِ مؤثرِ تازه را برمی‌گرداند."""
    v = _normalise(key, value)
    conn = _connect(db_path)
    try:
        with _LOCK:
            conn.executescript(_SCHEMA)
            conn.execute(
                f"INSERT OR REPLACE INTO {_TABLE}(key, value, updated_at) VALUES (?, ?, ?)",
                (key, v, int(time.time())))
            conn.commit()
    finally:
        conn.close()
    return read(db_path)


__all__ = ["ADAPTERS", "ADAPTER_EASYTRADER", "ADAPTER_MOCK", "ADAPTER_MOFID",
           "ALLOWED_KEYS", "ENV_ADAPTER", "ENV_LIVE", "read", "set_value"]
