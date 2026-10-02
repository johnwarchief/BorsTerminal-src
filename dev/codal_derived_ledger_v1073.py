#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/codal_derived_ledger_v1073.py — یکِ اطلاعیه = یکِ پردازش؛ «دورۀ مشترک» دلیلِ ردکردن نیست.

چرا این گارد متولد شد (هدفِ ۱ کارِ بنیادی، ۱۴۰۵-۰۷-۱۳). نقص از داده درآمد، نه از حدس
(`_audit/` و شمارشِ رویِ `market.db` درِ همین اجرا):

  • `feed_sync` دو مجموعۀ `known_pe/known_ms_pe` را از `DISTINCT period_end` **سراسری**
    می‌ساخت و `_deep_extract` هر گزارشِ هم‌دوره را پیش ازِ هر درخواست رد می‌کرد:

        اطلاعیهٔ فروشِ ماهانۀ بی‌ردیف   ۳٬۵۳۷  →  ۳٬۵۱۶ (۹۹٫۴٪) قربانیِ همین گارد
        اطلاعیهٔ صورتِ مالیِ بی‌ردیف    ۶٬۱۷۱  →  ۶٬۰۷۸ (۹۸٫۵٪) قربانیِ همین گارد

    یعنی به‌محضِ این‌که **یک** نماد دورۀ ۱۴۰۵-۰۶-۳۱ را ثبت می‌کرد، گزارشِ بقیۀ بازار
    برایِ آن دوره برایِ همیشه بی‌ردیف می‌ماند. پوششِ فروشِ ماهانه به همین شکل بود:
    ۶۷۹ نماد درِ دورۀ ۰۴-۳۱، ۴۱۴ درِ ۰۵-۳۱، ۳۲۹ درِ ۰۶-۳۱.
  • `_period_from_title` با «/» می‌ساخت و `period_end` درِ بانک خط تیره دارد، پس
    گاردِ دومِ عنوان‌محور هرگز true نمی‌شد (گاردِ مُرده).
  • `fs_done`/`ms_done` به `_deep_extract` پاس داده می‌شدند ولی **هیچ‌وقت خوانده
    نمی‌شدند** → گزارشِ ثبت‌شده دوباره دوباره scrape می‌شد.
  • قاعدۀ ترجیح (مستقل بر تلفیقی) دو جا نوشته شده بود (`dedupe_symbol` و
    `dev/db_housekeeping.py`) و درِ `_deep_extract` اصلاً اجرا نمی‌شد.
  • `FS_UPSERT` با `INSERT OR REPLACE` بیست‌وششمین ستون (`has_operating_sales`) را
    به NULL برمی‌گرداند (امروز ۸٬۲۲۰ از ۸٬۲۲۰ NULL).
  • نشانکِ increment `MAX(publish_date)` بود، و ۲۰٬۵۴۴ از ۳۶٬۱۸۷ اطلاعیه تاریخشان
    با ارقامِ فارسی ذخیره شده → مقایسهٔ رشته‌ها «۱۴۰۵/…» را بزرگ‌ترین می‌خواند.

قاعدۀ جدید: تنها شناسۀ یکِ گزارش `tracing_no` است، نتیجه درِ `codal_extracted`
ثبت می‌شود (شکستِ شبکه ثبت نمی‌شود تا دوباره تلاش شود)، و درِ پایانِ هر batch
قاعدۀ ترجیح رویِ همان نمادها اجرا می‌شود. بی‌شبکه: scraper فیکچر است.
اجرا:  python dev/codal_derived_ledger_v1073.py    → ۰ سبز، ۱ قرمز
"""
import io
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import codal_fetcher as CF  # noqa: E402

PASS = FAIL = 0
SCRAPES = []            # (tracing_no) — هر scrape واقعی که اتفاق افتاده ثبت می‌شود


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  ✓ {what}")
    else:
        FAIL += 1
        print(f"  ✗ {what}" + (f"   ← {detail}" if detail else ""))


def new_db():
    """بانکِ موقت با همان create_schemaِ خودِ فایل (هیچ مسیری به market.db نمی‌خورد)."""
    path = os.path.join(tempfile.mkdtemp(prefix="codal_guard_"), "t.db")
    conn = sqlite3.connect(path)
    CF.create_schema(conn)
    CF.migrate_schema(conn)      # تولید هم همین دو را پشتِ هم می‌زند (ستون‌های مشتق اینجا می‌آیند)
    # `instruments` درِ بانکِ تولید از سینکِ بازار می‌آید؛ اینجا همان سه ستونِ
    # لازمِ `pending_notices` ساخته می‌شود (نامِ کامل برایِ تشخیصِ صندوق).
    conn.execute("CREATE TABLE IF NOT EXISTS instruments"
                 " (ins_code TEXT PRIMARY KEY, l_val18 TEXT, l_val30 TEXT,"
                 "  sector_name TEXT, paper_type INTEGER)")
    return conn


def notice(tn, sym, title, url="https://codal.ir/1"):
    return (tn, sym, "شرکت " + sym, title, "4", "1405/06/01 10:00:00",
            "1405/06/01 10:00:00", url, "2026-10-01 10:00:00", "", "")


# عنوان‌ها را از خودِ بانکِ واقعی برداشته‌ایم: `kind_of` باید هر دو نوع را بشناسد
FS_TITLE = "اطلاعات و صورتهای مالی میاندورهای دوره ۳ ماهه منتهی به ۱۴۰۵/۰۶/۳۱"
MS_TITLE = "گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به ۱۴۰۵/۰۶/۳۱"


def install_scrapers(fs_map=None, ms_map=None, fail_for=()):
    """scraperهایِ فیک: fs_map/ms_map = {tracing_no: (مقادیر، متا، واحد)}."""
    def scrape_report(sess, url):
        tn = int(url.rsplit("/", 1)[-1])
        SCRAPES.append(("fs", tn))
        if tn in fail_for:
            raise RuntimeError("simulated network failure")
        vals = (fs_map or {}).get(tn)
        if vals is None:
            return {}, {}, None
        return ({"revenue": vals[0], "gross_profit": vals[1], "net_profit": vals[2]},
                {"period": 3, "end": vals[3], "is_consolidated": vals[4]}, "10 ریال")

    def scrape_monthly_report(sess, url):
        tn = int(url.rsplit("/", 1)[-1])
        SCRAPES.append(("ms", tn))
        if tn in fail_for:
            raise RuntimeError("simulated network failure")
        vals = (ms_map or {}).get(tn)
        if vals is None:
            return {}, None
        return ({"monthly_revenue": vals[0], "ytd_revenue": vals[1]}, vals[2])

    CF.scrape_report = scrape_report
    CF.scrape_monthly_report = scrape_monthly_report
    CF.make_session = lambda *a, **k: object()


def seed(conn, notices):
    conn.executemany(CF.NOTICE_UPSERT, notices)
    conn.commit()


def main():
    print("— ۱) دورۀ مشترکِ دو نماد دیگر ردیفِ هیچ‌کدام را نمی‌کُشد (ریشۀ نقص)")
    install_scrapers(ms_map={11: (1.0, 3.0, "1405-06-31"), 12: (2.0, 5.0, "1405-06-31")})
    conn = new_db()
    seed(conn, [notice(11, "فولاد", MS_TITLE, "u/11"), notice(12, "خگستر", MS_TITLE, "u/12")])
    processed, fs_done, ms_done = CF.derived_state(conn)
    n_fs, n_ms = CF._deep_extract(list(conn.execute(
        "SELECT tracing_no, symbol, company_name, title, letter_code, publish_date,"
        " sent_date, url, fetched_at, pdf_url, excel_url FROM codal_notices")),
        processed, conn)
    ck(n_ms == 2, "هر دو نماد ردیفِ فروشِ ماهانه می‌گیرند", f"n_ms={n_ms}")
    rows = conn.execute("SELECT symbol, period_end FROM monthly_sales ORDER BY symbol").fetchall()
    ck([r[0] for r in rows] == ["خگستر", "فولاد"], "دو ردیفِ مستقل برایِ یکِ دورۀ واحد", str(rows))

    print("\n— ۲) یکِ اطلاعیه یک‌بار پردازش می‌شود (دفتر، نه شمارِ ردیف‌هایِ باقی‌مانده)")
    SCRAPES.clear()
    again, _f2, _m2 = CF.derived_state(conn)
    CF._deep_extract(list(conn.execute(
        "SELECT tracing_no, symbol, company_name, title, letter_code, publish_date,"
        " sent_date, url, fetched_at, pdf_url, excel_url FROM codal_notices")), again, conn)
    ck(len(SCRAPES) == 0, "اجرای دوم هیچ درخواستی نمی‌زند", str(SCRAPES))
    led = conn.execute("SELECT tracing_no, ok FROM codal_extracted ORDER BY tracing_no").fetchall()
    ck(led == [(11, 1), (12, 1)], "دفترِ استخراج هر دو اطلاعیه را با نتیجه ثبت کرده", str(led))

    print("\n— ۲-ب) اطلاعیه‌ای که درِ اجرایِ *بعد* می‌رسد هم ردیف می‌گیرد")
    SCRAPES.clear()
    n3 = [notice(13, "شبندر", MS_TITLE, "u/13")]
    seed(conn, n3)
    p3x, _a, _b = CF.derived_state(conn)
    install_scrapers(ms_map={11: (1.0, 3.0, "1405-06-31"), 12: (2.0, 5.0, "1405-06-31"),
                             13: (4.0, 9.0, "1405-06-31")})
    CF._deep_extract(n3, p3x, conn)
    ck(conn.execute("SELECT COUNT(*) FROM monthly_sales WHERE symbol='شبندر'").fetchone()[0] == 1,
       "دورۀ ۱۴۰۵-۰۶-۳۱ از قبل برایِ دو نماد دیگر ثبت بود — باز هم پردازش شد", "")
    ck(len(SCRAPES) == 1, "فقط همین یکِ گزارشِ تازه باز شد", str(SCRAPES))


    print("\n— ۳) قاعدۀ ترجیح: مستقل بر تلفیقی، بدونِ ترتیبِ رسیدن")
    for order, want in ((("tel", "std"), "std"), (("std", "tel"), "std")):
        c2 = new_db()
        ns = []
        for i, kind in enumerate(order):
            tn = 100 + i
            ns.append(notice(tn, "فولاد", FS_TITLE, "u/%d" % tn))
        seed(c2, ns)
        fs_map = {100: (10.0, 4.0, 2.0, "1405-06-31", 1),
                  101: (7.0, 3.0, 1.0, "1405-06-31", 0)}   # 101 = مستقل
        install_scrapers(fs_map=fs_map)
        p2, _a, _b = CF.derived_state(c2)
        CF._deep_extract(ns, p2, c2)
        left = c2.execute("SELECT tracing_no, COALESCE(is_consolidated,0)"
                          " FROM financial_statements WHERE symbol='فولاد'").fetchall()
        ck(len(left) == 1 and left[0][1] == 0,
           "ترتیبِ «%s» → یکِ ردیف و همانِ مستقل می‌ماند" % ("/".join(order)), str(left))

    print("\n— ۴) شکستِ شبکه ثبت نمی‌شود (باید درِ اجرای بعدی تلاش شود)")
    c3 = new_db()
    ns = [notice(201, "فولاد", FS_TITLE, "u/201"), notice(202, "پارس", FS_TITLE, "u/202")]
    seed(c3, ns)
    install_scrapers(fs_map={201: (5.0, 1.0, 1.0, "1405-06-31", 0),
                             202: (9.0, 2.0, 2.0, "1405-06-31", 0)}, fail_for={201})
    p3, _a, _b = CF.derived_state(c3)
    CF._deep_extract(ns, p3, c3)
    ck(c3.execute("SELECT COUNT(*) FROM codal_extracted WHERE tracing_no=201").fetchone()[0] == 0,
       "سطرِ ناموفق درِ دفتر نیامده", "")
    ck(c3.execute("SELECT COUNT(*) FROM codal_extracted WHERE tracing_no=202").fetchone()[0] == 1,
       "سطرِ موفق درِ دفتر ثبت شد", "")

    print("\n— ۵) گزارشِ بی‌عدد (empty) ثبت می‌شود تا هر اجرا تکرار نشود")
    c4 = new_db()
    ns = [notice(301, "فولاد", FS_TITLE, "u/301")]
    seed(c4, ns)
    install_scrapers(fs_map={})                 # هیچ چیزی برنمی‌گرداند
    p4, _a, _b = CF.derived_state(c4)
    CF._deep_extract(ns, p4, c4)
    ck(c4.execute("SELECT ok FROM codal_extracted WHERE tracing_no=301").fetchone()[0] == 0,
       "ok=0 ثبت شده و ردیفی ساخته نشده", "")

    print("\n— ۶) store_notices=False سطرِ اطلاعیه را بازنویسی نمی‌کند")
    c5 = new_db()
    ns = [notice(401, "فولاد", MS_TITLE, "u/401")]
    seed(c5, ns)
    c5.execute("UPDATE codal_notices SET fetched_at='قدیم', excel_url='کدال-x' WHERE tracing_no=401")
    install_scrapers(ms_map={401: (1.0, 3.0, "1405-06-31")})
    p5, _a, _b = CF.derived_state(c5)
    CF._deep_extract(ns, p5, c5, store_notices=False)
    keep = c5.execute("SELECT fetched_at, excel_url FROM codal_notices WHERE tracing_no=401").fetchone()
    ck(keep == ("قدیم", "کدال-x"), "فیلدهایِ ثبت‌شدۀ اطلاعیه دست‌نخورده", str(keep))
    ck(c5.execute("SELECT COUNT(*) FROM monthly_sales").fetchone()[0] == 1,
       "با این حال ردیفِ مشتق ساخته شد", "")

    print("\n— ۷) بازنشرِ همان گزارش ستون‌هایِ فهرست‌نشده را خالی نمی‌کند")
    c6 = new_db()
    ns = [notice(501, "فولاد", FS_TITLE, "u/501")]
    seed(c6, ns)
    install_scrapers(fs_map={501: (5.0, 1.0, 1.0, "1405-06-31", 0)})
    p6, _a, _b = CF.derived_state(c6)
    CF._deep_extract(ns, p6, c6)
    c6.execute("UPDATE financial_statements SET has_operating_sales=1 WHERE tracing_no=501")
    c6.execute("DELETE FROM codal_extracted WHERE tracing_no=501")     # وادار به بازنشر
    p6b, _a, _b = CF.derived_state(c6)
    CF._deep_extract(ns, p6b, c6)
    ck(c6.execute("SELECT has_operating_sales FROM financial_statements"
                  " WHERE tracing_no=501").fetchone()[0] == 1,
       "DO UPDATE ستونِ بیست‌وششم را نگه می‌دارد (با INSERT OR REPLACE NULL می‌شد)", "")

    print("\n— ۸) نشانکِ increment با ارقامِ فارسی نمی‌شکند")
    c7 = new_db()
    seed(c7, [notice(601, "فولاد", MS_TITLE, "u/601")])
    c7.execute("UPDATE codal_notices SET publish_date='۱۴۰۴/۰۱/۰۱ 10:00:00' WHERE tracing_no=601")
    c7.execute("INSERT INTO codal_notices (tracing_no,symbol,title,publish_date) VALUES"
               " (602,'پارس','x','1405-06-13 10:00:00')")
    ck(c7.execute("SELECT MAX(publish_date) FROM codal_notices").fetchone()[0].startswith("۱۴۰۴"),
       "خودِ MAXِ SQLite فریبِ رقمِ فارسی را می‌خورد (شاهدِ نقص)")
    ck(CF.newest_publish_date(c7) == "1405/06/13",
       "newest_publish_date تاریخِ درست را برمی‌گرداند", str(CF.newest_publish_date(c7)))

    print("\n— ۹) صفِ جبران: فقطِ معوق‌ها، تازۀ‌ترین اول، با سقف")
    c8 = new_db()
    ns = [notice(701, "فولاد", FS_TITLE, "u/701"), notice(702, "پارس", FS_TITLE, "u/702"),
          notice(703, "خگستر", MS_TITLE, "u/703")]
    seed(c8, ns)
    c8.execute("UPDATE codal_notices SET publish_date='1405-07-01 09:00:00' WHERE tracing_no=702")
    c8.execute("INSERT INTO financial_statements (tracing_no,symbol,title,period_end,revenue)"
               " VALUES (701,'فولاد','x','1405-06-31',5)")
    pend = CF.pending_notices(c8, limit=5)
    ck([r[0] for r in pend] == [702, 703], "دو معوق، تازۀ‌ترین اول (۷۰۱ چون ردیف دارد بیرون است)",
       str([r[0] for r in pend]))
    ck(len(CF.pending_notices(c8, limit=1)) == 1, "سقفِ بودجه اعمال می‌شود", "")
    c8.execute("INSERT INTO instruments (ins_code, l_val18, l_val30) VALUES"
               " ('x703','خگستر','صندوق سرمایه گذاری مشترک خگستر')")
    ck([r[0] for r in CF.pending_notices(c8, limit=5)] == [702],
       "گزارشِ صندوق (فقط پورتفوی/NAV) بودجۀ صف را نمی‌خورد", str(
           [r[0] for r in CF.pending_notices(c8, limit=5)]))

    print("\n— ۱۰) derived_state دفتر ∪ FS ∪ MS است و برایِ یکِ نماد هم درست کار می‌کند")
    st_all = CF.derived_state(c8)
    ck(st_all[0] == {701}, "سراسری: فقطِ ردیف‌دارها پردازش‌شده‌اند", str(st_all[0]))
    st_sym = CF.derived_state(c8, "فولاد")          # (processed, fs_done, ms_done)
    ck(st_sym[0] == {701} and st_sym[1] == {701} and st_sym[2] == set(),
       "نماد-محور: fs_done و processed فقط ردیف‌هایِ همان نماد را می‌بینند", str(st_sym))
    for c in (conn, c2, c3, c4, c5, c6, c7, c8):
        c.close()
    print(f"\nنتیجه: {PASS} سبز، {FAIL} قرمز")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
