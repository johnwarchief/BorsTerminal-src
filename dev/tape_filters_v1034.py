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

گارد نه به شبکه نیاز دارد نه به market.db (قاعدهٔ مخزن: گارد نباید به
چیزی که CI ندارد وابسته باشد)؛ همه‌چیز رویِ چارچوبِ مصنوعی سنجیده می‌شود.

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

from tape_flags import (CLOCK_DELTA, JET_BUYER_POWER, JET_LADDER, JET_MIN_TRADES,  # noqa: E402
                        JET_TRADES, JET_VOL_MULT,
                        NOQTEH_MAX_DIST, ROOBI_MAX_CHANGE, ROOBI_PREV_DAY_MIN,
                        ROOBI_QD1_MIN, SUSP_TRADES, SUSP_VOL_MULT,
                        VOL_BASE_MIN_SESSIONS, VOL_BASE_SESSIONS, apply_tape_flags,
                        formula_vol_ratio, resistance_ladder_high, vol_ratio)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKET_PY = os.path.join(ROOT, "api", "market.py")
CHART_PY = os.path.join(ROOT, "api", "chart.py")
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

    ستون‌هایِ «ورودیِ فایل» (prior29_vol/prior29_n/min_low_28/prev_day_tran) هم
    اینجا پراند؛ بدونِ آن‌ها همهٔ فیلترها به‌دلیلِ «نسنج» رد می‌شدند و گارد
    هیچ‌چیز را نمی‌آزمود. مبناءِ سی‌نشستیِ این ردیف:
    (tvol 4M + prior29_vol 26M) / 30 = 1M، یعنی نسبتِ ۴.۰×.
    """
    base = {
        "symbol": "آزمون", "p_closing": 1000.0, "p_last": 1025.0, "p_min": 1025.0,
        "percent_change": 2.5, "price_yesterday": 980.0,
        "q_tot_tran": 4_000_000.0, "tvol": 4_000_000.0, "z_tot_tran": 120.0,
        "month_avg_vol": 1_000_000.0, "prev_day_vol": 2_000_000.0,
        "prior29_vol": 26_000_000.0, "prior29_n": 29.0,
        "min_low_28": 995.0, "prev_day_tran": 150.0,
        "buy_i_vol": 2_000_000.0, "buy_count_i": 100.0,
        "sell_i_vol": 1_000_000.0, "sell_count_i": 100.0,
        "min30_low": 995.0,
    }
    for k in JET_LADDER:
        base[f"h{k}_max"] = 900.0
    base["h1_max"] = 900.0
    base.update(over)
    return pd.DataFrame([base])


def flags(**over):
    return apply_tape_flags(row(**over)).iloc[0]


def one(col, **over):
    return bool(flags(**over)[col])


def roobi(**over):
    """ردیفِ کف‌روبی: نشسته روی کفِ روز و منفی -- همان ردیفِ.jet مثبت نمی‌تواند باشد."""
    base = {"p_closing": 970.0, "p_last": 970.0, "p_min": 970.0,
            "percent_change": -2.0, "z_tot_tran": 150.0, "prev_day_vol": 2_000_000.0}
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
    ck(ROOBI_MAX_CHANGE == -1.0 and ROOBI_QD1_MIN == 100 and ROOBI_PREV_DAY_MIN == 1,
       "کف‌روبی: plp < -1، zd1 > 1 و qd1 > 100")
    ck(NOQTEH_MAX_DIST == 3.0 and SUSP_TRADES == 50, "نقطه‌زنی فاصله < 3 و حجم مشکوک tno > 50")
    # رأیِ ۱۸ (۱۴۰۵-۰۷-۰۴): فیلترِ تابلو عینِ فایل است، پس ``tno > 100`` در جت.
    ck(JET_TRADES == 1 and JET_MIN_TRADES == 100, "جت: tno > 1 و tno > 100، عینِ فایل")
    ck(VOL_BASE_SESSIONS == 30 and VOL_BASE_MIN_SESSIONS == 10,
       "پنجرۀ فایل ۳۰ نشاست و زیر ۱۰ نشست سنجیده نمی‌شود")

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
    # مبناءِ فایل «امروز + ۲۹ پیش روی ۳۰» است؛ برایِ نسبتِ درستِ ۱٫۰ باید
    # prior29_vol را تنظیم کرد، چون tvol هم درِ صورت و هم درِ مبناء است.
    ck(not one("f_clock", prior29_vol=116_000_000.0), "ساعت: حجمِ برابرِ مبناء قبول نیست (>)")
    # B) حجم مشکوک
    # نسبتِ دقیقاً ۳.۰: مبناء باید tvol/3 شود، پس Σ[ih][1..29] = ۳×۴M − ۴M
    ck(abs(float(formula_vol_ratio(row(prior29_vol=36_000_000.0)).iloc[0]) - 3.0) < 1e-9,
       "مبناءِ فایل درست ساخته می‌شود: (تومان + ۲۹ پیش) ÷ ۳۰")
    ck(not one("f_susp", prior29_vol=36_000_000.0), "حجم مشکوک: دقیقاً ۳× مبناء کافی نیست (>)")
    ck(not one("f_susp", z_tot_tran=50), "حجم مشکوک: tno > 50 اکید است")
    # C) جت
    ck(not one("f_jet", p_last=899.0, p_closing=890.0), "جت: آخرینِ زیرِ مقاومت قبول نیست")
    ck(one("f_jet", p_last=901.0, p_closing=900.0), "جت: یک ریال بالاتر از مقاومت قبول است")
    ck(not one("f_jet", p_last=900.0, p_closing=880.0), "جت: آخرینِ دقیقاً رویِ مقاومت مردود است (>)")
    ck(not one("f_jet", p_last=880.0, p_closing=870.0),
       "جت با پایانیِ زیرِ مقاومت ولی آخرینِ زیرِ مقاومت مردود است")
    ck(not one("f_jet", sell_i_vol=3_000_000.0), "جت: قدرت خریدار زیر ۱٫۵× مردود است")
    ck(not one("f_jet", percent_change=-0.5), "جت: درصد تغییر منفی مردود است")
    ck(not one("f_jet", p_last=999.0), "جت: آخرینِ زیرِ پایانی مردود است")
    ck(not one("f_jet", z_tot_tran=1), "جت: tno > 1 اکید است")
    ck(not one("f_jet", z_tot_tran=100), "جت: tno > 100 (رأیِ ۱۸، عینِ فایل) مردود است")
    ck(one("f_jet", z_tot_tran=101), "جت: یکی بالاتر از ۱۰۰ قبول است")
    # D) کف‌روبی
    ck(not roobi(p_last=971.0), "کف‌روبی: آخرین باید دقیقاً روی کفِ روز باشد")
    ck(not roobi(percent_change=-1.0), "کف‌روبی: plp < -1 اکید است")
    ck(not roobi(prev_day_tran=100), "کف‌روبی: qd1 > 100 اکید است")
    ck(roobi(z_tot_tran=12), "کف‌روبی: تعدادِ «امروز» جانشینِ qd1 نمی‌شود")
    ck(not roobi(prev_day_vol=1), "کف‌روبی: zd1 > 1 اکید است")
    ck(not roobi(p_min=960.0), "کف‌روبی: کفِ روز جابه‌جا شد، شرطِ pl==tmin می‌شکند")
    # E) نقطه‌زنی
    ck(not one("f_noqteh", min_low_28=969.0), "نقطه‌زنی: فاصلۀِ ۳٫۱٪ از کفِ فایل مردود است")
    ck(one("f_noqteh", min30_low=800.0),
       "ستونِ نمایشیِ min30_low درِ نقطه‌زنی نیست (کفِ فایل = [ih][0..28])")

    # ── ۴) نبودنِ داده هیچ‌وقت قبول نیست ───────────────────────────────────
    print("\n[۴] نبودنِ داده = رد، نه قبول")
    NULLS = {
        # مبناءِ فایل: هر چه از سی نشستِ لازم کم باشد سنجش ممکن نیست.
        "prior29_vol": ("f_clock", "f_susp", "f_jet", "f_noqteh"),
        "prior29_n": ("f_clock", "f_susp", "f_jet", "f_noqteh"),
        "tvol": ("f_clock", "f_susp", "f_jet", "f_noqteh"),
        "z_tot_tran": ("f_clock", "f_susp", "f_jet", "f_noqteh"),
        "p_last": ("f_clock", "f_jet", "f_roobi"),
        "p_closing": ("f_clock", "f_jet", "f_noqteh"),
        "p_min": ("f_roobi",),
        "prev_day_vol": ("f_roobi",),
        "percent_change": ("f_jet", "f_roobi"),
        "min_low_28": ("f_noqteh",),
    }
    for col, dependents in NULLS.items():
        for fname in dependents:
            # کف‌روبی ردیفِ منفیِ خودش را دارد؛ با ردیفِ مثبتِ پیش‌فرض آزمون
            # صوری می‌شد (همیشه مردود، چه داده باشد چه نه).
            test = roobi(**{col: None}) if fname == "f_roobi" else one(fname, **{col: None})
            ck(not test, f"{fname} با {col} تهی مردود است")
    # نمادِ کم‌سابقه: مبناءِ «تقسیم بر ۳۰» برایِ آن عددِ جعلی می‌سازد (۵۵ ردیف
    # جعلیِ حجم مشکوک در اندازه‌گیریِ ۱۴۰۵-۰۷-۰۴)؛ قاعدهٔ ۱ بالای tape_flags.
    ck(not one("f_susp", prior29_n=8.0), "نه نشستِ کُل → حجم مشکوک سنجیده نمی‌شود")
    ck(one("f_susp", prior29_n=9.0, prior29_vol=9_000_000.0),
       "ده نشستِ کُل → میانگینِ همان ده نشست مبناء می‌شود، نه تقسیمِ بر ۳۰")
    ck(not one("f_noqteh", prior29_n=8.0), "کمتر از ۱۰ نشست → نقطه‌زنی سنجیده نمی‌شود")
    ck(one("f_noqteh", prior29_n=27.0),
       "۲۸ نشست: کفِ فایل و مبناء از نشست‌هایِ موجود ساخته می‌شوند")
    # قیدِ چهارمِ کف‌روبی تا نبودِ ستونش رد نمی‌کند و جانشین هم نمی‌خواهد.
    ck(roobi(prev_day_tran=None), "f_roobi با qd1 تهی سه قیدِ دیگر را می‌سنجد (رأیِ پایلوت)")
    # نبودنِ qd1 جانشین نمی‌خواهد: تعدادِ امروز درِ کف‌روبی نیست، پس هر دو
    # ردیفِ زیر باید یکسان داوری شوند (با سه قیدِ دیگر).
    ck(roobi(prev_day_tran=None, z_tot_tran=2_000) == roobi(prev_day_tran=None, z_tot_tran=3),
       "کف‌روبی به تعدادِ معاملاتِ امروز بی‌تفاوت است")
    # ماه‌مبناء فقط ستونِ نمایش است؛ درِ هیچ فیلتری نیست.
    for fname in ("f_clock", "f_susp", "f_jet", "f_noqteh"):
        ck(one(fname, month_avg_vol=None), f"{fname} به month_avg_volِ نمایشی وابسته نیست")
    # دو مبناء، دو معنا — این همان جایی است که ۵۵ ردیفِ جعلی از آمد.
    short = row(prior29_n=9.0, prior29_vol=2_700_000.0)
    ck(pd.isna(formula_vol_ratio(row(prior29_n=4.0)).iloc[0]),
       "زیرِ کفِ ۱۰ نشست مبناء NaN است (نسنج، نه عددِ جعلی)")
    ck(abs(float(formula_vol_ratio(short).iloc[0])
             - 4_000_000.0 / ((4_000_000.0 + 2_700_000.0) / 10.0)) < 1e-9,
       "با ده نشست، مبناء میانگینِ همان ده نشست است (Σ ÷ ۱۰، نه ÷ ۳۰)")
    ck(float(vol_ratio(short).iloc[0]) > 3.0,
       "مبناءِ نمایشی همان ردیف را «بیش از ۳×» می‌خواند؛ پس نباید درِ فیلتر باشد")
    for k in JET_LADDER:
        ck(not one("f_jet", **{f"h{k}_max": None}), f"f_jet با نبودنِ [ih][{k}].PriceMax مردود است")
        ck(not one("f_jet", **{f"h{k}_max": 0.0}), f"f_jet سقفِ صفرِ [ih][{k}] را «شکسته» نمی‌شمارد")

    # قدرت خریدارِ ساختنی نیست -> صفرِ جعلی نساز
    ck(resistance_ladder_high(row(), 59).iloc[0] == 900.0, "پلکان، بلندترینِ سقفِ نقاطِ لازم است")
    ck(pd.isna(resistance_ladder_high(row(h9_max=None), 59).iloc[0]),
       "پلکانِ ناقص NaN است، نه کمینۀِ نقاطِ موجود")
    ck(pd.isna(vol_ratio(row(month_avg_vol=0.0)).iloc[0]), "تقسیمِ بر حجمِ مبنایِ صفر NaN است")
    nan_row = row(buy_count_i=0.0, sell_count_i=0.0)
    ck(not bool(apply_tape_flags(nan_row).iloc[0]["f_jet"]),
       "قدرت خریدارِ بی‌معامله حقیقی جت را قبول نمی‌کند (نه ۱، نه بی‌نهایت)")

    # ── ۵) تایم‌فریمِ کوتاه‌تر، نقاطِ کمتری می‌خواهد ───────────────────────
    print("\n[۵] تایم‌فریمِ انتخابیِ کاربر")
    partial = row(h19_max=None, h29_max=None, h39_max=None, h49_max=None, h59_max=None)
    ck(bool(apply_tape_flags(partial.assign()).iloc[0]["f_clock"]), "ساعت به پلکان کاری ندارد")
    ladder5 = resistance_ladder_high(partial, 5).iloc[0]
    ladder59 = resistance_ladder_high(partial, 59).iloc[0]
    ck(ladder5 == 900.0 and pd.isna(ladder59),
       "با تایم‌فریم ۵ فقط [ih][2] و [ih][5] لازم‌اند")

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
       "پنجرۀ تاریخچه از اتحادِ daily_prices و price_history ساخته می‌شود")
    ck("AVG(CASE WHEN rn <= 30 THEN volume END)" in src,
       "حجمِ مبنا میانگینِ ۳۰ نشست است، نه ۶۰ تا")
    ck("MIN(CASE WHEN rn <= 29 AND low > 0 THEN low END)" in src,
       "کفِ ۳۰ روزهٔ نمایشی رویِ [ih][1..29] و بدونِ صفرهایِ نشستِ بی‌معامله")
    # ورودی‌هایِ «عینِ فایل» باید ازِ SQL بیایند؛ فرانت‌اند پنجرهٔ ۳۰ نشستی ندارد.
    for needle, what in (
        ("SUM(CASE WHEN rn <= 29 THEN volume END) AS prior29_vol",
         "Σ[ih][1..29] برایِ مبناءِ فایل از SQL می‌آید (امروز درِ tvolِ تابلو هست)"),
        ("MIN(CASE WHEN rn <= 28 AND low > 0 THEN low END)   AS min_low_28",
         "کمینۀِ [ih][1..28] از SQL می‌آید و صفرِ نشستِ بی‌معامله کفِ جعلی نمی‌سازد"),
        ("MAX(CASE WHEN rn = 1 THEN tran END)",
         "qd1 = تعدادِ معاملاتِ نشستِ پیش از SQL می‌آید"),
        ("COUNT(CASE WHEN rn <= 29 THEN volume END)",
         "شمارشِ نشست‌هایِ پیشینه برایِ «نسنج» آمد"),
    ):
        ck(needle in src, what, needle)
    ck("MAX(CASE WHEN rn = 2 THEN high END) AS h2_max" in src,
       "نقطۀ [ih][2] -- که جزوه از آن شروع می‌کند -- از SQL می‌آید")
    ck("(SELECT dt FROM iso)" in src and "d.d_even < (SELECT d FROM iso)" in src,
       "نشستِ جاریِ تابلو از پنجرۀ تاریخچه بیرون است (rn=1 یعنی «نشستِ پیش»)")

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
    ck("function resistanceLadderHigh" in ts_math and "v == null || v <= 0) return null" in ts_math,
       "پلکانِ فرانت‌اند هم با نقطۀ غایب null می‌دهد")
    ck("last <= resistance" in ts_math, "جتِ فرانت‌اند هم با «آخرین» می‌سنجد")
    ck("export function filterVolumeRatio(r: { vol_ratio_file?: number | null })" in ts_math,
       "فرانت‌اند نسبتِ فایل را از ستونِ بک‌اند می‌خواند، نه از میانگین ماه")
    m = re.search(r"export const JET_MIN_TRADES = (\d+)", ts_math)
    ck(bool(m) and int(m.group(1)) == JET_MIN_TRADES, "کفِ تعدادِ معاملۀِ جت در دو سو یکی است")
    ck("export const ROOBI_PREV_DAY_TRAN_MIN = 100" in ts_math,
       "qd1 > 100 در فرانت‌اند هم هست")

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
    ck("num(r.prev_day_tran)" in ts_algo,
       "کف‌روبیِ فرانت‌اند qd1 واقعی را می‌سنجد، نه تعدادِ امروز")

    row_ts = read(ROW_TS)
    ck("h2_max: num" in row_ts,
       "zod schema باید h2_max را داشته باشد؛ کلیدِ ناشناخته‌ی zod دور ریخته می‌شود")
    for field in ("vol_ratio_file", "prior29_vol", "prior29_n", "min_low_28",
                  "prev_day_tran", "percent_last"):
        ck(f"{field}: num" in row_ts,
           f"ستونِ {field} باید در zod باشد، وگرنه از پاسخ /api/market حذف می‌شود")

    # ── ۷) چارت و تابلو باید یک «جت» ببینند ────────────────────────────────
    print("\n[۷] ستاپ جتِ چارت = پلکانِ جزوه")
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

    print(f"\ntape_filters_v1034: {PASS} passed / {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
