# -*- coding: utf-8 -*-
"""api/structure3.py -- رابطِ APIِ موتورِ سوم (ZigZagِ آستانه‌دارِ ATR٪).

چرا مسیرِ جدای `/api/fts`: رأیِ رسمی FTS همان `api/chart.py` می‌ماند (بند ۱ و ۴
طرحِ مأموریت: «هیچ منطقی در فرانت قضاوت نمی‌کند» و «نتایجِ سه موتور ادغام
نمی‌شوند»). این فایل هیچ داوریِ جدیدی نمی‌سازد و فقط خروجیِ خالصِ
`structure_engine3` را روی یک قراردادِ دادهٔ مستقل منتشر می‌کند؛ پرچمِ
`official=False` و `voting=False` درِ پاسخ همین مرز را به رابط می‌گوید تا
رأیِ موتورِ اول با ساختارِ موتورِ سوم یکی خوانده نشود.

منبعِ داده همان سریِ موتورِ اول است (`_fts_analysis_series`): کندلِ TSETMC با
تعدیلِ عملکردی و مبنایِ قیمتِ ذخیرۀ کاربر. موتورِ سوم سریِ دومی نمی‌سازد، پس
مقایسهٔ دو موتور رویِ یک کندلِ واحد است، نه دو worldview.

وضعیتِ مرجع (تنها مانعِ مرحلۀ ۲): لینکِ مرجعی که مالک گفته بود در گفت‌وگوهایِ
پیشین ارائه کرده درِ فایل‌هایِ ردیابی‌شدۀ پروژه، پیوست‌هایِ مأموریت و نشست‌هایِ
در دسترس پیدا نشد. تا پیش از آن لینک هیچ آستانۀ تازه‌ای اختراع نمی‌شود: سه
پارامتر از خودِ `structure_engine3` خوانده و درِ `params` منتشر می‌شوند، و
`reference_status` صادقاً بی‌مرجعِ بیرونی بودن را اعلام می‌کند.
"""
from fastapi import APIRouter, Query

import structure_engine3 as E3

router = APIRouter()

ENGINE_ID = "structure3"
ENGINE_LABEL = "موتور سوم - زیگزاگ آستانه‌دار (ATR٪)"
# بی‌مرجعِ بیرونیِ تأییدشدنی؛ مقدار ثابت تا روزی که لینکِ مالک برسد.
REFERENCE_STATUS = "unverified-no-external-reference"
RULE_SOURCE = ("لایۀ ساختاریِ مقایسه؛ قواعدِ جزوۀ FTS برای ZigZagِ آستانه‌دار عددی "
               "نمی‌دهد، پس درِ رأیِ رسمی FTS مشارکت نمی‌کند")


def _params():
    """تک‌منبعِ آستانه‌ها: خودِ موتور. اینجا هیچ عددِ جدیدی نوشته نمی‌شود."""
    return {"atr_period": E3.ATR_PERIOD, "atr_mult": E3.ATR_MULT, "floor_pct": E3.FLOOR_PCT}


def analyze_symbol(symbol: str, as_of: str | None = None):
    """بدونِ FastAPI: سریِ تحلیلِ موتورِ اول -> قراردادِ موتورِ سوم.

    حالت‌هایِ صریح (مرحلۀ ۲: «ورودی/خروجی/نامعتبر را صریح تعریف کن»):
      error        -- سریِ کندل ساخته نشد (شبکه/بانک/نمادِ ناشناخته)
      empty        -- صفر کندل؛ نه پیوت، نه برچسب
      insufficient -- یک کندل؛ ZigZag بی‌دو نکت نمی‌سازد (قلّۀ موتورِ خودِ فایل)
      success      -- `points`/`choch`/`meta` پر می‌شوند
    `pending` درِ `meta` می‌ماند و هرگز به لایۀ رسم راه نمی‌یابد: پیوتِ
    تأییدنشده یعنی «هنوز فهمیده نشده»، و رسم‌کردنش همان repaint است.
    """
    from . import chart as CH

    try:
        candles, basis = CH._fts_analysis_series(symbol)
    except Exception as e:
        return {"status": "error", "symbol": symbol, "engine": ENGINE_ID, "message": str(e)}
    if as_of:
        candles = CH._candles_upto_asof(candles, as_of)

    base = {"symbol": symbol, "engine": ENGINE_ID, "engine_label": ENGINE_LABEL,
            "official": False, "voting": False, "rule_source": RULE_SOURCE,
            "reference_status": REFERENCE_STATUS, "params": _params(),
            "tf": "D", "basis": basis, "bars": len(candles),
            "as_of": as_of}
    if not candles:
        base["status"] = "empty"
        base["message"] = "هیچ کندلی برای این نماد در دسترس نیست"
        return base
    # لنگرِ نگاشتِ عددِ سرور به فضایِ کندلِ رسم‌شده (قاعدۀ لایۀ ۴) -- همان
    # بستۀ سریِ تحلیل، نه بستۀ دیدِ مرورگر.
    base["ref_close"] = candles[-1].get("close")
    if len(candles) < 2:
        base["status"] = "insufficient"
        base["message"] = "زیگزاگ به دستِ کمِ دو کندل نیاز دارد"
        return base

    zz = E3.zigzag(candles, atr_mult=E3.ATR_MULT, floor_pct=E3.FLOOR_PCT,
                   atr_period=E3.ATR_PERIOD)
    labeled = E3.label_structure(zz["pivots"])
    base["status"] = "success"
    base["points"] = labeled["points"]
    base["choch"] = labeled["choch"]
    base["meta"] = zz["meta"]
    return base


@router.get("/api/structure3/{symbol}")
def get_structure3(symbol: str,
                   as_of: str | None = Query(
                       None, description="YYYY-MM-DD؛ بازپخشِ ساختار فقط با کندل‌هایِ T و پیش‌تر")):
    """قراردادِ دادهٔ موتورِ سوم (مستقل، بی‌رأی).

    پاسخِ موفق: `{status, symbol, engine, official:false, voting:false, params,
    tf:'D', basis, bars, ref_close, points[], choch[], meta}` که در آن
    `points[*] = {idx, time, price, kind:'high'|'low', confirm_idx, confirm_time,
    threshold_pct, atr_used, label:'HH'|'HL'|'LH'|'LL'|null}` و
    `choch[*] = {kind, direction:'bullish'|'bearish', idx, time, confirm_idx,
    confirm_time, level}`. `meta` شمارشِ تأییدهایِ ATR در برابرِ کفِ-only،
    کندل‌هایِ بی‌ATR و `pending` (ساختارِ تأییدنشده) را می‌گوید.
    """
    return analyze_symbol(symbol, as_of=as_of)
