"""codal_periods.py — تنها تعریفِ «دورۀ گزارش» درِ کلِ پروژه.

چرا این فایل متولد شد (کارِ بنیادی، ۱۴۰۵-۰۷-۱۰). قاعدۀ «این ردیف دوره دارد یا
نه» و «کلیدِ دوره چیست» پنج جا مستقل نوشته شده بود:

  • `codal_fetcher._pe_key`        → ترجمۀ رقم + یکسان‌سازیِ جداکننده
  • `_parse_year_month` / `_ym_from_title` / `_period_from_title` → سه regex جدا
    برایِ استخراجِ یکِ تاریخ از دو منبع
  • `fs_derived` (fiscal_year)     → `pe[:4].isdigit()` (تفسیرِ سوم)
  • `dev/db_housekeeping.py:316`، `dev/db_final_report.py:279`،
    `dev/codal_logic_guard.py:81` → هر کدام `period_end IS NOT NULL`ِ خودش
  • `fts_engine` و `api/fundamental.py` (چهار کوئری) → `ORDER BY period_end DESC`؛
    «بی‌دوره» فقط به‌یاریِ ترتیبِ NULL در SQLite آخر می‌افتاد، نه به‌عنوانِ قاعده

نتیجه‌اش این بود که «چند ردیف بی‌دوره داریم» سه جوابِ مختلف داشت.

قاعده (همین فایل، بی‌هیچ استثنای دوم):
  ۱) شکلِ canonicalِ یکِ دوره `'YYYY/MM/DD'` است (ارقامِ لاتین، جداکننده «/»).
     هر چیزِ دیگر — از جمله خط تیره، رقمِ فارسی، رشتهٔ خالی، NULL و برچسبِ
     «۱۴۰۴/۰۹/۲۳ ۱۸:۱۰:۳۰» — **بی‌دوره** است.
  ۲) مسیرِ نوشتن از `canonicalize()` می‌گذرد، پس هر چیزی که درِ ستون می‌نشیند
     از پیش canonical است؛ به همان دلیلِ شرطِ خواندن (`VALID_GLOB`) و شرطِ
     پایتون (`is_undated`) یک معنا دارند — این هم‌سنجی خودِ شرط‌ها درِ
     `dev/codal_period_canonical_v1075.py` سنجیده می‌شود، نه با فرض.
  ۳) دو منبعِ دوره هست و ترتیبشان قرارداد است: اول `periodEndToDate` خودِ
     datasource کدال (معتبرترین)، سپس تاریخِ داخلِ عنوانِ نامه
     («… منتهی به ۱۴۰۴/۱۲/۲۹ …»). `derive()` همان زنجیر است و می‌گویدWhich
     منبع جواب داده.
  ۴) ردیفی که هیچ‌کدام را ندارد **بی‌دوره** است: معتبر می‌ماند و حذف نمی‌شود
     (داده‌اش ممکن است درِ جای دیگری به کار آید)، ولی هرگز «آخرین دورۀ نماد»
     حساب نمی‌شود. شمارششان فقط از `undated_counts()` خوانده می‌شود.

stdlib-only است تا هیچ چرخۀ import نسازد (الگو: `price_basis.py`،
`candle_contract.py`). چون سطح-بال import می‌شود و درِ `api/` هم لازمش دارد،
درِ `fts_terminal.spec` → `hiddenimports` صریح فهرست شده است.
"""
from __future__ import annotations

import re

__all__ = [
    "CANON_RE", "VALID_GLOB", "DATED_SQL", "UNDATED_SQL", "dated_sql", "undated_sql",
    "latest_order_sql", "order_expr",
    "canonicalize", "from_title", "derive", "is_canonical", "is_undated",
    "ym", "fiscal_year", "desc_sort_key", "latest",
    "undated_counts", "tables",
]

# ── شکلِ canonical ──────────────────────────────────────────────────────────
# `[0-9]` و نه `\d`: درِ پایتون `\d` رقمِ فارسی/عربی را هم می‌پذیرد، ولی GLOBِ
# SQLite ارقامِ ASCII را. با `\d` شرطِ پایتون «۱۴۰۴/۱۲/۲۹» را canonical می‌شمرد و
# شرطِ SQL بی‌دوره — یعنی همان چیزی که این ماژول قرار بود از بین ببرد.
# (گاردِ dev/codal_period_canonical_v1075.py همین را درِ اجرا گرفت.)
CANON_RE = re.compile(r"^([0-9]{4})/([0-9]{2})/([0-9]{2})$")

# همان شرط درِ SQL. الگو فقط رقم و «/» دارد، پس بحثِ بزرگ/کوچکِ حرف‌ها معنا ندارد
# و دقیقاً همان «شکلِ canonical» است که `CANON_RE` می‌سنجد — با این فرق که تقویم
# را بررسی نمی‌کند (بندِ ۲ بالا و گاردِ v1075).
VALID_GLOB = "GLOB '[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]'"


def _col(alias=None) -> str:
    return f"{alias}.period_end" if alias else "period_end"


def dated_sql(alias=None) -> str:
    """شرطِ «این ردیف دوره دارد» درِ SQL — با نامِ مستعارِ اختیاریِ جدول."""
    c = _col(alias)
    return f"({c} IS NOT NULL AND trim({c}) {VALID_GLOB})"


def undated_sql(alias=None) -> str:
    """شرطِ «این ردیف بی‌دوره است» — نقیضِ `dated_sql`، نه تعریفِ دوم."""
    c = _col(alias)
    return f"({c} IS NULL OR trim({c}) NOT {VALID_GLOB})"


DATED_SQL = dated_sql()
UNDATED_SQL = undated_sql()


def order_expr(alias=None) -> str:
    """عبارتِ ترتیبِ «تازۀترین دورۀ اول، بی‌دوره آخر» — **بی‌کلیدواژهٔ ORDER BY**،
    تا درِ ترتیب‌هایِ مرکّب (`ORDER BY symbol, …`) هم قابلِ استفاده باشد."""
    return f"CASE WHEN {dated_sql(alias)} THEN 0 ELSE 1 END, {_col(alias)} DESC"


def latest_order_sql(alias=None) -> str:
    """همان `order_expr` با پیشوندِ ORDER BY، برایِ کوئری‌هایِ «آخرین» ساده.

    چرا نه `WHERE dated_sql()`: کوئری‌هایِ «آخرین نامِ شرکت / آخرین صورتِ مالی»
    نباید نمادی را که فقط ردیفِ بی‌دوره دارد بی‌جواب بگذارند؛ بی‌دوره بازندهٔ
    ترتیب است، نه حذف‌شده. (ترتیبِ خامِ `ORDER BY period_end DESC` این را به
    SQLite واگذار می‌کرد: NULL تصادفاً آخر می‌افتاد. حالا قاعده صریح است.)"""
    return "ORDER BY " + order_expr(alias)

_TABLES = ("financial_statements", "monthly_sales")

# رقمِ فارسی (U+06F0..) و عربی (U+0660..) → لاتین
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# «۱۴۰۵/۰۶/۳۱»، «1405-6-31»، «۱۴۰۵-۰۶-۳۱»، «1405/06/31 18:10:30»
# lookaround: «1405/02/301» تاریخ نیست؛ بی‌`(?!\d)` از دلش 1405/02/30 درمی‌آمد.
_LOOSE = re.compile(r"(?<!\d)(\d{4})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{1,2})(?!\d)")


def canonicalize(raw) -> str | None:
    """هر نمونۀ تاریخِ خام → `'YYYY/MM/DD'` یا None (هیچ چیزی حدس زده نمی‌شود).

    ماه/روزِ تک‌رقمی دورقامی می‌شود تا ترتیبِ واژگانیِ همین رشته (= ترتیبِ زمانی،
    که هر چهار کوئریِ «آخرین دوره» به آن تکیه کرده‌اند) درست بماند.

    سمتِ نوشتن **سخت‌گیرانه‌تر** از سمتِ خواندن است: اینجا ماه ۱..۱۲ و روز ۱..۳۱
    هم سنجیده می‌شود، پس «۱۴۰۵/۱۳/۴۵» هرگز درِ ستون نمی‌نشیند و بی‌دوره می‌ماند.
    شرطِ خواندن (`is_undated` / `UNDATED_SQL`) فقط شکل را می‌بیند، چون باید درِ
    SQL هم قابلِ بیان باشد؛ همان‌جا که دو شرط ممکن است جدا شوند یکِ ردیفِ
    بی‌اعتبار است، و گاردِ `dev/codal_period_canonical_v1075.py` ثابت می‌کند رویِ
    دادهٔ واقعی این دو هم‌معنا هستند (هیچ ردیفِ «شکل‌درست ولی تقویم‌غلط» نیست).
    """
    if raw is None:
        return None
    s = str(raw).translate(_DIGITS)
    m = _LOOSE.search(s)
    if not m:
        return None
    y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
    if not 1 <= mo <= 12 or not 1 <= d <= 31:
        return None
    return f"{y}/{mo:02d}/{d:02d}"


# «… منتهی به ۱۴۰۴/۱۲/۲۹ …» — برایِ ردیف‌هایی که datasourceِ کدال دوره نداشت
# (هر ۶۷ ردیفِ بی‌دورۀ بانکِ کاری امروز از همین‌جا دوره می‌گیرند). یکِ regex، که
# هر سه مسیرِ repair/backfill/feed از آن می‌خوانند.
_END_ANCHOR = re.compile(r"منتهی\s*به")


def from_title(title) -> str | None:
    """دورۀ داخلِ عنوانِ نامه، در شکلِ canonical؛ یا None.

    اگر «منتهی به» هست، تاریخِ **بعد از آن** خوانده می‌شود: عنوان‌هایی که دو
    تاریخ دارند (بازگشایی/مجمع: «… از ۱۴۰۳/۰۱/۰۱ تا …») نباید شروعِ بازه را به‌جای
    پایانِ دوره بدهند."""
    s = str(title or "")
    m = _END_ANCHOR.search(s)
    if m:
        s = s[m.end():]
    return canonicalize(s)


def derive(datasource_end=None, title=None):
    """زنجیرۀ قرارداد: اول datasource، در نبودش عنوان. `(period, source)` می‌دهد.

    source ∈ {'datasource', 'title', None} — برایِ این‌که درِ گزارش/دفتر معلوم
    باشد دوره از کدامِ منبع آمده، نه این‌که فقط یکِ رشته باشد."""
    pe = canonicalize(datasource_end)
    if pe:
        return pe, "datasource"
    pe = canonicalize(title)
    if pe:
        return pe, "title"
    return None, None


def is_canonical(value) -> bool:
    """آیا این مقدار همان شکلِ canonical است (شرطِ خواندنِ دقیقِ بندِ ۱)."""
    return value is not None and CANON_RE.match(str(value).strip()) is not None


def is_undated(value) -> bool:
    """تعریفِ یگانۀ «ردیفِ بی‌دوره» — نقیضِ `DATED_SQL`."""
    return not is_canonical(value)


def ym(period):
    """(year, month) از یکِ دورۀ canonical؛ بی‌دوره → (None, None)."""
    pe = canonicalize(period)
    if not pe:
        return None, None
    parts = pe.split("/")
    return int(parts[0]), int(parts[1])


def fiscal_year(period) -> str | None:
    """سالِ مالیِ دوره ('۱۴۰۴' لاتین) یا None. جایِ `pe[:4].isdigit()` درِ fs_derived."""
    pe = canonicalize(period)
    return pe[:4] if pe else None


def desc_sort_key(period) -> str:
    """کلیدِ `sorted(items, key=desc_sort_key, reverse=True)` و مقایسۀ «برنده»:
    تازۀترین اول، و **هر چیزی که canonical نیست آخر** — چون رشتهٔ خالی از هر
    تاریخِ کوچک‌تر است.

    شکلِ canonical پهنایثابت (`YYYY/MM/DD`) است، پس ترتیبِ واژگانی = ترتیبِ
    زمانی. (کلیدِ `str(pe or "")` که پیش از این درِ `fts_engine` بود همین را
    می‌خواست، ولی «۱۴۰۵/۰۶/۳۱»ِ فارسی را جلویِ تاریخِ لاتین می‌گذاشت.)"""
    return canonicalize(period) or ""


def latest(periods):
    """تازۀ‌ترین دورۀ canonical از یکِ فهرست؛ اگر همه بی‌دوره بودند None."""
    vals = [p for p in (canonicalize(x) for x in periods) if p]
    return max(vals) if vals else None


def tables(conn) -> tuple:
    """جدول‌هایِ مشتقِ کدال که همین قرارداد بر آن‌ها حاکم است (فقطِ موجودها)."""
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return tuple(t for t in _TABLES if t in have)


def undated_counts(conn) -> dict:
    """**تنها** شمارشِ «ردیف‌هایِ واقعاً بی‌دوره». هر consumer (پنل، اسکرینر،
    housekeeping، pipeline، ممیزی، گارد) همین را گزارش می‌کند؛ کوئریِ دوم
    نوشته نمی‌شود.

    برمی‌گرداند: {'financial_statements': n, 'monthly_sales': n, 'total': n}
    """
    out = {}
    total = 0
    for t in tables(conn):
        n = conn.execute(
            f"SELECT COUNT(*) FROM {t} WHERE {UNDATED_SQL}").fetchone()[0]
        out[t] = n
        total += n
    out["total"] = total
    return out
