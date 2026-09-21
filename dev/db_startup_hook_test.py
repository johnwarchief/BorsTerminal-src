#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تستِ هوکِ استارتاپِ مهاجرت (dev-only) — اثبات می‌کند که مسیرِ استارتاپ
app._startup_sync_market اسکیما را قبل از هر کوئریِ fts_engine مهاجرت می‌دهد.

روی یک کپی از market.db اجرا می‌شود که هنوز ستون‌های FTS v2.2 را ندارد.
"""
import os
import sqlite3
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, _ROOT)

import codal_fetcher as cf  # noqa: E402


def _has_col(conn, table, col):
    return col in [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def _has_table(conn, t):
    return t in [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else "_startup_hook_test.db"
    # مسیر را قبل از chdir به مطلق تبدیل کن (آرگومان ممکن است نسبت به cwdِ
    # فراخواننده باشد، نه نسبت به ریشهٔ ریپو).
    db = os.path.abspath(db)
    if not os.path.exists(db):
        print(f"[FAIL] db not found: {db}")
        return 2
    # حالا که مسیرها مطلق‌اند، cwd را به ریشهٔ ریپو می‌بریم تا import app
    # و مسیرهای نسبیِ پروژه درست کار کنند.
    os.chdir(_ROOT)
    cf.DB_PATH = db

    # bors_config.DB_PATH هم باید روی db تست باشد، وگرنه threadهای استارتاپ
    # (market sync / screener warm) از DB واقعی استفاده می‌کنند.
    import bors_config
    bors_config.DB_PATH = db

    conn = sqlite3.connect(cf.DB_PATH)
    pre_unit = _has_col(conn, "financial_statements", "unit_norm")
    pre_vol = _has_col(conn, "monthly_sales", "monthly_volume")
    pre_fts = _has_table(conn, "fts_results")
    conn.close()
    print(f"[.. ] pre-hook:  unit_norm={pre_unit}  monthly_volume={pre_vol}  fts_results={pre_fts}")
    if pre_unit or pre_vol or pre_fts:
        print("[WARN] test db already migrated; re-extract a pristine copy for a real test")

    # هوکِ واقعیِ استارتاپ
    import app  # noqa: PLC0415
    app._startup_sync_market()

    conn = sqlite3.connect(cf.DB_PATH)
    post_unit = _has_col(conn, "financial_statements", "unit_norm")
    post_ms = _has_col(conn, "monthly_sales", "monthly_volume") and \
        _has_col(conn, "monthly_sales", "volume_unit")
    post_fts = _has_table(conn, "fts_results")
    post_ss = _has_table(conn, "symbol_sectors")
    post_mcs = _has_table(conn, "market_cap_snapshots")
    integ = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()

    print(f"[OK ] post-hook: unit_norm={post_unit} monthly_volume/volume_unit={post_ms}")
    print(f"[OK ] post-hook tables: fts_results={post_fts} symbol_sectors={post_ss} "
          f"market_cap_snapshots={post_mcs}")
    print(f"[OK ] integrity_check = {integ}")

    if not (post_unit and post_ms and post_fts and post_ss and post_mcs and integ == "ok"):
        print("[FAIL] startup hook did not fully migrate the schema")
        return 1
    print("[DONE] startup hook migrates the schema before any engine query")
    return 0


if __name__ == "__main__":
    sys.exit(main())
