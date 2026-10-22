# -*- coding: utf-8 -*-
"""notifications.py — مرکزِ اطلاعِ رویدادهایِ بازار؛ تنها طبقه‌بندِ اطلاعیه‌ها.

بند ۶ مأموریت (رأیِ مالک 1405-07-20). منبع، همان چیزی است که خودِ برنامه
همین حالا واکشی و ذخیره می‌کند: جدولِ `codal_notices` (کدال، با `url`ِ
خودِ اطلاعیه، `publish_date`/`sent_date`/`fetched_at`). هیچ خبرِ تازه‌ای
از هیچ سرویسِ بیرونی اضافه نمی‌شود و هیچ تیترِ ساختگی درِ این لایه نیست —
بی‌ردیف یعنی «چیزی از کدال نرسیده».

طبقه‌بندیِ نوع از همان داورِ موجودِ برنامه می‌آید (`api/chart.py::_cal_classify`
که رویدادهایِ تقویم را دسته می‌زند)؛ پس «مجمع» درِ مرکزِ اعلان و درِ
تقویمِ چارت یک معنا دارند، نه دو تا.

معیارِ اهمیت — قابلِ توضیح، نه سلیقه‌ای: هر سطح به *مصرفِ خودِ عدد* درِ
برنامه گره می‌خورد، نه به هیجانِ واژه:

    بالا    = چیزی را درِ داوری یا قابلیتِ معامله عوض می‌کند:
              صورتهایِ مالی (ورودیِ EPS/حاشیه/رشدِ پنج‌شاخصه)، مجمع
              (وتویِ زمان‌بندیِ ورود درِ قیف)، افزایشِ سرمایه و تقسیمِ سود
              (مبنایِ سهم و قیمت)، عرضهٔ اولیه، سررسیدِ اوراق.
    متوسط   = ورودیِ یکی از محورهایِ FTS است ولی حکمِ فوری را نمی‌شکند:
              گزارشِ فعالیتِ ماهانه (مبنایِ رشدِ فروشِ ۱۲ماهه).
    پایین   = افشایِ عمومیِ بی‌ربط به پنج محور.
    بی‌طبقه = عنوانی که هیچ‌کدام از داورهایِ بالا آن را نشناخت؛ این
              «پایین» نیست، «نشناخته» است و درِ رابط جدا خوانده می‌شود.

حذفِ تکراری: کلیدِ یکتایِ خودِ کدال (`tracing_no`) و یک کلیدِ ادغام
(نماد + عنوانِ نرمال‌شده + تاریخِ انتشار) برایِ ردیف‌هایِ هم‌متنِ دو
واکشیِ متوالی. ادغام یعنی «یکی نشان بده، بشمار که چند بار آمد»، نه حذفِ بی‌صدا.
"""
from __future__ import annotations

import re
import threading
import time

import codal_periods as CP

SOURCE = "codal"
SOURCE_LABEL = "کدال (سازمانِ بورس)"

LEVEL_HIGH, LEVEL_MED, LEVEL_LOW, LEVEL_UNKNOWN = "high", "medium", "low", "unclassified"

LEVEL_LABEL = {LEVEL_HIGH: "بالا", LEVEL_MED: "متوسط", LEVEL_LOW: "پایین",
               LEVEL_UNKNOWN: "بی‌طبقه"}

# عنوان‌هایی که درِ همین برنامه مصرفِ داوری دارند. واژگان از خودِ کدال است
# (نمونۀِ زنده: «گزارش فعالیت ماهانه دوره … منتهی به …»، «اطلاعات و صورتهای
# مالی …»، «آگهی دعوت به مجمع…»). این فهرستِ ترتیب‌دار است: اولینِ تطبیق
# برنده است تا «گزارش فعالیت ماهانه(اصلاحیه)» دو بار شمرده نشود.
_KINDS = (
    ("statements", "صورتهایِ مالیِ دوره (ورودیِ EPS/حاشیه/رشدِ پنج‌شاخصه)", LEVEL_HIGH,
     r"صورته?ا?ی مالی|صورتهایِ مالی|صورت\u200cهای مالی|صورت\u200fمسئولیت"),
    # «مجمع» تنها وقتی مجمع است که دعوت/برگزاری/مورخِ جلسه بیاید؛ «تقسیم سود
    # نقدی مجمع» خبرِ سود است، نه دعوتِ جلسه — و آن باید سود خوانده شود.
    ("assembly", "مجمعِ عمومی (وتویِ زمان‌بندیِ ورود درِ قیف)", LEVEL_HIGH,
     r"آگهی دعوت|اعلانیه? دعوت|برگزاری مجمع|دعوت به مجمع|زمان\s*مجمع"),
    ("capital", "افزایشِ سرمایه (مبنایِ سهم و ارزشِ بازار)", LEVEL_HIGH,
     r"افزایش\s*سرمایه"),
    ("dividend", "تقسیمِ سود / سودِ نقدی (مبنایِ قیمت)", LEVEL_HIGH,
     r"تقسیم\s*سود|سود\s*نقدی|تقسیم\s*مبلغ"),
    ("ipo", "عرضهٔ اولیه / پذیرش", LEVEL_HIGH,
     r"عرضه\s*اولیه|پذیرش\s*نظر|پذیرش\s*شده"),
    ("maturity", "سررسیدِ اوراق/صکوک", LEVEL_HIGH,
     r"سررسید|اخزا|صکوک|اوراق"),
    ("monthly", "گزارشِ فعالیتِ ماهانه (مبنایِ رشدِ فروشِ ۱۲ماهه)", LEVEL_MED,
     r"گزارش\s*فعالیت|فعالیت\s*ماهانه"),
    ("production", "گزارشِ تولیدِ هفته/ماه (کمکیِ همان محورِ فروش)", LEVEL_MED,
     r"گزارش\s*تولید|تولید\s*ماهانه|تولید\s*هفتگی"),
    ("governance", "مدیریت/حاکمیت — افشا، خبری از پنج محور نیست", LEVEL_LOW,
     r"هیئت\s*مدیره|مدیر\s*عامل|سرمایه\s*گذار|انتشار|اصلاحیه|لغو|به\s*تعویق"),
)

# نرمال‌سازیِ عنوان برایِ کلیدِ ادغام: نیم‌فاصله/فاصله، ك/ي عربی، و ارقام
_NORM_ZWNJ = "\u200c"


def norm_title(title) -> str:
    t = str(title or "").replace(_NORM_ZWNJ, " ").replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def classify(title, letter_code=None) -> dict:
    """نوع + سطح + دلیلِ همان سطح. هیچ‌وقت «پایین» را جای «نشناخته» نمی‌گذارد."""
    t = str(title or "")
    for key, reason, level, pat in _KINDS:
        if re.search(pat, t, flags=re.IGNORECASE):
            return {"kind": key, "level": level, "reason": reason,
                    "letter_code": (str(letter_code).strip() or None) if letter_code else None}
    return {"kind": "other", "level": LEVEL_UNKNOWN,
            "reason": "هیچ‌کدام از داورهایِ موجودِ برنامه این عنوان را نشناخت؛ "
                      "این «کم‌اهمیت» نیست، «بی‌طبقه» است.",
            "letter_code": (str(letter_code).strip() or None) if letter_code else None}


def dedupe_key(row: dict) -> str:
    """کلیدِ ادغام: نماد + عنوانِ نرمال + تاریخِ انتشار (بدونِ ساعت)."""
    return "%s|%s|%s" % (str(row.get("symbol") or "").strip(),
                         norm_title(row.get("title")),
                         str(row.get("publish_date") or "")[:10])


_COLS = ("tracing_no, symbol, company_name, title, letter_code, publish_date,"
         " sent_date, url, fetched_at")


def feed(conn, since=None, levels=None, limit: int = 120) -> dict:
    """تازۀِ اطلاعیه‌ها از `codal_notices`، با نوع/اهمیتِ توضیح‌دادنی.

    `since` «YYYY/MM/DD HH:MM:SS»ِ جلالیِ خودِ کدال است (همان نوشتارِ ستون)؛
    بی‌آن، از تازه‌ترینِ ردیفِ بانک خوانده می‌شود. `levels` فیلترِ انتخابیِ
    کاربر است (بالا/متوسط/…)؛ تهی یعنی همه.
    """
    want = {str(x).strip() for x in (levels or []) if str(x).strip()}
    try:
        rows = conn.execute(
            ("SELECT %s FROM codal_notices ORDER BY " % _COLS) + CP.pub_order_expr()
            + " LIMIT ?",
            (max(1, min(int(limit or 120), 2000)) * 3,)).fetchall()
    except Exception as e:
        return {"status": "error", "source": SOURCE, "items": [],
                "message": "جدولِ اطلاعیه‌های کدال درِ این بانک نیست: %s" % e}
    items, seen, dropped = [], {}, 0
    for r in rows:
        row = dict(zip(_COLS.split(", "), r))
        pub = str(row.get("publish_date") or "")
        if since and pub and pub < str(since):
            continue
        k = dedupe_key(row)
        if k in seen:
            seen[k]["occurrences"] += 1
            dropped += 1
            continue
        cls = classify(row.get("title"), row.get("letter_code"))
        if want and cls["level"] not in want:
            continue
        item = {
            "id": row.get("tracing_no"),
            "symbol": str(row.get("symbol") or "").strip() or None,
            "company": str(row.get("company_name") or "").strip() or None,
            "title": str(row.get("title") or "").strip(),
            "publish_date": pub or None,
            "sent_date": str(row.get("sent_date") or "").strip() or None,
            "received_at": str(row.get("fetched_at") or "").strip() or None,
            "url": row.get("url"),
            "source": SOURCE,
            "occurrences": 1,
            **cls,
        }
        seen[k] = item
        items.append(item)
    kept = items[:max(1, int(limit or 120))]
    return {"status": "ok", "source": SOURCE, "count": len(kept),
            # «چرا کمتر از بانک است» باید خوانده شود: ادغامِ تکراری، فیلترِ
            # سطح، و سقفِ درخواست — سه علتِ جدا، نه یک عددِ مبهام.
            "scanned": len(rows), "merged_duplicates": dropped,
            "levels": sorted(want) if want else None,
            "since": since, "items": kept}


# ── کشِ «تازه‌ترین انتشار / آخرین واکشی» بر پایۀِ محتوایِ بانک ─────────────
# سنجشِ ۱۴۰۵-۰۷-۳۰ رویِ market.db: پنلِ سلامت ۳۴۳ms p50 داشت با بدنهٔ ۳۹۸
# بایت. علتش دو اسکنِ کاملِ codal_notices بود: MAX(fetched_at) ~۶۱ms (بی‌ایندکس)
# و MAX(canonical publish_date) ~۲۹۷ms (چند replace رویِ هر ردیف). درِ عوض
# COUNT(*) و MAX(publish_date) هر دو ایندکسی‌اند (~۰٫۱ms با هم).
# کلیدِ کش همین دو + هویتِ فایلِ بانک است: هر درج/جایگزینی معمولِ کدال
# (INSERT OR REPLACE با fetched_at تازه) count یا max را عوض می‌کند و کش
# همان لحظه باطل می‌شود. سقفِ ۱۲۰ثانیه‌ای هم برایِ ویرایشِ درجایِ نادر است،
# تا «تازه» هرگز بیش از دو دقیقه پشتِ یک تغییرِ نامرئی نماند. دو بانکِ متفاوت
# با محتوای یکسان هرگز یکی نمی‌شوند (هویتِ فایل در کلید است).
_SOURCES_CACHE = {"key": None, "at": 0.0, "newest": None, "fetched": None}
_SOURCES_LOCK = threading.Lock()
_SOURCES_TTL_S = 120.0


def _db_identity(conn) -> str:
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
        return str(row[2] or "") if row and len(row) > 2 else ""
    except Exception:
        return ""


def _sources_facts(conn, now=None):
    """(rows, newest_publish, last_fetch) با کشِ محتوا-کلید.

    برایِ بانکِ درحافظه/ناشناس کش نمی‌شود (هویتِ پایدار ندارد)؛ همان رفتارِ
    قبلی. برایِ بانکِ فایل، فقط وقتی کلید عوض شود دو مقدارِ گران دوباره
    محاسبه می‌شوند.
    """
    n, raw_max = conn.execute(
        "SELECT COUNT(*), MAX(publish_date) FROM codal_notices").fetchone()
    ident = _db_identity(conn)
    key = (ident, int(n or 0), str(raw_max or "")) if ident else None
    now = time.monotonic() if now is None else float(now)
    if key is not None:
        with _SOURCES_LOCK:
            ent = _SOURCES_CACHE
            if (ent["key"] == key and ent["newest"] is not None
                    and (now - ent["at"]) < _SOURCES_TTL_S):
                return int(n or 0), ent["newest"], ent["fetched"]
    newest = conn.execute(
        "SELECT MAX(" + CP.pub_canon_sql() + ") FROM codal_notices").fetchone()[0]
    fetched = conn.execute("SELECT MAX(fetched_at) FROM codal_notices").fetchone()[0]
    if key is not None:
        with _SOURCES_LOCK:
            _SOURCES_CACHE.update(key=key, at=now, newest=newest, fetched=fetched)
    return int(n or 0), newest, fetched


def invalidate_sources_cache() -> None:
    """برایِ آزمون/نویسندۀ درون‌فرایندی: کشِ پنلِ سلامت را خالی می‌کند."""
    with _SOURCES_LOCK:
        _SOURCES_CACHE.update(key=None, at=0.0, newest=None, fetched=None)


def sources(conn) -> dict:
    """سلامتِ خودِ منبع — «چیزی نیست» با «نرسیده» یکی نباید بماند."""
    out = []
    try:
        n, newest, fetched = _sources_facts(conn)
        out.append({"source": SOURCE, "label": SOURCE_LABEL, "rows": int(n or 0),
                    "newest_publish": newest, "last_fetch": fetched,
                    "state": "ok" if (n or 0) > 0 else "empty"})
    except Exception as e:
        out.append({"source": SOURCE, "label": SOURCE_LABEL, "rows": 0,
                    "state": "unavailable", "message": str(e)})
    return {"status": "ok", "sources": out,
            "note": "تک‌منبع: کدالِ خودِ سازمانِ بورس، همان واکشیِ که FTS هم "
                    "از آن تغذیه می‌کند. منبعِ بیرونیِ تازه اضافه نشده است."}
