#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/codal_publish_date_v1089.py — «تازۀ‌ترینِ اطلاعیه» بی‌فریبِ encoding.

CA-1 (ممیزیِ بنیادیِ دورِ اول، ۱۴۰-۰۷-۰): `publish_date` درِ **یکِ ستون** دو
encoding دارد — ارقامِ فارسی (U+06F0..) و ارقامِ ASCII. قفسۀ فارسی درِ واژگانِ
SQLite بعدِ لاتین می‌آید، پس `MAX(publish_date)` و `ORDER BY publish_date DESC`
همیشه ردیفِ فارسی‌رقم را «تازه‌ترین» می‌گزینند، حتی وقتی سه سال کهنه‌تر است.
پیامدِ عملی: پنجرۀ واکشیِ افزایشی یا بی‌مورد باز می‌شود (فشارِ درخواست/خطر ۴۲۹)
یا روزهایِ تازه جا می‌مانند.

قراردادی که این گارد می‌کارد (همه درِ `codal_periods`):
  ۱ نمایشِ canonicalِ مقایسه = ارقامِ لاتین + جداکنندۀ «/» + ساعتِ اختیاری؛
  ۲ همان نمایش درِ SQL (`pub_canon_sql`) و درِ پایتون (`pub_key`) **یکِ جواب**
     می‌دهد — این هم‌سنجی رویِ هر مقدارِ متمایزِ بانکِ واقعی سنجیده می‌شود،
     نه با fixture؛
  ۳ مقدارِ خام درِ ستون می‌ماند (ردیابیِ منبع)، پس هیچ migration/ستونِ افزوده‌ای
     لازم نشده و بانکِ عملیاتی فقط **خوانده** می‌شود؛
  ۴ «ساعتِ نامعلوم» ساعتِ ساختگی نمی‌گیرد: درِ برابریِ روز، رشتهٔ بی‌ساعت
     پیش از رشتهٔ بلساعت می‌آید (= آغازِ روز)، پس یکِ اطلاعیهٔ بی‌ساعت هرگز
     «تازۀ‌ترینِ آن روز» نمی‌شود.

    python dev/codal_publish_date_v1089.py            # fixture + بانکِ کاری (فقط‌خواندنی)
    python dev/codal_publish_date_v1089.py --no-db    # بی‌bank، فقط fixture
"""
import argparse
import ast
import io
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import codal_periods as CP  # noqa: E402

PASS = FAIL = 0
FA = str.maketrans("0123456789", "".join(chr(0x06F0 + d) for d in range(10)))


def fa(s):
    return s.translate(FA)


def ck(cond, what, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ✓ " + what)
    else:
        FAIL += 1
        print("  ✗ " + what + ("   ← " + detail if detail else ""))
    return bool(cond)


def _mem(rows):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE codal_notices (tracing_no INTEGER PRIMARY KEY,"
                 " symbol TEXT, title TEXT, publish_date TEXT)")
    conn.executemany("INSERT INTO codal_notices(tracing_no, symbol, title, publish_date)"
                     " VALUES (?,?,?,?)", rows)
    conn.commit()
    return conn


# ── ۱) خودِ نقص + کنترلِ منفی ───────────────────────────────────────────────
def t1_raw_max_is_wrong():
    print("\n— 1) MAXِ خام فریبِ رقمِ فارسی را می‌خورد؛ canonical نمی‌خورد")
    rows = [
        (1, "الف", "گزارش فعالیت ماهانه", fa("1402/01/01 10:00:00")),   # کهنه، فارسی
        (2, "الف", "گزارش فعالیت ماهانه", "1405/06/13 10:00:00"),        # تازه، لاتین
    ]
    c = _mem(rows)
    raw = c.execute("SELECT MAX(publish_date) FROM codal_notices").fetchone()[0]
    canon = c.execute("SELECT MAX(%s) FROM codal_notices" % CP.pub_canon_sql()).fetchone()[0]
    ck(raw == fa("1402/01/01 10:00:00"),
       "سنسور زنده است: MAXِ خام ردیفِ کهنۀ فارسی‌رقم را برمی‌گرداند", raw)
    ck(canon == "1405/06/13 10:00:00",
       "MAX رویِ عبارتِ canonical ردیفِ واقعاً تازه را برمی‌گرداند", canon)
    import codal_fetcher as CF
    ck(CF.newest_publish_date(c) == "1405/06/13",
       "`newest_publish_date` همان روزِ درست را می‌دهد (نه رشتهٔ خام)",
       str(CF.newest_publish_date(c)))
    c.close()


# ── ۲) پنجرۀ هر-نماد ───────────────────────────────────────────────────────
def t2_per_symbol_window():
    print("\n— 2) پنجرۀ افزایشیِ یکِ نماد از همان نمایش می‌خواند")
    rows = [
        (1, "الف", "x", fa("1404/11/19 15:11:02")),
        (2, "الف", "x", "1405/01/01"),
        (3, "ب",   "x", "1404/01/01"),
    ]
    c = _mem(rows)
    import codal_fetcher as CF
    ck(CF.newest_publish_date(c, "الف") == "1405/01/01",
       "نماد «الف»: ردیفِ لاتینِ 1405 می‌برد، نه فارسی‌رقمِ 1404",
       str(CF.newest_publish_date(c, "الف")))
    ck(CF.newest_publish_date(c, "ب") == "1404/01/01",
       "نماد «ب» پنجرۀ خودش را دارد (نمونۀ سراسری به آن واگذار نمی‌شود)",
       str(CF.newest_publish_date(c, "ب")))
    ck(CF.newest_publish_date(c, "ناموجود") is None,
       "نمادِ بی‌سابقه ⇒ None، نه صفر و نه «1400/01/01»ِ ساختگی درِ تابع",
       str(CF.newest_publish_date(c, "ناموجود")))
    c.close()


# ── ۳) قاعدۀ روز/ساعت ─────────────────────────────────────────────────────
def t3_day_vs_time():
    print("\n— 3) «بی‌ساعت» یعنی آغازِ روز، نه تازۀ‌ترین")
    rows = [
        (1, "پ", "x", "1405/06/13"),                 # بی‌ساعت
        (2, "پ", "x", fa("1405/06/13 07:00:00")),    # همان روز، با ساعت
    ]
    c = _mem(rows)
    import codal_fetcher as CF
    ck(CF.newest_publish_date(c, "پ") == "1405/06/13",
       "پنجره رویِ یکِ روز قفل می‌شود (روزِ خالص برمی‌گردد)",
       str(CF.newest_publish_date(c, "پ")))
    order = c.execute("SELECT tracing_no FROM codal_notices WHERE symbol='پ'"
                      " ORDER BY " + CP.pub_order_expr()).fetchall()
    ck([r[0] for r in order] == [2, 1],
       "ترتیبِ «تازه‌ترین اول» ردیفِ بلساعت را جلوتر می‌گذارد",
       str([r[0] for r in order]))
    c.close()


# ── ۴) SQL ⇄ پایتون رویِ دادهٔ واقعی ───────────────────────────────────────
def t4_sql_python_agreement(db):
    print("\n— 4) عبارتِ SQL و تابعِ پایتون رویِ هر مقدارِ متمایزِ بانک")
    c = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    n = mismatch = 0
    first = []
    for (raw,) in c.execute("SELECT DISTINCT publish_date FROM codal_notices"):
        # مقدار SQL رویِ همان ورودی: یک صفِ ساختگی
        sql_v = c.execute("WITH t(v) AS (SELECT ?) SELECT %s FROM t"
                          % CP.pub_canon_sql().replace("publish_date", "v"),
                          (raw,)).fetchone()[0]
        py_v = CP.pub_key(raw) or ""
        n += 1
        if (CP.pub_key(sql_v) or "") != py_v:
            mismatch += 1
            if len(first) < 3:
                first.append((str(raw), py_v, CP.pub_key(sql_v)))
    ck(mismatch == 0,
       "هیچ ورودی‌ای درِ بانک نیست که SQL و پایتون دو جواب بدهند",
       "checked=%d mismatch=%d %s" % (n, mismatch, first))
    # شمارشِ دامِنۀ نقصِ خام (گزارش، نه ادعا)
    raw_new = c.execute("SELECT MAX(publish_date) FROM codal_notices").fetchone()[0]
    canon_new = c.execute("SELECT MAX(%s) FROM codal_notices" % CP.pub_canon_sql()).fetchone()[0]
    ck(CP.pub_date_only(raw_new) != CP.pub_date_only(canon_new),
       "رویِ بانکِ امروز هم MAXِ خام با canonical فرق دارد (نقص زنده است)",
       "raw=%s canon=%s" % (raw_new, canon_new))
    wrong = c.execute(
        "SELECT COUNT(*) FROM (SELECT symbol, MAX(publish_date) raw, MAX(%s) canon"
        " FROM codal_notices GROUP BY symbol) WHERE raw <> canon" % CP.pub_canon_sql()
    ).fetchone()[0]
    tot = c.execute("SELECT COUNT(DISTINCT symbol) FROM codal_notices").fetchone()[0]
    ck(wrong > 0,
       "پنجرۀ هر-نماد رویِ %d از %d نماد اشتباه می‌گزید (سنجیده شد)" % (wrong, tot),
       "")
    print("  info  نمادهایی که پنجرۀ خامشان کهنه‌تر از واقع است: %d از %d" % (wrong, tot))
    # هیچ مقدارِ دست‌نخورده‌ای با خواندن عوض نمی‌شود (ردیابیِ منبع حفظ است)
    sample = c.execute("SELECT publish_date FROM codal_notices LIMIT 5").fetchall()
    c.close()
    ck(all(s[0] is None or "/" in s[0] or "-" in s[0] for s in sample),
       "مقدارِ خام درِ ستون با شکلِ منبع می‌ماند (canonical فقط درِ خواندن ساخته می‌شود)")
    return wrong, tot


# ── ۵) ورودی‌هایِ نامعتبر ⇒ None، نه صفر ───────────────────────────────────
def t5_invalid_inputs():
    print("\n— 5) نبودِ تاریخ ⇒ None (نه صفر، نه حدس)")
    for bad in (None, "", "   ", "چرند", fa("1405-13-45 10:00:00"), "بی‌تاریخ"):
        got = CP.pub_key(bad)
        ck(got is None, "5) `%r` ⇒ None" % (bad,), str(got))
    ck(CP.pub_key(fa("1405/06/13 ۲۳:۵۳:۵۷")) == "1405/06/13 23:53:57",
       "5) رقمِ فارسی با ساعتِ کامل canonical می‌شود",
       str(CP.pub_key(fa("1405/06/13 ۲۳:۵۳:۵۷"))))
    ck(CP.pub_key("1405-06-13 09:05") == "1405/06/13 09:05:00",
       "5) ساعت بی‌ثانیه ⇒ ثانیه درِ کلید پُر می‌شود (ترتیبِ واژگانی درست بماند)",
       str(CP.pub_key("1405-06-13 09:05")))
    ck(CP.pub_date_only(fa("1404/11/19 15:11:02")) == "1404/11/19",
       "5) `pub_date_only` روزِ خالص می‌دهد (ساعتِ ساختگی نه، برشِ درست بله)")
    ck(CP.pub_key("1405-06-31") == "1405/06/31",
       "5) جداکنندۀ «-» هم به canonicalِ «/» می‌رسد (ورودیِ معتبر رد نمی‌شود)",
       str(CP.pub_key("1405-06-31")))


# ── ۶) قاعدۀ دوم ساخته نشود ────────────────────────────────────────────────
LIVE = ["codal_fetcher.py", "notifications.py", "fts_engine.py", "api/fundamental.py",
        "dev/pipeline_updater.py", "dev/update_codal.py", "dev/db_housekeeping.py",
        "dev/codal_fts_updater.py", "tools/codal_fundamental_audit.py"]
RAW_PAT = re.compile(r"(ORDER BY|MAX\()\s*[^)]*?\bpublish_date\b", re.I)


def t6_no_second_rule():
    """هیچ `execute` درِ مسیرِ زنده مقایسۀ خامِ publish_date نمی‌کند.

    متنِ docstring و کامنت خوانده نمی‌شوند: درختِ پایتون ساخته می‌شود و فقط
    آرگومانِ فراخوانی‌هایِ `.execute(...)` سنجیده می‌شود — وگرنه هر توضیحِ
    «پیش از این MAXِ خام اشتباه بود» گارد را قرمز می‌کرد، و قرمزِ بی‌معنا
    روزی خاموش می‌شود.
    """
    print("\n— 6) هیچ مقایسۀ خامِ «تازۀ‌ترین تاریخ» درِ کوئری‌هایِ زنده نمانده")
    hits = []
    for rel in LIVE:
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            continue
        src = io.open(p, encoding="utf-8").read()
        tree = ast.parse(src, filename=rel)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "execute" and node.args):
                continue
            sql = ast.unparse(node.args[0])
            if (RAW_PAT.search(sql) and "pub_canon_sql" not in sql
                    and "pub_order_expr" not in sql):
                hits.append("%s:%d %s" % (rel, node.lineno, sql[:100]))
    ck(not hits, "6) هر MAX/ORDER BYِ publish_date از `codal_periods` می‌خواند",
       " | ".join(hits[:4]))
    src = io.open(os.path.join(ROOT, "codal_periods.py"), encoding="utf-8").read()
    ck(src.count("def pub_canon_sql") == 1 and src.count("def pub_key") == 1,
       "6) تعریفِ canonical یکی است")


def io_lines(p):
    import io as _io
    return _io.open(p, encoding="utf-8").read().split("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-db", action="store_true")
    ap.add_argument("--db", default=os.path.join(ROOT, "market.db"))
    a = ap.parse_args()
    t1_raw_max_is_wrong()
    t2_per_symbol_window()
    t3_day_vs_time()
    if not a.no_db:
        if os.path.isfile(a.db):
            t4_sql_python_agreement(os.path.abspath(a.db).replace("\\", "/"))
        else:
            print("  SKIP  بانکِ کاری نیست (%s) — بند ۴ اجرا نشد" % a.db)
    t5_invalid_inputs()
    t6_no_second_rule()
    print("\ncodal_publish_date_v1089: %d passed / %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
