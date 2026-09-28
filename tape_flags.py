# tape_flags.py -- پنج فیلترِ تابلوخوانی، عینِ فرمول‌هایِ فایلِ مالک
#
# منبعِ حقیقت، پنج فایلِ دسکتاپ‌اند (`فیلتر جت.txt`، `حجم مشکوک.txt`،
# `کف روبی صف فروش.txt`، `نقطه زنی.txt`، `الگوی ساعت.txt`) که همان‌ها را
# `tools/tape_formula_parity.py` یک‌به‌یک با همین ماژول می‌سنجد. جزوه فقط
# «چرا»یِ آستانه‌ها را توضیح می‌دهد؛ متنِ فایل، «چه»یِ فیلتر است.
#
# واژه‌هایِ TSETMC درِ فایل‌ها — عیناً از `ExecFilter` درِ باندلِ خودِ سایت
# (tsetmc.com/main.f24603b0cc21e2598771.js) برداشته شده، نه از گلاسریِ شخصِ
# ثالث. آن تابع هر متغیر را به یک فیلدِ ردیفِ تابلو بدل می‌کند:
#   pl  = element.pdv      آخرین قیمت
#   pc  = element.pcl      قیمت پایانی
#   plc = element.pc       تغییرِ آخرین قیمت (مطلق)
#   plp = round(100*pc/py, 2)   ← درصدِ آخرین، نه درصدِ پایانی (آن (pcp) است)
#   tmin= element.pMin     آستانهٔ مجاز پایین   ← کفِ همین نشست نیست! (کفِ نشست (pmin)=pmn)
#   tmax= element.pMax     آستانهٔ مجاز بالا
#   tvol= element.qtj      حجمِ همین نشست
#   tno = element.ztt      تعدادِ معاملاتِ همین نشست
#   tval= element.qtc      ارزشِ همین نشست        bvol = element.bv   حجم مبنا
#   zd1 = element.blDs[0].zmd   تعدادِ سفارشِ سطرِ اولِ خرید
#   qd1 = element.blDs[0].qmd   حجمِ سفارشِ سطرِ اولِ خرید   (pd1 = قیمتِ همان سطر)
#   ct  = clientType[insCode]   Buy_I_Volume / Buy_CountI / Sell_I_Volume / Sell_CountI
#   [ih][k]  = kِمین **نشستِ** آخرِ همان نماد، نزولی بر dEven، و درِ سایت برایِ
#              هر نشستِ تقویمی ردیف دارد — حتی نشستِ بی‌معامله، با
#              QTotTran5J = 0 و PriceMin = PriceMax = 0.
#   [ih][k].QTotTran5J = qtjِ همان نشست  (نامِ فیلد گمراه‌کننده است: حجمِ
#              تک‌نشست است، نه میانگینِ پنج روزه)
#   [ih][0]  = آخرین روزنۀِ **منتشرشده**. تا پیش از نهایات، امروز درِ این آرایه
#              نیست (اندازه‌گیریِ ۱۴۰۵-۰۷-۰۵: خوراکِ ۱۴۰۵-۰۷-۰۵ درِ
#              GetClosingPriceDailyList هنوز نبود و [ih][0] برابرِ ۱۴۰۵-۰۷-۰۴
#              بود). پنجرۀِ فایل «امروزِ بی‌نهایه» را نمی‌شمارد.
#   اگر شاخصِ خواسته‌شده از طولِ [ih] بزرگ‌تر باشد خودِ ExecFilter استثنا می‌دهد
#   و ردیف با try/catch بیرون می‌افتد — یعنی نمادِ کم‌سابقه درِ آن فیلتر **سنجیده
#   نمی‌شود**، نه اینکه بر تعدادِ موجود تقسیم شود.

import numpy as np
import pandas as pd

# نردبانِ مقاومتِ فیلترِ جت: [ih][2] تا [ih][59] — هشت نقطه، عینِ فایل.
JET_LADDER = (2, 5, 9, 19, 29, 39, 49, 59)

# Σ[ih][0..29] بر سی **نشستِ** آخر می‌گردد و همان ۳۰ِ ثابت مخرج است. بانکِ ما
# نشستِ بی‌معامله را نمی‌نویسد، پس پنجره درِ api/market.py با شمارۀِ نشست
# (`srn`) ساخته می‌شود نه با شمارۀِ ردیفِ موجود؛ اندازه‌گیریِ ۱۴۰۵-۰۷-۰۵:
# بيوتيكح — مرجعِ فایل ۵۶٬۲۶۴، پنجرۀِ ردیف‌محور ۳۴۲٬۲۲۸ (شش برابرِ اشتباه).
VOL_BASE_SESSIONS = 30
# نمادی که سی نشست سابقه ندارد درِ خودِ سایت استثنا می‌دهد و ردیفش می‌افتد؛
# «کمتر از سی» یعنی «نسنج»، و هیچ‌وقت «بر تعدادِ موجود تقسیم کن».
HIST_MIN_SESSIONS = 30
# کمینۀِ نقطه‌زنی: [ih][0..28].PriceMin، عینِ حلقۀِ JS فایل (`n=1; n<29`) —
# بیست‌ونُه نشست. نشستِ بی‌معامله PriceMin=0 دارد و فایل `MinPriceOfMonth() != 0`
# را صریحاً می‌خواهد، پس یک نشستِ بی‌معامله کلِ ردیف را رد می‌کند.
LOW_BASE_SESSIONS = 29

# ضریب‌هایِ حجمیِ فایل
JET_VOL_MULT = 3.0
SUSP_VOL_MULT = 3.0
# قدرتِ خریدار: ``Buy_I_Volume/Buy_CountI >= 1.5 * Sell_I_Volume/Sell_CountI``
JET_BUYER_POWER = 1.5
# دلتای الگوی ساعت: ``pl >= pc*1.02``
CLOCK_DELTA = 0.02
# سقفِ فاصلۀِ نقطه‌زنی: ``round((pc-min)/pc*100*100)/100 < 3``
NOQTEH_MAX_DIST = 3.0
# کف‌روبی: ``pl == tmin`` یعنی آخرینِ معامله رویِ **آستانۀ مجاز پایین** چسبیده،
# ``plp < -1`` درصدِ آخرین است (نه پایانی)، و ``zd1 > 1 && qd1 > 100`` صفِ خریدِ
# سطرِ اول را می‌سنجد — «کف‌روبیِ صف فروش» یعنی همین: رویِ کف، خریدار در صف است.
ROOBI_MAX_CHANGE = -1.0
ROOBI_ZD1_MIN = 1                  # ``zd1 > 1`` — تعدادِ سفارشِ سطرِ اولِ خرید
ROOBI_QD1_MIN = 100                # ``qd1 > 100`` — حجمِ سفارشِ سطرِ اولِ خرید
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


def _alive(df: pd.DataFrame) -> pd.Series:
    """ردیف‌هایِ تابلویِ **همین نشست**. پنج فیلتر دربارهٔ «امروز» حرف می‌زنند؛
    ردیفی که آخرینِ نشستِ بانکِ خودش دیروز است نمی‌تواند بگوید «حجمِ امروزِ من
    سه برابرِ مبناءست». اندازه‌گیریِ ۱۴۰۵-۰۷-۰۵ ساعت ۱۰:۴۳: «حجم مشکوک» ۷۴ ردیف
    می‌داد که ۵۵ تایشان همین ردیف‌هایِ بی‌ربط بودند (اختیارِ سررسیدشده و
    متوقف)؛ رویِ تابلویِ زنده ۱۹ ردیف می‌مانَد — و همان‌ها فیلترنویسِ TSETMC.
    نبودنِ ستون یعنی «همه زنده» (غربگر و `/api/screener` آن را نمی‌سازند).
    """
    if "is_live" not in df.columns:
        return pd.Series(True, index=df.index)
    return df["is_live"].fillna(False).astype(bool)


def history_sessions(df: pd.DataFrame) -> pd.Series:
    """چند **نشستِ** تقویمی از عمرِ نماد درِ پنجرۀِ ۶۰ روزه دیده می‌شود.

    ستونِ `hist_sessions` درِ کوئری `MAX(srn)` است، یعنی شمارهٔ نشستِ
    کهنه‌ترین ردیفِ معامله‌شده. نمادی که ردیفش تا نشستِ ۳۰امِ آخر می‌رسد،
    قطعاً ۳۰ نشست عمر دارد؛ اگر نشستی درِ میانه نبوده، آن نشستِ بانکِ ما
    بی‌معامله بوده و درِ سایت صفر ثبت شده — نه غایب.
    """
    return _col(df, "hist_sessions")


def _sessions_ok(df: pd.DataFrame, need: int) -> pd.Series:
    """آیا پنجرۀِ فایل برایِ «سنجیدن» کامل است؟ (کمبود = نسنج، نه تقسیمِ دیگری)"""
    return history_sessions(df) >= need


def formula_volume_base(df: pd.DataFrame) -> pd.Series:
    """مبنایِ حجم: Σ[ih][0..29] ÷ ۳۰ — یا NaN اگر پنجره کامل نباشد.

    نشستِ بی‌معامله درِ Σ صفر است، پس نبودنِ ردیفش درِ بانکِ ما همان چیزی است
    که درِ سایت عددِ صفر است: هیچ افزودنی لازم ندارد. تقسیم بر تعدادِ ردیفِ
    موجود، همان ۵۵ ردیفِ جعلی را می‌ساخت که مالک به آن‌ها «اختلافِ TSE» گفت.
    """
    base = _col(df, "prior30_vol") / VOL_BASE_SESSIONS
    return base.where(base > 0).where(_sessions_ok(df, VOL_BASE_SESSIONS))


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

    قراردادِ ستون‌ها: `h{k}_max` درِ کوئریِ تابلو نشانهٔ `[ih][k]` است و `[ih]`
    بر **نشست** می‌گردد، پس `srn = k + 1`. با شمارۀِ ردیفِ ذخیره‌شده، نمادی که
    بیست روز تعطیل بوده پلکان را از تیرماه می‌آورد.

    نشستِ بی‌معامله درِ سایت PriceMax = 0 دارد، پس نبودنِ ستون «پلکانِ غایب»
    نیست و سقف را بالا نمی‌برد؛ آن‌چه سنجش را ناممکن می‌کند کم‌سابقهِ خودِ نماد
    است: اگر `[ih][k]` از طولِ آرایه بیرون بزند، ExecFilter استثنا می‌دهد و ردیف
    درِ همان فیلتر نمی‌نشیند — پس NaN، نه «کمینۀِ نقاطِ موجود».
    """
    pts = [k for k in JET_LADDER if k <= lookback]
    if not pts:
        return pd.Series(np.nan, index=df.index)
    stack = pd.concat([_col(df, f"h{k}_max").fillna(0.0).clip(lower=0.0) for k in pts], axis=1)
    return stack.max(axis=1).where(_sessions_ok(df, max(pts) + 1))


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
    pc, pl, plp = _n(df["p_closing"]), _n(df["p_last"]), _n(df["percent_last"])
    tno = _n(df["z_tot_tran"])
    res = resistance_ladder_high(df, lookback)
    return ((formula_vol_ratio(df) > JET_VOL_MULT)
            & (buyer_power(df) >= JET_BUYER_POWER)
            & (pc > 0) & (pl >= pc)
            & (plp > 0)
            & (tno > JET_TRADES) & (tno > JET_MIN_TRADES)
            & (res > 0) & (pl > res)).fillna(False)


def roobi_flag(df: pd.DataFrame) -> pd.Series:
    """D) کف‌روبی، عینِ فایل: ``pl == tmin && zd1 > 1 && plp < -1 && qd1 > 100``.

    معنی‌ها از `ExecFilterِ` خودِ سایت (سرآمدِ فایل): «آخرینِ معامله رویِ **آستانۀِ
    مجازِ پایین** چسبیده، بیش از یک درصد پایین، و در صفِ خریدِ سطرِ اول دو سفارش
    یا بیشتر با بیش از ۱۰۰ سهمِ صف است» — یعنی کسی زیرِ صفِ فروشِ کف خرید می‌گذارد.

    پیش از این ما `(tmin)` را کفِ همین نشست و `(zd1)`/`(qd1)` را حجم/تعدادِ نشستِ
    پیش می‌خواندیم؛ آن سه قیدِ آخر هیچ‌کدام صفِ امروز را نمی‌دیدند. سنجشِ ۱۴۰۵-۰۷-۰۵
    رویِ تابلویِ زنده: مرجعِ TSETMC ۳۱ ردیف، جدولِ ما ۶۳ ردیف، و تقریباً هیچ
    اشتراکی — همان چیزی که مالک می‌دیدد.

    نبودِ هر قید (عمقِ نداشتۀِ این نماد، آستانۀِ صفر) = مردود، نه «تطبیقِ خودکار»؛
    درِ خودِ سایت هم ExecFilter با `try/catch` چنین ردیفی را بیرون می‌اندازد.
    """
    pl = _n(df["p_last"])
    # نامِ ستون = نامِ متغیرِ فایل. کوئریِ تابلو «m.allowed_min AS tmin» می‌نویسد
    # دقیقاً برایِ اینکه این‌جا `allowed_min` نخواند؛ اگر یکی از دو سو نامش عوض
    # شود (pl) بی‌صدا تهی می‌شود و f_roobi برایِ همیشه صفر می‌ماند.
    tmin = _col(df, "tmin")
    zd1 = _col(df, "buy_q1_cnt")
    qd1 = _col(df, "buy_q1_vol")
    plp = _n(df["percent_last"])
    return ((pl > 0) & (tmin > 0) & (pl == tmin)
            & (zd1 > ROOBI_ZD1_MIN)
            & (plp < ROOBI_MAX_CHANGE)
            & (qd1 > ROOBI_QD1_MIN)).fillna(False)


def noqteh_flag(df: pd.DataFrame) -> pd.Series:
    """E) نقطه‌زنی: ``cfield2 < 3 && tvol > Σ[ih][0..29]/30 && tno > 5`` با
    ``cfield2 = round((pc-min)/pc*100*100)/100`` و min = کمینۀِ [ih][0..28].PriceMin.

    دو تصحیح نسبتِ نسخۀِ پیشین:
      ۱) بازه بر **نشست** می‌گردد (`min_low_29` = srn≤29 = [ih][0..28]) و کوئری
         خودِ پنجرۀِ ناقص را صفر می‌کند؛ پیش از این کمینه رویِ ردیف‌هایِ
         ذخیره‌شده می‌گشت و به بیست‌وهفتِ ردیفِ یک نمادِ تعطیل‌شده راضی می‌شد.
      ۲) صفر **معتبر** است، نه حذف‌شدنی: فایل `MinPriceOfMonth() != 0` را صریحاً
         می‌خواهد — یک نشستِ بی‌معامله کلِ ردیف را رد می‌کند. نسخۀِ پیشین با
         `low > 0` همان صفر را دور می‌انداخت و ردیفِ جعلی می‌ساخت.
      ۳) سقفِ فاصله **از بالا** بسته است، از پایین نه (۱۴۰۵-۰۷-۰۷): درِ سنجشِ زنده
         با تابلویِ خودِ سایت، یک نمادِ کف‌شکن (طملي7072، پایانیِ ۲ به کمینۀِ
         پنجرۀِ ۳ → فاصلۀِ ‎−۵۰٪) درِ فایل «نقطه‌زنی» می‌نشست و درِ ما رد
         می‌شد. فایل هیچ کرانِ پایینِ برایِ `cfield2` نمی‌نویسد و کف‌شکنی
         خودِ قوی‌ترینِ مصداقِ «نزدیکِ کف» است؛ `dist >= 0` درِ نسخۀِ ۱٫۰٫۳۳
         رأیِ مالک نداشت و بی‌صدا ردیف‌هایِ درست را می‌کُشت.
    """
    pc = _n(df["p_closing"])
    low_file = _col(df, "min_low_29").where(lambda s: s != 0)
    low_file = low_file.where(_sessions_ok(df, LOW_BASE_SESSIONS))
    dist = ((pc - low_file) / pc * 100).round(2)
    return ((pc > 0) & (dist < NOQTEH_MAX_DIST)
            & (formula_vol_ratio(df) > 1.0)
            & (_n(df["z_tot_tran"]) > NOQTEH_TRADES)).fillna(False)


def apply_tape_flags(df: pd.DataFrame) -> pd.DataFrame:
    """پنج پرچم + نسبت‌هایِ کمکی را می‌سازد؛ ورودی را دست نمی‌زند.

    پنج پرچم بر «همین نشست» شرط دارند (`_alive`)؛ نسبت‌ها و ستون‌هایِ نمایشی
    نه — آن‌ها تاریخچند و باید برایِ ردیف‌هایِ بیرونِ تابلو هم حساب بمانند.
    """
    out = df.copy()
    alive = _alive(out)
    out["vol_ratio"] = vol_ratio(out).round(2)
    out["vol_ratio_file"] = formula_vol_ratio(out).round(2)
    out["buyer_power_raw"] = buyer_power(out)
    out["resistance_59"] = resistance_ladder_high(out)
    out["dist_min30_pct"] = ((_n(out["p_closing"]) - _n(out["min30_low"]))
                             / _n(out["p_closing"]) * 100).round(2)
    out["f_clock"] = clock_flag(out) & alive
    out["f_susp"] = suspicious_flag(out) & alive
    out["f_jet"] = jet_flag(out) & alive
    out["f_roobi"] = roobi_flag(out) & alive
    out["f_noqteh"] = noqteh_flag(out) & alive
    return out
