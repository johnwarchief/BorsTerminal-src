# -*- coding: utf-8 -*-
"""tape_flag_history.py — سابقۀ ماندگارِ «کدام فیلترِ تابلو، کدام نماد، کدام روز».

چرا این فایل هست: هفت پرچمِ `tape_flags` تا پیش از این فقط درِ RAMِ هر درخواست
حساب می‌شدند و هیچ‌جا نوشته نمی‌شدند؛ پس پرسشِ مالک «این نماد در چند روزِ اخیر
چند بار حجم مشکوک داشته» جوابِ داده‌شده نداشت — فقط جوابِ حدسی. این ماژول همان
داوریِ خودِ اپ را درِ یک جدولِ روزانه می‌نویسد و همان را می‌خواند.

دو قراردادِ مهم:

۱) **ماضی بازسازی نمی‌شود.** `[is6]`، `allowed_min` و صفِ امروز درِ بانک
    نگه داشته نمی‌شوند (`tse_inst_stat` و `market_watch` روزانه بازنویسی
    می‌شوند)، پس هیچ روزِ گذشته‌ای را از دادهٔ امروز نمی‌سازیم. اولین روزی که
    این جدول درِ آن نوشته شده، `reliable_from` است و پیش‌از آن «ثبت نشده»
    خوانده می‌شود — نه «غیرفعال».

۲) **یک روز = یک ردیف.** کلیدِ طبیعی (ins_code, flag, d_even) با UPSERT؛ پس
    اجرایِ دوبلۀ سینک یا هر تعداد رفرشِ تابلو ردیفِ تکراری نمی‌سازد. شمارۀ
    «دفعات» درِ رابط همان شمارِ روزهاست، و `passes` جدا از آن می‌گوید درِ آن
    روز چند نوبتِ ثبت (حداکثر یکی هر FLUSH_S ثانیه) فیلتر روشن بوده.

فایل هیچ داوری‌ای نمی‌سازد: پرچم‌ها را همان `tape_flags.apply_tape_flags`
می‌دهد و این‌جا فقط نوشته/خوانده می‌شوند.
"""
from __future__ import annotations

import json
import sqlite3
import time

FLAGS = ("f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh", "f_smart", "f_legal")

# شواهدی که درِ اولین دیدارِ همان روز ثبت می‌شوند — همان ستون‌هایی که خودِ
# فرمول‌ها خوانده‌اند؛ چیزِ دیگری نمی‌سازیم.
EVIDENCE_COLS = ("tvol", "p_closing", "p_last", "percent_last", "z_tot_tran",
                 "vol_ratio_file", "buyer_power_raw", "resistance_59", "is6")

TAPE_FLAG_DAY = """
CREATE TABLE IF NOT EXISTS tape_flag_day (
    ins_code TEXT NOT NULL,
    flag TEXT NOT NULL,
    d_even INTEGER NOT NULL,
    symbol TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    passes INTEGER NOT NULL DEFAULT 1,
    evidence TEXT,
    source TEXT,
    PRIMARY KEY (ins_code, flag, d_even))
"""

# «آن روز واقعاً رصد شد» — بی‌این علامت، روزِ بی‌ردیف میانِ دو روزِ ثبت‌شده
# نمی‌تواند از روزی که برنامه خاموش بوده جدا شود.
TAPE_FLAG_DAY_META = """
CREATE TABLE IF NOT EXISTS tape_flag_day_meta (
    d_even INTEGER PRIMARY KEY,
    first_at TEXT, last_at TEXT,
    passes INTEGER NOT NULL DEFAULT 1,
    symbols INTEGER,
    active_rows INTEGER)
"""

TABLES = ("tape_flag_day", "tape_flag_day_meta")

FLUSH_S = 240.0            # حداقلِ فاصلۀ دو نوبتِ ثبت درِ یک روز
_ensured = False
_last_flush: dict[int, float] = {}
_last_token: dict[int, object] = {}
_last_err: str | None = None


def ensure(conn) -> None:
    """جدول‌ها، یک‌بار درِ هر پروسه (CREATE IF NOT EXISTS ارزان نیست اگر هر
    درخواست بزند؛ و بانکِ قفل‌شده نباید درخواستِ خواندن را ۵۰۰ کند)."""
    global _ensured, _last_err
    if _ensured:
        return
    try:
        for ddl in (TAPE_FLAG_DAY, TAPE_FLAG_DAY_META):
            conn.execute(ddl)
        conn.commit()
        _ensured = True
    except sqlite3.Error as e:
        _last_err = f"{type(e).__name__}: {e}"


def note_error(exc: BaseException) -> None:
    """خطایِ مسیرِ نوشتن را ثبت می‌کند تا خواننده صادق بگوید «ثبت نشد»."""
    global _last_err
    _last_err = f"{type(exc).__name__}: {exc}"


def record_observations(conn, df, session_day: int, source: str = "board",
                        token=None) -> int:
    """پرچم‌هایِ همین قاب را برایِ روزِ معاملاتیِ جاری می‌نویسد.

    برگشت: شمارۀ ردیف‌هایی که همین نوبت نوشته/تازه شدند (۰ یعنی یا نوبت تکراری
    بوده یا پرچمی روشن نبود). هر استثنا بلعیده می‌شود و درِ `_last_err`
    می‌ماند: ثبتِ سابقه حقِ ندارد تابلو را بشکند.

    `token` نشاندۀ «این داده نو است» (درِ اپ: شمارۀ سینک). برابرِ آخرین نشانۀ
    همان روز ⇒ نوبتی ثبت نمی‌شود. بی‌این، هر رفرشِ تابلو — و هر پولینگِ
    پنج‌ثانیه‌ای بعد از تعطیلی بازار — یک «دفعۀ» ساختگی به شمارش اضافه می‌کرد.
    `FLUSH_S` کفِ زمانی است، نه کلید: سینکِ پشت‌سرِ هم هم هر ۴ دقیقه یک نوبت
    می‌نویسد وگرنه یک دورۀ پرِ نوسان، شمارۀ دفعات را می‌ترکاند.
    """
    global _last_err
    if df is None or not len(df) or not session_day:
        return 0
    now = time.time()
    if token is not None and _last_token.get(session_day) == token:
        return 0
    if now - _last_flush.get(session_day, 0.0) < FLUSH_S:
        return 0
    _last_flush[session_day] = now
    _last_token[session_day] = token
    try:
        ensure(conn)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        # قابِ تابلو بر `ins_code` ایندکس است (ستون نیست)؛ پس ایندکس همان
        # شناسۀِ پایدار است و اگر جایی ستون بود، همان ستون خوانده می‌شود.
        have = set(df.columns)
        if "ins_code" in have:
            codes = [str(x or "") for x in df["ins_code"].tolist()]
        else:
            codes = [str(x or "") for x in df.index.tolist()]
        names = ([str(x or "") for x in df["symbol"].tolist()] if "symbol" in have
                 else [""] * len(codes))
        flags = {f: df[f].fillna(False).astype(bool).tolist()
                 for f in FLAGS if f in have}
        ev_src = {c: df[c].tolist() for c in EVIDENCE_COLS if c in have}
        rows = []
        for i, code in enumerate(codes):
            if not code:
                continue
            on = [f for f in FLAGS if f in flags and flags[f][i]]
            if not on:
                continue
            ev = {}
            for c, src in ev_src.items():
                v = src[i]
                if v is not None and v == v:        # None و NaN بیرون می‌مانند
                    ev[c] = v
            evs = json.dumps(ev, ensure_ascii=False, allow_nan=False, default=str)
            for f in on:
                rows.append((code, f, int(session_day), names[i],
                             stamp, stamp, evs, source))
        if not rows:
            return 0
        c = conn.cursor()
        # first_seen_at و evidence از اولین دیدار می‌مانند؛ فقط last_seen_at و
        # passes جلو می‌روند — وگرنه «اولین بار کِی؟» با هر رفرش عوض می‌شد.
        c.executemany(
            "INSERT INTO tape_flag_day(ins_code, flag, d_even, symbol, first_seen_at,"
            "                          last_seen_at, evidence, source)"
            " VALUES(?,?,?,?,?,?,?,?)"
            " ON CONFLICT(ins_code, flag, d_even) DO UPDATE SET"
            "   last_seen_at = excluded.last_seen_at,"
            "   passes = tape_flag_day.passes + 1", rows)
        c.execute(
            "INSERT INTO tape_flag_day_meta(d_even, first_at, last_at, passes, symbols)"
            " VALUES(?,?,?,1,?)"
            " ON CONFLICT(d_even) DO UPDATE SET"
            "   last_at = excluded.last_at,"
            "   passes = tape_flag_day_meta.passes + 1,"
            "   symbols = excluded.symbols",
            (int(session_day), stamp, stamp,
             len({r[0] for r in rows})))
        conn.commit()
        return len(rows)
    except Exception as e:                              # noqa: BLE001
        _last_err = f"{type(e).__name__}: {e}"
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        return 0


def trading_days(conn, limit: int = 20) -> list[int]:
    """روزهایی که **واقعاً رصد شده‌اند** — نه هر روزِ تقویمی."""
    try:
        return [int(r[0]) for r in conn.execute(
            "SELECT d_even FROM tape_flag_day_meta ORDER BY d_even DESC LIMIT ?",
            (int(limit),)).fetchall()]
    except sqlite3.Error:
        return []


def reliable_from(conn) -> int | None:
    try:
        r = conn.execute("SELECT MIN(d_even) FROM tape_flag_day_meta").fetchone()
    except sqlite3.Error:
        return None
    return int(r[0]) if r and r[0] is not None else None


def history_for(conn, ins_codes, days: int = 20) -> dict:
    """سابقۀ چندروزۀ هفت فیلتر برایِ چند نماد، به‌همراہ تقویمِ ثبت.

    خروجی: {days: […از کهنه به تازه…], reliable_from, by_symbol:
            {ins_code: {flag: {days: {d_even: {active, first_at, last_at,
                                               passes, evidence}},
                              total, last_seen_at}}}}
    روزی که درِ `days` هست و ردیفی ندارد یعنی «غیرفعال»؛ روزی که درِ `days`
    نیست یعنی «ثبت نشده» — این دو هرگز یکی نمی‌شوند.
    """
    codes = [str(c) for c in (ins_codes or []) if c]
    cal = list(reversed(trading_days(conn, days)))
    out = {"days": cal, "reliable_from": reliable_from(conn), "by_symbol": {},
           "flags": list(FLAGS), "write_error": _last_err}
    if not codes or not cal:
        # تقویمِ خالی یعنی هنوز هیچ روزی رصد نشده — کوئری با `IN ()` نمی‌دود،
        # و پاسخِ خالی هم صادق است: سابقه‌ای نیست، نه «همه جا غیرفعال».
        return out
    # دو فهرستِ جدا، دو شمارِ جدا: اگر یک `marks` برایِ هر دو به‌کار رود،
    # شمارۀ placeholder با شمارۀ پارامتر نمی‌خواند و کوئری بی‌صدا هیچ
    # ردیفی برنمی‌گرداند (سوختنِ واقعیِ ۱۴۰۵-۰۷-۲۱ درِ نگهبان).
    ph_codes = ",".join("?" * len(codes))
    ph_days = ",".join("?" * len(cal))
    try:
        rows = conn.execute(
            f"SELECT ins_code, flag, d_even, first_seen_at, last_seen_at, passes, evidence"
            f" FROM tape_flag_day WHERE ins_code IN ({ph_codes}) AND d_even IN ({ph_days})",
            [*codes, *cal]).fetchall()
    except sqlite3.Error as e:
        out["write_error"] = f"{type(e).__name__}: {e}"
        return out
    by: dict = out["by_symbol"]
    for code, flag, d_even, first_at, last_at, passes, evidence in rows:
        s = by.setdefault(code, {})
        f = s.setdefault(flag, {"days": {}, "total": 0, "last_seen_at": None})
        try:
            ev = json.loads(evidence) if evidence else {}
        except (TypeError, ValueError):
            ev = {}
        f["days"][int(d_even)] = {"active": True, "first_at": first_at, "last_at": last_at,
                                  "passes": int(passes or 1), "evidence": ev}
        f["total"] += 1
        if last_at and (f["last_seen_at"] is None or last_at > f["last_seen_at"]):
            f["last_seen_at"] = last_at
    # روزهایِ ثبت‌شدۀ بدونِ ردیف = «غیرفعال» (نه نبودِ داده)
    for code in codes:
        s = by.setdefault(code, {})
        for flag in FLAGS:
            f = s.setdefault(flag, {"days": {}, "total": 0, "last_seen_at": None})
            for d in cal:
                f["days"].setdefault(d, {"active": False, "first_at": None, "last_at": None,
                                         "passes": 0, "evidence": {}})
    return out


def summary(conn, ins_code: str) -> dict:
    """یک‌خطیِ هر فیلتر برایِ سرِ پروندۀ نماد: چند روز، آخرین بار کِی."""
    h = history_for(conn, [ins_code])
    per = (h.get("by_symbol") or {}).get(str(ins_code)) or {}
    return {flag: {"total": v.get("total", 0), "last_seen_at": v.get("last_seen_at")}
            for flag, v in per.items()}
