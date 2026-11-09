#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""phase45_chart_oracle.py — خروجیِ مرجعِ پایتونِ get_chart_db برایِ ۳۰ نماد.

رویِ یک **کپی** از بانکِ آزمایشگاهی اجرا می‌شود؛ بانکِ اصلی هرگز باز نمی‌شود.
CDN و حلقه‌هایِ شبکه خاموش‌اند، پس همان مسیرِ آفلاینِ get_chart_db سنجیده می‌شود.

خروجی: JSON {symbol: payload} — شاملِ candles/adjustEvents/capability/coverage.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-dir", required=True)
    ap.add_argument("--symbols", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="p45-oracle-")
    for name in ("market.db", "user.db"):
        src = os.path.join(args.db_dir, name)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(tmp, name))
    os.environ["BORS_DATA_DIR"] = tmp
    os.environ["BORS_CHART_CDN"] = "off"
    os.environ["BORS_NO_FETCH_LOOPS"] = "1"
    os.environ.setdefault("BORS_CODAL_OFFLINE", "1")
    os.environ.setdefault("BORS_CODAL_AUTO", "0")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    with open(args.symbols, encoding="utf-8-sig") as fh:
        symbols = [r["symbol"] for r in csv.DictReader(fh)]

    import api.chart as ch

    out = {}
    for sym in symbols:
        out[sym] = ch.get_chart_db(sym)
        print(sym, out[sym].get("status"), out[sym].get("count"), flush=True)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("written", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
