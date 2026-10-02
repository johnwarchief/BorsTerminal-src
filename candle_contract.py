# -*- coding: utf-8 -*-
"""candle_contract.py — یکِ هندسه، یکِ مالکیتِ سطر، یکِ شکلِ خروجی برایِ همهٔ سازنده‌هایِ کندل.

قرارداد: docs/CANDLE-CONTRACT.md §۱-ث (مبنایِ قیمت) و §۱-ج (open = FIRST). موجودیِ
واگرایی: docs/RAHAVARD-PARITY-INVENTORY.md §۲-الف و §۳، و اندازه‌گیریِ این قدم درِ
`_audit/candle_builder_divergence.py` + `_audit/candle_source_priority_probe.py` +
`_audit/legacy_open_basis.json`.

سه چیز که فقط درِ این فایل تعریف می‌شوند:

۱) `widen()` — تنها قاعدۀ هندسه. پیش از این سه پیادۀ هم‌سان و یک پیادۀ **مخالف** داشت
   (clampِ open درِ `api/market_index.py`). قاعده: سایه گِشاد می‌شود؛ بدنه و پایانی هرگز
   خُرد نمی‌شوند. دلیلش درِ کامنتِ v8.7 FIX-1b هست: خودِ TSETMC درِ درصدِ قابلِ توجهی از
   ردیف‌هایِ تاریخی H/L را بیرونِ بدنه منتشر می‌کند (فولاد ۲۰۰-۱۲-۲۲: H=L=۱۹۷۳ در برابر
   C=۱۹۱۷)، و پایانی به پایهٔ روزِ بعد زنجیر می‌شود ⇒ عددِ قیمت معتبر است و نقص درِ
   سایه است. کمینهٔ صفر («هنوز پر نشده») هم با بدنه عوض می‌شود، نه با صفر.

۲) `src` — مالکیتِ سطر. پنج نویسندۀ `price_history` داشتیم و هیچ تستی ترتیب را نگه
   نمی‌داشت؛ نتیجه‌اندازه‌گیری‌شده: ۴۷۰ از ۱٬۲۷۲ ردیف (۳۷٪) open‌شان «قیمتِ پایه» است نه
   «اولین» — نه به‌خاطرِ کدِ غلطِ امروز، به‌خاطرِ اینکه مشخص نیست کدامِ نویسندۀ آخر نوشت؛
   و ۴ نشست از ۷۲ نشستِ مشترک، snapshotِ میانۀ تابلو را رویِ ردیفِ **منتشرشده** نشانده‌اند.
   قاعده: `published` (فهرستِ روزانۀ منتشرشدهٔ TSETMC) بالاترین اولویت است؛ `board`
   (اسنپشاتِ زندهٔ تابلو) هرگز ردیفِ منتشرشده را بازنویسی نمی‌کند.

۳) `from_*_row()` — یکِ شکلِ خروجی: `time, open, high, low, close, last, value, volume`
   با `close` = قیمتِ پایانی (لنگر) و `last` = آخرینِ خام یا None. هیچ سازنده‌ای حقِ
   ساختنِ شکلِ خودش را ندارد؛ `price_basis` بعداً همین شکل را می‌خواند.
"""
from __future__ import annotations

# ---- سرچشمه‌ها (rank: بالاتر، برندهٔ نوشتنِ سطر) ----
SRC_PUBLISHED = "published"    # GetClosingPriceDailyListCSV / GetInstrmentsHistoryInDay
SRC_BOARD = "board"            # GetMarketWatch → daily_prices (اسنپشاتِ نشستِ جاری)
SRC_INDEX = "index-synthetic"  # کندلِ ساختگیِ شاخص کل (open از closeِ دیروز)
RANK = {None: 0, "": 0, SRC_BOARD: 1, SRC_INDEX: 1, SRC_PUBLISHED: 2}


def rank(src):
    return RANK.get(src or "", 0)


# ---- SQLِ نوشتن با مالکیتِ سطر ----
CANDLE_COLUMNS = ("symbol", "date", "open", "high", "low", "close", "volume",
                  "last", "value", "src")

UPSERT_SQL = (
    "INSERT INTO price_history (" + ", ".join(CANDLE_COLUMNS) + ") "
    "VALUES (" + ",".join("?" * len(CANDLE_COLUMNS)) + ") "
    "ON CONFLICT(symbol, date) DO UPDATE SET "
    + ", ".join("%s = excluded.%s" % (c, c) for c in CANDLE_COLUMNS[2:])
    + " WHERE COALESCE(price_history.src, '') <> ? OR excluded.src = ?"
)
# دو ؟ آخر همان SRC_PUBLISHED است: «اگر ردیفِ فعلی منتشرشده است، فقط یکِ منتشرشدهٔ دیگر
# جایش را می‌گیرد». نشانگرِ نام‌دار (?11) عمداً استفاده نشده — bindings ترتیبیِ
# sqlite3 پایتون با آن درهم می‌شود، پس مقدار دو بار درِ tuple می‌رود و یکسان بودنش
# درِ گارد آزموده می‌شود.


def upsert_row(candle):
    """دیکشنریِ کندل → tupleِ متناظرِ UPSERT_SQL (به‌همراه قیدِ اولویت)."""
    return (candle["symbol"], candle["time"] or candle.get("date"),
            candle["open"], candle["high"], candle["low"], candle["close"],
            candle.get("volume"), candle.get("last"), candle.get("value"),
            candle.get("src") or SRC_BOARD, SRC_PUBLISHED, SRC_PUBLISHED)


# ---- تنها قاعدۀ هندسه ----

def widen(open_, high, low, *prices):
    """(high, low) را گِشاد می‌کند تا بدنه و هر قیمتِ داده‌شده داخلِ سایه بنشینند.

    `high` فقط سقف را باز می‌کند و `low` فقط کف را — هیچ‌کدام برایِ طرفِ دیگر کاندید
    نیستند. چرا این ظرافت مهم است: ردیفِ معیوبِ «پالایش ۲۰۲۴-۱۰-۲۳» (O=۱۲۰۰، C=۱۱۵۰،
    H=۱۱۰۰، L=۰) اگر high را کاندیدِ کف بگیریم کفش ۱۱۰۰ می‌شود، یعنی یک عددِ معیوب
    جایِ عددِ معتبرِ بدنه را می‌گیرد؛ قاعدۀ درست «۱۱۵۰ = چیزی که می‌دانیم» است.
    صفر/None درِ high|low یعنی «منبع هنوز پر نکرده»، پس با بدنه ساخته می‌شود.

    هیچ ورودیِ دیگری را عوض نمی‌کند — به‌ویژه `close`/`last` را نه. دلیلِ کلِ قاعده درِ
    کامنتِ v8.7 FIX-1b هست: خودِ TSETMC درِ درصدِ قابلِ توجهی از ردیف‌ها H/L را بیرونِ
    بدنه منتشر می‌کند و پایانی به پایهٔ روزِ بعد زنجیر می‌شود ⇒ قیمت معتبر است، سایه نقص.
    """
    body = [v for v in (open_,) + tuple(prices) if v]
    if not body:
        return high, low
    hi = max([high] + body) if high else max(body)
    lo = min([low] + body) if low else min(body)
    return hi, lo


# ---- سازنده‌هایِ ورودی (همه به یکِ شکل) ----

def candle(symbol, date, o, h, l, c, volume=None, last=None, value=None, src=SRC_PUBLISHED):
    """یکِ کندلِ استاندارد: هندسه از `widen`، مبنایِ خامِ دوگانه، بی‌ساختنِ عدد."""
    if not symbol or not date:
        return None
    try:
        c = float(c or 0)
        o = float(o or 0) or c
        h = float(h or 0)
        l = float(l or 0)
        v = float(volume or 0)
        ls = float(last) if last else None
        val = float(value) if value else None
    except (TypeError, ValueError):
        return None
    if c <= 0 or o <= 0:
        return None
    if v <= 0:
        # روزِ بی‌معامله کندل نمی‌شود — پیش از بازگشایی تابلو ردیفِ «امروز» را با
        # قیمتِ پایه و حجمِ صفر می‌فرستد (شاهد: کندلِ شبحِ فولاد ۱۴۰۵-۰۷-۰۸).
        return None
    h, l = widen(o, h, l, c, ls)
    return {"symbol": str(symbol), "time": date, "date": date, "open": o, "high": h,
            "low": l, "close": c, "last": ls, "value": val, "volume": v, "src": src}


def iso_from_csv(fields):
    """`DTYYYYMMDD` ردیفِ CSV → 'YYYY-MM-DD'؛ بی‌اعتبار ⇒ None.

    جدا شده تا سازنده‌ای که *پیش* از ساختنِ کندل می‌خواهد بداند این ردیف روزِ معتبر
    دارد یا نه (فیلترِ پنجره) همان قضاوتِ `from_csv_row` را بکند، نه تجزیۀ دوباره‌ای
    که ممکن است با آن فرق کند.
    """
    if len(fields) < 2:
        return None
    d = str(fields[1]).strip()
    if len(d) != 8 or not d.isdigit():
        return None
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def from_csv_row(symbol, fields, src=SRC_PUBLISHED):
    """ردیفِ `GetClosingPriceDailyListCSV` → کندل.

    نگاشتِ سنجیده‌شده (قرارداد §۱-ج الف، ۱۴٬۲۱۰/۱۴٬۷۰۶): open از `FIRST`، close از
    `CLOSE` (لنگر)، last از `LAST`، value از `VALUE`. `fields[10]` (= `OPEN`) قیمتِ پایه
    است و هیچ‌وقت open نمی‌شود.
    """
    if len(fields) < 12:
        return None
    d = str(fields[1]).strip()
    if len(d) != 8 or not d.isdigit():
        return None
    try:
        num = lambda i: float(fields[i]) if str(fields[i]).strip() else None  # noqa: E731
        first, hi, lo, close, value, vol, base, last = (num(2), num(3), num(4), num(5),
                                                        num(6), num(7), num(10), num(11))
    except (TypeError, ValueError):
        return None
    if not close:
        return None
    return candle(symbol, f"{d[:4]}-{d[4:6]}-{d[6:]}",
                  first if first else base, hi, lo, close, vol, last, value, src)


def from_board_row(symbol, d_even, first, high, low, closing, volume, last=None, value=None):
    """ردیفِ `daily_prices`/تابلو → کندل (src=board).

    تابلو «آخرینِ» خام دارد (`pdv` — سنجشِ ۶/۶ نماد درِ `_audit/mw_key_to_csv_column.json`)؛
    نبودش None می‌ماند، نه پایانی.
    """
    from test_tsetmc import _iso_from_deven  # محلی: چرخۀ import را نمی‌شکند
    date = _iso_from_deven(d_even)
    if not date:
        return None
    return candle(symbol, date, first, high, low, closing, volume, last, value, SRC_BOARD)


def from_db_row(row):
    """ردیفِ `price_history` (۱۰ ستونه) → کندلِ استاندارد.

    هندسه دوباره از همان `widen` می‌گذرد تا حتی ردیف‌هایِ کهنه (که با قاعدۀ دیگری
    نوشته شده‌اند) درِ خواندن هم همان کندلی بدهند که درِ نوشتن باید ساخته می‌شد.
    """
    src = row[9] if len(row) > 9 else None
    return candle(row[0], row[1], row[2], row[3], row[4], row[5], row[6],
                  row[7] if len(row) > 7 else None,
                  row[8] if len(row) > 8 else None,
                  src or SRC_PUBLISHED)


DB_COLUMNS = ("symbol", "date", "open", "high", "low", "close", "volume",
              "last", "value", "src")

SELECT_SQL = "SELECT " + ", ".join(DB_COLUMNS) + " FROM price_history"
