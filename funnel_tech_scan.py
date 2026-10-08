# -*- coding: utf-8 -*-
"""funnel_tech_scan.py — داوریِ تکنیکالِ **کلِ جوامع**، یک‌بار، بازنشانیِ افزایشی.

چرا این فایل هست: `api/screener.py` تکنیکال را فقط برایِ ردیف‌هایِ واچ‌لیست
(حداکثر `watchlist_max` = ۵۰) حساب می‌کرد و فرانت هم `TECH_QUERY_CAP = 60` را
جدا می‌زد؛ یعنی «داورِ تکنیکال» درِ عمل رویِ ۵۰-۶۰ نماد کار می‌کرد و بقیهٔ
جوامع بی‌داوری می‌ماندند. دلیلش هم واقعی بود: هر نماد یک fetchِ کاملِ
تاریخچه است — اندازه‌گیریِ ۱۴۰۵-۰۷-۱۶ رویِ همین بانک: میانیِ ۲۴۸ms، p90 411ms،
بیشینه 600ms ⇒ ۹۲۲ نماد تک‌رشته‌ای ≈ ۲۵۲ ثانیه.

راهِ رفع (نه «بیش از این حساب نکن»):
  • یک بار برایِ همه حساب می‌شود و درِ جدولِ `funnel_tech_scan` می‌نشیند؛
    اسکرینر و قیف هر دو همان را می‌خوانند، پس داوریِ دوم ساخته نمی‌شود.
  • افزایشی است: امضایِ هر نماد (آخرینِ بستۀِ `price_history` + `basis`) با
    ردیفِ ذخیره‌شده می‌خواند ⇒ بی‌تغییریِ داده، آن نماد دوباره fetch نمی‌شود.
    درِ میانهٔ نشست، یک بازنشانیِ کامل فقط نمادهایِ معامله‌شدهٔ تازه را می‌زند.
  • همان `_fts_analyze_symbol` و `_fts_analysis_series` مسیرِ تعاملی صدا زده
    می‌شوند — یک کد، یک داوری. این فایل هیچ فرمولِ تازه‌ای ندارد.
  • اگر داوریِ نمادی ساخته نشود، `None` می‌ماند نه `False` (قانونِ مالک:
    null ≠ false)، و `analysis_basis` می‌گوید سری از CDN بوده یا بانکِ محلی.

اندازه‌گیریِ همین دور (۱۴۰۵-۰۷-۱۶، market.dbِ همین کارتری، نمادهایِ الفباییِ اول):
    تک‌رشته‌ای  ۱۲ نماد = 6.8s   ⇒ ~0.57s/نماد ⇒ ۹۲۲ نماد ≈ ۸.۸ دقیقه (سرد)
    ۴ رشته      ۱۲ نماد = 68s    ⇒ بدتر، نه بهتر (کارِ محاسباتی زیرِ GIL و
                                  sqliteِ per-call؛ پس پیش‌فرض تک‌رشته است)
    دومین فراخوانِ همان نماد = 0.02s ⇒ کشِ CHART_CACHE/FTS_ANALYSIS_CACHE کار
                                  می‌کند، پس «افزایشی» بودنِ این اسکن تزئینی نیست.
    universe() روی ۴۳۳٬۹۲۲ ردیف = 0.4s؛ خودِ کوئریِ امضا گلوگاه نیست.

اجرا (رویِ PC، با market.db موجود):
    python -m funnel_tech_scan            # بازنشانیِ افزایشیِ کلِ جوامع
    python -m funnel_tech_scan --force    # از نو
    python -m funnel_tech_scan --limit 40 --workers 4
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import threading
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

REPO = os.path.dirname(os.path.abspath(__file__))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import funnel_registry as REG  # noqa: E402

TABLE = "funnel_tech_scan"

# DDL این جدول تنها درِ همین فایل است (همان قراردادی که tsetmc_p0_schema دارد).
DDL = f"""CREATE TABLE IF NOT EXISTS {TABLE} (
    symbol TEXT PRIMARY KEY,
    basis TEXT,
    sessions INTEGER,
    sig TEXT,
    tech_trend_w TEXT,
    tech_trend_d TEXT,
    tech_trend_m TEXT,
    tech_alignment TEXT,
    tech_status TEXT,
    tech_matrix_decision TEXT,
    tech_matrix_setup TEXT,
    tech_matrix_desc TEXT,
    tech_jet INTEGER,
    tech_choch_bull INTEGER,
    tech_choch_bear INTEGER,
    tech_double_bottom INTEGER,
    tech_range_break INTEGER,
    tech_fib_zone TEXT,
    tech_exit_verdict TEXT,
    tech_exit_signals TEXT,
    tech_hourglass_active INTEGER,
    tech_hourglass_action TEXT,
    as_of INTEGER,
    engine_version TEXT,
    ruleset_version TEXT
)"""

# ستون‌هایی که از دیکشنریِ `fts` ساخته می‌شوند — ترتیبش با DDL یکی است تا
# `_row_from_fields` بی‌سوءتفاهم باشد.
_COLUMNS = ("basis", "sessions", "sig", "tech_trend_w", "tech_trend_d", "tech_trend_m",
            "tech_alignment", "tech_status", "tech_matrix_decision", "tech_matrix_setup",
            "tech_matrix_desc", "tech_jet", "tech_choch_bull", "tech_choch_bear",
            "tech_double_bottom", "tech_range_break", "tech_fib_zone",
            "tech_exit_verdict", "tech_exit_signals", "tech_hourglass_active",
            "tech_hourglass_action")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(DDL)


def tech_fields_from_fts(fts: dict | None, *, basis: str = "", sessions: int = 0,
                         sig: str = "") -> dict:
    """استخراجِ ستون‌ها از پاسخِ `_fts_analyze_symbol` — تنها نسخۀ این استخراج.

    `api/screener.py` هم همین تابع را صدا می‌زند؛ اگر روزی کسی این بلاک را
    دوباره بنویسد، دو داورِ تکنیکال خواهیم داشت (چیزی که ممیزیِ قیف دقیقاً
    همین را به‌عنوانِ عیبِ اول ردیف کرده بود).
    """
    f = (fts or {}).get("fts") or {}
    tr = f.get("trend") or {}
    ex = f.get("exit_engine") or {}
    fib = f.get("fib") or {}
    mat = tr.get("matrix") or {}
    hg = f.get("hourglass") or {}
    # بی‌تحلیل ⇒ هیچ‌کدام از بج‌ها «نیست» نیستند؛ «نظر داده نشده».
    _none = not f

    def _tri(v):
        return None if (_none or v is None) else bool(v)

    def _int(v):
        return None if v is None else int(bool(v))

    if (fib.get("zone_33_40") or {}).get("in_zone"):
        fib_zone = "33-40"
    elif (fib.get("zone_618_70") or {}).get("in_zone"):
        fib_zone = "61.8-70"
    else:
        fib_zone = None

    return {
        "basis": basis or None,
        "sessions": int(sessions or 0),
        "sig": sig or None,
        "tech_trend_w": (tr.get("W") or {}).get("trend"),
        "tech_trend_d": (tr.get("D") or {}).get("trend"),
        "tech_trend_m": (tr.get("M") or {}).get("trend"),
        "tech_alignment": tr.get("alignment"),
        "tech_status": (f.get("status") or {}).get("code"),
        "tech_matrix_decision": mat.get("decision"),
        "tech_matrix_setup": mat.get("setup"),
        "tech_matrix_desc": mat.get("desc"),
        "tech_jet": _int(_tri((f.get("jet") or {}).get("active"))),
        "tech_choch_bull": _int(_tri((f.get("choch") or {}).get("bullish"))),
        "tech_choch_bear": _int(_tri((f.get("choch") or {}).get("bearish"))),
        "tech_double_bottom": _int(_tri((f.get("double_bottom") or {}).get("active"))),
        "tech_range_break": _int(_tri((f.get("range_box") or {}).get("active"))),
        "tech_fib_zone": fib_zone,
        "tech_exit_verdict": ex.get("verdict"),
        "tech_exit_signals": json.dumps(ex.get("signals") or [], ensure_ascii=False),
        "tech_hourglass_active": _int(_tri(hg.get("active"))),
        "tech_hourglass_action": hg.get("action"),
    }


def norm_symbol(raw: str) -> str:
    """ك/ي عربی → فارسی — همان ترجمۀ `api/screener.py`، یک‌جا."""
    return (raw or "").translate(str.maketrans({"ك": "ک", "ي": "ی", "ى": "ی"}))


def universe(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """نمادهایی که اسکرینر می‌شناسد + امضایِ داده‌شان.

    امضا = آخرین `date` و آخرین `close` درِ `price_history`. بی‌fetchِ CDN و با
    یک کوئری درمی‌آید، پس «آیا این نماد از بازنشانیِ آخر تازگی داشته؟» تقریباً
    رایگان پرسیده می‌شود. نمادی که درِ `price_history` نیست امضایش خالی است و
    همیشه دوباره سنجیده می‌شود (داده‌اش زنده است، نه از بانک).
    """
    rows = conn.execute(
        """SELECT s, MAX(d), COALESCE(MAX(c), 0) FROM (
               SELECT replace(replace(trim(symbol),'ي','ی'),'ك','ک') AS s,
                      date AS d, close AS c
                 FROM price_history)
           GROUP BY s""").fetchall()
    return [(str(s), f"{d}|{c}") for s, d, c in rows if s]


def stored(conn: sqlite3.Connection) -> dict[str, dict]:
    """همۀ ردیف‌هایِ ذخیره‌شده — همان چیزی که اسکرینر به‌جایِ fetch می‌خواند."""
    ensure_schema(conn)
    cur = conn.execute(f"SELECT symbol, {', '.join(_COLUMNS)} FROM {TABLE}")
    cols = ["symbol", *_COLUMNS]
    return {str(r[0]): dict(zip(cols, r)) for r in cur.fetchall()}


def _one(symbol: str, sig: str) -> tuple[str, dict | None]:
    """یک نماد، یک مسیرِ داوری — همان `_fts_analyze_symbol`ِ مسیرِ تعاملی.

    پیش از این اینجا `_fts_analysis_series` هم جدا صدا زده می‌شد تا `sessions`
    دربیاید؛ آن یعنی یک fetchِ کاملِ تاریخچه رویِ همان fetchِ خودِ تحلیل.
    پاسخِ `_fts_analyze_symbol` خودش `bars` و `analysis_basis` را دارد.
    """
    from api.chart import _fts_analyze_symbol  # درونِ تابع: چرخۀ import
    try:
        fts = _fts_analyze_symbol(norm_symbol(symbol) or symbol)
    except Exception:
        return symbol, None
    if not isinstance(fts, dict) or fts.get("status") != "success":
        return symbol, None
    fields = tech_fields_from_fts(fts, basis=str(fts.get("analysis_basis") or ""),
                                  sessions=int(fts.get("bars") or 0), sig=sig)
    return symbol, fields


def run(conn: sqlite3.Connection, *, force: bool = False, workers: int = 1,
        limit: int = 0) -> dict:
    """بازنشانیِ (افزایشی|کامل) داوریِ تکنیکال. خلاصهٔ عددی برمی‌گرداند."""
    t0 = time.time()
    ensure_schema(conn)
    have = stored(conn)
    uni = universe(conn)
    todo = [(s, sig) for s, sig in uni
            if force or have.get(s, {}).get("sig") != sig]
    # «بازاستفاده» یعنی امضایش با ردیفِ ذخیره‌شده می‌خواند و اصلاً لازم نبود
    # fetch شود — پیش از برشِ --limit شمرده می‌شود، وگرنه عددِ ساختگی می‌شود.
    reusable = len(uni) - len(todo)
    if limit > 0:
        todo = todo[:limit]
    done = reused = failed = 0
    now = int(time.time())
    eng = os.environ.get("BORS_ENGINE_VERSION") or "dev"
    ruleset = REG.RULESET_VERSION

    def write(sym: str, fields: dict | None) -> None:
        if fields is None:
            return
        vals = [fields.get(c) for c in _COLUMNS]
        conn.execute(
            f"INSERT OR REPLACE INTO {TABLE}(symbol, {', '.join(_COLUMNS)}, as_of,"
            f" engine_version, ruleset_version) VALUES (?, {', '.join('?' * len(_COLUMNS))}, ?, ?, ?)",
            [sym, *vals, now, eng, ruleset])

    if todo:
        with ThreadPoolExecutor(max_workers=max(1, min(workers, 16))) as pool:
            for sym, fields in pool.map(lambda a: _one(*a), todo):
                if fields is None:
                    failed += 1
                else:
                    write(sym, fields)
                    done += 1
                if (done + failed) % 100 == 0:
                    conn.commit()
        conn.commit()
    return {"universe": len(uni), "computed": done, "failed": failed,
            "reused": reusable, "queued": len(todo), "forced": force,
            "as_of": now, "ms": int((time.time() - t0) * 1000),
            "workers": workers, "ruleset_version": ruleset}


# ── خواندن/ساختنِ داوری برایِ یک فهرستِ نماد (مسیرِ قیف) ───────────────────
def read(conn: sqlite3.Connection, symbols: Iterable[str]) -> dict[str, dict]:
    """داوریِ ذخیره‌شدۀ همین نمادها — بی‌fetch و بی‌SELECTِ هر-نماد.

    چیزی که نبودش «سقف» می‌سازد: قیف باید برایِ *هر* رسیدگی که به این گام
    رسیده رأی داشته باشد، پس ستون‌ها از همین جدولِ یک‌بار-ساخته‌شده خوانده
    می‌شوند، نه از ۵۰ ردیفِ اولِ اسکرینر.
    """
    want = list(dict.fromkeys(norm_symbol(str(s)) for s in symbols if s))
    if not want:
        return {}
    ensure_schema(conn)
    cols = ", ".join(_COLUMNS)
    out: dict[str, dict] = {}
    for i in range(0, len(want), 500):
        part = want[i:i + 500]
        marks = ", ".join("?" * len(part))
        for r in conn.execute(f"SELECT symbol, {cols} FROM {TABLE} WHERE symbol IN ({marks})", part):
            out[str(r[0])] = dict(zip(("symbol", *_COLUMNS), r))
    return out


def sig_map(conn: sqlite3.Connection) -> dict[str, str]:
    """امضایِ دادهٔ هر نماد؛ نمادی که درِ `price_history` ردیفی ندارد اینجا هم
    نیست — یعنی تکنیکالش سنجیدنی نیست (UNAVAILABLE)، نه «هنوز نوبتش نشده»."""
    return dict(universe(conn))


def _todo_for(conn: sqlite3.Connection, symbols: Iterable[str],
              sigs: dict[str, str]) -> tuple[list[tuple[str, str]], int, int]:
    """(چه‌چیزی باید سنجیده شود، چند تا آماده است، چند تا بی‌سابقه‌اند)."""
    have = stored(conn)
    todo: list[tuple[str, str]] = []
    ready = nohist = 0
    for sym in dict.fromkeys(norm_symbol(str(s)) for s in symbols if s):
        sig = sigs.get(sym, "")
        if not sig:
            nohist += 1
            continue
        if have.get(sym, {}).get("sig") == sig:
            ready += 1
            continue
        todo.append((sym, sig))
    return todo, ready, nohist


def refresh(conn: sqlite3.Connection, symbols: Iterable[str], *, workers: int = 1) -> dict:
    """همان بازنشانیِ `run`، ولی فقط رویِ یک فهرستِ نماد (افزایشیِ امضامحور)."""
    t0 = time.time()
    ensure_schema(conn)
    sigs = sig_map(conn)
    todo, ready, nohist = _todo_for(conn, symbols, sigs)
    done = failed = 0
    now = int(time.time())
    eng = os.environ.get("BORS_ENGINE_VERSION") or "dev"
    ruleset = REG.RULESET_VERSION
    if todo:
        with ThreadPoolExecutor(max_workers=max(1, min(workers, 16))) as pool:
            for sym, fields in pool.map(lambda a: _one(*a), todo):
                if fields is None:
                    failed += 1
                    continue
                vals = [fields.get(c) for c in _COLUMNS]
                conn.execute(
                    f"INSERT OR REPLACE INTO {TABLE}(symbol, {', '.join(_COLUMNS)}, as_of,"
                    f" engine_version, ruleset_version)"
                    f" VALUES (?, {', '.join('?' * len(_COLUMNS))}, ?, ?, ?)",
                    [sym, *vals, now, eng, ruleset])
                done += 1
        conn.commit()
    return {"requested": ready + nohist + len(todo), "computed": done, "failed": failed,
            "reused": ready, "no_history": nohist, "queued": len(todo), "as_of": now,
            "ms": int((time.time() - t0) * 1000)}


# ── پشت‌زمینه: داوری را هیچ درخواستِ HTTPی منتظر نمی‌ماند ─────────────────
# هزینه‌ای که درِ مسیرِ درخواست نمی‌نشیند: اندازه‌گیریِ ۱۴۰۵-۰۷-۱۶ رویِ همین
# بانک، چهار رسیدۀ تابلو = 99.5s ⇒ ~۲۵ ثانیه برایِ هر نمادِ سرد (fetchِ
# تاریخچه)، و ۰٫۰۲s برایِ نمادی که امضایش با ردیفِ ذخیره‌شده می‌خواند. کلِ
# ۹۲۲ نمادِ سرد پس ساعت‌ها کار است، نه دقیقه؛ دقیقاً برای همین اسکن درِ
# رشتهٔ پس‌زمینه می‌رود و پاسخِ همان لحظه TECH_SCAN_PENDING می‌گوید — نه
# حذفِ نماد، نه داوریِ نصفه.
_BG_LOCK = threading.Lock()
_BG = {"thread": None, "todo": set(), "done": 0, "failed": 0, "error": None,
       "attempted": set(), "last_ms": 0}


def _bg_worker() -> None:
    from bors_config import DB_PATH
    conn = sqlite3.connect(DB_PATH, timeout=60)
    try:
        while True:
            with _BG_LOCK:
                batch = sorted(_BG["todo"])[:40]
                _BG["todo"] -= set(batch)
                _BG["attempted"] |= set(batch)
            if not batch:
                with _BG_LOCK:
                    if not _BG["todo"]:
                        _BG["thread"] = None
                        return
                continue
            out = refresh(conn, batch)
            with _BG_LOCK:
                _BG["done"] += int(out.get("computed") or 0)
                _BG["failed"] += int(out.get("failed") or 0)
                _BG["last_ms"] = int(out.get("ms") or 0)
                # نمادی که سنجیده نشد (fetch شکست) از «در حال» بیرون می‌رود تا
                # دورِ بعد دوباره شانسش باشد؛ بی‌این یک بار شکست = ابدی.
                _BG["attempted"] -= set(batch)
    except Exception as e:  # هر خطایی باید دیده شود، نه اینکه رشته خاموش بمیرد
        with _BG_LOCK:
            _BG["error"] = f"{type(e).__name__}: {e}"
            _BG["thread"] = None
    finally:
        conn.close()


def start_refresh(symbols: Iterable[str]) -> dict:
    """این نمادها را درِ پس‌زمینه بساز؛ فوراً برمی‌گردد (هیچ داوریِ منتظره‌ای نیست)."""
    want = [norm_symbol(str(s)) for s in symbols if s]
    with _BG_LOCK:
        if _BG["thread"] is None or not _BG["thread"].is_alive():
            _BG["todo"] = set(want)
            _BG["thread"] = threading.Thread(target=_bg_worker, daemon=True,
                                             name="funnel-tech-scan")
            _BG["thread"].start()
        else:
            # نمادی که همین حالا در حالِ سنجش است را دوباره صف نکن (fetchِ تکراری)
            _BG["todo"] |= {s for s in want if s not in _BG["attempted"]}
        return {"running": True, "queued": len(_BG["todo"]), "done": _BG["done"],
                "failed": _BG["failed"], "in_flight": len(_BG["attempted"]),
                "error": _BG["error"]}


def bg_status() -> dict:
    with _BG_LOCK:
        return {"running": bool(_BG["thread"] and _BG["thread"].is_alive()),
                "queued": len(_BG["todo"]), "done": _BG["done"], "failed": _BG["failed"],
                "in_flight": len(_BG["attempted"]), "last_ms": _BG["last_ms"],
                "error": _BG["error"]}


def freshness(conn: sqlite3.Connection) -> dict:
    ensure_schema(conn)
    r = conn.execute(f"SELECT count(*), min(as_of), max(as_of), count(DISTINCT ruleset_version)"
                     f" FROM {TABLE}").fetchone()
    n, lo, hi, vers = r
    return {"rows": int(n or 0), "oldest_as_of": lo, "newest_as_of": hi,
            "ruleset_versions": int(vers or 0),
            "age_s": int(time.time() - hi) if hi else None}


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass
    from bors_config import DB_PATH
    ap = argparse.ArgumentParser(description="بازنشانیِ داوریِ تکنیکالِ کلِ جوامع")
    ap.add_argument("--force", action="store_true", help="بی‌نگاه‌کردنِ امضا، از نو")
    ap.add_argument("--workers", type=int, default=1,
                    help="۱ پیش‌فرض: اندازه‌گیریِ ۱۴۰۵-۰۷-۱۶ با ۴ رشته ۱۰× کندتر شد")
    ap.add_argument("--limit", type=int, default=0, help="فقط N نماد (سنجشِ هزینه)")
    ap.add_argument("--db", default=DB_PATH)
    args = ap.parse_args()
    conn = sqlite3.connect(args.db, timeout=60)
    try:
        out = run(conn, force=args.force, workers=args.workers, limit=args.limit)
        print(json.dumps(out, ensure_ascii=False, indent=1))
        print(json.dumps(freshness(conn), ensure_ascii=False))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
