# tape_flags.py -- پنج فیلترِ تابلوخوانی، عینِ فرمول‌هایِ جزوه
#
# قبلاً این پرچم‌ها داخلِ بدۀِ مسیرِ ``/api/market`` نوشته شده بودند و هیچِ
# آزمونیِ loro را نمی‌پوشاند. اینجا تنها توابعِ خالصِ pandas زندگی می‌کنند تا
# همِ مسیرِ API و همِ نگهبانِ ``dev/tape_filters_v1034.py`` یکِ منطقِ واحدِ
# را بسنجند (نهِ دوِ نسخۀِ واگرا).
#
# واژه‌هایِ TSETMC درِ جزوه (تأییدشده از «الگوی ساعت»: pl باید «آخرین» باشد
# تا شرطِ ``pl >= pc*1.02`` معنیِ «بازگشتِ خریدار در دقایقِ آخر» بدهد):
#   pl  = p_last        آخرین معامله
#   pc  = p_closing     قیمت پایانی
#   plp = percent_change درصد تغییر
#   tmin= p_min         کفِ همین نشست
#   tvol= q_tot_tran    حجم معاملات
#   tno = z_tot_tran    تعداد معاملات
#   zd1 = prev_day_vol  حجمِ نشستِ پیش
#   [ih][k].PriceMax    سقفِ تک‌روزیِ kِمین نشستِ پیش  ->  h{k}_max
#
# قیدِ «دادهٔ نبودن ≠ قبول»: هر شرطی که جزوه گذاشته، با نبودنِ داده **رد**
# می‌شود. بازگرداندنِ ``isna() | (...)`` ممنوع است -- همین بود که ۶۷۱ ردیفِ
# تابلو را به‌جایِ ~۵ ردیف «جت» می‌زد.

import numpy as np
import pandas as pd

# نردبانِ مقاومتِ فیلترِ جت: [ih][2] تا [ih][59] (جزوه همین هشتِ نقطه را
# می‌خواهد؛ [ih][1] درِ جزوه نیست چون سقفِ دیروز تنهاییِ کافی نیست).
JET_LADDER = (2, 5, 9, 19, 29, 39, 49, 59)

# حجمِ مبنایِ جزوه: میانگینِ ۳۰ نشستِ پیش -- نه ۶۰ تا.
VOL_BASE_SESSIONS = 30
# کمینۀِ ۲۹ نشستِ پیش برایِ «کفِ ۳۰ روزه»: [ih][0..28].PriceMin
LOW_LADDER_SESSIONS = 29

# نسبتِ حجمِ مشکوک و ضریبِ حجمِ جت (جزوه: ``tvol > 3 * avg30``)
JET_VOL_MULT = 3.0
SUSP_VOL_MULT = 3.0
# قدرتِ خریدارِ حقیقیِ جزوه: ``Buy_I_Volume/Buy_CountI >= 1.5 * Sell_I_Volume/Sell_CountI``
JET_BUYER_POWER = 1.5
# دلتای الگوی ساعت: ``pl >= pc * 1.02``
CLOCK_DELTA = 0.02
# سقفِ فاصلۀِ نقطه‌زنی: ``cfield2 < 3``
NOQTEH_MAX_DIST = 3.0
# کف‌روبی: ``plp < -1``
ROOBI_MAX_CHANGE = -1.0
# کف‌روبی: ``qd1 > 100`` -- تعدادِ معاملاتِ نشستِ پیش منبعِ داده ندارد (جدولِ
# daily_prices ستونِ z_tot_tran ندارد)، پس تعدادِ امروز جانشینِ مستند آن است.
ROOBI_TRADE_COUNT = 100
# آستانه‌هایِ تعدادِ معاملۀِ جزوه
CLOCK_TRADES = 30
SUSP_TRADES = 50
NOQTEH_TRADES = 5


def _n(s: pd.Series) -> pd.Series:
    """عددِ معتبر؛ هر چیزِ دیگر NaN تا «نبودن» از «صفر» جدا بماند."""
    v = pd.to_numeric(s, errors="coerce")
    return v.replace([np.inf, -np.inf], np.nan)


def volume_base(df: pd.DataFrame) -> pd.Series:
    """میانگینِ حجمِ ۳۰ نشستِ پیش، یا NaN. صفرِ جعلی نمی‌سازد."""
    base = _n(df["month_avg_vol"])
    return base.where(base > 0)


def vol_ratio(df: pd.DataFrame) -> pd.Series:
    """تعدادِ چندبرابرِ میانگینِ ۳۰ روزه -- NaN یعنی «سنجش ممکن نیست»."""
    return _n(df["tvol"]) / volume_base(df)


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
    """بیشترینِ سقفِ تک‌روزی درِ نقاطِ پلکانِ جزوه که از ``lookback`` کوتاه‌ترند.

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
    """A) الگوی ساعت: ``pl >= pc*1.02 && tvol > avg30 && tno > 30``"""
    pc, pl = _n(df["p_closing"]), _n(df["p_last"])
    return ((pc > 0) & (pl >= pc * (1.0 + CLOCK_DELTA))
            & (vol_ratio(df) > 1.0)
            & (_n(df["z_tot_tran"]) > CLOCK_TRADES)).fillna(False)


def suspicious_flag(df: pd.DataFrame) -> pd.Series:
    """B) حجم مشکوک: ``tvol > 3*avg30 && tno > 50``"""
    return ((vol_ratio(df) > SUSP_VOL_MULT)
            & (_n(df["z_tot_tran"]) > SUSP_TRADES)).fillna(False)


def jet_flag(df: pd.DataFrame, lookback: int = max(JET_LADDER)) -> pd.Series:
    """C) فیلتر جت: حجمِ ۳× + قدرتِ خریدارِ ۱.۵× + آخرین بالای پایانی + مثبت +
    شکستِ کاملِ پلکانِ مقاومتِ [ih][2..59].PriceMax با **آخرینِ** معامله.

    رأیِ مالکِ ۱۴۰۵-۰۷-۰۳: جت هیچ «حداقلِ تعدادِ معامله»ای ندارد؛ تنها
    ``tno >= 1`` به‌عنوانِ نگهبانِ «اصلاً معامله شده؟» مانده است.
    """
    pc, pl, plp = _n(df["p_closing"]), _n(df["p_last"]), _n(df["percent_change"])
    res = resistance_ladder_high(df, lookback)
    return ((vol_ratio(df) > JET_VOL_MULT)
            & (buyer_power(df) >= JET_BUYER_POWER)
            & (pc > 0) & (pl >= pc)
            & (plp > 0)
            & (_n(df["z_tot_tran"]) >= 1)
            & (res > 0) & (pl > res)).fillna(False)


def roobi_flag(df: pd.DataFrame) -> pd.Series:
    """D) کف‌روبی صف فروش: ``pl == tmin && zd1 > 1 && plp < -1 && qd1 > 100``"""
    pl, tmin = _n(df["p_last"]), _n(df["p_min"])
    return ((pl.notna() & tmin.notna() & (pl == tmin))
            & (_n(df["prev_day_vol"]) > 1)
            & (_n(df["percent_change"]) < ROOBI_MAX_CHANGE)
            & (_n(df["z_tot_tran"]) > ROOBI_TRADE_COUNT)).fillna(False)


def noqteh_flag(df: pd.DataFrame) -> pd.Series:
    """E) نقطه‌زنی: ``round((pc-min29)/pc*100, 2) < 3 && tvol > avg30 && tno > 5``"""
    pc, low = _n(df["p_closing"]), _n(df["min30_low"])
    dist = ((pc - low) / pc * 100).round(2)
    return ((pc > 0) & (low > 0) & (dist >= 0) & (dist < NOQTEH_MAX_DIST)
            & (vol_ratio(df) > 1.0)
            & (_n(df["z_tot_tran"]) > NOQTEH_TRADES)).fillna(False)


def apply_tape_flags(df: pd.DataFrame) -> pd.DataFrame:
    """پنج پرچم + نسبت‌هایِ کمکی را می‌سازد؛ ورودی را دست نمی‌زند."""
    out = df.copy()
    out["vol_ratio"] = vol_ratio(out).round(2)
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
