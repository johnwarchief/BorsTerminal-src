# tape_flags.py -- پنج فیلترِ تابلوخوانی، عینِ فرمول‌هایِ فایلِ مالک
#
# منبعِ حقیقت، پنج فایلِ دسکتاپ‌اند (`فیلتر جت.txt`، `حجم مشکوک.txt`،
# `کف روبی صف فروش.txt`، `نقطه زنی.txt`، `الگوی ساعت.txt`) که همان‌ها را
# `tools/tape_formula_parity.py` یک‌به‌یک با همین ماژول می‌سنجد. جزوه فقط
# «چرا»یِ آستانه‌ها را توضیح می‌دهد؛ متنِ فایل، «چه»یِ فیلتر است.
#
# واژه‌هایِ TSETMC درِ فایل‌ها:
#   pl  = p_last        آخرین معامله
#   pc  = p_closing     قیمت پایانی
#   plp = percent_change درصد تغییر (پایانی نسبت به دیروز)
#   tmin= p_min         کفِ همین نشست
#   tvol= q_tot_tran    حجم معاملات
#   tno = z_tot_tran    تعداد معاملات
#   zd1 = prev_day_vol  حجمِ نشستِ پیش
#   qd1 = prev_day_tran تعدادِ معاملاتِ نشستِ پیش
#   [ih][k].PriceMax    سقفِ تک‌روزیِ kِمین نشستِ پیش  ->  h{k}_max
#   [ih][0]             **همین نشست** — پس Σ[ih][0..29] یعنی «امروز + ۲۹ پیش»
#
# دو قاعده‌ای که از فایل‌ها فاصله می‌گیرند، عمدی‌اند و هردو با رأیِ ثبت‌شده
# مستند شده‌اند (رأیِ ۱۸ در docs/fts-notes/OWNER_RULINGS.md):
#   ۱) مبناءِ حجم بر **تعدادِ نشست‌هایِ موجود** تقسیم می‌شود، نه ۳۰ِ ثابت.
#      فایل بر ۳۰ می‌نویسد چون TSETMC تاریخچۀِ کامل دارد؛ بانکِ ما برایِ ۲٬۴۸۴
#      نماد از ۵٬۳۰۶ کمتر از ۲۹ نشستِ پیش دارد و آن ۳۰ِ ثابت مبناء را تا ۱٫۵
#      برابرِ واقعی کوچک می‌کرد — اندازه‌گیری‌شده: ۵۵ ردیفِ جعلیِ «حجم مشکوک» و
#      ۳۱ ردیفِ «نقطه‌زنی» تنها از همین آمد. نمادِ کمتر از ۱۰ نشست سنجیده نمی‌شود.
#   ۲) قیدِ چهارمِ کف‌روبی (qd1>۱۰۰) فقط وقتی سنجیده می‌شود که آن عدد در بانک
#      باشد. ستونش تازه افزوده شده و از نخستین نشستِ پس از این نسخه پر می‌شود؛
#      پیش از آن «تعدادِ امروز» جانشینش نمی‌شود.
#
# قیدِ «دادهٔ نبودن ≠ قبول» همه‌جا برقرار است: بازگرداندنِ ``isna() | (...)``
# ممنوع -- همین بود که ۶۷۱ ردیفِ تابلو را به‌جایِ ~۵ ردیف «جت» می‌زد.

import numpy as np
import pandas as pd

# نردبانِ مقاومتِ فیلترِ جت: [ih][2] تا [ih][59] — هشت نقطه، عینِ فایل.
JET_LADDER = (2, 5, 9, 19, 29, 39, 49, 59)

# Σ[ih][0..29] رویِ سی نشست می‌گردد. فایل **همیشه بر ۳۰ ثابت** تقسیم می‌کند،
# چون TSETMC تاریخچۀِ کاملِ هر نماد را دارد. بانکِ ما ندارد: اندازه‌گیریِ
# ۱۴۰۵-۰۷-۰۴ رویِ ۵٬۳۰۶ ردیفِ زنده — تنها ۱٬۴۱۱ نماد ۲۹ نشستِ پیش دارد و
# ۲٬۴۸۴ تا ۱۰ تا ۲۸ تا. تقسیمِ همانِ ۳۰ بر این‌ها مبناء را مثلاً ۱٫۵ برابرِ
# واقعی کوچک می‌کند (همان ۵۵/۱۳۲ ردیفِ جعلی) و «نسنج»ِ بی‌قیدوشرط هم ۶۰٪ِ
# ردیف‌هایِ معامله‌شده را بی‌داوری می‌گذاشت. راهِ سوم: بر تعدادِ نشست‌هایِ
# **موجود** تقسیم کن — برایِ نمادِ سی‌نشستی دقیقاً همان فایل می‌شود، و برایِ
# بقیه نزدیک‌ترین میانگینِ صادق به همان عدد.
VOL_BASE_SESSIONS = 30
VOL_BASE_MIN_SESSIONS = 10              # کمتر از آن میانگینِ حجمی معنادار نیست
# کمینۀِ نقطه‌زنی: [ih][0..28].PriceMin = همین نشست + ۲۸ نشستِ پیش. کمینه با
# نشستِ کمتر **کوچک‌تر** می‌شود نه بزرگ‌تر، پس اینجا هم همان کفِ ۱۰ کافی است.
LOW_BASE_MIN_SESSIONS = 10

# ضریب‌هایِ حجمیِ فایل
JET_VOL_MULT = 3.0
SUSP_VOL_MULT = 3.0
# قدرتِ خریدار: ``Buy_I_Volume/Buy_CountI >= 1.5 * Sell_I_Volume/Sell_CountI``
JET_BUYER_POWER = 1.5
# دلتای الگوی ساعت: ``pl >= pc*1.02``
CLOCK_DELTA = 0.02
# سقفِ فاصلۀِ نقطه‌زنی: ``round((pc-min)/pc*100*100)/100 < 3``
NOQTEH_MAX_DIST = 3.0
# کف‌روبی: ``plp < -1`` و ``zd1 > 1``
ROOBI_MAX_CHANGE = -1.0
ROOBI_PREV_DAY_MIN = 1         # ``zd1 > 1`` — حجمِ نشستِ پیش
ROOBI_QD1_MIN = 100              # ``qd1 > 100`` — تعدادِ معاملاتِ نشستِ پیش
# آستانه‌هایِ تعدادِ معاملۀِ فایل
CLOCK_TRADES = 30
SUSP_TRADES = 50
NOQTEH_TRADES = 5
JET_TRADES = 1                 # ``tno > 1``
JET_MIN_TRADES = 100           # ``tno > 100`` — رأیِ ۱۸: عینِ فایل برگشت


def _n(s: pd.Series) -> pd.Series:
    """عددِ معتبر؛ هر چیزِ دیگر NaN تا «نبودن» از «صفر» جدا بماند."""
    v = pd.to_numeric(s, errors="coerce")
    return v.replace([np.inf, -np.inf], np.nan)


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    """ستونِ اختیاری — کوئریِ قدیمی یا بانکِ بدونِ مایگریشن نباید کرش کند."""
    if name in df.columns:
        return _n(df[name])
    return pd.Series(np.nan, index=df.index)


def _sessions(df: pd.DataFrame) -> pd.Series:
    """چند نشست از پنجرۀِ فایل واقعاً درِ بانک است؟ (همین نشست + تا ۲۹ پیش)"""
    n = _col(df, "prior29_n").fillna(0.0).clip(upper=VOL_BASE_SESSIONS - 1)
    return 1.0 + n


def formula_volume_base(df: pd.DataFrame) -> pd.Series:
    """مبنایِ حجم: میانگینِ حجمِ نشست‌هایِ پنجرۀِ فایل — یا NaN اگر پنجره کم باشد.

    فایل `Σ[ih][0..29] ÷ ۳۰` می‌نویسد و TSETMC سی نشست را دارد؛ ما گاهی کمتر.
    تقسیم بر **تعدادِ موجود** (نه ۳۰ِ ثابت) همان عددِ فایل را برایِ نمادِ
    کاملِ تاریخچه می‌سازد و برایِ بقیه به‌جایِ مبناءِ جعلیِ کوچک، نزدیک‌ترین
    میانگینِ صادق را می‌دهد. نمادی که کمتر از ۱۰ نشست دارد سنجیده نمی‌شود.
    """
    today = _n(df["tvol"]).fillna(0.0)
    # SUM تهی = «هیچ سطرِ تاریخچه‌ای نچسبید»؛ با ۰ پر نمی‌شود، مبناء NaN می‌ماند.
    prior = _col(df, "prior29_vol")
    sessions = _sessions(df)
    base = (today + prior) / sessions
    return base.where(base > 0).where(sessions >= VOL_BASE_MIN_SESSIONS)


def volume_base(df: pd.DataFrame) -> pd.Series:
    """میانگینِ حجمِ ۳۰ نشستِ پیش، یا NaN. صفرِ جعلی نمی‌سازد.

    این مبناء ستونِ «نسبت حجم ماه» را می‌سازد و عمداً از مبناءِ فایل جدا مانده
    است: یکی نمایشِ روند است، دیگری قیدِ فیلتر.
    """
    base = _n(df["month_avg_vol"])
    return base.where(base > 0)


def vol_ratio(df: pd.DataFrame) -> pd.Series:
    """تعدادِ چندبرابرِ میانگینِ ۳۰ روزه -- NaN یعنی «سنجش ممکن نیست»."""
    return _n(df["tvol"]) / volume_base(df)


def formula_vol_ratio(df: pd.DataFrame) -> pd.Series:
    """حجمِ امروز ÷ مبناءِ فایل؛ همان نسبتی که پنج فیلتر با آن داوری می‌کنند."""
    return _n(df["tvol"]) / formula_volume_base(df)


def buyer_power(df: pd.DataFrame) -> pd.Series:
    """قدرتِ خریدارِ حقیقی نسبت به فروشندهٔ حقیقی (سرانۀِ حجم به تعدادِ معامله).

    هیچِ دو سمتیِ صفر/صفر را به ۱ نزدیک نمی‌کنیم: NaN می‌ماند تا فیلتر
    «داده نبود» را از «قدرت برابر» متمایز بداند.
    """
    bc = _n(df["buy_count_i"]).where(lambda s: s > 0)
    sc = _n(df["sell_count_i"]).where(lambda s: s > 0)
    buy = _n(df["buy_i_vol"]) / bc
    sell = _n(df["sell_i_vol"]) / sc
    return buy / sell


def resistance_ladder_high(df: pd.DataFrame, lookback: int = max(JET_LADDER)) -> pd.Series:
    """بیشترینِ سقفِ تک‌روزی درِ نقاطِ پلکانِ فایل که از ``lookback`` کوتاه‌ترند.

    هر نقطۀِ لازم باید وجود داشته باشد؛ اگر یکی کم باشد نتیجه NaN است، نه
    «کمینۀِ نقاطِ موجود». این دقیقاً همان جایی است که نسخۀِ قبلی NULL را
    قبول می‌شمرد.
    """
    pts = [k for k in JET_LADDER if k <= lookback]
    if not pts:
        return pd.Series(np.nan, index=df.index)
    stack = pd.concat([_n(df[f"h{k}_max"]).where(lambda s: s > 0) for k in pts], axis=1)
    complete = stack.notna().all(axis=1)
    out = stack.max(axis=1)
    return out.where(complete)


def clock_flag(df: pd.DataFrame) -> pd.Series:
    """A) الگوی ساعت: ``pl >= pc*1.02 && tvol > Σ[ih][0..29]/30 && tno > 30``"""
    pc, pl = _n(df["p_closing"]), _n(df["p_last"])
    return ((pc > 0) & (pl >= pc * (1.0 + CLOCK_DELTA))
            & (formula_vol_ratio(df) > 1.0)
            & (_n(df["z_tot_tran"]) > CLOCK_TRADES)).fillna(False)


def suspicious_flag(df: pd.DataFrame) -> pd.Series:
    """B) حجم مشکوک: ``tvol > 3*Σ[ih][0..29]/30 && tno > 50``"""
    return ((formula_vol_ratio(df) > SUSP_VOL_MULT)
            & (_n(df["z_tot_tran"]) > SUSP_TRADES)).fillna(False)


def jet_flag(df: pd.DataFrame, lookback: int = max(JET_LADDER)) -> pd.Series:
    """C) جت، عینِ فایل: حجمِ ۳× + قدرتِ خریدارِ ۱٫۵× + ``pl>=pc`` + ``plp>0`` +
    پلکانِ هشت‌نقطه‌ایِ ``[ih][2..59].PriceMax < pl`` + ``tno>1`` + ``tno>100``.

    رأیِ ۱۸ (۱۴۰۵-۰۷-۰۴): ``tno > 100`` که در فایل هست و رأیِ ۱۷ آن را از «جتِ
    استراتژیک» بیرون گذاشته بود، در **فیلترِ تابلو** برمی‌گردد؛ مالک خواست
    نشانِ «جت» همان چیزی باشد که فیلترنویسِ TSETMC می‌دهد.
    """
    pc, pl, plp = _n(df["p_closing"]), _n(df["p_last"]), _n(df["percent_change"])
    tno = _n(df["z_tot_tran"])
    res = resistance_ladder_high(df, lookback)
    return ((formula_vol_ratio(df) > JET_VOL_MULT)
            & (buyer_power(df) >= JET_BUYER_POWER)
            & (pc > 0) & (pl >= pc)
            & (plp > 0)
            & (tno > JET_TRADES) & (tno > JET_MIN_TRADES)
            & (res > 0) & (pl > res)).fillna(False)


def roobi_flag(df: pd.DataFrame) -> pd.Series:
    """D) کف‌روبی: ``pl == tmin && zd1 > 1 && plp < -1 && qd1 > 100``.

    قیدِ چهارم فقط وقتی سنجیده می‌شود که ``prev_day_tran`` عدد داشته باشد
    (قاعدهٔ ۲ بالای فایل)؛ جانشین‌کردنش با تعدادِ امروز ۷۳ ردیف می‌ساخت که
    هیچ‌کدام معادلۀِ فایل نبودند.
    """
    pl, tmin = _n(df["p_last"]), _n(df["p_min"])
    qd1 = _col(df, "prev_day_tran")
    out = ((pl.notna() & tmin.notna() & (pl == tmin))
           & (_n(df["prev_day_vol"]) > ROOBI_PREV_DAY_MIN)
           & (_n(df["percent_change"]) < ROOBI_MAX_CHANGE))
    # qd1 هست → فایل‌وار بسنج؛ هنوز جمع نشده → همین سه قید (رأیِ پایلوت: strict)
    return (out & (qd1.isna() | (qd1 > ROOBI_QD1_MIN))).fillna(False)


def noqteh_flag(df: pd.DataFrame) -> pd.Series:
    """E) نقطه‌زنی: ``cfield2 < 3 && tvol > Σ[ih][0..29]/30 && tno > 5`` با
    ``cfield2 = round((pc-min)/pc*100*100)/100`` و min = کمینۀِ [ih][0..28].PriceMin
    — یعنی کفِ **همین نشست** هم داخلِ بازه است، عینِ حلقۀِ JS فایل.
    """
    pc = _n(df["p_closing"])
    low_file = pd.concat([_n(df["p_min"]), _col(df, "min_low_28")], axis=1).min(axis=1)
    low_file = low_file.where(_sessions(df) >= LOW_BASE_MIN_SESSIONS)
    dist = ((pc - low_file) / pc * 100).round(2)
    return ((pc > 0) & (low_file > 0) & (dist >= 0) & (dist < NOQTEH_MAX_DIST)
            & (formula_vol_ratio(df) > 1.0)
            & (_n(df["z_tot_tran"]) > NOQTEH_TRADES)).fillna(False)


def apply_tape_flags(df: pd.DataFrame) -> pd.DataFrame:
    """پنج پرچم + نسبت‌هایِ کمکی را می‌سازد؛ ورودی را دست نمی‌زند."""
    out = df.copy()
    out["vol_ratio"] = vol_ratio(out).round(2)
    out["vol_ratio_file"] = formula_vol_ratio(out).round(2)
    out["buyer_power_raw"] = buyer_power(out)
    out["resistance_59"] = resistance_ladder_high(out)
    out["dist_min30_pct"] = ((_n(out["p_closing"]) - _n(out["min30_low"]))
                             / _n(out["p_closing"]) * 100).round(2)
    out["f_clock"] = clock_flag(out)
    out["f_susp"] = suspicious_flag(out)
    out["f_jet"] = jet_flag(out)
    out["f_roobi"] = roobi_flag(out)
    out["f_noqteh"] = noqteh_flag(out)
    return out
