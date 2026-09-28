#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/tape_filters_v1034.py — پنج فیلترِ تابلو باید عینِ فرمولِ جزوه باشند.

چرا این گارد متولد شد (TAPE-F + JET-BREAK + HIST-SRC، ۲۶ سپتامبر ۲۰۲۶):

۱) **«داده نبودن» بی‌صدا یعنی «قبول».** هر پنج شرطِ frontend به شکلِ
   ``if (cfg.x > 0 && typeof r.y === 'number')`` نوشته شده بود؛ اگر y نبود،
   گیت رد می‌شد و ردیف **قبول** می‌ماند. رویِ تابلوی واقعی ۲۳ سپتامبر:
   ۶۷۱ ردیف از ۳٬۸۴۵ «جت» خورد، در حالی که همان فیلتر رویِ خودِ TSETMC یک
   ردیف می‌دهد. مقایسهٔ عددی در tools/tape_flag_yield.py.

۲) **جت سقف را با «پایانی» می‌سنجید و فقط یک نقطه را.** جزوه هشت نقطه
   ([ih][2] تا [ih][59]) را می‌خواهد و مقایسه با «آخرین» است -- جت یعنی
   «همین حالا از مقاومت عبور کرد»، نه «دیروز عبور کرده بود».

۳) **منبعِ تاریخچه اشتباه بود.** حجمِ مبنا و سقف‌ها فقط از price_history
   خوانده می‌شد؛ آن جدول تنها برایِ نمادهایی نوشته می‌شود که یک‌بار باز شده
   باشند و حجمِ انبوه‌اش از ۱۴۰۵/۰۶/۰۱ (۲۰۲۶-۰۸-۲۳) نرسیده است. یعنی
   «میانگین ۳۰ روزه» برایِ صدها نماد یک‌ماهه کهنه و برایِ ۴٬۲۰۰ نماد غایب
   بود (۱۰۸۹ از ۵۳۰۲ نشسته بودند). ترمیم: اتحادِ daily_prices با
   price_history -- پوششِ حجمِ مبنا از ۳۰٪ به ۹۹٪ تابلو رسید.

۴) **نامِ متغیرهایِ فایل را از خودِ سایت نگرفته بودیم.** مالک بارِ دوم گفت
   «نتایجِ TSE با جدولِ ما فرق دارد» (۱۴۰۵-۰۷-۰۵). `ExecFilter` درِ باندلِ
   خودِ tsetmc.com نشان داد که درِ کف‌روبی سه از چهار قید معناشان عوض است:
   `tmin` آستانۀِ مجازِ پایین است نه کفِ نشست، `zd1`/`qd1` سفارشِ سطرِ اولِ
   خریدند نه حجم/تعدادِ نشستِ پیش، و `plp` درصدِ «آخرین» است نه پایانی.
   همچنین `[ih][k]` با rn = k+1 می‌نشیند (روزنۀِ منتشرشدۀِ آخر = [ih][0]) و
   `[ih]` امروزِ بی‌نهایه را داخلِ خودش ندارد. سنجشِ همان روز: مرجعِ TSETMC
   ۳۱ ردیفِ کف‌روبی، جدولِ ما ۶۳ ردیف، تقریباً بدونِ اشتراک.

۵) **عمرِ [ih] را از شمارِ ردیفِ خودمان نمی‌شود فهمید.** مالک بارِ سوم هم
   گفت نتایج فرق دارد (۱۴۰۵-۰۷-۰۵ عصر). فرمول‌ها درست شده بودند و مرجعِ
   زنده رویِ ۲۵۰ نماد فقط دو اختلاف می‌داد -- هر دو از یک جنس: نمادی مثلِ
   خگلپا شصت نشست درِ آرایۀِ سایت دارد ولی درِ بانکِ ما هجده ردیف (روزهایِ
   بی‌معامله را هیچ‌کس برایِ او ننوشته)، پس درِ «کمتر از سی نشست» بسته
   می‌ماند و فیلترهایِ حجمی خاموش. درمان: پنجره از `GetClosingPriceDailyAllInst`
   (منبعِ خودِ سایت) درِ جدولِ `tape_history` نوشته می‌شود.

گارد نه به شبکه نیاز دارد نه به market.db (قاعدهٔ مخزن: گارد نباید به
چیزی که CI ندارد وابسته باشد)؛ همه‌چیز رویِ چارچوبِ مصنوعی سنجیده می‌شود.
بخشِ [۸] تنها پیوندِ نامِ ستون‌ها را می‌کاود -- بی‌آن، `allowed_min AS tmin`
درِ SQL و `allowed_min` درِ فیلتر می‌توانند ماه‌ها بی‌صدا با هم نجنگند.

اجرا:  python dev/tape_filters_v1034.py
خروج: ۰ اگر همه درست، ۱ در غیر این صورت.
"""
import io
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tape_flags import (CLOCK_DELTA, HIST_MIN_SESSIONS, JET_BUYER_POWER,  # noqa: E402
                        JET_LADDER, JET_MIN_TRADES, JET_TRADES, JET_VOL_MULT,
                        LOW_BASE_SESSIONS, NOQTEH_MAX_DIST, ROOBI_MAX_CHANGE,
                        ROOBI_QD1_MIN, ROOBI_ZD1_MIN, SUSP_TRADES, SUSP_VOL_MULT,
                        VOL_BASE_SESSIONS, apply_tape_flags, formula_vol_ratio,
                        formula_volume_base, history_sessions,
                        resistance_ladder_high, vol_ratio)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKET_PY = os.path.join(ROOT, "api", "market.py")
CHART_PY = os.path.join(ROOT, "api", "chart.py")
FLAGS_PY = os.path.join(ROOT, "tape_flags.py")
SPEC = os.path.join(ROOT, "fts_terminal.spec")
TS_MATH = os.path.join(ROOT, "frontend", "src", "features", "market", "lib", "tapeMath.ts")
TS_ALGO = os.path.join(ROOT, "frontend", "src", "features", "market", "lib", "tapeAlgorithms.ts")
ROW_TS = os.path.join(ROOT, "frontend", "src", "shared", "types", "marketRow.ts")

PASS = FAIL = 0


def ck(cond, what, got=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {what}")
    else:
        FAIL += 1
        print(f"  FAIL {what}" + (f"  -> {got}" if got else ""))


def row(**over):
    """یک ردیفِ تابلو که هر پنج فیلتر را با هم رد می‌کند، بعد یک‌به‌یک تغییرش می‌دهیم.

    نامِ ستون‌ها عیناً نام‌هایی‌اند که `api/market.py` به `apply_tape_flags` می‌دهد
    (تبدیلِ `allowed_min AS tmin` و …). اگر این‌جا نامی با ستونِ واقعیِ کوئری فرق
    بگیرد، فیلتر بی‌صدا «داده نیست» می‌شمارد و صفر ردیف می‌دهد — همان چیزی که
    یک‌بار با `f_roobi` اتفاق افتاد و بخشِ [۸] همین گارد می‌گیرد.

    مبناءِ سی‌نشستیِ این ردیف: Σ[ih][0..29] = ۳۰M روی ۳۰ نشست = ۱M، یعنی نسبتِ
    tvolِ ۴M برابرِ ۴٫۰×. «امروز» درِ Σ نیست؛ درِ TSETMC هم تا پیش از نهایه
    درِ [ih] نیست.
    """
    base = {
        "symbol": "آزمون", "p_closing": 1000.0, "p_last": 1025.0, "p_min": 1025.0,
        "percent_change": 2.5, "percent_last": 4.6, "price_yesterday": 980.0,
        "q_tot_tran": 4_000_000.0, "tvol": 4_000_000.0, "z_tot_tran": 120.0,
        "month_avg_vol": 1_000_000.0, "prev_day_vol": 2_000_000.0,
        "prior30_vol": 30_000_000.0, "hist_sessions": 60.0,
        "min_low_29": 995.0,
        "buy_i_vol": 2_000_000.0, "buy_count_i": 100.0,
        "sell_i_vol": 1_000_000.0, "sell_count_i": 100.0,
        "min30_low": 995.0,
        # کف‌روبی: آستانۀ مجاز، تعدادِ سفارشِ سطرِ اولِ خرید و حجمِ همان سطر
        "tmin": 900.0, "tmax": 1100.0, "buy_q1_cnt": 8.0, "buy_q1_vol": 250_000.0,
    }
    for k in JET_LADDER:
        base[f"h{k}_max"] = 900.0
    base.update(over)
    return pd.DataFrame([base])


def flags(**over):
    return apply_tape_flags(row(**over)).iloc[0]


def one(col, **over):
    return bool(flags(**over)[col])


def roobi(**over):
    """ردیفِ کف‌روبی: آخرینِ چسبیده به آستانۀ مجازِ پایین و درصدِ آخرینِ منفی.

    با ردیفِ مثبتِ جت نمی‌شود ساخت، چون `plp < -1` و `pl >= pc` با هم محال‌اند.
    """
    base = {"p_last": 900.0, "tmin": 900.0, "percent_last": -2.0, "percent_change": -3.0}
    base.update(over)
    return bool(apply_tape_flags(row(**base)).iloc[0]["f_roobi"])


def read(path):
    return io.open(path, encoding="utf-8").read()


def main():
    # ── ۱) اعدادِ جزوه باید همان بمانند ────────────────────────────────────
    print("\n[۱] ثابت‌هایِ جزوه")
    ck(CLOCK_DELTA == 0.02, "الگوی ساعت: pl >= pc*1.02", str(CLOCK_DELTA))
    ck(JET_VOL_MULT == 3.0 and SUSP_VOL_MULT == 3.0, "جت و حجم مشکوک: tvol > 3*avg30")
    ck(JET_BUYER_POWER == 1.5, "جت: خرید حقیقی >= 1.5 × فروش حقیقی")
    ck(tuple(JET_LADDER) == (2, 5, 9, 19, 29, 39, 49, 59),
       "پلکان جت دقیقاً [ih][2..59] است، بدون [ih][1]", str(JET_LADDER))
    ck(ROOBI_MAX_CHANGE == -1.0 and ROOBI_QD1_MIN == 100 and ROOBI_ZD1_MIN == 1,
       "کف‌روبی: plp < -1، zd1 > 1 و qd1 > 100")
    ck(NOQTEH_MAX_DIST == 3.0 and SUSP_TRADES == 50, "نقطه‌زنی فاصله < 3 و حجم مشکوک tno > 50")
    # رأیِ ۱۸ (۱۴۰۵-۰۷-۰۴): فیلترِ تابلو عینِ فایل است، پس ``tno > 100`` در جت.
    ck(JET_TRADES == 1 and JET_MIN_TRADES == 100, "جت: tno > 1 و tno > 100، عینِ فایل")
    ck(VOL_BASE_SESSIONS == HIST_MIN_SESSIONS == 30,
       "پنجرۀ فایل سی **نشست** است و همان سی نشست برایِ سنجش لازم است")
    ck(LOW_BASE_SESSIONS == 29, "کفِ فایل (کمینۀِ [ih][0..28]) بیست‌ونُه نشست می‌خواهد")

    # ── ۲) هر پنج فیلتر رویِ ردیفِ واجدِ شرایط قبول می‌شوند ────────────────
    print("\n[۲] حالتِ مثبتِ هر پنج فیلتر")
    f = flags()
    for col in ("f_clock", "f_susp", "f_jet", "f_noqteh"):
        ck(bool(f[col]), f"{col} ردیفِ واجدِ شرایط را قبول کند")
    # کف‌روبی شرطِ متضاد دارد (درصدِ منفی و نشستنِ رویِ کف)، پس ردیفِ خودش را
    # می‌خواهد -- یکی کردنشان یعنی یکی از دو فیلتر همیشه می‌بازد.
    ck(roobi(), "f_roobi ردیفِ واجدِ شرایط را قبول کند")

    print("\n[۳] تک‌تکِ شروط، مردودکننده‌اند")
    # A) الگوی ساعت
    ck(not one("f_clock", p_last=1019.0), "ساعت: دلتای ۱٫۹٪ زیر ۲٪ است")
    ck(one("f_clock", p_last=1020.0), "ساعت: دقیقاً ۲٪ قبول است (>=)")
    ck(not one("f_clock", z_tot_tran=30), "ساعت: tno > 30 اکید است")
    # مبناءِ فایل «Σ[ih][0..29] ÷ تعدادِ نشست» است و امروز داخلِ Σ نیست؛ برایِ
    # نسبتِ درستِ ۱٫۰ باید Σ برابرِ ۳۰×tvol شود.
    ck(not one("f_clock", prior30_vol=120_000_000.0), "ساعت: حجمِ برابرِ مبناء قبول نیست (>)")
    # B) حجم مشکوک
    ck(abs(float(formula_vol_ratio(row(prior30_vol=40_000_000.0)).iloc[0]) - 3.0) < 1e-9,
       "مبناءِ فایل درست ساخته می‌شود: Σ[ih][0..29] ÷ ۳۰")
    ck(not one("f_susp", prior30_vol=40_000_000.0), "حجم مشکوک: دقیقاً ۳× مبناء کافی نیست (>)")
    ck(not one("f_susp", z_tot_tran=50), "حجم مشکوک: tno > 50 اکید است")
    # C) جت
    ck(not one("f_jet", p_last=899.0, p_closing=890.0), "جت: آخرینِ زیرِ مقاومت قبول نیست")
    ck(one("f_jet", p_last=901.0, p_closing=900.0), "جت: یک ریال بالاتر از مقاومت قبول است")
    ck(not one("f_jet", p_last=900.0, p_closing=880.0), "جت: آخرینِ دقیقاً رویِ مقاومت مردود است (>)")
    ck(not one("f_jet", p_last=880.0, p_closing=870.0),
       "جت با پایانیِ زیرِ مقاومت ولی آخرینِ زیرِ مقاومت مردود است")
    ck(not one("f_jet", sell_i_vol=3_000_000.0), "جت: قدرت خریدار زیر ۱٫۵× مردود است")
    ck(not one("f_jet", percent_last=-0.5),
       "جت: (plp) درصدِ «آخرین» است؛ با آخرینِ پایین‌ترِ دیروز مردود، هرچند پایانی مثبت باشد")
    ck(one("f_jet", percent_change=-3.0),
       "جت درصدِ پایانی (pcp) را نمی‌خواند؛ فایل آن را درِ شرط ندارد")
    ck(not one("f_jet", percent_last=None), "جت: plp تهی مردود است")
    ck(not one("f_jet", p_last=999.0), "جت: آخرینِ زیرِ پایانی مردود است")
    ck(not one("f_jet", z_tot_tran=1), "جت: tno > 1 اکید است")
    ck(not one("f_jet", z_tot_tran=100), "جت: tno > 100 (رأیِ ۱۸، عینِ فایل) مردود است")
    ck(one("f_jet", z_tot_tran=101), "جت: یکی بالاتر از ۱۰۰ قبول است")
    # D) کف‌روبی -- چهار قیدِ فایل، و هیچ‌کدام جایِ دیگری را نمی‌گیرد
    ck(not roobi(p_last=899.0), "کف‌روبی: آخرین باید دقیقاً روی آستانۀِ مجازِ پایین باشد")
    ck(not roobi(tmin=899.0), "کف‌روبی: آستانه جابه‌جا شد، شرطِ pl == tmin می‌شکند")
    ck(not roobi(tmin=0.0), "کف‌روبی: آستانۀ صفر (بندِ بی‌معتبر) «رویِ کف» شمارده نمی‌شود")
    ck(not roobi(percent_last=-1.0), "کف‌روبی: plp < -1 اکید است")
    ck(not roobi(buy_q1_cnt=1.0), "کف‌روبی: zd1 > 1 اکید است (یک سفارشِ صف کافی نیست)")
    ck(roobi(buy_q1_cnt=2.0), "کف‌روبی: دو سفارش از یک کافی است")
    ck(not roobi(buy_q1_vol=100.0), "کف‌روبی: qd1 > 100 اکید است")
    # منفیِ کنترل‌ها: سه ستونی که نسخهٔ پیشین *به‌جای* این قیدها می‌خواند. جابه‌جا
    # کردنشان نباید رأی را عوض کند؛ اگر گاردی روزی این سه را سبزِ «غیّرأی» دید،
    # یعنی یکی از قیدها دوباره به دادهٔ اشتباه وصل شده است.
    ck(roobi(p_min=700.0), "کف‌روبی کفِ همین نشست (p_min) را نمی‌خواند (تصحیحِ tmin)")
    ck(roobi(prev_day_vol=1.0), "کف‌روبی حجمِ نشستِ پیش را نمی‌خواند (تصحیحِ zd1)")
    ck(roobi(z_tot_tran=3.0) == roobi(z_tot_tran=2_000.0),
       "کف‌روبی به تعدادِ معاملاتِ امروز بی‌تفاوت است (تصحیحِ qd1)")
    ck(roobi(percent_change=+5.0) is True and roobi(percent_last=-2.0),
       "کف‌روبی با plpِ خودِ «آخرین» سنجیده می‌شود، نه درصدِ پایانی")
    # E) نقطه‌زنی
    ck(not one("f_noqteh", min_low_29=969.0), "نقطه‌زنی: فاصلۀِ ۳٫۱٪ از کفِ فایل مردود است")
    ck(not one("f_noqteh", min_low_29=0.0),
       "نقطه‌زنی: کفِ صفرِ نشستِ بی‌معامله کلِ ردیف را رد می‌کند (MinPriceOfMonth() != 0)")
    ck(one("f_noqteh", min30_low=800.0),
       "ستونِ نمایشیِ min30_low درِ نقطه‌زنی نیست (کفِ فایل = [ih][0..28])")
    # سنجشِ زنده ۱۴۰۵-۰۷-۰۷ با تابلویِ خودِ سایت: نمادی که پایانیِ امروز زیرِ
    # کفِ پنجره نشسته (فاصلۀِ منفی) درِ فایل «نقطه‌زنی» می‌نشیند؛ کرانِ پایین
    # رأیِ مالک نبود و ردیف‌هایِ درست را می‌کُشت.
    ck(one("f_noqteh", min_low_29=1100.0),
       "نقطه‌زنی: کف‌شکنی (فاصلۀِ ‎−۱۰٪) قبول است — فایل فقط سقف می‌گذارد")
    ck(not one("f_noqteh", min_low_29=None),
       "نقطه‌زنی بی‌کفِ فایل سنجیده نمی‌شود")

    # ── ۴) نبودنِ داده هیچ‌وقت قبول نیست ───────────────────────────────────
    print("\n[۴] نبودنِ داده = رد، نه قبول")
    NULLS = {
        # مبناءِ فایل: هر چه از سی **نشستِ** پنجره کم باشد سنجش ممکن نیست.
        "prior30_vol": ("f_clock", "f_susp", "f_jet", "f_noqteh"),
        "hist_sessions": ("f_clock", "f_susp", "f_jet", "f_noqteh"),
        "tvol": ("f_clock", "f_susp", "f_jet", "f_noqteh"),
        "z_tot_tran": ("f_clock", "f_susp", "f_jet", "f_noqteh"),
        "p_last": ("f_clock", "f_jet", "f_roobi"),
        "p_closing": ("f_clock", "f_jet", "f_noqteh"),
        "percent_last": ("f_jet", "f_roobi"),
        "tmin": ("f_roobi",),
        "buy_q1_cnt": ("f_roobi",),
        "buy_q1_vol": ("f_roobi",),
        "min_low_29": ("f_noqteh",),
    }
    for col, dependents in NULLS.items():
        for fname in dependents:
            # کف‌روبی ردیفِ منفیِ خودش را دارد؛ با ردیفِ مثبتِ پیش‌فرض آزمون
            # صوری می‌شد (همیشه مردود، چه داده باشد چه نه).
            test = roobi(**{col: None}) if fname == "f_roobi" else one(fname, **{col: None})
            ck(not test, f"{fname} با {col} تهی مردود است")
    # نمادِ کم‌سابقه: فایل [ih][29] و [ih][59] را صریح می‌خواهد و خودِ
    # ExecFilter بیرونِ آرایه استثنا می‌دهد → ردیف داوری نمی‌شود. «بر تعدادِ
    # موجود تقسیم کن» همان چیزی بود که ۵۵ ردیفِ جعلی می‌ساخت.
    ck(not one("f_susp", hist_sessions=29.0), "بیست‌ونُه نشست → حجم مشکوک سنجیده نمی‌شود")
    ck(one("f_susp", hist_sessions=30.0), "سی نشست → مبناء دقیقاً Σ÷۳۰، همان عددِ فایل")
    ck(not one("f_noqteh", hist_sessions=28.0), "بیست‌وهشت نشست → کفِ فایل سنجیده نمی‌شود")
    ck(one("f_noqteh", hist_sessions=30.0),
       "سی نشست → هم کمینۀِ [ih][0..28] کامل است و هم مبناء")
    ck(one("f_jet", hist_sessions=59.0) is False,
       "جت: پنجاه‌ونهشت نشست، [ih][59] را نمی‌سنجد (سایت هم استثنا می‌دهد)")
    ck(one("f_jet", hist_sessions=60.0), "جت: با شصت نشستِ شناخته‌شده سنجیده می‌شود")
    # ماه‌مبناء فقط ستونِ نمایش است؛ درِ هیچ فیلتری نیست.
    for fname in ("f_clock", "f_susp", "f_jet", "f_noqteh"):
        ck(one(fname, month_avg_vol=None), f"{fname} به month_avg_volِ نمایشی وابسته نیست")
    # دو مبناء، دو معنا — این همان جایی است که ۵۵ ردیفِ جعلی از آمد.
    wide = row(prior30_vol=120_000_000.0)
    ck(pd.isna(formula_vol_ratio(row(hist_sessions=4.0)).iloc[0]),
       "زیرِ سی نشست مبناء NaN است (نسنج، نه عددِ جعلی)")
    ck(abs(float(formula_vol_ratio(wide).iloc[0]) - 1.0) < 1e-9,
       "مبناء همیشه Σ÷۳۰ است، هر چند ردیفِ معامله‌شده کمتر باشد (Σ÷۱۲ نه)")
    ck(float(vol_ratio(wide).iloc[0]) > 3.0,
       "مبناءِ نمایشی همان ردیف را «بیش از ۳×» می‌خواند؛ پس نباید درِ فیلتر باشد")
    ck(abs(float(formula_volume_base(row(hist_sessions=60.0)).iloc[0]) - 1_000_000.0) < 1e-9,
       "مبناءِ فایل = ۱M: Σِ ۳۰M بر ۳۰ نشست")
    # نشستِ بی‌معامله درِ آرایۀِ سایت PriceMax = 0 دارد، پس نبودنِ یک پلکان
    # «پلکانِ غایب» نیست؛ اگر آن را غایب بشماریم، نمادِ قدیمیِ کم‌معامله هیچ‌وقت
    # جت نمی‌خورد و این بار اختلاف به سمتِ «کمتر از TSE» می‌رود.
    for k in JET_LADDER:
        ck(one("f_jet", **{f"h{k}_max": None}),
           f"f_jet پلکانِ بی‌معاملۀِ [ih][{k}] را صفر می‌شمارد، نه مردود")
        ck(not one("f_jet", **{f"h{k}_max": 1100.0}),
           f"f_jet با سقفِ [ih][{k}] بالایِ آخرین مردود است")

    # قدرت خریدارِ ساختنی نیست -> صفرِ جعلی نساز
    ck(resistance_ladder_high(row(), 59).iloc[0] == 900.0, "پلکان، بلندترینِ سقفِ نقاطِ لازم است")
    ck(resistance_ladder_high(row(h9_max=None), 59).iloc[0] == 900.0,
       "نشستِ بی‌معامله پلکان را صفر می‌کند و سقفِ بقیه را نگه می‌دارد")
    ck(pd.isna(resistance_ladder_high(row(hist_sessions=59.0), 59).iloc[0]),
       "کم‌سابقه NaN است، نه «کمینۀِ نقاطِ موجود» — همان استثنایی که سایت می‌دهد")
    ck(pd.isna(vol_ratio(row(month_avg_vol=0.0)).iloc[0]), "تقسیمِ بر حجمِ مبنایِ صفر NaN است")
    nan_row = row(buy_count_i=0.0, sell_count_i=0.0)
    ck(not bool(apply_tape_flags(nan_row).iloc[0]["f_jet"]),
       "قدرت خریدارِ بی‌معامله حقیقی جت را قبول نمی‌کند (نه ۱، نه بی‌نهایت)")

    # ── ۵) تایم‌فریمِ کوتاه‌تر، نقاطِ کمتری می‌خواهد ───────────────────────
    print("\n[۵] تایم‌فریمِ انتخابیِ کاربر")
    partial = row(h19_max=None, h29_max=None, h39_max=None, h49_max=None, h59_max=None)
    ck(bool(apply_tape_flags(partial.assign()).iloc[0]["f_clock"]), "ساعت به پلکان کاری ندارد")
    ladder5 = resistance_ladder_high(partial, 5).iloc[0]
    ladder5_young = resistance_ladder_high(partial.assign(hist_sessions=5.0), 5).iloc[0]
    ck(ladder5 == 900.0,
       "با تایم‌فریم ۵ فقط [ih][2] و [ih][5] لازم‌اند، و غایب‌ها صفر می‌مانند")
    ck(pd.isna(ladder5_young),
       "پنج نشست برایِ [ih][5] کافی نیست — پلکانِ کوتاه هم حدِّ سِنّ خودش را دارد")

    # ── ۶) پرچم‌هایِ فایل فقط دربارهٔ «همین نشست» حرف می‌زنند ──────────────
    # اندازه‌گیریِ زندهٔ ۱۴۰۵-۰۷-۰۵ ساعت ۱۰:۴۳: «حجم مشکوک» ۷۴ ردیف می‌داد و
    # فیلترنویسِ TSETMC ۱۹؛ ۵۵ تایِ ما ردیف‌هایِ فسیل بودند (اختیارِ سررسیدشده
    # و متوقف) که عددِ «امروزِ» خودشان را ندارند.
    print("\n[۶] ردیفِ بیرونِ تابلویِ امروز داوری نمی‌شود")
    ck(one("f_susp"), "ردیفِ زنده (بی‌ستونِ is_live) مثلِ قبل سنجیده می‌شود")
    for fname in ("f_clock", "f_susp", "f_jet", "f_noqteh"):
        ck(not one(fname, is_live=False), f"{fname} ردیفِ فسیل را قبول نمی‌کند")
    ck(not roobi(is_live=False), "f_roobi ردیفِ فسیل را قبول نمی‌کند")
    dead = row(is_live=False)
    ck(bool(pd.notna(formula_vol_ratio(dead).iloc[0])),
       "ستون‌هایِ نمایشی برایِ ردیفِ فسیل هم حساب می‌مانند (فقط پرچم بند می‌آید)")
    _FRONT = os.path.join(ROOT, "frontend", "src", "features", "market", "lib", "tapeAlgorithms.ts")
    ts_algo = read(_FRONT)
    ck("if (filterKey !== 'f_smart_flow' && !isLiveBoardRow(r)) return false;" in ts_algo,
       "سمتِ مرورگر هم همان قاعده را دارد (شمارشِ چیپ و فیلترِ ردیف یکی بماند)")

    # ── ۷) سیم‌کشی: یکِ نسخهٔ منطق، نه سه تا ──────────────────────────────
    print("\n[۷] سیم‌کشی")
    src = read(MARKET_PY)
    ck("from tape_flags import apply_tape_flags" in src,
       "api/market.py از ماژولِ آزمودنی استفاده می‌کند")
    ck("jet_hist_ok" not in src and ".isna() | (" not in src,
       "نسخۀ قدیمیِ «NULL یعنی قبول» حذف شده باشد")
    ck("is_close(V(\"p_closing\"), V(\"p_min\")" not in src,
       "کف‌روبی دیگر با np.isclose روی قیمتِ پایانی حساب نمی‌شود")
    ck("UNION ALL" in src and "daily_prices d" in src and "price_history h" in src,
       "پنجرۀ *نمایش* از اتحادِ daily_prices و price_history ساخته می‌شود")
    ck("AVG(CASE WHEN rn <= 30 THEN volume END)" in src,
       "حجمِ مبنا میانگینِ ۳۰ روزه است، نه ۶۰ تا")
    ck("MIN(CASE WHEN rn <= 29 AND low > 0 THEN low END) AS min30_low" in src,
       "کفِ ۳۰ روزۀ نمایشی صفرها را بیرون می‌گذارد (کفِ جعلیِ نشستِ بی‌معامله)")
    # ورودی‌هایِ «عینِ فایل» باید ازِ SQL بیایند؛ فرانت‌اند پنجرۀِ [ih] را ندارد.
    # نگاشت: `[ih][k]` ↔ جایگاهِ (k+1)امِ ردیفِ **خودِ نماد** درِ آرایۀِ سایت
    # (`tape_history`، یعنی همان GetClosingPriceDailyAllInst).
    for needle, what in (
        ("FROM tape_history",
         "پنجرۀ [ih] از جدولِ عینِ سایت می‌آید، نه از شمارشِ ردیفِ بانک"),
        ("ROW_NUMBER() OVER (PARTITION BY ins_code ORDER BY d_even DESC) AS srn",
         "جایگاهِ [k] درِ آرایۀِ خودِ نماد است، نه درِ تقویمِ کلِ بازار"),
        ("SUM(CASE WHEN srn <= 30 THEN volume END) AS prior30_vol",
         "Σ[ih][0..29] بر **نشست** می‌گردد، نه بر ردیفِ ذخیره‌شده"),
        ("CASE WHEN COUNT(CASE WHEN srn <= 29 THEN 1 END) < 29 THEN 0",
         "پنجرۀِ کمِ نشست‌ها کفِ صفر می‌گیرد، عینِ MinPriceOfMonth() != 0"),
        ("ELSE MIN(CASE WHEN srn <= 29 THEN price_min END) END AS min_low_29",
         "کمینۀِ [ih][0..28] از SQL می‌آید"),
        ("MAX(srn) AS hist_sessions",
         "عمرِ نماد = طولِ آرایۀِ خودش؛ همان حدِّ سِنّی که ExecFilter می‌گذارد"),
        ("MAX(CASE WHEN srn = 3  THEN price_max END) AS h2_max",
         "[ih][2] = سومین نشستِ آخر = srn 3"),
        ("MAX(CASE WHEN srn = 30 THEN price_max END) AS h29_max",
         "[ih][29] = srn 30"),
        ("MAX(CASE WHEN srn = 60 THEN price_max END) AS h59_max",
         "[ih][59] = srn 60 -- آخرین پلکان، وگرنه پنجرۀ ۶۰ بی‌معنی است"),
        ("LEFT JOIN fv ON fv.ins_code = m.ins_code",
         "پیوندِ پنجره با ins_code است؛ نامِ نماد کلیدِ پایدار نیست"),
        ("GROUP BY date ORDER BY date DESC LIMIT 60",
         "سقفِ پنجرۀِ نمایش از خودِ تاریخچه می‌آید"),
        ("m.allowed_min AS tmin", "(tmin) فیلترنویس = آستانۀ مجاز، و با همین نام به فیلتر می‌رسد"),
        ("m.buy_q1_cnt", "(zd1) = تعدادِ سفارشِ سطرِ اولِ خرید از SQL می‌آید"),
        ("m.buy_q1_vol", "(qd1) = حجمِ سفارشِ سطرِ اولِ خرید از SQL می‌آید"),
    ):
        ck(needle in src, what, needle)
    # نمادِ کهنۀِ کم‌معامله (خگلپا: ۶۰ نشست درِ سایت، ۱۸ ردیفِ بانک) دیگر با
    # شمارشِ ردیف «کم‌سابقه» شمرده نمی‌شود؛ حدسِ prewin هم لازم نماند.
    ck("prewin" not in src and "hs.srn" not in src,
       "حدس‌هایِ ردیف‌محورِ پیش (prewin، hs) حذف شدند — پنجره حالا عینِ سایت است")
    ck("AS MATERIALIZED" in src,
       "CTEهایِ تاریخچه materialize‌اند؛ بی‌آن SQLite هر ارجاع را دوباره "
       "می‌خواند و همین کوئری به هشت ثانیه می‌رسید")
    ck("prior30_n" not in src,
       "شمارندۀِ ردیفیِ قدیمی (prior30_n) جایش را به hist_sessions داده است")
    ck("df[\"percent_last\"]" in src,
       "(plp) درصدِ «آخرین» ساخته می‌شود؛ جت و کف‌روبی با آن داوری می‌کنند")
    # نشستِ جاریِ تابلو از daily_prices بیرون است (market_watch همان را دارد) ولی
    # price_history بی‌شرطِ تاریخ برداشته می‌شود: روزنۀِ منتشرشدۀِ امروز درِ TSETMC
    # هم [ih][0] است، پس حذفش پنجره را یک روزه عقب می‌برد.
    ck("d.d_even < (SELECT d FROM iso)" in src,
       "امروز از daily_prices نیامده؛ درِ [ih] همان‌جا است که نهایه منتشر شده")
    ck("FROM price_history h" in src and "h.date >= (SELECT MIN(dt) FROM spine)" in src,
       "پنجره از سقفِ ستونِ نشست بسته می‌شود، نه از تاریخِ دست‌نویس")
    ck("AS tran" not in src and "prev_day_tran" not in src,
       "«qd1 = تعدادِ معاملاتِ نشستِ پیش»ِ اشتباه هیچ‌جایِ کوئری نمانده باشد")
    flags_src = read(FLAGS_PY)
    ck('tmin = _col(df, "tmin")' in flags_src,
       "tape_flags هم دقیقاً همان نامِ ستونی را می‌خواند که کوئری می‌سازد "
       "(allowed_min اینجا نبود؛ f_roobi بی‌صدا صفر ردیف می‌داد)")

    spec = read(SPEC)
    ck("'tape_flags'" in spec, "tape_flags در hiddenimports هست، وگرنه EXE روی اولین درخواست می‌میرد")

    ts_math = read(TS_MATH)
    ck("export const JET_LADDER = [2, 5, 9, 19, 29, 39, 49, 59]" in ts_math,
       "فرانت‌اند همان هشت نقطۀ پلکان را دارد")
    ck("export const CLOCK_GAP = 0.02" in ts_math, "فرانت‌اند هم دلتای ساعت را ۲٪ می‌داند")
    m = re.search(r"export const SUSP_VOL_MULT = (\d+)", ts_math)
    ck(bool(m) and float(m.group(1)) == SUSP_VOL_MULT, "ضریب حجم مشکوک در دو سو یکی است")
    m = re.search(r"export const PER_CAPITA_MIN = ([\d.]+)", ts_math)
    ck(bool(m) and float(m.group(1)) == JET_BUYER_POWER, "آستانۀ قدرت خریدار در دو سو یکی است")
    ck("function resistanceLadderHigh" in ts_math
       and "sessions < Math.max(...pts) + 1) return null" in ts_math,
       "پلکانِ فرانت‌اند هم کم‌سابقه را null می‌دهد و نشستِ بی‌معامله را صفر")
    ck("last <= resistance" in ts_math, "جتِ فرانت‌اند هم با «آخرین» می‌سنجد")
    ck("const chg = num(r.percent_last)" in ts_math,
       "جتِ فرانت‌اند (plp) را از درصدِ «آخرین» می‌خواند، نه پایانی")
    ck("export function filterVolumeRatio(r: { vol_ratio_file?: number | null })" in ts_math,
       "فرانت‌اند نسبتِ فایل را از ستونِ بک‌اند می‌خواند، نه از میانگین ماه")
    m = re.search(r"export const JET_MIN_TRADES = (\d+)", ts_math)
    ck(bool(m) and int(m.group(1)) == JET_MIN_TRADES, "کفِ تعدادِ معاملۀِ جت در دو سو یکی است")
    m = re.search(r"export const ROOBI_ZD1_MIN = (\d+)", ts_math)
    ck(bool(m) and int(m.group(1)) == ROOBI_ZD1_MIN, "zd1 > 1 در فرانت‌اند هم هست")
    m = re.search(r"export const ROOBI_QD1_MIN = (\d+)", ts_math)
    ck(bool(m) and int(m.group(1)) == ROOBI_QD1_MIN, "qd1 > 100 در فرانت‌اند هم هست")
    ck("ROOBI_PREV_DAY" not in ts_math and "prev_day_tran" not in ts_math,
       "نامِ قدیمیِ «حجم/تعدادِ نشستِ پیش» از فرانت‌اند رفته باشد (آن قیدِ فایل نبود)")

    ts_algo = read(TS_ALGO)
    ck("typeof r.vol_ratio === 'number'" not in ts_algo
       and "typeof r.buyer_power === 'number'" not in ts_algo,
       "هیچ گیتی در tapeAlgorithms با «عدد نبود» بی‌صدا رد نمی‌شود")
    ck("minDeltaPct: 2.0" in ts_algo, "پیش‌فرضِ ساعت = عددِ فایل")
    ck("minTradeCount: 100" in ts_algo and "minVolRatio: 0" in ts_algo,
       "پیش‌فرضِ کف‌روبی = فایل، و گیت‌هایی که فایل ندارد خاموش‌اند")
    ck("volumeMultiple(" not in ts_algo,
       "هیچ دروازۀِ فیلتری در tapeAlgorithms به میانگین ماه نگاه نمی‌کند")
    ck(ts_algo.count("filterVolumeRatio") >= 3,
       "هر پنج گیتِ حجمیِ فرانت‌اند از مبناءِ فایل می‌خوانند")
    for needle, what in (
        ("num(r.tmin)", "کف‌روبیِ فرانت‌اند آستانۀِ مجازِ پایین را می‌بیند، نه کفِ روز"),
        ("num(r.buy_q1_cnt)", "zd1 = تعدادِ سفارشِ سطرِ اولِ خرید"),
        ("num(r.buy_q1_vol)", "qd1 = حجمِ سفارشِ سطرِ اولِ خرید"),
        ("below(r.percent_last, cfg.maxChangePct)", "plp = درصدِ «آخرین» در کف‌روبی"),
        ("num(r.min_low_29)", "کفِ فایل در فرانت‌اند هم خام است و صفر را رد می‌کند"),
        ("num(r.hist_sessions)", "شمارندۀِ نشست از ستونِ بک‌اند می‌آید، نه از شمارشِ ردیف"),
    ):
        ck(needle in ts_algo, what, needle)
    ck('r.p_min' not in ts_algo and 'prev_day_vol' not in ts_algo,
       "هیچ دروازۀِ کف‌روبی دوباره به کفِ نشست یا حجمِ دیروز وصل نشده باشد")

    row_ts = read(ROW_TS)
    ck("h2_max: num" in row_ts,
       "zod schema باید h2_max را داشته باشد؛ کلیدِ ناشناخته‌ی zod دور ریخته می‌شود")
    for field in ("vol_ratio_file", "prior30_vol", "hist_sessions", "min_low_29",
                  "percent_last", "tmin", "buy_q1_cnt", "buy_q1_vol"):
        ck(f"{field}: num" in row_ts,
           f"ستونِ {field} باید در zod باشد، وگرنه از پاسخ /api/market حذف می‌شود")
    for gone in ("prior29_vol", "prior29_n", "min_low_28", "prev_day_tran",
                 "prior30_n", "h1_max"):
        ck(gone not in row_ts, f"{gone} دیگر ستونِ تابلو نیست؛ در zod نمانده باشد")

    # ── ۸) سیم‌کشیِ ستون‌ها: هر چه tape_flags می‌خواند، کوئری هم می‌سازد ────
    # فاجعۀِ واقعیِ همین پروندّه: `allowed_min AS tmin` در SQL و `_col(df,
    # "allowed_min")` در فیلتر. هیچ‌کدام خطا نمی‌دهد؛ فقط f_roobi برایِ همیشه
    # صفر ردیف می‌ماند. پس نام‌هایی که tape_flags از DataFrame برمی‌دارد باید
    # درِ خروجیِ api/market.py پیدا شوند.
    print("\n[۸] هر ستونی که فیلتر می‌خواند، کوئری هم می‌دهد")
    consumed = set(re.findall(r'_n\(df\["([a-z0-9_]+)"\]\)|_col\(df, "([a-z0-9_]+)"\)',
                              flags_src))
    consumed = {a or b for a, b in consumed}
    consumed |= {f"h{k}_max" for k in JET_LADDER}      # پلکان با f-string ساخته می‌شود
    produced = set(re.findall(r"\bAS\s+([a-z_][a-z0-9_]*)", src))
    produced |= set(re.findall(r'df\["([a-z_0-9]+)"\]\s*=', src))
    produced |= set(re.findall(r"\bm\.([a-z_][a-z0-9_]*)", src))
    missing = sorted(consumed - produced - {"is_live"})
    ck(not missing, "همهٔ ستون‌هایِ مصرفیِ tape_flags درِ کوئریِ تابلو هست", str(missing))
    ck("is_live" in produced or 'df["is_live"]' in src,
       "ستونِ ردیفِ زنده هم ساخته می‌شود (بی‌آن پنج فیلتر رویِ فسیل‌ها داوری می‌کنند)")

    # ── ۹) چارت و تابلو باید یک «جت» ببینند ────────────────────────────────
    print("\n[۹] ستاپ جتِ چارت = پلکانِ جزوه")
    from api.chart import _fts_jet_setup  # noqa: E402

    def series(n=70, spikes=None, last_close=129.0, last_open=110.0):
        out = [{"open": 100.0, "high": 110.0, "low": 95.0, "close": 105.0} for _ in range(n)]
        for offset, high in (spikes or {}).items():
            # کندلِ آخرِ خروجی = امروز = [ih][0]؛ پس [ih][k] در آرایۀِ پایه
            # خانه‌ای به شمارهٔ n-k می‌نشیند.
            out[n - offset]["high"] = high
        out.append({"open": last_open, "high": max(last_close, last_open),
                    "low": 108.0, "close": last_close})
        return out

    r = _fts_jet_setup(series(spikes={30: 200.0}))
    ck(bool(r["active"]),
       "سقفِ بلند در نشستی که جزوه آن را درِ پلکان نمی‌خواهد، شکست را متوقف نمی‌کند",
       str(r))
    r2 = _fts_jet_setup(series(spikes={29: 200.0}))
    ck(not r2["active"] and r2["resistance"] == 200.0,
       "سقفِ بلند رویِ [ih][29] (نقطۀِ پلکان) شکست را رد می‌کند", str(r2))
    r3 = _fts_jet_setup(series(last_close=111.0, last_open=120.0))
    ck(not r3["active"] and r3["resistance"] == 110.0,
       "بدنۀِ نزولی بالای مقاومت تریگر نیست (کندلِ شمشِ بی‌تعهد)")
    r4 = _fts_jet_setup(series(n=40))
    ck(not r4["active"] and "تاریخچه" in (r4["reason"] or ""),
       "تاریخچۀِ کوتاه به‌جای حدس، صادقاً دلیل می‌آورد", str(r4))
    ck("JET_LADDER" in read(CHART_PY) and "_FTS_ENTRY_LOOKBACK = 60" not in read(CHART_PY),
       "api/chart.py پلکان را از tape_flags می‌گیرد، نه از ماکسِ متحرکِ ۶۰ کندله")

    screen_ts = read(os.path.join(ROOT, "frontend", "src", "features", "fundamental", "ui",
                                  "FtsScreenTable.tsx"))
    ck("r.tech_jet === true" in screen_ts and "jet: base.filter((r) => r.i1_pass" not in screen_ts,
       "چیپ «نامزدهای ستاپ جت» واقعاً ستاپِ جت را می‌شمارد، نه شاخص ۱ را")

    # ── ۱۰) پنجرۀ [ih]: منبع، نوشتنِ اتمی، و سِنٍّ صادق ────────────────────
    # هر چه بالا ساختارِ درست است، ولی اگر جدولِ [ih] خالی بماند یا نیمه‌کاره
    # پاک شود، همان فرمول‌هایِ درست صدها ردیف را بی‌دلیل «نسنج» می‌کنند
    # (خگلپا: ۶۰ نشست درِ سایت، ۱۸ ردیفِ بانک). پس این‌ها قفل می‌شوند.
    print("\n[۱۰] پنجرۀ [ih] از منبعِ خودِ سایت نوشته می‌شود")
    sync = read(os.path.join(ROOT, "test_tsetmc.py"))
    ck("GetClosingPriceDailyAllInst" in sync,
       "سینک پنجره را از همان درخواستی می‌گیرد که فیلترنویسِ سایت می‌گیرد")
    ck("def refresh_tape_history" in sync and "refresh_tape_history(conn)" in sync,
       "نوکردنِ پنجره به مسیرِ نوشتنِ روزانۀِ بازار وصل است")
    # شکستِ شبکه نباید دادهٔ موجود را ببرد: «پاک‌کردن» فقط بعدِ آن می‌آید که
    # پاسخِ سالم دستِ نویسنده رسیده باشد.
    m = re.search(r"def refresh_tape_history.*?\n\n\n", sync, re.S)
    body = m.group(0) if m else ""
    ck(bool(body), "بدنۀ refresh_tape_history پیدا شد")
    ck(body.index("if not rows:") < body.index("DELETE FROM") if body else False,
       "اول «نگرفتم» برگردانده می‌شود، بعد پاک‌کردنِ قدیمی‌ها (شکست = دادهٔ کهنه، نه بی‌داده)")
    ck("stream=True" not in body,
       "درخواستِ پنجره بی‌stream است؛ با stream=True همان پاسخ ۱۸۰ ثانیه ترکید")
    ck("TAPE_HIST_RETRY_S" in sync and "throttled" in sync,
       "پاسخِ ۵۱ مگابایتی هر چند دقیقه یک‌بار گرفته نمی‌شود")
    ck("stats[\"tape_history\"]" in sync,
       "پنجره آخرین کارِ سینک است، نه نخستین (تأخیرِ CDN نباید تابلو را عقب بیندازد)")
    me = read(os.path.join(ROOT, "mstat_engine.py"))
    ck("TAPE_HIST_DDL" in me and "tape_history" in me,
       "جدول در ensure_schema ساخته می‌شود؛ کوئریِ تابلو رویِ بانکِ قدیمی "
       "«no such table» نمی‌خورد")
    ck("CREATE TABLE IF NOT EXISTS {TAPE_HIST_TABLE}" in sync,
       "مسیرِ نوشتن هم همان جدول را می‌سازد (دو سوی مرز یک تعریف)")

    print(f"\ntape_filters_v1034: {PASS} passed / {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
