"""dev/fts_trend_staleness_v1064.py — رأیِ روند نباید روی پیوتِ کهنه بماند

چرا: تأییدِ پیوت (fractal) سه کندل در هر دو طرف می‌خواهد، پس در یک حرکتِ
یک‌طرفهٔ طولانی *هیچ* پیوتی تأیید نمی‌شود و `_fts_classify_trend` روی دو پیوتِ
ماه‌ها پیش رأی می‌داد. شاهدِ واقعی (کايزد، ۱۴۰۵-۰۷-۰۷): سریِ تعدیل‌شده از ۱۵۱۴
به ۳۸۲۰ رسیده بود (+۱۵۲٪) و کندلِ امروز ۳۶۰۰ ← ۳۷۰۰ (بدنهٔ سبز)، ولی تازه‌ترین
پیوتِ تأییدشده ۴۴ کندل عقب بود؛ موتور «روزانه نزولی / هفتگی خنثی» می‌گفت و
ماتریس REJECT می‌داد — همان چیزی که مالک دید: «کندل روزانه صعودیه، نوشته نزولی».

رأیِ پایلوت (گزینهٔ B): پیوت‌های تأییدشده دست‌نخورده می‌مانند؛ فقط وقتی
تازه‌ترین پیوت بیش از `_FTS_STALE_BARS` کندل عقب است، جهت از روی شیبِ
رگرسیونِ خطیِ بازهٔ اخیر و جایِ قیمت نسبت به میانگینِ ۵۲ دوره خوانده می‌شود.

این گارد بی‌شبکه و بی‌market.db می‌دود و می‌سنجد:
  • صعودِ یک‌طرفهٔ بی‌پیوت ⇒ up (و ماتریس PERMITTED) با basis=recent-window
  • سقوطِ یک‌طرفهٔ بی‌پیوت ⇒ down (شاهدِ منفی: fallback همیشه صعودی نمی‌گوید)
  • دریفتِ کوچک ⇒ range (آستانهٔ جابه‌جایی واقعاً کار می‌کند)
  • پیوتِ تازه ⇒ همان رأیِ پیوت‌ها، fallback دخالت نمی‌کند (شاهدِ منفیِ ربایش)
  • سریِ کوتاه ⇒ na، بدونِ رأیِ ساختگی
  • دلیلِ فارسی می‌گوید بر چه مبنایی (تاریخِ پیوت‌ها یا بازهٔ اخیر) قضاوت شد
"""
import datetime
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.chart as CH  # noqa: E402

FAILS = []


def ck(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAILS.append(label)


def series(prices, start="2025-01-01"):
    d0 = datetime.date.fromisoformat(start)
    out = []
    for i, p in enumerate(prices):
        out.append({"time": (d0 + datetime.timedelta(days=i)).isoformat(),
                    "open": float(p), "high": float(p) * 1.01,
                    "low": float(p) * 0.99, "close": float(p), "volume": 1000.0})
    return out


def zigzag(n=100, base=100.0, amp=6.0, period=18.85):
    """نوسانِ رفت‌وبرگشتی ⇒ پیوت‌های تأییدشده. period کوچک = پیوتِ تازه."""
    return [base + amp * math.sin(2.0 * math.pi * i / period) for i in range(n)]


def ramp(n, start_px, pct):
    """شیبِ یکنواخت: هیچ پیوتی تأیید نمی‌شود (ساختار همیشه کهنه است)."""
    return [start_px * (1.0 + pct * i / (n - 1)) for i in range(n)]


# ── ۱) صعودِ یک‌طرفهٔ بی‌پیوت: رأیِ پیوت‌ها down است، fallback باید up بگوید ───
zz = zigzag()
climb = [zz[-1] + 5.0 * (j + 1) for j in range(200)]   # ۲۰۰ کندل تا هفتگی هم کهنه شود
up_ser = series(zz + climb)
up_sw = CH._fts_swings(up_ser, k=CH._FTS_SWING_K)
up_piv = CH._fts_classify_trend(up_sw)                 # بدون سری = رفتارِ قدیم
up_new = CH._fts_classify_trend(up_sw, series=up_ser)
gap = len(up_ser) - 1 - max(s["idx"] for s in up_sw)
ck(f"ساختار کهنه است (فاصلهٔ پیوت {gap} > {CH._FTS_STALE_BARS})", gap > CH._FTS_STALE_BARS)
ck(f"رأیِ قدیمیِ پیوت‌ها «{up_piv['trend']}» بود (همان که کايزد را رد می‌کرد)",
   up_piv["trend"] in ("down", "range", "na"))
ck(f"رأیِ تازهٔ همان سری up است (basis={up_new['basis']})",
   up_new["trend"] == "up" and up_new["basis"] == "recent-window")
ck("رأیِ قدیمی برایِ ممیزی نگه داشته می‌شود (pivots)",
   isinstance(up_new.get("pivots"), dict) and up_new["pivots"]["trend"] == up_piv["trend"])
ck("تعدادِ کندلِ کهنگی در خروجی هست", up_new.get("stale_bars") == gap)

# ── ۲) سقوطِ یک‌طرفه: fallback نباید همیشه صعودی بگوید (شاهدِ منفی) ───────────
fall = [zz[-1] - 0.3 * (j + 1) for j in range(200)]
down_ser = series(zz + fall)
down_new = CH._fts_classify_trend(CH._fts_swings(down_ser, k=CH._FTS_SWING_K),
                                  series=down_ser)
ck(f"سقوطِ یک‌طرفه down می‌گیرد (basis={down_new['basis']})",
   down_new["trend"] == "down" and down_new["basis"] == "recent-window")
ck("سقوط زیرِ میانگینِ ۵۲ دوره است", down_new.get("above_ma") is False)

# ── ۳) دریفتِ کوچک: نه صعود نه سقوط ⇒ range ──────────────────────────────────
flat = series(ramp(60, 100.0, 0.02))
rng = CH._fts_classify_trend(CH._fts_swings(flat, k=CH._FTS_SWING_K), series=flat)
ck(f"دریفتِ {rng.get('move_pct')}٪ range می‌ماند (آستانهٔ ۵٪)",
   rng["trend"] == "range" and rng["basis"] == "recent-window")
ck("شیبِ بزرگِ همان بازه up می‌گیرد (آستانه یک‌طرفه نیست)",
   CH._fts_classify_trend(CH._fts_swings(series(ramp(60, 100.0, 0.8)), k=CH._FTS_SWING_K),
                          series=series(ramp(60, 100.0, 0.8)))["trend"] == "up")

# ── ۴) پیوتِ تازه: fallback باید ساکت بماند (شاهدِ منفیِ ربایش) ───────────────
fresh = series(zigzag(n=60, period=8.0))
fresh_sw = CH._fts_swings(fresh, k=CH._FTS_SWING_K)
fresh_gap = len(fresh) - 1 - max(s["idx"] for s in fresh_sw)
fresh_new = CH._fts_classify_trend(fresh_sw, series=fresh)
ck(f"پیوتِ تازه است (فاصله {fresh_gap} ≤ {CH._FTS_STALE_BARS})",
   fresh_gap <= CH._FTS_STALE_BARS)
ck("با پیوتِ تازه همان رأیِ پیوت‌ها برگردانده می‌شود",
   fresh_new["basis"] == "pivots" and fresh_new == CH._fts_classify_trend(fresh_sw))

# ── ۵) سریِ کوتاه: رأیِ ساختگی نمی‌دهد ────────────────────────────────────────
tiny = series([100.0 + 3.0 * i for i in range(10)])
tiny_res = CH._fts_classify_trend(CH._fts_swings(tiny, k=CH._FTS_SWING_K), series=tiny)
ck("سریِ ۱۰ کندلی na می‌ماند", tiny_res["trend"] == "na" and tiny_res["basis"] == "pivots")

# ── ۶) دلیلِ فارسی: می‌گوید بر چه مبنایی قضاوت شد ────────────────────────────
r_win = CH._fts_trend_reason(up_new)
r_piv = CH._fts_trend_reason(fresh_new)
ck("دلیلِ بازهٔ اخیر، بازه و جابه‌جایی و کهنگیِ پیوت را می‌گوید",
   "کندلِ اخیر" in r_win and "٪" in r_win and "عقب است" in r_win)
ck("دلیلِ پیوت‌ها، تاریخِ دو سقف و دو کف را می‌گوید",
   r_piv.count("←") == 2 and "۲۰۲۵" in r_piv)
ck("رقم‌هایِ دلیل فارسی است (بدونِ رقمِ لاتین)",
   not any(c in r_win for c in "0123456789"))

# ── ۷) ماتریسِ چندزمانه: صعودِ بی‌پیوت دیگر REJECT نیست ──────────────────────
payload = CH._fts_analyze_candles("TEST", up_ser)
mx = payload["trend"]["matrix"]
ck(f"ماتریس {mx['decision']} است (پیش‌تر REJECT بود)", mx["decision"] == "PERMITTED")
ck("ستاپِ جت/پولبک پیشنهاد می‌شود", mx["setup"] == "JET_OR_PULLBACK_HOLD")
ck("مبنایِ هفتگی و روزانه در پیلود هست",
   bool(mx["basis"]["weekly"]) and bool(mx["basis"]["daily"]))

down_mx = CH._fts_analyze_candles("TEST", down_ser)["trend"]["matrix"]
ck("سقوطِ یک‌طرفه هنوز REJECT می‌گیرد (وتوی هفتگی زنده است)",
   down_mx["decision"] == "REJECT")
ck("دلیلِ رد، مبنایش را هم می‌گوید", "مبنا:" in down_mx["desc"])

print()
if FAILS:
    print(f"FTS TREND STALENESS GUARD FAILED ({len(FAILS)})")
    for f in FAILS:
        print("  - " + f)
    sys.exit(1)
print("FTS TREND STALENESS GUARD OK")
