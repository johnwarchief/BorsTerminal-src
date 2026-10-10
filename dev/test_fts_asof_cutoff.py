"""گاردِ as_of/کلیدِ کشِ تحلیلِ FTS (P0-3).

ثابت می‌کند:
  ۱) `_candles_upto_asof` واقعاً کندل‌هایِ بعد از T را بیرون می‌اندازد (بدونِ as_of
     هیچ برشی نیست ⇒ رفتارِ امروز).
  ۲) cutoffِ واقعی است نه تزئینی: دادهٔ بعد از T خروجِ موتور را عوض می‌کند، پس
     اگر برش کار نکند تستِ کنترلِ منفی سرخ می‌شود (کنترلِ کاشته‌شده).
  ۳) نتیجهٔ as_of=T با نتیجهٔ محاسبه‌شده از فقطِ کندل‌هایِ <= T یکی است.
  ۴) کلیدِ کش as_of را می‌برد ⇒ دو cutoff هرگز به هم نشت نمی‌کنند؛ و یک buildِ
     جدید (APP_VERSION) کشِ rulebookِ پیشین را جواب نمی‌دهد.

بی‌شبکه و بی‌market.db. اجرا:  python dev/test_fts_asof_cutoff.py
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from api import chart as CH  # noqa: E402

RES = []


def ck(name, cond, got=""):
    RES.append((name if cond else "✗ " + name, bool(cond), "" if cond else repr(got)))


def bars(closes, start="2024-01-01"):
    d0 = dt.date.fromisoformat(start)
    out = []
    for i, c in enumerate(closes):
        day = (d0 + dt.timedelta(days=i)).isoformat()
        out.append({"time": day, "open": c, "high": c * 1.01,
                    "low": c * 0.99, "close": c})
    return out


# ۷۰ کندل تا T، بعد ۵ کندلِ تازه با بستۀ متفاوت (بعد از T)
base = bars([100.0 + 0.5 * i for i in range(70)])
T = base[-1]["time"]
later = bars([500.0, 520.0, 480.0, 540.0, 560.0], start=(dt.date.fromisoformat(T)
            + dt.timedelta(days=1)).isoformat())
full = base + later

# ۱) خودِ برش
ck("بی‌as_of هیچ برشی نیست", CH._candles_upto_asof(full, None) is full)
sliced = CH._candles_upto_asof(full, T)
ck(f"برش تا {T} دقیقاً ۷۰ کندل", len(sliced) == 70, len(sliced))
ck("هیچ کندلِ بعدِ T نمی‌ماند", all(c["time"] <= T for c in sliced))
ck("آخرینِ برشیده همان T است", sliced[-1]["time"] == T, sliced[-1]["time"])

# ۲) کنترلِ منفی: موتور کندلِ آخر را می‌خواند، پس دادهٔ بعدِ T خروج را عوض می‌کند
fts_T = CH._fts_analyze_candles("X", sliced)
fts_full = CH._fts_analyze_candles("X", full)
ck("کنترلِ منفی: بعدِT خروج را تغییر می‌دهد (closeِ جت)",
   fts_T["jet"]["close"] != fts_full["jet"]["close"],
   (fts_T["jet"]["close"], fts_full["jet"]["close"]))

# ۳) برشِ real ⇒ نتیجه از فقطِ <=T بازسازی‌شدنی است
ck("نتیجهٔ برشیده با نتیجهٔ pre-T یکی است",
   CH._fts_analyze_candles("X", sliced)["jet"]["close"] == fts_T["jet"]["close"])

# ۴) کلیدِ کش همهٔ ورودی‌هایِ مؤثر را می‌برد ⇒ نشتِ cutoff/rulebook ندارد
CH.FTS_ANALYSIS_CACHE.clear()
_orig_series = CH._fts_analysis_series
CH._fts_analysis_series = lambda symbol: (full, "test-basis")
try:
    r_none = CH._fts_analyze_symbol("X")            # as_of=None → کلِ ۷۵ کندل
    r_T = CH._fts_analyze_symbol("X", as_of=T)       # as_of=T → ۷۰ کندل
    r_other = CH._fts_analyze_symbol("X", as_of=sliced[40]["time"])
finally:
    CH._fts_analysis_series = _orig_series

keys = list(CH.FTS_ANALYSIS_CACHE.keys())
ck("سه cutoff ⇒ سه کلیدِ کشِ جدا (بی‌نشت)", len(keys) == 3, keys)
ck("پاسخِ as_of=T فقط ۷۰ کندل را داوری کرده", r_T.get("bars") == 70, r_T.get("bars"))
ck("پاسخِ بی‌as_of هر ۷۵ کندل", r_none.get("bars") == 75, r_none.get("bars"))
ck("برچسبِ as_of درِ پاسخِ replay می‌آید", r_T.get("as_of") == T, r_T.get("as_of"))

# ۵) هر بُعدِ مؤثر درِ هویتِ کلید باشد — با کنترلِ منفیِ تک‌تک
def _k(**over):
    base_kwargs = dict(symbol="X", last_close=134.5, entry_hint=None,
                       basis="local-db-adjusted", as_of=None)
    base_kwargs.update(over)
    return CH._fts_analysis_cache_key(**base_kwargs)

k0 = _k()
ck("کلید نماد را می‌برد", _k(symbol="Y") != k0)
ck("کلید as_of را می‌برد", _k(as_of=T) != k0)
ck("کلید مبنایِ تعدیل را می‌برد", _k(basis="tsetmc-raw") != k0)
ck("کلید entry_hint را می‌برد", _k(entry_hint=120.0) != k0)
ck("کلید tf (دقّتِ سریِ ورودی) را می‌برد (کنترلِ مثبت: درِ متنِ کلید هست)",
   "tf=daily" in k0, k0)
ck("کلید نسخهٔ قواعد را می‌برد", f"rs={CH.FTS_TECH_RULESET_VERSION}" in k0, k0)
# کنترلِ منفیِ ruleset: با عوض‌شدنِ نسخهٔ قواعد، کلید باید عوض شود (کشِ کهنه نماند)
_old_rs = CH.FTS_TECH_RULESET_VERSION
try:
    CH.FTS_TECH_RULESET_VERSION = "999"
    ck("بumpِ نسخهٔ قواعد ⇒ کلید عوض می‌شود", _k() != k0)
finally:
    CH.FTS_TECH_RULESET_VERSION = _old_rs


fails = [n for n, ok, _ in RES if not ok]
for n, ok, extra in RES:
    print(f"  {'PASS' if ok else 'FAIL'}  {n}{'  <<< ' + extra if extra else ''}")
print(f"\n{len(RES) - len(fails)}/{len(RES)} passed")
sys.exit(1 if fails else 0)
