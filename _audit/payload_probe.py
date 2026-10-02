# -*- coding: utf-8 -*-
"""پروبِ حجمِ بدنهٔ /api/market — چهقدر از ۶٫۹۵ مگابایت واقعاً خوانده می‌شود؟

رویِ کپیِ بانکِ کاری (_audit/live_market.db) اجرا می‌شود؛ بانکِ اصلی دست
نمی‌خورد. سه چیز می‌سنجد:
  ۱) زمانِ هر مرحلۀ بازسازی (SQL / مشتقات / سریال‌سازی) — برایِ تصمیمِ «آیا
     لایۀ ایستا را در RAM نگه داریم یا نه».
  ۲) حجمِ بدنه با همان ۷۳ فیلد.
  ۳) حجمِ بدنه بی‌۲۵ فیلدی که فرانت‌اند هرگز نمی‌خواند، و بی‌کلیدهای null.
"""
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

COPY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_market.db")
assert os.path.exists(COPY), COPY

# بیست‌وپنج فیلدی که `Explore` در frontend/src بی‌ارجاع یافت (به‌جز schema).
UNUSED = ["eps", "price_max", "price_min", "p_max", "p_min", "buy_n_vol",
          "sell_n_vol", "buy_q_vol", "buy_q_val", "buy_q_cnt", "buy_q1_px",
          "sell_q_vol", "sell_q_val", "sell_q_cnt", "sell_q1_vol", "sell_q1_px",
          "prev_day_vol", "tmax", "vol_trend", "sell_power_i", "suspicious_vol",
          "d_even", "resistance_59", "max30_high", "d1_vol", "dist_min30_pct",
          "month_avg_vol"]

import api.market as M                                  # noqa: E402

M.get_db = lambda: sqlite3.connect(COPY, timeout=120)   # read/write روی کپی


class Req:
    headers = {}


def stage_times():
    """زمانِ SQLِ تابلو، کوئریِ meta، مشتقاتِ pandas و سریال‌سازی."""
    conn = M.get_db()
    t0 = time.perf_counter()
    M.ensure_board_history(conn)
    t_hist = time.perf_counter() - t0
    # کوئریِ اصلیِ تابلو (همان متنِ داخلِ _build_market_response)
    import re
    src = open("api/market.py", encoding="utf-8").read()
    q = src.split('query = """', 1)[1].split('"""', 1)[0]
    import pandas as pd
    t0 = time.perf_counter()
    df = pd.read_sql_query(q, conn)
    t_sql = time.perf_counter() - t0
    t0 = time.perf_counter()
    conn.execute("SELECT d_even, MAX(h_even), MAX(fetched_at) FROM market_watch "
                 "WHERE d_even = (SELECT MAX(d_even) FROM market_watch)").fetchone()
    t_meta = time.perf_counter() - t0
    conn.close()
    return t_hist, t_sql, t_meta, df


def main():
    print(f"copy: {COPY}  size={os.path.getsize(COPY)/1e6:.1f}MB")
    t_hist, t_sql, t_meta, df = stage_times()
    print(f"ensure_board_history={t_hist*1000:8.1f}ms  board_sql={t_sql*1000:8.1f}ms  "
          f"meta_sql={t_meta*1000:8.1f}ms  rows={len(df)} cols={len(df.columns)}")

    # بازسازیِ کاملِ فعلی (همه‌چیز داخلِ _build_market_response)
    best = []
    for _ in range(3):
        t0 = time.perf_counter()
        resp = M._build_market_response(Req())
        best.append(time.perf_counter() - t0)
    body = resp.body if isinstance(resp.body, bytes) else resp.body.encode()
    print(f"full build: min={min(best)*1000:.0f}ms  body={len(body)/1e6:.2f}MB  "
          f"rows_in_body={len(json.loads(body)['data'])}")

    d = json.loads(body)
    recs = d["data"]
    n_fields = sum(len(r) for r in recs)
    null_keys = sum(1 for r in recs for v in r.values() if v is None)
    print(f"fields/row={n_fields/len(recs):.1f}  null_values={null_keys} "
          f"({100*null_keys/n_fields:.0f}% of all values)")

    variants = {}
    raw = json.dumps(d, ensure_ascii=False).encode()
    variants["as-is (json)"] = raw

    d2 = dict(d, data=[{k: v for k, v in r.items() if k not in UNUSED} for r in recs])
    variants["-unused fields"] = json.dumps(d2, ensure_ascii=False).encode()

    d3 = dict(d2, data=[{k: v for k, v in r.items() if v is not None} for r in d2["data"]])
    variants["-unused -nulls"] = json.dumps(d3, ensure_ascii=False).encode()

    import orjson
    variants["-unused -nulls (orjson)"] = orjson.dumps(d3)
    variants["as-is (orjson)"] = orjson.dumps(d)

    base = len(body)
    for name, b in variants.items():
        import gzip
        print(f"  {name:28s} {len(b)/1e6:6.2f}MB  gzip={len(gzip.compress(b, 6))/1e3:7.0f}KB  "
              f"({100*len(b)/base:4.0f}% of current {base/1e6:.2f}MB)")

    # یک ردیفِ نمونه برایِ دیدنِ شکلِ واقعیِ داده
    print("\nsample row keys:", sorted(recs[0].keys())[:8], "...")
    print(f"orjson dumps time full={timeit(lambda: orjson.dumps(d))[0]*1000:.1f}ms  "
          f"slim={timeit(lambda: orjson.dumps(d3))[0]*1000:.1f}ms  "
          f"to_dict={timeit(lambda: df.to_dict('records'))[0]*1000:.1f}ms")


def timeit(fn, n=3):
    best = (1e9, None)
    for _ in range(n):
        t0 = time.perf_counter()
        r = fn()
        dt = time.perf_counter() - t0
        if dt < best[0]:
            best = (dt, r)
    return best


if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
