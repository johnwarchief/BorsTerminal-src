# -*- coding: utf-8 -*-
"""tools/ctv_coverage_stepper.py — پوششِ client_type_value را قدم‌به‌قدم اندازه می‌گیرد

چرا: رأیِ سندِ پوشش («بودجه را بالا نبر، اول اندازه بگیر») و رفعِ گیتِ نشستِ باز
درِ ۱٫۰٫۸۵. عددهایِ پیشین (۲۰۰۰ ردیف / ۸۳۶ نماد / ۴ نشست، پوششِ ۲۵٪ از هدفِ
نشستِ ۲۰۲۶۱۰۱۰) رویِ بانکِ مشترکِ همین ماشین است که یک دیدبانِ دیگر همزمان درِ
آن می‌نویسد. این اسکریپت رویِ یک کپیِ جدا از `market.db` همان `refresh_client_type_values`
تولیدی را n بار صدا می‌زند — دقیقاً همان کاری که دیدبان هر ۳۰ دقیقه می‌کند —
و بعد از هر قدم پوشش را چاپ می‌کند. بانکِ اصلی دست نمی‌خورد.

`market_state_touch` درِ اینجا بی‌کار می‌شود: لایۀ داغِ shared به بانکِ واقعیِ
همین ماشین وصل است و ما نباید به دیدبانِ مالک خبرِ جعلی بفرستیم.

فرمان:  python tools/ctv_coverage_stepper.py --steps 3 [--db _audit/ctv_lab/market.db]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "dev"))

import test_tsetmc as T  # noqa: E402
from tsetmc_native_coverage_report import measure  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(REPO, "_audit", "ctv_lab", "market.db"))
    ap.add_argument("--steps", type=int, default=3)
    ap.add_argument("--out", default=os.path.join(REPO, "_audit", "ctv_stepper.json"))
    a = ap.parse_args()

    if not os.path.exists(a.db):
        print(f"[ERR] کپیِ بانک پیدا نشد: {a.db}")
        return 2
    # دیدبانِ مالک را بیدار نکن: لایۀ داغ فقط برایِ بانکِ واقعی معنی دارد.
    T.market_state_touch = lambda: None  # noqa: E731

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    T.ensure_client_type_value_schema(conn)
    conn.commit()

    report = {"db": a.db, "steps": [], "before": measure(conn)}
    print("پیش ازِ هر قدم: " + json.dumps(report["before"], ensure_ascii=False, default=str))
    for i in range(a.steps):
        t0 = time.monotonic()
        try:
            r = T.refresh_client_type_values(conn, force=True)
        except Exception as e:  # noqa: BLE001
            r = {"error": f"{type(e).__name__}: {e}"}
        wall = round(time.monotonic() - t0, 1)
        cov = measure(conn)
        step = {"n": i + 1, "run": r, "wall_s": wall,
                "rows_all": cov["rows_all"], "symbols_all": cov["symbols_all"],
                "sessions": cov["sessions"], "day": cov["day"],
                "day_rows": cov["rows_day"], "day_target": cov["universe"],
                "pct_of_target": cov["pct_of_target"]}
        report["steps"].append(step)
        print(f"قدم {i+1}: نوشت={r.get('written')} تلاش={r.get('attempted')} "
              f"خطا={r.get('errors')} بی‌پاسخ={r.get('no_payload')} "
              f"بسته‌شده={r.get('aborted')} زمانِ اجرا={r.get('ran_s')}s "
              f"دیواری={wall}s | ردیفِ کل={cov['rows_all']} "
              f"نشستِ {cov['day']}: {cov['rows_day']}/{cov['universe']} "
              f"= {cov['pct_of_target']}٪")
        conn.commit()
    report["after"] = measure(conn)
    conn.close()
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1, default=str)
    print(f"گزارش: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
