"""Fundamental (CODAL) per-symbol endpoint — موتور ۵ لایهٔ بنیادی FTS v10.

این فایل در v9.8.1 از app.py جدا شد و تا نسخهٔ قبل تنها خروجی
`fts_engine.scan_symbol` را بازآرایی میکرد. نسخهٔ ۱۰، روش‌شناسی پنج‌لایهٔ FTS
را صریح و کامل پیاده میکند:

  لایهٔ ۱  درآمد/فروش — دو چکِ الزامی:
           ۱الف رشد ریالی: فروش تجمیعی ÷ همان دورهٔ سال قبل ≥ ۶۰٪
           ۱ب رشد فیزیکی (تناژ/تعداد): ردِ سودی که صرفاً از تورم و افزایش
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
  * `static/index.html` و `static/app.js` مصرف‌کنندهٔ فرجمد این payload هستند؛
    کلیدهای `insights[].{step,title,text}`، `metrics.{mcap,revenue,
    gross_margin,roe,ps}`، `fs_count` و `history[].tracing_no` حفظ شده‌اند.
"""
from ._core import _num, get_db
from .market import load_fts_config
from bors_config import DB_PATH
from fastapi import APIRouter
from fastapi import HTTPException
import fts_engine
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
    "volume_growth_min": 0.0,       # ۱ب — رشد فیزیکی باید غیرمنفی باشد (٪)
    "volume_breadth_min": 0.60,     # ۱ب — حداقل share ماههایی که واقعاً بهتر شده‌اند
    "eps_years": 3,                 # ۲ — طول سابقهٔ سودسازی (سالِ متوالی سودآور)
    "margin_min": 20.0,             # ۳ — کف حاشیهٔ ناخالص
    "margin_ideal": 30.0,           # ۳ — حاشیهٔ ایده‌آل
    "sales_to_mcap_min": 1.0,       # ۴الف — فروش سالانه ÷ ارزش بازار (۱۰۰٪ = ۱×، استاندارد جزوه)
    "potential_min": 40.0,          # ۴ب — سود ناخالص پتانسیل ÷ ارزش بازار (٪)
}

MRL_TO_RIAL = 1e6      # جداول کدال «میلیون ریال» هستند
BT_FACTOR = 1e-4       # میلیون ریال → میلیارد تومان (حذف ۴ رقم راست)

# مبنای تورم/افزایش قیمت — همان عددی که fts_engine به‌عنوان «تورم سالانه» در
# شاخص ۱ به کار می‌برد (fts_thresholds.json → inflation_min).
_INFLATION_FALLBACK = 58.0


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
    out["inflation_benchmark"] = _f(cfg.get("inflation_min")) or _INFLATION_FALLBACK
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

# کشِ «این جدول ستونِ ارزش بازار را دارد یا نه» — کلید: (id(conn), table)
_MCAP_COLS: dict = {}


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
    key = (id(conn), table)
    hit = _MCAP_COLS.get(key)
    if hit is None:
        try:
            hit = any((r[1] or "").lower() == "market_cap"
                      for r in conn.execute("PRAGMA table_info(%s)" % table))
        except sqlite3.Error:
            hit = False
        _MCAP_COLS[key] = hit
    return hit


def ensure_market_cap_schema(conn) -> bool:
    """اگر market.db هنوز ستونِ ارزش بازار ندارد، می‌سازد و پر می‌کند.

    خودِ مهاجرت در test_tsetmc است (تک‌مسیرِ نوشتن)؛ این پوسته فقط برای DB‌ای
    است که پیش از ارتقا ساخته شده و هنوز سینک نشده. import تنبل — نبودش
    (نسخهٔ ناقصِ استقرار) نباید کارتِ بنیادی را بیندازد.
    """
    try:
        import test_tsetmc
        test_tsetmc.ensure_market_cap_schema(conn)
        _MCAP_COLS.pop((id(conn), "market_watch"), None)
        _MCAP_COLS.pop((id(conn), "daily_prices"), None)
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
            try:
                row = conn.execute(
                    "SELECT m.market_cap, m.market_cap_src, m.d_even"
                    " FROM market_watch m JOIN instruments i ON i.ins_code = m.ins_code"
                    " WHERE " + where + " ORDER BY i.updated_at DESC LIMIT 1", args).fetchone()
            except sqlite3.Error:
                row = None
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
    """(کل ارزش بازارِ ریال, منبع) — مجموعِ همان ستونِ رسمی، نه ضربِ دستی."""
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
#  تفکیک طبقهٔ شرکت (پیش‌شرط لایهٔ ۱): تولیدی در برابر مالی/خدماتی
# ═══════════════════════════════════════════════════════════════════════════
# «فروش» برای بانک معنا ندارد؛ جزوه برای شرکت‌های مالی «درآمد تسهیلات اعطایی +
# سپرده‌گذاری + سرمایه‌گذاری + اوراق + کارمزد» را می‌نویسد و برای تولیدی
# «فروش داخلی + صادراتی». این تابع همان تفکیک را از sector_name/نام شرکت می‌سازد
# تا هر دو چکِ لایهٔ ۱ روی مبنای درستِ همان طبقه اجرا شوند.
_FIN_TOKENS = tuple(fts_engine.norm_fa(x) for x in
                    ("اعتباري", "اعتباری", "بيمه", "بیمه",
                     "ليزينگ", "لیزینگ", "کارگزاري", "کارگزاری", "اوراق"))
# هلدینگ/سرمایه‌گذاری/واسطه‌گری مالی/بانکی: «فروش کالا» و رشد فیزیکی/تناژ
# معنا ندارد؛ درآمد از پرتفوی/تسهیلات/سپرده می‌آید → رشد فیزیکی کاملاً مخفی.
_HOLD_TOKENS = tuple(fts_engine.norm_fa(x) for x in
                     ("بانک", "سرمایه گذاری", "سرمایه‌گذاری", "هلدینگ",
                      "واسطه گری", "واسطه‌گری", "نهادهای مالی واسط"))
_SVC_TOKENS = tuple(fts_engine.norm_fa(x) for x in
                    ("خدمات", "حمل", "ترابری", "فناوري", "فناوری", "مخابرات",
                     "بازرگاني", "بازرگانی", "پخش", "رستوران", "گردش"))
_PROFILE_LABEL = {"production": "تولیدی / صادراتی", "financial": "مالی و بانکی",
                  "service": "خدماتی", "fund": "صندوق",
                  "holding": "هلدینگ / سرمایه‌گذاری"}


def company_profile(sector: str = "", company_name: str = "") -> dict:
    """طبقهٔ شرکت + مبنای درآمد + اینکه چکِ فیزیکی (تناژ) برایش معنا دارد یا نه."""
    both = fts_engine.norm_fa(sector) + " " + fts_engine.norm_fa(company_name)
    if "صندوق" in both:
        kind = "fund"
        basis = "صندوق — درآمد پرتفوی و تغییرات خالص دارایی‌ها"
        applicable = False
    elif any(t in both for t in _HOLD_TOKENS):
        kind = "holding"
        basis = ("هلدینگ/سرمایه‌گذاری/بانکی — درآمد عملیاتی از پرتفوی، سود "
                 "تسهیلات/سپرده و سرمایه‌گذاری‌ها (بدون «فروش کالا» و تناژ فیزیکی)")
        applicable = False
    elif any(t in both for t in _FIN_TOKENS):
        kind = "financial"
        basis = ("مالی/بانکی — جمع درآمد تسهیلات اعطایی + سپرده‌گذاری + "
                 "سرمایه‌گذاری‌ها + اوراق بدهی + کارمزد (نه «فروش کالا»)")
        applicable = False
    elif any(t in both for t in _SVC_TOKENS):
        kind = "service"
        basis = "خدماتی — کارمزد و درآمد عملیاتی (بدون تناژ فیزیکی)"
        applicable = False
    else:
        kind = "production"
        basis = "تولیدی/عمرانی — جمع فروش داخلی + صادراتی (ردیف «جمع» جدول فروش)"
        applicable = True
    return {"kind": kind, "label": _PROFILE_LABEL[kind], "revenue_basis": basis,
            "volume_applicable": applicable,
            "volume_note": ("تناژ/تعداد محصول در گزارش فعالیت ماهانه معنادار است؛ "
                            "رشد ریالی بدون رشد تناژ = افزایش قیمت."
                            if applicable else
                            "این شرکت کالای وزن‌شدنی تولید نمی‌کند؛ چک فیزیکی روی "
                            "مبنای متناسبِ همان طبقه (درآمد واقعی پس از تورم) سنجیده "
                            "میشود نه تن محصول."),
            "pricing_note": ("درآمد به دلار/بورس کالا گره خورده (صادراتی)."
                             if applicable else
                             "درآمد ریالیِ نرخ‌گذاری‌شده — ریسک سرکوب نرخ وجود دارد.")}


# ═══════════════════════════════════════════════════════════════════════════
#  سری گزارش فعالیت ماهانه — مبنای مشترک لایه‌های ۱ و ۴
# ═══════════════════════════════════════════════════════════════════════════
MS_COLS = "year, month, monthly_revenue, ytd_revenue, ytd_revenue_prev, period_end"


def _dedupe_ym(rows, ytd_idx: int = 3) -> list:
    """یکی‌کردن ردیف‌های تکراریِ (سال,ماه) پس از ادغام نوشتارهای ي/ک عربی-فارسی.

    با symbol_aliases گزارشِ یک شرکت از دو نوشتار (داریک/داريك) با هم می‌آید؛
    بدون این ادغام مخرج رشد YoY می‌توانست صفرِ نوشتارِ بی‌داده باشد. قاعده:
    برای هر (سال,ماه) رکوردی که `ytd_revenue` بزرگ‌تر دارد نگه داشته میشود —
    همان contract ای که fts_engine اجرا میکند، تا دو مسیر یک عدد بدهند.
    """
    best, order = {}, []
    for r in rows:
        try:
            k = (int(r[0] or 0), int(r[1] or 0))
        except (TypeError, ValueError):
            k = (str(r[0]), str(r[1]))
        if k not in best:
            order.append(k)
            best[k] = list(r)
            continue
        if _f(r[ytd_idx]) > _f(best[k][ytd_idx]):
            best[k] = list(r)
    return [best[k] for k in order]


def monthly_series(conn, symbol: str) -> list:
    """گزارش‌های فعالیت ماهانه، تازه‌ترین در ابتدا →
    [[year, month, monthly_revenue, ytd_revenue, ytd_revenue_prev, period_end], …]"""
    pred, params = fts_engine.sym_in("symbol", symbol)
    rows = conn.execute(
        "SELECT %s FROM monthly_sales WHERE %s AND ytd_revenue IS NOT NULL "
        "AND ytd_revenue>0 ORDER BY year DESC, month DESC LIMIT 60" % (MS_COLS, pred),
        params).fetchall()
    return _dedupe_ym([list(r) for r in rows])


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
_MS_GAP_HINT = ("شکافِ گزارش ماهانه با همگام‌سازی کدال بسته میشود "
                "(POST /api/sync/codal?mode=backfill)؛ پوششِ فعلیِ کل بازار را "
                "از GET /api/sync/codal/fts-coverage ببینید.")


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
    cur = series[0]
    year, month, ytd_now = int(_f(cur[0])), int(_f(cur[1])), _f(cur[3])
    if ytd_now <= 0 or month <= 0:
        return _nodata("تجمیعیِ آخرین گزارش ماهانه صفر یا نامعتبر است.",
                       months=month, year=year)
    ytd_prev, basis = _f(cur[4]), "ستون رسمی «مقایسه با دورهٔ مشابه سال قبل» در همان گزارش"
    if ytd_prev <= 0:
        prev = next((r for r in series[1:] if int(_f(r[0])) == year - 1
                     and int(_f(r[1])) == month), None)
        if prev is None or _f(prev[3]) <= 0:
            return _nodata("مخرج YoY (تجمیعیِ همان دورهٔ سال قبل) در کدال نیست.",
                           months=month, year=year, ytd_now_bt=_bt(ytd_now),
                           ytd_prev_bt=None, period="%02d/%d" % (month, year),
                           denominator_basis="ناموجود — ردیف تجمیعی همان دورهٔ سال قبل نیست")
        ytd_prev = _f(prev[3])
        basis = "تجمیعی %02d/%d از گزارش فعالیت ماهانه (نه ماه قبل)" % (month, year - 1)
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
#  لایهٔ ۱ب — رشد فیزیکی/تناژ (ردِ سودِ صرفاً تورمی)
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
        out["reason"] = "رشد ریالی محاسبه نشد → تأیید فیزیکی ناممکن است."
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
                         "کمیت فروش کاهش یافته یا ثابت مانده؛ رشد ریالی از افزایش نرخ آمده است.")
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
    gates = [real >= th["volume_growth_min"]]
    if breadth is not None:
        gates.append(breadth >= th["volume_breadth_min"])
    out["pass"] = all(gates)
    if out["pass"]:
        out["reason"] = ""
    elif real < th["volume_growth_min"]:
        out["reason"] = ("رشد اسمی (%+.1f٪) از مبنای افزایش نرخ (%.0f٪) کمتر است → "
                         "سودِ صرفاً تورمی." % (monetary_pct, th["inflation_benchmark"]))
    else:
        out["reason"] = ("رشد واقعی کافی است، اما فقط %d از %d ماهِ سپری‌شده بهتر شده → "
                         "رشدِ فراگیرِ حجم تأیید نمیشود." % (improved, compared))
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  لایهٔ ۲ — سابقهٔ ۳ سالهٔ سودسازی (سال‌پایان + راستی‌آزمایی میاندوره‌ای)
# ═══════════════════════════════════════════════════════════════════════════
def _is_audited_title(title) -> bool:
    """عنوان «حسابرسی شده» دارد و «نشده» ندارد (همان قاعدهٔ fts_engine)."""
    t = fts_engine.norm_fa(title)
    return ("حسابرسی شده" in t) and ("نشده" not in t)


def _eps_track_blended(conn, symbol, years: int = 3) -> dict:
    """سابقهٔ سودسازی با «سال‌پایان + میاندوره» — لایهٔ پشتیبانِ v10.

    چرا لازم است: قاعدهٔ سختِ v8 (فقط ۱۲ماههٔ حسابرسی‌شدهٔ غیرتلفیقی) روی این
    دیتابیس برای خیلی از نمادهای بزرگ صفر رکورد می‌دهد — یا چون صورت سالانه
    «حسابرسی‌نشده» بارگذاری شده (فولاد: ۱۴۰۳/۱۴۰۴ هر دو این‌طور) یا چون شرکت
    اصلاً صورت «غیرتلفیقی» سالانه ندارد و فقط تلفیقی منتشر میکند. دستور کارِ
    نسخهٔ ۱۰ صریحاً می‌گوید مسیر EPS با year-end **و** interim سنجیده شود، پس
    اینجا روی یک نردبانِ شفاف تنزل میکنیم و هر تنزل را برچسب میزنیم:
      ۱) سال‌پایانِ حسابرسی‌شدهٔ غیرتلفیقی   (audited_year_end)
      ۲) سال‌پایانِ غیرتلفیقیِ حسابرسی‌نشده  (unaudited_year_end)
      ۳) سال‌پایانِ حسابرسی‌شدهٔ تلفیقی      (consolidated_audited)
      ۴) سال‌پایانِ تلفیقیِ حسابرسی‌نشده     (consolidated_unaudited)
      ۵) بلندترین دورهٔ میاندورهٔ همان سال × ۱۲÷م (annualized_interim)
    سطح ۱-۲ «تمیز» و ۳-۵ «مستندِ جایگزین» شمرده میشوند؛ پرچم‌های
    consolidated_used / relaxed_evidence / low_quality_track در نتیجه می‌مانند
    تا رابط کاربری بتواند صراحتاً بگوید EPS از کجا آمده است.
    سالِ مالیِ در‌جریان (فقط میاندوره) پیشِ‌فرض بیرون از «سابقه» می‌ماند و به‌عنوان
    شواهدِ تداوم در `_interim_eps_check` گزارش میشود؛ فقط وقتی سابقهٔ ۳ساله از
    آب‌تمام‌ها درنمی‌آید، با برچسب annualized_interim به انتهای سابقه افزوده میشود.
    """
    pred, params = fts_engine.sym_in("symbol", symbol)
    rows = conn.execute(
        "SELECT period_end, period_months, title, basic_eps FROM financial_statements "
        "WHERE %s AND basic_eps IS NOT NULL AND period_months > 0 "
        "ORDER BY period_end DESC LIMIT 120" % pred, params).fetchall()
    per_year = {}
    for pe, pm, title, eps in rows:
        try:
            y, pm, eps = int(str(pe or "")[:4]), int(_f(pm)), float(eps)
        except (TypeError, ValueError):
            continue
        if y <= 0 or pm <= 0:
            continue
        cons = _is_consolidated_title(title or "")
        bucket = per_year.setdefault(y, {"annual": [], "interim": []})
        (bucket["annual"] if pm >= 12 else bucket["interim"]).append(
            (pm, _is_audited_title(title or ""), eps, str(pe or "")[:10],
             str(title or "")[:60], cons))
    if not per_year:
        return {}

    # ---- نردبانِ شواهد برای هر سال مالی -------------------------------------
    # rank هر رکورد: (سطح، مرتبهٔ دوره)؛ سطحِ کوچک‌تر = معتبرتر. ترتیبِ مقایسه
    # طوری است که داخلِ یک سطح، بلندترین/تازه‌ترین رکورد انتخاب شود.
    def _rank(r):
        pm, aud, eps, pe, title, cons = r
        if pm >= 12:
            # 0=غیرتلفیقیِ حسابرسی‌شده · 1=غیرتلفیقیِ نشده · 2=تلفیقیِ حسابرسی‌شده · 3=تلفیقیِ نشده
            tier = (2 if cons else 0) + (0 if aud else 1)
            return (tier, -pm, pe)
        return (4, -pm, pe)

    _QUALITY = {0: "audited_year_end", 1: "unaudited_year_end",
                2: "consolidated_audited", 3: "consolidated_unaudited"}

    def _pick(y):
        """بهترین رکورد یک سال مالی → (eps, period_end, quality, months, cons)."""
        b = per_year[y]
        pool = sorted(list(b["annual"]) + list(b["interim"]), key=_rank)
        best = pool[0]
        pm, aud, eps, pe, title, cons = best
        if pm >= 12:
            return eps, pe, _QUALITY[_rank(best)[0]], pm, cons
        return (round(eps * 12.0 / pm, 2), pe,
                "annualized_interim_short" if pm < 6 else "annualized_interim",
                pm, cons)

    def _has_annual(y):
        return bool(per_year[y]["annual"])

    # سال‌هایی که «سالی کامل» گزارش دارند (۱۲ماهه؛ تلفیقی هم مجاز، سطح ۳/۴).
    # سالِ در‌جریان = تازه‌ترین سالی که فقط میاندوره دارد.
    years_sorted = sorted(per_year, reverse=True)
    complete = [y for y in years_sorted if _has_annual(y)]
    newest = years_sorted[0]
    in_progress = newest if not _has_annual(newest) else None
    need = max(int(years or 3), 2)
    window = []
    if complete:
        y = complete[0]
        while len(window) < need and y in per_year:
            window.append(y)
            y -= 1
        # سابقه ناقص بود؟ سالِ در‌جریان را فقط در صورتی اضافه میکنیم که دقیقاً
        # بعد از آخرین سالِ کامل باشد (۱۲÷م روی بلندترین میاندورهٔ همان سال).
        if (len(window) < need and in_progress
                and in_progress == window[0] + 1):
            window.insert(0, in_progress)
            in_progress = None
    out = {"years_required": need, "years_available": len(window),
           "in_progress_year": in_progress,
           "fiscal_years": [str(y) for y in reversed(window)]}
    if len(window) < need:
        # ── قاعدهٔ خروجی جدول بنیادی: سطر هرگز حذف نمیشود ──────────────────
        # اگر به‌جای ۳ دوره فقط ۲ دوره (یا کمتر) موجود است، مقادیرِ موجود درج
        # میشود و به‌جایِ هر دورهٔ ناموجود «-» می‌نشیند. `eps_series` پس از این
        # همیشه به بلندای `years_required` است؛ دوره‌های غایب = None.
        if not window:
            out.update({"eps_series": None, "pass": False, "data_gap": True,
                        "available_periods": 0, "periods_missing": need,
                        "partial": False,
                        "reason": "کمتر از %d سال مالیِ متوالی با EPS ثبت‌شده (موجود: 0)"
                                  % need})
            return out
        picked_g = {yr: _pick(yr) for yr in window}
        top = max(picked_g)
        slots = list(range(top - need + 1, top + 1))          # قدیمی ← تازه
        have = [str(y) for y in slots if y in picked_g]
        out.update({
            "eps_series": [(round(_f(picked_g[y][0]), 2) if y in picked_g else None)
                           for y in slots],
            "period_slots": [str(y) for y in slots],
            "period_ends": [picked_g[y][1] if y in picked_g else None for y in slots],
            "evidence": [picked_g[y][2] if y in picked_g else "missing" for y in slots],
            "period_months": [picked_g[y][3] if y in picked_g else None for y in slots],
            "available_periods": len(have),
            "periods_missing": need - len(have),
            "partial": True,
            "pass": False, "data_gap": True,
            "reason": ("فقط %d دوره از %d موجود است — %s"
                       % (len(have), need,
                          " | ".join("%s: %s" % (y, _n(picked_g[int(y)][0])) for y in have)))
                       if len(have) < need else ""})
        return out
    picked = [_pick(yr) for yr in window]
    series = [p[0] for p in reversed(picked)]
    ev = [p[2] for p in reversed(picked)]
    out.update({
        "eps_series": [round(_f(s), 2) for s in series],
        "period_slots": [str(y) for y in reversed(window)],
        "partial": False, "available_periods": need, "periods_missing": 0,
        "period_ends": [p[1] for p in reversed(picked)],
        "evidence": ev,
        "period_months": [p[3] for p in reversed(picked)],
        "net_profit_series": [None] * need,
        "consecutive_years": True,
        "strictly_rising": all(series[i] < series[i + 1] for i in range(len(series) - 1)),
        "all_profitable": all(_f(s) > 0 for s in series),
        "consolidated_used": any(p[4] for p in picked),
        "audited_only": all(e == "audited_year_end" for e in ev),
        # هر سالِ غیرتلفیقیِ حسابرسی‌شده نبودن → شواهد «جایگزین» و باید برچسب بخورد
        "relaxed_evidence": any(e != "audited_year_end" for e in ev),
        # میاندورهٔ کوتاه‌مدت سال‌سازی‌شده ضعفِ روش است نه ضعفِ شرکت
        "low_quality_track": any(e.startswith("annualized_interim") for e in ev),
        "source": "کدال — صورت‌های مالی سالانه + میاندوره"})
    out["data_gap"] = False
    out["pass"] = bool(out["strictly_rising"] and out["all_profitable"])
    # اگر تنها دلیلِ «صعودی نبودن»، سالِ جاریِ فقط-۳ماهه باشد، نتیجه قابلِ استناد
    # نیست (۶۲ ریالِ فصل اول ≠ سال کامل). این را soft_gap می‌نامیم: عدد نشان داده
    # میشود ولی رابط کاربری نباید آن را «ردِ قطعیِ روند» بخواند.
    out["soft_gap"] = bool(not out["pass"] and ev[-1] == "annualized_interim_short")
    if out["pass"]:
        out["reason"] = ""
    else:
        # شکستِ واقعیِ روند (هر ۳ دوره موجود) → علت از خودِ سری ساخته میشود،
        # نه متنِ عمومیِ «دیتا ناقص»؛ مثال: «سقوط سود به زیان در سال آخر».
        out["reason"] = fts_engine.eps_trend_reason(
            series, [str(y) for y in reversed(window)])
        if out["soft_gap"]:
            out["reason"] += (" — سالِ آخر تنها میاندورهٔ کوتاهِ سال‌سازی‌شده است "
                              "(قطعیتِ کمتر)")
    return out


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
        "WHERE %s AND period_months BETWEEN 1 AND 11 AND basic_eps IS NOT NULL "
        "ORDER BY period_end DESC LIMIT 40" % pred, params).fetchall()
    cand = [r for r in rows if not _is_consolidated_title(r[3] or "")]
    if not cand:
        return {"available": False, "reason": "صورت مالی میاندوره‌ایِ غیرتلفیقی ثبت نشده."}
    seen = set(track_period_ends or ())
    try:
        newest_ty = max(int(y) for y in (track_years or ()))
    except (TypeError, ValueError):
        newest_ty = 0
    if newest_ty:
        newer = [r for r in cand if int(str(r[0] or "")[:4] or 0) > newest_ty]
        if not newer:
            return {"available": False,
                    "reason": "میاندورهٔ تازه‌تر از آخرین سالِ سابقه ثبت نشده است."}
        cand = newer
    pe, pm, eps, title = cand[0]
    if str(pe or "")[:10] in seen:
        return {"available": False, "period_end": str(pe or "")[:10],
                "reason": "میاندورهٔ جاری به‌عنوان سالِ در‌جریان داخل خودِ سابقه محاسبه شده."}
    pm = int(_f(pm)) or 1
    eps = _f(eps)
    try:
        y = int(str(pe or "")[:4])
    except (TypeError, ValueError):
        y = 0
    prev = next((r for r in cand[1:] if str(r[0] or "")[:4] == str(y - 1)
                 and int(_f(r[1])) == pm), None)
    projected = round(eps * 12.0 / pm, 2)
    return {"available": True, "period_end": str(pe or "")[:10], "period_months": pm,
            "eps_interim": round(eps, 2), "eps_projected_year": projected,
            "same_period_last_year": (None if prev is None else round(_f(prev[2]), 2)),
            "interim_yoy_pct": _pct(eps, _f(prev[2])) if prev is not None else None,
            "continues_trend": (None if last_fy_eps is None
                                else projected > _f(last_fy_eps)),
            "annualize_label": "EPS میاندوره × ۱۲÷%d" % pm,
            "title": str(title or "")[:70]}


def ind2_eps_track(conn, symbol, th=None, sector="", last_fy_eps=None) -> dict:
    """EPS سه سال مالی متوالی — اکیداً صعودی و همگی مثبت (لایهٔ ۲)، دو سطحِ شاهد.

    سطح ۱ (معتبرترین): fts_engine.eps_trend_3y — فقط ۱۲ماههٔ حسابرسی‌شدهٔ
      غیرتلفیقیِ سال‌های متوالی. همین مسیر در v8 تنها ملاک بود و روی این
      دیتابیس برای نمادهای زیادی «بی‌داده» برمی‌گرداند.
    سطح ۲ (پشتیبانِ v10): _eps_track_blended — سال‌پایان (حسابرسی‌شده یا
      نشده) و در نبودش میاندوره × ۱۲÷م، همان چیزی که دستور کار با عبارت
      «year-end and interim statements» می‌خواهد. تنزلِ شاهد با
      `evidence_tier` و `relaxed_evidence` صریح اعلام میشود، نه پنهان.
    روی هر دو سطح، «تداومِ سال جاری» با `_interim_eps_check` سنجیده و فقط به‌صورت
    `interim_confirms` گزارش میشود (هشدارِ نرم، وتوی سخت نه — قراردادِ v9.7.4).
    """
    th = th or v10_thresholds()
    need = int(th["eps_years"])
    insurance = fts_engine.is_insurance_sector(sector)
    strict = (None if insurance else
              fts_engine.eps_trend_3y(conn, symbol, years=need, sector=sector))
    blended = (None if insurance else _eps_track_blended(conn, symbol, years=need))
    strict_ok = bool(strict and not strict.get("data_gap"))
    if strict_ok:
        base, tier = strict, "audited_year_end"
    elif blended and not blended.get("data_gap"):
        base = blended
        # رتبه‌بندیِ شفافِ شاهدِ جایگزین — از تمیز‌ترین به ضعیف‌ترین
        if blended.get("low_quality_track"):
            tier = "year_end_plus_interim"
        elif blended.get("consolidated_used"):
            tier = "consolidated_year_end"
        else:
            tier = "year_end_unaudited"
    else:
        # هیچ‌کدام پنجره را کامل نکرد؛ آن‌که دورهٔ واقعیِ بیشتری دارد نگه داشته
        # میشود تا سطرِ شاخص ۲ در جدول خالی نشود (قاعدهٔ «هرگز سطر را حذف نکن»).
        def _have(x):
            return len([v for v in ((x or {}).get("eps_series") or [])
                        if v is not None])
        _cands = [x for x in (strict, blended) if x]
        base = max(_cands, key=_have) if _cands else {}
        tier = "insufficient"
    if not base:
        base = {"eps_series": None, "pass": False, "data_gap": True,
                "years_required": need, "years_available": 0,
                "reason": ("صنعت بیمه — لایهٔ EPS اجرا نمیشود." if insurance
                           else "هیچ صورت مالیِ معتبری با EPS ثبت نشده.")}
    base["evidence_tier"] = tier
    base["strict_evidence"] = strict_ok
    base["relaxed_evidence"] = (False if strict_ok
                                else bool(base.get("relaxed_evidence")))
    base["consolidated_used"] = bool(base.get("consolidated_used"))
    base["low_quality_track"] = bool(base.get("low_quality_track"))
    base["soft_gap"] = bool(base.get("soft_gap"))
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
         "year_end_unaudited": "سال‌پایانِ غیرتلفیقی (حسابرسی‌نشده)",
         "consolidated_year_end": "سال‌پایانِ تلفیقی (غیرتلفیقیِ ۱۲ماهه موجود نیست)",
         "year_end_plus_interim": "سال‌پایان + میاندورهٔ سال‌سازی‌شده × ۱۲÷م",
         "insufficient": "شاهدِ کافی برای مسیر EPS موجود نیست"}[tier],
        " + راستی‌آزمایی میاندوره‌ای" if interim.get("available")
        else " (میاندورهٔ مستقلِ راستی‌آزمایی موجود نیست)"))
    base["threshold"] = "%d سال مالی متوالی" % need
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
        prof = profile or company_profile()
        return {"margin_pct": None, "pass": False, "ideal": False, "na": True,
                "band": "not_applicable", "threshold": th["margin_min"],
                "ideal_threshold": th["margin_ideal"], "optimal": False,
                "reason": ("این شرکت «بهای تمام‌شدهٔ کالای فروش‌رفته» درج نمیکند (%s)؛ "
                           "حاشیهٔ ناخالص فقط برای شرکت‌های تولیدی معنا دارد."
                           % prof["label"])}
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


def dynamic_annualized_sales(conn, symbol, series=None, ref=None, profile=None) -> dict:
    """فروش سالانه = فروش تجمیعی × (۱۲ ÷ م)، م = ماه‌های سپری‌شدهٔ سال مالی.

    ضریب ثابت نیست: ۳ ماه ×۴، ۴ ماه ×۳، ۵ ماه ×۲٫۴، ۶ ماه ×۲ و… (شرطِ صریحِ
    دستور کار). م از «بزرگ‌ترین ماهِ دارای گزارش تجمیعی در آخرین سال مالی» خوانده
    میشود، نه از تقویم — تا نمادی که ماهِ جاافتاده دارد درست annualize شود.
    راستی‌آزمایی: اگر برآورد بیش از ۴× یا کمتر از ۰٫۲۵× فروشِ صورت مالی سالانه
    شد، واحد/ساختارِ گزارش مشکوک است → مبنای سالانه به فروش کدال برمی‌گردد و
    `reconciled=False` ثبت میشود (همان گیتِ fts_engine، بدون واگرایی دو مسیر).

    طبقهٔ مالی/خدماتی/صندوق: «فروش کالا» معنا ندارد، پس مبنا **درآمد عملیاتیِ
    صورت مالی سالانه** است و گزارش ماهانه جای آن را نمی‌گیرد (قاعدهٔ جزوه).
    """
    series = series if series is not None else monthly_series(conn, symbol)
    ref_row = ref if ref is not None else fts_engine.reference_annual(conn, symbol)
    fs_rev = _f((ref_row or {}).get("revenue"))
    prof = profile or company_profile()
    op_basis = ((prof.get("kind") in ("financial", "service", "fund", "holding"))
                and fs_rev > 0)
    annual, months, basis, reconciled = 0.0, 0, "", True
    if op_basis:
        annual, months = fs_rev, 12
        basis = ("درآمد عملیاتیِ صورت مالی سالانه — جایگزینِ «فروش» برای طبقهٔ %s"
                 % prof.get("label", "مالی/خدماتی"))
    elif series:
        year = int(_f(series[0][0]))
        cur = _fiscal_year_rows(series, year)
        months = int(_f(cur[0][1])) if cur else 0
        ytd = _f(cur[0][3]) if cur else 0.0
        if months >= 1 and ytd > 0:
            factor = 12.0 / months
            annual = ytd * factor if months < 12 else ytd
            basis = (("تجمیعی %02d/%d × ۱۲÷%d (=×%.2f)" % (months, year, months, factor))
                     if months < 12 else
                     "تجمیعی ۱۲ ماهِ کاملِ سال مالی %d (×۱٫۰)" % year)
    if annual <= 0 and fs_rev > 0:
        annual, months = fs_rev, 12
        basis = "مراجعه به فروش صورت مالی سالانه (بی‌گزارش ماهانه)"
    if annual <= 0:
        return None
    # گیتِ «واحد مشکوک» فقط برای سالانه‌سازیِ واقعی (ماهِ سپری‌شده < ۱۲) معنا دارد؛
    # گزارشی که خودش ۱۲ ماه کامل را پوشش می‌دهد مستقیم پذیرفته می‌شود، نه مشکوک.
    if (fs_rev > 0 and not op_basis and 0 < months < 12
            and (annual > fs_rev * 4.0 or annual < fs_rev * 0.25)):
        reconciled = False
        annual, months = fs_rev, 12
        basis = "ضریب پویا مردود شد (واحد مشکوک) → فروش سالانهٔ کدال"

    return {"annual_sales_mrl": annual, "annual_sales_bt": _bt(annual),
            "months_used": months, "scale_factor": round(12.0 / max(months, 1), 4),
            "basis": basis, "reconciled": reconciled,
            "revenue_basis": prof.get("revenue_basis", ""),
            "operational_revenue_basis": bool(op_basis),
            "ytd_sales_bt": _bt(annual / max(12.0 / max(months, 1), 1e-9)),
            "scale_table": [{"months": m, "factor": round(12.0 / m, 2)}
                            for m in ANNUALIZATION_SCALE]}


def ind4_valuation(annual, gm, market_cap_rials, th=None, kind=None) -> dict:
    """۴الف فروش سالانه ÷ ارزش بازار (≥۱×) + ۴ب پتانسیل سود ناخالص ÷ ارزش بازار (≥۴۰٪).

    سود ناخالص پتانسیل = فروش سالانهٔ annualized × حاشیهٔ ناخالص.
    برای شرکت مالی که «سود ناخالص» ندارد، حاشیهٔ سود خالص به‌عنوان «مبنای
    جایگزین» مصرف و صریحاً برچسب می‌خورد تا با عددِ شرکت تولیدی اشتباه نشود.
    """
    th = th or v10_thresholds()
    # سند v2.1: برای هلدینگ/سرمایه‌گذاری، فروش‌به‌ارزش‌بازار و جانشین NAV ممنوع ⇒ N/A
    if kind == "holding":
        return {"available": False, "na": True, "pass": False, "potential_pass": False,
                "sales_pass": False, "rule_ref": "F-04",
                "reason": "هلدینگ/سرمایه‌گذاری: اعمال نسبت فروش به ارزش بازار و جانشین NAV مجاز نیست (N/A)."}
    mcap = _f(market_cap_rials)
    if not annual or mcap <= 0:
        return {"available": False, "pass": False, "potential_pass": False,
                "sales_pass": False, "mcap_ht": round(mcap / 1e13, 2),
                "potential_threshold": th["potential_min"],
                "sales_threshold": th["sales_to_mcap_min"],
                "reason": "فروش سالانه یا ارزش بازار موجود نیست."}
    ann_rial = _f(annual["annual_sales_mrl"]) * MRL_TO_RIAL
    sales_ratio = ann_rial / mcap
    margin = None
    margin_basis, margin_label = "gross_margin", "حاشیهٔ سود ناخالص"
    if gm and not gm.get("na"):
        margin = _f(gm.get("margin_pct")) or None
    elif gm and gm.get("net_margin_pct") is not None:
        margin = _f(gm["net_margin_pct"])
        margin_basis, margin_label = "net_margin_proxy", "حاشیهٔ سود خالص (جایگزینِ مالی)"
    pot_pct = (round(ann_rial * (margin / 100.0) / mcap * 100.0, 1)
               if margin is not None else None)
    sales_pass = sales_ratio >= th["sales_to_mcap_min"]
    pot_pass = pot_pct is not None and pot_pct >= th["potential_min"]
    return {"available": True, "mcap_ht": round(mcap / 1e13, 2),
            "annual_sales_bt": annual["annual_sales_bt"],
            "months_used": annual["months_used"], "scale_factor": annual["scale_factor"],
            "annualize_basis": annual["basis"], "reconciled": annual["reconciled"],
            "sales_to_mcap": round(sales_ratio, 2),
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
                  "رشد فروش بدون مجوز افزایش نرخ عملاً ممکن نیست و حاشیه تحت "
                  "سرکوب نرخ است. استراتژی FTS این گروه را از سبد بیرون می‌گذارد."),
    "neutral": ("رژیم مخلوط/بی‌طرف — نیازمند بررسی موردیِ نرخ محصول و مجوز "
                "افزایش قیمت."),
}


def ind5_industry(sector, cfg=None, market_cap_rials=0.0, total_market_cap_rials=0.0) -> dict:
    """تگ صنعت: آزاد/بورس‌کالایی در برابر دستوری (دیکشنری fts_engine، بدون موازی‌سازی)."""
    sec = fts_engine.sector_filter(sector, cfg=cfg, market_cap_rials=market_cap_rials,
                                   total_market_cap_rials=total_market_cap_rials)
    verdict = sec.get("verdict", "neutral")
    sec["outlook"] = _PRICING_OUTLOOK.get(verdict, _PRICING_OUTLOOK["neutral"])
    sec["regime_label"] = {"free": "آزاد / بورس کالا", "mandatory": "دستوری",
                           "neutral": "مخلوط / بی‌طرف"}[verdict]
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
            reasons.append("ارزش بازار نامشخص — پیش‌شرطِ کفِ ارزش بازار قابلِ بررسی نیست")
        elif mcap < floor:
            reasons.append("ارزش بازار (%s همت) زیرِ کفِ %s همت"
                           % (_n(mcap / HEMMAT_RIAL, 2), _n(_f(cfg.get("mcap_min_hmt")), 2)))
    # ۳) نقدشوندگی — حداقلِ میانگین ارزش معاملات روزانه (همت)
    min_liq = _f(cfg.get("min_trade_val"))
    if min_liq > 0:
        tv = trade_value_hmt(conn, symbol, liq_map=liq_map)
        if tv <= 0:
            reasons.append("میانگین ارزش معاملات روزانه ناموجود — پیش‌شرطِ نقدشوندگی برقرار نیست")
        elif tv < min_liq:
            reasons.append("نقدشوندگی (%s همت) زیرِ آستانهٔ %s همت"
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
            gm["net_margin_period"] = str(ref.get("period_end") or "")[:10]
        elif rev > 0 and net:
            gm["net_margin_rejected_pct"] = round(net / rev * 100.0, 1)
    annual = dynamic_annualized_sales(conn, symbol, series=series, ref=ref, profile=prof)
    # سند v2.1: گیتِ «عدم اعمال نسبت فروش بر هلدینگ‌ها» (holdings_sales_na)
    _holdings_na = bool((cfg or {}).get("holdings_sales_na", True))
    val = ind4_valuation(annual, gm, market_cap_rials, th=th,
                         kind=(prof.get("kind") if (prof and _holdings_na) else None))
    sec = ind5_industry(sector, cfg=cfg, market_cap_rials=market_cap_rials,
                        total_market_cap_rials=total_market_cap_rials)
    # سند v2.1: استثنای دارویی — فقط با حاشیهٔ ناخالص > آستانهٔ پیکربندی
    # (pharma_margin_exempt_min؛ ۰ = غیرفعال) مجاز است.
    _pm = float((cfg or {}).get("pharma_margin_exempt_min", 0) or 0)
    try:
        _is_pharma = "دارو" in fts_engine.norm_fa(sector)
    except Exception:
        _is_pharma = False
    if _pm > 0 and _is_pharma:
        _m = None
        try:
            _m = gm.get("margin_pct") if isinstance(gm, dict) else None
        except Exception:
            _m = None
        if _m is None or float(_m) < _pm:
            sec = dict(sec)
            sec["verdict"] = "mandatory"
            sec["reason"] = ("دارویی با حاشیهٔ ناخالص کمتر از %.0f٪ مجاز نیست (سند v2.1)." % _pm)

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

    reasons = []
    if sec.get("verdict") == "mandatory" and sec.get("exclusion_active"):
        reasons.append("قیمت‌گذاری دستوری — حذف خودکار")
    # v10: همهٔ حذف‌های خودکار در یک نقطه — بیمه / تعلیق / ماده ۱۴۱ /
    # کف ارزش بازار / نقدشوندگی / Include-Excludeِ صنایعِ پنل.
    gate = industry_gate(sector, cfg)
    reasons += risk_gates(conn, symbol, sector, market_cap_rials, cfg=cfg, th=th,
                          m141_map=m141_map, liq_map=liq_map, gate=gate)

    return {"symbol": symbol, "sector": sector, "pricing_mode": sec.get("verdict"),
            "market_cap_rials": _f(market_cap_rials), "score": score,
            "passes": passes, "excluded": bool(reasons), "exclusion_reasons": reasons,
            "verdict": ("EXCLUDED" if reasons else "STRONG" if score >= 4
                        else "WATCH" if score >= 3 else "REJECT"),
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
        txt1 = "⚠️ ۱الف رشد ریالی محاسبه نمیشود — %s" % (g.get("reason") or "مخرج YoY موجود نیست")
    elif g.get("pass"):
        txt1 = "✅ ۱الف رشد ریالی %s — آستانهٔ %g٪ پاس شد" % (
            _pct_txt(g.get("monetary_pct")), th["monetary_growth_min"])
    else:
        txt1 = "⚠️ ۱الف رشد ریالی %s — زیر آستانهٔ %g٪" % (
            _pct_txt(g.get("monetary_pct")), th["monetary_growth_min"])
    if v.get("data_gap"):
        txt1b = "⚠️ ۱ب حجم/تناژ قابل راستی‌آزمایی نیست — %s" % (v.get("reason") or "بدون داده")
    elif v.get("pass"):
        txt1b = "✅ ۱ب رشد فیزیکی تأیید شد (مبنای %s، اطمینان %s)" % (
            v.get("basis"), v.get("confidence"))
    else:
        txt1b = "🚫 ۱ب رد شد — %s" % (v.get("reason") or "رشد فقط از افزایش نرخ آمده است")
    insights.append({"step": "۱", "title": "لایهٔ ۱ — درآمد/فروش (رشد ریالی + تأیید حجم)",
                     "type": "success" if axis1 else "warning",
                     "text": "%s<br>%s" % (txt1, txt1b)})
    breadth = v.get("breadth") or {}
    details["۱"] = {
        "title": "درآمد/فروش — دو چکِ الزامی",
        "formula": ("۱الف = (تجمیعی دوره ÷ تجمیعی همان دورهٔ سال قبل) × ۱۰۰ − ۱۰۰ · پاس ≥ %g٪"
                    " · ۱ب = رشد کمیت ≥ %g٪ (یا رشد واقعیِ پس از تورم ≥ %g٪ و پهنای رشد ≥ %.0f٪)"
                    % (th["monetary_growth_min"], th["volume_growth_min"],
                       th["volume_growth_min"], th["volume_breadth_min"] * 100)),
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
            {"key": "1b", "label": "رشد فیزیکی / تناژ",
             "state": _state(v.get("pass"), gap=bool(v.get("data_gap"))),
             "value": _pct_txt(v.get("volume_pct") if v.get("quantity_verified")
                               else v.get("real_pct")),
             "threshold": "≥ %g٪" % th["volume_growth_min"],
             "verified": bool(v.get("quantity_verified")),
             "confidence": v.get("confidence"),
             "detail": "%s · اطمینان %s" % (v.get("basis") or "—", v.get("confidence") or "—")}]}


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
                else " 〔شاهدِ جایگزین: %s〕" % (
                    "تلفیقی" if e.get("consolidated_used") else
                    "میاندورهٔ سال‌سازی‌شده" if e.get("low_quality_track") else
                    "حسابرسی‌نشده"))
    if e.get("data_gap") and _partial:
        # قاعدهٔ جدول: سطر هرگز حذف نمیشود — مقادیرِ موجود + «-» برایِ دورهٔ
        # غایب، و عنوان/سلول‌ها قرمز با ذکرِ تعدادِ دوره‌های موجود.
        insights.append({"step": "۲", "title": "لایهٔ ۲ — سابقهٔ ۳ سالهٔ سودسازی (EPS)",
                         "type": "danger", "partial": True,
                         "row": _row["markdown"],
                         "text": "🚫 شاخص ۲ (تنها %s دوره موجود است) — EPS %s ریال · %s"
                                 % (_fa(_avail), " ← ".join(_cells),
                                    e.get("reason") or "کمبود صورت مالی")})
    elif e.get("data_gap"):
        insights.append({"step": "۲", "title": "لایهٔ ۲ — سابقهٔ ۳ سالهٔ سودسازی (EPS)",
                         "type": "warning",
                         "text": "⚠️ محاسبه نمیشود — %s" % (e.get("reason") or "کمبود صورت مالی")})
    elif e.get("pass"):
        insights.append({"step": "۲", "title": "لایهٔ ۲ — سابقهٔ ۳ سالهٔ سودسازی (EPS)",
                         "type": "success",
                         "text": "✅ EPS %s ریال در سال‌های %s%s%s"
                                 % (" ← ".join(_cells),
                                    " ← ".join(str(y) for y in (e.get("fiscal_years") or [])),
                                    ev_badge,
                                    "" if e.get("interim_confirms") is not False
                                    else " — ⚠️ برآورد میاندوره‌ای روند را تأیید نمیکند")})
    else:
        _vals = " ← ".join(_cells)
        insights.append({"step": "۲", "title": "لایهٔ ۲ — سابقهٔ ۳ سالهٔ سودسازی (EPS)",
                         "type": "warning" if e.get("soft_gap") else "danger",
                         "text": "%s%s%s" % (
                             "⚠️ " if e.get("soft_gap") else "🚫 ",
                             (("EPS %s ریال — %s" % (_vals, e.get("reason")))
                              if e.get("soft_gap") and _vals
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
                         "text": "✅ حاشیهٔ %s — ایده‌آل (≥ %g٪)"
                                 % (_pct_txt(gm.get("margin_pct"), signed=False),
                                    th["margin_ideal"])})
    elif gm.get("pass"):
        insights.append({"step": "۳", "title": "لایهٔ ۳ — حاشیهٔ سود ناخالص",
                         "type": "info",
                         "text": "✅ حاشیهٔ %s — قابل‌قبول (≥ %g٪، ایده‌آل ≥ %g٪)"
                                 % (_pct_txt(gm.get("margin_pct"), signed=False),
                                    th["margin_min"], th["margin_ideal"])})
    else:
        insights.append({"step": "۳", "title": "لایهٔ ۳ — حاشیهٔ سود ناخالص",
                         "type": "warning",
                         "text": "⚠️ حاشیهٔ %s — زیر کف %g٪"
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
        # «—» و «0×» دو چیز متفاوت‌اند: نبودِ حاشیه یعنی نسبت محاسبه نشده، نه صفر
        pot_txt = ("محاسبه نمیشود (حاشیهٔ ناخالص ندارد)" if val.get("potential_pct") is None
                   else "%s از ارزش بازار (≥ %g٪)"
                        % (_pct_txt(val.get("potential_pct"), signed=False),
                           val.get("potential_threshold") or 0))
        s_txt = ("محاسبه نمیشود" if val.get("sales_to_mcap") is None
                 else "= %g× (≥ %g×)" % (val.get("sales_to_mcap"),
                                         val.get("sales_threshold") or 0))
        insights.append({
            "step": "۴", "title": "لایهٔ ۴ — پتانسیل سود سالانه به ارزش بازار",
            "type": "success" if val.get("pass") else "warning",
            "text": ("%s پتانسیل سود ناخالص %s · %s فروش سالانه ÷ ارزش بازار %s · "
                     "ضریب پویا ×%g برای %d ماه"
                     % (pot_ok, pot_txt, s_ok, s_txt,
                        _f(ann.get("scale_factor")), int(_f(ann.get("months_used")))))})
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
    tagline = "تگ: %s" % ("، ".join(sec.get("matched_tokens") or []) or "—")
    if verdict5 == "mandatory":
        insights.append({"step": "۵", "title": "لایهٔ ۵ — رژیم قیمت‌گذاری صنعت و چشم‌انداز",
                         "type": "danger",
                         "text": "🚫 مردود — گروه «%s» دستوری است. %s"
                                 % (res.get("sector") or "—", tagline)})
    elif verdict5 == "free":
        insights.append({"step": "۵", "title": "لایهٔ ۵ — رژیم قیمت‌گذاری صنعت و چشم‌انداز",
                         "type": "success",
                         "text": "✅ تایید شد — گروه «%s» آزاد/بورس‌کالایی است. %s"
                                 % (res.get("sector") or "—", tagline)})
    else:
        insights.append({"step": "۵", "title": "لایهٔ ۵ — رژیم قیمت‌گذاری صنعت و چشم‌انداز",
                         "type": "info",
                         "text": "ℹ️ بی‌طرف — گروه «%s» در هیچ‌یک از دو فهرست نیست؛ "
                                 "بررسی موردی لازم است." % (res.get("sector") or "—")})
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
    ann = val.get("annual") or {}
    gaps = []
    if g.get("data_gap"):
        gaps.append({"layer": "۱الف", "axis": "1a_monetary_growth",
                     "why": g.get("reason") or "",
                     "fix": g.get("remediation") or _MS_GAP_HINT})
    if v.get("basis") == "unavailable":
        gaps.append({"layer": "۱ب", "axis": "1b_physical_volume",
                     "why": "هیچ ستونِ حجم/تناژ فیزیکی در monthly_sales وجود ندارد.",
                     "fix": "با افزودن ستون فیزیکی (مثلاً monthly_sales.quantity) و پرکردنش "
                            "از فیلد «حجم فروش/تناژ» صورت وضعیت فروش کدال، لایهٔ ۱ب از "
                            "«تعدیل تورمی» به «شاهد مستقیم» ارتقا می‌یابد."})
    elif v.get("data_gap"):
        gaps.append({"layer": "۱ب", "axis": "1b_physical_volume",
                     "why": v.get("reason") or "", "fix": "گزارش ماهانهٔ سال قبل لازم است."})
    if e.get("data_gap"):
        gaps.append({"layer": "۲", "axis": "2_eps_trend", "why": e.get("reason") or "",
                     "available_periods": int(e.get("available_periods") or 0),
                     "required_periods": int(e.get("years_required") or 3),
                     "partial": bool(e.get("partial")),
                     "fix": "با همگام‌سازی کدال (mode=backfill) صورت‌های ۱۲ماههٔ سال‌های "
                            "قدیمی‌تر این نماد اضافه میشود."})
    elif e.get("soft_gap"):
        gaps.append({"layer": "۲", "axis": "2_eps_trend", "why": e.get("reason") or "",
                     "fix": "با انتشار صورت ۱۲ماههٔ سال مالی جاری، داوری قطعی میشود."})
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


@router.get("/api/fundamental/{symbol}")
def get_fundamental(symbol: str, months: int = 0):
    """کارت بنیادی پنج‌لایهٔ FTS v10 — درآمد (ریالی+حجمی)، سودسازی، حاشیه، پتانسیل، صنعت.

    برخلاف v8 که فقط خروجیِ `fts_engine.scan_symbol` را بازآرایی میکرد، اینجا هر
    پنج لایه با قواعدِ نسخهٔ ۱۰ محاسبه میشوند: آستانهٔ ۶۰٪ برای رشد ریالی، چکِ
    الزامیِ رشد فیزیکی، سابقهٔ ۳ سالهٔ EPS + تداوم میاندوره‌ای، حاشیهٔ ۲۰/۳۰٪،
    سالانه‌سازیِ پویا ×۱۲÷م با آستانهٔ ۳۳٪ پتانسیل سود، و رژیم قیمت‌گذاری صنعت.
    `months` برای سازگاری با فراخوانی‌های قدیمی پذیرفته میشود و در داوری اثر
    ندارد — «م» از خودِ گزارش‌های ماهانه خوانده میشود، نه از پارامتر کاربر.
    """
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(_INSTR_SQL, (symbol,))
        inst = cur.fetchone()
        pred, params = fts_engine.sym_in("symbol", symbol)
        cn = conn.execute("SELECT company_name FROM financial_statements WHERE %s "
                          "ORDER BY period_end DESC LIMIT 1" % pred, params).fetchone()
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
        m_und = re.match(r"^(.*?)\d+$", symbol)
        base_cand = m_und.group(1) if m_und else None
        if base_cand and base_cand != symbol and inst is None:
            cur.execute(_INSTR_SQL, (base_cand,))
            inst = cur.fetchone()
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
            m30 = re.search(r"\S+\s+([^\s-]+)[\s-]?", str(inst["l_val30"]))
            probe = m30.group(1) if m30 else None
            if probe and conn.execute("SELECT 1 FROM instruments WHERE l_val18 = ?",
                                      (probe,)).fetchone():
                ref_symbol, ref_reason = probe, "قرارداد اختیار معامله — تحلیل به نماد اصلی آن"

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
                   "eps_required": int(e.get("years_required") or th["eps_years"]),
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

        history = [{"period_end": str(r["period_end"])[:10], "fiscal_year": r["fiscal_year"],
                    "revenue": r["revenue"], "gross_profit": r["gross_profit"],
                    "net_profit": r["net_profit"], "eps": r["basic_eps"],
                    "audited": r["audited"], "consolidated": r["consolidated"]}
                   for r in fts_engine.annual_statements(conn, norm_symbol, limit=6)]

        return {"status": "success",
                "symbol": symbol, "sector": sector, "pricing_mode": res["pricing_mode"],
                "score": res["score"], "verdict": res["verdict"],
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
    """
    conn = get_db()
    try:
        # تطبیق چند-نویشتاری (ك/ي عربی ↔ فارسی): ورودیِ کاربر ممکن است فارسی
        # باشد و رکوردهای کدالِ همان نماد با نوشتار عربی ذخیره شده باشند.
        _fp, _fa = fts_engine.sym_in("symbol", symbol)
        _raw = conn.execute(
            "SELECT period_end, period_months, revenue, operating_profit,"
            " net_profit, basic_eps, publish_date FROM financial_statements"
            " WHERE %s ORDER BY period_end DESC, publish_date DESC LIMIT ?" % _fp,
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
            for r in conn.execute("""
                SELECT i.l_val18,
                       COALESCE(m.market_cap,
                                (SELECT d.market_cap FROM daily_prices d
                                  WHERE d.ins_code = i.ins_code AND d.market_cap > 0
                                  ORDER BY d.d_even DESC LIMIT 1)),
                       COALESCE(i.sector_name, 'سایر'),
                       COALESCE(m.market_cap_src,
                                (SELECT d.market_cap_src FROM daily_prices d
                                  WHERE d.ins_code = i.ins_code AND d.market_cap > 0
                                  ORDER BY d.d_even DESC LIMIT 1))
                FROM instruments i
                LEFT JOIN market_watch m ON m.ins_code = i.ins_code"""):
                k = fts_engine.norm_fa(r[0])
                if k and k not in ctx:
                    ctx[k] = (r[1], r[2], r[3])
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
        "       COUNT(DISTINCT CASE WHEN p.symbol IS NOT NULL THEN l.symbol END) "
        "FROM latest l "
        "JOIN monthly_sales c ON c.symbol = l.symbol AND c.year * 100 + c.month = l.k "
        "                     AND c.ytd_revenue > 0 "
        "LEFT JOIN monthly_sales p ON p.symbol = l.symbol "
        "     AND p.year = (l.k / 100) - 1 AND p.month = (l.k % 100) "
        "     AND p.ytd_revenue > 0").fetchone()
    n_ms_latest, n_1a = int(_f(row[0])), int(_f(row[1]))
    # منشأ مخرج: ستونِ رسمیِ «مقایسه با دورهٔ مشابه» (اولویت ۱ موتور) چقدر پر است؟
    n_prev_col = int(_f(conn.execute(
        "SELECT COUNT(DISTINCT m.symbol) FROM monthly_sales m "
        "JOIN (SELECT symbol, MAX(year * 100 + month) AS k FROM monthly_sales "
        "      WHERE ytd_revenue > 0 GROUP BY symbol) l "
        "  ON l.symbol = m.symbol AND m.year * 100 + m.month = l.k "
        "WHERE COALESCE(m.ytd_revenue_prev, 0) > 0").fetchone()[0]))
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
            y, mm, ev = int(str(pe or "")[:4]), int(_f(pm)), float(eps)
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
            "denominator_from_same_month_last_year": n_1a - n_prev_col,
            "note": "نمادهایی که ردیف (سال قبل، همان ماه) با فروش تجمیعی > ۰ دارند"},
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



@router.get("/api/fts/{symbol}")
def get_fts_symbol(symbol: str, v10: int = 0):
    """۵ شاخص FTS برای یک نماد + جزئیات کامل هر شاخص.

    `v10=1` خلاصهٔ پنج‌لایهٔ نسخهٔ ۱۰ را هم اضافه میکند (یک ارزیابی اضافه؛
    پیش‌فرض خاموش است تا هزینهٔ مصرف‌کننده‌های فعلی دو برابر نشود).
    """
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            cfg = load_fts_config()
            mcap, sector, total_mcap, mcap_info = _fts_market_ctx(conn, symbol)
            result = fts_engine.scan_symbol(conn, symbol, mcap or 0.0, total_mcap, sector, cfg=cfg)
            result["market_cap_rials"] = mcap
            result["market_cap_src"] = mcap_info["source"]
            result["market_cap_error"] = mcap_info["error"]

            if int(v10 or 0):
                res = evaluate_v10(conn, symbol, mcap, total_mcap, sector, cfg=cfg)
                result["fts_v10"] = {"score": res["score"], "passes": res["passes"],
                                     "verdict": res["verdict"], "profile": res["profile"],
                                     "methodology": res["methodology"],
                                     "indicators": res["indicators"]}
            return {"status": "success", "data": result}
        finally:
            conn.close()
    except Exception as e:
        return {"status": "error", "message": str(e)}













