# -*- coding: utf-8 -*-
"""`_audit/indicator_audit/make_dataset.py` — مجموعۀ دادهٔ سنجشِ اندیکاتورها (آفلاین).

منبع: CSVهایِ منتشرشدۀ TSETMC که در دورۀ Reference Parity درِ
`_audit/parity_event_csv/raw_<ins_code>.txt` کش شده‌اند (بدونِ شبکه، بدونِ ADB).
نگاشتِ ستون‌ها از همان `candle_contract.from_csv_row` می‌گذرد که محصول مصرف می‌کند
(FIRST/HIGH/LOW/CLOSE/VALUE/VOL/OPENِ پایه/LAST)، پس سنجش رویِ همان OHLC+LAST
انجام می‌شود که درِ چارت می‌نشیند.

اجرا:  python _audit/indicator_audit/make_dataset.py [--min-bars 300]
خروجی: `_audit/indicator_audit/candles.json` (reproducible، درِ گیت نیست)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-bars", type=int, default=300)
    ap.add_argument("--out", default=os.path.join(HERE, "candles.json"))
    args = ap.parse_args()
    conn = sqlite3.connect(os.path.join(ROOT, "market.db"), timeout=30)
    try:
        out = {}
        for path in sorted(glob.glob(os.path.join(ROOT, "_audit", "parity_event_csv", "raw_*.txt"))):
            code = os.path.basename(path)[4:-4]
            row = conn.execute("SELECT l_val18 FROM instruments WHERE ins_code=?", (code,)).fetchone()
            sym = row[0] if row else code
            with open(path, encoding="utf-8", errors="replace", newline="") as fh:
                rd = csv.reader(fh)
                next(rd, None)                       # سرستون
                bars = [b for b in (CC.from_csv_row(sym, f) for f in rd) if b]
            bars.sort(key=lambda b: b["time"])
            if len(bars) < args.min_bars:
                print("  skip %-10s %d bars" % (sym, len(bars)))
                continue
            out[sym] = {k: [b.get(k) for b in bars]
                        for k in ("time", "open", "high", "low", "close", "last", "volume", "value")}
            print("  %-10s %5d bars  %s → %s" % (sym, len(bars), bars[0]["time"], bars[-1]["time"]))
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False)
        print("dataset:", len(out), "symbols →", args.out)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
