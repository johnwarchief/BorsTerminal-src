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
  • ادعایِ «گاردِ عنوان‌محور مُرده است چون DB خط تیره دارد» **تصحیح شد**
    (۱۴۰۵-۰۷-۱۰، شمارشِ رویِ بانکِ کاری): `period_end` خط تیره ندارد — ۸٬۳۹۶ ردیفِ
    `financial_statements` و ۱۴٬۶۹۷ ردیفِ `monthly_sales` همه با «/» و ۶۷ تا NULL.
    چیزی که مقایسه را می‌شکست رقمِ فارسی و دو فاصلۀ داخلِ عنوان بود. حالا هر دو
    از `codal_periods` می‌خوانند و این بندِ فهرست دیگر معنا ندارد.
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
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import codal_fetcher as CF  # noqa: E402

PASS = FAIL = 0
SCRAPES = []            # (tracing_no) — هر scrape واقعی که اتفاق افتاده ثبت می‌شود
_REAL_FS = CF.scrape_report              # خودِ توابع، پیشِ این‌که فیک‌ها جایشان را
_REAL_MS = CF.scrape_monthly_report      # بگیرند (بخشِ ۱۳ باید مسیرِ واقعی را بسنجد)


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

    print("\n— ۹ب) صفِ جبران آنچه همین اجرا آزموده را دوباره نمی‌آورد (exclude_tried)")
    c9 = new_db()
    seed(c9, [notice(801, "فولاد", FS_TITLE, "u/801"), notice(802, "پارس", FS_TITLE, "u/802"),
              notice(803, "خاورمیانه", MS_TITLE, "u/803")])
    # ۸۰۱ و ۸۰۲ تازه باز شده‌اند: یکی ردیف داده، دیگری خالی بوده (ok=0) — دومی هم
    # «پردازش‌شده» است و بودجه را نباید بخورد.
    c9.execute("INSERT INTO codal_extracted (tracing_no, kind, ok, tried_at)"
               " VALUES (801,'fs',1,'2026-10-02 15:00:00')")
    c9.execute("INSERT INTO codal_extracted (tracing_no, kind, ok, tried_at)"
               " VALUES (802,'fs',0,'2026-10-02 15:00:00')")
    q_new = [r[0] for r in CF.pending_notices(c9, limit=5)]
    q_old = [r[0] for r in CF.pending_notices(c9, limit=5, exclude_tried=False)]
    ck(q_new == [803], "بی‌ردیف‌هایِ واقعی می‌مانند؛ آزموده‌شده‌ها (ok=1 و ok=0) از صف بیرون",
       str(q_new))
    ck(q_old == [802, 801, 803] or set(q_old) == {801, 802, 803},
       "رفتارِ قدیم (بی‌فیلتر) هر سه را برمی‌گرداند — همان چیزی که بودجه را می‌خورد",
       str(q_old))
    c9.execute("DELETE FROM codal_extracted WHERE tracing_no=803")
    c9.execute("INSERT INTO codal_extracted (tracing_no, kind, ok, tried_at)"
               " VALUES (803,'ms',0,'2026-10-02 15:00:00')")
    ck(CF.pending_notices(c9, limit=5) == [], "صفِ تمام‌شده خالی است، نه پرِ دوباره‌کاری",
       str([r[0] for r in CF.pending_notices(c9, limit=5)]))

    print("\n— ۱۰) derived_state دفتر ∪ FS ∪ MS است و برایِ یکِ نماد هم درست کار می‌کند")
    st_all = CF.derived_state(c8)
    ck(st_all[0] == {701}, "سراسری: فقطِ ردیف‌دارها پردازش‌شده‌اند", str(st_all[0]))
    st_sym = CF.derived_state(c8, "فولاد")          # (processed, fs_done, ms_done)
    ck(st_sym[0] == {701} and st_sym[1] == {701} and st_sym[2] == set(),
       "نماد-محور: fs_done و processed فقط ردیف‌هایِ همان نماد را می‌بینند", str(st_sym))
    print("\n— ۱۱) اهرمِ سرعت: اندازهٔ استخرِ استخراج از CLI تنظیم می‌شود (کدال ۱۴۰۵-۰۷-۱۰)")
    # چیزی که محدودکننده است شبکه است، نه SQLite: هر گزارش ~۳ GET. پس گارد باید
    # «همزمانیِ واقعی» را ببیند نه متنِ سورس.
    _st = {"cur": 0, "peak": 0}
    _lk = threading.Lock()

    def slow_ms(sess, url):
        tn = int(url.rsplit("/", 1)[-1])
        with _lk:
            _st["cur"] += 1
            _st["peak"] = max(_st["peak"], _st["cur"])
            _st.setdefault("sessions", set()).add(id(sess))
        time.sleep(0.05)
        with _lk:
            _st["cur"] -= 1
        return ({"monthly_revenue": float(tn), "ytd_revenue": 2.0}, "1405-06-31")

    CF.scrape_monthly_report = slow_ms
    CF.make_session = lambda *a, **k: object()
    c10 = new_db()
    ns10 = [notice(900 + i, "S%02d" % i, MS_TITLE, "u/%d" % (900 + i)) for i in range(24)]
    seed(c10, ns10)
    _saved_workers, _saved_polite = CF.EXTRACT_WORKERS, CF.POLITE

    def peak_with(workers, polite):
        # دفتر باید پیش از هر سنجش خالی شود، وگرنه `derived_state` همه را
        # پردازش‌شده می‌خواند، `todo` خالی می‌ماند و اوجِ همزمانی صفر «سبز» می‌شود.
        c10.execute("DELETE FROM codal_extracted")
        c10.execute("DELETE FROM monthly_sales")
        CF.set_extract_workers(workers)
        CF.POLITE = polite
        _st["cur"] = _st["peak"] = 0
        _st["sessions"] = set()
        p10, _a, _b = CF.derived_state(c10)
        CF._deep_extract(ns10, p10, c10, store_notices=False)
        return _st["peak"], len(_st["sessions"])

    _p8, _s8 = peak_with(8, False)
    ck(_p8 >= 8, "با --extract-workers 8 تا ۸ اسکرپ همزمان در جریان است", "peak=%d" % _p8)
    ck(_s8 <= 8, "session به‌ازایِ ترد ساخته می‌شود، نه به‌ازایِ گزارش (۲۴ گزارش ≤ ۸ session)",
       "sessions=%d" % _s8)
    _p4, _s4 = peak_with(4, False)
    ck(_p4 == 4, "پیش‌فرضِ ۴ برگشت: اوجِ همزمانی دقیقاً ۴ است (نه بیشتر، نه کمتر)",
       "peak=%d" % _p4)
    CF.POLITE = True
    _p1, _s1 = peak_with(8, True)
    CF.POLITE = False
    ck(_p1 == 1, "درِ --polite استخر همیشه ۱ است (بی‌روتاریشنِ IP ⇒ تک‌کارگر)", "peak=%d" % _p1)
    ck(_s1 == 1, "با یکِ کارگر فقط یکِ session ساخته می‌شود", "sessions=%d" % _s1)
    ck(c10.execute("SELECT COUNT(*) FROM monthly_sales").fetchone()[0] == 24,
       "سرعت، درستیِ نوشتن را خراب نمی‌کند: هر ۲۴ ردیف نشسته", "")
    CF.set_extract_workers(99)
    ck(CF.EXTRACT_WORKERS == 16, "سقفِ ۱۶ اعمال می‌شود (WAF را یک اجرا نزند)",
       str(CF.EXTRACT_WORKERS))
    CF.set_extract_workers(0)
    ck(CF.EXTRACT_WORKERS == 1, "کفِ ۱ اعمال می‌شود", str(CF.EXTRACT_WORKERS))
    CF.set_extract_workers(_saved_workers)
    CF.POLITE = _saved_polite

    print("\n— ۱۲) ترمیم: ردیفِ بی‌دوره پر می‌شود و عددِ موجود پاک نمی‌شود")
    # ۳۸ ردیفِ FS و ۳۰ ردیفِ MS درِ بانکِ کاری `period_end` ندارند (از پاسِ
    # ۲۰۲۶-۰۸-۲۹، پیشِ پارسرِ «نام‌محور»): `collapse_symbol` آن‌ها را درِ هیچ
    # دورگی نمی‌بیند، پس قاعدۀ «یکِ دورۀ یکِ نماد = یکِ ردیف» هرگز رویشان اجرا
    # نمی‌شود. `--repair` تنها مسیرِ موجود است و بی‌این اصلاح دوره را نمی‌داد.
    rpath = os.path.join(tempfile.mkdtemp(prefix="codal_repair_"), "r.db")
    rc = sqlite3.connect(rpath)
    CF.create_schema(rc)
    CF.migrate_schema(rc)
    seed(rc, [notice(1001, "فولاد", MS_TITLE, "u/1001"), notice(1002, "پارس", MS_TITLE, "u/1002"),
              notice(1003, "خگستر", FS_TITLE, "u/1003"), notice(1004, "شبندر", FS_TITLE, "u/1004")])
    rc.execute("INSERT INTO monthly_sales (tracing_no,symbol,title,period_end,"
               " monthly_revenue,ytd_revenue) VALUES (1001,'فولاد','x',NULL,NULL,NULL)")
    rc.execute("INSERT INTO monthly_sales (tracing_no,symbol,title,period_end,"
               " monthly_revenue,ytd_revenue) VALUES (1002,'پارس','x',NULL,5.0,9.0)")
    rc.execute("INSERT INTO financial_statements (tracing_no,symbol,title,period_end,revenue)"
               " VALUES (1003,'خگستر','x',NULL,NULL)")
    rc.execute("INSERT INTO financial_statements (tracing_no,symbol,title,period_end,revenue)"
               " VALUES (1004,'شبندر','x',NULL,7.0)")
    # نامۀ باز نشد، ولی **عنوانش** تاریخ دارد → مرحلۀ عنوان (که بعدِ بازمخانی
    # می‌آید) دوره را می‌دهد و عددِ موجود دست نمی‌زند.
    rc.execute("INSERT INTO financial_statements (tracing_no,symbol,title,period_end,revenue)"
               " VALUES (1005,'فولاد',?,NULL,8.0)", (FS_TITLE,))
    rc.commit()
    rc.close()

    def rep_fs(sess, url):
        tn = int(url.rsplit("/", 1)[-1])
        if tn == 1003:
            return ({"revenue": 11.0, "net_profit": 3.0}, {"end": "1405-06-31"}, "10 ریال")
        return {}, {}, None

    def rep_ms(sess, url):
        tn = int(url.rsplit("/", 1)[-1])
        if tn == 1001:
            return {"monthly_revenue": 2.0, "ytd_revenue": 6.0}, "1405-06-31"
        if tn == 1002:      # دورۀ درست، فقط یکِ عددِ تازه (ماهانه None)
            return {"monthly_revenue": None, "ytd_revenue": 99.0}, "1405-05-31"
        return {}, None

    CF.scrape_report = rep_fs
    CF.scrape_monthly_report = rep_ms
    CF.make_session = lambda *a, **k: object()
    _saved_db, CF.DB_PATH = CF.DB_PATH, rpath
    n_ms, n_fs = CF.repair_broken_rows()
    CF.DB_PATH = _saved_db
    rr = sqlite3.connect(rpath)
    ms1 = rr.execute("SELECT period_end, year, month, monthly_revenue, ytd_revenue"
                     " FROM monthly_sales WHERE tracing_no=1001").fetchone()
    # رابطِ scrape تاریخ را با «-» می‌دهد؛ درِ ستون باید canonical («/») بنشیند
    ck(ms1 == ("1405/06/31", 1405, 6, 2.0, 6.0),
       "ردیفِ بی‌مبلغ: عدد + دوره/سال/ماه پر می‌شود و دوره در شکلِ canonical می‌نشیند",
       str(ms1))
    ms2 = rr.execute("SELECT period_end, monthly_revenue, ytd_revenue"
                     " FROM monthly_sales WHERE tracing_no=1002").fetchone()
    ck(ms2 == ("1405/05/31", 5.0, 99.0),
       "ردیفِ عدددارِ بی‌دوره: دوره پر می‌شود، COALESCE عددِ موجود را با NULLِ parseِ ناقص نمی‌کُشد",
       str(ms2))
    fs3 = rr.execute("SELECT period_end, revenue, net_profit FROM financial_statements"
                     " WHERE tracing_no=1003").fetchone()
    ck(fs3 == ("1405/06/31", 11.0, 3.0), "FS بی‌فیلدِ کلیدی: مبالغ و دوره می‌آید", str(fs3))
    ck(rr.execute("SELECT fiscal_year FROM financial_statements WHERE tracing_no=1003"
                  " ").fetchone()[0] == "1405",
       "سالِ مالیِ مشتق هم از همان دوره می‌آید (بی‌ستونِ بی‌همخوان)", "")
    fs4 = rr.execute("SELECT period_end, revenue FROM financial_statements"
                     " WHERE tracing_no=1004").fetchone()
    ck(fs4 == (None, 7.0), "نامه‌ای که باز نشد: ردیفِ موجود دست‌نخورده (بی‌صفرکردن، بی‌NULL‌کردن)",
       str(fs4))
    ck((n_ms, n_fs) == (2, 1), "شمارشِ ترمیم فقطِ ردیف‌هایِ واقعاً تغییرکرده", str((n_ms, n_fs)))
    fs5 = rr.execute("SELECT period_end, revenue FROM financial_statements"
                     " WHERE tracing_no=1005").fetchone()
    ck(fs5 == ("1405/06/31", 8.0),
       "نامۀ بازنشده ولی عنوانش تاریخ دارد: دوره از عنوان پر می‌شود، عدد دست‌نخورده",
       str(fs5))
    ck(rr.execute("SELECT fiscal_year FROM financial_statements WHERE tracing_no=1005"
                  " ").fetchone()[0] is None,
       "مرحلۀ عنوان فقط دوره را می‌نویسد (سالِ مالیِ آن ردیف به اجرای بعدِ backfill می‌ماند)",
       "")
    rr.close()

    print("\n— ۱۳) «باز نشد» با «باز شد و عدد نداشت» یکی نیست (سقفِ دفتر)")
    # پیش از این هر دو scraper خطایِ شبکه را می‌بلعیدند و `{}` برمی‌گرداندند؛
    # `_scrape_one` آن را empty می‌خواند و ok=0 درِ دفتر می‌نوشت → گزارشِ یکِ
    # بنِ گذرا برایِ همیشه بی‌مشتق می‌ماند (شاهدِ امروز: ConnectionResetError
    # 10054 درِ پاسِ ۵٬۲۳۸ی، بعدِ ۴۲۹ و قبلِ چرخشِ IP).
    _saved_get = CF._resilient_get
    CF._resilient_get = lambda s, url, **k: None          # بن/قطعِ شبکه
    for fn, name in ((lambda: _REAL_FS(object(), "u/1"), "scrape_report"),
                     (lambda: _REAL_MS(object(), "u/1"), "scrape_monthly")):
        try:
            fn()
            ck(False, "%s بی‌خطا برگشت — باید RuntimeError می‌داد" % name, "")
        except RuntimeError:
            ck(True, "%s خطایِ شبکه را پنهان نمی‌کند (⇒ درِ دفتر ثبت نمی‌شود)" % name, "")
        except Exception as e:
            ck(False, "%s خطایِ دیگری داد" % name, "%s: %s" % (type(e).__name__, e))
    CF._resilient_get = _saved_get

    print("\n— ۱۴) «URL بی‌اعتبار» چرخشِ IP راه نمی‌اندازد")
    # دو سطرِ خرابِ `codal_notices.url` (تاریخِ فارسی درِ ستونِ url) هر تلاش را
    # «خطایِ شبکه» می‌خواند و چهار بار `rotate_ip_via_adb()` می‌زد = چهار دورۀ
    # ~۲ دقیقه‌ای قطعِ شبکه برایِ یکِ نقصِ داده‌ای.
    _saved_hook = (CF.rotate_ip_via_adb, CF._control_sleep, CF.POLITE)
    CF.POLITE = False
    CF._control_sleep = lambda *a, **k: None
    _EXC = CF.requests.exceptions

    class _Boom:
        def __init__(self, exc):
            self.exc, self.calls = exc, 0

        def get(self, url, **kw):
            self.calls += 1
            raise self.exc

    for exc, want_rot, name in ((_EXC.InvalidSchema("nope"), 0, "InvalidSchema"),
                                (_EXC.ConnectionError("reset"), 1, "ConnectionError")):
        rot, b = [], _Boom(exc)
        CF.rotate_ip_via_adb = lambda *a, **k: (rot.append(1), True)[1]
        r = CF._resilient_get(b, "۱۴۰۴/۰۹/۲۳ ۱۸:۱۰:۳۰", tries=3, quiet=True)
        want = "بی‌چرخشِ IP و بی‌تلاشِ دوباره" if not want_rot else "با تلاشِ دوباره و چرخشِ IP"
        ck(r is None and (len(rot) > 0) == bool(want_rot)
           and b.calls == (1 if not want_rot else 3),
           "%s ⇒ %s" % (name, want), "calls=%d rotations=%d" % (b.calls, len(rot)))
    CF.rotate_ip_via_adb, CF._control_sleep, CF.POLITE = _saved_hook

    print("\n— ۱۵) قاعدۀ «یکِ دوره یکِ ردیف» سه جا نمی‌شکند (ردیفِ مستقل نمی‌میرد)")
    # دام: تلفیقی شمارهٔ ردیابیِ **بزرگ‌تر** دارد (اصلاحیهٔ تلفیقی بعد از مستقل
    # منتشر شده). قاعدۀ MAX(tracing_no) همان را نگه می‌داشت و مستقل را حذف —
    # سنجیدۀ بانکِ کاری: ۱۱ دورۀ مستقل+تلفیقی در همین دام افتاده بودند.
    c11 = new_db()
    ns11 = [notice(200, "دعبید", FS_TITLE, "u/200"), notice(900, "دعبید", FS_TITLE, "u/900")]
    seed(c11, ns11)
    # مبنا درِ **عنوان** نوشته می‌شود، چون عنوان منبعِ هر دو مسیر است:
    # `period_winners` (نویسنده) و `pick_reference` (خواننده) هر دو
    # `_is_consolidated(title)` را می‌خوانند — ستونِ `is_consolidated` درِ
    # auditِ ۱۴۰۵-۰۷-۱۱ غیرقابل‌اتکا شناخته شد (۱٬۲۰۸ ردیف با عنوان نمی‌خواند).
    SOLO = "صورت‌های مالی سال مالی منتهی به ۱۴۰۵/۰۶/۳۱ (حسابرسی نشده)"
    CONS = "صورت‌های مالی تلفیقی سال مالی منتهی به ۱۴۰۵/۰۶/۳۱ (حسابرسی نشده)"
    import fts_engine as _fe11
    FE_IS_CONS = _fe11._is_consolidated
    ck(FE_IS_CONS(CONS) and not FE_IS_CONS(SOLO),
       "شاهدِ عنوان: «تلفیقی» درِ عنوان خوانده می‌شود، نه ستون", "")
    c11.execute("INSERT INTO financial_statements (tracing_no, symbol, title, period_end,"
                " revenue, is_consolidated) VALUES"
                " (200,'دعبید','%s','1405/06/31',100.0,0),"
                " (900,'دعبید','%s','1405/06/31',160.0,1),"
                " (910,'دعبید','%s',NULL,7.0,0)" % (SOLO, CONS, SOLO))
    ck(max(r[0] for r in c11.execute("SELECT tracing_no FROM financial_statements"
                                     " WHERE period_end='1405/06/31'")) == 900,
       "شاهدِ دام: «MAX(tracing_no)» ردیفِ تلفیقی (۹۰۰) را برمی‌دارد", "")
    ck(CF.period_winners(c11, "financial_statements") == {("دعبید", "1405/06/31"): 200},
       "period_winners (یکِ جا) مستقل را برندۀ همان دوره می‌داند و بی‌دوره را اصلاً نمی‌بیند",
       str(CF.period_winners(c11, "financial_statements")))
    CF.collapse_symbol(c11, "دعبید")
    left = c11.execute("SELECT tracing_no, COALESCE(is_consolidated,0)"
                       " FROM financial_statements ORDER BY tracing_no").fetchall()
    ck(left == [(200, 0), (910, 0)],
       "collapse_symbol: یکِ ردیف درِ آن دوره + ردیفِ بی‌دوره دست‌نخورده (بندِ ۳)", str(left))

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import db_housekeeping as HK  # noqa: E402
    c12 = new_db()
    seed(c12, ns11)
    c12.execute("INSERT INTO financial_statements (tracing_no, symbol, title, period_end,"
                " revenue, is_consolidated) VALUES"
                " (200,'دعبید','%s','1405/06/31',100.0,0),"
                " (900,'دعبید','%s','1405/06/31',160.0,1),"
                " (910,'دعبید','%s','1404/12/29',7.0,0),"   # تنها ردیفِ دورۀ خودش
                " (920,'دعبید','%s',NULL,9.0,0)"
                % (SOLO, CONS, SOLO, SOLO))           # بی‌دوره
    ck(HK._dup_victims(c12, "financial_statements", "period_end") == [900],
       "dev/db_housekeeping --apply: قربانی فقط تلفیقی است؛ نه تنها-ردیفِ یکِ دوره و نه بی‌دوره",
       str(HK._dup_victims(c12, "financial_statements", "period_end")))
    # دو ابزارِ دیگر باید به همین یکِ قاعده واگرد کنند (نقشۀ متنِ سورس: واگردِ
    # صریح، نه قاعدۀ دومِ بی‌سرنخ)
    pu_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "pipeline_updater.py"), encoding="utf-8").read()
    hk_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "db_housekeeping.py"), encoding="utf-8").read()
    ck("cf.collapse_symbol(conn, sym)" in pu_src,
       "dev/pipeline_updater.dedupe_symbol به collapse_symbol واگرد می‌کند", "")
    ck("CF.period_winners(conn, table)" in hk_src,
       "dev/db_housekeeping از period_winners می‌خواند (قاعدۀ دوم درِ فایل نیست)", "")
    ck("MAX(tracing_no) FROM financial_statements" not in pu_src,
       "درِ pipeline_updater هیچ «MAX(tracing_no)» برایِ صورتهایِ مالی نمانده", "")

    for c in (conn, c2, c3, c4, c5, c6, c7, c8, c10, c11, c12):
        c.close()
    print(f"\nنتیجه: {PASS} سبز، {FAIL} قرمز")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
