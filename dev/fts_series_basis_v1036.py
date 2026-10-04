"""dev/fts_series_basis_v1036.py — تحلیل FTSِ سرور همان سریِ چارت را می‌بیند (#187 #186)

چرا: نوارِ نشان‌ها، پنلِ «وضعیت FTS»، سایدبارِ «ترازها و حد ضرر»، تابلوی حد ضررِ
پرتفوی و ستون‌های tech_*ِ غربگر همه از `/api/fts/{symbol}` می‌آیند؛ ولی آن endpoint
روی `price_history` محلی می‌دوید که فقط دو سال نگه می‌دارد و میانیِ نمادها ۲۰ نشست
است (از ۲۵۱۸ نماد تنها ۸۷۲ تا به ۶۰ نشست می‌رسند) و قیمت‌هایش هم **خام** است.
چارتِ همان صفحه از جای دیگری می‌خواند: تاریخچۀ کامل از CDN + ضرایبِ تعدیل.
نتیجهٔ اندازه‌گیری‌شده (۱۴۰۵-۰۷-۰۵، سرورِ پیش از این اصلاح در برابر بعد از آن):
  • خودرو: ۵ بار «بدون داده» در پنلِ ترازها، بدون MA(14)، بدون کمربند فیبو ⇒ بعد:
    صفر «بدون داده»، MA(14)=۷۲۲، حکم «خروج» با چهار سیگنال. (۶ نشست در برابر ۵۲۸۷)
  • تكنار: موتور می‌گفت «تاریخچه به ۶۰ نشست نمی‌رسد»؛ با سریِ درست **جت فعال** است.
  • فولاد: کمربند ۳۳–۴۰٪ روی ۲٬۷۹ تا ۲۸۴۰ نشسته بود وقتی پایانیِ امروز ۳٬۲۶۰ است —
    چون پلکانِ مقاومت پیش از افزایشِ سرمایه خوانده می‌شد (۴٬۴۷۹ در برابر ۳٬۴۱۰).

این گارد بی‌شبکه و بی‌market.db می‌دود (هر دو منبع داده جعل می‌شوند) و می‌سنجد:
  • `_fts_scaled` مرتبِ صعودی می‌سازد، ضریب را مثلِ فرانت اعمال می‌کند، و حجم را
    بر ضریب می‌شکند
  • جت روی سریِ تعدیل‌شده فعال می‌شود در حالی که روی همان سریِ خام هرگز فعال نمی‌شود
  • بی‌CDN صادقاً به بانکِ محلی برمی‌گردد و همان را در `analysis_basis` اعلام می‌کند
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.chart as CH  # noqa: E402

FAILS = []


def ck(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAILS.append(label)


def days(n, end="2026-09-26"):
    e = datetime.date.fromisoformat(end)
    return [(e - datetime.timedelta(days=n - 1 - i)).isoformat() for i in range(n)]


# ---------- ۱) خودِ نگاشتِ سری ----------
N = 70
T = days(N)
# ۴۰ نشستِ نخست پیش از یک افزایشِ سرمایه است: خام ۱۰۰، تعدیل‌شده ۵۰
raw = [{"time": T[i], "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0}
       if i < 40 else
       ({"time": T[i], "open": 60.0, "high": 60.0, "low": 60.0, "close": 60.0}
        if i < N - 1 else
        {"time": T[i], "open": 60.0, "high": 61.0, "low": 60.0, "close": 61.0})
       for i in range(N)]
factors = [{"time": T[i], "factor": 0.5 if i < 40 else 1.0} for i in range(N)]
volumes = [{"time": T[i], "value": 1000.0} for i in range(N)]

desc = list(reversed(raw))                       # CDN نزولی می‌دهد؛ چارت صعودی می‌خواهد
adj = CH._fts_scaled(desc, factors, volumes)
ck("سریِ صعودی ساخته می‌شود با همان تعدادِ نشست",
   len(adj) == N and adj[0]["time"] == T[0] and adj[-1]["time"] == T[-1])
ck("ضریبِ تعدیل مثلِ فرانت رویِ ریال می‌نشیند (۱۰ ⇒ ۵۰)",
   adj[0]["close"] == 50.0 and adj[39]["high"] == 50.0)
ck("کندل‌هایِ پس از رویداد خام می‌مانند (۶۱ دست‌نخورده)", adj[-1]["close"] == 61.0)
ck("حجم بر ضریب تقسیم می‌شود تا ارزشِ معامله ثابت بماند (۱۰۰ ⇒ ۲۰۰۰)",
   adj[0]["volume"] == 2000.0 and adj[-1]["volume"] == 1000.0)
ck("هیچ کندلی بی‌time نمی‌ماند و کلیدهایِ موتور کامل است",
   all(set(("time", "open", "high", "low", "close", "volume")) <= set(c) for c in adj))

# ---------- ۲) جت: خام می‌گوید نه، تعدیل‌شده می‌گوید بله ----------
raw_series = CH._fts_scaled(desc, [], volumes)
jet_adj = (CH._fts_analyze_candles("آزمایشی", adj).get("jet") or {})
jet_raw = (CH._fts_analyze_candles("آزمایشی", raw_series).get("jet") or {})
ck("پلکانِ خام به ۱۰۰ می‌رسد ⇒ جت خام false است", jet_raw.get("active") is False)
ck("روی سریِ تعدیل‌شده همان نماد جت می‌زند (شرطِ #187)",
   jet_adj.get("active") is True and jet_adj.get("resistance") == 60.0)
ck("تفاوتِ دو جواب فقط از ضریبِ تعدیل است: پنجره و پایانی یکی است",
   len(raw_series) == len(adj) and raw_series[-1]["close"] == adj[-1]["close"])

# ---------- ۳) مسیرِ سرور: منبعِ سری و فال‌بکِ صادق ----------
class _Resp:
    def __init__(self, payload):
        self.payload = payload

    def __call__(self, symbol):
        return self.payload


PAYLOAD = {"status": "success", "candles": desc, "factors": factors,
           "volumes": volumes, "adjustSource": "base-price-discontinuity"}

_local = [{"time": T[i], "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0,
           "last": 100.0, "volume": 1000.0} for i in range(N)]

_saved_cdn, _saved_db, _saved_cache = CH.get_chart_tsetmc, CH.get_chart_db, dict(CH.FTS_ANALYSIS_CACHE)
try:
    CH.get_chart_tsetmc = _Resp(PAYLOAD)
    CH.get_chart_db = lambda symbol, adjustment=3: {"status": "success", "candles": list(_local)}
    series, basis = CH._fts_analysis_series("آزمایشی")
    ck("سریِ تحلیل از CDNِ تمام‌تاریخ می‌آید و مبنا اعلام می‌شود",
       basis == "tsetmc-adjusted" and len(series) == N and series[-1]["close"] == 61.0)

    CH.FTS_ANALYSIS_CACHE.clear()
    payload = CH._fts_analyze_symbol("جت-تعدیل")
    ck("پیلودِ /api/fts مبنا و تعدادِ نشست را با خود می‌فرستد",
       payload.get("analysis_basis") == "tsetmc-adjusted" and payload.get("bars") == N)
    ck("جتِ همان پیلود رویِ مبنایِ تعدیل‌شده فعال است",
       ((payload.get("fts") or {}).get("jet") or {}).get("active") is True)

    # CDN قطع ⇒ فال‌بکِ محلی، و این باید در پاسخ معلوم باشد نه پنهان
    def _boom(symbol):
        raise RuntimeError("cdn down")

    CH.get_chart_tsetmc = _boom
    CH.FTS_ANALYSIS_CACHE.clear()
    series2, basis2 = CH._fts_analysis_series("آزمایشی")
    ck("بی‌CDN و بی‌رویدادِ شناخته‌شده ⇒ بانکِ محلی، خام، و صریح اعلام‌شده",
       basis2 == "local-db-raw" and len(series2) == N)
    CH.FTS_ANALYSIS_CACHE.clear()
    payload2 = CH._fts_analyze_symbol("جت-محلی")
    ck("روی سریِ خامِ محلی همان نماد جت نمی‌زند (تفاوتِ واقعیِ دو مسیر)",
       ((payload2.get("fts") or {}).get("jet") or {}).get("active") is False
       and payload2.get("analysis_basis") == "local-db-raw")

    # Round K/PHASE A: بانکِ محلی همان مجموعهٔ رویدادِ کاننیکال را نگه می‌دارد، پس
    # فال‌بک دیگر «سریِ خامِ برچسب‌خورده» نیست — هر دو مسیر یک قیمت می‌بینند.
    CH.get_chart_db = lambda symbol, adjustment=3: {
        "status": "success", "candles": list(_local), "factors": list(factors),
        "volumes": list(volumes), "adjustSource": "local-cache",
        "adjustCapability": {"source": "local-cache", "combined_available": True,
                             "functional_available": False,
                             "functional_reason": "دادهٔ رویدادِ تفکیکی نیست",
                             "event_count": 2}}
    CH.FTS_ANALYSIS_CACHE.clear()
    series3, basis3 = CH._fts_analysis_series("آزمایشی")
    ck("فال‌بکِ محلی با رویدادِ کاننیکال ⇒ سریِ تعدیل و مبنایِ local-db-adjusted",
       basis3 == "local-db-adjusted" and len(series3) == N and series3[0]["close"] < 100.0)
finally:
    CH.get_chart_tsetmc, CH.get_chart_db = _saved_cdn, _saved_db
    CH.FTS_ANALYSIS_CACHE.clear()
    CH.FTS_ANALYSIS_CACHE.update(_saved_cache)

print()
if FAILS:
    print("FTS SERIES BASIS GUARD FAILED: %d" % len(FAILS))
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("FTS SERIES BASIS GUARD OK")
