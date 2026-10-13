# -*- coding: utf-8 -*-
"""خروجیِ `bulk_scan` را روی یکِ ریشۀ کدِ مشخص به JSON می‌ریزد (بدونِ هیچ داوری).

این فایل **بینِ نسخه‌ها خنثی** است: فقط ستون‌هایی را برمی‌دارد که درِ هر دو
نسخۀ قدیم (`5c97b5c`) و جدید همینِ کلیدها را دارند. بی‌این قید، مقایسۀ
«پیش/پس» معنایش را از دست می‌رفت: پیش‌ازین «پیش» با خاموش‌کردنِ یکِ قاعده در
کدِ امروز ساخته می‌شد، پس هر تغییری که آن قاعده را نمی‌لمید (لایۀ هویت، نردبانِ
P-2، خوانندۀ EPS) درِ آمارِ منشأ ناپدید می‌شد یا به قاعدۀ اشتباه نسبت می‌شد.

usage:
  PYTHONIOENCODING=utf-8 python tools/codal_bulk_dump.py --root . --out new.json
  PYTHONIOENCODING=utf-8 python tools/codal_bulk_dump.py --root /tmp/old --out old.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

# ستون‌های مشترکِ دو نسخه — هر چیزِ تازه‌تر (ردپایِ مرجع، per-index need) عمداً
# بیرونِ این فهرست است تا ابزارِ مقایسه هیچ‌وقت «پیش» را از کدِ «پس» نسازد.
COLS = ("symbol", "symbol_norm", "sector_name", "score", "primary_score",
        "i1_pass", "i2_pass", "i3_pass", "i4_pass", "i5_pass",
        "gross_margin", "rev_growth", "sales_to_mcap", "profit_potential_pct",
        "annual_sales_bt", "annualize_months", "eps_series", "eps_last",
        "mcap", "excluded", "exclusion_reasons", "applicable", "m141")


def dump(root: str, db: str) -> dict:
    sys.path.insert(0, os.path.abspath(root))
    import fts_engine as FE
    conn = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
    conn.row_factory = sqlite3.Row
    try:
        FE.register_sql(conn)
    except Exception:
        pass
    rows = FE.bulk_scan(conn, cfg=None)
    conn.close()
    out = {}
    for r in rows:
        rec = {}
        for c in COLS:
            v = r.get(c)
            rec[c] = v
        out[str(r.get("symbol") or "")] = rec
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="ریشۀ کدی که import می‌شود")
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    db = a.db if os.path.isabs(a.db) else os.path.join(os.path.abspath(a.root), a.db)
    data = dump(a.root, db)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"root": os.path.abspath(a.root), "db": db, "rows": data},
                  fh, ensure_ascii=False, indent=1, sort_keys=True)
    print("rows=%d root=%s out=%s" % (len(data), os.path.abspath(a.root), a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
