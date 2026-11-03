# -*- coding: utf-8 -*-
"""dev/fts_wave_direction_v1125.py — گاردِ رأیِ مالک درِ موجِ فیبو (ادغامِ System 2)

رأیِ مالک (۱۴۰۵-۰۷-۲۸): «جهتِ موجِ System 1 بر مبنای دو Extreme بماند و
پرچمِ `provisional` از System 2 افزوده شود؛ این پرچم نباید خودکار جهت موج یا
رأی قیف FTS را تغییر دهد.»

این suite همان را می‌سنجد، نه سه‌خط resolve را:

  ۱) شاخۀ بی‌پیوت: موجِ min/max با `provisional: True` می‌آید و جهت از جایِ
     نسبی دو Extreme خوانده می‌شود (نه همیشه «up»).
  ۲) موجِ تأییدشده (پیوت هست): پرچم در leg نیست و در پاسخ `False` منتشر می‌شود.
  ۳) دادۀ ناکافی: سریِ کوتاه‌تر از دو کندل None می‌دهد (نه موجِ ساختگی).
  ۴) نقطۀ مرزیِ hi == lo: دو Extreme روی یک کندل ⇒ `lo_idx <= hi_idx` صادق است
     و موج «up» می‌ماند؛ یعنی حالتِ تساوی هیچ‌وقت بی‌صدا «down» نمی‌شود.
  ۵) برابریِ دو فرمول: روی هزاران سریِ تصادفی، `lo_idx <= hi_idx` (System 1) و
     `hi_i >= lo_i` (System 2) یک گزاره‌اند. پیش‌فرضِ ادغامِ «یک جهت باید انتخاب
     می‌شد» با این عدد سنجیده می‌شود، نه با متنِ کامنت.
  ۶) برابریِ رأی پیش/پس از پرچم: همان سری با `_fts_fib_leg` نسخه‌یِ System 1
     (بدون `provisional`) و نسخه‌یِ ادغام‌شده اجرا می‌شود و کلِ بلوکِ فیبو
     (`zone_33_40`، `zone_618_70`، `levels`، `retrace_*`) باید بیت‌به‌بیت یکی
     بماند. تنها اختلافِ مجاز خودِ کلیدِ `leg.provisional` است — چون `in_fib`
     در `api/chart.py:3484` از همین `in_zone` خوانده می‌شود، این سطر عملاً
     «رأی جابه‌جا نشد» را ثابت می‌کند.
  ۷) منفی‌کنترل: اگر جهت را به «همیشه up» برگردانیم (همان باگِ پیشین)، سنجه‌های
     بالا باید قرمز شوند — بی‌این، صفرِ قرمز معنایی ندارد.

اجرا بی‌شبکه و بی‌market.db است (سری‌های مصنوعیِ قطعی با seed).
"""
import datetime as dt
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.chart as CH  # noqa: E402

FAILS = []
CHECKS = 0


def ck(label, cond):
    global CHECKS
    CHECKS += 1
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAILS.append(label)


DAY0 = dt.date(2024, 1, 6)


def to_candles(closes):
    out = []
    for i, c in enumerate(closes):
        prev = closes[i - 1] if i else c
        o = prev
        out.append({
            "time": (DAY0 + dt.timedelta(days=i)).isoformat(),
            "open": round(o, 4), "high": round(max(o, c) * 1.012, 4),
            "low": round(min(o, c) * 0.988, 4), "close": round(c, 4),
            "volume": 1000 + 37 * i,
        })
    return out


# ── ۱ و ۴) شاخۀ بی‌پیوت ─────────────────────────────────────────────────
def test_provisional_branch():
    up = to_candles([100, 105, 110, 118, 124])          # کف اول، سقف آخر
    down = to_candles([124, 118, 110, 105, 100])        # سقف اول، کف آخر
    leg_up = CH._fts_fib_leg(up, [])
    leg_dn = CH._fts_fib_leg(down, [])
    ck("۱ موجِ بی‌پیوتِ صعودی: جهت up و provisional=True",
       leg_up["direction"] == "up" and leg_up.get("provisional") is True)
    ck("۱ موجِ بی‌پیوتِ نزولی: جهت down (نه همیشه up)",
       leg_dn["direction"] == "down" and leg_dn.get("provisional") is True)
    ck("۱ پایۀ موج از زودتر از دو Extreme آغاز می‌شود و به آخرین کندل می‌رسد",
       leg_up["start_idx"] == min(
           max(range(len(up)), key=lambda i: up[i]["high"]),
           min(range(len(up)), key=lambda i: up[i]["low"]))
       and leg_up["end_idx"] == len(up) - 1)

    # ۴) تساوی: دو Extreme روی یکِ کندل نشسته‌اند
    tie = [{"time": (DAY0 + dt.timedelta(days=i)).isoformat(),
            "open": 100.0, "high": h, "low": l, "close": 100.0, "volume": 10}
           for i, (h, l) in enumerate([(90.0, 80.0), (120.0, 70.0), (100.0, 90.0)])]
    hi_idx = max(range(len(tie)), key=lambda i: tie[i]["high"])
    lo_idx = min(range(len(tie)), key=lambda i: tie[i]["low"])
    ck("۴ زمینۀ آزمون: همان index هم سقف و هم کف است", hi_idx == lo_idx == 1)
    leg_tie = CH._fts_fib_leg(tie, [])
    ck("۴ در تساویِ hi == لو جهت «up» می‌ماند (down شدنِ بی‌صدا ممنوع)",
       leg_tie["direction"] == "up")


# ── ۲) موجِ تأییدشده پرچم نمی‌گیرد ────────────────────────────────────────
def test_confirmed_wave_has_no_flag():
    closes = [100, 112, 104, 120, 108, 126, 112, 130, 118, 124, 116, 128]
    candles = to_candles(closes)
    swings = CH._fts_swings(candles)
    if not swings:
        ck("۲ سریِ آزمون پیوت تولید کرد (وگرنه این سنجه بی‌محتواست)", False)
        return
    leg = CH._fts_fib_leg(candles, swings)
    ck("۲ موجِ تأییدشده کلیدِ provisional ندارد (پرچم فقط مالِ موجِ min/max است)",
       "provisional" not in leg)
    zones = CH._fts_fib_zones(candles, swings)
    ck("۲ در پاسخِ منتشرشده همان False خوانده می‌شود",
       zones["leg"]["provisional"] is False)
    zones_np = CH._fts_fib_zones(candles, [])
    ck("۲ در موجِ بی‌پیوت پاسخ True منتشر می‌کند",
       zones_np["leg"]["provisional"] is True)


# ── ۳) دادۀ ناکافی ───────────────────────────────────────────────────────
def test_insufficient_data():
    ck("۳ بی‌کندل ⇒ None", CH._fts_fib_leg([], []) is None)
    ck("۳ یکِ کندل ⇒ None (دوExtreme لازم است)",
       CH._fts_fib_leg(to_candles([100]), []) is None)
    ck("۳ بلوکِ فیبو هم بی‌داده None می‌دهد، نه کمربندِ ساختگی",
       CH._fts_fib_zones(to_candles([100]), []) is None)


# ── ۵) برابریِ دو فرمول ──────────────────────────────────────────────────
def test_the_two_formulas_are_one_predicate():
    rnd = random.Random(1125)
    n_eq = n_tot = 0
    for _ in range(4000):
        m = rnd.randint(2, 60)
        candles = to_candles([rnd.uniform(50, 500) for _ in range(m)])
        s1 = "up" if min(range(m), key=lambda i: candles[i]["low"]) <= \
            max(range(m), key=lambda i: candles[i]["high"]) else "down"
        s2 = "up" if max(range(m), key=lambda i: candles[i]["high"]) >= \
            min(range(m), key=lambda i: candles[i]["low"]) else "down"
        n_tot += 1
        n_eq += (s1 == s2)
    ck("۵ در %d سریِ تصادفی، جهتِ System 1 و System 2 در %d/%d یکی است" % (n_tot, n_eq, n_tot),
       n_eq == n_tot)


# ── ۶) برابریِ رأی پیش/پس ازِ افزودنِ پرچم ────────────────────────────────
def test_flag_moves_no_verdict():
    rnd = random.Random(7)
    series = []
    for _ in range(120):
        m = rnd.randint(3, 40)
        series.append(to_candles([rnd.uniform(50, 500) for _ in range(m)]))
    # سریِ صعودیِ پیوسته (همان شکلِ «فولاد» #161) دستی افزوده می‌شود
    series.append(to_candles([100 + i * 3 for i in range(25)]))
    series.append(to_candles([300 - i * 3 for i in range(25)]))

    real_leg = CH._fts_fib_leg

    def legacy_leg(candles, swings):
        """نسخۀ System 1، پیش ازِ پرچم: همان dict بی‌`provisional`."""
        out = dict(real_leg(candles, swings) or {})
        out.pop("provisional", None)
        return out or None

    diff_keys = set()
    same = moved = 0
    for candles in series:
        for swings in ([], CH._fts_swings(candles)):
            CH._fts_fib_leg = real_leg
            after = CH._fts_fib_zones(candles, swings)
            CH._fts_fib_leg = legacy_leg
            before = CH._fts_fib_zones(candles, swings)
            if after is None or before is None:
                continue
            a = dict(after)
            b = dict(before)
            la, lb = a.pop("leg", {}), b.pop("leg", {})
            la_p, lb_p = la.pop("provisional", None), lb.pop("provisional", None)
            if a == b and la == lb:
                same += 1
            else:
                moved += 1
                for k in set(a) | set(b):
                    if a.get(k) != b.get(k):
                        diff_keys.add(k)
                if la != lb:
                    diff_keys.add("leg(بی‌پرچم)")
            if bool(la_p) != bool(lb_p):
                diff_keys.add("provisional_flag")
    CH._fts_fib_leg = real_leg
    ck("۶ بلوکِ فیبو در %d/%d حالت بی‌تغییر ماند (پرچم تنها اختلافِ مجاز است)" % (same, same + moved),
       moved == 0)
    ck("۶ کلیدِ کمربند/سطحی که جابه‌جا شده باشد: %s" % (sorted(diff_keys - {"provisional_flag"}) or "هیچ"),
       not (diff_keys - {"provisional_flag"}))


# ── ۷) منفی‌کنترل: سنسور زنده است ────────────────────────────────────────
def test_negative_control():
    """باگِ پیشین («همیشه up») برگردد ⇒ همان سنجه‌ها باید قرمز شوند."""
    real_leg = CH._fts_fib_leg
    try:
        def always_up(candles, swings):
            out = dict(real_leg(candles, swings) or {})
            if out:
                out["direction"] = "up"
            return out or None
        CH._fts_fib_leg = always_up
        down = to_candles([124, 118, 110, 105, 100])
        ck("۷ منفی‌کنترل: با جهتِ «همیشه up» سنجۀ ۱ باید قرمز شود (سنسور کور نیست)",
           CH._fts_fib_leg(down, [])["direction"] == "up")
        rnd = random.Random(1125)
        mismatch = 0
        for _ in range(400):
            m = rnd.randint(2, 40)
            candles = to_candles([rnd.uniform(50, 500) for _ in range(m)])
            got = CH._fts_fib_leg(candles, [])["direction"]
            want = "up" if min(range(m), key=lambda i: candles[i]["low"]) <= \
                max(range(m), key=lambda i: candles[i]["high"]) else "down"
            mismatch += (got != want)
        ck("۷ منفی‌کنترل: با همان باگ، مقایسۀ فرمول‌ها نابه‌جایی می‌بیند", mismatch > 0)
    finally:
        CH._fts_fib_leg = real_leg
    ck("۷ پسِ بازگردانی، نسخۀ واقعی دوباره down می‌دهد",
       CH._fts_fib_leg(to_candles([124, 118, 110, 105, 100]), [])["direction"] == "down")


if __name__ == "__main__":
    for fn in (test_provisional_branch, test_confirmed_wave_has_no_flag,
               test_insufficient_data, test_the_two_formulas_are_one_predicate,
               test_flag_moves_no_verdict, test_negative_control):
        print("── %s" % fn.__name__)
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            ck("%s استثنا داد: %s" % (fn.__name__, str(e)[:120]), False)
    print("\nنتیجه: %d سنجه، %d خطا" % (CHECKS, len(FAILS)))
    if FAILS:
        for f in FAILS:
            print("  ✗ " + f)
    raise SystemExit(1 if FAILS else 0)
