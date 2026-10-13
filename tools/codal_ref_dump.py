# -*- coding: utf-8 -*-
"""ردیفِ مرجعِ هر نماد را از یکِ ریشۀ کد به JSON می‌ریزد (خنثیِ نسخه‌ای).

همراه `codal_bulk_dump.py`: «پیش» و «پس» از خودِ کدِ آن دور می‌آیند، نه از
خاموش‌کردنِ قاعده درِ کدِ امروز. این‌جا همان قاعده برایِ **انتخابِ ردیف** است:
مرجعِ شاخص‌های ۳ و ۴ در `5c97b5c` با مرجعِ امروز مقایسه می‌شود، پس پاسخِ سؤالِ
«گزارشِ منتخبِ پیش از اصلاح چه بود؟» از ردیفِ واقعیِ همان کد خوانده می‌شود.

usage:
  PYTHONIOENCODING=utf-8 python tools/codal_ref_dump.py --root /tmp/old --out old.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

COLS = ("tracing_no", "symbol", "company_name", "title", "report_kind",
        "period_months", "period_end", "publish_date", "revenue", "gross_profit",
        "operating_profit", "net_profit", "basic_eps", "unit", "fiscal_year",
        "audited", "consolidated", "other_entity", "conflicts", "months_source")


def dump(root: str, db: str) -> dict:
    sys.path.insert(0, os.path.abspath(root))
    import fts_engine as FE
    conn = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
    conn.row_factory = sqlite3.Row
    try:
        FE.register_sql(conn)
    except Exception:
        pass
    syms = sorted({str(r[0]) for r in conn.execute(
        "SELECT DISTINCT symbol FROM financial_statements") if r[0]})
    out = {}
    for s in syms:
        rec = {}
        try:
            ref = FE.reference_annual(conn, s)
        except Exception as e:
            ref = None
            rec["error"] = str(e)[:120]
        rec["ref"] = {c: (ref or {}).get(c) for c in COLS} if ref else None
        mr = getattr(FE, "margin_reference", None)
        if mr is not None and ref:
            try:
                m = mr(conn, s, ref)
                rec["margin_ref"] = {c: (m or {}).get(c) for c in COLS} if m else None
            except Exception as e:
                rec["margin_ref_error"] = str(e)[:120]
        out[s] = rec
    conn.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    db = a.db if os.path.isabs(a.db) else os.path.join(os.path.abspath(a.root), a.db)
    data = dump(a.root, db)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"root": os.path.abspath(a.root), "db": db, "rows": data},
                  fh, ensure_ascii=False, indent=1, sort_keys=True)
    print("refs=%d root=%s out=%s" % (len(data), os.path.abspath(a.root), a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
