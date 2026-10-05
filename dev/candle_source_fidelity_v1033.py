#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/candle_source_fidelity_v1033.py — کندل باید همان باشد که TSETMC منتشر می‌کند.

چرا این گارد متولد شد (CANDLE-1، ۲۰۲۶-۰۹-۲۶؛ نمونه‌ای که کاربر گزارش داد «آسود» بود):

۱) **هندسهٔ ناممکن.** خودِ CSV تاریخِ TSETMC در درصدِ قابل‌توجهی از ردیف‌ها،
   «قیمت پایانی» را بیرونِ [کمینه، بیشینه] می‌دهد. اندازه‌گیریِ واقعی روی ۱۴۰ نماد
   (tools/candle_source_audit.py): اخابر ۶۹۴ ردیف (۱۸٪)، اميد ۳۹۲ (۲۰٪)،
   البرز ۵۲۲، خودرو ۴۱۵، فولاد ۲۸۵. نمونهٔ عینیِ فولاد ۲۰۰۸-۱۲-۲۲:
   H=L=۱۹۷۳ در برابر C=۱۹۱۷. مسیرِ CDN هیچ‌وقت این را ترمیم نمی‌کرد، پس بدنهٔ کندل
   بیرونِ سایهٔ خودش کشیده می‌شد — و همان سایه خوردهٔ معیارهای فنی است:
   سقف/کفِ نوسانی، ATR، حمایت/مقاومت و شرطِ «شکست مقاومت» ستاپ جت.
   ترمیم: پایانی معتبر است (به پایهٔ روزِ بعد زنجیر می‌شود: base(t+1)==close(t))،
   پس سایه گِشاد می‌شود و پایانی دست‌نخورده می‌ماند.

۲) **تعدیلِ جعلی.** تشخیصِ تعدیل از گسستِ «قیمت پایه» فقط وقتی درست است که پایهٔ هر
   روز «خودِ پایانیِ دیروز» باشد. در سهام این برقرار است؛ در صندوق‌هایی که پایه را
   بازارگردان/NAV می‌گذارد خیر، و آنجا شمارشگر هر روز را تعدیل می‌شمرد:
   اعتماد4 = ۹۰۲ «تعدیل»، آبادا3 = ۱٬۲۳۱، آسود2 = ۳۴۲. فاکتورِ تجمعیِ آن‌ها کل
   تاریخِ گذشته را مقیاس می‌کرد و چارت را می‌شکست. ترمیم: درِ لنگر — اگر کسرِ روزهایی
   که پایه==پایانیِ دیروز است از ANCHOR_MIN پایین‌تر بود، هیچ رویدادی نمی‌دهیم و
   adjustSource صادقاً «base-not-anchored» می‌شود.

هر دو منطق از داخلِ روتِ شبکه‌دار بیرون کشیده شده تا همین‌جا، بدونِ شبکه و بدونِ
market.db، قابلِ آزمون باشد (گارد نباید به چیزی که CI ندارد وابسته باشد).

اجرا:  python dev/candle_source_fidelity_v1033.py
خروج: ۰ اگر همه درست، ۱ در غیر این صورت.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.chart import (ANCHOR_MIN, ADJ_TOL, _adjust_events_from_rows,  # noqa: E402
                       _parse_tsetmc_csv)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHART_PY = os.path.join(ROOT, "api", "chart.py")

HDR = "<TICKER>,<DTYYYYMMDD>,<FIRST>,<HIGH>,<LOW>,<CLOSE>,<VALUE>,<VOL>,<OPENINT>,<PER>,<OPEN>,<LAST>\n"

PASS = FAIL = 0


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  ok   %s" % what)
    else:
        FAIL += 1
        print("  FAIL %s%s" % (what, ("  ← " + detail) if detail else ""))


def csv_of(rows):
    """rows: [(yyyymmdd, first, high, low, close, vol, base, last)] → متنِ CSV."""
    out = [HDR.rstrip("\n")]
    for dt, first, hi, lo, c, vol, base, last in rows:
        out.append(f"19900101,{dt},{first:.2f},{hi:.2f},{lo:.2f},{c:.2f},"
                   f"1000000.00,{vol:.0f},20,D,{base:.2f},{last:.2f}")
    return "\n".join(out)


def days(n, start=20250101):
    """n روزِ کاریِ ساختگی با فرمت f"%Y%m%d" (بدون تقویم، فقط افزایش عددی امن)."""
    seq, y, m, d = [], start // 10000, (start // 100) % 100, start % 100
    for _ in range(n):
        seq.append(y * 10000 + m * 100 + d)
        d += 1
        if d > 28:
            d = 1
            m += 1
            if m > 12:
                m, y = 1, y + 1
    return seq


def anchored_series(n=60, price=1000.0, gap_at=None, gap_ratio=0.5):
    """سریِ عادی: پایهٔ هر روز == پایانیِ دیروز. gap_at یک گسستِ واقعی می‌سازد."""
    ds, rows, prev_close = days(n), [], price
    for i, dt in enumerate(ds):
        base = prev_close
        if gap_at == i:
            base = round(prev_close * gap_ratio)
        c = base + 5
        rows.append((dt, base + 1, base + 10, base - 2, c, 1000, base, c))
        prev_close = c
    return rows


def nav_fund_series(n=60, price=10000.0, step=0.0013):
    """صندوقی که پایه‌اش را NAV می‌گذارد: هر روز ~۰.۱۳٪ بالاتر از پایانیِ دیروز."""
    ds, rows, prev_close = days(n), [], price
    for dt in ds:
        base = round(prev_close * (1 + step))
        c = base + 1
        rows.append((dt, base, base + 1, base, c, 1000, base, c))
        prev_close = c
    return rows


def main():
    print("candle_source_fidelity_v1033")

    # ── ۱) ترمیمِ هندسه ────────────────────────────────────────────────────
    print("\n[۱] پایانیِ بیرونِ سایه")
    txt = csv_of([(20250101, 1973, 1973, 1973, 1917, 100, 1916, 1973),
                  (20250102, 1919, 1928, 1897, 1929, 100, 1917, 1900)])
    candles, volumes, all_rows = _parse_tsetmc_csv(txt)
    ck(len(candles) == 2, "both defective rows still become candles", str(len(candles)))
    a, b = candles
    ck(a["close"] == 1917 and a["low"] == 1917 and a["high"] == 1973,
       "close below the low widens the low instead of moving the close", str(a))
    ck(b["close"] == 1929 and b["high"] == 1929 and b["low"] == 1897,
       "close above the high widens the high instead of moving the close", str(b))
    ck(all(x["low"] <= x["open"] <= x["high"] and x["low"] <= x["close"] <= x["high"]
           for x in candles),
       "every served candle has its body inside its wicks")
    ck([c["close"] for c in candles] == [1917, 1929],
       "no close value was rewritten — the price series is untouched")
    ck(len(volumes) == len(candles), "one volume bar per candle")

    # ── ۲) روزِ بدونِ معامله حذف می‌شود ولی در محاسبهٔ تعدیل می‌ماند ───────
    print("\n[۲] روزِ بدونِ معامله")
    txt = csv_of([(20250101, 0, 0, 0, 14071, 0, 14071, 14070),
                  (20250102, 14072, 14073, 14071, 14072, 50, 14071, 14072)])
    candles, _, all_rows = _parse_tsetmc_csv(txt)
    ck(len(candles) == 1, "the H=L=0 day is not a candle", str(len(candles)))
    ck(len(all_rows) == 2, "but it still counts for the anchoring measurement",
       str(all_rows))

    # ── ۳) درِ لنگر: صندوقِ NAV-محور تعدیلِ جعلی نمی‌گیرد ──────────────────
    print("\n[۳] درِ لنگر")
    _, _, rows = _parse_tsetmc_csv(csv_of(nav_fund_series(60)))
    ev, anchored = _adjust_events_from_rows(rows)
    ck(not anchored, "a NAV-set base is detected as unanchored")
    ck(ev == [], "an unanchored instrument gets zero adjustment events, not ~58", str(len(ev)))

    _, _, rows = _parse_tsetmc_csv(csv_of(anchored_series(60)))
    ev, anchored = _adjust_events_from_rows(rows)
    ck(anchored, "an ordinary equity passes the gate")
    ck(ev == [], "and a clean series produces no events")

    _, _, rows = _parse_tsetmc_csv(csv_of(anchored_series(60, gap_at=30)))
    ev, anchored = _adjust_events_from_rows(rows)
    ck(anchored and len(ev) == 1, "one real base discontinuity → exactly one event",
       str(ev))
    ck(abs(ev[0]["ratio"] - 0.5) < 1e-6, "the ratio is base/prev-close", str(ev))

    # ── ۴) بی‌شواهد داوری نمی‌کند: سریِ کوتاه گیت را فعال نمی‌کند ──────────
    print("\n[۴] نمونهٔ کم")
    _, _, short = _parse_tsetmc_csv(csv_of(nav_fund_series(10)))
    ev, anchored = _adjust_events_from_rows(short)
    ck(anchored, "fewer than 20 day-pairs never disqualifies an instrument", str(len(short)))
    _, _, pairs20 = _parse_tsetmc_csv(csv_of(nav_fund_series(25)))
    ev, anchored = _adjust_events_from_rows(pairs20)
    ck(not anchored and ev == [], "25 days is enough evidence to refuse fabrication")

    # ── ۵) آستانه‌ها باید با هم بخوانند ────────────────────────────────────
    print("\n[۵] آستانه‌ها")
    ck(0.0 < ADJ_TOL < 0.05, "ADJ_TOL is a relative tolerance", str(ADJ_TOL))
    ck(0.5 <= ANCHOR_MIN < 1.0, "ANCHOR_MIN is a majority-of-days rule", str(ANCHOR_MIN))

    # ── ۶) روت باید از همین دو تابع استفاده کند، نه نسخهٔ دست‌دومِ منطق ────
    print("\n[۶] سیم‌کشی")
    src = io.open(CHART_PY, encoding="utf-8").read()
    ck("_parse_tsetmc_csv(r.text)" in src, "the route parses through the tested helper")
    ck("_adjust_events_from_rows(all_rows)" in src,
       "the route counts adjustments through the tested helper")
    ck(src.count('adjustSource') >= 2 and '"base-not-anchored"' in src,
       "adjustSource reports the honest reason instead of always claiming success")
    # Step 4: «shared parser» یعنی یکِ پیادۀ هندسه درِ کلِ برنامه — حالا
    # candle_contract.widen. چکِ قبلی رشتهٔ `max(hi, lo, o, c)` را می‌جست؛ آن رشته
    # به‌عمد ازِ chart.py رفت (دومین پیادۀ هم‌شکل بودنِ هندسه همان واگراییِ
    # ۷۶ روز high / ۱۰۹ روز low درِ _audit/candle_builder_divergence.py بود).
    ck("candle_contract.widen(" in src,
       "the geometry repair lives in the single shared rule (candle_contract.widen)")
    ck("max(hi, lo, o, c)" not in src,
       "NEGATIVE CONTROL: پیادۀ دست‌دومِ هندسه درِ chart.py برنگشته", "")

    print("\ncandle_source_fidelity_v1033: %d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
