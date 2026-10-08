#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""watchlist_store.py — ذخیرهٔ واچ‌لیست کاربر + ساخت ماتریس تایید سه‌گانه.

چرا یک ماژول جدا و نه داخل app.py:
  * همان مسیری که fts_engine.py و confidence_engine.py می‌روند: منطق در ماژول،
    route در app.py فقط لایهٔ نازک HTTP است. با این کار گاردِ dev بدون FastAPI
    و بدون باز کردن پورت قابل اجراست.
  * نوشتن روی دیتابیس فقط همین‌جاست. confidence_engine عمداً هیچ چیزی ذخیره
    نمی‌کند (خروجی‌اش با هر sync عوض می‌شود)؛ اینجا فقط «انتخابِ کاربر» می‌ماند.

کلید جدول norm_fa(نماد) است، نه رشتهٔ خام. دلیلش باگِ رفع‌شدهٔ v9.7.3 است:
همان شرکت در market.db با دو امضا وجود دارد («داريك» با ي عربی و «داریک» با ی
فارسی). اگر PK روی رشتهٔ خام می‌بود، یک نماد دو ردیف واچ‌لیست می‌گرفت و
ماتریس تکراری تولید می‌شد. با کلیدِ نرمال، افزودن هر املا همان ردیف را
به‌روزرسانی می‌کند و رشتهٔ نمایشِ آخر جای قبلی را می‌گیرد.
"""
from __future__ import annotations

import datetime
import sqlite3
from typing import Iterable, Optional

import confidence_engine
import fts_engine

# سه مفهومِ جدا (رأیِ مالک ۱۴۰۵-۰۷-۱۶، §۹ و §۱۰ — پیش‌تر هر سه «watchlist_max»
# نام داشتند و یکی از زیرِ بارِ دیگری له می‌شد):
#   USER_WATCHLIST_MAX  ظرفیتِ خودِ واچ‌لیستِ کاربر — اینکه چند نماد *ماندگار*
#                       نگاه داشته می‌شود. هیچ جای دیگری نباید این عدد را به‌عنوان
#                       سقفِ محاسبه یا نمایش مصرف کند.
#   MATRIX_PROBE_MAX    سقفِ ردیف‌هایِ یک ماتریسِ آزمایشی (سنگینیِ یک درخواستِ
#                       HTTP)، نه ظرفیتِ کاربر.
USER_WATCHLIST_MAX = 60
MATRIX_PROBE_MAX = 60
MAX_NOTE = 200
MAX_NAME = 120

DDL = """
CREATE TABLE IF NOT EXISTS user_watchlists (
    symbol_norm TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL DEFAULT '',
    name        TEXT DEFAULT '',
    note        TEXT DEFAULT '',
    added_at    TEXT DEFAULT ''
)
"""


def ensure_table(conn: sqlite3.Connection) -> None:
    """جدول را یک‌بار می‌سازد (idempotent — همان الگوی selection_decisions در app.py)."""
    conn.execute(DDL)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_uwl_added ON user_watchlists(added_at)")


# ============================================================ CRUD
def add(conn: sqlite3.Connection, symbol: str, name: str = "",
        note: str = "", when: str = None) -> Optional[dict]:
    """افزودن/بروزرسانی یک نماد. نماد تهی → None (بی‌سکوت، ولی بدون نوشتن)."""
    sym = str(symbol or "").strip()
    if not sym:
        return None
    key = fts_engine.norm_fa(sym)
    if not key:
        return None
    stamp = when or datetime.datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO user_watchlists(symbol_norm, symbol, name, note, added_at)"
        " VALUES(?,?,?,?,?)"
        " ON CONFLICT(symbol_norm) DO UPDATE SET"
        "   symbol=excluded.symbol,"
        "   name=CASE WHEN excluded.name<>'' THEN excluded.name ELSE user_watchlists.name END,"
        "   note=CASE WHEN excluded.note<>'' THEN excluded.note ELSE user_watchlists.note END",
        (key, sym[:MAX_NAME], str(name or "")[:MAX_NAME],
         str(note or "")[:MAX_NOTE], stamp))
    return get(conn, key)


def remove(conn: sqlite3.Connection, symbol: str) -> int:
    """حذف با هر املا؛ تعداد ردیف‌های حذف‌شده را برمی‌گرداند."""
    key = fts_engine.norm_fa(str(symbol or "").strip())
    if not key:
        return 0
    cur = conn.execute("DELETE FROM user_watchlists WHERE symbol_norm = ?", (key,))
    return cur.rowcount or 0


def get(conn: sqlite3.Connection, symbol_norm: str) -> Optional[dict]:
    r = conn.execute("SELECT * FROM user_watchlists WHERE symbol_norm = ?",
                     (symbol_norm,)).fetchone()
    # `_row(None)` رویِ `None.keys()` می‌ترکید، و `get()` تنها راهِ پرسیدنِ
    # «هست یا نیست» است: پس افزودنِ هر نمادِ **نو** درِ `POST /api/watchlist`
    # قبل از رسیدنِ INSERT با خطایِ `'NoneType' object has no attribute 'keys'`
    # برمی‌گشت (handler خودش `is None` را انتظار دارد).
    return _row(r) if r is not None else None


def list_rows(conn: sqlite3.Connection) -> list:
    """همهٔ واچ‌لیست، تازه‌ترین‌ها اول."""
    return [_row(r) for r in conn.execute(
        "SELECT * FROM user_watchlists ORDER BY added_at DESC, symbol_norm ASC")]


def count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM user_watchlists").fetchone()[0] or 0)


def _row(r) -> dict:
    d = {k: r[k] for k in r.keys()} if not isinstance(r, tuple) else dict(
        zip(("symbol_norm", "symbol", "name", "note", "added_at"), r))
    d["symbol_norm"] = d.get("symbol_norm") or ""
    return {"symbol": d.get("symbol") or "", "name": d.get("name") or "",
            "note": d.get("note") or "", "added_at": d.get("added_at") or "",
            "norm": d.get("symbol_norm") or ""}


# ============================================================ ماتریس
def matrix(conn: sqlite3.Connection, symbols: Iterable = None,
           cfg: dict = None, fts_cfg: dict = None) -> dict:
    """ماتریس تایید سه‌گانه برای واچ‌لیست — با دو کوئریِ کل‌بازاری، نه N+1.

    `symbols=None` از جدول برمی‌دارد؛ فهرست صریح هم می‌پذیرد (برای اینکه UI
    بتواند بدون ذخیره، نتایج اسکرینر را هم همینجا نشان دهد).

    ترتیب مهم است: build_ctx یک‌بار، bulk_scan یک‌بار، بعد triple_many با
    fund_rows. اگر fund_rows داده نشود confidence_engine به‌ازای هر نماد
    ~۲۰ کوئری می‌زند؛ برای ۶۰ نماد یعنی ~۱۲۰۰ کوئری در یک درخواست HTTP.
    """
    if symbols is None:
        rows = list_rows(conn)
        syms = [r["symbol"] for r in rows]
        meta = {fts_engine.norm_fa(r["symbol"]): r for r in rows}
    else:
        syms = [str(s).strip() for s in symbols if str(s or "").strip()][:MATRIX_PROBE_MAX]
        meta = {}
    if not syms:
        return {"status": "success", "count": 0, "rows": [], "asof": {},
                "limit": MATRIX_PROBE_MAX, "capacity": USER_WATCHLIST_MAX}
    # `conn` اینجا connectionsِ *کاربر* است (user.db: جدولِ واچ‌لیست و یادداشت‌ها).
    # سه تابعِ confidence_engine اما جدول‌های بازار (instruments،
    # financial_statements، market_watch، …) را می‌خوانند و آن‌ها درِ market.db
    # اند. بی‌این تفکیک، `/api/watchlist/matrix?symbols=…` با
    # `no such table: instruments` می‌شکست (سابقاً همین اتفاق می‌افتاد و فقط
    # حالتِ «خودِ جدول» کار می‌کرد، آن هم وقتی واچ‌لیست خالی بود).
    import bors_config
    mconn = sqlite3.connect(bors_config.DB_PATH, timeout=30)
    try:
        ctx = confidence_engine.build_ctx(mconn)
        fund_rows = confidence_engine.fund_map(mconn, cfg=fts_cfg)
        out = confidence_engine.triple_many(mconn, syms, ctx=ctx, cfg=cfg,
                                           fts_cfg=fts_cfg, fund_rows=fund_rows)
    finally:
        mconn.close()
    for rec in out:
        m = meta.get(fts_engine.norm_fa(rec.get("symbol") or "")) or {}
        rec["note"] = m.get("note") or ""
        rec["watch_name"] = m.get("name") or ""
        rec["added_at"] = m.get("added_at") or ""
    # asof از خودِ ردیف‌ها خوانده می‌شود؛ build_ctx هیچ کلید asof ندارد
    # (کلیدهایش: cfg, daily, index, liq, m141, sessions, tape, watch,
    # total_mcap_rials) و ساختن کلید جعلی یعنی «تاریخی» که هیچ‌کس تولیدش
    # نکرده. هر ستون asof را خودش triple برمی‌گرداند.
    def _latest(k):
        vals = [r["asof"].get(k) for r in out if isinstance(r.get("asof"), dict)
                and r["asof"].get(k)]
        return max(vals, key=lambda v: str(v)) if vals else None
    return {"status": "success", "count": len(out), "rows": out,
            "limit": MATRIX_PROBE_MAX,
            "capacity": USER_WATCHLIST_MAX,
            "asof": {"tech": _latest("tech"), "tape": _latest("tape"),
                     "fund": _latest("fund")}}
