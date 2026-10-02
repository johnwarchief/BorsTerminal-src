# -*- coding: utf-8 -*-
"""_audit/bench_live_market.py — عددِ قبل/بعد برایِ کارِ #73 (بخشِ Live Market)

رویِ کپیِ بانکِ کاری (`_audit/live_market.db`) و با *همان* کدِ محصول:

  قبل = هر بازسازی کوئریِ تابلو + کوئریِ امضا را از SQLite می‌خواند و بدنۀ
        ۷۳-فیلدی با null می‌فرستد، و تیک هر سیکل کلِ ردیف‌ها را می‌نوشت.
  بعد = قابِ ایستا در RAM + دلتایِ حالتِ داغ + بدنه بی‌فیلدهایِ بی‌خواننده و
        بی‌null + نوشتنِ فقط-تغییریافته + endpoint دلتا.

هیچ عددی اینجا حدس نیست: زمان با perf_counter، حجم با len(body)، نوشتن‌ها با
شمارندۀ خودِ market_state.
"""
import gzip
import json
import os
import sqlite3
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
COPY = os.path.join(REPO, "_audit", "live_market.db")
assert os.path.exists(COPY), "copy first: cp market.db _audit/live_market.db"

import api.market as M                    # noqa: E402
import market_state as MS                 # noqa: E402
import test_tsetmc as T                   # noqa: E402


class Req:
    headers = {}


def db():
    return sqlite3.connect(COPY, timeout=120)


M.get_db = db
MS.reset()
M._reset_board_cache()
M._HIST_CACHE_KEY = (None,)

# ── ۱) مسیرِ «قبل»: اولین بازسازی همیشه از SQLite ───────────────────────
t0 = time.perf_counter()
r1 = M._build_market_response(Req())
t_sql_build = time.perf_counter() - t0
body_before = len(r1.body)

# ── ۲) حالتِ داغ: قاب کشیده شد؛ تیکِ مصنوعی ۲۰۰ نماد را تکان می‌دهد ──────
conn = db()
codes = [row[0] for row in conn.execute(
    "SELECT ins_code FROM market_watch WHERE d_even = (SELECT MAX(d_even) FROM market_watch)"
    " LIMIT 200")]
mw_cols = list(T.MW_COLS)
i_pcl, i_vol = mw_cols.index("p_closing"), mw_cols.index("q_tot_tran")


def fake_tick(shift=1.0):
    """همان مسیری که tick_live می‌رود، بی‌شبکه: ۲۰۰ ردیفِ تغییریافته."""
    rows = []
    for c in codes:
        r = list(MS.rows_for([c]).get(c) or _db_row(c))
        r[i_pcl] = (r[i_pcl] or 0) + shift
        r[i_vol] = (r[i_vol] or 0) + 10
        rows.append(tuple(r))
    changed = MS.diff(rows)
    n = MS.commit(changed)
    MS.note_cycle(len(rows), n, 0.05)
    return len(changed)


def _db_row(code):
    row = conn.execute("SELECT " + ", ".join(mw_cols) + " FROM market_watch"
                       " WHERE ins_code=?", (code,)).fetchone()
    return list(row)


# قابِ ایستا هنوز روزِ نشستِ RAM را ندیده ⇒ یک بازسازیِ SQLite‌ای دیگر مجاز است
wrote = fake_tick()
M._build_market_response(Req())           # steady-state: قاب از این به بعد کش است
t0 = time.perf_counter()
r2 = M._build_market_response(Req())
t_ram_build = time.perf_counter() - t0
body_after = len(r2.body)

# نوشتن‌هایِ دیسک درِ یک سیکل — قبل: کلِ تابلو، بعد: دِلتا
all_rows = conn.execute("SELECT COUNT(*) FROM market_watch WHERE d_even ="
                        " (SELECT MAX(d_even) FROM market_watch)").fetchone()[0]
writes_before = all_rows * 2              # market_watch + daily_prices
writes_after = wrote * 2

# ── ۳) دلتایِ HTTP ────────────────────────────────────────────────────────
M.warm_market_cache()
rev = MS.revision()
wrote2 = fake_tick(2.0)
M.warm_market_cache()
d = json.loads(M.get_market_delta(since=rev).body.decode())
delta_bytes = len(M.get_market_delta(since=rev).body)
unchanged = len(M.get_market_delta(since=MS.revision()).body)

after_rows = json.loads(r2.body.decode())["data"]
print(json.dumps({
    "rows_in_board": all_rows,
    "build_ms_sql_path": round(t_sql_build * 1000, 1),
    "build_ms_hot_path": round(t_ram_build * 1000, 1),
    "body_before_bytes": body_before,
    "body_after_bytes": body_after,
    "body_before_gzip": len(gzip.compress(r1.body, 6)),
    "body_after_gzip": len(gzip.compress(r2.body, 6)),
    "tick_writes_before": writes_before,
    "tick_writes_after": writes_after,
    "delta_status": d["status"],
    "delta_rows": len(d.get("rows", [])),
    "delta_bytes": delta_bytes,
    "delta_bytes_gzip": len(gzip.compress(
        M.get_market_delta(since=rev).body, 6)),
    "unchanged_bytes": unchanged,
    "fields_per_row_after": max(len(r) for r in after_rows),
    "hot_stats": MS.stats(),
}, ensure_ascii=False, indent=1))
