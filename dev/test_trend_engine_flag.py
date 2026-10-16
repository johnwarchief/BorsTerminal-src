"""گاردِ اتصالِ موتورِ روند (P0-3): flag، سازگاریِ legacy، بی‌تغییریِ جت، نشتنکردنِ کش.

اجرا:  python dev/test_trend_engine_flag.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import datetime as dt
from api import chart as CH  # noqa: E402

RES = []


def ck(name, cond, got=""):
    RES.append((name if cond else "✗ " + name, bool(cond), "" if cond else repr(got)))


def zig(n=180, start="2024-01-02"):
    d0 = dt.date.fromisoformat(start)
    out = []
    for i in range(n):
        base = 100 + 0.6 * i + (6 if (i // 12) % 2 == 0 else 0)
        hi = base + (5 if i % 5 == 2 else 1)
        lo = base - (5 if i % 5 == 4 else 1)
        out.append({"time": (d0 + dt.timedelta(days=i)).isoformat(),
                    "open": base, "high": hi, "low": lo, "close": base, "volume": 1000})
    return out


CANDLES = zig()

# ۱) flag=legacy ⇒ برچسب‌ها دقیقاً مثلِ `_fts_classify_trend` (رفتارِ امروز)
CH.TREND_ENGINE = "legacy"
legacy_out = CH._fts_analyze_candles("X", [dict(c) for c in CANDLES])
sw = CH._fts_swings(CANDLES, k=CH._FTS_SWING_K)
direct = CH._fts_classify_trend(sw, series=CANDLES)["trend"]
ck("legacy: trend.D == _fts_classify_trend (بدونِ تغییرِ رفتار)",
   legacy_out["trend"]["D"]["trend"] == direct, (legacy_out["trend"]["D"]["trend"], direct))

# ۲) flag=hybrid ⇒ برچسبِ معتبر + فیلدهایِ ممیزی
CH.TREND_ENGINE = "hybrid"
hyb_out = CH._fts_analyze_candles("X", [dict(c) for c in CANDLES])
hd = hyb_out["trend"]["D"]
ck("hybrid: trend.D ∈ {up,down,range,na}", hd["trend"] in ("up", "down", "range", "na"), hd["trend"])
ck("hybrid: فیلدهایِ ممیزی هست (confidence/outcome)",
   "confidence" in hd and "outcome" in hd, sorted(hd.keys())[:6])

# ۳) جت تحتِ هر دو flag یکسان است (جت به hybrid گره نخورده)
CH.TREND_ENGINE = "legacy"
jet_legacy = CH._fts_jet_setup([dict(c) for c in CANDLES])
CH.TREND_ENGINE = "hybrid"
jet_hybrid = CH._fts_jet_setup([dict(c) for c in CANDLES])
ck("jet: خروجی تحتِ legacy و hybrid یکسان است", jet_legacy == jet_hybrid,
   (jet_legacy.get("tier"), jet_hybrid.get("tier")))

# ۴) کلیدِ کش با engine عوض می‌شود ⇒ پاسخِ legacy به hybrid نشت نمی‌کند
CH.TREND_ENGINE = "legacy"
k_legacy = CH._fts_analysis_cache_key("X", 100.0, None, "b", None)
CH.TREND_ENGINE = "hybrid"
k_hybrid = CH._fts_analysis_cache_key("X", 100.0, None, "b", None)
ck("کلیدِ کش engine را می‌برد (بی‌نشتِ موتور)", k_legacy != k_hybrid, (k_legacy, k_hybrid))
ck("کلید همچنان مبنا را درِ آخر می‌برد (قراردادِ گاردِ basis)",
   k_hybrid.split("|")[-1] == "b", k_hybrid)

# ۵) قاعدۀِ دروازۀِ هفتگی حفظ است: weekly=range ⇒ REJECT، weekly=na ⇒ UNKNOWN
#    (hybrid خنثی را به 'range' و کم‌داده را به 'na' نگاشت می‌کند تا همین مسیرها بخورند)
CH.TREND_ENGINE = "legacy"
mx_range = CH._fts_analyze_candles("X", [])  # بدونِ کندل ⇒ مسیرِ na
# بررسیِ مستقیمِ منطقِ matrix با تزریقِ trendِ ساختگی:
def _matrix_for(tw, td):
    out = {"trend": {"D": {"trend": td}, "W": {"trend": tw}, "M": {"trend": tw}, "alignment": "na"}}
    # همان قاعدۀِ chart.py را صدا نمی‌زنیم؛ به‌جایش از خروجیِ واقعیِ یک سریِ کنترل‌شده استفاده می‌کنیم
    return out

# یک سریِ نزولیِ روشن بساز تا هر دو موتور هفتگی را نزولی/خنثی بدهند و matrix REJECT شود
down = zig(180)
for i, c in enumerate(down):
    p = 200 - 0.6 * i
    c.update(open=p, high=p + 2, low=p - 2, close=p)
for eng in ("legacy", "hybrid"):
    CH.TREND_ENGINE = eng
    o = CH._fts_analyze_candles("X", [dict(c) for c in down])
    tw = o["trend"]["W"]["trend"]
    dec = (o["trend"].get("matrix") or {}).get("decision")
    # اگر هفتگی نزولی/خنثی است ⇒ باید REJECT باشد؛ اگر na است ⇒ UNKNOWN. هیچ‌وقت PERMITTED نه.
    ok = (dec == "REJECT" if tw in ("down", "range") else dec == "UNKNOWN" if tw == "na" else True)
    ck(f"دروازۀِ هفتگی حفظ شد ({eng}): weekly={tw} ⇒ decision={dec}", ok and dec != "PERMITTED",
       (tw, dec))

fails = [n for n, ok, _ in RES if not ok]
for n, ok, extra in RES:
    print(f"  {'PASS' if ok else 'FAIL'}  {n}{'  <<< ' + extra if extra else ''}")
print(f"\n{len(RES) - len(fails)}/{len(RES)} passed")
sys.exit(1 if fails else 0)
