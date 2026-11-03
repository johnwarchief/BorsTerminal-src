# dev/test_fts_zero_volume_collapse_v1.py — regressionِ ادغامِ بلوکِ VOL=0 به یک رویدادِ واحد (RC3، مرحلۀِ ۲)
# خالصِ read-only: هیچ شبکه/دیتابیس/سرویسی لازم نیست. رویِ ردیف‌هایِ مصنوعیِ همان
# الگوهایِ واقعیِ ولانا و لخزر و یکِ جداسازیِ مستقل سنجیده می‌شود.
# شرطِ امنیتیِ محوری: فاکتورِ تحویلیِ پیش و پس ازِ ادغام باید بیتغییر بماند — ادغام
# فقط «تعدادِ رویداد/تاریخِ مؤثر» را درست می‌کند، سریِ قیمت را تحریف نمی‌کند.
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
    if got == want:
        P += 1
        print(f"  ✓ {name}")
    else:
        F += 1
        print(f"  ✗ {name}: got={got} want={want}")


def rows(lst):
    return [{"time": t, "base": b, "close": c, "vol": v} for t, b, c, v in lst]


def factors_of(events, times):
    return [f["factor"] if isinstance(f, dict) else f for f in C._factors_from_events(times, events)]


def without_collapse(asc, by_date):
    """همان شمارشگرِ قبلی (بی‌ادغام)، برایِ اثباتِ بیتغییریِ فاکتور."""
    return by_date


# ── ولانا ۱۴۰۵: سه سطرِ VOL=0 با پایۀِ اداریِ متفاوت = یک اقدامِ شرکتی، نه سه رویداد
vl = rows([
    ("2026-07-21", 8920, 8920, 5_000_000),   # آخرینِ جلسۀِ واقعی
    ("2026-07-28", 2680, 2680, 0),           # پایه‌re-publish (ادغامی)
    ("2026-08-01", 2676, 2676, 0),           # پایه‌re-publish (ادغامی)
    ("2026-08-02", 3380, 3480, 0),           # سومینِ سطرِ بلوک (ادغامی)
    ("2026-08-05", 3380, 3400, 6_000_000),   # بازگشتِ معامله
])
ev, anchored = C._adjust_events_from_rows(vl)
check("ولانا: لنگر باز است", anchored, True)
run_dates = {"2026-07-28", "2026-08-01", "2026-08-02"}
check("ولانا: سه سطرِ VOL=0 → یکِ رویدادِ ادغامی", sum(1 for e in ev if e["date"] in run_dates), 1)
merged = next(e for e in ev if e["date"] in run_dates)
check("ولانا: برچسبِ collapsed=3 ثبت شد", merged.get("collapsed"), 3)
check("ولانا: نسبتِ ادغامی = حاصلِ ضربِ سه نسبتِ گِردِ هرِسطر (تلسکوپی تا ±۱e-۵)",
      abs(merged["ratio"] - 3380 / 8920) < 1e-5, True)

# بیتغییریِ فاکتور: رویدادهایِ ادغام‌شده همان زنجیره‌ای را می‌دهند که سه رویدادِ جدا
all_times = sorted([r["time"] for r in vl])
f_merged = factors_of(ev, all_times)
f_split = factors_of([{"date": "2026-07-28", "ratio": round(2680 / 8920, 6)},
                      {"date": "2026-08-01", "ratio": round(2676 / 2680, 6)},
                      {"date": "2026-08-02", "ratio": round(3380 / 2676, 6)},
                      {"date": "2026-08-05", "ratio": next(e["ratio"] for e in ev if e["date"] == "2026-08-05")}],
                     all_times)
# پس از آخرینِ سطرِ بلوکِ VOL=0 هر دو باید همسان باشند (هیچ کندلی درِ میانه نیست)
check("ولانا: فاکتورِ پس ازِ بلوک بیتغییر (ادغام سری را تحریف نمی‌کند)",
      f_merged[all_times.index("2026-08-05"):], f_split[all_times.index("2026-08-05"):])

# ── لخزر ۱۴۰۵: بلوکِ تعطیلِ شش‌روزه با سه پایه‌پلکان (۵۳۹۰/۴۷۹۰/۲۷۸۰)
lk = rows([
    ("2026-07-18", 3150, 3150, 6_642_682),
    ("2026-07-22", 5390, 5390, 0),
    ("2026-07-25", 4790, 4790, 0),
    ("2026-07-26", 2780, 2780, 0),
    ("2026-07-27", 2780, 2860, 4_056_184),
])
ev2, _ = C._adjust_events_from_rows(lk)
blk = {"2026-07-22", "2026-07-25", "2026-07-26"}
check("لخزر: سه گسستِ بلوکِ تعطیل → یکِ رویداد", sum(1 for e in ev2 if e["date"] in blk), 1)
m2 = next(e for e in ev2 if e["date"] in blk)
check("لخزر: نسبتِ ادغامی = ۲۷۸۰/۳۱۵۰", round(m2["ratio"], 6), round(2780 / 3150, 6))

# ── دو تعدیلِ مستقل که میانِ آن‌ها یکِ روزِ معاملۀِ واقعی هست: ادغام نباید بشود
ind = rows([
    ("2020-01-01", 1000, 1000, 100),
    ("2020-01-05", 700, 700, 0),      # تعدیلِ اول (بلوکِ تک‌سطری → ادغام نمی‌شود)
    ("2020-01-06", 700, 700, 500),    # روزِ واقعی، بلوک را می‌شکند
    ("2020-01-09", 490, 490, 0),      # تعدیلِ دوم (بلوکِ تک‌سطری)
    ("2020-01-10", 490, 490, 500),
])
ev3, _ = C._adjust_events_from_rows(ind)
check("مستقل: دو تعدیل با روزِ واقعیِ میانی ادغام نشدند", len(ev3), 2)
check("مستقل: هیچِ collapsed رویِ تک‌سطرها نیست", any("collapsed" in e for e in ev3), False)

# ── بلوکِ VOL=0 که فقط یکِ رویداد می‌سازد → نباید collapsed بگیرد (ادغامِ الکی ممنوع)
single = rows([
    ("2021-01-01", 1000, 1000, 100),
    ("2021-01-05", 800, 800, 0),
    ("2021-01-06", 800, 800, 0),      # دومینِ سطرِ VOL=0 ولی بی‌جابه‌جاییِ پایه → یکِ رویداد
    ("2021-01-07", 800, 810, 100),
])
ev4, _ = C._adjust_events_from_rows(single)
check("تک‌رویدادِ درونِ بلوک: collapsed اضافه نشد", any("collapsed" in e for e in ev4), False)

print("\n" + "=" * 60)
print(f"نتیجه: {P} سبز، {F} قرمز")
sys.exit(1 if F else 0)
