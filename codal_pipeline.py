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
    "discover_instruments", "instrument_snapshot", "instrument_coverage",
    "discover_instruments", "coverage_resolver",
    "worker_once", "start_worker", "stop_worker", "worker_status",
    "next_wakeup", "catchup_state", "crawler_busy", "market_in_session",
    "offline_gate", "status_payload",
    "CADENCE_IDLE_S", "CADENCE_BACKLOG_S", "DISCOVERY_MIN_GAP_S",
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
               "cache_invalidated", "phase", "error", "checkpoint_after"} | set(
                   CF._RUN_INSTRUMENT_COLS)
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


# ─── محاسبۀ افزایشیِ پنج شاخص (بندِ ۷ مأموریت) ────────────────────────────── #

RECALC_BATCH = 80               # سقفِ نماد در هر چرخه


def recompute_dirty(conn, dirty=None, *, judge=None, invalidate=None,
                    limit=RECALC_BATCH, now=None):
    """مصرفِ `pipeline_dirty` با باطل‌کردنِ **همان نمادها**، نه کل بازار.

    نقشۀ وابستگی درِ `AXES_BY_SOURCE` است و اینجا هیچ فرمول یا آستانه‌ای دوباره
    نوشته نمی‌شود. معماریِ فعلیِ برنامه خروجیِ بنیادی را جایی ذخیره نمی‌کند جز
    `fts_results` (ردیف به‌ازایِ نماد) و کشِ اسکرینر/قیف؛ کارتِ جزئیات هر درخواست
    را از canonical دوباره می‌سنجد. پس «محاسبۀ افزایشی» درِ این خط یعنی:
      ۱) ردیفِ مادی‌شدۀ همان نمادها باطل شود ⇒ قیف/غربالگری/کارت از منبعِ
         canonical دوباره می‌خوانند و نتیجهٔ کهنه نمی‌دهند؛
      ۲) اگر `judge` تزریق شده باشد (محاسبه‌گرِ واقعی یا گرم‌کردنِ پیش‌دستانه)،
         برایِ همان نمادها صدا زده می‌شود و فقط همان‌ها «محاسبه‌شده» شمرده‌اند.

    رأیِ مأموریت «محاسبۀ محافظه‌کارانۀ بیشتر بهتر از نتیجهٔ کهنه» است، پس بی‌
    مدرکِ موفقیت هیچ علامتی از `pipeline_dirty` پاک نمی‌ماند؛ `run_cycle`
    نمادهایِ بی‌جواب را دوباره علامت می‌زند.
    """
    now = now or now_s()
    if dirty is None:
        dirty = dirty_take(conn, limit=limit)
    if not dirty:
        return {"recomputed": 0, "cache_invalidated": 0, "failed": 0,
                "done_symbols": [], "axes": {}}
    done, failed = [], []
    if invalidate is None:
        invalidate = _invalidate_materialized
    try:
        dropped = int(invalidate(conn, sorted(dirty)) or 0)
    except Exception:
        dropped = 0
        failed = sorted(dirty)
        return {"recomputed": 0, "cache_invalidated": 0, "failed": len(failed),
                "done_symbols": [], "axes": {}}
    if dropped:
        # کشِ payload اسکرینر/قیف **سراسری** است و باطل‌سازِ تک‌نمادی ندارد؛ پس
        # بی‌مورد بودنِ آن یعنی قیف همان ردیفِ کهنه را نشان می‌دهد. بی‌`dirty`ِ
        # مصرف‌شده هیچ‌وقت صدا زده نمی‌شود، و `drop_materialized=False` چون
        # ردیفِ جدول را همین‌جا بردیم (در EXE هم تنها این راه می‌ماند).
        try:
            from api.screener import invalidate_screener_cache
            invalidate_screener_cache(drop_materialized=False)
        except Exception:
            pass
    if judge:
        for sym, axes in dirty.items():
            try:
                ok = judge(conn, sym, axes or [])
            except Exception:
                ok = False
            (done if ok else failed).append(sym)
    else:
        done = sorted(dirty)
    return {"recomputed": len(done), "cache_invalidated": dropped,
            "failed": len(failed), "done_symbols": done,
            "axes": {s: list(v or []) for s, v in dirty.items()}}


def _invalidate_materialized(conn, symbols):
    """ردیف‌های `fts_results` همان نمادها − کشِ خواننده.

    `fts_engine` سنگین است و درِ این ماژولِ stdlib-only جا نمی‌شود؛ دیرهنگام
    import می‌شود و اگر نبود، با صفر برمی‌گردد (نه ساختنِ باطل‌کنندۀ دوم).
    """
    try:
        import fts_engine as _fe
    except Exception:
        return 0
    try:
        return int(_fe.invalidate_fts_results(conn, symbols=list(symbols)))
    except TypeError:           # پیادۀ بی‌`symbols` (سازگاریِ دوطرفه)
        return int(_fe.invalidate_fts_results(conn))
    except Exception:
        return 0


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


# ─── کشفِ ابزارِ تازه/تغییرکرده (بندِ ۳ مأموریت) ──────────────────────────── #

# دفترِ عضویت، نه خزندۀ دوم: `test_tsetmc.py` تابلو را درِ `instruments` و
# `market_watch` می‌نویسد؛ این لایه همان منبعِ معتبر را با دفترِ خودش مقایسه
# می‌کند تا «ابزارِ تازه»، «تغییرِ شناسه»، «تغییرِ نام»، «غیرفعال» و
# «حذف‌شده از Universe» از هم جدا بمانند.
MEMBERSHIP_PRESENT = "present"
MEMBERSHIP_ABSENT = "absent"
MEMBERSHIP_REMOVED = "removed"
REMOVED_AFTER_CYCLES = 2        # دو چرخۀ پی‌درپی غیبت ⇒ حذف از Universe
INSTR_LEDGER_COLS = ("ins_code", "symbol", "name", "class", "kind", "sector",
                     "isin", "paper_type", "prev_name", "first_seen_at",
                     "last_seen_at", "last_board_at", "membership",
                     "cycles_absent", "flags", "identity", "identity_note",
                     "coverage", "coverage_at", "updated_at")


def _table_exists(conn, name):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table'"
                             " AND name=?", (name,)).fetchone())


def instrument_snapshot(conn):
    """جامعۀ فعلی + حضور در تابلو + وضعیتِ معاملاتی، از خودِ بانکِ کاری.

    ستون‌ها با `PRAGMA table_info` گزینش می‌شوند: نسخۀ trim‌شدهٔ بانک (یا بانکِ
    تست) ممکن است `isin`/`paper_type`/`sector_name` را نداشته باشد، و نبودِ
    ستون نباید با مقدارِ ساختگی پر شود — آن `None` می‌ماند. نبودِ `market_watch`
    یا `instrument_state` هم یعنی **سنسور نیست**، نه «غیرفعال است»؛ پس هیچ
    ادعایِ غیرفعالی از هیچِ مدرک ساخته نمی‌شود.
    """
    if not _table_exists(conn, "instruments"):
        return []
    icols = {r[1] for r in conn.execute("PRAGMA table_info(instruments)")}
    sel = ["i.ins_code", "i.l_val18", "i.l_val30"]
    for _c in ("paper_type", "isin", "sector_name"):
        sel.append("i." + _c if _c in icols else "NULL")
    has_w = _table_exists(conn, "market_watch")
    has_s = _table_exists(conn, "instrument_state")
    # EXISTS → 0/1: «تابلو هست ولی این ابزار درِ آن نیست» با «سنسور نیست»
    # یکی نمی‌شود (بی‌این تفکیک، غیرفعال هیچ‌وقت دیده نمی‌شد — سنجیده شد).
    sel.append("EXISTS (SELECT 1 FROM market_watch w"
               " WHERE w.ins_code = i.ins_code)" if has_w else "NULL")
    sel.append("(SELECT s.c_etaval_title FROM instrument_state s"
               " WHERE s.ins_code = i.ins_code)" if has_s else "NULL")
    out = []
    for r in conn.execute("SELECT %s FROM instruments i"
                          " ORDER BY i.l_val18, i.ins_code" % ", ".join(sel)):
        out.append({"ins_code": r[0], "symbol": r[1], "name": r[2],
                    "paper_type": r[3], "isin": r[4], "sector": r[5],
                    "on_board": (None if r[6] is None else bool(r[6])),
                    "state": r[7]})
    return out


def _coverage_maps(conn):
    """نقشۀ شمارشِ هر نوشتارِ خام درِ کدال — یکِ GROUP BY به‌ازایِ جدول.

    چرا: سنجشِ رویِ کپیِ بانکِ کاری (۱۴۰۵-۰۷-۲۷) یکِ پاسِ Universe را ۸۱ ثانیه
    برد؛ دلیلش ~۱۲٬۰۰۰ کوئریِ COUNT (دو به‌ازایِ هر ۵٬۹۹۲ ابزار) بود. همان
    شمارش با یکِ بارِ خواندنِ جدول به‌دست می‌آید و معنایش عوض نمی‌شود.
    """
    maps = {}
    for tbl in ("financial_statements", "monthly_sales"):
        try:
            maps[tbl] = {r[0]: int(r[1]) for r in conn.execute(
                "SELECT symbol, COUNT(*) FROM %s GROUP BY symbol" % tbl)}
        except sqlite3.Error:
            maps[tbl] = None
    return maps


def _cov_for(maps, variants):
    """جمعِ ردیف‌ها برایِ همهٔ نوشتارهایِ زیرِ یکِ کلیدِ هویت."""
    fs = ms = 0
    for m, keyname in ((maps.get("financial_statements"), "fs"),
                       (maps.get("monthly_sales"), "ms")):
        if m is None:
            return "unknown", 0, 0
        n = 0
        for v in variants:
            n += m.get(v, 0)
        if keyname == "fs":
            fs = n
        else:
            ms = n
    if fs and ms:
        return "fs+ms", fs, ms
    if fs:
        return "fs", fs, ms
    if ms:
        return "ms", fs, ms
    return "none", 0, 0


def coverage_resolver(conn):
    """یکِ تابعِ `symbol → (coverage, n_fs, n_ms)` با کشِ داخلیِ هر پاس.

    نوشتارها از خودِ `symbol_identity.variants`/`line_variants` می‌آیند — همان
    قاعدۀ «دو رشته یکی است» با گیتِ ISIN؛ نه شباهتِ نام و نه رقمِ انتهاییِ
    حدسی. نبودِ `symbol_identity` ⇒ `unknown` (بی‌ادعا)، نه صفر.
    """
    maps = _coverage_maps(conn)
    try:
        import symbol_identity as SI
    except Exception:
        SI = None
    cache = {}

    def resolve(symbol):
        sym = str(symbol or "").strip()
        if not sym:
            return "none", 0, 0
        if sym in cache:
            return cache[sym]
        if SI is None:
            out = ("unknown", 0, 0)
        else:
            try:
                variants = list(SI.variants(conn, sym, SI.CODAL))
                extra, _ev = SI.line_variants(conn, sym, SI.CODAL)
                for x in extra:
                    if x not in variants:
                        variants.append(x)
                out = _cov_for(maps, variants)
            except Exception:
                out = ("unknown", 0, 0)
        cache[sym] = out
        return out
    return resolve


def instrument_coverage(conn, symbol):
    """پوششِ بنیادیِ یکِ نماد، از **همان** کلیدِ هویتِ `symbol_identity`."""
    return coverage_resolver(conn)(symbol)


def discover_instruments(conn, *, now=None, snapshot=None, classify=None,
                         mark_dirty=True, removed_after=REMOVED_AFTER_CYCLES,
                         eligible_classes=("stock",)):
    """یکِ پاسِ مقایسۀ Universe ← دفترِ `pipeline_instrument` + رویدادها.

    هویت: تنها `ins_code` کلیدِ عضویت است. نامِ نمایشی به‌تنهایی هویت نیست، پس
    تغییرِ نام «ابزارِ تازه» نمی‌سازد و تغییرِ `ins_code` زیرِ یکِ نماد
    `id_changed` پرچم می‌خورد و **هیچ‌وقت** خودکار ادغام نمی‌شود (نه با حذفِ
    رقمِ انتهایی، نه با شباهتِ نام). طبقه‌بندی از `mstat_engine.classify` است:
    صندوق/حقِ تقدم/اوراق مثلِ شرکتِ عملیاتی رفتار نمی‌کنند و اصلاً واردِ مسیرِ
    پنج شاخص نمی‌شوند (`not_eligible`).

    پوششِ بنیادی و پیوندِ کدال **ثبت** می‌شود؛ هیچ رأیِ بنیادی اینجا ساخته
    نمی‌شود. ابزارِ بی‌صورتِ مالی، `coverage='none'` می‌گیرد و همان «بدون داده»
    درِ رابط می‌ماند.
    """
    now = now or now_s()
    if snapshot is None:
        snapshot = instrument_snapshot(conn)
    if classify is None:
        import mstat_engine as _M
        classify = _M.classify
    try:
        import symbol_identity as _SI
        _key = _SI.key
    except Exception:
        def _key(x):
            return str(x or "").strip()
    cov_of = coverage_resolver(conn)      # یکِ بارِ خواندنِ جدول‌ها برایِ هر پاس
    led = {}
    cur = conn.execute("SELECT %s FROM pipeline_instrument"
                       % ",".join(INSTR_LEDGER_COLS))
    for r in cur.fetchall():
        d = dict(zip(INSTR_LEDGER_COLS, tuple(r)))
        led[d["ins_code"]] = d
    by_symbol = {}
    for r in snapshot:
        s = str(r.get("symbol") or "").strip()
        if s:
            by_symbol.setdefault(s, []).append(r["ins_code"])
    # -- هویت و پوشش **پیش از** هر نوشتن محاسبه می‌شود.
    # دلیلِ اندازه‌گیری‌شده (کپیِ بانکِ کاری، ۱۴۰۵-۰۷-۲۷): `symbol_identity` با
    # هر نوشتنِ همین اتصال کشِ خود را می‌اندازد؛ ۱۰۰ جستارِ هویت بی‌نوشتن
    # 0.08 ثانیه و با یکِ نوشتنِ میانِ هر جستار 4.29 ثانیه شد — یعنی پاسِ
    # Universe رویِ ۵٬۹۹۲ ابزار ۷۷ ثانیه می‌کشید. بی‌این تفکیک، «یکِ چرخۀ
    # چندثانیه‌ای» عملاً شد یکِ پاسِ یک‌ونیم‌دقیقه‌ای.
    ident = {}
    for r in snapshot:
        sym = str(r.get("symbol") or "").strip()
        if not sym or sym in ident:
            continue
        cov, n_fs, n_ms = cov_of(sym)
        try:
            ev = _SI.evidence(conn, sym, _SI.CODAL)
        except Exception:
            ev = "identity_key"
        ident[sym] = (cov, n_fs, n_ms, ev)
    tally = {"instr_scanned": 0, "instr_new": 0, "instr_renamed": 0,
             "instr_id_changed": 0, "instr_deactivated": 0, "instr_absent": 0,
             "instr_removed": 0, "instr_ambiguous": 0, "instr_not_eligible": 0,
             "instr_no_publisher": 0}
    events = []
    seen = set()
    for r in snapshot:
        code = r["ins_code"]
        if not code:
            continue
        seen.add(code)
        tally["instr_scanned"] += 1
        sym = str(r.get("symbol") or "").strip()
        nm = str(r.get("name") or "").strip()
        cls, kind = classify(r.get("paper_type"), nm, sym, r.get("sector") or "")
        eligible = cls in tuple(eligible_classes)
        prev = led.get(code)
        flags = []
        if prev is None:
            flags.append("new")
            tally["instr_new"] += 1
            first_seen = now
            prev_name = None
        else:
            first_seen = prev["first_seen_at"] or now
            prev_name = prev["name"]
            if (prev["name"] or "") != nm:
                flags.append("renamed")
                tally["instr_renamed"] += 1
                prev_name = prev["name"]
            if (prev["symbol"] or "") != sym:
                flags.append("symbol_changed")
            if prev["membership"] != MEMBERSHIP_PRESENT:
                flags.append("reactivated")
        if len(by_symbol.get(sym, [])) > 1 and sym:
            flags.append("id_changed")
            tally["instr_id_changed"] += 1
        if r.get("on_board") is False:
            flags.append("deactivated")
            tally["instr_deactivated"] += 1
        # هویتِ صادرکننده — فقط با کلیدِ هویت، نه با حدسِ نام
        if not eligible:
            identity, id_note = "not_eligible", "%s:%s" % (cls, kind)
            tally["instr_not_eligible"] += 1
            cov = "none" if not sym else "unknown"
            n_fs = n_ms = 0
        elif "id_changed" in flags:
            identity, id_note = "ambiguous", "more_than_one_ins_code"
            tally["instr_ambiguous"] += 1
            cov = ident.get(sym, ("unknown", 0, 0, ""))[0]
        else:
            cov, n_fs, n_ms, id_note = ident.get(sym, ("none", 0, 0, ""))
            if cov == "none":
                identity, id_note = "no_publisher", "no_codal_rows_for_identity_key"
                tally["instr_no_publisher"] += 1
            else:
                identity = "linked"          # id_note از همان پیش‌محاسبه می‌آید
        membership = MEMBERSHIP_PRESENT
        conn.execute(
            "INSERT INTO pipeline_instrument (ins_code, symbol, name, class, kind,"
            " sector, isin, paper_type, prev_name, first_seen_at, last_seen_at,"
            " last_board_at, membership, cycles_absent, flags, identity,"
            " identity_note, coverage, coverage_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?,?,?,?,?)"
            " ON CONFLICT(ins_code) DO UPDATE SET"
            "   symbol=excluded.symbol, name=excluded.name, class=excluded.class,"
            "   kind=excluded.kind, sector=excluded.sector, isin=excluded.isin,"
            "   paper_type=excluded.paper_type, prev_name=excluded.prev_name,"
            "   last_seen_at=excluded.last_seen_at,"
            "   last_board_at=excluded.last_board_at,"
            "   membership=excluded.membership, cycles_absent=0,"
            "   flags=excluded.flags, identity=excluded.identity,"
            "   identity_note=excluded.identity_note, coverage=excluded.coverage,"
            "   coverage_at=excluded.coverage_at, updated_at=excluded.updated_at",
            (code, sym, nm, cls, kind, r.get("sector"), r.get("isin"),
             r.get("paper_type"), prev_name, first_seen, now,
             now if r.get("on_board") else prev["last_board_at"] if prev else None,
             membership, ",".join(flags), identity, id_note, cov, now, now))
        if flags:
            events.append({"ins_code": code, "symbol": sym, "flags": flags,
                           "identity": identity, "coverage": cov,
                           "class": cls, "kind": kind})
        if mark_dirty and eligible and ({"new", "renamed", "id_changed",
                                         "symbol_changed", "deactivated"} & set(flags)):
            dirty_mark(conn, sym, "instruments", reason="instrument:" +
                       ",".join(flags))
    # غیبت: سطرهایِ دفتر که درِ Universeِ امروز نیستند
    for code, prev in led.items():
        if code in seen:
            continue
        absent = int(prev["cycles_absent"] or 0) + 1
        membership = (MEMBERSHIP_REMOVED if absent >= int(removed_after)
                      else MEMBERSHIP_ABSENT)
        was_removed = prev["membership"] == MEMBERSHIP_REMOVED
        flag = "removed" if membership == MEMBERSHIP_REMOVED else "absent"
        conn.execute("UPDATE pipeline_instrument SET membership=?,"
                     " cycles_absent=?, flags=?, updated_at=? WHERE ins_code=?",
                     (membership, absent, flag, now, code))
        ev = {"ins_code": code, "symbol": prev["symbol"], "flags": [flag],
              "identity": prev["identity"], "coverage": prev["coverage"],
              "class": prev["class"], "kind": prev["kind"]}
        if membership == MEMBERSHIP_REMOVED and not was_removed:
            tally["instr_removed"] += 1
            events.append(ev)
            if mark_dirty and prev["symbol"]:
                dirty_mark(conn, prev["symbol"], "instruments",
                           reason="instrument:removed")
        else:
            # غیبتِ یکِ چرخه «حذف» نیست؛ هنوز سنسور ممکن است یک‌بار ننویسد.
            tally["instr_absent"] += 1
            events.append(ev)
    conn.commit()
    tally["events"] = events
    tally["ledger"] = int(conn.execute("SELECT COUNT(*) FROM pipeline_instrument")
                          .fetchone()[0])
    return tally


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
              recalc=None, now=None, kinds=None, instruments="auto"):
    """یکِ چرخۀ کامل: قفل ← بازیابیِ کارِ نیمه ← کشفِ Universe ← کشفِ اطلاعیه ←
    پردازش ← تازه‌سازی ← نوشتنِ گزارش و checkpoint.

    همه‌چیز تزریق‌پذیر است (`discover`، `scrape`، `recalc`، `instruments`) تا
    گاردِ آفلاین همان مسیرِ تولید را با scraperِ فیک بزند، نه یک مسیرِ دومِ
    نمایشی. `instruments="auto"` یعنی مقایسۀ Universe از خودِ بانک (بی‌شبکه).
    """
    now = now or now_s()
    out = {"skipped": None, "recovered": 0, "found": 0, "enqueued": 0,
           "done": 0, "empty": 0, "failed": 0, "rejected": 0,
           "processed": 0, "symbols": [], "dirty": 0, "recomputed": 0,
           "cache_invalidated": 0, "checkpoint_before": cursor_get(conn, "discovery_day"),
           "checkpoint_after": None, "run_id": None, "error": None,
           "instruments": {}, "events": []}
    if not lock_acquire(conn, "codal_pipeline", owner, now=now):
        out["skipped"] = "locked"
        return out
    run_id = run_start(conn, "cycle", owner, checkpoint_before=out["checkpoint_before"])
    out["run_id"] = run_id
    try:
        out["recovered"] = release_stale(conn, now=now)
        if instruments == "auto":
            ins = discover_instruments(conn, now=now) or {}
            out["instruments"] = {k: v for k, v in ins.items()
                                  if k.startswith("instr_")}
            out["events"] = ins.get("events") or []
            run_update(conn, run_id, **out["instruments"])
        elif callable(instruments):
            ins = instruments(conn) or {}
            out["instruments"] = {k: v for k, v in ins.items()
                                  if k.startswith("instr_")}
            out["events"] = ins.get("events") or []
            run_update(conn, run_id, **out["instruments"])
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
        if recalc == "auto":
            recalc = recompute_dirty
        if recalc and out["dirty"]:
            # سقفِ هر چرخه: صفِ بزرگ یک‌باره خالی نمی‌شود (بودجه‌مند، مثلِ کارها)
            dirty = dirty_take(conn, limit=RECALC_BATCH)
            res = recalc(conn, dirty) or {}
            out["recomputed"] = int(res.get("recomputed") or 0)
            out["cache_invalidated"] = int(res.get("cache_invalidated") or 0)
            out["recalc_failed"] = int(res.get("failed") or 0)
            reported = res.get("done_symbols")
            # فقط وقتی محاسبه‌گر خروجیِ **تک‌نمادی** گزارش می‌کند، بی‌جواب‌ها را
            # برمی‌گردانیم. اگر چیزی گزارش نکرد، قراردادِ پیشین حاکم است: همان
            # که `dirty_take` برداشته، مصرف شده است.
            missed = ({} if reported is None
                      else {k: v for k, v in dirty.items() if k not in set(reported)})
            for sym, axes in missed.items():
                # نمادی که محاسبه‌گر یا آن را ندید یا شکست خورد ⇒ دوباره علامت،
                # تا «نتیجهٔ کهنه» جایِ «هنوز محاسبه نشده» را نگیرد.
                for ax in (axes or ["1_growth"]):
                    conn.execute(
                        "INSERT INTO pipeline_dirty (symbol, axis, reason, marked_at)"
                        " VALUES (?,?,?,?) ON CONFLICT(symbol, axis) DO UPDATE SET"
                        " reason=excluded.reason, marked_at=excluded.marked_at",
                        (sym, ax, "recalc-missed", now))
            conn.commit()
            out["dirty"] = dirty_count(conn)
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


# ─── زمان‌بندی مستقل از رابط (بندِ ۶ مأموریت) ─────────────────────────────── #
#
# چرا تایمرِ ثابت نه: «کِی بیدار شویم» از خودِ داده معلوم می‌شود — کارِ
# بازیابی‌شدنی درِ صف `next_attempt_at` دارد، و پاسِ شبکه‌ای بودجۀ زمانیِ خودش
# را. چرخۀ نمایشیِ «هر N دقیقه یک درخواست به کدال» همان چیزی است که بن ۴۲۹
# می‌سازد.
CADENCE_IDLE_S = 6 * 3600          # صف تهی ⇒ روزی دو پاس کافی است
CADENCE_BACKLOG_S = 300            # کارِ بازیابی‌شدنی ⇒ هر پنج دقیقه
CADENCE_MIN_S = 60                 # سقفِ بیدارباشِ پی‌درپی
DISCOVERY_MIN_GAP_S = 3 * 3600     # حداقل فاصلۀ دو پاسِ شبکه‌ای
CURSOR_LAST_NETWORK = "notice_last_network_pass_at"
CODAL_BUSY_PHASES = ("codal_sync", "codal_backoff", "codal_paused", "codal_stopped")
_WORKER: dict = {"thread": None, "stop": None, "owner": None, "started_at": None,
                 "cycles": 0, "last_error": None}


def offline_gate():
    """دربۀ آفلاین: با `BORS_CODAL_OFFLINE=1` هیچ درخواستی به کدال و هیچ
    کنترلی به دستگاه (ADB) نرود، ولی مسیرِ صف/چرخه همچنان اجرا شود.

    چرا لازم شد: گاردِ همین بند رویِ ماشینِ توسعه یکِ پاسِ شبکه‌ایِ واقعی را
    تصمیم گرفت (چون `network=None` خود تصمیم می‌گیرد) و خزنده از راهِ ADB خواست
    IP بچرخاند — کاری که قراردادِ مخزن برایِ آزمونِ یکِ گارد ممنوع می‌کند.
    قفلِ «تزریقِ stub در گارد» جواب نمی‌دهد، چون زیرمسیرها (CLI، subprocess)
    همان‌جا نمی‌آیند؛ این دربه‌دیوار درِ خودِ `worker_once` است.
    """
    return (os.environ.get("BORS_CODAL_OFFLINE") or "").strip().lower() in (
        "1", "true", "yes")


def _offline_scrape(n):
    """جانشینِ بی‌شبکهٔ `scrape_notice_row`: فقط «باز نشد» را ثبت می‌کند."""
    kind = n[1] if (n and n[1] in ("fs", "ms")) else "fs"
    return kind, None, "failed"


def _to_dt(s):
    """`%Y-%m-%d %H:%M:%S` و همان `isoformat()` با `T`.

    `write_progress` زمان را با `isoformat(timespec="seconds")` می‌نویسد («T»
    جداکننده)؛ بی‌پذیرفتنِ هر دو، `crawler_busy` همیشه «آزاد» می‌گفت و worker
    خودکار وسطِ کارِ خزندۀ دستی درخواست می‌زد (سنجیده شد).
    """
    t = str(s or "").strip().replace("T", " ")
    try:
        return datetime.datetime.strptime(t[:19], "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def _age_s(s, now_dt=None):
    d = _to_dt(s)
    if not d:
        return None
    return int(((now_dt or datetime.datetime.now()) - d).total_seconds())


def market_in_session(now_dt=None) -> bool:
    """آیا بازار باز است؟ از **همان** پنجره‌ای که `app.py` و `mstat_engine`
    استفاده می‌کنند (۰۹:۰۰–۱۳:۰۰ و تعطیلی پنجشنبه/جمعه) — تعریفِ دوم نمی‌سازیم.

    بی‌خبرِ تعطیلاتِ رسمی: درِ این مخزن تقویمِ تعطیلیِ جایگزینِ آفلاینی وجود
    ندارد (سنجشِ Stage 0: `grep jalali|shamsi` هیچی); وضعیتِ رسمی از جدولِ
    `market_index` می‌آید. لذا «خم» فقط پنجرۀ معاملاتی است و ادعایِ تعطیلی
    نمی‌شود — بندِ «صادقانه» مأموریت.
    """
    try:
        from mstat_engine import in_trading_session
        n = now_dt or datetime.datetime.now()
        return bool(in_trading_session(n.hour * 10000 + n.minute * 100 + n.second, n))
    except Exception:
        return False


def crawler_busy(status_path=None, max_age_s=900, now_dt=None):
    """آیا خزندۀ دستی (دکمۀ «بروزرسانی کدال») همین حالا ترافیک می‌زند؟

    `codal_pipeline` و `api/_sync_codal.py` دو مسیرِ مستقل به یکِ IP هستند؛ اگر
    هر دو هم‌زمان بدوند، ۴۲۹/بن نصیبِ کاربر می‌شود. این دربه‌دیوار از همان
    `sync_status.json` می‌خواند که خودِ خزنده می‌نویسد — حلقهٔ جدیدی نمی‌سازد.
    """
    path = status_path or getattr(CF, "STATUS_PATH", None)
    if not path:
        return {"busy": False, "reason": "no-status-path"}
    try:
        import json
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return {"busy": False, "reason": "unreadable"}
    age = _age_s(d.get("ts"), now_dt)
    ph = str(d.get("phase") or d.get("stage") or "")
    busy = ph in CODAL_BUSY_PHASES and age is not None and age <= int(max_age_s)
    return {"busy": bool(busy), "phase": ph, "age_s": age,
            "reason": "fresh-codal-phase" if busy else "idle"}


def next_wakeup(conn, now=None, network_gap_s=DISCOVERY_MIN_GAP_S):
    """چراغِ بیدارباش بعدی + علتش — از خودِ صف و checkpoint.

    خروجی: `{"at", "seconds", "reason", "need_network"}`؛ `reason` یکی از
    `retry-at` (وقتِ تلاشِ دوبارهٔ یکِ کار)، `backlog` (کارِ بازیابی‌شدنی هست)،
    `discovery-gap` (پاسِ شبکه زودتر از این مجاز نیست)، `idle`.
    """
    now_dt = _to_dt(now) or datetime.datetime.now()
    now_s = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    c = counts(conn)
    cand, reason = [], "idle"
    if c["retryable"]:
        try:
            rows = conn.execute(
                "SELECT next_attempt_at FROM codal_extracted"
                " WHERE state IN ('queued','failed')"
                " ORDER BY COALESCE(next_attempt_at,'') LIMIT 1").fetchall()
        except sqlite3.Error:
            rows = []
        if rows and rows[0][0]:
            cand.append(str(rows[0][0])[:19])
            reason = "retry-at"
        else:
            cand.append((now_dt + datetime.timedelta(seconds=CADENCE_BACKLOG_S))
                        .strftime("%Y-%m-%d %H:%M:%S"))
            reason = "backlog"
    last_net = cursor_get(conn, CURSOR_LAST_NETWORK)
    age_net = _age_s(last_net, now_dt)
    if age_net is None or age_net >= int(network_gap_s):
        cand.append(now_s)
        if reason == "idle":
            reason = "discovery-due"
    else:
        nxt = (now_dt + datetime.timedelta(seconds=int(network_gap_s) - age_net))
        cand.append(nxt.strftime("%Y-%m-%d %H:%M:%S"))
        if not c["retryable"]:
            reason = "discovery-gap"
    if not c["retryable"] and reason in ("idle", "discovery-gap"):
        cand.append((now_dt + datetime.timedelta(seconds=CADENCE_IDLE_S))
                    .strftime("%Y-%m-%d %H:%M:%S"))
    at = min(x for x in cand if x)
    d = _to_dt(at)
    secs = CADENCE_MIN_S if not d else max(
        CADENCE_MIN_S, int((d - now_dt).total_seconds()))
    return {"at": at, "seconds": int(secs), "reason": reason,
            "need_network": reason in ("discovery-due", "idle") or not last_net,
            "queue": c}


def catchup_state(conn, now=None):
    """آنچه درِ زمانِ خاموشی جا مانده — خام از checkpoint و شمارنده‌ها.

    بی‌ادعا: اگر بانک هیچ چرخۀ موفقی ندارد، `never_synced` می‌گویم و «چند روز
    عقبیم» را نمی‌سازم.
    """
    now_dt = _to_dt(now) or datetime.datetime.now()
    h = health(conn, worker_key="")
    last_ok = (h.get("last_successful_sync") or {}).get("at")
    gap = _age_s(last_ok, now_dt)
    cur = h.get("cursor") or {}
    return {
        "last_successful_sync": last_ok,
        "gap_seconds": gap,
        "never_synced": last_ok is None,
        "queued": h["queue"]["queued"], "failed": h["queue"]["failed"],
        "running": h["queue"]["running"], "unresolved": h["queue"]["unresolved"],
        "retryable": h["queue"]["retryable"],
        "dirty": h["dirty_symbols"],
        "notice_watermark": {k: v for k, v in cur.items()
                             if k.startswith("notice_scan_tn")},
        "last_network_pass": cur.get(CURSOR_LAST_NETWORK),
    }


def worker_once(db_path=None, *, owner=None, conn=None, budget=8, network=None,
                recalc=None, now=None, force=False, busy=None, status_path=None):
    """یکِ چرخه، آماده برایِ threadِ بک‌اند یا Task Scheduler.

    `network=None` یعنی خودِ زمان‌بند تصمیم بگیرد: اگر خزندۀ دستی در کار است،
    یا پاسِ شبکه‌ای زودتر از `DISCOVERY_MIN_GAP_S` از این است، فقط صفِ
    محلی/کارهایِ بازیابی‌شدنی زده می‌شود (بی‌درخواستِ تازه). `recalc=None` هنگامِ
    بازارِ باز یعنی محاسبۀ سنگین به چرخۀ بعد موکول می‌شود — نمادها درِ
    `pipeline_dirty` می‌مانند و چیزی گم نمی‌شود.
    """
    now = now or now_s()
    own = conn is None
    if own:
        conn = sqlite3.connect(db_path or CF.DB_PATH, timeout=120,
                               isolation_level=None)
        conn.row_factory = sqlite3.Row
        CF.create_schema(conn)
        CF.migrate_schema(conn)
    try:
        if busy is None:
            busy = crawler_busy(status_path=status_path)
        age_net = _age_s(cursor_get(conn, CURSOR_LAST_NETWORK), _to_dt(now))
        want = age_net is None or age_net >= DISCOVERY_MIN_GAP_S
        want = want and not busy["busy"]
        use_network = want if network is None else bool(network)
        if offline_gate():
            use_network = False
        if (not use_network and not force
                and not counts(conn)["retryable"]
                and not dirty_count(conn)):
            return {"skipped": "nothing-to-do", "reason": busy.get("reason", ""),
                    "network": False}
        defer_recalc = market_in_session(_to_dt(now))
        res = run_cycle(
            conn, owner or "worker-%d" % os.getpid(),
            discover=discover_auto if use_network else None,
            scrape=_offline_scrape if offline_gate() else CF.scrape_notice_row,
            recalc=(None if defer_recalc and recalc is None
                    else (recalc or "auto")),
            budget=budget, now=now)
        if use_network and res.get("run_id"):
            cursor_set(conn, CURSOR_LAST_NETWORK, now,
                       note="cycle=%s skipped=%s" % (res.get("run_id"),
                                                     res.get("skipped")))
        res["network"] = use_network
        res["recalc_deferred"] = bool(defer_recalc and recalc is None)
        # چراغِ بیدارباش از همان اتصال می‌آید؛ رشتۀ زمان‌بند برایِ «چند
        # ثانیه بخوابم» اتصالِ دوم به بانکِ کاری باز نمی‌کند.
        res["wakeup"] = next_wakeup(conn, now=now)
        return res
    finally:
        if own:
            try:
                conn.close()
            except sqlite3.Error:
                pass


def start_worker(db_path=None, owner=None, *, budget=8, tick_s=30,
                 conn_factory=None, name="codal-auto"):
    """رشتۀ زمان‌بند — **حداکثر یکی به‌ازایِ پروسه** (بندِ ۶: تب‌هایِ زیاد ⇒
    workerِ زیاد نباشد). بازگشت: شرحِ وضعیت، بدونِ ساختنِ رشتۀ دوم.
    """
    if _WORKER.get("thread") and _WORKER["thread"].is_alive():
        return dict(_WORKER, started=False, reason="already-running",
                    thread=_WORKER["thread"].name)

    def _loop():
        stop = _WORKER.get("stop")
        while not (stop and stop.is_set()):
            try:
                r = worker_once(db_path=db_path, owner=owner,
                                conn=(conn_factory() if conn_factory else None),
                                budget=budget)
                _WORKER["cycles"] = int(_WORKER.get("cycles") or 0) + 1
                _WORKER["last"] = {k: r.get(k) for k in
                                   ("skipped", "processed", "done", "failed",
                                    "network", "recalc_deferred", "error")}
                wait = int((r.get("wakeup") or {}).get("seconds") or CADENCE_MIN_S)
            except Exception as e:
                _WORKER["last_error"] = "%s: %s" % (type(e).__name__, e)
                wait = CADENCE_MIN_S
            if stop:
                stop.wait(min(max(int(wait), CADENCE_MIN_S), 6 * 3600))
            else:
                break

    import threading
    _WORKER["stop"] = threading.Event()
    _WORKER["owner"] = owner or "worker-%d" % os.getpid()
    _WORKER["started_at"] = now_s()
    t = threading.Thread(target=_loop, name=name, daemon=True)
    _WORKER["thread"] = t
    t.start()
    return dict(_WORKER, started=True, thread=t.name)


def stop_worker(timeout_s=5):
    st = _WORKER.get("stop")
    if st:
        st.set()
    t = _WORKER.get("thread")
    if t and t.is_alive():
        t.join(timeout=float(timeout_s))
    return worker_status()


def worker_status():
    t = _WORKER.get("thread")
    return {"running": bool(t and t.is_alive()), "owner": _WORKER.get("owner"),
            "started_at": _WORKER.get("started_at"),
            "cycles": _WORKER.get("cycles"), "last": _WORKER.get("last"),
            "last_error": _WORKER.get("last_error")}


# ─── سلامتیِ خط (برایِ API و UI) ─────────────────────────────────────────── #

def health(conn, worker_key="codal_pipeline", db_path=None):
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
    instruments = {}
    if _table_exists(conn, "pipeline_instrument"):
        try:
            instruments = {
                "ledger": int(conn.execute(
                    "SELECT COUNT(*) FROM pipeline_instrument").fetchone()[0]),
                "present": int(conn.execute(
                    "SELECT COUNT(*) FROM pipeline_instrument"
                    " WHERE membership='present'").fetchone()[0]),
                "absent": int(conn.execute(
                    "SELECT COUNT(*) FROM pipeline_instrument"
                    " WHERE membership='absent'").fetchone()[0]),
                "removed": int(conn.execute(
                    "SELECT COUNT(*) FROM pipeline_instrument"
                    " WHERE membership='removed'").fetchone()[0]),
                "ambiguous": int(conn.execute(
                    "SELECT COUNT(*) FROM pipeline_instrument"
                    " WHERE identity='ambiguous'").fetchone()[0]),
                "no_publisher": int(conn.execute(
                    "SELECT COUNT(*) FROM pipeline_instrument"
                    " WHERE identity='no_publisher'").fetchone()[0]),
                "no_fundamental": int(conn.execute(
                    "SELECT COUNT(*) FROM pipeline_instrument"
                    " WHERE class='stock' AND coverage IN ('none','unknown')"
                    " AND membership='present'").fetchone()[0]),
            }
        except sqlite3.Error:
            instruments = {}
    def _scalar(sql, params=()):
        try:
            return conn.execute(sql, params).fetchone()[0]
        except sqlite3.Error:
            return None

    # «آخرین به‌روزرسانیِ دادهٔ بنیادی» = زمانِ نوشتنِ آخرین ردیفِ canonicalِ
    # موفق (`state='done'`)، نه زمانِ تمام‌شدنِ یکِ چرخه. چرخۀ بی‌write هم
    # «sync موفق» دارد (`last_successful_sync`) ولی داده را تازه نکرده، پس
    # این دو درِ پاسخِ سلامت جدا می‌مانند.
    last_data = _scalar("SELECT MAX(tried_at) FROM codal_extracted"
                        " WHERE state='done'")
    return {
        "queue": c,
        "dirty_symbols": dirty_count(conn),
        "cursor": cursors,
        "instruments": instruments,
        "last_data_update": last_data,
        "data_epoch": "%s|%s" % (last_data or "",
                                 _scalar("SELECT COUNT(*) FROM financial_statements")
                                 or 0),
        "last_successful_sync": ({"at": last_ok[0], "cycle": last_ok[1],
                                  "processed": last_ok[2], "done": last_ok[3],
                                  "failed": last_ok[4]} if last_ok else None),
        "last_attempt": (dict(zip(
            ["started_at", "finished_at", "cycle", "phase", "error", "found",
             "enqueued", "processed", "done", "empty", "failed", "unresolved",
             "symbols_dirty", "indicators_recomputed", "cache_invalidated",
             "checkpoint_before", "checkpoint_after"], last_any)) if last_any else None),
        "lock": lock_state(conn, worker_key),
        "worker": worker_status(),
        "checked_at": now_s(),
    }


def status_payload(conn, now=None):
    """همۀ آنچه بندِ ۸ و ۹ خواسته‌اند، درِ یکِ پاسخ — از جدول، نه حافظه.

    هشت شمارشِ الزامیِ رابطِ کاربر:
      آخرین sync موفق (`last_successful_sync`) · آخرین تلاش (`last_attempt`) ·
      اطلاعیه‌های پردازش‌نشده (`queue.queued`) · کارهای شکست‌خورده
      (`queue.failed` + `queue.unresolved`) · استخراج‌های ناقص
      (`incomplete_extractions`) · نمادهای دارای شکاف پوشش
      (`instruments.no_fundamental`) · زمان آخرین به‌روزرسانی دادهٔ بنیادی
      (`last_data_update`) · وضعیت worker (`worker`) + (`cadence`) چراغِ بعدی.
    """
    h = health(conn)
    h["catchup"] = catchup_state(conn, now=now)
    h["cadence"] = next_wakeup(conn, now=now)
    try:
        h["incomplete_extractions"] = int(conn.execute(
            "SELECT COUNT(*) FROM codal_extracted WHERE state='empty'"
            " OR (state IS NULL AND ok=0)").fetchone()[0])
    except sqlite3.Error:
        h["incomplete_extractions"] = 0
    try:
        h["undated_notices"] = len(CF.CP.undated_counts(conn))
    except Exception:
        h["undated_notices"] = 0
    h["offline_gate"] = offline_gate()
    return h


# ─── دريچۀ فرمانی (برایِ Task Scheduler یا اجرایِ دستیِ امن) ──────────────── #

def main(argv=None):
    """`python codal_pipeline.py --once --json [--db PATH] [--budget N] [--force]`

    یکِ چرخه، بی‌رشتۀ نگه‌دارنده، خروجیِ JSON = همان چیزی که `health()` می‌دهد.
    این دريچه برایِ «برنامهٔ زمان‌بندیِ ویندوز» ساخته شده تا وقتی BorsTerminal
    باز نیست هم عقب‌ماندگی جبران شود — اما **خودِ ثبتِ وظیفه را انجام نمی‌دهد**
    (بندِ ۱۲ مأموریت: عملیاتِ سیستمی بدونِ مجوزِ مالک ممنوع). مرزِ عملیاتی و
    فرمانِ دقیق درِ `docs/CODAL-AUTO-UPDATE-2026-10-14.md` است.
    """
    import argparse
    import json
    ap = argparse.ArgumentParser(description="codal pipeline: one durable cycle")
    ap.add_argument("--once", action="store_true", help="یکِ چرخه و خروج")
    ap.add_argument("--db", default=None, help="مسیرِ بانک (پیش‌فرض: بانکِ کاری)")
    ap.add_argument("--budget", type=int, default=8, help="سقفِ کارِ هر چرخه")
    ap.add_argument("--network", choices=("auto", "on", "off"), default="auto")
    ap.add_argument("--force", action="store_true",
                    help="حتی اگر چیزی برایِ کار نیست، پاسِ شبکه بزن")
    ap.add_argument("--status", action="store_true", help="فقط سلامتِ خط")
    ap.add_argument("--catchup", action="store_true",
                    help="فقط وضعیتِ عقب‌ماندگی (بی‌نوشتن)")
    ap.add_argument("--json", action="store_true", help="خروجیِ JSON")
    a = ap.parse_args(argv)
    db = a.db or CF.DB_PATH
    conn = sqlite3.connect(db, timeout=120, isolation_level=None)
    conn.row_factory = sqlite3.Row
    CF.create_schema(conn)
    CF.migrate_schema(conn)
    try:
        if a.status:
            out = health(conn, db_path=db)
        elif a.catchup:
            out = catchup_state(conn)
        else:
            net = {"auto": None, "on": True, "off": False}[a.network]
            out = worker_once(db_path=db, conn=conn, budget=a.budget,
                              network=net, force=a.force)
            out["health"] = health(conn, db_path=db)
        if a.json:
            print(json.dumps(out, ensure_ascii=False, default=str))
        else:
            for k, v in out.items():
                print("%-22s %s" % (k, v))
        return 1 if out.get("error") else 0
    finally:
        try:
            conn.close()
        except sqlite3.Error:
            pass


if __name__ == "__main__":
    sys.exit(main())
