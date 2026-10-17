"""codal_units.py — تنها تعریفِ «واحدِ پول» درِ کلِ پروژه.

چرا این فایل متولد شد (مرحلۀ 6 مأموریت CODAL، 1405/07/21). ادعایِ «این عدد
میلیون ریال است» چهار جا مستقل نوشته شده بود و هیچ‌کدام به خودِ ردیف نگاه
نمی‌کرد:

  * `fts_engine.MRL_TO_RIAL = 1e6`        → دو مصرف (`sales_to_marketcap`,
    `gross_profit_potential`)
  * `api/fundamental.MRL_TO_RIAL = 1e6`   → مصرفِ سوم (کارِ کارتِ جزئیات)
  * `fts_engine.normalize_mrl_to_btom`    → `÷ 10_000` (قاعدهٔ جزوه)
  * `api/fundamental._btom`               → تارِ دومِ همین `÷ 10_000`

نتیجه‌اش: موتورِ پنج شاخص **هیچ‌وقت `unit_norm` را نمی‌خواند**. ستونی که درِ
بانک هست و موقعِ درج پر می‌شود (`codal_fetcher.fs_derived` ← `_classify_unit`)
درِ هیچ کوئریِ خوانده نمی‌شد (`FS_COLS` نداشتش). پس هر ردیفی — از جمله ردیف‌هایی
که هیچ منبعی واحدشان را نگفته‌اند — با ضریبِ 1e6 به ریال می‌رفت و بر ارزشِ بازار
تقسیم می‌شد، بی‌این‌که کسی بپرسد واحدش چه بوده.

قاعده (همین فایل، بی‌هیچ استثنای دوم):
  1) مقیاسِ یکِ ردیف از خودِ `unit_norm` خوانده می‌شود، نه از ثابتِ ماژول:
     'mrl' (میلیون ریال) → 1e6 ریال، 'btl' (میلیارد تومان) → 1e10 ریال، و هر
     چیزِ دیگر (NULL، رشتهٔ خالی، 'unknown') → **بی‌واحد**.
  2) «بی‌واحد» با صفر یا clamp یا «همان 1e6 که بقیه هستند» جایگزین نمی‌شود.
     `to_rial()` در این حالت None می‌دهد و مصرف‌کننده باید رأیِ وابسته به
     مقیاس را **نامعتبر** اعلام کند. نسبت‌های بی‌مقیاس (رشد، حاشیۀ سود) که صورت
     و مخرجشان از یکِ ردیفِ تک‌واحد است، از این قاعده متأثر نمی‌شوند.
  3) مبناىِ داخلیِ موتور «میلیون ریال» است و `to_mrl()` تنها جایی است که مقیاس
     عوض می‌شود؛ پس `annual_sales_mrl` همیشه «میلیون ریال» معنا می‌دهد، حتی اگر
     ردیفِ منبع میلیارد تومان بوده باشد.
  4) نوشتن از `classify()` می‌گذرد (`codal_fetcher._classify_unit` به همین واگرد
     می‌کند) و خواندن از `PRESENT_SQL`/`is_valid()` — همان ستون، همان مجموعه.
     هم‌سنجیِ دو شرط رویِ دادهٔ واقعی درِ `dev/codal_unit_scale_v1090.py` سنجیده
     می‌شود، نه با فرض.
  5) هیچِ نوشتارِ دیگری مقیاس نمی‌سازد: «میلیون تومان» یا «ریال» تنهایی درِ
     `classify` شناخته‌شده نیستند و ردیف‌شان **بی‌واحد** می‌ماند (fail-closed).
     این عمدی است: افزودنِ حدسِ 1e5 برایِ «میلیون تومان» اگر روزی همان نوشتار با
     معنایِ دیگری بیاید، 10× اشتباهِ بی‌صدا می‌سازد؛ بهتر است آن روز یکِ رأی
     نامعتبر ببینیم تا 9000 رأیِ غلط.

دو محدودیت که درِ همین فایل اعلا می‌شوند (نه پنهان):
  * `monthly_sales` هیچ ستونِ واحدی برایِ پولِ ندارد (تنها `volume_unit` برایِ
     حجم). مقیاسِ آن از خودِ ردیف نمی‌آید و تنها شاهدِ موجود، گیتِ «واحد مشکوک»
     درِ `fts_engine.annualize_rows` است که سالانه‌سازیِ ماهانه را با فروشِ
     سالانۀ صورتِ مالی می‌سنجد. این ماژول برایِ آن ادعایِ اثبات نمی‌کند؛ درِ رابط
     با `unit_basis` اعلام می‌شود.
  * ردیف‌هایی که `unit` خامشان خالی ولی `unit_norm`شان پر است دروغ نمی‌گویند:
     واحد را خودِ شیتِ گزارش درِ واکشیِ عمیق گفته (`_apply` ← `scrape_report`).
     `provenance()` همین دو حالت را از هم جدا می‌کند تا شمارشِ خامِ
     `unit IS NULL` «نقصِ داده» خوانده نشود.

stdlib-only است تا هیچ چرخۀ import نسازد (الگو: `codal_periods.py`،
`price_basis.py`). چون سطح-بال import می‌شود و `api/` هم لازمش دارد، درِ
`fts_terminal.spec` → `hiddenimports` صریح فهرست شده است.
"""
from __future__ import annotations

import re

__all__ = [
    "SCALES", "UNIT_TOKENS", "RIAL_PER_BTM", "MISSING_SQL", "PRESENT_SQL",
    "missing_sql", "present_sql", "classify", "scale", "is_valid", "is_missing",
    "to_rial", "to_btom", "to_mrl", "label", "provenance", "tables",
    "unit_counts",
]

# مقیاس‌ها: چند ریال در هر یکِ عددِ ذخیره‌شده.
#   mrl = «ميليون ريال»  = 1e6 ریال
#   btl = «میلیارد تومان» = 1e9 تومان = 1e10 ریال (سمتِ پولِ رایجِ نمایش)
# نامِ توکن از `codal_fetcher._classify_unit`ِ پیشین می‌آید و معنایش همان است؛
# همان توکن‌ها که درِ ستونِ بانک نشسته‌اند، پس دادهٔ امروز بی‌تبدیلِ دوباره می‌خواند.
SCALES = {"mrl": 1_000_000.0, "btl": 10_000_000_000.0}

# یک میلیارد تومان = 1e9 تومان = 1e10 ریال (قاعدهٔ جزوه: «حذف 4 رقمِ سمت راست»
# از میلیون ریال — یعنی 1e6/1e10 = 1e-4، که همان ÷10_000 است).
RIAL_PER_BTM = 1e10

# واگردِ `codal_fetcher.norm`: ي/ك عربی ← فارسی، حذفِ نیم‌فاصله/RLM و فاصله‌ها.
# این تنها normalizeِ مسیرِ واحد است (`_classify_unit` به `classify` واگرد کرده)،
# پس دو نوشتارِ «عربی/فارسی» هرگز از هم جدا نمی‌شوند.
_NORM = str.maketrans({"ي": "ی", "ك": "ک", "\u200c": "", "\u200f": "",
                       "\u064a": "ی"})


def classify(raw) -> str | None:
    """متنِ خامِ «واحد» از کدال → 'mrl' | 'btl' | None.

    تشخیص با دو نشانۀ **هم‌زمان** انجام می‌شود (یکِ مقیاس + یکِ واحدِ پول)، تا
    «میلیارد» درِ متنِ آزادِ بی‌ربط تنهایی مقیاس نسازد. None یعنی «واحد گفته
    نشده یا شناخته‌شده نیست» — نه «میلیون ریال» و نه هیچِ حدسِ دیگر.
    """
    if raw is None:
        return None
    t = re.sub(r"\s+", "", str(raw or "").translate(_NORM))
    if not t:
        return None
    currency = ("ریال" in t) or ("تومان" in t)
    if "میلیارد" in t or "بيليون" in t or "بیلیون" in t:
        # فقط «میلیارد تومان» مقیاسِ شناخته‌شده است؛ «میلیارد ریال» امروز درِ
        # قرارداد توکن ندارد و عمداً بی‌واحد می‌ماند (بندِ 5 سرِ فایل).
        return "btl" if (("تومان" in t) and currency) else None
    if "میلیون" in t or "مليون" in t:
        # «میلیون ریال» مبناىِ همۀ صورتهایِ مالیِ کدال است؛ «میلیون تومان»
        # عمدی شناخته نمی‌شود (بندِ 5).
        return "mrl" if "ریال" in t else None
    return None


# همان مقادیرِ معتبر درِ SQL. `unit_norm` فقط از `classify()` می‌آید، پس membership
# دقیقاً نقیضِ «بی‌واحد» است و بحثِ LIKE/ترجمۀ متن درِ خوانده لازم نیست.
UNIT_TOKENS = "'mrl','btl'"


def _col(alias=None) -> str:
    return f"{alias}.unit_norm" if alias else "unit_norm"


def present_sql(alias=None) -> str:
    """شرطِ «این ردیف واحدش معلوم است» درِ SQL — قرینۀ `is_valid`."""
    return f"({_col(alias)} IN ({UNIT_TOKENS}))"


def missing_sql(alias=None) -> str:
    """شرطِ «این ردیف بی‌واحد است» — نقیضِ `present_sql`، نه تعریفِ دوم."""
    return f"({_col(alias)} IS NULL OR {_col(alias)} NOT IN ({UNIT_TOKENS}))"


PRESENT_SQL = present_sql()
MISSING_SQL = missing_sql()


def is_valid(unit_norm) -> bool:
    """آیا این `unit_norm` یکِ مقیاسِ شناخته‌شده است (شرطِ خواندنِ پایتون)."""
    return unit_norm in SCALES


def is_missing(unit_norm) -> bool:
    """تعریفِ یگانۀ «ردیفِ بی‌واحد» — نقیضِ `PRESENT_SQL`."""
    return not is_valid(unit_norm)


def scale(unit_norm) -> float | None:
    """چند ریال در هر یکِ عددِ ذخیره‌شده؛ بی‌واحد → None (هیچ ضریبی حدس نمی‌شود)."""
    return SCALES.get(unit_norm) if is_valid(unit_norm) else None


def to_rial(value, unit_norm) -> float | None:
    """عددِ ذخیره‌شده ← ریال. بی‌واحد → None. مقدارِ None هم → None (نه صفر)."""
    s = scale(unit_norm)
    if s is None or value is None:
        return None
    try:
        return float(value) * s
    except (TypeError, ValueError):
        return None


def to_btom(value, unit_norm) -> float | None:
    """عددِ ذخیره‌شده ← میلیارد تومان (واحدِ نمایشِ جزوه). بی‌واحد → None."""
    rial = to_rial(value, unit_norm)
    return None if rial is None else rial / RIAL_PER_BTM


def to_mrl(value, unit_norm) -> float | None:
    """هر مقیاسِ شناخته‌شده ← مبناىِ داخلیِ موتور (میلیون ریال). بی‌واحد → None.

    تنها جایی است که مقیاس عوض می‌شود. یکِ «میلیارد تومان» = 1e10 ریال = 1e4
    میلیون ریال، پس ضریبش 1e4 است؛ اگر روزی مقیاسِ تازه‌ای به `SCALES` افزود،
    همین‌جا کافی است و هیچِ مصرف‌کننده‌ای نباید دوباره ضریب بنویسد.
    """
    s = scale(unit_norm)
    if s is None or value is None:
        return None
    try:
        return float(value) * s / SCALES["mrl"]
    except (TypeError, ValueError):
        return None


_LABEL = {"mrl": "میلیون ریال", "btl": "میلیارد تومان"}


def label(unit_norm) -> str:
    """نامِ خوانایِ واحد برایِ اعلام درِ رابط (بی‌واحد → «واحد نامعلوم»)."""
    return _LABEL.get(unit_norm, "واحد نامعلوم")


def provenance(unit, unit_norm) -> str:
    """واحدِ این ردیف از کدامِ منبع آمده: 'notice' | 'sheet' | 'none'.

    'sheet' حالتی است که `unit` خامِ نامه خالی است ولی واکشیِ عمیق واحد را از
    خودِ شیتِ گزارش خوانده — نقصِ داده نیست، کمبودِ ستونِ منبع است. بدونِ این
    تفکیک، شمارشِ خامِ `unit IS NULL` این ردیف‌ها را «بی‌شاهد» نشان می‌داد در
    حالی که رأی‌شان شاهد دارد.
    """
    if is_valid(unit_norm):
        return "notice" if (unit is not None and str(unit).strip()) else "sheet"
    return "none"


_TABLES = ("financial_statements",)


def tables(conn) -> tuple:
    """جدول‌هایی که این قرارداد بر پولِ آن‌ها حاکم است (فقطِ موجودها).

    `monthly_sales` عمداً نیست: ستونِ واحدِ پول ندارد و ادعایِ اثبات نمی‌کند
    (docstring سرِ فایل، بندِ «محدودیت‌ها»).
    """
    have = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    return tuple(t for t in _TABLES if t in have)


def unit_counts(conn) -> dict:
    """**تنها** شمارشِ «ردیف‌های بی‌واحد». هر consumer (پنل، اسکرینر، ممیزی،
    گارد) همین را گزارش می‌کند؛ کوئریِ دوم نوشته نمی‌شود.

    برمی‌گرداند: {'financial_statements': n, 'symbols_financial_statements': n,
                 'total': n}
    """
    out = {}
    total = 0
    for t in tables(conn):
        n, syms = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT symbol) FROM %s WHERE %s"
            % (t, MISSING_SQL)).fetchone()
        out[t] = n
        out["symbols_" + t] = syms
        total += n
    out["total"] = total
    return out
