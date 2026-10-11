# _audit/ra365_confirm_claims.py -- سه ادعایِ مرحلۀِ ۳ که درِ گزارش می‌آیند، دوباره اندازه‌گیری می‌شوند
#   ۱) high/low مرجع باریک‌تر است: آیا مرجع فقط جلسۀ اصلی را می‌بیند؟ (آزمونِ نیابتی: آیا
#      highِ مرجع با یکی از ستون‌هایِ روزِ ما می‌خورد، و آیا فقط روزهایی که FIRST<HIGH است پرچم دارد)
#   ۲) مسیرِ دیتابیس: ستونِ open در چند درصد سطرهایش با FIRSTِ همان روز نمی‌خورد
#   ۳) مسیرِ دیتابیس: چندسشن‌هایِ مرجع از ۲۰۲۴-۰۱-۰۱ در بانک نیست
# هیچ‌کدام از این‌ها با تغییرِ منطقِ داده سنجیده نمی‌شوند؛ فقط خواندن.
import json
import io
import sys
import sqlite3
import glob
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = "C:/Users/Johnkallnaya/Desktop/Borsterminal/BorsTerminal-src"
R = json.load(open(f"{ROOT}/_audit/ra365_ref_bars.json", encoding="utf-8"))
P = json.load(open(f"{ROOT}/_audit/ra365_product_bars.json", encoding="utf-8"))
CORPUS = json.load(open(f"{ROOT}/_audit/ra365_corpus.json", encoding="utf-8"))


def tehran_date(b):
    s = str(b["utc"]).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=3, minutes=30))).date().isoformat()


def ref_bars(sym, suf="type0"):
    e = R["bars"].get(f"{sym}|{suf}|D")
    if not e or e.get("status") != 200:
        return {}
    return {tehran_date(b): b for b in e["bars"]}


print("۱) high/low")
n_hi_short = n_lo_long = n_hi_eq_first = n_hi_eq_last = n_hi_eq_close = 0
n_hi_eq_prevclose = n_lo_eq_first = n_lo_eq_last = n_bad = n_common = 0
prev_raw = {}
for c in CORPUS:
    sym = c["sym"]
    rf = ref_bars(sym)
    cx = {k["time"]: k for k in P[sym]["live"]["candles"]}
    for d, r in sorted(rf.items()):
        p = cx.get(d)
        if not p or not r.get("h"):
            continue
        n_common += 1
        prev_raw[d] = prev_raw.get(d + "_prev")
        tol = max(r["h"] * 5e-4, 0.6)
        if abs(p["high"] - r["h"]) > tol:
            n_bad += 1
            if r["h"] < p["high"]:
                n_hi_short += 1
            if r["h"] and abs(r["h"] - p["open"]) <= tol:
                n_hi_eq_first += 1
            if r["h"] and abs(r["h"] - p["last"]) <= tol:
                n_hi_eq_last += 1
            if r["h"] and abs(r["h"] - p["close"]) <= tol:
                n_hi_eq_close += 1
        tol2 = max(r["l"] * 5e-4, 0.6)
        if r.get("l") and p["low"] and abs(p["low"] - r["l"]) > tol2:
            if r["l"] > p["low"]:
                n_lo_long += 1
            if abs(r["l"] - p["open"]) <= tol2:
                n_lo_eq_first += 1
            if abs(r["l"] - p["last"]) <= tol2:
                n_lo_eq_last += 1
print(f"  کندل‌هایِ مشترک (بدونِ تعدیل): {n_common}")
print(f"  highِ ما با مرجع نمی‌خورد: {n_bad}")
print(f"    از آن‌ها highِ مرجع کوتاه‌تر: {n_hi_short}  |  lowِ مرجع بلندتر (کم‌ترِ ما): {n_lo_long}")
print(f"    highِ مرجع == FIRSTِ ما: {n_hi_eq_first}   == LAST: {n_hi_eq_last}   == CLOSE: {n_hi_eq_close}")
print(f"    lowِ مرجع  == FIRSTِ ما: {n_lo_eq_first}   == LAST: {n_lo_eq_last}")

# آیا واگرایی فقط در روزهایی است که FIRST/HIGH فرق دارد؟ (نشانهٔ معاملۀ پیش‌جلسه)
n_hi_ne_first = 0
tot = 0
for c in CORPUS:
    sym = c["sym"]
    rf = ref_bars(sym)
    cx = {k["time"]: k for k in P[sym]["live"]["candles"]}
    for d, r in rf.items():
        p = cx.get(d)
        if not p or not r.get("h"):
            continue
        tot += 1
        if abs(p["open"] - p["high"]) > max(p["high"] * 5e-4, 0.6):
            n_hi_ne_first += 1
print(f"  روزهایی که FIRST<HIGH در دادۀِ ما: {n_hi_ne_first}/{tot}")

print("\n۲) و ۳) مسیرِ دیتابیس")
db = glob.glob(f"{ROOT}/market.db")[0]
con = sqlite3.connect(db)
n_open_wrong = n_rows = 0
missing_total = 0
missing_by_month = {}
syms_missing = []
for c in CORPUS:
    sym = c["sym"]
    dbr = {k["time"]: k for k in P[sym]["db"]["candles"]}
    rf = ref_bars(sym)
    miss = sorted(d for d in rf if d >= "2024-01-01" and d not in dbr)
    missing_total += len(miss)
    for m in miss:
        missing_by_month[m[:7]] = missing_by_month.get(m[:7], 0) + 1
    if miss:
        syms_missing.append((sym, len(miss)))
    cx = {k["time"]: k for k in P[sym]["live"]["candles"]}
    for d, row in dbr.items():
        p = cx.get(d)
        if not p or row.get("open") is None:
            continue
        n_rows += 1
        if abs(row["open"] - p["open"]) > max(p["open"] * 5e-4, 0.6):
            n_open_wrong += 1
print(f"  سطرهایِ دیتابیسِ مقایسه‌شده با FIRSTِ زنده: {n_rows}  ناهمخوانِ open: {n_open_wrong} "
      f"({100.0*n_open_wrong/max(1,n_rows):.1f}٪)")
print(f" سشن‌هایِ مرجع از ۲۰۲۴-۰۱-۰۱ که در بانک نیست: {missing_total}  "
      f"(میانگینِ هر نماد {missing_total/len(CORPUS):.1f})")
print("  بدترینِ نمادها:", ", ".join(f"{s}={n}" for s, n in sorted(syms_missing, key=lambda z: -z[1])[:8]))
print("  تفکیکِ ماهانه (۶ ماهِ آخر):", {k: missing_by_month[k] for k in sorted(missing_by_month)[-6:]})
last = [d for d in missing_by_month if d >= "2026-10"]
print(" در ۲۰۲۶-۱۰:", sum(missing_by_month.get(k, 0) for k in last))

print("\n  لنگرِ قیمتِ پایانی/آخرین در دیتابیس:")
n_last_none = n_tot = 0
for c in CORPUS:
    for k in P[c["sym"]]["db"]["candles"]:
        n_tot += 1
        if k.get("last") is None:
            n_last_none += 1
print(f"    سطرهایِ دیتابیس با last=None: {n_last_none}/{n_tot} ({100.0*n_last_none/n_tot:.1f}٪)")
con.close()
