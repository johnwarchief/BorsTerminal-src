# dev/test_fts_ma_source_v1.py — RC/منبعِ `/api/ma` (مرحلۀِ ۴): MA رویِ همان زنجیرۀِ تعدیلِ چارت
# فقط _sma_series و _factors_from_eventsِ خالص سنجیده می‌شوند؛ هیچ بانکِ عملیاتی لمس
# نمی‌شود. parityِ عددیِ endpoint با مرجع بیرونی عمداً UNVERIFIED می‌ماند (دسترِ رهاورد
# درِ این دور نیست) — اینجا فقط «درستیِ محاسبه نسبت به یک منطقِ مستقلِ هم‌سری» اثبات می‌شود.
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from api import chart as C  # noqa: E402

P = F = 0


def check(name, got, want):
    global P, F
    ok = got == want
    if ok:
        P += 1
        print(f"  ✓ {name}")
    else:
        F += 1
        print(f"  ✗ {name}: got={got!r} want={want!r}")


pairs = [(f"d{i}", float(i + 1)) for i in range(6)]  # d0..d5 → 1..6
ma = C._sma_series(pairs, [3])
# پیش ازِ w-1 ⇒ None
check("پیشِ پنجره None است", ma["ma3"][:2], [["d0", None], ["d1", None]])
# پنجرۀِ ۳: میانگینِ [1,2,3]=2.00، [2,3,4]=3.00، [3,4,5]=4.00، [4,5,6]=5.00
check("میانگینِ باریکِ ۳ درِ i≥2", [ma["ma3"][i][1] for i in range(2, 6)], [2.0, 3.0, 4.0, 5.0])
# برابرِ منطقِ مستقلِ هم‌سری (تازۀ ۳ تا، نه شمارِ کل)
indep = [round(sum(p[1] for p in pairs[max(0, i - 2):i + 1]) / min(3, i + 1), 2) if i >= 2 else None
         for i in range(len(pairs))]
check("مطابقتِ کامل با میانگینِ متحرکِ مستقل", [ma["ma3"][i][1] for i in range(len(pairs))], indep)

# ── اثرِ ضریبِ تعدیل رویِ MA: نمادِ رویداددار باید MAِ تعدیل‌شده بدهد، نه خام
rows = [{"time": f"2024-01-{i:02d}", "close": 1000.0, "last": 1000.0} for i in range(1, 8)]
ev = [{"date": "2024-01-05", "ratio": 0.5}]     # همهٔ پیش‌ازِ ۰۵-۰۵ نصف می‌شود
fct = C._factors_from_events([r["time"] for r in rows], ev)
adj_pairs = [(r["time"], round(r["close"] * f, 6)) for r, f in zip(rows, fct)]
raw_ma = C._sma_series([(r["time"], r["close"]) for r in rows[:4]], [3])["ma3"][2][1]   # ≈1000
adj_ma = C._sma_series(adj_pairs[:4], [3])["ma3"][2][1]
check("فاکتورِ تعدیل رویِ MA اثر می‌گذارد (۵۰۰ نه ۱۰۰۰)", adj_ma, 500.0)
check("MAِ خامِ بی‌تعدیل همان ۱۰۰۰ می‌ماند", raw_ma, 1000.0)

# ── بی‌رویداد ⇒ فاکتورِ ۱ و MA == خام (بدونِ تحریف برایِ نمادهایِ بی‌تعدیل)
fct_none = C._factors_from_events([r["time"] for r in rows], [])
check("بی‌رویداد ⇒ همهٔ فاکتورها ۱", set(fct_none), {1.0})

print("\n" + "=" * 60)
print(f"نتیجه: {P} سبز، {F} قرمز")
sys.exit(1 if F else 0)
