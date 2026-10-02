# -*- coding: utf-8 -*-
"""`_audit/indicator_audit/make_fixtures.py` — fixtureِ کوچکِ واقعی برایِ گاردها.

گاردِ `dev/indicator_math_v1074.py` باید بی‌شبکه و بی‌market.dbِ واقعی بدود، ولی
«چند نمادِ واقعی» را هم ببیند. این اسکریپت از CSVهایِ منتشرشدۀ TSETMC (کشِ
`_audit/parity_event_csv`) ۶ نماد × ۳۰۰ کندلِ آخر را به `fixtures_ohlcv.json`
می‌نویسد؛ همان فایل درِ گیت می‌ماند، پس گارد به کشِ محلیِ شما وابسته نیست.

اجرا (فقط وقتی خواستید fixture نو شود):
    python _audit/indicator_audit/make_fixtures.py [--bars 300] [--symbols a,b,...]
"""
import argparse
import csv
import glob
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import candle_contract as CC     # noqa: E402

DEFAULT = ["فولاد", "پارس", "وبملت", "شپنا", "كگل", "فاراك"]
COLS = ("time", "open", "high", "low", "close", "last", "volume", "value")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=300)
    ap.add_argument("--symbols", default=",".join(DEFAULT))
    ap.add_argument("--out", default=os.path.join(HERE, "fixtures_ohlcv.json"))
    args = ap.parse_args()
    want = [s for s in args.symbols.split(",") if s]
    conn = sqlite3.connect(os.path.join(ROOT, "market.db"), timeout=30)
    try:
        code_of = {row[0]: row[1] for row in
                   conn.execute("SELECT ins_code, l_val18 FROM instruments")}
    finally:
        conn.close()
    by_sym = {}
    for path in glob.glob(os.path.join(ROOT, "_audit", "parity_event_csv", "raw_*.txt")):
        code = os.path.basename(path)[4:-4]
        sym = code_of.get(code)
        if sym not in want or sym in by_sym:
            continue
        with open(path, encoding="utf-8", errors="replace", newline="") as fh:
            rd = csv.reader(fh)
            next(rd, None)
            bars = [b for b in (CC.from_csv_row(sym, f) for f in rd) if b]
        bars.sort(key=lambda b: b["time"])
        if len(bars) >= args.bars:
            by_sym[sym] = bars[-args.bars:]
    missing = [s for s in want if s not in by_sym]
    if missing:
        raise SystemExit("CSV کش‌شده نیست برای: %s (باید دستی از منبع گرفته شود)"
                         % ", ".join(missing))
    out = {sym: {"src": "tsetmc:GetClosingPriceDailyListCSV",
                 **{k: [b.get(k) for b in bars] for k in COLS}}
           for sym, bars in by_sym.items()}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=0, sort_keys=True)
    print("fixture:", {s: len(v["close"]) for s, v in out.items()}, "→", args.out)


if __name__ == "__main__":
    main()
