# _audit/ra365_candle_parity.py -- سنجشِ کندل‌هایِ روزانۀِ ما با کندل‌هایِ مرجع (ره‌آورد ۳۶۵، تعدیلِ عملکردی)
# مرجع: _audit/ra365_ref_bars.json (خروجیِ _audit/ra365_job_bars2.js از API خودِ ره‌آورد)
# محصول: market.db -> price_history(symbol,date,open,high,low,close,volume,last,src)
# خروجی: _audit/RA365-CANDLE-PARITY-2026-10-12.csv + چکیدۀِ ترمینال
# فقط خواندن. هیچ داوریِ رفعی اینجا نیست؛ هدفِ این فایل «اندازه‌گیریِ اختلاف» است.
import json
import sqlite3
import csv
import sys
import io
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

RAW = "_audit/ra365_ref_bars.json"
OUT = "_audit/RA365-CANDLE-PARITY-2026-10-12.csv"
OUT_D = "_audit/RA365-CANDLE-DIVERGE-2026-10-12.csv"
TEHRAN = timezone(timedelta(hours=3, minutes=30))  # +03:30 (Iran Standard)


def bar_date(utc_str):
    """برچسبِ جلسۀِ تهرانیِ یک کندل؛ utc ممکن است با 'Z' یا با آفستِ +04:30 آمده باشد."""
    dt = datetime.fromisoformat(utc_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TEHRAN).date().isoformat()


def main():
    raw = json.load(open(RAW, encoding="utf-8"))
    con = sqlite3.connect("market.db")
    cur = con.cursor()

    series = {}
    for key, obj in raw["bars"].items():
        sym, suf, res = key.split("|")
        if res != "D" or suf != "type7":
            continue
        series[sym] = {bar_date(b["utc"]): b for b in obj["bars"]}

    rows = []
    diverge = []
    print(f"{'نماد':8s} {'تعدادِ مرجع':>12s} {'تعدادِ ما':>10s} {'سر به سر O':>10s} {'سر به سر H':>10s} {'C=close':>8s} {'C=last':>7s} {'کمبودِ ما':>9s} {'اضافۀِ ما':>9s}")
    for sym, ref in series.items():
        cur.execute(
            "select date, open, high, low, close, volume, last, src from price_history where symbol=? and date>=?",
            (sym, min(ref)),
        )
        ours = {r[0]: r for r in cur.fetchall()}
        ref_dates, our_dates = set(ref), set(ours)
        common = sorted(ref_dates & our_dates)
        stats = dict(n_ohc=0, n_h=0, n_l=0, n_o=0, c_close=0, c_last=0, c_none=0, n=0, vol=0)
        for d in common:
            rb, ob = ref[d], ours[d]
            stats["n"] += 1
            if round(rb["o"]) == round(ob[1]):
                stats["n_o"] += 1
            if round(rb["h"]) == round(ob[2]):
                stats["n_h"] += 1
            if round(rb["l"]) == round(ob[3]):
                stats["n_l"] += 1
            if round(rb["c"]) == round(ob[4]):
                stats["c_close"] += 1
            if ob[6] is not None and round(rb["c"]) == round(ob[6]):
                stats["c_last"] += 1
            if round(rb["c"]) != round(ob[4]) and (ob[6] is None or round(rb["c"]) != round(ob[6])):
                stats["c_none"] += 1
            if ob[5] and abs(rb["v"] - ob[5]) < 1:
                stats["vol"] += 1
            if round(rb["o"]) == round(ob[1]) and round(rb["h"]) == round(ob[2]) and round(rb["l"]) == round(ob[3]) and round(rb["c"]) == round(ob[4]):
                stats["n_ohc"] += 1
        missing = sorted(ref_dates - our_dates)
        extra = sorted(our_dates - ref_dates)
        print(
            f"{sym:8s} {len(ref):12d} {len(ours):10d} {stats['n_o']:>7d}/{stats['n']:<3d} {stats['n_h']:>7d}/{stats['n']:<3d}"
            f" {stats['c_close']:>5d}/{stats['n']:<3d} {stats['c_last']:>4d}/{stats['n']:<3d} {len(missing):>9d} {len(extra):>9d}"
        )
        rows.append({
            "symbol": sym,
            "ref_bars": len(ref),
            "our_bars": len(ours),
            "common": stats["n"],
            "open_match": stats["n_o"],
            "high_match": stats["n_h"],
            "low_match": stats["n_l"],
            "close_eq_our_close": stats["c_close"],
            "close_eq_our_last": stats["c_last"],
            "close_matches_neither": stats["c_none"],
            "volume_match": stats["vol"],
            "full_ohlc_match": stats["n_ohc"],
            "ref_dates_absent_from_our_db": "|".join(missing),
            "our_dates_absent_from_ref": "|".join(extra),
        })
        # سطرهایِ اختلافِ close با جزئیات (برایِ گزارش)
        for d in common:
            rb, ob = ref[d], ours[d]
            if round(rb["c"]) != round(ob[4]):
                diverge.append({
                    "symbol": sym, "date": d,
                    "ref_o": rb["o"], "ref_h": rb["h"], "ref_l": rb["l"], "ref_c": rb["c"], "ref_v": rb["v"],
                    "our_o": ob[1], "our_h": ob[2], "our_l": ob[3], "our_c": ob[4], "our_v": ob[5], "our_last": ob[6], "our_src": ob[7],
                    "ref_c_equals_our_last": "yes" if (ob[6] is not None and round(rb["c"]) == round(ob[6])) else "no",
                })

    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=sorted({k for r in rows for k in r}))
        w.writeheader()
        w.writerows(rows)
    with open(OUT_D, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=sorted({k for r in diverge for k in r}))
        w.writeheader()
        w.writerows(diverge)
    print("CSV ->", OUT, "rows", len(rows))
    print("CSV ->", OUT_D, "rows", len(diverge))


if __name__ == "__main__":
    main()
