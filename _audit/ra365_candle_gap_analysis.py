# _audit/ra365_candle_gap_analysis.py -- ریشه‌یابیِ دو اختلافِ باقی‌ماندۀِ کندل
# ۱) high/low: دربارۀِ ۵٪ از کندل‌ها با مرجع نمی‌خواند (درحالی که open/close/volume دقیق‌اند)
# ۲) پوشش: جلسۀِ ۲۰۲۶-۱۰-۱۰ و دیگر روزهایِ غایب درِ دیتابیسِ محلی در برابرِ مسارۀِ زنده و مرجع
# مرجع = ra365_ref_bars.json (type0 = بدونِ تعدیل) | محصول = ra365_product_bars.json
import json
import sys
import io
from collections import Counter
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
TEHRAN = timezone(timedelta(hours=3, minutes=30))
TOL = 0.0005


def tdate(u):
    dt = datetime.fromisoformat(u)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TEHRAN).date().isoformat()


ref = json.load(open("_audit/ra365_ref_bars.json", encoding="utf-8"))
prod = json.load(open("_audit/ra365_product_bars.json", encoding="utf-8"))
corpus = [c["sym"] for c in json.load(open("_audit/ra365_corpus.json", encoding="utf-8"))]

hi_dir = Counter()
lo_dir = Counter()
hi_mag = []
sample = []
flat_link = Counter()
weekday = Counter()
miss_live = Counter()
miss_db = Counter()
gap_dates = Counter()
d1010 = []
for sym in corpus:
    obj = ref["bars"].get(f"{sym}|type0|D")
    if not obj:
        continue
    R = {tdate(b["utc"]): b for b in obj["bars"] if tdate(b["utc"]) >= "2024-01-01"}
    rec = prod[sym]["live"]
    fac = {f["time"]: f["factor"] for f in (rec["factors"] or [])}
    L = {c["time"]: c for c in (rec["candles"] or []) if c["time"] >= "2024-01-01"}
    D = {c["time"]: c for c in (prod[sym]["db"]["candles"] or [])}
    miss_live[sym] = len(set(R) - set(L))
    miss_db[sym] = len(set(R) - set(D))
    for d in sorted(set(R) & set(L)):
        r, p = R[d], L[d]
        tol = max(abs(r["h"]) * TOL, 0.6)
        if abs(r["h"] - p["high"]) > tol:
            hi_dir["مرجع بلندتر" if r["h"] > p["high"] else "مرجع کوتاهتر"] += 1
            hi_mag.append(abs(r["h"] - p["high"]) / r["h"])
            if len(sample) < 14:
                sample.append((sym, d, r["o"], r["h"], r["l"], r["c"], p["open"], p["high"], p["low"], p.get("closing"), p.get("last"), p.get("basis")))
            weekday[datetime.fromisoformat(d).strftime("%A")] += 1
            flat_link["کندلِ ما تک‌قیمت" if p["high"] == p["low"] else "کندلِ ما بازه دارد"] += 1
        tol2 = max(abs(r["l"]) * TOL, 0.6)
        if abs(r["l"] - p["low"]) > tol2:
            lo_dir["مرجع بلندتر" if r["l"] > p["low"] else "مرجع کوتاهتر"] += 1
    if "2026-10-10" in R:
        d1010.append((sym, R["2026-10-10"]["o"], R["2026-10-10"]["c"],
                      "live" if "2026-10-10" in L else "-", "db" if "2026-10-10" in D else "-"))
    for d in sorted(set(R) - set(D)):
        gap_dates[d[:7]] += 1

print("=== ۱) high/low که با مرجع نمی‌خواند (بازوهایِ بی‌تعدیل، ۲۰۲۴ به بعد) ===")
print("تعدادِ اختلافِ high:", sum(hi_dir.values()), "| جهت:", dict(hi_dir))
print("تعدادِ اختلافِ low:", sum(lo_dir.values()), "| جهت:", dict(lo_dir))
if hi_mag:
    hi_mag.sort()
    print(f"اندازهٔ اختلافِ high  میانهِ={sum(hi_mag) / len(hi_mag) * 100:.3f}٪  "
          f"نمایان={hi_mag[len(hi_mag) // 2] * 100:.3f}٪  بیشینه={hi_mag[-1] * 100:.3f}٪")
print("پیوند با تک‌قیمتِ ما:", dict(flat_link))
print("پراکندگیِ روزهایِ هفتگی:", dict(weekday))
print("\nنمونۀِ اختلاف (نماد | روز | مرجع O H L C | محصول O H L closing last basis):")
for s in sample:
    print("  " + f"{s[0]:8s} {s[1]} | {s[2]:>9,.0f} {s[3]:>9,.0f} {s[4]:>9,.0f} {s[5]:>9,.0f} | "
          f"{s[6]:>9,.0f} {s[7]:>9,.0f} {s[8]:>9,.0f} {s[9]:>9,.0f} {s[10]!s:>9} {s[11]}")

print("\n=== ۲) پوششِ دیتابیسِ محلی در برابرِ مرجع (تعدادِ روزِ غایب، ۲۰۲۴ به بعد) ===")
print("غایب از مسارۀِ زنده:", dict(miss_live))
tot = sum(miss_db.values())
print(f"غایب از دیتابیس: مجموع={tot}  میانهِ به ازایِ نماد={tot / max(1, len(miss_db)):.1f}")
print("پراکندگیِ ماه‌هایِ دارایِ حفره (۱۲ تا آخر):", dict(sorted(gap_dates.items())[-14:]))

print("\n=== ۳) جلسۀِ ۲۰۲۶-۱۰-۱۰ (شنبه) در سه بستر ===")
print(f"{'نماد':9s} {'مرجع O':>10s} {'مرجع C':>10s} {'زنده':>7s} {'دیتابیس':>9s}")
for row in d1010:
    print(f"{row[0]:9s} {row[1]:>10,.0f} {row[2]:>10,.0f} {row[3]:>7s} {row[4]:>9s}")
print("نمادهایی که مرجع این جلسه را دارند:", len(d1010), "| در دیتابیس موجود:", sum(1 for r in d1010 if r[4] == "db"))
