#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/codal_discovery_v1101.py — گاردِ بندِ ۲: کشفِ خودکارِ اطلاعیهٔ تازهٔ کدال.

چرا این گارد جدا از `codal_pipeline_v1100.py` است: آن گارد «صف و checkpoint و
بازیابی» را می‌سنجد؛ این گارد دقیقاً همان ده بندی را می‌سنجد که مأموریت برایِ
*کشف* نوشته است — و چند بندش فقط با فیدِ ساختگیِ چندصفحه‌ای قابلِ اثبات‌اند:

  ۱) مسیرِ discovery تکمیل شده (همان `CF.discover_notices`، نه پیادۀ دوم)
  ۲) checkpoint پایدار است (تا کدامِ شناسۀ منبع موفق بررسی شده)
  ۳) به `MAX(publish_date)` خام تکیه نمی‌شود (ارقامِ فارسی/لاتین + ترتیبِ فید)
  ۴) انتشارِ تازه، اطلاعیهٔ دیررس و اصلاحیه جا نمی‌مانند
  ۵) دریافت افزایشی است (کل تاریخچه هر چرخه خوانده نمی‌شود)
  ۶) شناسۀ اطلاعیه و نشانهٔ اصلاحیه حفظ می‌شود
  ۷) تاریخِ انتشار با دورۀ مالی/تاریخِ مؤثر قاطی نمی‌شود
  ۸) دریافتِ مجدد رکورد یا مقدارِ مالیِ تکراری نمی‌سازد
  ۹) اطلاعیهٔ ناقص ثبت می‌شود و retry کنترل‌شده دارد
  ۱۰) خطای منبع checkpoint را جلو نمی‌برد (بازیابی از دست نمی‌رود)

همه بی‌شبکه: فید با `fetch`ِ تزریق‌شده ساخته می‌شود و **همان** کدِ تولید اجرا
می‌شود. بانکِ عملیاتی (`market.db`) هیچ‌وقت باز نمی‌شود — همه رویِ `:memory:`.

اجرا:  PYTHONIOENCODING=utf-8 python dev/codal_discovery_v1101.py
خروجی: هر بررسی یکِ خط PASS/FAIL + «N passed / M failed»؛ exit 0 یا 1
"""
from __future__ import annotations

import inspect
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import codal_fetcher as CF                    # noqa: E402
import codal_periods as CP                    # noqa: E402
import codal_pipeline as PL                   # noqa: E402
import fts_engine as FE                       # noqa: E402

PASS = FAIL = 0


def fa(n):
    """رقمِ فارسی از کدِ نقطه — رقمِ دست‌نویس درِ متنِ فارسی می‌دزدد (AGENTS.md)."""
    return "".join(chr(0x06F0 + int(d)) for d in str(n))


def jd(y, m, d):
    """تاریخِ شمسیِ فارسی: jd(1405,3,31) → «۱۴۰۵/۰۳/۳۱»."""
    return "%s/%s/%s" % (fa(y), fa(str(m).zfill(2)), fa(str(d).zfill(2)))


_DIG_FA = "".join(chr(0x06F0 + d) for d in range(10))


def day_is(s, y, m, d):
    """روزِ canonical: «YYYY?MM?DD». جداکننده را چشمی نمی‌سنجیم — همین ترمینال
    `/` را `-` نشان می‌دهد و یکِ expectationِ دست‌نویس رقمِ تاریخ را می‌بُرد."""
    return bool(re.fullmatch(r"%04d[/\-]%02d[/\-]%02d" % (y, m, d), str(s or "")))


def pdate(x):
    """متنِ ASCII (تاریخ/ساعت) ← ارقامِ فارسی؛ رقمِ دست‌نویس نمی‌شود."""
    return x.translate(str.maketrans("0123456789", _DIG_FA))


# عنوانها از نوشتارِ واقعیِ `financial_statements.title` هستند: سفیدِ
# `SAVE_USEFUL_ONLY` با الگوهایِ آموخته‌شده از همین نوشتارها کار می‌کند، پس
# فیکچرِ ساختگیِ بی‌ZWNJ درِ خودِ مسیرِ کشف رد می‌شود.
FS_TITLE = "صورت‌های مالی  سال مالی منتهی به " + jd(1405, 3, 31) + " (حسابرسی شده)"
FS_ANNUAL = "صورت‌های مالی  سال مالی منتهی به " + jd(1404, 12, 29) + " (حسابرسی شده)"
AMEND_TITLE = FS_ANNUAL + "(اصلاحیه)"
MS_TITLE = ("گزارش فعالیت ماهانه دوره " + fa(1) + " ماهه منتهی به " +
            jd(1405, 6, 31))
NOISE_TITLE = "اطلاعیه تغییر ساعات معاملات"


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("PASS %s" % what)
    else:
        FAIL += 1
        print("FAIL %s%s" % (what, ("   ← " + str(detail)) if detail else ""))


def fresh_db():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    CF.create_schema(c)
    CF.migrate_schema(c)
    c.execute("CREATE TABLE IF NOT EXISTS instruments (ins_code TEXT PRIMARY KEY,"
              " l_val18 TEXT, l_val30 TEXT, sector_name TEXT, paper_type INTEGER)")
    return c


def letter(tn, sym, title, pub="1405/07/24 10:00:00", pdf="uploads/a.pdf"):
    """یکِ «حرف» همان شکلی که `search.codal.ir` می‌دهد (همان ده کلیدِ مصرفی)."""
    return {"TracingNo": tn, "Symbol": sym, "CompanyName": sym, "Title": title,
            "LetterCode": "1", "PublishDateTime": pub, "SentDateTime": pub,
            "Url": "/L/Detail/%d" % tn, "PdfUrl": pdf, "ExcelUrl": ""}


class Feed:
    """فیدِ ساختگی: `{cat: [صفحه۱, صفحه۲, …]}`؛ `None` یعنی بن/قطعِ شبکه.

    صفحه‌ای که درِ فهرست نیست = پایانِ فید (آرایۀ خالی). `calls` شمارِ درخواست‌ها
    است — بندِ ۵ (افزایشی بودن) با همین شماری می‌شود، نه با حدس.
    """

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def __call__(self, session, page, query):
        cat = str(query.get("Category"))
        self.calls.append((cat, int(page), query.get("FromDate")))
        lst = self.pages.get(cat) or []
        i = int(page) - 1
        if i < len(lst):
            return lst[i]
        return []


def n_notice(c):
    return int(c.execute("SELECT COUNT(*) FROM codal_notices").fetchone()[0])


def state_of(c, tn):
    r = c.execute("SELECT state, attempts, error_kind, last_error,"
                  " next_attempt_at FROM codal_extracted WHERE tracing_no=?",
                  (int(tn),)).fetchone()
    return dict(r) if r else None


def fs_scrape(n):
    """scraperِ فیکِ صورتِ مالی — همان FS_KEYS/`fs_derived`ِ خطِ تولید."""
    vals = {k: None for k in CF.FS_KEYS}
    vals.update({"revenue": 1000.0, "gross_profit": 400.0, "net_profit": 200.0,
                 "basic_eps": 50.0})
    pe, _src = CP.derive(None, n[3])
    unit = "کليه" + " مبالغ به ميليون ريال است"
    row = ((n[0], n[1], n[2], n[3], "Financial Statements", 12, pe, n[5])
           + tuple(vals.get(k) for k in CF.FS_KEYS)
           + (unit, n[7], PL.now_s()) + CF.fs_derived(n[3], pe, unit, 0))
    return "fs", row, "ok"


def main() -> int:
    # ── ۱) یکِ اطلاعیهٔ تازه کشف می‌شود: فید ← codal_notices ← صف ──────────
    c = fresh_db()
    feed = Feed({"1": [[letter(2001, "فولاد", FS_TITLE)],
                       [letter(2002, "خودرو", MS_TITLE, pub="1405/07/23 09:00:00")]],
                 "3": [[]]})
    res = PL.discover_auto(c, fetch=feed)
    ck(res["found"] == 2 and res["new"] == 2, "دو حرفِ فید دو ردیفِ اطلاعیه می‌شوند", res)
    ck(sorted(res["items"]) == [(2001, "fs"), (2002, "ms")],
       "طبقه‌بندیِ کار با خودِ kind_of انجام می‌شود (fs و ms جدا)", res["items"])
    ck(res["enqueued"] == 2 and PL.counts(c)["queued"] == 2,
       "کارهایِ کشف‌شده درِ صفِ queued می‌نشینند (نه «پردازش‌شده»)", PL.counts(c))
    r = c.execute("SELECT symbol, title, url, pdf_url, publish_date FROM codal_notices"
                  " WHERE tracing_no=2001").fetchone()
    ck(r["symbol"] == "فولاد" and r["url"].startswith("https://codal.ir/L/Detail/2001"),
       "شناسۀ اطلاعیه + پیوندِ کامل حفظ می‌شود", tuple(r))
    ck(r["pdf_url"] == "https://codal.ir/uploads/a.pdf",
       "پیوندِ PDF نسبی → مطلق (بندِ ۲-۶: نسخه‌ها دست‌نخورده بمانند)", r["pdf_url"])

    # ── ۲) checkpoint پایدار: «تا کدامِ شناسه موفقاً بررسی شد» ──────────────
    wm = PL.watermarks(c)
    ck(wm.get("1") == 2001 and wm.get("3") == 0,
       "نشانکِ هر دسته جدا ثبت می‌شود (مقدارش = کوچک‌ترین شمارۀ صفحۀ کامل‌خوانده‌شده)", wm)
    stored = c.execute("SELECT value, previous, updated_at, note FROM pipeline_cursor"
                       " WHERE key='notice_scan_tn_cat1'").fetchone()
    ck(stored is not None and stored["value"] == "2001" and stored["previous"] is None,
       "checkpoint درِ pipeline_cursor است با previous و زمان (قابلِ ردیابی)",
       tuple(stored) if stored else None)
    vnew = c.execute("SELECT value FROM pipeline_cursor WHERE key=?",
                    ("notice_newest_date",)).fetchone()[0]
    ck(day_is(vnew, 1405, 7, 24),
       "تاریخِ canonicalِ دیدہ‌شده جدا از نشانکِ شناسه نگه داشته می‌شود", vnew)
    ck(ord(str(vnew)[4]) == 0x2F,
       "جداکنندۀ canonical درِ codal_periods اسلش است (۰x2f) — چشمی قابلِ اعتماد نیست",
       hex(ord(str(vnew)[4])))

    # ── ۳) تکیه بر MAX(publish_date) خام حذف شده (هم فارسی هم لاتین) ───────
    src = inspect.getsource(CF.discover_notices)
    src_code = src.split('"""', 2)[2]           # بدونِ docstring، فقط بدنه
    ck("newest_publish_date" not in src_code and "MAX(publish_date)" not in src_code,
       "دریبِ کشف هیچ‌جای MAX(publish_date) خام نمی‌خواند (بندِ ۲-۳)",
       [l for l in src_code.splitlines() if "MAX(" in l][:2])
    feed2 = Feed({"1": [[letter(3001, "شپنا", FS_TITLE,
                                pub=pdate("1405/07/24 10:00:00")),
                         letter(3002, "وسپهر", FS_TITLE,
                                pub="2026-10-13 08:00:00")]],
                  "3": [[]]})
    c2 = fresh_db()
    res2 = PL.discover_auto(c2, fetch=feed2)
    d1 = CP.pub_date_only(c2.execute("SELECT publish_date FROM codal_notices"
                                     " WHERE tracing_no=3001").fetchone()[0])
    d2 = CP.pub_date_only(c2.execute("SELECT publish_date FROM codal_notices"
                                     " WHERE tracing_no=3002").fetchone()[0])
    ck(d1 == "1405/07/24" and d2 == "2026/10/13",
       "ارقامِ فارسی و ASCII هر دو به canonicalِ قابلِ مقایسه می‌رسند", (d1, d2))
    ck(res2["newest"] == max(d1, d2),
       "newest با خودِ CP.pub_date_only ساخته می‌شود، نه با MAXِ رشته‌ای", res2["newest"])

    # ── ۴) اطلاعیهٔ دیررس و اصلاحیه جا نمی‌مانند ────────────────────────────
    # دیررس: شمارۀ بزرگتر (چیزی که «بعد» درج شده) ولی تاریخِ انتشارِ قدیمی‌تر.
    feed3 = Feed({"1": [[letter(4001, "فولاد", FS_TITLE, pub="1405/01/05 08:00:00")]],
                  "3": [[]]})
    res3 = PL.discover_auto(c2, fetch=feed3)
    ck(res3["new"] == 1 and res3["enqueued"] == 1,
       "اطلاعیهٔ دیررس (تاریخِ قدیمی، شمارۀ تازه) کشف و صف می‌شود", res3)
    ck(PL.watermarks(c2)["1"] == 4001,
       "نشانک بر اساسِ شناسۀ منبع جلو می‌رود، نه بر اساسِ تاریخِ انتشار",
       PL.watermarks(c2))
    # اصلاحیه: دو اطلاعیهٔ هم‌دوره با شناسهٔ متفاوت، نشانهٔ اصلاحیه حفظ می‌شود
    feed4 = Feed({"1": [[letter(5001, "فولاد", AMEND_TITLE)]], "3": [[]]})
    res4 = PL.discover_auto(c2, fetch=feed4)
    t_am = c2.execute("SELECT title FROM codal_notices WHERE tracing_no=5001").fetchone()[0]
    ck(res4["new"] == 1 and FE._is_amendment(t_am),
       "اصلاحیه با شناسۀ خودش می‌ماند و نشانه‌اش را خودِ fts_engine می‌شناسد", t_am)
    ck(not FE._is_amendment(c2.execute("SELECT title FROM codal_notices"
                                       " WHERE tracing_no=3001").fetchone()[0]),
       "و نشانهٔ اصلاحیه به اطلاعیهٔ اصلی هم نمی‌چسبد (برچسبِ ساختگی نیست)")

    # ── ۵) دریافت افزایشی: چرخۀ پایدار کل تاریخچه را نمی‌خواند ─────────────
    before = len(feed.calls)
    again = PL.discover_auto(c, fetch=feed)
    calls = len(feed.calls) - before
    ck(again["found"] == 2 and again["new"] == 0 and again["enqueued"] == 0,
       "همان فید دوباره خوانده می‌شود ولی هیچ رکورد/کارِ تازه نمی‌سازد", again)
    ck(calls <= 2 * len(CF.DISCOVERY_FEED_CATS),
       "صفحه‌هایِ چرخۀ دوم محدود است (افزایشی، نه اسکنِ کامل)", calls)
    ck(n_notice(c) == 2, "تعدادِ سطرهایِ اطلاعیه ثابت ماند (بندِ ۲-۸)", n_notice(c))

    # ── ۶) چند اطلاعیه با زمانِ انتشارِ یکسان: ترتیب و نشانک گم نمی‌شوند ────
    c3 = fresh_db()
    same = "1405/07/24 10:00:00"
    feed6 = Feed({"1": [[letter(6003, "و", FS_TITLE, pub=same),
                         letter(6001, "الف", FS_TITLE, pub=same),
                         letter(6002, "ب", MS_TITLE, pub=same)]], "3": [[]]})
    r6 = PL.discover_auto(c3, fetch=feed6)
    ck(sorted(x[0] for x in r6["items"]) == [6001, 6002, 6003],
       "سه اطلاعیه با یکِ ثانیهٔ انتشار هر سه کشف می‌شوند", r6["items"])
    ck(PL.watermarks(c3)["1"] == 6001,
       "نشانک = کوچک‌ترین شناسۀ صفحۀ خوانده‌شده (با تاریخِ یکسان هم درست)",
       PL.watermarks(c3))

    # ── ۷) تاریخِ انتشار ≠ دورۀ مالی (بندِ ۲-۷) ────────────────────────────
    row = c3.execute("SELECT publish_date FROM codal_notices WHERE tracing_no=6003").fetchone()
    ck(day_is(CP.pub_date_only(row["publish_date"]), 1405, 7, 24),
       "ستونِ اطلاعیه فقط تاریخِ انتشار است", row["publish_date"])
    ck("period" not in [d[1] for d in c3.execute("PRAGMA table_info(codal_notices)")],
       "و هیچ دورۀ مالی درِ جدولِ اطلاعیه نوشته نمی‌شود (جایِ آن financial_statements است)",
       [d[1] for d in c3.execute("PRAGMA table_info(codal_notices)")])
    # و دورۀ مالی از خودِ گزارش می‌آید، نه از این ستون (بندِ ۲-۷):
    pe, src_pe = CP.derive(None, FS_TITLE)
    ck(day_is(pe, 1405, 3, 31) and src_pe == "title",
       "دورۀ canonical از عنوان/منبعِ گزارش می‌آید، جدا از تاریخِ انتشار",
       (pe, src_pe))
    ck(CP.pub_date_only(row["publish_date"]) != pe,
       "تاریخِ انتشار و دورۀ مالی دو مقدارِ جدا می‌مانند (قاطی نمی‌شوند)",
       (CP.pub_date_only(row["publish_date"]), pe))

    # ── ۸) قطعیِ شبکه درِ میانهٔ کشف: نشانک جلو نمی‌رود ─────────────────────
    c4 = fresh_db()
    feed8 = Feed({"1": [[letter(7001, "فولاد", FS_TITLE)], None],   # صفحۀ ۲ = بن
                  "3": [[letter(7002, "خودرو", MS_TITLE, pub="1405/07/20 08:00:00")]]})
    r8 = PL.discover_auto(c4, fetch=feed8)
    ck(r8["blocked"] is True and r8["complete"] is False,
       "قطع/بنِ فید درِ نتیجه ثبت می‌شود (نه صفحۀ خالیِ بی‌صدا)", r8)
    ck(r8.get("error_kind") == "network", "علتِ شکست از نوعِ شبکه برچسب می‌خورد", r8)
    wm8 = PL.watermarks(c4)
    ck(wm8["1"] == 0,
       "دستۀ قطع‌شده نشانک نمی‌گیرد؛ اجرایِ بعدی از همان صفحۀ اول بازیابی می‌کند", wm8)
    ck(n_notice(c4) == 2 and PL.counts(c4)["queued"] == 2,
       "حرفهایِ صفحۀ موفق از دست نمی‌روند: ثبت و صف شده‌اند", (n_notice(c4), PL.counts(c4)))
    # بازیابی: پاسِ بعدی همان دسته را دوباره می‌خواند و بی‌تکرار تمام می‌کند
    feed8.pages["1"] = [[letter(7001, "فولاد", FS_TITLE)],
                        [letter(7003, "شپنا", FS_TITLE, pub="1405/07/22 08:00:00")]]
    r8b = PL.discover_auto(c4, fetch=feed8)
    ck(r8b["blocked"] is False and r8b["new"] == 1,
       "پس از رفعِ قطعی، کارِ ناتمام کامل می‌شود و سطرِ تکراری نمی‌سازد", r8b)
    ck(n_notice(c4) == 3, "شمارِ سطرهایِ اطلاعیه = سه (نه چهار)", n_notice(c4))
    ck(PL.watermarks(c4)["1"] == 7001,
       "نشانک حالا جلو رفت (کوچک‌ترین شناسۀ صفحۀ آخرِ کامل)", PL.watermarks(c4))

    # ── ۹) بودجهٔ صفحه تمام شود، نشانک جلو نمی‌رود (عقب‌ماندگی پنهان نشود) ──
    c5 = fresh_db()
    pages = [[letter(9000 + i, "فولاد", FS_TITLE, pub="1405/07/24 10:00:00")]
             for i in range(1, 9)]                    # هشت صفحۀ تازه
    feed9 = Feed({"1": pages, "3": [[]]})
    r9 = CF.discover_notices(c5, watermarks={"1": 0}, cats=("1",),
                             max_pages=2, overlap_pages=0, fetch=feed9)
    ck(r9["complete"] is False and not r9["floors"],
       "با تمام‌شدنِ بودجه قبل از مرزِ کهنه، نه floors نوشته می‌شود نه نشانک", r9)
    c5b = fresh_db()
    PL.enqueue(c5b, [], reason="noop")
    r9b = PL.discover_auto(c5b, fetch=Feed({"1": pages, "3": [[]]}), max_pages=2)
    ck(PL.watermarks(c5b)["1"] == 0,
       "discover_auto همان نشانکِ محافظه‌کارانه را رعایت می‌کند", PL.watermarks(c5b))
    ck(r9b["enqueued"] == 2, "ولی کارهایِ دیدۀ این پاس فوراً صف می‌شوند (بندِ ۲-۹)",
       r9b["enqueued"])
    # کنترلِ منفیِ سنسور: اگر floors بی‌اعتباریِ scan برگردانَد، نشانک جلو می‌رود
    c5c = fresh_db()
    real = CF.discover_notices

    def broken(conn, watermarks=None, **kw):
        r = real(conn, watermarks=watermarks, **kw)
        r["floors"] = {"1": 8999}            # یعنی «همه‌چیز بالای ۸۹۹۹ دیدہ شد»
        return r
    CF.discover_notices = broken
    try:
        PL.discover_auto(c5c, fetch=Feed({"1": pages, "3": [[]]}), max_pages=2)
        ck(PL.watermarks(c5c)["1"] == 8999,
           "دامِ سنسور: با floorsِ نادرست، نشانک جلو می‌رود — پس گارد کور نیست",
           PL.watermarks(c5c))
    finally:
        CF.discover_notices = real

    # ── ۱۰) اطلاعیهٔ ناقص: ثبت می‌شود، تاریخِ ساختگی نمی‌گیرد، و retry دارد ─
    c6 = fresh_db()
    feed10 = Feed({"1": [[letter(10001, "فولاد", FS_TITLE, pub="")],
                         [letter(10002, "فولاد", FS_TITLE)]], "3": [[]]})
    r10 = PL.discover_auto(c6, fetch=feed10)
    row10 = c6.execute("SELECT publish_date FROM codal_notices WHERE tracing_no=10001").fetchone()
    ck(r10["incomplete"] == 1 and CP.pub_date_only(row10["publish_date"]) is None,
       "بی‌تاریخِ انتشار = رکوردِ ناقص ثبت‌شده، بی‌عددِ ساختگی",
       (r10["incomplete"], row10["publish_date"]))
    pend = [x[0] for x in CF.pending_notices(c6)]
    ck(10001 in pend,
       "و همان رکوردِ ناقص از صفِ استخراج بیرون نمی‌افتد (بازیابی‌پذیر می‌ماند)", pend)

    # ── ۱۱) یدم‌پذیریِ کامل: چرخۀ دوباره همان canonical را می‌دهد ───────────
    c7 = fresh_db()
    fd = Feed({"1": [[letter(11001, "فولاد", FS_TITLE)]], "3": [[]]})
    PL.enqueue(c7, PL.discover_auto(c7, fetch=fd)["items"], reason="x")
    one = PL.run_cycle(c7, "w1", scrape=fs_scrape, budget=4)
    cnt_fs = int(c7.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0])
    rev = c7.execute("SELECT tracing_no, revenue FROM financial_statements"
                     " WHERE symbol='فولاد'").fetchall()
    PL.enqueue(c7, PL.discover_auto(c7,
                                    fetch=Feed({"1": [[letter(11001, "فولاد", FS_TITLE)]],
                                                "3": [[]]}))["items"], reason="x")
    two = PL.run_cycle(c7, "w2", scrape=lambda n: ("fs", None, "empty"), budget=4)
    ck(cnt_fs == 1 and int(c7.execute("SELECT COUNT(*) FROM financial_statements")
                          .fetchone()[0]) == 1,
       "اجرایِ دوباره رویِ همان اطلاعیه ردیفِ مالیِ تکراری نمی‌سازد (بندِ ۲-۸)",
       (cnt_fs, two))
    ck(one["done"] == 1 and two["done"] == 0 and two["empty"] == 0,
       "چرخۀ دوم کاری برایِ پردازش ندارد (صف از قبل تمام شده)", (one, two))
    ck(len(rev) == 1 and rev[0]["revenue"] == 1000.0,
       "مقدارِ مالی یک‌بار اعمال شده است", [tuple(x) for x in rev])

    # ── ۱۲) یکِ منبعِ حقیقت: کوئری و نگاشتِ اطلاعیه دو نسخه ندارند ─────────
    src_all = open(os.path.join(ROOT, "codal_fetcher.py"), encoding="utf-8").read()
    ck(src_all.count('"FromDate": from_date') == 1,
       "ساختارِ کوئریِ فید فقط یکِ بار نوشته شده (feed_query)",
       src_all.count('"FromDate": from_date'))
    ck(src_all.count('"https://codal.ir/" +') == 1,
       "مطلق‌کردنِ پیوندِ کدال فقط یکِ بار (داخلِ _abs_codal_url)",
       src_all.count('"https://codal.ir/" +'))
    ck(src_all.count("letter_to_notice(") >= 7,
       "همۀ درهایِ ورودِ اطلاعیه از همان letter_to_notice می‌گذرند",
       src_all.count("letter_to_notice("))
    ck("pdf_raw" not in src_all, "هیچ نگاشتِ دست‌نویسِ باقی‌مانده‌ای از حرفِ فید نمانده",
       [l for l in src_all.splitlines() if "pdf_raw" in l][:3])

    print("\n%d passed / %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
