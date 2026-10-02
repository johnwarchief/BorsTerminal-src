"""Fundamental (CODAL) per-symbol endpoint — موتور ۵ لایهٔ بنیادی FTS v10.

این فایل در v9.8.1 از app.py جدا شد و تا نسخهٔ قبل تنها خروجی
`fts_engine.scan_symbol` را بازآرایی میکرد. نسخهٔ ۱۰، روش‌شناسی پنج‌لایهٔ FTS
را صریح و کامل پیاده میکند:

  لایهٔ ۱  درآمد/فروش — دو چکِ الزامی:
           ۱الف رشد ریالی: فروش تجمیعی ÷ همان دورهٔ سال قبل ≥ ۶۰٪
           ۱ب رشد تولیدی (تناژ/تعداد): ردِ سودی که صرفاً از تورم و افزایش
              قیمت میآید؛ برای شرکت‌های مالی «تناژ» معنا ندارد و مبنای
              درآمد، تسهیلات اعطایی + سپرده‌گذاری + سرمایه‌گذاری + اوراق +
              کارمزد است.
  لایهٔ ۲  سابقهٔ ۳ سالهٔ سودسازی: مسیر صعودی EPS از صورت‌های مالی ۱۲ماههٔ
           حسابرسی‌شدهٔ شرکت اصلی + راستی‌آزمایی با دورهٔ میاندوره‌ایِ جاری.
  لایهٔ ۳  حاشیهٔ سود ناخالص = سود ناخالص ÷ درآمدهای عملیاتی
           (ایده‌آل ≥ ۳۰٪، قابل‌قبول ≥ ۲۰٪).
  لایهٔ ۴  پتانسیل سالانه‌سازیِ پویا: م = ماه‌های سپری‌شدهٔ سال مالی (۱..۱۲)
             فروش سالانه        = فروش تجمیعی × (۱۲ ÷ م)
                                  # ۳م×۴، ۴م×۳، ۵م×۲٫۴، ۶م×۲ …
             سود ناخالص پتانسیل = فروش سالانه × حاشیهٔ ناخالص
             نسبت پتانسیل       = سود ناخالص پتانسیل ÷ ارزش بازار ≥ ۳۳٪
  لایهٔ ۵  چشم‌انداز صنعت و رژیم قیمت‌گذاری: آزاد/بورس‌کالایی/صادرات‌محور
           (سیمان، فلزات، پتروشیمی) در برابر دستوری (خودرو، نیروگاه، دارو،
           retail) — همان دیکشنری fts_engine، بدون موازی‌سازی.

مرز مسئولیت (تصادم دو Agent):
  * fts_engine.py **ویرایش نمی‌شود** — اسکریپت‌های dev/fts_pipeline_v981.py،
    dev/confidence_engine_v973.py و dev/fts_m141_parity_v97.py پاریتی
    `scan_symbol`/`bulk_scan` را قفل کرده‌اند. از آنجا فقط پریمیتیرهای عمومی
    (norm_fa، sym_in، annual_statements، gross_margin، sector_filter) مصرف
    میشوند.
  * تنها استثنا — معافیتِ شاخص ۴: تک‌مرجعش `fts_engine.ind4_exempt` است و
    هر دو مسیر (اسکرینر و کارت) همان را می‌خوانند؛ این فایل دیگر هیچ
    معیارِ نام/طبقهٔ دومی برای N/A ندارد. قفلش:
    dev/fts_screener_card_parity_v10.py.
  * `static/index.html` و `static/app.js` مصرف‌کنندهٔ فرجمد این payload هستند؛
    کلیدهای `insights[].{step,title,text}`، `metrics.{mcap,revenue,
    gross_margin,roe,ps}`، `fs_count` و `history[].tracing_no` حفظ شده‌اند.
"""
from typing import Optional
from ._core import _num, get_db
from .market import load_fts_config
from bors_config import DB_PATH
from fastapi import APIRouter
from fastapi import HTTPException
import fts_engine
import mstat_engine
# تنها تعریفِ «دورۀ گزارش» — همان که `codal_fetcher` می‌نویسد و `fts_engine` می‌خواند.
import codal_periods as CP
import datetime
import os
import re
import sqlite3


router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
#  آستانه‌های روش‌شناسی — حکمِ جزوه، نه سلیقهٔ کاربر
# ═══════════════════════════════════════════════════════════════════════════
# fts_thresholds.json (growth_min/margin_min/…) مسیر اسکرینر و ماتریس اطمینان
# را تغذیه میکند و از این فایل نوشتنش مجاز نیست. پس آستانه‌های v10 پیش‌فرضِ
# خودشان را دارند و فقط با کلیدهای صریحِ `v10_*` قابل روشن‌کردن‌اند؛ طوری که
# تغییر `growth_min: 40` اسکرینر را جابه‌جا کند ولی چک ۱الفِ کارت بنیادی (۶۰٪)
# را بی‌صدا شل نکند.
FTS_V10_DEFAULTS = {
    "monetary_growth_min": 60.0,    # ۱الف — رشد ریالی تجمیعی (٪)
    "volume_growth_min": 0.0,       # ۱ب — رشد تولیدی باید غیرمنفی باشد (٪)
    "volume_breadth_min": 0.60,     # ۱ب — حداقل share ماههایی که واقعاً بهتر شده‌اند
    "eps_years": 3,                 # ۲ — طول سابقهٔ سودسازی (سالِ متوالی سودآور)
    "margin_min": 20.0,             # ۳ — کف حاشیهٔ ناخالص
    "margin_ideal": 30.0,           # ۳ — حاشیهٔ ایده‌آل
    "sales_to_mcap_min": 0.33,      # ۴الف — فروش سالانه ÷ ارزش بازار (۳۳٪ = ۰٫۳۳×، استاندارد جزوه)
    "potential_min": 40.0,          # ۴ب — سود ناخالص پتانسیل ÷ ارزش بازار (٪)
    # ۱ب — مبنای تورمِ داخلِ فرمولِ «رشد تولیدی». حکمِ مالک (۱۴۰۵/۰۷/۰۴):
    # این عدد از هدفِ ۶۰٪ جدا شد و خودش در پنلِ تنظیمات قابل تغییر است.
    "inflation_basis": 60.0,
}

MRL_TO_RIAL = 1e6      # جداول کدال «میلیون ریال» هستند
BT_FACTOR = 1e-4       # میلیون ریال → میلیارد تومان (حذف ۴ رقم راست)

# پیش‌فرضِ «مبنای تورم» وقتی کاربر هنوز عددی نگذاشته: همان هدفِ ۶۰٪ جزوه
# (حکم ۳ — کف ۴۰٪ قبولی، ۶۰٪ پوشش تورم). ثابتِ ۵۸٪ بی‌منبع حذف شده است.
# از حکم ۱۴۰۵/۰۷/۰۴ این عدد کلیدِ مستقلِ خودش را دارد (`v10_inflation_basis`)
# و دیگر از `v10_monetary_growth_min` قرض گرفته نمی‌شود.
_INFLATION_FALLBACK = 60.0


def v10_thresholds(cfg: dict = None) -> dict:
    """آستانه‌های مؤثر v10 = پیش‌فرضِ جزوه + override از پنلِ تنظیمات کدال.

    ترتیبِ اولویت برای هر پارامتر:
      ۱) `v10_<k>` — overrideِ اختیاری که فقط کارتِ بنیادی را تغییر میدهد
      ۲) کلیدِ مشترکِ پنل (eps_years/margin_min/margin_optimal/…) — «یک پارامتر،
         یک جا»: کاربر در پنل یک عدد می‌زند و همان عدد هم اسکرینر و هم کارت را
         می‌گرداند؛ دو منبعِ حقیقت برای «حاشیهٔ ناخالص» نداشتن بهتر است.
      ۳) پیش‌فرضِ جزوهٔ همین فایل
    استثنای عمدی: `monetary_growth_min` (چک ۱الفِ کارت = ۶۰٪) هیچ‌وقت از
    `growth_min`ِ اسکرینر (۴۰٪) ارث نمی‌برد — دلیلش در بالای همین فایل است:
    شل‌کردنِ عددِ اسکرینر نباید بی‌صدا حکمِ سختِ کارت را عوض کند. برای همین
    پنل، فیلدِ جداگانهٔ `v10_monetary_growth_min` دارد.
    """
    cfg = cfg or {}
    out = dict(FTS_V10_DEFAULTS)
    shared = {"eps_years": "eps_years", "margin_min": "margin_min",
              "margin_ideal": "margin_optimal",
              "sales_to_mcap_min": "sales_to_mcap_min",
              "potential_min": "profit_potential_min",
              "volume_growth_min": "volume_growth_min",
              "volume_breadth_min": "volume_breadth_min"}
    for k, default in FTS_V10_DEFAULTS.items():
        probes = ["v10_%s" % k]
        if k in shared:
            probes.append(shared[k])
        for probe in probes:
            if probe in cfg:
                try:
                    out[k] = int(cfg[probe]) if k == "eps_years" else float(cfg[probe])
                    break
                except (TypeError, ValueError):
                    pass
    # مبنای تورم: کلیدِ مستقلِ خودش، نه قرض‌گرفته از هدفِ رشدِ ۱الف. صفرِ کاربر
    # «بدون تعدیلِ تورم» است و باید همان بماند — پس `or` اینجا ممنوع است.
    infl = _num_or_none(cfg.get("v10_inflation_basis"))
    out["inflation_benchmark"] = infl if infl is not None and infl >= 0 else _INFLATION_FALLBACK
    return out



def _f(v) -> float:
    """float امن: None/str/NaN → 0.0 (ستون‌های خالی کدال فراوان‌اند)."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return x if x == x else 0.0


def _bt(value_million_rials) -> float:
    """میلیون ریال → میلیارد تومان (قاعدهٔ جزوه: حذف ۴ رقم سمت راست)."""
    return round(_f(value_million_rials) * BT_FACTOR, 1)


def _fa_date(period_end) -> str:
    """نمونۀ دورۀ یکِ ردیف برایِ متنِ کاربر — از `codal_periods` می‌خواند، پس رقمِ
    فارسی و خط تیره هم به همان شکلِ canonical (`۱۴۰۴/۰۹/۳۰`) درمی‌آید و ردیفِ
    بی‌دوره «—» می‌شود (نه رشته‌ای نصفه)."""
    return CP.canonicalize(period_end) or "—"


def _pct(new, old) -> float:
    """رشد٪ با محافظ مخرج صفر — None یعنی «محاسبه نشد»، نه «صفر درصد»."""
    old = _f(old)
    if old <= 0:
        return None
    return round((_f(new) / old - 1.0) * 100.0, 1)


def _real_growth(nominal_pct, price_pct) -> float:
    """رشد واقعی = حذف اثر قیمت از رشد اسمی (فیشرِ فشرده)."""
    if nominal_pct is None:
        return None
    return round(((1.0 + nominal_pct / 100.0) / (1.0 + _f(price_pct) / 100.0) - 1.0) * 100.0, 1)


def _num_or_none(v):
    """عدد یا None — «داده نیست» هیچ‌وقت ۰.۰ نمی‌شود (برخلاف _f)."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def _eps_yoy_pct(series):
    """درصد رشد سال‌به‌سالِ همان سری EPS (#101 — «درصدها نوشته بشه»).

    حالت‌های None که باید None بمانند: نخستین دوره (مبنایی ندارد)، سالِ غایب،
    دورهٔ جاریِ بدون عدد، و مبنای صفر/زیان (درصد از زیان معنا ندارد). هیچ‌گاه
    جای None عدد ۰٪ نمی‌نشیند — رابط کاربری همان «داده نداریم» را می‌نویسد.
    """
    out = []
    prev = None
    for i, v in enumerate(list(series or [])):
        cur = _num_or_none(v)
        out.append(None if (i == 0 or cur is None or prev is None) else _pct(cur, prev))
        prev = cur
    return out

# ═══════════════════════════════════════════════════════════════════════════
#  ارزش بازار — تک‌منبعِ حقیقت (ستونِ market_cap در اسنپ‌شاتِ تابلوی TSETMC)
# ═══════════════════════════════════════════════════════════════════════════
# قاعدهٔ v10: هیچ مسیرِ خواندنی — کارت بنیادی، واچ‌لیست، اسکرینر، خروجی یا UI —
# حق ندارد ارزش بازار را دوباره بسازد. عدد یک‌بار در موتور همگام‌سازی
# (test_tsetmc.board_market_cap) از ردیفِ خامِ تابلو ساخته و در ستونِ
# `market_watch.market_cap` ذخیره میشود؛ اینجا فقط **خوانده** میشود و اگر
# معتبر نبود None برمی‌گردد با پرچمِ خطا — نه صفر، تا شاخص ۴ بر صفر تقسیم نکند.
HEMMAT_RIAL = 1e13          # ۱ همت = ۱۰^۱۲ تومان = ۱۰^۱۳ ریال

# دلیلِ نبودِ عدد، برای UI و برای v10_data_gaps — «داده نبود» ≠ «صفر» ≠ «رد»
MCAP_ERR_NO_ROW = "symbol_not_on_board"        # نماد فقط-کدال (صندوق/حق تقدم/…)
MCAP_ERR_NO_COL = "market_cap_column_missing"  # market.db پیش از مهاجرت v10
MCAP_ERR_NO_VALUE = "market_cap_missing_value"  # سطر هست ولی ستون NULL/≤0
MCAP_ERR_BAD_VALUE = "market_cap_invalid_value"  # NaN/inf در ستونِ ذخیره‌شده
MCAP_ERR_NO_BAND = "market_cap_no_live_band"    # مجازِ قیمت max<=min ⇒ نشانه، نه ارزش بازار


def hmt_to_rials(hmt) -> float:
    """همت → ریال. تنها نقطهٔ تبدیلِ این یکا در مسیر API؛ پیش‌شرطِ ارزش بازار و
    آستانهٔ نقدشوندگی هر دو همین‌جا به ریال می‌آیند (یک ضریب، دو مصرف)."""
    return _f(hmt) * HEMMAT_RIAL


def _rials_or_none(v) -> tuple:
    """تبدیلِ امنِ ستونِ ارزش بازار → (float|None, error|None).

    صفر/منفی/NaN/inf «ارزش بازار» نیستند؛ None برمی‌گرداند تا مصرف‌کننده
    مجبور نشود حدس بزند ۰ یعنی «بی‌داده» یا «واقعاً صفر».
    """
    if v is None:
        return None, MCAP_ERR_NO_VALUE
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None, MCAP_ERR_BAD_VALUE
    if x != x or x in (float("inf"), float("-inf")):
        return None, MCAP_ERR_BAD_VALUE
    if x <= 0:
        return None, MCAP_ERR_NO_VALUE
    return x, None


def _has_mcap_col(conn, table: str) -> bool:
    """واگرد به `fts_engine.has_market_cap_col` — تک‌پیاده‌سازیِ تشخیصِ ستون.

    کارت (اینجا) و موتور (`mcap_bulk_expr`) باید یک بانک را «ستون دارد/ندارد»
    یکسان ببینند؛ تشخیص بی‌کش است تا پاسخِ اتصالِ کهنه به اتصالِ تازه نشت نکند.
    """
    return fts_engine.has_market_cap_col(conn, table)


def ensure_market_cap_schema(conn) -> bool:
    """اگر market.db هنوز ستونِ ارزش بازار ندارد، می‌سازد و پر می‌کند.

    خودِ مهاجرت در test_tsetmc است (تک‌مسیرِ نوشتن)؛ این پوسته فقط برای DB‌ای
    است که پیش از ارتقا ساخته شده و هنوز سینک نشده. import تنبل — نبودش
    (نسخهٔ ناقصِ استقرار) نباید کارتِ بنیادی را بیندازد.
    """
    try:
        import test_tsetmc
        test_tsetmc.ensure_market_cap_schema(conn)
        return True
    except Exception:
        return False




def get_tsetmc_market_cap_info(symbol, db=None) -> dict:
    """ارزش بازارِ رسمیِ یک نماد → {rials, hmt, source, asof, stale, error}.

    `db` یا مسیرِ market.db است یا connectionِ باز (تا حلقهٔ واچ‌لیست همان
    اتصال را باز نگه دارد و N+1ِ بازکردن اتصال نداشته باشد).

    ترتیب خواندن — همان fallback که دستور کار خواسته، بدون هیچ ضربِ دستی:
      ۱) market_watch.market_cap            سطرِ جاریِ تابلو
      ۲) آخرین market_capِ معتبرِ daily_prices   تاریخچهٔ اسنپ‌شات (stale=True)
    اگر هیچ‌کدام معتبر نبود → `rials` برابر None + پرچمِ خطا. هرگز صفر برنمی‌گردد که
    شاخص ۴ آن را «بازارِ صفر» و نسبت را «بی‌نهایت» بخواند.
    """
    out = {"symbol": symbol, "rials": None, "hmt": None, "source": None,
           "asof": None, "stale": False, "error": None}
    own = db is None or isinstance(db, (str, bytes, os.PathLike))
    try:
        conn = db if not own else sqlite3.connect(str(db or DB_PATH), timeout=30)
    except Exception as e:
        out["error"] = "db_unavailable"
        out["reason"] = str(e)[:120]
        return out
    try:
        pred, params = fts_engine.sym_in("i.l_val18", symbol)
        where = "(%s OR %s)" % (pred, pred.replace("i.l_val18", "i.l_val30"))
        args = (*params, *params)
        if not _has_mcap_col(conn, "market_watch"):
            ensure_market_cap_schema(conn)
        if _has_mcap_col(conn, "market_watch"):
            has_band = (fts_engine.has_column(conn, "market_watch", "allowed_max")
                        and fts_engine.has_column(conn, "market_watch", "allowed_min"))
            # بانِ مرده از همان تک‌تعریفِ موتور (`mcap_dead_band_sql`) خوانده می‌شود،
            # پس کارت و اسکرینر یک ردیف را «ارزش بازار دارد/ندارد» می‌بینند.
            sel = ("m.market_cap, m.market_cap_src, m.d_even" +
                   (", CASE WHEN %s THEN 1 ELSE 0 END" % fts_engine.mcap_dead_band_sql("m")
                    if has_band else ""))
            try:
                row = conn.execute(
                    "SELECT " + sel +
                    " FROM market_watch m JOIN instruments i ON i.ins_code = m.ins_code"
                    " WHERE " + where + " ORDER BY i.updated_at DESC LIMIT 1", args).fetchone()
            except sqlite3.Error:
                row = None
            if row is not None and has_band and row[3]:
                # تابلو برایِ این نماد بانِ معاملۀ زنده ندارد (نشار: ۱٫۰ ریال با
                # مجازِ ۱٫۰ تا ۱٫۰ و صفردیدۀ معامله) ⇒ «قیمت × سهام» ارزشِ بازار
                # نیست. مقدار درِ بانک می‌ماند (حذف نمی‌شود) ولی واردِ محاسبهٔ
                # فروش÷ارزش نمی‌شود: None + پرچم — حتی از مسیرِ history.
                out["error"] = MCAP_ERR_NO_BAND
                out["asof"] = row[2]
                return out
        else:
            out["error"] = MCAP_ERR_NO_COL
            return out
        if row is not None:
            mcap, err = _rials_or_none(row[0])
            if mcap is not None:
                out.update({"rials": mcap, "hmt": round(mcap / HEMMAT_RIAL, 4),
                            "source": str(row[1] or "tse_board"), "asof": row[2]})
                return out
            out["error"] = err
            out["asof"] = row[2]
        else:
            on_board = conn.execute("SELECT 1 FROM instruments i WHERE " + where +
                                    " LIMIT 1", args).fetchone()
            out["error"] = MCAP_ERR_NO_ROW if not on_board else MCAP_ERR_NO_VALUE
        # ۲) آخرین مقدارِ معتبرِ ثبت‌شده (امروزِ خالی جای دیروزِ معتبر را نمی‌گیرد)
        if _has_mcap_col(conn, "daily_prices"):
            hist = conn.execute(
                "SELECT d.market_cap, d.market_cap_src, d.d_even"
                " FROM daily_prices d JOIN instruments i ON i.ins_code = d.ins_code"
                " WHERE " + where + " AND d.market_cap > 0"
                " ORDER BY d.d_even DESC LIMIT 1", args).fetchone()
            if hist:
                hm, herr = _rials_or_none(hist[0])
                if hm is not None:
                    out.update({"rials": hm, "hmt": round(hm / HEMMAT_RIAL, 4),
                                "source": str(hist[1] or "tse_board"),
                                "asof": hist[2], "stale": True, "error": None})
        elif out["error"] == MCAP_ERR_NO_VALUE:
            out["error"] = MCAP_ERR_NO_COL
        return out
    except Exception as e:
        out["error"] = "mcap_lookup_failed"
        out["reason"] = str(e)[:120]
        return out
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def get_tsetmc_market_cap(symbol, db=None):
    """رویهٔ سادهٔ SSoT: عددِ ریالی یا None. (جزئیات/خطا → get_tsetmc_market_cap_info)"""
    return get_tsetmc_market_cap_info(symbol, db=db)["rials"]


def board_total_market_cap(conn) -> tuple:
    """(کل ارزش بازارِ ریال, منبع).

    جمعِ ستونِ market_cap روی market_watch **ممنوع** است: یک شرکت چند ردیفِ
    تابلو دارد و ردیفِ نشست‌های قدیمی حذف نمی‌شود، پس جمعِ دستی ۲.۸ برابرِ
    عددِ واقعی می‌شود. عدد از mstat_engine.market_total_rials می‌آید (همان
    marketValue خودِ TSETMC)؛ اگر هنوز نیامده، خودِ تابع به جمعِ تابلو
    بازمی‌گردد و منبعِ پشتیبان را اعلام می‌کند.
    """
    total, src = mstat_engine.market_total_rials(conn)
    if total > 0:
        return total, src
    if _has_mcap_col(conn, "market_watch"):
        try:
            row = conn.execute("SELECT SUM(market_cap) FROM market_watch "
                               "WHERE market_cap > 0").fetchone()
            total = _f(row[0])
            if total > 0:
                return total, "market_watch.market_cap"
        except sqlite3.Error:
            pass
    return 0.0, MCAP_ERR_NO_COL
# ═══════════════════════════════════════════════════════════════════════════
#  طبقۀ شرکت — واگرد به تک‌مرجعِ fts_engine
# ═══════════════════════════════════════════════════════════════════════════
# جدولِ توکن‌ها و «مبنای درآمد» در `fts_engine.company_profile` زندگی می‌کند؛
# این‌جا فقط نامِ دوباره‌سازی‌نشده نگه داشته شده تا `evaluate_v10`، `ind1b`،
# `_growth_breadth` و گاردها (dev/fund_not_applicable_v1028.py و
# dev/test_fts_v10_ladder.py که این نام را صدا می‌زنند) بی‌تغییر کار کنند.
# پیش از این همین جدول دو جا بود و `bulk_scan` (که به `api/` دسترسی ندارد)
# نسخهٔ موتور را نمی‌دید ⇒ طبقۀ مالی/خدماتی در کارت N/A و در اسکرینر «فروش».
company_profile = fts_engine.company_profile
_PROFILE_LABEL = fts_engine._PROFILE_LABEL
_OP_BASIS_KINDS = fts_engine._OP_BASIS_KINDS




# ═══════════════════════════════════════════════════════════════════════════
#  سری گزارش فعالیت ماهانه — مبنای مشترک لایه‌های ۱ و ۴
# ═══════════════════════════════════════════════════════════════════════════
MS_COLS = "year, month, monthly_revenue, ytd_revenue, ytd_revenue_prev, period_end"


def _dedupe_ym(rows, ytd_idx: int = 3) -> list:
    """واگرد به `fts_engine._dedupe_ym` — یکی‌کردن ردیف‌هایِ (سال، ماه) یکِ جا."""
    return fts_engine._dedupe_ym(rows, ytd_idx)


def monthly_series(conn, symbol: str) -> list:
    """سریِ گزارشِ ماهانه — واگرد به تک‌منبعِ `fts_engine.monthly_series`.

    کارت، موتور و bulk از همین یک کوئری (با یک سقف) می‌خوانند؛ پیش از این کارت
    LIMIT ۶۰ و موتور LIMIT ۳۰ داشت و مخرجِ YoY گاه بیرونِ پنجرۀ موتور می‌ماند.
    """
    return fts_engine.monthly_series(conn, symbol)


def _fiscal_year_rows(series, year) -> list:
    """ردیف‌های یک سال مالی، ماهِ بیشتر اول (برای شمارش مِ ماه‌های سپری‌شده)."""
    rows = [r for r in series if int(_f(r[0])) == int(year)]
    rows.sort(key=lambda r: -int(_f(r[1])))
    return rows


# ─────────── لایهٔ ۱ب: دادهٔ فیزیکی (تناژ/تعداد) — در دسترس؟ ───────────
_VOL_NOW_KEYS = ("ytd_volume", "ytd_quantity", "ytd_tonnage", "ytd_qty",
                 "ytd_weight", "ytd_production", "ytd_sales_qty")
_VOL_PREV_KEYS = ("ytd_volume_prev", "ytd_quantity_prev", "ytd_tonnage_prev",
                  "ytd_qty_prev")


def _physical_pair(conn, symbol: str, year: int, month: int) -> tuple:
    """(کمیت تجمیعی دوره, کمیت تجمیعی همان دورهٔ سال قبل, نام ستون).

    امروز market.db هیچ ستون فیزیکی ندارد — هر ۱۳٬۶۴۲ ردیف monthly_sales فقط
    ستون ریالی دارند (راستی‌آزمایی با PRAGMA table_info) → خروجی (None, None,
    None) است و چک ۱ب به «تجزیهٔ اثر قیمت + پهنای رشد» تنزل میشود. به‌محض اینکه
    fetcher ستونی مانند `ytd_volume` اضافه کند، همین شاخص بی‌هیچ بازنویسی به
    دادهٔ واقعیِ تناژ سوییچ میکند.
    """
    try:
        present = {r[1] for r in conn.execute("PRAGMA table_info(monthly_sales)")}
    except Exception:
        return None, None, None
    col_now = next((c for c in _VOL_NOW_KEYS if c in present), None)
    if not col_now:
        return None, None, None
    col_prev = next((c for c in _VOL_PREV_KEYS if c in present), None)
    pred, params = fts_engine.sym_in("symbol", symbol)
    sel = "year, month, MAX(%s)" % col_now + (", MAX(%s)" % col_prev if col_prev else "")
    try:
        rows = conn.execute("SELECT %s FROM monthly_sales WHERE %s "
                            "GROUP BY year, month" % (sel, pred), params).fetchall()
    except Exception:
        return None, None, col_now
    table = {}
    for r in rows:
        try:
            table[(int(_f(r[0])), int(_f(r[1])))] = (r[2], r[3] if len(r) > 3 else None)
        except (TypeError, ValueError, IndexError):
            continue
    hit, prev = table.get((int(year), int(month))), table.get((int(year) - 1, int(month)))
    now = _f(hit[0]) if hit and hit[0] is not None else None
    back = None
    if prev and prev[0] is not None:
        back = _f(prev[0])
    elif hit and col_prev and len(hit) > 1 and hit[1] is not None:
        back = _f(hit[1])
    return now, back, col_now


def _growth_breadth(series, year: int, month: int) -> tuple:
    """پهنای رشد: از ماه ۱ تا م، چند ماه از نظر فروشِ تک‌ماهه بهتر از سال قبل است؟

    افزایش نرخ، همهٔ ماه‌ها را با هم بالا می‌برد؛ فروشِ یک‌بارهٔ انبار یا یک
    قراردادِ تک‌نفره فقط یک ماه را. پس «بیشترِ ماه‌ها رشد کرده باشند» شرطِ لازمِ
    دومِ تأیید فیزیکی است وقتی تناژ گزارش‌شده در دسترس نیست.
    """
    cur = {int(_f(r[1])): _f(r[2]) for r in series if int(_f(r[0])) == int(year)}
    prev = {int(_f(r[1])): _f(r[2]) for r in series if int(_f(r[0])) == int(year) - 1}
    improved = compared = 0
    for m in range(1, max(int(month), 0) + 1):
        if m in cur and cur[m] > 0 and m in prev and prev[m] > 0:
            compared += 1
            if cur[m] > prev[m]:
                improved += 1
    return improved, compared


# ═══════════════════════════════════════════════════════════════════════════
#  لایهٔ ۱الف — رشد ریالی (تجمیعی ÷ همان دورهٔ سال قبل) ≥ ۶۰٪
# ═══════════════════════════════════════════════════════════════════════════
_MS_GAP_HINT = ("با گرفتنِ دیتابیس تازهٔ کدال (دکمهٔ «دیتابیس کدال» در جدول غربالگری) "
                "گزارش‌های ماهانهٔ جاافتاده اضافه می‌شود.")


def ind1a_monetary_growth(conn, symbol, series=None, th=None, profile=None) -> dict:
    """فروش/درآمد تجمیعی از ابتدای سال مالی تا ماه آخر ÷ همان دورهٔ سال قبل.

    مخرج کسر هرگز «ماه قبل» نیست (قاعدهٔ جزوه). اولویت مخرج:
      ۱) ستون رسمیِ «مقایسه با دورهٔ مشابه سال قبل» در همان گزارش (ytd_revenue_prev)
      ۲) ردیف (سال−۱، همان ماه) از گزارش‌های ماهانه
    هر دو نبود → `data_gap` (شاخص «رد» محاسبه نمیشود، «قابل محاسبه نبود»).
    """
    th = th or v10_thresholds()
    series = series if series is not None else monthly_series(conn, symbol)
    prof = profile or company_profile()

    def _nodata(reason, **extra):
        gap = {"monetary_pct": None, "pass": False, "data_gap": True,
               "threshold": th["monetary_growth_min"],
               "revenue_basis": prof["revenue_basis"], "reason": reason,
               "remediation": _MS_GAP_HINT}
        gap.update(extra)
        return gap

    if not series:
        return _nodata("هیچ گزارش فعالیت ماهانه‌ای با فروش تجمیعی ثبت نشده است.")
    # مخرج از تک‌قاعدهٔ `fts_engine.ytd_denominator` می‌آید (ستونِ «مقایسه با
    # دورۀ مشابه سال قبل» ← ردیفِ سال−۱/همان ماه) — کارت نسخهٔ دومِ این
    # سلسلۀ‌مراتب را نداشت، فقط ترتیبِ کوئری‌اش فرق می‌کرد (LIMIT ۶۰ در برابر ۳۰).
    d = fts_engine.ytd_denominator(series)
    if not d:
        return _nodata("تجمیعیِ آخرین گزارش ماهانه صفر یا نامعتبر است.",
                       months=int(_f(series[0][1])), year=int(_f(series[0][0])))
    year, month, ytd_now = d["year"], d["month"], d["ytd_now"]
    basis = d["denominator_basis"]
    if d["ytd_prev"] is None:
        return _nodata("فروش تجمیعیِ همان دورۀ سال قبل در کدال ثبت نشده؛ "
                       "مقایسۀ سال‌به‌سال ممکن نیست.",
                       months=month, year=year, ytd_now_bt=_bt(ytd_now),
                       ytd_prev_bt=None, period="%02d/%d" % (month, year),
                       denominator_basis=basis)
    ytd_prev = d["ytd_prev"]
    growth = _pct(ytd_now, ytd_prev)
    return {"monetary_pct": growth,
            "ytd_now_bt": _bt(ytd_now), "ytd_prev_bt": _bt(ytd_prev),
            "ytd_now_mrl": ytd_now, "ytd_prev_mrl": ytd_prev,
            "period": "%02d/%d" % (month, year), "months": month, "year": year,
            "denominator_basis": basis, "revenue_basis": prof["revenue_basis"],
            "threshold": th["monetary_growth_min"],
            "pass": growth is not None and growth >= th["monetary_growth_min"],
            "data_gap": False, "reason": ""}


# ═══════════════════════════════════════════════════════════════════════════
#  لایهٔ ۱ب — رشد تولیدی/تناژ (ردِ سودِ صرفاً تورمی)
# ═══════════════════════════════════════════════════════════════════════════
def _is_consolidated_title(title) -> bool:
    """عنوان صورت مالی تلفیقی است؟ (همان قاعدهٔ fts_engine، بدون وابستگی خصوصی)"""
    return "تلفیقی" in fts_engine.norm_fa(title)


def ind1b_volume_growth(conn, symbol, monetary=None, series=None, th=None,
                        profile=None) -> dict:
    """چک دومِ لایهٔ ۱: آیا «مقدار» واقعاً زیاد شده یا فقط «نرخ» بالا رفته؟

    سه سطح، به ترتیب قدرتِ شواهد:
      A) `reported_quantity` — ستون فیزیکیِ تناژ/تعداد در گزارش ماهانه موجود باشد
         → رشد واقعیِ کمیت سنجیده میشود (قوی‌ترین حالت؛ امروز در DB چنین ستونی
            نیست، و به‌محض افزودنش توسط fetcher همین شاخص به آن سوییچ میکند).
      B) `price_effect_decomposition` — رشد اسمی با شاخص افزایش نرخ تعدیل میشود
         تا «رشد واقعی» بیرون بیاید؛ به‌علاوه پهنای رشد (چند ماه از م ماه بهتر
         بوده) که فروشِ یک‌بارهِ انبار/قراردادِ تکی را از رشدِ فراگیرِ حجم جدا
         میکند.
      C) `unavailable` — نه مخرج هست نه شاخص مرجع → چک «رد» محاسبه میشود، نه پاس.
    برای شرکت‌های مالی/خدماتی «تن محصول» معنا ندارد و سطح B دقیقاً همان چیزی
    است که جزوه می‌خواهد: درآمدِ واقعیِ پس از تورم.
    """
    th = th or v10_thresholds()
    prof = profile or company_profile()
    g = monetary if monetary is not None else ind1a_monetary_growth(
        conn, symbol, series=series, th=th, profile=prof)
    out = {"quantity_verified": False, "basis": "unavailable", "confidence": "none",
           "volume_pct": None, "real_pct": None, "implied_price_pct": None,
           "price_benchmark_pct": th["inflation_benchmark"], "breadth": None,
           "threshold": th["volume_growth_min"], "applicable": prof["volume_applicable"],
           "pass": False, "data_gap": True, "revenue_basis": prof["revenue_basis"],
           "note": prof["volume_note"]}
    if g.get("data_gap") or g.get("monetary_pct") is None:
        out["reason"] = "رشد ریالی محاسبه نشد؛ رشد تولیدی هم قابل بررسی نیست."
        return out
    year, month, monetary_pct = g["year"], g["months"], g["monetary_pct"]
    series = series if series is not None else monthly_series(conn, symbol)

    # ── سطح A: کمیت گزارش‌شده (تناژ/تعداد) ────────────────────────────────
    qty_now, qty_prev, col = _physical_pair(conn, symbol, year, month)
    if col and qty_now and qty_prev and qty_prev > 0:
        vol = _pct(qty_now, qty_prev)
        implied = (round(((1.0 + monetary_pct / 100.0) / (1.0 + vol / 100.0) - 1.0) * 100.0, 1)
                   if vol is not None else None)
        out.update({"basis": "reported_quantity", "quantity_verified": True,
                    "confidence": "high", "volume_pct": vol, "real_pct": vol,
                    "implied_price_pct": implied, "data_gap": False,
                    "quantity_column": col,
                    "source_detail": "ستون %s در گزارش فعالیت ماهانهٔ کدال" % col})
        out["pass"] = vol is not None and vol >= th["volume_growth_min"]
        out["reason"] = ("" if out["pass"] else
                         "فروش تولیدی کم شده یا ثابت مانده؛ رشد ریالی فقط از افزایش نرخ آمده است.")
        return out

    # ── سطح B: تجزیهٔ اثر قیمت + پهنای رشد ────────────────────────────────
    real = _real_growth(monetary_pct, th["inflation_benchmark"])
    improved, compared = _growth_breadth(series, year, month)
    breadth = round(improved / compared, 3) if compared else None
    out.update({"basis": "price_effect_decomposition",
                "confidence": "medium" if breadth is not None else "low",
                "real_pct": real, "data_gap": real is None,
                "implied_price_pct": th["inflation_benchmark"],
                "breadth": {"improved_months": improved, "compared_months": compared,
                            "ratio": breadth, "min": th["volume_breadth_min"]},
                "source_detail": "تعدیل رشد اسمی با شاخص افزایش نرخ %.0f٪ و پهنای رشد ماهانه"
                                 % th["inflation_benchmark"]})
    if real is None:
        out["reason"] = "شاخص مرجع افزایش نرخ موجود نیست."
        return out
    # پهنای رشد **دادهٔ نمایشی** است، نه دروازۀ امتیاز: جزوه برایِ «breadth» هیچ
    # فرمول یا آستانه‌ای ندارد، پس داوریِ ۱ب همان تعدیلِ رشد اسمی با مبنای تورم
    # است (رأیِ مالک ۱۴۰۵-۰۷-۱۱). موتورِ اسکرینر هم اصلاً پهنا نمی‌ساخت؛ با
    # گیت‌بودنِ آن، کارت و موتور دو داوریِ متفاوت برایِ یکِ نماد داشتند.
    out["pass"] = real >= th["volume_growth_min"]
    if out["pass"]:
        out["reason"] = ""
    else:
        out["reason"] = ("رشد اسمی %+.1f٪ کمتر از مبنای افزایش نرخ %.0f٪ است؛ "
                         "رشد واقعی منفی است (فقط قیمت بالا رفته)."
                         % (monetary_pct, th["inflation_benchmark"]))
    if breadth is not None and improved < compared:
        out["note_breadth"] = ("فقط %d از %d ماهِ سپری‌شده بهتر شده — رشد حجم فراگیر نیست."
                               % (improved, compared))
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  لایهٔ ۲ — سابقهٔ ۳ سالهٔ سودسازی (سال‌پایان + راستی‌آزمایی میاندوره‌ای)
# ═══════════════════════════════════════════════════════════════════════════
def _is_audited_title(title) -> bool:
    """عنوان «حسابرسی شده» دارد و «نشده» ندارد (همان قاعدهٔ fts_engine)."""
    t = fts_engine.norm_fa(title)
    return ("حسابرسی شده" in t) and ("نشده" not in t)


def _eps_track_blended(conn, symbol, years: int = 3) -> dict:
    """نردبانِ شاهدِ EPS — واگرد به `fts_engine.eps_ladder` (تک‌پیاده‌سازیِ مشترکِ
    کارت و اسکرینر؛ جزئیاتِ سطوح و قاعدهٔ «سطر حذف نشود» در آن docstring است).
    """
    return fts_engine.eps_ladder(conn, symbol, years=years)




def _interim_eps_check(conn, symbol, last_fy_eps=None, track_period_ends=(),
                       track_years=()) -> dict:
    """آیا سال مالی جاری هم با همان شتاب سودسازی پیش می‌رود؟

    از صورت‌های مالی میاندوره‌ای (۳/۶/۹ ماههٔ غیرتلفیقی) استفاده میکند:
    EPS تجمیعیِ میاندوره × ۱۲÷ماه = برآوردِ EPS سال جاری؛ مقایسه با آخرین EPS
    سال‌پایان، «تداومِ روند» یا «قطعِ روند» را نشان میدهد.

    دو گِردِشِ واقعی اینجا وجود دارد و هر دو بسته شده‌اند:
      · اگر همان میاندوره پیش‌تر داخلِ سابقه (track_period_ends) وارد شده باشد،
        مقایسهٔ عدد با خودش می‌شود.
      · اگر تازه‌ترین میاندوره از آخرین سالِ سابقه قدیمی‌تر باشد (مثلاً گزارش
        ۱۱ماههٔ سال ۱۴۰۴ در حالی که ۱۴۰۵ کامل در سابقه است)، «قطعِ روند» کاذب
        می‌سازد — پس فقط میاندورهٔ **جدیدتر از سال‌های سابقه** دیده میشود.
    """
    pred, params = fts_engine.sym_in("symbol", symbol)
    rows = conn.execute(
        "SELECT period_end, period_months, basic_eps, title FROM financial_statements "
        "WHERE %s AND %s AND period_months BETWEEN 1 AND 11 AND basic_eps IS NOT NULL "
        "ORDER BY period_end DESC LIMIT 40" % (pred, CP.DATED_SQL), params).fetchall()
    cand = [r for r in rows if not _is_consolidated_title(r[3] or "")]
    if not cand:
        return {"available": False, "reason": "صورت مالی میاندوره‌ایِ غیرتلفیقی ثبت نشده."}
    seen = set(track_period_ends or ())
    try:
        newest_ty = max(int(y) for y in (track_years or ()))
    except (TypeError, ValueError):
        newest_ty = 0
    if newest_ty:
        newer = [r for r in cand if int(CP.fiscal_year(r[0]) or 0) > newest_ty]
        if not newer:
            return {"available": False,
                    "reason": "میاندورهٔ تازه‌تر از آخرین سالِ سابقه ثبت نشده است."}
        cand = newer
    pe, pm, eps, title = cand[0]
    pe_c = CP.canonicalize(pe) or ""
    if pe_c in seen:
        return {"available": False, "period_end": pe_c,
                "reason": "میاندورهٔ جاری به‌عنوان سالِ در‌جریان داخل خودِ سابقه محاسبه شده."}
    pm = int(_f(pm)) or 1
    eps = _f(eps)
    y = int(CP.fiscal_year(pe) or 0)
    prev = next((r for r in cand[1:] if CP.fiscal_year(r[0]) == str(y - 1)
                 and int(_f(r[1])) == pm), None)
    projected = round(eps * 12.0 / pm, 2)
    return {"available": True, "period_end": pe_c, "period_months": pm,
            "eps_interim": round(eps, 2), "eps_projected_year": projected,
            "same_period_last_year": (None if prev is None else round(_f(prev[2]), 2)),
            "interim_yoy_pct": _pct(eps, _f(prev[2])) if prev is not None else None,
            "continues_trend": (None if last_fy_eps is None
                                else projected > _f(last_fy_eps)),
            "annualize_label": "EPS میاندوره × ۱۲÷%d" % pm,
            "title": str(title or "")[:70]}


def ind2_eps_track(conn, symbol, th=None, sector="", last_fy_eps=None) -> dict:
    """لایهٔ ۲ (EPS سه سال مالی متوالی، اکیداً صعودی و همگی مثبت) — لایۀ نمایشِ کارت.

    داوری در `fts_engine.eps_assessment` است (نردبانِ پنج‌سطحی + بیمه + حکمِ
    «فقط تلفیقی ⇒ na»)؛ همان تابعی که `scan_symbol`/`bulk_scan` می‌خوانند، پس
    کارت و اسکرینر دو عدد از دو قاعده نمی‌بینند. این‌جا فقط سه چیز افزوده می‌شود:
    نشانه‌هایِ جدول (partial/period_slots)، درصدِ رشدِ سال‌به‌سالِ سری
    (`eps_yoy_pct` — رأیِ #101: موتور می‌سازد، UI دوباره حک نمی‌کند)، و
    راستی‌آزماییِ میاندوره (`interim_confirms` — هشدارِ نرم، وتوی سخت نه؛
    قراردادِ v9.7.4).
    """
    th = th or v10_thresholds()
    need = int(th["eps_years"])
    # تک‌منبعِ داوری: `fts_engine.eps_assessment` — همان نردبانی که مسیرِ اسکرینر
    # می‌خواند (سطح ۱ = سال‌پایانِ حسابرسی‌شدهٔ غیرتلفیقی … سطح ۵ = میاندوره ×۱۲÷م،
    # پیش‌گیتِ بیمه، و حکمِ «فقط تلفیقی ⇒ na»). کارت هیچ قاعدۀ انتخابِ دوم
    # نمی‌سازد؛ فقط لایۀ نمایش (partial، eps_yoy_pct، راستی‌آزمایی میاندوره) رویش
    # می‌نشیند. پیش‌تر این‌جا strict و blended جدا خوانده و دو‌بار انتخاب
    # می‌شدند — همان دودلی که شاخص ۲ را بین کارت و اسکرینر واگرا می‌کرد.
    base = fts_engine.eps_assessment(conn, symbol, years=need, sector=sector)
    tier = str(base.get("evidence_tier") or "insufficient")
    insurance = (tier == "insurance")
    # حالتِ «ناقص»: دوره‌های موجود نشان داده میشوند و جایِ غایب «-»
    _ser = base.get("eps_series") or []
    _real = [v for v in _ser if v is not None]
    base["partial"] = bool(base.get("partial")) or (
        bool(_ser) and len(_real) < int(base.get("years_required") or need))
    base.setdefault("available_periods", len(_real))
    base.setdefault("periods_missing", max(int(base.get("years_required") or need)
                                           - len(_real), 0))
    if not base.get("period_slots"):
        base["period_slots"] = [str(y) for y in (base.get("fiscal_years") or [])]
    # #101: درصد رشد سال‌به‌سالِ همین سری — موتور می‌سازد تا UI عدد را دوباره
    # حک نکن؛ جایی که درصد قابل محاسبه نیست None می‌ماند (نه ۰٪).
    base["eps_yoy_pct"] = _eps_yoy_pct(_ser)
    latest = None
    try:
        if _real:
            latest = float(_real[-1])
    except (TypeError, ValueError, IndexError):
        latest = None
    interim = _interim_eps_check(conn, symbol,
                                 last_fy_eps=latest if latest is not None else last_fy_eps,
                                 track_period_ends=base.get("period_ends") or (),
                                 track_years=base.get("fiscal_years") or ())
    base["interim"] = interim
    base["interim_confirms"] = (None if not interim.get("available")
                                or interim.get("continues_trend") is None
                                else bool(interim["continues_trend"]))
    base["eps_basis"] = ("%s%s" % (
        {"audited_year_end": "سال‌پایانِ حسابرسی‌شدهٔ غیرتلفیقی",
         "unaudited_year_end": "سال‌پایانِ غیرتلفیقی (حسابرسی‌نشده)",
         "year_end_unaudited": "سال‌پایانِ غیرتلفیقی (حسابرسی‌نشده)",
         "consolidated_year_end": "سال‌پایانِ تلفیقی (غیرتلفیقیِ ۱۲ماهه موجود نیست)",
         "year_end_plus_interim": "سال‌پایان + میاندورهٔ سال‌سازی‌شده × ۱۲÷م",
         "insurance": "صنعت بیمه — لایهٔ EPS اجرا نمی‌شود",
         "insufficient": "شاهدِ کافی برای مسیر EPS موجود نیست"}.get(
             tier, "شاهدِ کافی برای مسیر EPS موجود نیست"),
        " + راستی‌آزمایی میاندوره‌ای" if interim.get("available")
        else " (میاندورهٔ مستقلِ راستی‌آزمایی موجود نیست)"))
    base["threshold"] = "%d سال مالی متوالی" % need
    base.setdefault("consolidated_used", False)
    base.setdefault("low_quality_track", False)
    base.setdefault("soft_gap", False)
    base.setdefault("source", "کدال — صورت سود و زیان (حسابرسی شده، شرکت اصلی)")
    base.setdefault("reason", "")
    return base


# ═══════════════════════════════════════════════════════════════════════════
#  لایهٔ ۳ — حاشیهٔ سود ناخالص (سود ناخالص ÷ درآمدهای عملیاتی)
# ═══════════════════════════════════════════════════════════════════════════
def ind3_gross_margin(conn, symbol, th=None, ref=None, profile=None) -> dict:
    """حاشیه = سود ناخالص ÷ درآمدهای عملیاتی × ۱۰۰ — ایده‌آل ≥۳۰٪، قابل‌قبول ≥۲۰٪.

    منبع و فرمول از fts_engine.gross_margin می‌آید (سالانهٔ حسابرسی‌شدهٔ
    غیرتلفیقی)؛ v10 فقط «باند» را شفاف میکند و برای طبقاتی که بهای تمام‌شده
    ندارند (بانک/صندوق) حالتِ not_applicable برمی‌گرداند به‌جای صفرِ کاذب.
    """
    th = th or v10_thresholds()
    gm = fts_engine.gross_margin(conn, symbol, min_margin=th["margin_min"],
                                 optimal=th["margin_ideal"], ref=ref)
    if not gm:
        # «حاشیه نیست» با «داده نیست» یکی نیست. fts_engine.gross_margin در چند
        # حالتِ متفاوت None می‌دهد و کاربر باید تفاوت را بفهمد، وگرنه برای نمادی
        # که فقط همگام‌سازی نشده، «بهای تمام‌شده ندارد» می‌خواند و هرگز دکمهٔ
        # «دیتابیس کدال» را نمی‌زند. `ref` از قبل در دست است؛ کوئریِ تازه لازم نیست.
        prof = profile or company_profile()
        if ref is None:
            reason = ("صورت مالی سالانهٔ این نماد در پایگاه کدال ما نیست؛ "
                      "تا آن نیاید، سود ناخالص و در نتیجه حاشیه محاسبه نمی‌شود.")
            fix = ("با دکمهٔ «دیتابیس کدال» صورت‌های مالی این نماد را تازه کنید؛ "
                   "این شکاف با انتشار گزارش بعدی هم خودبه‌خود بسته می‌شود.")
            data_gap = True
        elif prof.get("kind") == "fund":
            # رأیِ ۱۵: صندوق «رد شده» نمی‌گیرد. علت را هم باید همان‌طور گفت.
            reason = ("این نماد صندوق است؛ صندوق «فروش» و «بهای تمام‌شده» ندارد که "
                      "حاشیهٔ ناخالص از آن‌ها ساخته شود. نبودِ این عدد نقص نیست.")
            fix = "برای صندوق‌ها شاخص ۳ سنجیده نمی‌شود؛ کارتِ بنیادیِ صندوق را ببینید."
            data_gap = False
        elif _f(ref.get("revenue")) <= 0:
            reason = ("درآمد عملیاتیِ سالِ مرجع (%s) در کدال خالی یا صفر ثبت شده، "
                      "پس تقسیمِ سود ناخالص بر آن ممکن نیست."
                      % _fa_date(ref.get("period_end")))
            fix = "با گرفتنِ دیتابیس تازهٔ کدال یا انتشار صورت سود و زیان سالانه بسته می‌شود."
            data_gap = True
        else:
            # نامِ صنعت را دلیل نمی‌کنیم: وسدید در جدول «فلزات اساسي» است ولی
            # درآمدش «سود سهام» است. آنچه قطعی است، نبودِ خودِ سطر در صورتِ مالی‌ست.
            reason = ("در صورت سود و زیانِ سالِ مرجع (%s) سطر «سود ناخالص» یا "
                      "«بهای تمام‌شدهٔ کالای فروش‌رفته» ثبت نشده است؛ "
                      "بدونِ این سطر، حاشیهٔ ناخالص محاسبه نمی‌شود."
                      % _fa_date(ref.get("period_end")))
            fix = "نقص داده نیست — تا خودِ کدال این سطر را منتشر نکند، شاخص ۳ سنجیده نمی‌شود."
            data_gap = False
        return {"margin_pct": None, "pass": False, "ideal": False, "na": True,
                "band": "not_applicable", "threshold": th["margin_min"],
                "ideal_threshold": th["margin_ideal"], "optimal": False,
                "data_gap": data_gap, "reason": reason, "remediation": fix}
    # حاشیۀ منفیِ واقعی (ثتران −۱۸۴٫۶، دامین −۱۴۲٫۵، وملل −۱۱۲٫۵) «N/A» نیست:
    # عدد است و طبیعی به «زیرِ باند» می‌رسد. `_sane(-99, 200)` همین را None می‌کرد
    # و باند را هم اشتباه می‌براند (و حاشیۀ ۱٬۸۸۵٪ را هم)؛ اینجا فقط NaN/inf دور
    # ریخته می‌شود — همان کاری که `_f` می‌کند. آستانۀ تازه‌ای اضافه نشده است.
    margin = _f(gm.get("margin_pct"))
    # حاشیه غایب یا نامعتبر: زیر باند (بدون داده) و نه کرش مقایسه با None
    gm["band"] = ("ideal" if margin is not None and margin >= th["margin_ideal"] else
                  "acceptable" if margin is not None and margin >= th["margin_min"] else "below")
    gm["ideal"] = bool(gm.get("optimal"))
    gm["ideal_threshold"] = th["margin_ideal"]
    gm["na"] = False
    gm.setdefault("reason", "")
    return gm


# ═══════════════════════════════════════════════════════════════════════════
#  لایهٔ ۴ — سالانه‌سازیِ پویا (×۱۲÷م) و نسبت‌های ارزش‌گذاری
# ═══════════════════════════════════════════════════════════════════════════
ANNUALIZATION_SCALE = (3, 4, 5, 6, 9, 12)


def dynamic_annualized_sales(conn, symbol, series=None, ref=None, profile=None,
                             exempt=None) -> dict:
    """لایۀ ۴ کارت — واگرد به `fts_engine.annualized_sales` (تک‌پیاده‌سازی).

    ضریبِ ثابت نیست: ۳ ماه ×۴، ۴ ماه ×۳، ۶ ماه ×۲ … (م = بلندترینِ ماهِ دارایِ
    گزارشِ تجمیعی در آخرین سالِ مالی، نه تقویم). طبقۀ مالی/خدماتی/صندوق/هلدینگ
    «فروش کالا» ندارد ⇒ مبنایش درآمدِ صورتِ مالیِ سالانه، و حکمِ معافیت از
    `fts_engine.ind4_exempt` می‌آید (تک‌مرجعِ کارت و اسکرینر).
    جزئیاتِ قاعده و گیتِ «واحد مشکوک» در docstring خودِ آن تابع است.
    """
    return fts_engine.annualized_sales(conn, symbol, ref=ref, series=series,
                                       profile=profile, exempt=exempt)




def ind4_valuation(annual, gm, market_cap_rials, th=None, exempt=False) -> dict:
    """۴الف فروش سالانه ÷ ارزش بازار (≥۱×) + ۴ب پتانسیل سود ناخالص ÷ ارزش بازار (≥۴۰٪).

    سود ناخالص پتانسیل = فروش سالانهٔ annualized × حاشیهٔ ناخالص.
    برای شرکت مالی که «سود ناخالص» ندارد، حاشیهٔ سود خالص به‌عنوان «مبنای
    جایگزین» مصرف و صریحاً برچسب می‌خورد تا با عددِ شرکت تولیدی اشتباه نشود.

    `exempt` تنها ورودیِ تصمیمِ N/A است و باید از fts_engine.ind4_exempt بیاید
    (تک‌مرجعِ مشترکِ اسکرینر و کارت). این تابع دیگر خودش هیچ معیارِ نام/طبقه‌ای
    ندارد — پیش از این `kind == "holding"` را می‌دید و با معافیتِ موتور
    (صنعت + شاهدِ درآمدِ عملیاتی) در ۲۳۱ نماد واگرا بود.
    """
    th = th or v10_thresholds()
    # سند v2.1: برای طبقهٔ معاف، فروش‌به‌ارزش‌بازار و جانشین NAV ممنوع ⇒ N/A
    if exempt:
        return {"available": False, "na": True, "exempt": True, "pass": False,
                "potential_pass": False, "sales_pass": False, "rule_ref": "F-04",
                "reason": "شرکت سرمایه‌گذاری/هلدینگ؛ نسبت فروش به ارزش بازار کاربرد ندارد (N/A)."}
    mcap = _f(market_cap_rials)
    if not annual or mcap <= 0:
        return {"available": False, "pass": False, "potential_pass": False,
                "sales_pass": False, "mcap_ht": round(mcap / 1e13, 2),
                "potential_threshold": th["potential_min"],
                "sales_threshold": th["sales_to_mcap_min"],
                "reason": "دادهٔ ارزش بازار یا فروش سالانه برای محاسبه نسبت در دسترس نیست."}
    ann_rial = _f(annual["annual_sales_mrl"]) * MRL_TO_RIAL
    sales_ratio = ann_rial / mcap
    margin = None
    margin_basis, margin_label = "gross_margin", "حاشیهٔ سود ناخالص"
    if gm and not gm.get("na"):
        margin = _f(gm.get("margin_pct")) or None
    elif gm and gm.get("net_margin_pct") is not None:
        margin = _f(gm["net_margin_pct"])
        margin_basis, margin_label = "net_margin_proxy", "حاشیهٔ سود خالص (جایگزینِ مالی)"
    pot_raw = (ann_rial * (margin / 100.0) / mcap * 100.0) if margin is not None else None
    pot_pct = round(pot_raw, 1) if pot_raw is not None else None
    sales_pass = sales_ratio >= th["sales_to_mcap_min"]
    # مقایسه با عددِ **خام** (همان قاعدۀ `fts_engine.gross_profit_potential`)؛
    # با عددِ گرد شده، پتانسیلِ ۳۹٫۹۶٪ «≥ ۴۰٪» می‌شد و کارت با موتور نمی‌خواند.
    pot_pass = pot_raw is not None and pot_raw >= th["potential_min"]
    return {"available": True, "mcap_ht": round(mcap / 1e13, 2),
            "annual_sales_bt": annual["annual_sales_bt"],
            "months_used": annual["months_used"], "scale_factor": annual["scale_factor"],
            "annualize_basis": annual["basis"], "reconciled": annual["reconciled"],
            "sales_to_mcap": (round(sales_ratio, 2)
                           if _sane(sales_ratio, -1000.0, 1000.0) is not None else None),
            "sales_threshold": th["sales_to_mcap_min"], "sales_pass": sales_pass,
            "margin_used_pct": margin, "margin_basis": margin_basis,
            "margin_label": margin_label,
            "est_gross_profit_bt": (_bt(annual["annual_sales_mrl"] * (margin / 100.0))
                                    if margin is not None else None),
            "potential_pct": pot_pct, "potential_threshold": th["potential_min"],
            "potential_pass": pot_pass, "rule_ref": "F-04", "gate": "OR",
            "pass": bool(sales_pass or pot_pass),
            "reason": (("قبولی با نسبت فروش/ارزش‌بازار" if sales_pass else
                        "قبولی با پوشش پتانسیل سود" if pot_pass else
                        "نه نسبت فروش و نه پوشش پتانسیل به حد نصاب نرسید.")
                       if margin is not None else
                       "هیچ حاشیه‌ای (ناخالص یا جایگزین) برای این طبقه محاسبه نشد.")}


# ═══════════════════════════════════════════════════════════════════════════
#  لایهٔ ۵ — رژیم قیمت‌گذاری صنعت و چشم‌انداز
# ═══════════════════════════════════════════════════════════════════════════
_PRICING_OUTLOOK = {
    "free": ("قیمت‌گذاری آزاد / بورس کالا / صادرات‌محور — نرخ از بازار می‌آید، پس "
             "رشد فروش قابلِ اتکا به تورم ریالی نیست و باید با حجم ثابت شود."),
    "mandatory": ("قیمت‌گذاری دستوری — نرخ توسط شورای رقابت/دولت تعیین میشود؛ "
                  "رشد فروش بدون مجوز افزایش نرخ عملاً ممکن نیست و افزایش حاشیه "
                  "مشمول مجوز است. استراتژی FTS این گروه را از سبد بیرون می‌گذارد."),
    "neutral": ("سایر صنایع (غیردستوری) — نیازمند بررسی موردیِ نرخ محصول و مجوز "
                "افزایش قیمت."),
}


def ind5_industry(sector, cfg=None, market_cap_rials=0.0, total_market_cap_rials=0.0,
                  gpm=None, sales_growth=None) -> dict:
    """تگ صنعت: آزاد/بورس‌کالایی در برابر دستوری (دیکشنری fts_engine، بدون موازی‌سازی).

    `gpm` و `sales_growth` هم مثلِ مسیرِ اسکرینر پاس داده می‌شوند: استثنای دارویی
    و بانک هر دو به آن‌ها نگاه می‌کنند، و بی‌آن‌ها کارت برایِ یکِ نمادِ دارویی
    «خنثی» می‌گفت جایی که موتور «دستوری» می‌گفت (رأیِ ۱۶: بی‌داده = خنثی، نه رد).
    """
    sec = fts_engine.sector_filter(sector, cfg=cfg, market_cap_rials=market_cap_rials,
                                   total_market_cap_rials=total_market_cap_rials,
                                   gpm=gpm, sales_growth=sales_growth)
    verdict = sec.get("verdict", "neutral")
    sec["outlook"] = _PRICING_OUTLOOK.get(verdict, _PRICING_OUTLOOK["neutral"])
    sec["regime_label"] = {"free": "آزاد / بورس کالا", "mandatory": "دستوری",
                           "neutral": "سایر صنایع"}[verdict]
    sec["rule_ref"] = "F-05"
    return sec


# ═══════════════════════════════════════════════════════════════════════════
#  فیلترهای ریسک و پیش‌شرط‌های حذف (ماده ۱۴۱ / نقدشوندگی / کف ارزش بازار / صنعت)
# ═══════════════════════════════════════════════════════════════════════════
def norm_industry_list(value) -> list:
    """فهرست صنایعِ پانل → لیستِ نرمال‌شده.

    ویرگولِ لاتین و فارسی («،») هر دو جداکننده‌اند؛ فاصله‌ها trimmed؛ و «ی/ک»
    عربی به فارسی برگردانده می‌شود — همان norm_fa که fts_engine در تطبیقِ تگ
    صنعت مصرف میکند، پس «پتروشیمی» با «پتروشیمی» (ي عربی) یکی میشود.
    """
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.replace("\u060c", ",").split(",")
    else:
        parts = list(value or [])
    out, seen = [], set()
    for p in parts:
        t = fts_engine.norm_fa(str(p or "").strip())
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def industry_gate(sector: str, cfg: dict = None, sec: dict = None) -> dict:
    """حالت Include/Exclude روی فهرستِ دستیِ صنایع — جدا از رژیم قیمت‌گذاری.

    `industry_mode` سه مقدار می‌پذیرد:
      Exclude_Mandatory_Pricing (پیش‌فرض) / Rank_Only → رفتارِ قیمت‌گذاریِ fts_engine
      Exclude_Industries → هر نمادی که صنعتش در `exclude_industries` باشد حذف
      Include_Industries → فقط صنایعِ داخل `include_industries` می‌مانند
    تطبیق «زیررشته» است چون sector_name کاملِ تابلو طولانی‌تر از برچسبِ پانل است
    («فلزات اساسی» ⊃ «فلزات») — همان قاعده‌ای که mandatory_sectors دارد.
    """
    cfg = cfg or {}
    mode = str(cfg.get("industry_mode") or "Exclude_Mandatory_Pricing").strip()
    s = fts_engine.norm_fa(sector)
    res = {"active": mode in ("Exclude_Industries", "Include_Industries"),
           "mode": mode, "pass": True, "matched": [], "reason": "",
           "include": norm_industry_list(cfg.get("include_industries")),
           "exclude": norm_industry_list(cfg.get("exclude_industries"))}
    if not res["active"]:
        return res
    if mode == "Include_Industries":
        hits = [t for t in res["include"] if t in s]
        res["matched"] = hits
        res["pass"] = bool(hits)
        if not hits:
            res["reason"] = ("صنعت «%s» در فهرستِ شاملِ پنل نیست — حذف خودکار"
                             % (sector or "—"))
    else:
        hits = [t for t in res["exclude"] if t in s]
        res["matched"] = hits
        if hits:
            res["pass"] = False
            res["reason"] = ("صنعت «%s» در فهرستِ مستثنیِ پنل است — حذف خودکار"
                             % (sector or "—"))
    return res


def m141_hit(conn, symbol, m141_map=None) -> bool:
    """ماده ۱۴۱: دارایی خالص ≤ نصفِ سرمایهٔ ثبت‌شده (زیان انباشته > ۵۰٪ سرمایه).

    تعریف و منبعِ محاسبه از fts_engine.m141_map می‌آید (تک‌کوئریِ کل بازار با
    کلیدِ norm_fa) — این‌جا فقط نقشه یک‌بار ساخته یا تزریق می‌شود تا حلقهٔ
    واچ‌لیست به N+1 نیفتد؛ نبودِ صورت‌مالیِ سالانه «مشمول نیست» است، نه «رد».
    """
    if m141_map is None:
        m141_map = fts_engine.m141_map(conn)
    return bool(m141_map.get(fts_engine.norm_fa(symbol), False))


def trade_value_hmt(conn, symbol, liq_map=None) -> float:
    """میانگین ارزش معاملات روزانه به **همتِ واقعی** (None/بی‌داده → 0.0).

    نکتهٔ واحد — fts_engine.avg_trade_value_hmt با وجود نامش، عدد را ÷۱۰^۱۰
    برمی‌گرداند، یعنی «میلیارد تومان»، نه همت. طبق قاعدهٔ جزوه ۱ همت =
    ۱۰^۱۲ تومان = ۱۰^۳ میلیارد تومان؛ پس تقسیمِ همان عدد بر ۱۰۰۰ همتِ درست
    می‌دهد. بدون این تصحیح، آستانهٔ «۲ همت» عملاً ۲ میلیارد تومان بود و
    نقدشوندگیِ تقریباً کل بازار قبول می‌شد.
    """
    if liq_map is None:
        liq_map = fts_engine.avg_trade_value_hmt(conn)
    v = liq_map.get(fts_engine.norm_fa(symbol))
    return 0.0 if v is None else _f(v) / 1000.0


def risk_gates(conn, symbol, sector, mcap_rials, cfg=None, th=None,
               m141_map=None, liq_map=None, gate=None) -> list:
    """دلیلِ حذف‌های خودکار (خارج از پنج محور) — فهرستِ رشته‌های فارسی."""
    cfg = cfg or {}
    reasons = []
    if fts_engine.is_insurance_sector(sector):
        reasons.append("صنعت بیمه — حذف خودکار")
    try:
        if fts_engine.is_suspended(conn, symbol, int(cfg.get("suspended_max_stale_sessions", 3) or 3)):
            reasons.append("نماد تعلیق — حذف خودکار")
    except Exception:
        pass
    # ۱) ماده ۱۴۱ — وقتی روشن است، نمادِ مشمول فوراً از واچ‌لیست بیرون می‌رود
    if cfg.get("filter_m141") and m141_hit(conn, symbol, m141_map=m141_map):
        reasons.append("ماده ۱۴۱ — زیان انباشته بیش از نصف سرمایه")
    # ۲) کف ارزش بازار — ورودیِ پانل «همت» است؛ ۱ همت = ۱۰^۱۳ ریال
    floor = hmt_to_rials(cfg.get("mcap_min_hmt"))
    if floor > 0:
        mcap = _f(mcap_rials)
        if mcap <= 0:
            reasons.append("ارزش بازار نامشخص (کف ارزش بازار قابل بررسی نیست)")
        elif mcap < floor:
            reasons.append("ارزش بازار (%s همت) زیرِ کفِ %s همت"
                           % (_n(mcap / HEMMAT_RIAL, 2), _n(_f(cfg.get("mcap_min_hmt")), 2)))
    # ۳) نقدشوندگی — حداقلِ میانگین ارزش معاملات روزانه (همت)
    min_liq = _f(cfg.get("min_trade_val"))
    if min_liq > 0:
        tv = trade_value_hmt(conn, symbol, liq_map=liq_map)
        if tv <= 0:
            reasons.append("ارزش معاملات ناموجود (پیش‌شرط نقدشوندگی احراز نشد)")
        elif tv < min_liq:
            reasons.append("نقدشوندگی (%s همت) زیرِ کفِ %s همت"
                           % (_n(tv, 4), _n(min_liq, 4)))

    # ۴) فیلتر صنعت Include/Exclude
    g = gate if gate is not None else industry_gate(sector, cfg)
    if g.get("active") and not g.get("pass") and g.get("reason"):
        reasons.append(g["reason"])
    return reasons


# ═══════════════════════════════════════════════════════════════════════════
#  ارزیاتور مرکزی — اجرای پنج لایه روی یک نماد
# ═══════════════════════════════════════════════════════════════════════════

def evaluate_v10(conn, symbol, market_cap_rials=0.0, total_market_cap_rials=0.0,
                 sector="", cfg=None, company_name="", m141_map=None,
                 liq_map=None) -> dict:
    """خروجیِ یکپارچهٔ v10: پنج لایه + پاس‌ها + امتیاز + دلایل حذف.

    `m141_map` / `liq_map` برای مسیرهای دسته‌ای (واچ‌لیست) تزریق میشوند تا
    نقشه‌های کل‌بازاری یک‌بار ساخته شوند، نه به ازای هر نماد — همان قراردادی
    که fts_engine.scan_symbol با m141_hit/avg_trade_val دارد.

    یک کوئریِ سری ماهانه و یک صورت‌مالیِ مرجع یک‌بار خوانده میشوند و به همهٔ
    لایه‌ها پاس داده میشوند (الگوی ضدِ N+1 خودِ fts_engine) — نه اینکه هر لایه
    مستقل دوباره همان ۶۰ ردیف را بخواند.
    """
    cfg = cfg or {}
    th = v10_thresholds(cfg)
    prof = company_profile(sector, company_name)
    series = monthly_series(conn, symbol)
    ref = fts_engine.reference_annual(conn, symbol)

    growth = ind1a_monetary_growth(conn, symbol, series=series, th=th, profile=prof)
    volume = ind1b_volume_growth(conn, symbol, monetary=growth, series=series,
                                 th=th, profile=prof)
    eps = ind2_eps_track(conn, symbol, th=th, sector=sector)
    gm = ind3_gross_margin(conn, symbol, th=th, ref=ref, profile=prof)
    if gm.get("na") and ref:
        rev, net = _f(ref.get("revenue")), _f(ref.get("net_profit"))
        # حاشیهٔ جایگزین فقط وقتی معنادار است: مخرج مثبت و نتیجه در بازهٔ منطقی.
        # (روی این DB نمادهایی هست که فروشِ صورت‌مالی‌شان کوچک‌تر از سود خالص ثبت
        #  شده — حاشیهٔ >۱۰۰٪ یعنی واحد/سطرِ گزارش غلط است، نه سودآوری فراوان.)
        if rev > 0 and net and 0 < (net / rev * 100.0) <= 100.0:
            gm["net_margin_pct"] = round(net / rev * 100.0, 1)
            gm["net_margin_period"] = CP.canonicalize(ref.get("period_end")) or ""
        elif rev > 0 and net:
            gm["net_margin_rejected_pct"] = round(net / rev * 100.0, 1)
    # سند v2.1: گیتِ «عدم اعمال نسبت فروش بر هلدینگ‌ها» (holdings_sales_na).
    # و حکمِ معافیت از fts_engine.ind4_exempt می‌آید — همان تابعی که
    # bulk_scan/scan_symbol (مسیرِ اسکرینر) صدا می‌زنند. `conn` همین‌جا باز است،
    # پس نه کوئریِ دوباره‌ای لازم است و نه منطقِ موازیِ دوم که بتواند واگرا شود.
    _holdings_na = bool((cfg or {}).get("holdings_sales_na", True))
    ind4_na = fts_engine.ind4_exempt(conn, symbol, sector, holdings_na=_holdings_na)
    annual = dynamic_annualized_sales(conn, symbol, series=series, ref=ref,
                                      profile=prof, exempt=ind4_na)
    val = ind4_valuation(annual, gm, market_cap_rials, th=th, exempt=ind4_na)
    # تک‌منبع: فیلتر صنعت و استثنای دارویی/بانکی در `fts_engine.sector_filter`
    # است — همان تابعی که bulk_scan/scan_symbol صدا می‌زنند. کارت پیش از این
    # هیچ gpm/رشدی نمی‌داد و بعداً بلوکِ تکراریِ «pharma_margin_exempt_min» را
    # خودش اعمال می‌کرد (و چون آن کلید درِ fts_thresholds.json نیست، عملاً
    # خاموش می‌ماند) ⇒ نمادِ دارویی در کارت «خنثی» و در اسکرینر «دستوری».
    _gpm = gm.get("margin_pct") if isinstance(gm, dict) else None
    _grw = growth.get("monetary_pct") if isinstance(growth, dict) else None
    sec = ind5_industry(sector, cfg=cfg, market_cap_rials=market_cap_rials,
                        total_market_cap_rials=total_market_cap_rials,
                        gpm=_gpm, sales_growth=_grw)

    # ممیزی (سند v2.1): ارجاع قاعده روی هر شاخص بنیادی
    try:
        growth["rule_ref"] = "F-01"
        volume["rule_ref"] = "F-01b"
        eps["rule_ref"] = "F-02"
        gm["rule_ref"] = "F-03"
    except Exception:
        pass
    axis1 = bool(growth.get("pass") and volume.get("pass"))
    axis2 = bool(eps.get("pass"))
    axis3 = bool(gm.get("pass"))
    axis4 = bool(val.get("pass"))
    axis5 = bool(sec.get("pass"))
    passes = {"1_growth": axis1, "2_eps_trend": axis2, "3_gross_margin": axis3,
              "4_sales_to_mcap": axis4, "5_industry": axis5,
              "1a_monetary_growth": bool(growth.get("pass")),
              "1b_volume_growth": bool(volume.get("pass")),
              "4a_sales_to_mcap": bool(val.get("sales_pass")),
              "4b_profit_potential": bool(val.get("potential_pass"))}
    score = sum(1 for k in ("1_growth", "2_eps_trend", "3_gross_margin",
                            "4_sales_to_mcap", "5_industry") if passes[k])
    # جزوه ص ۶: «سه آیتم اول مهم‌تر هستند» — F1-F3 بلاک‌اند، F4/F5 مرتب‌سازیِ دوم.
    primary_score = sum(1 for k in ("1_growth", "2_eps_trend", "3_gross_margin")
                        if passes[k])

    reasons = []
    if sec.get("verdict") == "mandatory" and sec.get("exclusion_active"):
        reasons.append("قیمت‌گذاری دستوری — حذف خودکار")
    # v10: همهٔ حذف‌های خودکار در یک نقطه — بیمه / تعلیق / ماده ۱۴۱ /
    # کف ارزش بازار / نقدشوندگی / Include-Excludeِ صنایعِ پنل.
    gate = industry_gate(sector, cfg)
    reasons += risk_gates(conn, symbol, sector, market_cap_rials, cfg=cfg, th=th,
                          m141_map=m141_map, liq_map=liq_map, gate=gate)

    # رأیِ مالک (۱۴۰۵-۰۷-۰۳): FTS برای شرکت‌های عملیاتی است؛ صندوق باید
    # «FTS ندارد» بگیرد نه REJECT با جدولِ خالی. عددِ امتیاز همین‌جا دست‌نخورده
    # می‌ماند (اسکرینر روی آن sort می‌کند و None آن را می‌شکند) — فقط مسیرِ
    # پاسخِ جزئیات آن را خالی نشان می‌دهد.
    applicable = (prof or {}).get("kind") != "fund"
    verdict = ("FTS ندارد" if not applicable else
               ("EXCLUDED" if reasons else
                "STRONG" if score >= 4 and primary_score == 3 else
                "WATCH" if score >= 3 else "REJECT"))

    return {"symbol": symbol, "sector": sector, "pricing_mode": sec.get("verdict"),
            "market_cap_rials": _f(market_cap_rials), "score": score,
            "primary_score": primary_score,
            "applicable": applicable,
            "passes": passes, "excluded": bool(reasons), "exclusion_reasons": reasons,
            "verdict": verdict,
            "methodology": {"version": "FTS-v10", "axes": 5,
                            "layer_1_subchecks": ("1a_monetary", "1b_volume"),
                            "annualization": "sales_ytd * (12 / elapsed_months)",
                            "thresholds": th},
            "profile": prof, "series_months": len(series), "ref": ref,
            "indicators": {"1": {"monetary": growth, "volume": volume, "pass": axis1},
                           "2": eps, "3": gm,
                           "4": dict(val, annual=annual), "5": sec}}




# ═══════════════════════════════════════════════════════════════════════════
#  متن‌ساز کارت‌ها — همان ۵ لایه برای UI و برای خروجی CSV (app.js فرجمد)
# ═══════════════════════════════════════════════════════════════════════════
def _state(passed, na=False, gap=False) -> str:
    if na:
        return "na"
    if gap:
        return "nodata"
    return "pass" if passed else "fail"


def _pct_txt(v, signed=True) -> str:
    if v is None:
        return "—"
    return (("%+.1f" if signed else "%.1f") % v) + "٪"


def _sane(v, lo=None, hi=None):
    """گارد مقادیر غیرمعقول منبع: خارج از بازه ⇒ None (بدون حذف بی‌صدا)."""
    x = _f(v)
    if x is None:
        return None
    if lo is not None and x < lo:
        return None
    if hi is not None and x > hi:
        return None
    return x


def _n(v, nd=0) -> str:
    """عددِ خوانا با جداکنندهٔ هزارگان — None/خطا → «—» (نه صفرِ گمراه‌کننده)."""
    try:
        return ("{:,.%df}" % nd).format(float(v))
    except (TypeError, ValueError):
        return "—"


# ── جدول بنیادی: قواعدِ نمایشِ دوره‌های ناقص ────────────────────────────────
# دستورالعملِ خروجی جدول: اگر دادهٔ «شاخص ۲» ناقص بود و تنها ۲ دوره (به‌جای ۳)
# موجود بود، (۱) سطر هرگز حذف نمیشود — مقادیرِ موجود درج و جایِ دورهٔ ناموجود
# علامت «-» می‌آید؛ (۲) عنوان و سلول‌های سطر کامل قرمز میشود و ذکر میگردد که
# فقط ۲ دوره موجود است.
_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa(v) -> str:
    """ارقامِ لاتین → فارسی برایِ برچسب‌های جدول."""
    return str(v).translate(_FA_DIGITS)


def _eps_cells(e: dict) -> tuple:
    """سلول‌های جدولِ شاخص ۲ — همیشه به بلندایِ دوره‌های لازم؛ غایب → «-»."""
    slots = list(e.get("period_slots") or e.get("fiscal_years") or [])
    vals = list(e.get("eps_series") or [])
    need = int(e.get("years_required") or len(slots) or len(vals) or 3)
    if len(vals) < need:
        vals = [None] * (need - len(vals)) + vals      # جایِ خالی = قدیمی‌ترین دوره
    if len(slots) < need:
        slots = [""] * (need - len(slots)) + slots
    cells = ["-" if v is None else _n(v) for v in vals[:need]]
    return cells, [str(s) for s in slots[:need]]


def _eps_row(e: dict) -> dict:
    """سطرِ آمادهٔ جدولِ شاخص ۲ (متنِ markdown با برچسبِ قرمز در حالتِ ناقص)."""
    cells, slots = _eps_cells(e)
    need = len(cells)
    try:
        avail = int(e.get("available_periods"))
    except (TypeError, ValueError):
        avail = sum(1 for c in cells if c != "-")
    if not avail:
        avail = sum(1 for c in cells if c != "-")
    partial = 0 < avail < need
    lbl = "شاخص ۲" + ((" (تنها %s دوره موجود است)" % _fa(avail)) if partial else "")
    if partial:
        def sp(x):
            return '<span style="color: red;">%s</span>' % x
        md = "|" + sp(lbl) + "| " + " | ".join(sp(c) for c in cells) + "|"
    else:
        md = "| %s | " % lbl + " | ".join(cells) + " |"
    return {"label": lbl, "cells": cells, "markdown": md, "red": partial,
            "available": avail, "required": need,
            "periods": [{"year": s or "—", "value": c, "missing": c == "-"}
                        for s, c in zip(slots, cells)]}


def build_insights(res: dict) -> tuple:
    """(insights, details) — یک ورودی برای هر لایه + زیرچک‌های ساختاریافته.

    `insights` همان قراردادِ قدیمی (step/title/text) است که app.js برای خروجی
    CSV مصرف میکند؛ `details[step]["subchecks"]` لایهٔ جدیدِ v10 است که کارتِ
    بنیادی با آن «چک الف/ب» را جدا می‌نمایشد.
    """
    ind = res["indicators"]
    th = res["methodology"]["thresholds"]
    prof = res["profile"]
    g, v = ind["1"]["monetary"], ind["1"]["volume"]
    insights, details = [], {}

    # ── لایهٔ ۱: درآمد/فروش (۱الف ریالی + ۱ب فیزیکی) ──────────────────────
    axis1 = bool(g.get("pass") and v.get("pass"))
    if g.get("data_gap"):
        txt1 = "⚠️ ۱الف رشد ریالی: داده موجود نیست (%s)" % (g.get("reason") or "مخرج YoY غایب")
    elif g.get("pass"):
        txt1 = "✅ ۱الف رشد ریالی: %s (کف %g٪ احراز شد)" % (
            _pct_txt(g.get("monetary_pct")), th["monetary_growth_min"])
    else:
        txt1 = "⚠️ ۱الف رشد ریالی: %s (زیر کف %g٪)" % (
            _pct_txt(g.get("monetary_pct")), th["monetary_growth_min"])

    _BASIS_FA = {
        "price_effect_decomposition": "تعدیل اثر تورمی",
        "reported_quantity": "تناژ گزارش‌شده",
        "direct_quantity": "تناژ مستقیم",
        "quantity_verified": "تناژ تأییدشده",
    }
    basis_str = _BASIS_FA.get(str(v.get("basis")), str(v.get("basis") or "تعدیل تورمی"))

    if v.get("data_gap"):
        txt1b = "⚠️ ۱ب رشد تولیدی: عدم دسترسی به داده" if not v.get("reason") else ("⚠️ ۱ب رشد تولیدی: %s" % v.get("reason"))
    elif v.get("pass"):
        txt1b = "✅ ۱ب رشد تولیدی: تأیید شد (%s)" % basis_str
    else:
        v_reason = (v.get("reason") or
                    "رشد صرفاً از افزایش نرخ است (فاقد رشد حجم)")
        txt1b = "🚫 ۱ب رشد تولیدی: %s" % v_reason
    insights.append({"step": "۱", "title": "لایهٔ ۱ — درآمد/فروش (رشد ریالی + تأیید حجم)",
                     "type": "success" if axis1 else "warning",
                     "text": "%s<br>%s" % (txt1, txt1b)})
    breadth = v.get("breadth") or {}
    details["۱"] = {
        "title": "درآمد/فروش — رشد ریالی (۱الف) + تأیید حجم (۱ب)",
        "formula": ("۱الف = (تجمیعی دوره ÷ تجمیعی همان دورهٔ سال قبل) × ۱۰۰ − ۱۰۰ · پاس ≥ %g٪"
                    " · ۱ب = رشد کمیت ≥ %g٪ یا رشد واقعیِ پس از تورم ≥ %g٪"
                    " · پهنای رشد (%d/%d ماه) فقط نمایشی است، دروازۀ امتیاز نیست"
                    % (th["monetary_growth_min"], th["volume_growth_min"],
                       th["volume_growth_min"],
                       breadth.get("improved_months") or 0,
                       breadth.get("compared_months") or 0)),
        "source": ("کدال — گزارش فعالیت ماهانهٔ منتهی به %s | مخرج: %s | طبقهٔ شرکت: %s"
                   % (g.get("period") or "—", g.get("denominator_basis") or "—", prof["label"])),
        "calc": ("%s ÷ %s میلیارد تومان = %s | ۱ب: مبنای %s → رشد واقعی %s (مبنای نرخ %s٪)"
                 % (_n(g.get("ytd_now_bt")), _n(g.get("ytd_prev_bt")),
                    _pct_txt(g.get("monetary_pct")), v.get("basis") or "—",
                    _pct_txt(v.get("real_pct")), _n(v.get("price_benchmark_pct")))),
        "what": ("%s<br>%s<br>شواهد حجم: %s%s"
                 % (prof["revenue_basis"], prof["volume_note"],
                    v.get("source_detail") or "—",
                    (" — پهنای رشد: %d/%d ماه" % (breadth.get("improved_months", 0),
                                                  breadth.get("compared_months", 0)))
                    if breadth.get("compared_months") else "")),
        "subchecks": [
            {"key": "1a", "label": "رشد ریالی",
             "state": _state(g.get("pass"), gap=bool(g.get("data_gap"))),
             "value": _pct_txt(g.get("monetary_pct")),
             "threshold": "≥ %g٪" % th["monetary_growth_min"],
             "detail": "تجمیعی %s ÷ %s میلیارد تومان (%s)"
                       % (_n(g.get("ytd_now_bt")), _n(g.get("ytd_prev_bt")),
                          g.get("period") or "—")},
            {"key": "1b", "label": "رشد تولیدی / تناژ",
             "state": _state(v.get("pass"), gap=bool(v.get("data_gap"))),
             "value": _pct_txt(v.get("volume_pct") if v.get("quantity_verified")
                               else v.get("real_pct")),
             "threshold": "≥ %g٪" % th["volume_growth_min"],
             "verified": bool(v.get("quantity_verified")),
             "confidence": v.get("confidence"),
             "detail": "%s (اطمینان %s)" % (basis_str, {"high": "بالا", "medium": "متوسط", "low": "پایین"}.get(str(v.get("confidence")), str(v.get("confidence") or "—")))}]}


    # ── لایهٔ ۲: سابقهٔ ۳ سالهٔ سودسازی ───────────────────────────────────
    e = ind["2"]
    itm = e.get("interim") or {}
    _EV_SHORT = {"audited_year_end": "حسابرسی‌شده",
                 "unaudited_year_end": "حسابرسی‌نشده",
                 "consolidated_audited": "تلفیقیِ حسابرسی‌شده",
                 "consolidated_unaudited": "تلفیقیِ حسابرسی‌نشده",
                 "annualized_interim": "میاندوره × ۱۲÷م",
                 "annualized_interim_short": "میاندورهٔ کوتاه × ۱۲÷م",
                 "missing": "بدون داده"}
    _ev_list = e.get("evidence") or []
    _cells, _slots = _eps_cells(e)
    _row = _eps_row(e)
    _partial = bool(_row["red"])
    _avail = int(_row["available"])
    ev_detail = (" | ".join("%s %s%s" % (y or "—", v,
                                         "" if v == "-"
                                         else " (%s)" % _EV_SHORT.get(tw, ""))
                            for y, v, tw in zip(_slots, _cells,
                                                _ev_list + [""] * len(_cells)))
                 if _cells else "—")
    _EV_FA = {"audited_year_end": "۱۲ماههٔ حسابرسی‌شدهٔ شرکت اصلی (غیرتلفیقی)",
              "year_end_unaudited": "سال‌پایانِ غیرتلفیقیِ حسابرسی‌نشده "
                                    "(صورت حسابرسی‌شدهٔ آن سال‌ها در کدال نیست)",
              "consolidated_year_end": "سال‌پایانِ تلفیقی "
                                       "(صورت ۱۲ماههٔ غیرتلفیقی منتشر نشده)",
              "year_end_plus_interim": "سال‌پایان + سال‌سازیِ میاندوره × ۱۲÷م "
                                       "برای تکمیلِ سه سال",
              "insufficient": "مبنای معتبری یافت نشد"}
    ev_fa = _EV_FA.get(e.get("evidence_tier") or "", "")
    ev_badge = ("" if e.get("strict_evidence") or e.get("data_gap")
                else " (%s)" % (
                    "تلفیقی" if e.get("consolidated_used") else
                    "میاندوره" if e.get("low_quality_track") else
                    "حسابرسی‌نشده"))
    if e.get("data_gap") and _partial:
        # قاعدهٔ جدول: سطر هرگز حذف نمیشود — مقادیرِ موجود + «-» برایِ دورهٔ
        # غایب، و عنوان/سلول‌ها قرمز با ذکرِ تعدادِ دوره‌های موجود.
        insights.append({"step": "۲", "title": "لایهٔ ۲ — سابقهٔ ۳ سالهٔ سودسازی (EPS)",
                         "type": "danger", "partial": True,
                         "row": _row["markdown"],
                         "text": "🚫 شاخص ۲ (تنها %s دوره موجود است) — سابقه EPS: %s ریال · %s"
                                 % (_fa(_avail), " ← ".join(_cells),
                                    e.get("reason") or "کمبود صورت مالی")})
    elif e.get("data_gap"):
        insights.append({"step": "۲", "title": "لایهٔ ۲ — سابقهٔ ۳ سالهٔ سودسازی (EPS)",
                         "type": "warning",
                         "text": "⚠️ سابقه EPS در دسترس نیست — %s" % (e.get("reason") or "کمبود صورت مالی")})
    elif e.get("pass"):
        insights.append({"step": "۲", "title": "لایهٔ ۲ — سابقهٔ ۳ سالهٔ سودسازی (EPS)",
                         "type": "success",
                         "text": "✅ روند سودسازی صعودی — EPS: %s ریال (%s)%s%s"
                                 % (" ← ".join(_cells),
                                    " ← ".join(str(y) for y in (e.get("fiscal_years") or [])),
                                    ev_badge,
                                    "" if e.get("interim_confirms") is not False
                                    else " — ⚠️ عدم تأیید در میاندوره")})
    else:
        _vals = " ← ".join(_cells)
        insights.append({"step": "۲", "title": "لایهٔ ۲ — سابقهٔ ۳ سالهٔ سودسازی (EPS)",
                         "type": "warning" if e.get("soft_gap") else "danger",
                         "text": "%s%s%s" % (
                             "⚠️ " if e.get("soft_gap") else "🚫 ",
                             (("%s | سابقه EPS: %s ریال" % (e.get("reason"), _vals))
                              if _vals and e.get("reason")
                              else (e.get("reason") or "روند صعودی سه‌ساله برقرار نیست")),
                             ev_badge)})
    details["۲"] = {
        "title": "سابقهٔ سودسازی (EPS سه سال + تداوم میاندوره)",
        "formula": ("EPSy > EPSy−1 > EPSy−2 · %d سال مالیِ متوالی · مبنای امروزی: %s · "
                    "تداوم: EPS میاندوره × ۱۲÷م ≥ آخرین EPS سال‌پایان"
                    % (th["eps_years"], ev_fa or "—")),
        "source": e.get("source") or "کدال — صورت سود و زیان",
        "calc": ("EPS: %s | متوالی: %s | مثبت: %s | میاندوره %s → برآورد سال %s (تعداد %s)"
                 % (" | ".join(_cells) or "—",
                    "بله" if e.get("consecutive_years") else "خیر",
                    "بله" if e.get("all_profitable") else "خیر",
                    itm.get("period_end") or "—", _n(itm.get("eps_projected_year"), 2),
                    {True: "تأیید", False: "قطع", None: "نامعلوم"}[e.get("interim_confirms")])),
        # سطرِ آمادهٔ جدول (سلول‌ها + markdownِ قرمز در حالتِ ناقص) — برای UI و خروجی
        "period_row": _row,
        "what": ("لایهٔ سختِ v8 (فقط ۱۲ماههٔ حسابرسی‌شدهٔ غیرتلفیقی) روی این دیتابیس "
                 "برای نمادهای زیادی صفر رکورد می‌دهد؛ نسخهٔ ۱۰ همان مسیر را با "
                 "سال‌پایان و میاندوره می‌سنجد ولی هر تنزلِ شاهد را صریح برچسب میزند "
                 "تا کاربر بداند EPS از کدالِ غیرتلفیقیِ حسابرسی‌شده آمده یا از "
                 "جایگزین‌های ضعیف‌تر. تداومِ سال جاری هشدارِ نرم است، وتوی سخت نه. "
                 "در کمبودِ دوره هم سطر حذف نمیشود: مقدارِ موجود می‌آید و جایِ "
                 "دورهٔ غایب «-» با سطرِ قرمز."),
        "subchecks": [
            {"key": "2a", "label": "سابقهٔ ۳ سالهٔ EPS"
                                   + (" (تنها %s دوره موجود است)" % _fa(_avail)
                                      if _partial else ""),
             "state": ("nodata" if e.get("data_gap") and not _partial
                       else "fail" if _partial           # ناقص = قرمز، نه خاکستری
                       else "warn" if e.get("soft_gap")
                       else _state(e.get("pass"))),
             "value": " ← ".join(_cells) or "—",
             "threshold": "%d سال صعودی" % th["eps_years"],
             "partial": _partial, "available_periods": _avail,
             "periods": _row["periods"], "row": _row["markdown"],
             "detail": ev_detail or "—"},
            {"key": "2b", "label": "تداوم در دورهٔ میاندوره‌ای",
             "state": ("na" if not itm.get("available")
                       or all(c == "-" for c in _cells)
                       else "pass" if e.get("interim_confirms") else "warn"),
             "value": _pct_txt(itm.get("interim_yoy_pct")),
             "threshold": "برآورد ≥ آخرین EPS سال‌پایان",
             "detail": "%s · دوره %s" % (itm.get("annualize_label") or "—",
                                         itm.get("period_end") or "—")}]}

    # ── لایهٔ ۳: حاشیهٔ سود ناخالص ────────────────────────────────────────
    gm = ind["3"]
    if gm.get("na"):
        insights.append({"step": "۳", "title": "لایهٔ ۳ — حاشیهٔ سود ناخالص",
                         "type": "info", "text": "ℹ️ %s" % gm.get("reason")})
    elif gm.get("band") == "ideal":
        insights.append({"step": "۳", "title": "لایهٔ ۳ — حاشیهٔ سود ناخالص",
                         "type": "success",
                         "text": "✅ حاشیهٔ ناخالص: %s (ایده‌آل ≥ %g٪)"
                                 % (_pct_txt(gm.get("margin_pct"), signed=False),
                                    th["margin_ideal"])})
    elif gm.get("pass"):
        insights.append({"step": "۳", "title": "لایهٔ ۳ — حاشیهٔ سود ناخالص",
                         "type": "info",
                         "text": "✅ حاشیهٔ ناخالص: %s (قابل‌قبول ≥ %g٪)"
                                 % (_pct_txt(gm.get("margin_pct"), signed=False),
                                    th["margin_min"])})
    else:
        insights.append({"step": "۳", "title": "لایهٔ ۳ — حاشیهٔ سود ناخالص",
                         "type": "warning",
                         "text": "⚠️ حاشیهٔ ناخالص: %s (زیر کف %g٪)"
                                 % (_pct_txt(gm.get("margin_pct"), signed=False),
                                    th["margin_min"])})
    details["۳"] = {
        "title": "حاشیهٔ سود ناخالص",
        "formula": ("حاشیه = (سود ناخالص ÷ درآمدهای عملیاتی) × ۱۰۰ · ایده‌آل ≥ %g٪ · "
                    "قابل‌قبول ≥ %g٪" % (th["margin_ideal"], th["margin_min"])),
        "source": "کدال — صورت سود و زیان سالانهٔ %s (%s)" % (gm.get("period_end") or "—",
                                                             gm.get("basis") or "—"),
        "calc": "سود ناخالص %s ÷ درآمدهای عملیاتی %s × ۱۰۰ = %s (باند: %s)" % (
            _n(gm.get("gross_profit_bt")), _n(gm.get("revenue_bt")),
            _pct_txt(gm.get("margin_pct"), signed=False), gm.get("band") or "—"),
        "what": ("سود ناخالص = درآمدهای عملیاتی − بهای تمام‌شدهٔ کالای فروش‌رفته؛ "
                 "سود عملیاتی و سود خالص در این لایه نقشی ندارند."),
        "subchecks": [
            {"key": "3", "label": "حاشیهٔ ناخالص",
             "state": ("na" if gm.get("na") else "pass" if gm.get("pass") else "fail"),
             "value": _pct_txt(gm.get("margin_pct"), signed=False),
             "threshold": "≥ %g٪ (ایده‌آل %g٪)" % (th["margin_min"], th["margin_ideal"]),
             "detail": "باند: %s" % (gm.get("band") or "—")}]}


    # ── لایهٔ ۴: سالانه‌سازیِ پویا + پتانسیل سود به ارزش بازار ────────────
    val = ind["4"]
    ann = val.get("annual") or {}
    if not val.get("available"):
        insights.append({"step": "۴", "title": "لایهٔ ۴ — پتانسیل سود سالانه به ارزش بازار",
                         "type": "warning",
                         "text": "⚠️ %s" % (val.get("reason") or "قابل محاسبه نیست")})
    else:
        pot_ok = "✅" if val.get("potential_pass") else "⚠️"
        s_ok = "✅" if val.get("sales_pass") else "⚠️"
        pot_txt = ("نامشخص" if val.get("potential_pct") is None
                   else "%s ارزش بازار (کف %g٪)"
                        % (_pct_txt(val.get("potential_pct"), signed=False),
                           val.get("potential_threshold") or 0))
        s_txt = ("نامشخص" if val.get("sales_to_mcap") is None
                 else "%g× (کف %g×)" % (val.get("sales_to_mcap"),
                                        val.get("sales_threshold") or 0))
        insights.append({
            "step": "۴", "title": "لایهٔ ۴ — پتانسیل سود سالانه به ارزش بازار",
            "type": "success" if val.get("pass") else "warning",
            "text": ("%s پتانسیل سود: %s · %s فروش به ارزش بازار: %s (سالانه‌سازی %d ماهه)"
                     % (pot_ok, pot_txt, s_ok, s_txt,
                        int(_f(ann.get("months_used")))))})
    details["۴"] = {
        "title": "پتانسیل سود با سالانه‌سازیِ پویا",
        "formula": ("م = ماه‌های سپری‌شده از گزارش ماهانه (۱…۱۲) · فروش سالانه = تجمیعی × "
                    "(۱۲ ÷ م) · سود ناخالص پتانسیل = فروش سالانه × حاشیهٔ ناخالص · "
                    "نسبت پتانسیل = سود پتانسیل ÷ ارزش بازار ≥ %g٪ · فروش ÷ ارزش بازار ≥ %g×"
                    % (th["potential_min"], th["sales_to_mcap_min"])),
        "source": ("ارزش بازار: TSETMC (تعداد سهام × قیمت پایانی = %s همت) | فروش و حاشیه: "
                   "کدال — گزارش فعالیت ماهانه + صورت مالی سالانه"
                   % _n(val.get("mcap_ht"), 2)),
        "calc": ("م = %d → ضریب × %s | %s | سود ناخالص پتانسیل %s میلیارد تومان ÷ ارزش بازار "
                 "%s همت = %s | مبنای حاشیه: %s%s"
                 % (int(_f(ann.get("months_used"))), _n(ann.get("scale_factor"), 2),
                    ann.get("basis") or "—", _n(val.get("est_gross_profit_bt")),
                    _n(val.get("mcap_ht"), 2),
                    _pct_txt(val.get("potential_pct"), signed=False),
                    val.get("margin_label") or "—",
                    "" if ann.get("reconciled", True) else " | ⚠️ Annualized مردود شد → فروش سالانهٔ کدال")),
        "what": ("ضریب سالانه‌سازی ثابت نیست: ۳ ماه ×۴، ۴ ماه ×۳، ۵ ماه ×۲٫۴، ۶ ماه ×۲ … — "
                 "تا نمادی که ۵ ماه از سال مالی‌اش گذشته با فروشِ ۵ ماه قضاوت نشود. "
                 "پتانسیل سود روی «سود ناخالص» است نه سود خالص، تا اوراق‌بهادار و "
                 "مواردِ مالیِ یک‌باره در آن راه نیابد."),
        "subchecks": [
            {"key": "4a", "label": "فروش سالانه ÷ ارزش بازار",
             "state": _state(val.get("sales_pass"), gap=not val.get("available")),
             "value": ("%g×" % val["sales_to_mcap"]) if val.get("sales_to_mcap") is not None else "—",
             "threshold": "≥ %g×" % (val.get("sales_threshold") or 0),
             "detail": "فروش سالانه %s میلیارد تومان (× %s برای %d ماه)"
                       % (_n(val.get("annual_sales_bt")), _n(ann.get("scale_factor"), 2),
                          int(_f(ann.get("months_used"))))},
            {"key": "4b", "label": "پتانسیل سود ناخالص ÷ ارزش بازار",
             "state": _state(val.get("potential_pass"), gap=val.get("potential_pct") is None),
             "value": _pct_txt(val.get("potential_pct"), signed=False),
             "threshold": "≥ %g٪" % (val.get("potential_threshold") or 0),
             "detail": "%s × %s = %s میلیارد تومان"
                       % (_n(val.get("annual_sales_bt")),
                          _pct_txt(val.get("margin_used_pct"), signed=False),
                          _n(val.get("est_gross_profit_bt")))}]}

    # ── لایهٔ ۵: رژیم قیمت‌گذاری صنعت ─────────────────────────────────────
    sec = ind["5"]
    verdict5 = sec.get("verdict")
    sector_name = (res.get("sector") or "").strip()
    has_sector = bool(sector_name and sector_name != "—")
    sec_display = sector_name if has_sector else "صنعت نامشخص"
    matched = sec.get("matched_tokens") or []
    tagline = (" · تگ: %s" % "، ".join(matched)) if matched else ""

    if verdict5 == "mandatory":
        insights.append({"step": "۵", "title": "لایهٔ ۵ — رژیم قیمت‌گذاری صنعت و چشم‌انداز",
                         "type": "danger",
                         "text": "🚫 قیمت‌گذاری دستوری: گروه «%s» مشمول نرخ‌گذاری دستوری است%s"
                                 % (sec_display, tagline)})
    elif verdict5 == "free":
        insights.append({"step": "۵", "title": "لایهٔ ۵ — رژیم قیمت‌گذاری صنعت و چشم‌انداز",
                         "type": "success",
                         "text": "✅ صنعت آزاد: گروه «%s» آزاد / بورس‌کالایی است%s"
                                 % (sec_display, tagline)})
    else:
        insights.append({"step": "۵", "title": "لایهٔ ۵ — رژیم قیمت‌گذاری صنعت و چشم‌انداز",
                         "type": "info",
                         "text": ("ℹ️ وضعیت صنعت: گروه «%s» غیردستوری (بررسی تکمیلی)%s"
                                  % (sec_display, tagline)) if has_sector else
                                 "ℹ️ صنعت نامشخص در تابلو؛ بررسی موردی"})
    details["۵"] = {
        "title": "رژیم قیمت‌گذاری صنعت",
        "formula": ("حالتِ پنل: %s · «دستوری» مردود است مگر حالت Rank_Only انتخاب شود"
                    % (sec.get("exclusion_active") and
                       "Exclude_Mandatory_Pricing" or "Rank_Only")),
        "source": "گروه صنعت: TSETMC (sector_name) | فهرست صنایع: پنل تنظیمات کدال",
        "calc": "طبقه: %s | تگ خورده: %s | حکم: %s | سهم از کل بازار: %s٪ (تکمیلی)" % (
            verdict5, "، ".join(sec.get("matched_tokens") or []) or "—",
            "پاس" if sec.get("pass") else "مردود", _n(sec.get("market_share_pct"), 3)),
        "what": sec.get("outlook"),
        "subchecks": [
            {"key": "5", "label": "رژیم قیمت‌گذاری",
             "state": "pass" if sec.get("pass") else "fail",
             "value": sec.get("regime_label") or "—",
             "threshold": "غیردستوری",
             "detail": "، ".join(sec.get("matched_tokens") or []) or "بدون تگ"}]}

    return insights, details


def v10_data_gaps(res: dict) -> list:
    """هر لایه‌ای که «قابل محاسبه نبود» شد + راه‌حلِ عملیِ بستنِ شکاف.

    این فهرست دلیلِ وجودِ «۰ امتیاز» را از «۰ امتیازِ واقعی» جدا میکند؛ رابط
    کاربری آن را به‌صورت بنر نمایش میدهد تا کاربر نداند شاخص رد شده یا داده کم است.
    """
    ind = res.get("indicators") or {}
    l1 = ind.get("1") or {}
    g, v = l1.get("monetary") or {}, l1.get("volume") or {}
    e, val = ind.get("2") or {}, ind.get("4") or {}
    m = ind.get("3") or {}
    ann = val.get("annual") or {}
    gaps = []
    if g.get("data_gap"):
        gaps.append({"layer": "۱الف", "axis": "1a_monetary_growth",
                     "why": g.get("reason") or "",
                     "fix": g.get("remediation") or _MS_GAP_HINT})
    if v.get("basis") == "unavailable":
        gaps.append({"layer": "۱ب", "axis": "1b_physical_volume",
                     "why": "کدال مقدار/تناژ فروش را در گزارش ماهانه نمی‌دهد؛ فقط مبلغِ ریالی ثبت شده است.",
                     "fix": "تا خودِ کدال ستونِ مقدار را منتشر نکند، رشد واقعی با تعدیل تورمی سنجیده می‌شود."})
    elif v.get("data_gap"):
        gaps.append({"layer": "۱ب", "axis": "1b_physical_volume",
                     "why": v.get("reason") or "", "fix": "گزارش ماهانهٔ سال قبل لازم است."})
    if e.get("data_gap"):
        gaps.append({"layer": "۲", "axis": "2_eps_trend", "why": e.get("reason") or "",
                     "available_periods": int(e.get("available_periods") or 0),
                     "required_periods": int(e.get("years_required") or 3),
                     "partial": bool(e.get("partial")),
                     "fix": "با گرفتنِ دیتابیس تازهٔ کدال، صورت‌های ۱۲ماههٔ سال‌های "
                            "قدیمی‌ترِ همین نماد اضافه می‌شود."})
    elif e.get("soft_gap"):
        gaps.append({"layer": "۲", "axis": "2_eps_trend", "why": e.get("reason") or "",
                     "fix": "با انتشار صورت ۱۲ماههٔ سال مالی جاری، داوری قطعی میشود."})
    if m.get("na"):
        # شاخص ۳ هیچ‌وقت در این فهرست نبود؛ یعنی رایج‌ترین سلولِ خالیِ جدول
        # (حاشیهٔ ناخالص) بی‌هیچ توضیحی می‌ماند. ind3_gross_margin علت را در سه
        # حالت جدا کرده — همین‌جا همان را به‌کار می‌بریم، چیز تازه‌ای نمی‌سازیم.
        gaps.append({"layer": "۳", "axis": "3_gross_margin",
                     "why": m.get("reason") or "سود ناخالصِ سالِ مرجع در کدال نیست.",
                     "fix": m.get("remediation") or "با همگام‌سازی کدال بررسی مجدد می‌شود."})
    if ann.get("reconciled") is False:
        gaps.append({"layer": "۴", "axis": "4_sales_to_mcap",
                     "why": "سالانه‌سازی ×۱۲÷م با گیتِ fts_engine سازگار نشد؛ "
                            "فروش سالانهٔ کدال جانشین شد.",
                     "fix": "گزارش‌های ماهانهٔ کاملِ همان سال مالی لازم است."})
    return gaps


def _sector_from_company(company_name):
    """سکتور از نام شرکت (همان منطق SectorGuess برای نمادهای فقط-کدال)."""
    n = fts_engine.norm_fa(company_name)
    if "صندوق" in n:
        return "صندوق سرمایه گذاری"
    if "بیمه" in n:
        return "بیمه"
    if "لیزینگ" in n:
        return "لیزینگ"
    if "بانك" in n or "بانک" in n:
        return "بانك"
    return "سایر"


_INSTR_SQL = """
    SELECT i.ins_code, i.sector_name, i.total_shares, m.p_closing, i.l_val18, i.l_val30
    FROM instruments i
    LEFT JOIN market_watch m ON i.ins_code = m.ins_code
    WHERE REPLACE(REPLACE(REPLACE(i.l_val18, 'ك', 'ک'), 'ي', 'ی'), 'ى', 'ی') = ?
    ORDER BY i.updated_at DESC LIMIT 1
"""


def _screen_verdict(r: dict) -> str:
    """داوریِ نهاییِ یک ردیف — تنها یک‌جا.

    جدولِ غربالگری و قیفِ نبض بازار هر دو همین را می‌خوانند؛ اگر این نگاشت
    دو بار نوشته شود، دو نمادِ یکسان دو داوریِ مختلف می‌گیرند.
    رأی ۱۵: صندوق در پنج‌شاخصه نمی‌گنجد — داوری ندارد، نه مردود.
    """
    if r.get("applicable") is False:
        return "NOT_APPLICABLE"
    if r.get("excluded"):
        return "REJECTED"
    score = int(r.get("score") or 0)
    if score == 5:
        return "SUPER_FUNDAMENTAL"
    if score == 4:
        return "PASSED"
    if score == 3:
        return "WATCHLIST"
    return "REJECTED"


@router.get("/api/fundamental/screen")
def api_fundamental_screen(
    verdict: Optional[str] = None,
    sector: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 0
):
    """غربالگری بازار بر اساس ۵ شاخص FTS — فیلتری رویِ همان payload که کارت می‌سازد.

    چرا (SCORE-PATH-1): این endpoint دومین پیاده‌سازیِ امتیازدهی بود. کارتِ
    جزئیات و /api/screener با evaluate_v10 می‌سنجند و bulk_scanِ خام هیچ‌یک از
    الحاقه‌هایِ بعدی را ندارد: نردبانِ EPSِ تلفیقی، معافیتِ شاخص ۴ (که به
    بانک/هلدینگ یک امتیازِ رایگان می‌داد)، استثنای حاشیهٔ دارویی، وتوی هفتگی.
    اندازه‌گیریِ ۱۴۰۵/۰۷/۰۳ رویِ کلِ بازار (۸۷۳ نماد، هر دو مسیر درونِ پروسه):
    امتیاز در ۴۵۶ نماد واگرا بود — محور ۲: ۱۴۵، محور ۴: ۳۰۶، محور ۵: ۲۵،
    محور ۱: ۸۵، محور ۳: صفر، و `applicable` صفر (رأی ۱۵ از پیش هم‌راستاست).
    یک سؤالِ روش‌شناسی دو جواب ندارد، پس این‌جا چیزی محاسبه نمی‌شود.

    مزیتِ دوم: اسکنِ سنگینِ دوم حذف شد. get_screener کشِ رم/دیسک و
    سریال‌سازیِ اسکنِ گرم دارد و این مسیر دورِ هر دو اجرا می‌شد — همان شکلی
    که در v1.0.22 «ردیفی نیامد» شد.

    سطرها را کپیِ سطحی می‌کنیم: `fts_verdict` رویِ آبجکتِ کش‌شده نمی‌نشیند،
    وگرنه پاسخِ /api/screener آلوده می‌شود.
    """
    from .screener import get_screener
    rows = get_screener().get("data") or []

    results = []
    for r in rows:
        sym = str(r.get("symbol") or "")
        name = str(r.get("name") or sym)

        if search:
            q = fts_engine.norm_fa(search).strip().lower()
            if q not in fts_engine.norm_fa(sym).lower() and q not in fts_engine.norm_fa(name).lower():
                continue

        if sector and r.get("sector_name") != sector:
            continue

        item = dict(r)
        item["name"] = name
        item["fts_verdict"] = _screen_verdict(r)

        if verdict and verdict != "ALL" and item["fts_verdict"] != verdict:
            continue

        results.append(item)

    if limit > 0:
        results = results[:limit]

    return {
        "status": "success",
        "count": len(results),
        "data": results,
        "symbols": results
    }


@router.get("/api/fundamental/sectors")
def api_fundamental_sectors():
    """فهرست صنایع بازار برای فیلتر در تب بنیادی."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT DISTINCT sector_name FROM instruments WHERE sector_name IS NOT NULL AND sector_name != '' ORDER BY sector_name"
        ).fetchall()
        secs = [r[0] for r in rows]
        return {"status": "success", "count": len(secs), "sectors": secs}
    finally:
        conn.close()


@router.get("/api/fundamental/{symbol}")
def get_fundamental(symbol: str, months: int = 0):
    """کارت بنیادی پنج‌لایهٔ FTS v10 — درآمد (ریالی+حجمی)، سودسازی، حاشیه، پتانسیل، صنعت.

    برخلاف v8 که فقط خروجیِ `fts_engine.scan_symbol` را بازآرایی میکرد، اینجا هر
    پنج لایه با قواعدِ نسخهٔ ۱۰ محاسبه میشوند: آستانهٔ ۶۰٪ برای رشد ریالی، چکِ
    الزامیِ رشد تولیدی، سابقهٔ ۳ سالهٔ EPS + تداوم میاندوره‌ای، حاشیهٔ ۲۰/۳۰٪،
    سالانه‌سازیِ پویا ×۱۲÷م با آستانهٔ ۳۳٪ پتانسیل سود، و رژیم قیمت‌گذاری صنعت.
    `months` برای سازگاری با فراخوانی‌های قدیمی پذیرفته میشود و در داوری اثر
    ندارد — «م» از خودِ گزارش‌های ماهانه خوانده میشود، نه از پارامتر کاربر.
    """
    conn = get_db()
    try:
        _pred_i, _params_i = fts_engine.sym_in("i.l_val18", symbol)
        inst = conn.execute(f"""
            SELECT i.ins_code, i.sector_name, i.total_shares, m.p_closing, i.l_val18, i.l_val30
            FROM instruments i
            LEFT JOIN market_watch m ON i.ins_code = m.ins_code
            WHERE {_pred_i}
            ORDER BY i.updated_at DESC LIMIT 1
        """, _params_i).fetchone()
        if not inst:
            inst = conn.execute(_INSTR_SQL, (fts_engine.norm_fa(symbol),)).fetchone()
        pred, params = fts_engine.sym_in("symbol", symbol)
        cn = conn.execute("SELECT company_name FROM financial_statements WHERE %s "
                          "%s LIMIT 1" % (pred, CP.latest_order_sql()),
                          params).fetchone()
        company_name = str(cn[0] or "") if cn else ""
        if not inst:
            # نمادهای فقط-کدال (صندوق‌ها و…): در instruments نیستند ولی اسکرینر نشانشان میدهد
            if not company_name:
                raise HTTPException(status_code=404, detail="Symbol not found")
            sector = _sector_from_company(company_name)
        else:
            sector = str(inst["sector_name"] or "")

        # نرمال‌سازی پسوند عددی (TSETMC: «آ س پ3» → کدال: «آ س پ»)
        norm_symbol, ref_reason = symbol, None
        option_contract = False
        m_und = re.match(r"^(.*?)\d+$", symbol)
        base_cand = m_und.group(1) if m_und else None
        if base_cand and base_cand != symbol and inst is None:
            inst = conn.execute(_INSTR_SQL, (base_cand,)).fetchone()
            if inst:
                sector = str(inst["sector_name"] or "")
                norm_symbol = base_cand
                ref_reason = "نماد با پسوند عددی — دادهٔ کدال روی نماد پایه"

        # ارزش بازار: فقط از ستونِ رسمیِ تابلو (get_tsetmc_market_cap_info).
        # ضربهٔ پشتیبانِ «total_shares × p_closing» عمداً حذف شد — اگر تابلو عددِ
        # معتبر ندارد، شاخص ۴ باید «قابل محاسبه نبود» بگوید، نه یک عدد ساختگی.
        mcap, _, total_mcap, mcap_info = _fts_market_ctx(conn, norm_symbol)

        cfg = load_fts_config()
        res = evaluate_v10(conn, norm_symbol, mcap or 0.0, total_mcap, sector,
                           cfg=cfg, company_name=company_name)
        # لایهٔ ۴ باید بگوید «چرا نشد»: نبودِ ارزش بازار از تابلو با نبودِ فروش
        # ماهانه دو چیز مختلف‌اند و دو کارِ مختلف کاربر را می‌طلبند.
        _val4 = res["indicators"]["4"]
        _val4["market_cap_source"] = mcap_info.get("source")
        _val4["market_cap_error"] = mcap_info.get("error")
        _val4["market_cap_asof"] = mcap_info.get("asof")
        _val4["market_cap_stale"] = bool(mcap_info.get("stale"))
        if not mcap_info.get("rials"):
            _val4["available"] = False
            _val4["data_gap"] = True
            _val4["reason"] = (
                "ارزش بازار از اسنپ‌شاتِ رسمیِ TSETMC خوانده نشد (%s)؛ فروش÷ارزش و "
                "پتانسیل سود محاسبه نمیشوند — پیش از «گزارش ماهانه»، تابلوخوانیِ این "
                "نماد باید تازه شود." % (mcap_info.get("error") or "بدون کد خطا"))
        insights, details = build_insights(res)
        ind = res["indicators"]
        g, v = ind["1"]["monetary"], ind["1"]["volume"]
        e, gm, val, sec = ind["2"], ind["3"], ind["4"], ind["5"]
        annual = val.get("annual") or {}

        # ارجاع نماد اصلی (قرارداد اختیار معامله روی سهمِ اصلی)
        ref_symbol = norm_symbol if norm_symbol != symbol else None
        if inst and str(inst["l_val18"] or "").startswith("ض") and inst["l_val30"]:
            # «ضهرم5026» → l_val30 = «اختيارخ اهرم-24000-1405/05/28» → اهرم.
            # نامِ متغیرِ این شاخه روزی `probe` بود و به `m30` عوض شد، ولی
            # سه خطِ پایین همان `probe` را خواندند — یعنی هر قراردادِ اختیار
            # (۱٬۰۴۹ نماد) با NameError پانصد می‌داد، از اولین ریلیز تا اینجا.
            m30 = re.search(r"\S+\s+([^\s-]+)[\s-]?", str(inst["l_val30"]))
            if m30 and m30.group(1):
                underlying = m30.group(1)
                _p_probe, _a_probe = fts_engine.sym_in("l_val18", underlying)
                if conn.execute(f"SELECT 1 FROM instruments WHERE {_p_probe}", _a_probe).fetchone():
                    ref_symbol, ref_reason = underlying, "قرارداد اختیار معامله — تحلیل به نماد اصلی آن"
                    option_contract = True

        # قرارداد اختیار صورت مالیِ خودش را ندارد (fs_count=0)، و با این حال
        # موتور برایش «رد شده در بررسی بنیادی» می‌داد — حکمِ سرخ رویِ دادهٔ صفر.
        # مثلِ صندوق (رأی ۱۵) برایش داوری صادر نمی‌شود؛ کاربر به نماد اصلی
        # ارجاع داده می‌شود. عددِ امتیازِ اسکرینر دست‌نخورده می‌ماند چون این
        # شاخه فقط در مسیرِ جزئیات است. نشانه‌اش option_contract است، نه
        # ref_reason — آن یکی برای پسوندِ عددیِ نمادهای عادی هم پر می‌شود.
        if option_contract:
            res["applicable"] = False
            res["verdict"] = "FTS ندارد"

        # حذف خودکار از غربالگری (تعلیق / بیمه / قیمت‌گذاری دستوری)
        if res["excluded"]:
            insights.insert(0, {"step": "۰", "title": "حذف خودکار از غربالگری FTS",
                                "type": "danger",
                                "text": "⚠️ " + " · ".join(res["exclusion_reasons"])})


        metrics = {"mcap": mcap or 0.0,
                   "mcap_source": mcap_info.get("source"),
                   "mcap_asof": mcap_info.get("asof"),
                   "mcap_stale": bool(mcap_info.get("stale")),
                   "mcap_error": mcap_info.get("error"),
                   "mcap_hmt": mcap_info.get("hmt"),

                   "annual_sales_bt": annual.get("annual_sales_bt"),
                   "revenue": annual.get("annual_sales_mrl"),
                   "sales_to_mcap": val.get("sales_to_mcap"),
                   "ps": (round(1.0 / val["sales_to_mcap"], 3)
                          if val.get("sales_to_mcap") else None),
                   "gross_margin": gm.get("margin_pct"),
                   "net_margin": gm.get("net_margin_pct"),
                   "growth_pct": g.get("monetary_pct"),
                   "monetary_growth_pct": g.get("monetary_pct"),
                   "volume_growth_pct": v.get("volume_pct"),
                   "real_growth_pct": v.get("real_pct"),
                   "volume_basis": v.get("basis"),
                   "quantity_verified": bool(v.get("quantity_verified")),
                   "eps_series": e.get("eps_series"),
                   "eps_slots": e.get("period_slots") or [],
                   "eps_partial": bool(e.get("partial")),
                   "eps_available": int(e.get("available_periods") or 0),
                   "eps_required": int(e.get("years_required") or v10_thresholds()["eps_years"]),
                   "eps_projected_year": (e.get("interim") or {}).get("eps_projected_year"),
                   "profit_potential_pct": val.get("potential_pct"),
                   "potential_pct": val.get("potential_pct"),
                   "months_used": annual.get("months_used"),
                   "scale_factor": annual.get("scale_factor")}

        secondary = {
            "طبقهٔ شرکت": "%s — %s" % (res["profile"]["label"], res["profile"]["revenue_basis"]),
            "مبنای حجم (لایهٔ ۱ب)": "%s · اطمینان %s · تناژ گزارش‌شده: %s"
            % (v.get("basis") or "—", v.get("confidence") or "—",
               "بله" if v.get("quantity_verified")
               else "خیر — ستون فیزیکی در DB نیست، تعدیل تورمی مصرف شد"),
            "سالانه‌سازی (لایهٔ ۴)": "م = %s ماه × ۱۲÷م = ×%s — %s"
            % (annual.get("months_used"), _n(annual.get("scale_factor"), 2),
               annual.get("basis") or "—")}
        roe_pct = None
        # ارزش بازار — فقط خواندن از ستونِ رسمی؛ متنِ «سهم × ریال» عمداً حذف شد
        # چون کاربر باید بداند عدد از کجا آمده، نه اینکه اینجا ضرب میشود.
        _src_fa = {"tse_raw": "فیلدِ خامِ تابلوی TSETMC",
                   "tse_board_calc": "اسنپ‌شاتِ تابلوی TSETMC (pcl×ztd در زمانِ سینک)",
                   "tse_board_calc_backfill": "اسنپ‌شاتِ ذخیره‌شدهٔ TSETMC (مهاجرت v10)",
                   "unknown": "اسنپ‌شاتِ تابلوی TSETMC"}
        if mcap_info.get("rials"):
            secondary["ارزش بازار"] = "%s همت — منبع: %s%s" % (
                _n(mcap_info["hmt"], 2),
                _src_fa.get(str(mcap_info.get("source")), str(mcap_info.get("source"))),
                " · تاریخچهٔ اسنپ‌شات (نماد امروز بی‌عدد)" if mcap_info.get("stale") else "")
            if mcap_info.get("asof"):
                secondary["تاریخ ارزش بازار"] = str(mcap_info["asof"])
        else:
            secondary["ارزش بازار"] = "موجود نیست — %s" % (
                {"symbol_not_on_board": "نماد در اسنپ‌شاتِ تابلو نیست (فقط-کدال)",
                 "market_cap_column_missing": "ستون ارزش بازار هنوز در market.db ساخته نشده",
                 "market_cap_missing_value": "تابلو برای این نماد ارزش بازارِ معتبر ندارد",
                 "market_cap_invalid_value": "مقدار ذخیره‌شده نامعتبر است"}.get(
                    str(mcap_info.get("error")), str(mcap_info.get("error")) or "دلیل نامشخص"))
        secondary["سهم بازار"] = "%s٪ از کل بازار (تکمیلی)" % _n(
            sec.get("market_share_pct") or 0.0, 3)
        ref_row = res.get("ref")
        if ref_row:
            # تطبیق چند-نویشتاری: norm_symbol ممکن است فارسی باشد و DB عربی نگه دارد
            _fp, _fa = fts_engine.sym_in("symbol", norm_symbol)
            te = conn.execute("SELECT total_equity FROM financial_statements WHERE %s "
                              "AND period_end=? ORDER BY tracing_no DESC LIMIT 1" % _fp,
                              (*_fa, ref_row["period_end"])).fetchone()
            if te and _num(te[0]) > 0 and _num(ref_row.get("net_profit")):
                roe_pct = round(_num(ref_row["net_profit"]) / _num(te[0]) * 100.0, 1)
                secondary["ROE"] = "%s٪ (تکمیلی)" % _n(roe_pct, 1)
        metrics["roe"] = roe_pct

        history = [{"period_end": CP.canonicalize(r["period_end"]) or "", "fiscal_year": r["fiscal_year"],
                    "revenue": r["revenue"], "gross_profit": r["gross_profit"],
                    "net_profit": r["net_profit"], "eps": r["basic_eps"],
                    "audited": r["audited"], "consolidated": r["consolidated"]}
                   for r in fts_engine.annual_statements(conn, norm_symbol, limit=6)]

        return {"status": "success",
                "symbol": symbol, "sector": sector, "pricing_mode": res["pricing_mode"],
                "score": (res["score"] if res.get("applicable", True) else None),
                "verdict": res["verdict"],
                "applicable": res.get("applicable", True),
                "excluded": res["excluded"], "exclusion_reasons": res["exclusion_reasons"],
                "passes": res["passes"], "methodology": res["methodology"],
                "profile": res["profile"], "indicators": ind,
                "metrics": metrics, "insights": insights, "details": details,
                "data_gaps": v10_data_gaps(res),
                "secondary": secondary, "history": history, "thresholds": cfg,
                "ref_symbol": ref_symbol, "ref_reason": ref_reason,
                "fs_count": len(history)}
    finally:
        conn.close()


@router.get("/api/fundamental/{symbol}/quarters")
def get_fundamental_quarters(symbol: str, limit: int = 16):
    """سری میاندوره‌ای خام برای نمودار روند فصلی فرانت React (فاز 3) — فقط خواندنی.

    ردیف‌ها تجمعی سال مالی‌اند (3/6/9/12 ماهه)؛ تفکیک فصلی در فرانت انجام میشود.
    هیچ منطق موجودی را تغییر نمیدهد.

    #102 (رأیِ جزوه): «سود ناخالص» هم فرستاده میشود — روند فصلیِ درآمد باید با
    سود ناخالص سنجیده شود نه سود خالص. ستون در کدال NULL است وقتی صورتِ مالی
    سطر «بهای تمام‌شده» ندارد (صندوق/سرمایه‌گذاری)؛ NULL هیچ‌وقت صفر نمی‌شود و
    هیچ‌وقت با سود خالص جایگزین نمی‌گردد — نبودش در پاسخ حفظ میشود.
    """
    conn = get_db()
    try:
        # تطبیق چند-نویشتاری (ك/ي عربی ↔ فارسی): ورودیِ کاربر ممکن است فارسی
        # باشد و رکوردهای کدالِ همان نماد با نوشتار عربی ذخیره شده باشند.
        _fp, _fa = fts_engine.sym_in("symbol", symbol)
        _raw = conn.execute(
            "SELECT period_end, period_months, revenue, gross_profit,"
            " operating_profit, net_profit, basic_eps, publish_date"
            " FROM financial_statements"
            " WHERE %s AND %s ORDER BY period_end DESC, publish_date DESC LIMIT ?"
            % (_fp, CP.DATED_SQL),
            (*_fa, max(1, min(limit, 40)))).fetchall()
        # حذف تکراریِ (period_end, period_months): نمادِ دو-املا می‌تواند یک دوره را
        # در دو نوشتار داشته باشد؛ تازه‌ترین ردیف می‌ماند.
        _seen, rows = set(), []
        for r in _raw:
            k = (r[0], r[1])
            if k in _seen:
                continue
            _seen.add(k)
            rows.append(r)
        return {"status": "success", "symbol": symbol, "count": len(rows),
                "quarters": [dict(r) for r in rows]}
    finally:
        conn.close()


def v10_batch(symbols, cfg=None, limit: int = 50) -> list:
    """چکیدهٔ پنج‌لایه برای چند نماد (واچ‌لیست) — بدون payload کاملِ کارت.

    اتصال و کانفیگ یک‌بار خوانده میشوند؛ خطای یک نماد نباید ماتریسِ بقیه را از
    کار بیندازد (try داخل حلقه). مصرف‌کننده: GET /api/watchlist/fts-v10.
    """
    out = []
    syms = [s for s in (symbols or []) if s][:max(0, min(int(limit), 50))]
    if not syms:
        return out
    conn = get_db()
    try:
        cfg = cfg if cfg is not None else load_fts_config()
        if not _has_mcap_col(conn, "market_watch"):
            ensure_market_cap_schema(conn)
        total_mcap, _mcap_src = board_total_market_cap(conn)
        # تک‌کوئریِ کل دسته به‌جای N کوئری: ارزش بازار از ستونِ تابلو خوانده
        # میشود و در نبودش، آخرین مقدارِ معتبرِ daily_prices (همان fallback که
        # مسیرِ تک‌نماد دارد) — وگرنه واچ‌لیست ۵۰ نمادی ۱۰۰ کوئری می‌زد.
        ctx = {}
        try:
            # همان عبارتِ موتور (`mcap_bulk_expr`) — ستونِ رسمی، در نبودش
            # daily_prices، و بانِ مرده ⇒ None. برچسبِ منبع هم با همان دروازه
            # بی‌اعتبار می‌شود تا «منبع» چیزی را توضیح ندهد که عددش را نداده‌ایم.
            _mc = fts_engine.mcap_bulk_expr(conn)
            _dead = (fts_engine.mcap_dead_band_sql("m")
                     if (fts_engine.has_column(conn, "market_watch", "allowed_min")
                         and fts_engine.has_column(conn, "market_watch", "allowed_max"))
                     else "0")
            for r in conn.execute("""
                SELECT i.l_val18, """ + _mc + """,
                       CASE WHEN """ + _dead + """ THEN NULL ELSE
                            COALESCE(m.market_cap_src,
                                     (SELECT d.market_cap_src FROM daily_prices d
                                       WHERE d.ins_code = i.ins_code AND d.market_cap > 0
                                       ORDER BY d.d_even DESC LIMIT 1))
                       END,
                       COALESCE(i.sector_name, 'سایر')
                FROM instruments i
                LEFT JOIN market_watch m ON m.ins_code = i.ins_code"""):
                k = fts_engine.norm_fa(r[0])
                if k and k not in ctx:
                    ctx[k] = (r[1], r[3], r[2])
        except sqlite3.Error:
            ctx = {}
        # دو نقشهٔ کل‌بازاری یک‌بار ساخته میشوند (الگوی fts_engine در scan_all) —
        # وگرنه هر نمادِ واچ‌لیست یک کوئریِ ماده ۱۴۱ و یک کوئریِ نقدشوندگی می‌زد.
        need_m141 = bool(cfg.get("filter_m141"))
        need_liq = _f(cfg.get("min_trade_val")) > 0
        m141_map = fts_engine.m141_map(conn) if need_m141 else {}
        liq_map = fts_engine.avg_trade_value_hmt(conn) if need_liq else {}
        for s in syms:
            try:
                hit = ctx.get(fts_engine.norm_fa(s)) or (None, "سایر", None)
                mcap_raw, sector, mcap_src = hit
                mcap, mcap_err = _rials_or_none(mcap_raw)
                if mcap is None:
                    mi = get_tsetmc_market_cap_info(s, db=conn)
                    mcap, mcap_src, mcap_err = mi["rials"], mi["source"], mi["error"]
                res = evaluate_v10(conn, s, mcap or 0.0, total_mcap, sector, cfg=cfg,
                                   m141_map=m141_map, liq_map=liq_map)
                res["market_cap_src"] = mcap_src
                res["market_cap_error"] = mcap_err

                ind = res["indicators"]
                g, v = ind["1"]["monetary"], ind["1"]["volume"]
                val = ind["4"]
                out.append({"symbol": s, "score": res["score"], "verdict": res["verdict"],
                            "passes": res["passes"], "sector": sector,
                            "pricing_mode": res["pricing_mode"],
                            "monetary_pct": g.get("monetary_pct"),
                            "volume_basis": v.get("basis"),
                            "volume_pct": v.get("volume_pct"),
                            "real_pct": v.get("real_pct"),
                            "quantity_verified": bool(v.get("quantity_verified")),
                            "potential_pct": val.get("potential_pct"),
                            "months_used": (val.get("annual") or {}).get("months_used")})
            except Exception as exc:               # یک نماد خراب ≠ ماتریس خراب
                out.append({"symbol": s, "score": 0, "verdict": "INSUFFICIENT",
                            "error": str(exc)[:120]})
    finally:
        conn.close()
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  پوششِ دادهٔ بازار برای موتور v10 (GET /api/sync/codal/fts-coverage)
# ═══════════════════════════════════════════════════════════════════════════
_VOLUME_TOKENS = ("volume", "quantity", "qty", "ton", "tonnage", "meghdar",
                  "تعداد", "حجم", "تناژ", "تن", "وزن")


def _volume_columns(conn) -> list:
    """ستون‌های فیزیکیِ واقعیِ monthly_sales (اگر روزی به DB اضافه شوند)."""
    try:
        cols = [str(r[1]) for r in conn.execute("PRAGMA table_info(monthly_sales)")]
    except sqlite3.Error:
        return []
    flat = [t.replace("_", "") for t in _VOLUME_TOKENS]
    return [c for c in cols if any(t in c.lower().replace("_", "") for t in flat)]


def _has_run3(years) -> bool:
    """آیا سه سالِ مالیِ متوالی در مجموعه هست؟ (ملاکِ «سابقهٔ ۳ ساله»)"""
    ys = sorted({int(y) for y in years})
    return any(ys[i] + 1 == ys[i + 1] and ys[i] + 2 == ys[i + 2]
               for i in range(len(ys) - 2))


def v10_coverage(conn) -> dict:
    """چقدر از بازار امروز قابلِ داوری است؟ (پاسخِ «چرا ۱الف خالی است»)

    همه‌چیز با یک‌مرورِ SQL حساب میشود — ارزیابیِ تک‌تکِ نمادها لازم نیست، وگرنه
    خودِ پوشش‌سنجی دقیقه‌ها طول می‌کشد. هر شمارش دقیقاً همان گیتی است که موتور در
    ind1a/ind1b/ind2/ind3 می‌گذارد؛ پس عددِ «۲٪» یعنی موتور واقعاً برای ۹۸٪ نمادها
    «قابل محاسبه نبود» برمی‌گرداند، نه «رد».
    """
    n_fs = int(_f(conn.execute("SELECT COUNT(DISTINCT symbol) FROM financial_statements")
                  .fetchone()[0]))
    n_ms = int(_f(conn.execute("SELECT COUNT(DISTINCT symbol) FROM monthly_sales")
                  .fetchone()[0]))
    pct = lambda part, whole: (round(part * 100.0 / whole, 1) if whole else None)

    # ── لایهٔ ۱الف: آیا مخرج YoY (ردیفِ سال−۱ِ همان ماه) وجود دارد؟ ─────────
    row = conn.execute(
        "WITH latest AS (SELECT symbol, MAX(year * 100 + month) AS k FROM monthly_sales "
        "                 WHERE ytd_revenue > 0 GROUP BY symbol) "
        "SELECT COUNT(DISTINCT l.symbol), "
        "       COUNT(DISTINCT CASE WHEN COALESCE(c.ytd_revenue_prev, 0) > 0 "
        "                           THEN l.symbol END), "
        "       COUNT(DISTINCT CASE WHEN COALESCE(c.ytd_revenue_prev, 0) <= 0 "
        "                            AND p.symbol IS NOT NULL THEN l.symbol END) "
        "FROM latest l "
        "JOIN monthly_sales c ON c.symbol = l.symbol AND c.year * 100 + c.month = l.k "
        "                     AND c.ytd_revenue > 0 "
        "LEFT JOIN monthly_sales p ON p.symbol = l.symbol "
        "     AND p.year = (l.k / 100) - 1 AND p.month = (l.k % 100) "
        "     AND p.ytd_revenue > 0").fetchone()
    n_ms_latest = int(_f(row[0]))
    # «قابل داوری» = دقیقاً قاعدهٔ `fts_engine.ytd_denominator`: ستونِ رسمی یا
    # ردیفِ (سال−۱، همان ماه). تفکیکِ دو منشأ هم از همان یک کوئری می‌آید؛ مجموع
    # دو ستون آخر، پس هیچ‌وقت عددِ منفی (طرحِ پیشین: ۶۲۴−۷۳۲) نمایش داده نمی‌شود.
    n_prev_col, n_prev_row = int(_f(row[1])), int(_f(row[2]))
    n_1a = n_prev_col + n_prev_row
    latest_ym = conn.execute("SELECT MAX(year * 100 + month) FROM monthly_sales "
                             "WHERE ytd_revenue > 0").fetchone()[0]

    # ── لایهٔ ۲: یک‌مرورِ صورت‌های مالی با همان نردبانِ موتور ────────────────
    per_sym = {}
    for sym, pe, pm, title, eps in conn.execute(
            "SELECT symbol, period_end, period_months, title, basic_eps "
            "FROM financial_statements "
            "WHERE basic_eps IS NOT NULL AND period_months > 0").fetchall():
        s = str(sym or "").strip()
        try:
            y, mm, ev = int(CP.fiscal_year(pe) or 0), int(_f(pm)), float(eps)
        except (TypeError, ValueError):
            continue
        if not s or y <= 0 or mm <= 0:
            continue
        aud, cons = _is_audited_title(title or ""), _is_consolidated_title(title or "")
        d = per_sym.setdefault(s, {})
        if mm >= 12:
            d.setdefault("all", set()).add(y)
            if aud and not cons:
                d.setdefault("clean", set()).add(y)
        else:
            best = d.setdefault("int", {})
            if y not in best or mm > best[y][0]:
                best[y] = (mm, ev)
    strict_eps = {s for s, d in per_sym.items() if _has_run3(d.get("clean") or ())}
    blended_eps = {s for s, d in per_sym.items()
                   if _has_run3(set(d.get("all") or ()) | set(d.get("int") or ()))}
    gm_avail = {str(s or "").strip() for s, in conn.execute(
        "SELECT DISTINCT symbol FROM financial_statements "
        "WHERE period_months >= 12 AND revenue > 0 AND gross_profit IS NOT NULL").fetchall()}
    vol_cols = _volume_columns(conn)
    layers = {
        "1a_monetary_growth": {
            "evaluable": n_1a, "of": n_ms_latest, "pct": pct(n_1a, n_ms_latest),
            "denominator_from_official_column": n_prev_col,
            "denominator_from_same_month_last_year": n_prev_row,
            "note": "نمادهایی که مخرجِ YoY دارند: ستونِ «مقایسهٔ دورهٔ مشابه» "
                    "یا ردیفِ (سال قبل، همان ماه) با فروشِ تجمیعیِ > ۰"},
        "1b_physical_volume": {
            "evaluable": 0 if not vol_cols else n_ms_latest, "of": n_ms_latest,
            "pct": 0.0 if not vol_cols else pct(n_ms_latest, n_ms_latest),
            "volume_columns_present": vol_cols,
            "note": ("هیچ ستونِ حجم/تناژ فیزیکی در monthly_sales نیست؛ ۱ب فقط با "
                     "تعدیلِ ریالی (اثر نرخ) راستی‌آزمایی میشود") if not vol_cols
                    else "ستون فیزیکی یافت شد — شواهدِ سطح ۱ فعال است"},
        "2_eps_strict": {"evaluable": len(strict_eps), "of": n_fs,
                         "pct": pct(len(strict_eps), n_fs),
                         "note": "۳ صورتِ ۱۲ماههٔ حسابرسی‌شدهٔ غیرتلفیقی (قاعدهٔ سختِ v8)"},
        "2_eps_blended": {"evaluable": len(blended_eps), "of": n_fs,
                          "pct": pct(len(blended_eps), n_fs),
                          "note": "با نردبانِ پشتیبانِ v10 (سال‌پایان + میاندورهٔ سال‌سازی‌شده)"},
        "3_gross_margin": {"evaluable": len(gm_avail), "of": n_fs,
                           "pct": pct(len(gm_avail), n_fs),
                           "note": "سود ناخالصِ ۱۲ماههٔ ثبت‌شده (بانک/صندوق not_applicable)"},
    }
    lm = str(latest_ym or "")
    return {"status": "success", "engine": "FTS-v10",
            "universe": {"fs_symbols": n_fs, "monthly_symbols": n_ms,
                         "monthly_with_latest_year": n_ms_latest,
                         "latest_month": ("%s/%s" % (lm[:4], lm[4:]) if len(lm) >= 5 else None)},
            "layers": layers,
            "blocking_gap": ("1a_monetary_growth"
                             if (pct(n_1a, n_ms_latest) or 0) < 80 else ""),
            "remediation": _MS_GAP_HINT,
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds")}


@router.get("/api/sync/codal/fts-coverage")
def get_fts_coverage():
    """پوششِ دادهٔ پنج‌لایه روی کل بازار — تشخیص «شاخص قابل محاسبه نبود» از «رد»."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        return v10_coverage(conn)
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


def _fts_market_ctx(conn, symbol: str) -> tuple:
    """(ارزش_بازار_ریال|None, صنعت, کل_ارزش_بازار_ریال) برای یک نماد.

    هیچ ضربِ دستی‌ای این‌جا انجام نمیشود: عدد از ستونِ `market_cap` می‌آید که
    موتور همگام‌سازی از ردیفِ خامِ تابلو نوشته است. نبودِ عددِ معتبر None است
    (نه ۰) تا شاخص ۴ «قابل محاسبه نبود» بگوید، نه «مردود».
    """
    if not _has_mcap_col(conn, "market_watch"):
        ensure_market_cap_schema(conn)
    info = get_tsetmc_market_cap_info(symbol, db=conn)
    pred, params = fts_engine.sym_in("i.l_val18", symbol)
    pred30 = pred.replace("i.l_val18", "i.l_val30")
    row = conn.execute(
        "SELECT COALESCE(i.sector_name, 'سایر') "
        "FROM instruments i "
        "WHERE %s OR %s ORDER BY i.updated_at DESC LIMIT 1" % (pred, pred30),
        (*params, *params)).fetchone()
    sector = (row[0] if row else "") or "سایر"
    total, _src = board_total_market_cap(conn)
    return info["rials"], sector, total, info


