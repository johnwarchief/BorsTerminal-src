# -*- coding: utf-8 -*-
"""
tools/rebuild_e2e_probe.py — زمانِ واقعیِ یک «بازسازیِ کاملِ تابلو» از خودِ
تابعِ `_build_market_response`، رویِ یک *کپی* از market.db.

چرا کپی: این مسیر دیتابیس را نوشتن می‌کد (کش، جدول‌هایِ موقت) و بانکِ نصبی
در حالِ اجراست. عددی که رویِ کپی دربیاید برایِ مقایسهٔ «قبل/بعد» کافی است و
هیچ دادهٔ کاربری را دست نمی‌زند.

    python tools/rebuild_e2e_probe.py --db "<copy-of-market.db>" --runs 3
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import statistics
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)


class FakeRequest:
    def __init__(self):
        self.headers = {}
        self.query_params = {}


class NoCloseConn(sqlite3.Connection):
    """`_build_market_response` درِ پایانِ خود conn.close() را صدا می‌زند، درحالی‌که
    اتصالِ واقعیِ برنامه (get_db) مشترک است و بسته نمی‌شود. این کپیِ سنجش هم باید
    مشترک بماند، وگرنه ساختِ دوم رویِ اتصالِ بسته می‌شکند و عددِ «دوم و سوم»
    هرگز ثبت نمی‌شود."""

    def close(self):  # noqa: D102 - عمداً بی‌عمل
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()
    db = os.path.abspath(args.db)
    if not os.path.exists(db):
        raise SystemExit(f"no such file: {db} (this tool measures a COPY)")

    import api.market as mk

    holder = {}
    mk.get_db = lambda: holder["c"]
    holder["c"] = sqlite3.connect(db, check_same_thread=False, factory=NoCloseConn)
    holder["c"].execute("PRAGMA cache_size=-65536")

    times = []
    sizes = []
    for i in range(args.runs):
        t0 = time.perf_counter()
        out = mk._build_market_response(FakeRequest())
        dt = time.perf_counter() - t0
        times.append(dt)
        body = getattr(out, "body", None)
        sizes.append(len(body) if isinstance(body, (bytes, str)) else -1)
        print(f"build {i + 1}: {dt:.3f}s  body={sizes[-1]} bytes")

    med = statistics.median(times)
    print(f"[e2e] cold={times[0]:.3f}s  median={med:.3f}s  all={['%.3f' % t for t in times]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
