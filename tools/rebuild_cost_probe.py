# -*- coding: utf-8 -*-
"""
tools/rebuild_cost_probe.py — سنجشِ هزینهٔ «بازسازیِ تابلو» رویِ یک کپی

سه عدد کنار هم، همه از متنِ خودِ `api/market.py` (تک‌نسخهٔ حقیقت):

  warm   — کوئریِ کاملِ تابلو، همان‌که امروز می‌دود: دو پنجرۀ روزانه از
           `board_hist_v` / `board_hist_fv` خوانده می‌شوند (کشِ materialized).
  cold   — همان کوئریِ کامل، کلمه‌به‌کلمه، ولی دو جدول با «VIEWِ همان متنِ
           پنجره» جانشین شده‌اند. یعنی دقیقاً حالتِ پیش از ۱٫۰٫۵۶ که هر
           درخواست پنجره‌ها را خودش می‌ساخت.
  rebuild— یک‌بارِ ساختنِ هر دو جدول از صفر (چیزی که هر پروسه روزی یک‌بار
           و هنگامِ درخواستِ نخستِ تابلو می‌پردازد).

برابریِ دو مسیر با چک‌سامِ بی‌بعد اثبات می‌شود، نه با نگاه: اگر مقادیرِ
کش‌شده با مقادیرِ مسیرِ زنده یکی نباشد ابزار غیرصفر می‌دهد. هیچ نوشتنی روی
دیتابیسِ داده‌شده انجام نمی‌شود — اول کپی گرفته می‌شود و همه‌چیز روی کپی.

    python tools/rebuild_cost_probe.py --db "<market.db>" --runs 5
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import statistics
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKET_PY = os.path.join(REPO, "api", "market.py")

COLS = ["p_closing", "p_last", "q_tot_tran", "month_avg_vol", "prev_day_vol",
        "min30_low", "max30_high", "h2_max", "h29_max", "h59_max",
        "prior30_vol", "min_low_29", "hist_sessions", "buy_i_vol"]

# نشانگرها: اگر متنِ خودِ api/market.py عوض شد، ابزار باید بگوید «کهنه‌ام»
# و خاموش شود؛ عددِ ساختگی از این ابزار بیرون نمی‌آید.
QUERY_ANCHORS = ("WITH iso AS (",
                 "v AS MATERIALIZED (SELECT * FROM board_hist_v)",
                 "fv AS MATERIALIZED (SELECT * FROM board_hist_fv)",
                 "ctm AS (", "SELECT m.ins_code")


def load_texts():
    src = open(MARKET_PY, encoding="utf-8").read()
    m = re.search(r'query = """(.*?)"""', src, re.DOTALL)
    if not m:
        raise SystemExit('marker `query = """` not found in api/market.py')
    q = m.group(1)
    for anchor in QUERY_ANCHORS:
        if anchor not in q:
            raise SystemExit(f"anchor lost: {anchor!r} — this tool is stale")
    out = {"query": q}
    for name in ("_HIST_V_SQL", "_HIST_FV_SQL"):
        mm = re.search(re.escape(name) + r' = """(.*?)"""', src, re.DOTALL)
        if not mm:
            raise SystemExit(f"{name} not found in api/market.py — this tool is stale")
        sql = mm.group(1).strip()
        if not sql.upper().startswith("WITH ") or not sql.rstrip().endswith("SELECT * FROM v") \
                and not sql.rstrip().endswith("SELECT * FROM fv"):
            raise SystemExit(f"{name} no longer has the `WITH … SELECT * FROM x` shape")
        out[name] = sql
    return out


def fingerprint(rows, names):
    """چک‌سامِ بی‌بعد از ستون‌هایِ کلیدی — اثباتِ برابریِ دو مسیر.

    ستونی که در نتیجه نباشد خطا می‌دهد، نه سکوت: مقایسهٔ دو نتیجهٔ بی‌ستونِ
    یکسان «برابر» به‌نظر می‌رسد و آن «برابر» کلِ سنجش را بی‌ارزش می‌کند.
    """
    missing = [c for c in COLS if c not in names]
    if missing:
        raise SystemExit(f"fingerprint: column(s) not in result: {missing}")
    idx = [names.index(c) for c in COLS]
    acc = 0
    for r in rows:
        for i in idx:
            v = r[i]
            if isinstance(v, float):
                v = round(v, 6)
            acc = (acc * 1315423911 + hash((i, v))) & 0xFFFFFFFFFFFFFFFF
    return f"{len(rows)}x{len(idx)}:{acc:016x}"


def run_query(conn, sql):
    cur = conn.execute(sql)
    return [d[0] for d in cur.description], cur.fetchall()


def timeit(conn, sql, runs):
    times, names, rows = [], [], None
    for _ in range(runs):
        t0 = time.perf_counter()
        names, rows = run_query(conn, sql)
        times.append(time.perf_counter() - t0)
    return times, names, rows


def swap_to_views(conn, hist_v_sql, hist_fv_sql):
    """دو جدولِ کش جانشینِ VIEWِ همان متنِ پنجره می‌شوند (حالتِ پیش از ۱٫۰٫۵۶)."""
    for table, sql in (("board_hist_v", hist_v_sql), ("board_hist_fv", hist_fv_sql)):
        conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute(f"DROP VIEW IF EXISTS {table}")
        conn.execute(f"CREATE VIEW {table} AS {sql}")


def rebuild_tables(conn, hist_v_sql, hist_fv_sql):
    """بازسازیِ دو جدول، عینِ `api/market.py::_rebuild_history_windows`."""
    out = {}
    for table, sql, source in (("board_hist_v", hist_v_sql, "price_history"),
                               ("board_hist_fv", hist_fv_sql, "tape_history")):
        tmp = table + "_new"
        # این ابزار پیش از بازسازی، جدول‌ها را به VIEWِ همان متن بدل کرده بود؛
        # پس «DROP TABLE» تنها کافی نیست و SQLite با خطا می‌ایستد.
        conn.execute(f"DROP VIEW IF EXISTS {table}")
        conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute(f"DROP TABLE IF EXISTS {tmp}")
        t0 = time.perf_counter()
        conn.execute(f"CREATE TABLE {tmp} AS {sql}")
        out[table] = time.perf_counter() - t0
        n = conn.execute(f"SELECT COUNT(*) FROM {tmp}").fetchone()[0]
        n_src = conn.execute(f"SELECT COUNT(*) FROM {source}").fetchone()[0]
        if n == 0 and n_src > 0:
            raise SystemExit(f"history window {table} built zero rows while {source} has {n_src}")
        conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute(f"ALTER TABLE {tmp} RENAME TO {table}")
    conn.commit()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    texts = load_texts()
    q, hist_v, hist_fv = texts["query"], texts["_HIST_V_SQL"], texts["_HIST_FV_SQL"]

    src_db = os.path.abspath(args.db)
    tmp_dir = tempfile.mkdtemp(prefix="bors_rebuild_probe_")
    work_db = os.path.join(tmp_dir, "market_copy.db")
    t0 = time.perf_counter()
    a = sqlite3.connect("file:" + src_db.replace("\\", "/") + "?mode=ro", uri=True)
    b = sqlite3.connect(work_db)
    a.backup(b, pages=256)
    a.close()
    b.close()
    print(f"[copy] {os.path.basename(src_db)} -> {work_db} "
          f"in {time.perf_counter() - t0:.1f}s "
          f"({os.path.getsize(work_db) / 1e6:.1f}MB) — source opened read-only")

    conn = sqlite3.connect(work_db)
    conn.execute("PRAGMA cache_size=-65536")

    warm_t, names, warm_rows = timeit(conn, q, args.runs)
    fp_warm = fingerprint(warm_rows, names)
    print(f"[warm  ] median={statistics.median(warm_t):.3f}s  "
          f"all={['%.3f' % t for t in warm_t]}  rows={len(warm_rows)}  fp={fp_warm}")

    swap_to_views(conn, hist_v, hist_fv)
    cold_t, cnames, cold_rows = timeit(conn, q, args.runs)
    fp_cold = fingerprint(cold_rows, cnames)
    print(f"[cold  ] median={statistics.median(cold_t):.3f}s  "
          f"all={['%.3f' % t for t in cold_t]}  rows={len(cold_rows)}  fp={fp_cold}")

    rebuilt = rebuild_tables(conn, hist_v, hist_fv)
    print(f"[rebuild] " + "  ".join(f"{k}={v:.3f}s" for k, v in rebuilt.items())
          + f"  once-per-day={sum(rebuilt.values()):.3f}s")
    after_t, anames, after_rows = timeit(conn, q, args.runs)
    fp_after = fingerprint(after_rows, anames)
    print(f"[after ] median={statistics.median(after_t):.3f}s  fp={fp_after}")

    identical = fp_warm == fp_cold == fp_after
    saved = statistics.median(cold_t) - statistics.median(warm_t)
    print(f"[parity] identical={identical}")
    print(f"[saving] per-request={saved:.3f}s "
          f"({saved / statistics.median(cold_t) * 100:.1f}% of the cold path)")
    conn.close()

    result = {
        "db": src_db, "runs": args.runs,
        "warm": warm_t, "cold": cold_t, "after_rebuild": after_t,
        "rebuild_seconds": rebuilt,
        "median_warm": statistics.median(warm_t),
        "median_cold": statistics.median(cold_t),
        "median_after_rebuild": statistics.median(after_t),
        "rows": len(warm_rows), "identical": identical,
        "fp_warm": fp_warm, "fp_cold": fp_cold, "fp_after": fp_after,
    }
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1, ensure_ascii=False)
        print("wrote " + args.out)
    try:
        os.remove(work_db)
        os.rmdir(tmp_dir)
    except OSError:
        pass
    return 0 if identical else 1


if __name__ == "__main__":
    sys.exit(main())
