# -*- coding: utf-8 -*-
"""dev/structure_engine3_compare_v1.py — موتورِ سوم در برابرِ موتورِ اول (مرحلۀ ۷)

ادعای مأموریت: «تفاوتِ الگوریتمیِ محاسبه‌پذیر، نه بازمصرفِ فراکتال». این harness
همان سریِ کندل را به هر دو موتور می‌دهد و می‌سنجد:
  • تعدادِ پیوت و واژگونیِ ترتیب (engine1: فراکتال k=3 با تأیید idx+3؛
    engine3: ZigZagِ آستانه‌دار با تأییدِ «زمانِ برگشتِ کافی»)
  • تطابقِ پیوت‌ها در پنجرۀ ±۳ کندل
  • برچسب‌های ساختار و رویدادهای CHoCH در هر دو
  • خاصیتِ ضدِ repaint: هیچ پیوتِ تأییدشدۀ engine3 با داده‌هایِ بیشتر جابه‌جا
    نمی‌شود (prefix-stability) — بی‌این، «مقایسه» یعنی مقایسهٔ دو ناپایداری.
گاردِ صحتِ الگوریتمی: دست‌کم روی یک سری، فهرستِ پیوت دو موتور باید *متفاوت*
باشد؛ اگر همیشه یکی بود، یعنی engine3 فقط نامِ تازهٔ همان فراکتال است.

مصرفِ داده: بی‌شبکه و بی‌market.db — هر دو سریِ مصنوعی (ترنجِ قطعی + random-walk
با seedِ ثابت) و در صورت دسترسی، حداکثر ۶ نمادِ محلی از بانکِ کندل. نبودِ بانک
خطا نیست؛ در خروجی اعلام می‌شود (UNVERIFIED روی دادهٔ واقعی، نه ادعایِ سبز).
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.chart as CH  # noqa: E402
import structure_engine3 as E3  # noqa: E402

FAILS = []


def ck(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAILS.append(label)


def tri_closes(amp=0.18, leg=8, n=120, base=100.0):
    out, up = [], True
    p = base
    for i in range(n):
        step = amp / leg if up else -amp / 1.3
        p = max(1.0, p * (1.0 + step))
        out.append(p)
        if i % leg == leg - 1:
            up = not up
    return out


def walk_closes(seed=42, n=160, base=100.0):
    rng = random.Random(seed)
    out, p = [], base
    drift = 0.0
    for _ in range(n):
        drift = 0.9 * drift + rng.gauss(0.0, 0.012)
        p = max(1.0, p * (1.0 + drift))
        out.append(p)
    return out


def to_candles(closes):
    c = []
    for i, cl in enumerate(closes):
        prev = closes[i - 1] if i else cl
        hi, lo = max(prev, cl) * 1.004, min(prev, cl) * 0.996
        c.append({"time": f"d{i:04d}", "open": prev, "high": hi, "low": lo, "close": cl})
    return c


def e1_pivots(candles):
    sw = CH._fts_swings(candles, k=CH._FTS_SWING_K)
    return sw


def match_rate(p1, p3, window=3):
    """درصدِ پیوت‌هایِ engine1 که یک پیوتِ engine3 در پنجرۀ ±window دارند."""
    if not p1:
        return None
    idx3 = [p["idx"] for p in p3]
    hit = sum(1 for p in p1 if any(abs(q - p["idx"]) <= window for q in idx3))
    return hit / len(p1)


def main():
    series = {
        "tri-amp18": to_candles(tri_closes()),
        "walk-42": to_candles(walk_closes(42)),
        "walk-7": to_candles(walk_closes(7)),
    }
    diverged_any = False
    rows = []
    for name, candles in series.items():
        s1 = e1_pivots(candles)
        z3 = E3.zigzag(candles)
        p3 = z3["pivots"]
        st3 = E3.label_structure(p3)
        ids1 = sorted(p["idx"] for p in s1)
        ids3 = sorted(p["idx"] for p in p3)
        rows.append((name, len(ids1), len(ids3), match_rate(s1, p3), len(st3["choch"])))
        rate = rows[-1][3]
        rate_s = "—" if rate is None else ("%.0f%%" % (rate * 100))
        print(f"\n── ۱) سری «{name}» — مقایسۀ کمّی دو موتور ──")
        print(f"  engine1 (فراکتال k={CH._FTS_SWING_K}): {len(ids1)} پیوت {ids1[:8]}…")
        print(f"  engine3 (ZigZag ATR٪): {len(ids3)} پیوت {ids3[:8]}…")
        print(f"  تطابقِ ±۳ کندل: {rate_s} — CHoCH موتور سوم: {rows[-1][4]}")
        if ids1 != ids3:
            diverged_any = True
        # ضدِ repaint در موتورِ سوم: confirm همواره پس از وقوع
        ck(f"anti-repaint سری «{name}»: confirm_idx > idx برای همهٔ پیوت‌ها",
           all(p["confirm_idx"] > p["idx"] for p in p3))
        # prefix-stability: برشِ آینده، گذشتهٔ تأییدشده را تکذیب نمی‌کند
        cut = len(candles) // 2
        half = E3.zigzag(candles[:cut])["pivots"]
        pref = [p for p in p3 if p["confirm_idx"] < cut]
        ck(f"prefix-stability سری «{name}»: پیوتِ تأییدشده با دادهٔ بیشتر تکذیب نمی‌شود",
           [p["idx"] for p in half] == [p["idx"] for p in pref])

    ck("تفاوتِ الگوریتمی: دست‌کم روی یک سریِ مصنوعی فهرستِ پیوت دو موتور جداست",
       diverged_any)

    # ── ۲) نمادهایِ واقعی (در صورت دسترس بودنِ بانکِ کندل) ──
    print("\n── ۲) نمادهایِ واقعی از بانکِ محلی ──")
    symbols = []
    try:
        import sqlite3
        db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "market.db")
        if os.path.exists(db):
            conn = sqlite3.connect(db)
            try:
                symbols = [r[0] for r in conn.execute(
                    "SELECT symbol FROM price_history GROUP BY symbol "
                    "HAVING COUNT(*) >= 120 ORDER BY COUNT(*) DESC LIMIT 6")]
            finally:
                conn.close()
    except Exception as e:
        print(f"  (بانک خوانده نشد: {e})")
    if not symbols:
        print("  UNVERIFIED روی دادهٔ واقعی: بانکِ کندل در دسترس نیست — "
              "مقایسۀ بالا فقط روی سریِ مصنوعی اجرا شد و در گزارش تکرار می‌شود.")
    else:
        real_diff = 0
        for sym in symbols:
            try:
                candles = CH._fts_analysis_series(sym)[0]
            except Exception:
                continue
            if len(candles) < 60:
                continue
            s1 = e1_pivots(candles)
            p3 = E3.zigzag(candles)["pivots"]
            ids1 = sorted(p["idx"] for p in s1)
            ids3 = sorted(p["idx"] for p in p3)
            rate = match_rate(s1, p3)
            rate_s = "—" if rate is None else ("%.0f%%" % (rate * 100))
            real_diff += 0 if ids1 == ids3 else 1
            print(f"  {sym}: engine1={len(ids1)} engine3={len(ids3)} تطابق={rate_s}")
        if real_diff:
            ck("روی دادهٔ واقعی هم حداقل یک نماد با فهرستِ پیوت جدا وجود دارد", True)
        else:
            print("  (روی نمادهایِ بررسی‌شده فهرست‌ها یکسان بود — ادعایِ تفاوتِ "
                  "الگوریتمی فقط با سریِ مصنوعی اثبات شده است)")

    print()
    if FAILS:
        print(f"STRUCTURE-ENGINE3 COMPARE FAILED: {len(FAILS)}")
        for f in FAILS:
            print("  -", f)
        return 1
    print("STRUCTURE-ENGINE3 COMPARE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
