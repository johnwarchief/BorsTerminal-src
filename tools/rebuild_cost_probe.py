# -*- coding: utf-8 -*-
"""
tools/rebuild_cost_probe.py — سنجشِ هزینهٔ «بازسازیِ تابلو» و تفکیکِ آن به
دو بخش: پنجره‌هایِ بی‌تغییرِ روزانه (v و fv) و بخشِ زنده.

کوئری از خودِ `api/market.py` بیرون کشیده می‌شود (تک‌نسخهٔ حقیقت) و با
برشِ متنی رویِ چند نشانگرِ شناخته‌شده به قطعه‌ها تقسیم می‌شود. اگر برش اشتباه باشد
مقایسۀ «نتیجهٔ کامل» با «نتیجهٔ تفکیک‌شده» قرمز می‌شود — پس این ابزار
هرگز عددِ ساختگی چاپ نمی‌کند.

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
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKET_PY = os.path.join(REPO, "api", "market.py")

# ── استخراجِ متنِ کوئری از منبع ────────────────────────────────────────────
def load_query() -> str:
    src = open(MARKET_PY, encoding="utf-8").read()
    m = re.search(r'query = """(.*?)"""', src, re.DOTALL)
    if not m:
        raise SystemExit("marker `query = \"\"\"` not found in api/market.py")
    q = m.group(1)
    for anchor in ("WITH iso AS (", "v AS (", "th AS MATERIALIZED (",
                   "ctm AS (", "SELECT m.ins_code"):
        if anchor not in q:
            raise SystemExit(f"anchor lost: {anchor!r} — this tool is stale")
    return q


def split_query(q: str):
    """بازگرداندنِ چهار قطعه: پیش‌تاگلِ v، قطعهٔ fv، سرآمدِ iso+ctm، بدنهٔ نهایی."""
    i_iso = q.index("WITH iso AS (")
    i_spine_marker = q.index("-- `spine`")
    i_v_end = q.index("ctm AS (")
    i_th = q.index("th AS MATERIALIZED (")
    i_final = q.index("SELECT m.ins_code")

    iso_only = q[i_iso:i_spine_marker]                      # WITH iso AS (...)،
    spine_hist_rk_v = q[i_spine_marker:i_th]                # spine, hist, rk, v AS (...)،
    th_fv = q[i_th:i_v_end]                                 # th, fv AS (...)
    final = q[i_final:]                                     # SELECT ... FROM market_watch ...
    return iso_only, spine_hist_rk_v, th_fv, final


def strip_tail(s: str) -> str:
    """حذفِ خط‌هایِ توضیحیِ انتهایی و کامِ جداکننده، تا قطعه با «)» تمام شود.

    چرا لازم است: قطعه‌هایِ برش‌خورده پیش از نشانگرِ بعدی یک بلوکِ توضیحی
    دارند؛ اگر همان بلوک باقی بماند، «SELECT * FROM v» که به انتهای رشته
    می‌چسبد داخلِ سطرِ توضیح فرو می‌رود و کوئری بی‌معنی (incomplete input)
    می‌شود — و ابزار به‌جایِ سنجش، خطا می‌داد.
    """
    lines = s.rstrip().splitlines()
    while lines and lines[-1].lstrip().startswith("--"):
        lines.pop()
    out = "\n".join(lines).rstrip()
    return out.rstrip(",").rstrip()


def build_variants(q: str):
    iso_only, spine_hist_rk_v, th_fv, final = split_query(q)

    # قطعهٔ v تنها با iso معنا دارد: شرطِ «امروز را بیرون بگذار» در hist به
    # (SELECT d FROM iso) نگاه می‌کند، پس iso باید در همین WITH بماند.
    cache_v_sql = strip_tail(iso_only) + ",\n" + strip_tail(spine_hist_rk_v) + " SELECT * FROM v"
    cache_fv_sql = "WITH " + strip_tail(th_fv) + " SELECT * FROM fv"

    live = (strip_tail(iso_only) + ",\n"
            + "ctm AS (\n                SELECT ins_code, MAX(d_even) AS d FROM client_type\n"
              "                WHERE d_even <= (SELECT d FROM iso)\n"
              "                GROUP BY ins_code\n            )\n"
            + final)
    live = live.replace("LEFT JOIN v ON v.symbol = i.l_val18",
                        "LEFT JOIN cache.v AS v ON v.symbol = i.l_val18")
    live = live.replace("LEFT JOIN fv ON fv.ins_code = m.ins_code",
                        "LEFT JOIN cache.fv AS fv ON fv.ins_code = m.ins_code")
    if "cache.v AS v" not in live or "cache.fv AS fv" not in live:
        raise SystemExit("live-only rewrite did not land — join text changed upstream")
    return q, cache_v_sql, cache_fv_sql, live


COLS = ["p_closing", "p_last", "q_tot_tran", "month_avg_vol", "prev_day_vol",
        "min30_low", "max30_high", "h2_max", "h29_max", "h59_max",
        "prior30_vol", "min_low_29", "hist_sessions", "buy_i_vol"]


def run(conn: sqlite3.Connection, sql: str):
    cur = conn.execute(sql)
    names = [d[0] for d in cur.description]
    return names, cur.fetchall()


def fingerprint(rows, names):
    """چک‌سامِ بی‌بعد از ستون‌هایِ کلیدی — برایِ اثباتِ برابریِ دو مسیر.

    اگر ستونی در نتیجه نباشد ابزار خطا می‌دهد، نه اینکه بی‌صدا از کنارش
    رد شود: مقایسهٔ دو مسیری که ستون‌هایشان یکی نیست «یکسان» به‌نظر می‌رسد
    و همان «یکسان»ِ دروغین تمامِ این سنجش را بی‌ارزش می‌کند.
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


def timeit(conn, sql, runs):
    times = []
    names = rows = None
    for _ in range(runs):
        t0 = time.perf_counter()
        names, rows = run(conn, sql)
        times.append(time.perf_counter() - t0)
    return times, names, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    src = open(MARKET_PY, encoding="utf-8").read()
    _ = src  # فقط برایِ اطمینان از وجودِ منبع
    q, cache_v_sql, cache_fv_sql, live_sql = build_variants(load_query())

    uri = "file:" + args.db.replace("\\", "/") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA cache_size=-65536")
    conn.execute("ATTACH DATABASE ':memory:' AS cache")

    print(f"db={os.path.basename(args.db)} runs={args.runs} "
          f"size={os.path.getsize(args.db)/1e6:.1f}MB")

    # ۱) مسیرِ کامل، N بار (اولین بار سرد است)
    full_t, names, full_rows = timeit(conn, q, args.runs)
    fp_full = fingerprint(full_rows, names)
    print(f"[full ] cold={full_t[0]:.3f}s  median={statistics.median(full_t):.3f}s  "
          f"all={['%.3f' % t for t in full_t]}  rows={len(full_rows)}  fp={fp_full}")

    # ۲) ساختِ کش (روزی یک بار) — جدا سنجیده می‌شود
    tv, _, _ = timeit(conn, cache_v_sql, 2)
    tf, _, _ = timeit(conn, cache_fv_sql, 2)
    conn.execute("DROP TABLE IF EXISTS cache.v")
    conn.execute(f"CREATE TABLE cache.v AS {cache_v_sql}")
    conn.execute("DROP TABLE IF EXISTS cache.fv")
    conn.execute(f"CREATE TABLE cache.fv AS {cache_fv_sql}")
    # در SQLite بخشِ ON نمی‌تواند نامِ اسکیما بگیرد؛ خودِ ایندیس اسکیما می‌گیرد.
    conn.execute("CREATE INDEX cache.idx_v ON v(symbol)")
    conn.execute("CREATE INDEX cache.idx_fv ON fv(ins_code)")
    nv = conn.execute("SELECT COUNT(*) FROM cache.v").fetchone()[0]
    nf = conn.execute("SELECT COUNT(*) FROM cache.fv").fetchone()[0]
    print(f"[cache] v={tv[1]:.3f}s (rows={nv})  fv={tf[1]:.3f}s (rows={nf})  "
          f"once-per-day={tv[1] + tf[1]:.3f}s")

    # ۳) مسیرِ تفکیک‌شده، N بار
    split_t, snames, srows = timeit(conn, live_sql, args.runs)
    fp_split = fingerprint(srows, snames)
    print(f"[split] cold={split_t[0]:.3f}s  median={statistics.median(split_t):.3f}s  "
          f"all={['%.3f' % t for t in split_t]}  rows={len(srows)}  fp={fp_split}")

    same = (fp_full == fp_split) and (len(full_rows) == len(srows))
    print(f"[parity] identical={same}  full_fp={fp_full}  split_fp={fp_split}")

    saved = statistics.median(full_t) - statistics.median(split_t)
    print(f"[saving] per-rebuild={saved:.3f}s  "
          f"({saved / statistics.median(full_t) * 100:.1f}% of full)")

    result = {
        "db": args.db, "runs": args.runs,
        "full": full_t, "split": split_t,
        "cache_v": tv[1], "cache_fv": tf[1],
        "rows": len(full_rows), "identical": same,
        "fp_full": fp_full, "fp_split": fp_split,
        "median_full": statistics.median(full_t),
        "median_split": statistics.median(split_t),
    }
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1, ensure_ascii=False)
    conn.close()
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
