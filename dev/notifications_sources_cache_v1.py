"""NOTIFICATION-SOURCES-CACHE v1 — گاردِ کشِ پنلِ سلامتِ منبع (PERF-R2).

پنلِ `/api/notifications/sources` پیش از این هر درخواست دو اسکنِ کاملِ
`codal_notices` می‌زد: `MAX(fetched_at)` (~۶۱ms، بی‌ایندکس) و
`MAX(canonical publish_date)` (~۲۹۷ms، چند replace رویِ هر ردیف). حالا
کلیدِ کش «هویتِ فایلِ بانک + COUNT(*) + MAX(publish_date)» است و دو مقدارِ
گران فقط با عوض شدنِ همان کلید دوباره حساب می‌شوند؛ سقفِ ۱۲۰ثانیه‌ای هم
ویرایشِ درجایِ نامرئی را دیر یا زود تازه می‌کند.

سه چیز باید ثابت بماند:
  ۱) فراخوانِ دوم همان مقدار را می‌دهد و کوئریِ گران را تکرار نمی‌کند؛
  ۲) درجِ ردیفِ تازه بلافاصله عددِ تازه می‌دهد (کشِ کهنه سرو نمی‌شود)؛
  ۳) دو فایلِ بانکِ متفاوت با محتوایِ یکسان کشِ هم را نمی‌خورند.

بانک‌ها فایلِ موقت‌اند؛ بانکِ کاری هرگز نوشته نمی‌شود.

usage: python dev/notifications_sources_cache_v1.py
"""
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import notifications as N  # noqa: E402

DDL = ("CREATE TABLE codal_notices (tracing_no INTEGER PRIMARY KEY, symbol TEXT,"
       " company_name TEXT, title TEXT, letter_code TEXT, publish_date TEXT,"
       " sent_date TEXT, url TEXT, fetched_at TEXT, pdf_url TEXT, excel_url TEXT)")

CHECKS = []


def ck(label, ok, detail=""):
    CHECKS.append(bool(ok))
    print(("OK   " if ok else "FAIL ") + label + (("  ⟨%s⟩" % detail) if detail else ""))
    return bool(ok)


def row(tno, pub, fetched):
    return (tno, "فولاد", "شرکت", "اطلاعات و صورت‌های مالی", "ن-۳۰", pub, pub,
            "https://codal.ir/x", fetched, None, None)


def make_db(path, rows):
    c = sqlite3.connect(path)
    c.execute(DDL)
    c.executemany("INSERT INTO codal_notices VALUES (" + ",".join(["?"] * 11) + ")", rows)
    c.commit()
    return c


def traced(conn):
    """(counter, canonical-query test) — فقط کوئریِ گرانِ canonical را می‌شمارد."""
    n = {"canon": 0}

    def cb(sql):
        if "replace(" in sql and "publish_date" in sql:
            n["canon"] += 1
    conn.set_trace_callback(cb)
    return n


def main():
    N.invalidate_sources_cache()
    tmp = tempfile.mkdtemp(prefix="bors_newssrc_")
    a_path = os.path.join(tmp, "a.db")
    b_path = os.path.join(tmp, "b.db")
    try:
        a = make_db(a_path, [
            row(1, "۱۴۰۵/۰۷/۱۰ ۱۰:۰۰:۰۰", "2026-10-10 10:02:00"),
            row(2, "۱۴۰۵/۰۷/۱۱ ۰۹:۰۰:۰۰", "2026-10-11 09:02:00"),
            row(3, "۱۴۰۴/۱۲/۲۹ ۱۲:۰۰:۰۰", "2026-10-12 12:02:00"),
        ])
        n = traced(a)
        s1 = N.sources(a)["sources"][0]
        first = n["canon"]
        s2 = N.sources(a)["sources"][0]
        ck("فراخوانِ اول مقدارِ canonical می‌سازد", first == 1, "canon=%d" % first)
        ck("فراخوانِ دوم همان مقدار را می‌دهد", s1 == s2, "%s vs %s" % (s1, s2))
        ck("فراخوانِ دوم کوئریِ گران را تکرار نمی‌کند", n["canon"] == first,
           "canon=%d" % n["canon"])

        a.execute("INSERT INTO codal_notices VALUES (" + ",".join(["?"] * 11) + ")", row(
            4, "۱۴۰۵/۰۷/۱۲ ۰۸:۰۰:۰۰", "2026-10-13 08:02:00"))
        a.commit()
        s3 = N.sources(a)["sources"][0]
        ck("درجِ ردیفِ تازه بلافاصله دیده می‌شود",
           s3["rows"] == 4 and "1405/07/12" in str(s3["newest_publish"]), s3)

        # فایلِ دوم با محتوایِ متفاوت: نباید کشِ فایلِ اول را بگیرد.
        b = make_db(b_path, [row(1, "۱۴۰۵/۰۷/۰۱ ۱۰:۰۰:۰۰", "2026-10-01 10:02:00")])
        sb = N.sources(b)["sources"][0]
        ck("دو فایلِ متفاوت کشِ هم را نمی‌خورند",
           sb["rows"] == 1 and "1405/07/01" in str(sb["newest_publish"]), sb)

        # بانکِ درحافظه هویتِ پایدار ندارد ⇒ کش نمی‌شود، ولی مقدار درست است.
        mem = sqlite3.connect(":memory:")
        mem.execute(DDL)
        mem.executemany("INSERT INTO codal_notices VALUES (" + ",".join(["?"] * 11) + ")",
                        [row(1, "۱۴۰۵/۰۶/۰۱ ۱۰:۰۰:۰۰", "2026-10-01 10:00:00")])
        sm = N.sources(mem)["sources"][0]
        ck("بانکِ درحافظه بدونِ کش هم مقدارِ درست می‌دهد",
           sm["rows"] == 1 and "1405/06/01" in str(sm["newest_publish"]), sm)
        a.close()
        b.close()
        mem.close()
    finally:
        for p in (a_path, b_path):
            try:
                os.remove(p)
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass

    print("\n%d بررسی، %d سبز، %d سرخ" %
          (len(CHECKS), sum(CHECKS), len(CHECKS) - sum(CHECKS)))
    print("NOTIFICATION-SOURCES-CACHE: " + ("PASS" if all(CHECKS) else "FAIL"))
    return 0 if all(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
