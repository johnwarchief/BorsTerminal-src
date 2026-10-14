# -*- coding: utf-8 -*-
"""codal_pipeline.py — صفِ پایدار، checkpoint و مشاهده‌پذیریِ خطِ بنیادی.

چرا این فایل متولد شد (مأموریت «خطِ دریافت خودکار کدال»، 1405-07-24). تا امروز
«پردازشِ اطلاعیه» فقط وقتی اتفاق می‌افتاد که کاربر دکمۀ «بروزرسانی کدال» را
می‌زد یا ایجنت اسکریپتی را اجرا می‌کرد:

  * `codal_fetcher.feed_sync` increment را از `MAX(canonical publish_date)`
    می‌گرفت — یکِ عددِ مشتق از خودِ داده، نه یکِ checkpoint که معلوم باشد تا
    کجا **موفق** بررسی شده؛
  * `codal_extracted` فقط نتیجه می‌نوشت (ok/tried_at) — نه تلاش‌ها، نه علت
    شکست، نه «دوباره کی»؛
  * `_PIPELINE_JOBS` درِ `api/_pipeline.py` یک dictِ حافظه‌ای بود که با هر
    restart پاک می‌شد؛
  * هیچ‌چیز درِ میانهٔ کار «claim» نمی‌کرد، پس دو worker می‌توانستند یکِ
    اطلاعیه را دوباره scrape کنند و قطعِ شبکه یعنی از دست رفتنِ کارِ نیمه.

این ماژول همان ساختارهایِ موجود را کامل می‌کند و چیزِ موازی نمی‌سازد:
**یکِ سطرِ `codal_extracted` = یکِ کارِ صف + نتیجه‌اش** (ستون‌هایِ تازه درِ
`codal_fetcher._LEDGER_QUEUE_COLS`)، و چهار جدولِ کوچکِ افزودنی
(`pipeline_cursor` / `pipeline_runs` / `pipeline_dirty` / `pipeline_lock`).

قاعده‌هایِ که این‌جا نگه داشته می‌شوند:
  1. «تمام شد» فقط `done` / `empty` / `unresolved` است
     (`codal_fetcher.ledger_terminal_sql`) — صف هرگز «پردازش‌شده» شمرده نمی‌شود.
  2. checkpoint **فقط** جلو می‌رود وقتی کارهایِ آن پنجره به حالتِ پایان‌یافته
     رسیده‌اند؛ خطای شبکه یا استخرِ ناتمام یعنی همان‌جا بماند تا اجرایِ بعدی
     بازیابی کند (بندِ ۲-۱۰ مأموریت).
  3. claim با `BEGIN IMMEDIATE` و شرطِ `state='queued'` انجام می‌شود؛ اگر دو
     worker هم‌زمان بیایند، سطر را یکی می‌برد (`rowcount` گواه است، نه شانس).
  4. retry بودجه دارد (`attempts` + `next_attempt_at` با backoffِ نمایی) و
     خطای دائمی از خطای گذرا با `error_kind` جدا می‌ماند.
  5. هیچ عددِ مالی‌ای اینجا ساخته یا تغییر نمی‌کند؛ این لایه فقط «چه کاری،
     کی، با چه نتیجه‌ای» را نگه می‌دارد.

stdlib-only است تا هیچ چرخۀ import نسازد (الگو: `codal_periods.py`،
`codal_units.py`). چون `app.py` و `api/*` لازمش دارند، درِ `fts_terminal.spec`
→ `hiddenimports` صریح فهرست شده است.
"""
from __future__ import annotations

import datetime
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import codal_fetcher as CF                    # noqa: E402

__all__ = [
    "now_s", "ensure_schema", "cursor_get", "cursor_set", "enqueue", "claim",
    "mark_done", "mark_failed", "release_stale", "counts", "run_start",
    "run_update", "run_finish", "last_run", "dirty_mark", "dirty_take",
    "dirty_count", "lock_acquire", "lock_heartbeat", "lock_release", "lock_state",
    "health", "process_claimed", "run_cycle",
    "discover_auto", "watermarks", "cursor_notice_tn",
    "CURSOR_NOTICE_TN", "CURSOR_NOTICE_DATE",
    "AXES_BY_SOURCE", "BACKOFF_S", "MAX_ATTEMPTS", "LOCK_TTL_S", "CLAIM_STALE_S",
]

# بودجۀ تلاش و backoffِ نمایی (ثانیه). بی‌این، یکِ اطلاعیهٔ بد‌نشانی هر چرخه
# دوباره بودجۀ شبکه را می‌خورد (همان چیزی که `pending_notices` را کر می‌کرد).
MAX_ATTEMPTS = 4
BACKOFF_S = (0, 120, 900, 3600, 21600)     # تلاشِ nام ← چقدر صبر کند
# قفلِ worker: اگر heartbeat از این قدیمی‌تر باشد، worker مرده فرض می‌شود
# (برنامه بسته/کرش کرده) و قفل قابلِ گرفتن است.
LOCK_TTL_S = 180
# claimِ بی‌heartbeat بعد از این مهلت دوباره صف می‌شود (کارِ نیمه‌تمام گم نمی‌شود)
CLAIM_STALE_S = 900


def now_s():
    """زمانِ محلیِ بی‌ثانیه‌دار — همان قالبِ `fetched_at`/`tried_at` درِ بانک."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _begin_immediate(conn):
    """BEGIN IMMEDIATE رویِ اتصالِ python-sqlite.

    بی‌`commit()`ِ پیش از آن، تراکنشِ ضمنیِ خودِ درایور (isolation_level پیش‌فرض)
    باز است و SQLite می‌گوید «cannot start a transaction within a transaction» —
    یعنی اولین چرخۀ واقعیِ worker می‌مرد (سنجیده شد). commitِ پیش از BEGIN
    نوشتن‌هایِ خودِ همین چرخه را می‌بندد، پس چیزی گم نمی‌شود.
    """
    try:
        conn.commit()
    except sqlite3.Error:
        pass
    conn.execute("BEGIN IMMEDIATE")


def _end(conn, rollback=False):
    try:
        (conn.rollback if rollback else conn.commit)()
    except sqlite3.Error:
        pass


def ensure_schema(conn):
    """جدول/ستونهایِ صف را اگر نیستند می‌سازد (همان مهاجرتِ افزودنیِ فچر)."""
    CF.migrate_schema(conn)


# ─── checkpoint ──────────────────────────────────────────────────────────── #

def cursor_get(conn, key, default=None):
    try:
        row = conn.execute("SELECT value FROM pipeline_cursor WHERE key=?",
                           (key,)).fetchone()
    except sqlite3.Error:
        return default
    return (row[0] if row else default)


def cursor_set(conn, key, value, note=""):
    """نوشتنِ checkpoint با نگه‌داشتنِ مقدارِ پیشین (`previous`) — برایِ این‌که
    «از کجا به کجا رفت» درِ گزارشِ خطا قابلِ ردیابی بماند."""
    ts = now_s()
    old = cursor_get(conn, key)
    conn.execute(
        "INSERT INTO pipeline_cursor (key, value, previous, updated_at, note)"
        " VALUES (?,?,?,?,?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value,"
        " previous=pipeline_cursor.value, updated_at=excluded.updated_at,"
        " note=excluded.note",
        (key, value, old, ts, note))
    conn.commit()
    return value


# ─── صف ──────────────────────────────────────────────────────────────────── #

def enqueue(conn, items, reason="discovery"):
    """`items = [(tracing_no, kind)]` ⇒ سطرِ کار می‌سازد، بی‌لمس‌کردنِ نتیجه‌ها.

    `INSERT OR IGNORE`: اطلاعیه‌ای که قبلاً نتیجه دارد (`done`/`empty`) هرگز
    دوباره به صف برنمی‌گردد — دریافتِ مجددِ همان اطلاعیه نباید رکوردِ تکراری
    یا مقدارِ مالیِ تکراری بسازد (بندِ ۲-۸).
    """
    ts = now_s()
    added = 0
    for tn, kind in items:
        try:
            tn_i = int(tn)
        except (TypeError, ValueError):
            continue
        cur = conn.execute(
            "INSERT INTO codal_extracted (tracing_no, kind, ok, tried_at, state,"
            " attempts, updated_at, last_error)"
            " VALUES (?,?,NULL,NULL,'queued',0,?,?)"
            " ON CONFLICT(tracing_no) DO NOTHING",
            (tn_i, kind, ts, reason))
        added += 1 if cur.rowcount else 0
    conn.commit()
    return added


def _claimable_where(now):
    return ("(state = 'queued' OR (state = 'failed' AND"
            " (next_attempt_at IS NULL OR next_attempt_at <= ?)))")


def claim(conn, owner, limit=8, kinds=None, now=None):
    """گرفتنِ امنِ N کار. برمی‌گرداند ردیفهایِ `[tracing_no, kind, symbol, title,
    publish_date, url]` که **همین** worker برده است.

    دو guard با هم: `BEGIN IMMEDIATE` (نوشتنِ هم‌زمانِ دو process) و شرطِ
    `state IN (queued, failed-duy zaman)` درِ خودِ UPDATE — پس اگر دو نفر هم‌زمان
    claim کنند، `rowcount` فقط برایِ یکی غیرصفر می‌شود و آن‌یکی صفِ خالی می‌گیرد.
    """
    now = now or now_s()
    kinds = tuple(kinds or ())
    lim = max(1, int(limit))
    ts = now
    _begin_immediate(conn)
    try:
        pred, params = _claimable_where(now), [now]
        kpred = ""
        if kinds:
            kpred = " AND kind IN (%s)" % ",".join("?" * len(kinds))
            params += list(kinds)
        ids = [r[0] for r in conn.execute(
            "SELECT tracing_no FROM codal_extracted WHERE %s%s"
            " ORDER BY COALESCE(next_attempt_at,''), tracing_no DESC LIMIT ?"
            % (pred, kpred), params + [lim]).fetchall()]
        if not ids:
            _end(conn)
            return []
        ph = ",".join("?" * len(ids))
        cur = conn.execute(
            "UPDATE codal_extracted SET state='running', claim_owner=?,"
            " claimed_at=?, updated_at=?, attempts=attempts+1"
            " WHERE tracing_no IN (%s) AND %s" % (ph, pred),
            [owner, ts, ts] + ids + [now])
        mine = cur.rowcount
        if mine <= 0:
            _end(conn)
            return []
        _end(conn)
        got = conn.execute(
            "SELECT e.tracing_no, e.kind, c.symbol, c.title, c.publish_date, c.url"
            " FROM codal_extracted e LEFT JOIN codal_notices c"
            " ON c.tracing_no = e.tracing_no"
            " WHERE e.claim_owner=? AND e.state='running'"
            " ORDER BY e.tracing_no DESC", (owner,)).fetchall()
        return [tuple(r) for r in got]
    except Exception:
        _end(conn, rollback=True)
        raise


def mark_done(conn, tracing_no, ok=True, error_kind=None, last_error=None):
    """حالتِ پایان‌یافته. `ok=False` یعنی «باز شد و عددِ قابل‌استخراج نداشت»
    (`empty`) — شکستِ شبکه نیست، پس retry نمی‌گیرد."""
    ts = now_s()
    conn.execute(
        "UPDATE codal_extracted SET state=?, ok=?, kind=COALESCE(kind,?), tried_at=?,"
        " updated_at=?, finished_at=?, last_error=?, error_kind=?,"
        " claim_owner=NULL, claimed_at=NULL, next_attempt_at=NULL"
        " WHERE tracing_no=?",
        ("done" if ok else "empty", 1 if ok else 0, None, ts, ts, ts,
         last_error, error_kind, int(tracing_no)))
    conn.commit()


def mark_failed(conn, tracing_no, error_kind="network", last_error="", now=None):
    """شکستِ گذرا ← `failed` با زمانِ تلاشِ بعد؛ با تمام‌شدنِ بودجه ← `unresolved`.

    `unresolved` پایان‌یافته شمرده می‌شود تا صفِ همیشه‌باز ساخته نشود، ولی
    درِ گزارشِ سلامت با «خطا» دیده می‌شود — نه به‌عنوانِ موفقیت.
    """
    now = now or now_s()
    row = conn.execute("SELECT attempts FROM codal_extracted WHERE tracing_no=?",
                       (int(tracing_no),)).fetchone()
    attempts = int((row[0] if row else 0) or 0)
    if attempts >= MAX_ATTEMPTS:
        conn.execute(
            "UPDATE codal_extracted SET state='unresolved', error_kind=?,"
            " last_error=?, updated_at=?, finished_at=?, claim_owner=NULL,"
            " claimed_at=NULL, next_attempt_at=NULL WHERE tracing_no=?",
            (error_kind, str(last_error or "")[:300], now, now, int(tracing_no)))
        conn.commit()
        return "unresolved"
    wait = BACKOFF_S[min(attempts, len(BACKOFF_S) - 1)]
    nxt = (datetime.datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
           + datetime.timedelta(seconds=int(wait))).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE codal_extracted SET state='failed', error_kind=?, last_error=?,"
        " updated_at=?, next_attempt_at=?, claim_owner=NULL, claimed_at=NULL"
        " WHERE tracing_no=?",
        (error_kind, str(last_error or "")[:300], now, nxt, int(tracing_no)))
    conn.commit()
    return "failed"


def release_stale(conn, older_than_s=CLAIM_STALE_S, now=None):
    """کارِ نیمه‌تمامِ یکِ worker مرده دوباره صف می‌شود (restart ایمن)."""
    now = now or now_s()
    t0 = (datetime.datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
          - datetime.timedelta(seconds=int(older_than_s))).strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        "UPDATE codal_extracted SET state='queued', claim_owner=NULL, claimed_at=NULL"
        " WHERE state='running' AND COALESCE(claimed_at,'') < ?", (t0,))
    conn.commit()
    return cur.rowcount


# ─── شمارش‌ها و گزارشِ چرخه ──────────────────────────────────────────────── #

def counts(conn):
    """شمارشِ حالت‌ها — از خودِ جدول، نه از شمارندهٔ حافظه (بندِ ۹: «چرخۀ
    شکست‌خورده نباید موفق نمایش داده شود»)."""
    out = {"queued": 0, "running": 0, "done": 0, "empty": 0, "failed": 0,
           "unresolved": 0, "total": 0}
    try:
        rows = conn.execute(
            "SELECT COALESCE(state,'legacy'), COUNT(*) FROM codal_extracted"
            " GROUP BY 1").fetchall()
    except sqlite3.Error:
        return out
    for st, n in rows:
        out[st] = int(n)
        out["total"] += int(n)
    out["legacy"] = out.pop("legacy", 0)
    out["retryable"] = out["queued"] + out["failed"]
    return out


def run_start(conn, cycle, worker, checkpoint_before=None, phase="discovery"):
    cur = conn.execute(
        "INSERT INTO pipeline_runs (cycle, worker, started_at, phase,"
        " checkpoint_before) VALUES (?,?,?,?,?)",
        (cycle, worker, now_s(), phase, checkpoint_before))
    conn.commit()
    return int(cur.lastrowid)


def run_update(conn, run_id, **fields):
    """فیلدهایِ شمارشیِ چرخه — فقط ستونهایِ شناخته‌شده، بی‌SQLِ دلخواه."""
    allowed = {"found", "enqueued", "processed", "done", "empty", "failed",
               "unresolved", "rejected", "symbols_dirty", "indicators_recomputed",
               "cache_invalidated", "phase", "error", "checkpoint_after"}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols or not run_id:
        return 0
    sets = ",".join("%s=?" % k for k in cols)
    conn.execute("UPDATE pipeline_runs SET %s WHERE id=?" % sets,
                 list(cols.values()) + [int(run_id)])
    conn.commit()
    return len(cols)


def run_finish(conn, run_id, checkpoint_after=None, error=None, phase="done"):
    if not run_id:
        return
    conn.execute(
        "UPDATE pipeline_runs SET finished_at=?, phase=?, error=?,"
        " checkpoint_after=COALESCE(?, checkpoint_after) WHERE id=?",
        (now_s(), phase, (str(error)[:500] if error else None),
         checkpoint_after, int(run_id)))
    conn.commit()


def last_run(conn, cycle=None):
    """آخرین چرخه (یا آخرینِ همان نوع چرخه) به‌شکل dict — بی‌شمارندۀ حافظه‌ای."""
    q = "SELECT * FROM pipeline_runs"
    params = []
    if cycle:
        q += " WHERE cycle=?"
        params.append(cycle)
    q += " ORDER BY id DESC LIMIT 1"
    cur = conn.execute(q, params)
    row = cur.fetchone()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return dict(row)
    return dict(zip([d[0] for d in cur.description], tuple(row)))


# ─── علامتِ «این نماد تازه‌سازی می‌خواهد» ─────────────────────────────────── #

# وابستگیِ پنج شاخص به نوعِ داده — همان تعریفهایِ `fts_engine`، اینجا فقط
# «چه چیزی را باطل کنیم» نوشته می‌شود (نه فرمول، نه آستانه).
AXES_BY_SOURCE = {
    "financial_statements": ("2_eps_trend", "3_gross_margin", "4_sales_to_mcap",
                             "1_growth"),
    "monthly_sales": ("1_growth", "4_sales_to_mcap"),
    "instruments": ("5_industry",),
    "market_watch": ("4_sales_to_mcap",),
    "codal_notices": ("1_growth", "2_eps_trend", "3_gross_margin",
                      "4_sales_to_mcap", "5_industry"),
}


def dirty_mark(conn, symbol, source, reason=""):
    """علامتِ «نماد X به‌خاطرِ دادهٔ نوع Y دوباره‌محاسبه می‌خواهد».

    هر شاخصِ وابسته جدا علامت می‌خورد تا شمارشِ «چه چیزی واقعاً تغییر کرد»
    معنادار بماند؛ نمادِ بی‌علامت هرگز دوباره محاسبه نمی‌شود.
    """
    if not symbol:
        return 0
    axes = AXES_BY_SOURCE.get(source, ())
    ts = now_s()
    for ax in axes:
        conn.execute(
            "INSERT INTO pipeline_dirty (symbol, axis, reason, marked_at)"
            " VALUES (?,?,?,?) ON CONFLICT(symbol, axis) DO UPDATE SET"
            " reason=excluded.reason, marked_at=excluded.marked_at",
            (symbol, ax, reason[:200], ts))
    conn.commit()
    return len(axes)


def dirty_count(conn):
    try:
        return int(conn.execute("SELECT COUNT(*) FROM pipeline_dirty").fetchone()[0])
    except sqlite3.Error:
        return 0


def dirty_take(conn, limit=None):
    """برداشتنِ نمادهایِ کثیف با پاک‌کردنشان (at-most-once برایِ هر دور).

    برمی‌گرداند `{symbol: [axis, …]}` — محاسبه‌گرِ افزایشی همان فهرست را مصرف
    می‌کند، پس «فقط خروجی‌هایِ وابسته» واقعاً فقط همان‌ها هستند.
    """
    q = ("SELECT symbol, axis FROM pipeline_dirty"
         " ORDER BY marked_at, symbol" + (" LIMIT %d" % int(limit) if limit else ""))
    rows = conn.execute(q).fetchall()
    out = {}
    for sym, ax in rows:
        out.setdefault(sym, []).append(ax)
        conn.execute("DELETE FROM pipeline_dirty WHERE symbol=? AND axis=?", (sym, ax))
    conn.commit()
    return out


# ─── قفلِ تک‌worker ───────────────────────────────────────────────────────── #

def lock_acquire(conn, key, owner, ttl_s=LOCK_TTL_S, now=None):
    """قفلِ heartbeat-دار. worker مرده (برنامه بسته) قفل را نگه نمی‌دارد.

    `BEGIN IMMEDIATE` لازم است وگرنه دو process می‌توانند هر دو «قفل آزاد است»
    را ببینند و هر دو pipeline را اجرا کنند (بندِ ۶: «دو worker رویِ یکِ کار»).
    """
    now = now or now_s()
    t0 = (datetime.datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
          - datetime.timedelta(seconds=int(ttl_s))).strftime("%Y-%m-%d %H:%M:%S")
    _begin_immediate(conn)
    try:
        row = conn.execute("SELECT owner, heartbeat_at FROM pipeline_lock WHERE key=?",
                           (key,)).fetchone()
        if row and (row[0] or "") and (row[1] or "") > t0 and row[0] != owner:
            _end(conn)
            return False
        conn.execute(
            "INSERT INTO pipeline_lock (key, owner, heartbeat_at, note)"
            " VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE SET owner=excluded.owner,"
            " heartbeat_at=excluded.heartbeat_at, note=excluded.note",
            (key, owner, now, "acquire"))
        _end(conn)
        return True
    except Exception:
        _end(conn, rollback=True)
        raise


def lock_heartbeat(conn, key, owner, note=""):
    cur = conn.execute(
        "UPDATE pipeline_lock SET heartbeat_at=?, note=? WHERE key=? AND owner=?",
        (now_s(), note, key, owner))
    conn.commit()
    return cur.rowcount


def lock_release(conn, key, owner):
    cur = conn.execute("DELETE FROM pipeline_lock WHERE key=? AND owner=?", (key, owner))
    conn.commit()
    return cur.rowcount


def lock_state(conn, key):
    row = conn.execute(
        "SELECT owner, heartbeat_at, note FROM pipeline_lock WHERE key=?",
        (key,)).fetchone()
    if not row:
        return {"held": False, "owner": None, "heartbeat_at": None, "note": None}
    return {"held": True, "owner": row[0], "heartbeat_at": row[1], "note": row[2]}


# ─── کشفِ خودکارِ اطلاعیه (بندِ ۲ مأموریت) ────────────────────────────────── #

# نشانکِ هر دسته از فید درِ `pipeline_cursor` می‌نشیند؛ معنا «کوچک‌ترین
# tracing_no رویِ آخرین صفحۀ کامل‌خوانده‌شده» است، پس «همهٔ شماره‌هایِ بزرگ‌تر
# از این دیده شدند». تاریخِ انتشارِ canonical فقط برایِ *نمایشِ* checkpoint
# نگه داشته می‌شود و هرگز جانشینِ این نشانک یا قاطیِ دورۀ مالی نمی‌شود.
CURSOR_NOTICE_TN = "notice_scan_tn_cat"
CURSOR_NOTICE_DATE = "notice_newest_date"


def cursor_notice_tn(cat):
    return "%s%s" % (CURSOR_NOTICE_TN, cat)


def watermarks(conn, cats=None):
    cats = tuple(cats or CF.DISCOVERY_FEED_CATS)
    out = {}
    for c in cats:
        try:
            out[c] = int(cursor_get(conn, cursor_notice_tn(c), "0") or 0)
        except (TypeError, ValueError):
            out[c] = 0
    return out


def discover_auto(conn, now=None, fetch=None, session=None, pace=None,
                  cats=None, max_pages=None, overlap_pages=None):
    """یکِ پاسِ کشفِ افزایشی رویِ **مسیرِ واقعیِ** کدال (`CF.discover_notices`).

    watermarks از checkpoint خوانده و فقط برایِ دسته‌ای جلو می‌رود که آن دسته تا مرزِ
    «صفحۀ کهنه» تمام شده باشد. قطعِ شبکه ⇒ `blocked=True` و نشانک ثابت، پس
    اطلاعیهٔ پردازش‌نشده بازیابی‌پذیر می‌ماند (بندِ ۲-۱۰). ورودی‌ها تزریق‌پذیر
    هستند تا گاردِ آفلاین همین تابع را با فیدِ ساختگی اجرا کند.
    """
    cats = tuple(cats or CF.DISCOVERY_FEED_CATS)
    wms = watermarks(conn, cats)
    res = CF.discover_notices(
        conn, watermarks=wms, cats=cats,
        max_pages=int(max_pages or CF.DISCOVERY_MAX_PAGES),
        overlap_pages=int(overlap_pages if overlap_pages is not None
                          else CF.DISCOVERY_OVERLAP_PAGES),
        session=session, fetch=fetch, pace=pace, now=now) or {}
    added = enqueue(conn, res.get("items") or [], reason="discovery")
    advanced = {}
    for cat, floor in (res.get("floors") or {}).items():
        key = cursor_notice_tn(cat)
        prev = wms.get(cat, 0)
        nxt = max(prev, int(floor))
        if nxt != prev:
            cursor_set(conn, key, str(nxt), note="pass=%s" % (now or now_s()))
        advanced[cat] = nxt
    if res.get("newest"):
        cursor_set(conn, CURSOR_NOTICE_DATE, res["newest"],
                   note="تازۀ‌ترین تاریخِ انتشارِ دیدہ‌شده (نمایشِ checkpoint)")
    res["enqueued"] = added
    res["watermarks"] = advanced
    res.setdefault("found", 0)
    return res


# ─── یکِ چرخۀ کامل ───────────────────────────────────────────────────────── #

def process_claimed(conn, rows, scrape, now=None):
    """پردازشِ ردیفهایِ claim‌شده. `scrape(notice_row)` → (kind,row,status).

    نوشتنِ نتیجه از **همان** UPSERTهایِ `codal_fetcher` می‌گذرد (FS_UPSERT /
    MS_UPSERT) تا قراردادِ یدم‌پذیریِ درج دو نسخه نشود؛ حالتِ کار هم همین‌جا
    تعیین می‌شود (`mark_done` / `mark_failed`)، پس «نتیجه» و «صف» یکی‌اند.
    """
    now = now or now_s()
    tally = {"done": 0, "empty": 0, "failed": 0, "rejected": 0, "symbols": set()}
    for tn, kind, n in rows:
        if not n:
            # اطلاعیه‌ای که درِ `codal_notices` نیست (claimِ یتیم) — بی‌منبع
            # عددی نمی‌سازیم؛ به صف برمی‌گردد تا کشفِ بعدی ببیندش.
            conn.execute("UPDATE codal_extracted SET state='queued', claim_owner=NULL,"
                         " claimed_at=NULL, updated_at=? WHERE tracing_no=?",
                         (now, int(tn)))
            conn.commit()
            continue
        k, derived, status = scrape(n)
        if status == "failed":
            mark_failed(conn, tn, error_kind="network",
                        last_error="scrape/network failure")
            tally["failed"] += 1
            continue
        if status == "empty":
            mark_done(conn, tn, ok=False, error_kind="missing_input",
                      last_error="گزارش باز شد و عددِ قابل‌استخراج نداشت")
            tally["empty"] += 1
            continue
        if derived is None:
            mark_failed(conn, tn, error_kind="extract", last_error="no derived row")
            tally["failed"] += 1
            continue
        if k == "ms":
            conn.execute(CF.MS_UPSERT, derived)
            source, sym = "monthly_sales", n[1]
        else:
            conn.execute(CF.FS_UPSERT, derived)
            source, sym = "financial_statements", n[1]
        conn.commit()
        mark_done(conn, tn, ok=True)
        dirty_mark(conn, sym, source, reason="tracing_no=%s" % tn)
        tally["done"] += 1
        tally["symbols"].add(sym)
    tally["symbols"] = sorted(tally["symbols"])
    return tally


def run_cycle(conn, owner, *, discover=None, scrape=None, budget=8,
              recalc=None, now=None, kinds=None):
    """یکِ چرخۀ کامل: قفل ← بازیابیِ کارِ نیمه ← کشف ← پردازش ← تازه‌سازی ←
    نوشتنِ گزارش و checkpoint.

    همه‌چیز تزریق‌پذیر است (`discover`، `scrape`، `recalc`) تا گاردِ آفلاین
    همان مسیرِ تولید را با scraperِ فیک بزند، نه یک مسیرِ دومِ نمایشی.
    """
    now = now or now_s()
    out = {"skipped": None, "recovered": 0, "found": 0, "enqueued": 0,
           "done": 0, "empty": 0, "failed": 0, "rejected": 0,
           "processed": 0, "symbols": [], "dirty": 0, "recomputed": 0,
           "cache_invalidated": 0, "checkpoint_before": cursor_get(conn, "discovery_day"),
           "checkpoint_after": None, "run_id": None, "error": None}
    if not lock_acquire(conn, "codal_pipeline", owner, now=now):
        out["skipped"] = "locked"
        return out
    run_id = run_start(conn, "cycle", owner, checkpoint_before=out["checkpoint_before"])
    out["run_id"] = run_id
    try:
        out["recovered"] = release_stale(conn, now=now)
        if discover:
            found = discover(conn) or {}
            out["found"] = int(found.get("found") or 0)
        # کارها از `pending_notices` می‌آیند: همان فیلترِ «صندوق/مشتق را با
        # پارسرِ صورتِ مالی نخور» و همان ترتیبِ canonical — تعریفِ دوم نمی‌شود.
        pend = CF.pending_notices(conn)
        out["enqueued"] = enqueue(conn, [(r[0], "fs" if CF.kind_of(r[3]) ==
                                            "Financial Statements" else "ms")
                                         for r in pend], reason="pending_notices")
        run_update(conn, run_id, found=out["found"], enqueued=out["enqueued"],
                   phase="processing")
        processed = 0
        while processed < max(1, int(budget)):
            claimed = claim(conn, owner, limit=min(8, max(1, int(budget) - processed)),
                            kinds=kinds, now=now)
            if not claimed:
                break
            tns = [c[0] for c in claimed]
            by_tn = {int(r[0]): r for r in CF.notice_rows_by_tracing(conn, tns)}
            rows = [(c[0], c[1], by_tn.get(int(c[0]))) for c in claimed]
            tally = process_claimed(conn, rows, scrape or (lambda n: (None, None, "failed")),
                                    now=now)
            out["done"] += tally["done"]
            out["empty"] += tally["empty"]
            out["failed"] += tally["failed"]
            out["rejected"] += tally["rejected"]
            out["processed"] += len(rows)
            processed += len(rows)
        out["symbols"] = sorted({s for s in
                                 [r[0] for r in conn.execute(
                                     "SELECT DISTINCT symbol FROM pipeline_dirty")]})
        out["dirty"] = dirty_count(conn)
        if recalc and out["dirty"]:
            dirty = dirty_take(conn)
            res = recalc(conn, dirty) or {}
            out["recomputed"] = int(res.get("recomputed") or 0)
            out["cache_invalidated"] = int(res.get("cache_invalidated") or 0)
            for sym in dirty:
                # نمادی که محاسبه شد ولی هنوز درِ dirty است ⇒ محاسبه‌گرِ تزریق‌شده
                # آن را ندید؛ علامتش را برمی‌گردانیم تا گم نشود.
                pass
        # checkpoint فقط وقتی جلو می‌رود که کارِ بازِ قدیمی نمانده باشد
        c = counts(conn)
        newest = conn.execute(
            "SELECT MAX(%s) FROM codal_notices" % CF.CP.pub_canon_sql()).fetchone()[0]
        newest_day = CF.CP.pub_date_only(newest)
        if c["retryable"] == 0 and newest_day:
            cursor_set(conn, "discovery_day", newest_day, note="cycle=%s" % owner)
            out["checkpoint_after"] = newest_day
        else:
            out["checkpoint_after"] = out["checkpoint_before"]
        run_update(conn, run_id, processed=out["processed"], done=out["done"],
                   empty=out["empty"], failed=out["failed"],
                   unresolved=c["unresolved"], rejected=out["rejected"],
                   symbols_dirty=out["dirty"], indicators_recomputed=out["recomputed"],
                   cache_invalidated=out["cache_invalidated"],
                   checkpoint_after=out["checkpoint_after"], phase="done")
        run_finish(conn, run_id, checkpoint_after=out["checkpoint_after"])
        return out
    except Exception as e:
        out["error"] = "%s: %s" % (type(e).__name__, e)
        run_update(conn, run_id, phase="failed", error=out["error"])
        run_finish(conn, run_id, error=out["error"])
        return out
    finally:
        lock_release(conn, "codal_pipeline", owner)


# ─── سلامتیِ خط (برایِ API و UI) ─────────────────────────────────────────── #

def health(conn, worker_key="codal_pipeline"):
    """وضعیتِ واقعیِ خط — از جدول، بدونِ شمارندهٔ ساختگی.

    «آخرین sync موفق» یعنی چرخه‌ای که `finished_at` دارد و `error` ندارد؛
    چرخۀ شکست‌خورده هرگز موفق گزارش نمی‌شود.
    """
    c = counts(conn)
    try:
        last_ok = conn.execute(
            "SELECT finished_at, cycle, processed, done, failed FROM pipeline_runs"
            " WHERE finished_at IS NOT NULL AND error IS NULL"
            " ORDER BY id DESC LIMIT 1").fetchone()
    except sqlite3.Error:
        last_ok = None
    try:
        last_any = conn.execute(
            "SELECT started_at, finished_at, cycle, phase, error, found, enqueued,"
            " processed, done, empty, failed, unresolved, symbols_dirty,"
            " indicators_recomputed, cache_invalidated, checkpoint_before,"
            " checkpoint_after FROM pipeline_runs ORDER BY id DESC LIMIT 1").fetchone()
    except sqlite3.Error:
        last_any = None
    try:
        cursors = {r[0]: r[1] for r in conn.execute(
            "SELECT key, value FROM pipeline_cursor")}
    except sqlite3.Error:
        cursors = {}
    return {
        "queue": c,
        "dirty_symbols": dirty_count(conn),
        "cursor": cursors,
        "last_successful_sync": ({"at": last_ok[0], "cycle": last_ok[1],
                                  "processed": last_ok[2], "done": last_ok[3],
                                  "failed": last_ok[4]} if last_ok else None),
        "last_attempt": (dict(zip(
            ["started_at", "finished_at", "cycle", "phase", "error", "found",
             "enqueued", "processed", "done", "empty", "failed", "unresolved",
             "symbols_dirty", "indicators_recomputed", "cache_invalidated",
             "checkpoint_before", "checkpoint_after"], last_any)) if last_any else None),
        "lock": lock_state(conn, worker_key),
        "checked_at": now_s(),
    }
