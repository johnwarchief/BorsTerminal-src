# -*- coding: utf-8 -*-
"""dev/test_cumulative_db_v1020.py -- نگهبانِ «ارتقای انباشتهٔ دادهٔ بازار».

چرا لازم است: استخراجِ market.db سال‌ها فقط با شرطِ «فایل وجود ندارد» فعال می‌شد،
پس baselineِ تازهٔ هر نسخهٔ جدید هرگز جایِ فایلِ استخراج‌شدهٔ قدیمی را نمی‌گرفت و
«آپدیت» برای دادهٔ بازار عملاً بی‌اثر بود. این گارد همان چهار رفتار را می‌سنجد.
"""
import lzma
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bors_config as bc  # noqa: E402

REQ = {"instruments", "daily_prices", "financial_statements"}
FAILED = []


def check(cond, msg):
    if cond:
        print("  PASS %s" % msg)
    else:
        print("  FAIL %s" % msg)
        FAILED.append(msg)


def build_db(path, tag, watch=()):
    if os.path.exists(path):
        os.remove(path)
    c = sqlite3.connect(path)
    c.execute("create table instruments (symbol text primary key, note text)")
    c.execute("create table daily_prices (d integer, v real)")
    c.execute("create table financial_statements (tracing_no integer primary key, revenue real)")
    c.execute("create table user_watchlists (symbol text, added text)")
    c.execute("insert into instruments values (?, ?)", ("فولاد", tag))
    c.execute("insert into daily_prices values (14010101, 1.0)")
    c.execute("insert into financial_statements values (1, 100.0)")
    for s in watch:
        c.execute("insert into user_watchlists values (?, ?)", (s, tag))
    c.commit()
    c.close()


def pack(src_db, dst_lzma):
    with open(src_db, "rb") as f:
        raw = f.read()
    tmp = dst_lzma + ".tmp"
    with open(tmp, "wb") as f:
        f.write(lzma.compress(raw))
    os.replace(tmp, dst_lzma)


def main():
    work = tempfile.mkdtemp(prefix="bors_cumdb_")
    lzma_path = os.path.join(work, "market.db.lzma")

    # ماژول را رویِ پوشهٔ موقت می‌نشینیم (همان چیزی که در EXE از WORK_DIR می‌آید)
    bc.WORK_DIR = work
    bc.DB_PATH = os.path.join(work, "market.db")
    bc._REQUIRED_MARKET_TABLES = REQ
    bc._find_bundled_db_lzma = lambda: lzma_path

    def tag_of():
        c = sqlite3.connect("file:%s?mode=ro" % bc.DB_PATH, uri=True)
        try:
            return c.execute("select note from instruments").fetchone()[0]
        finally:
            c.close()

    def watch_of():
        c = sqlite3.connect("file:%s?mode=ro" % bc.DB_PATH, uri=True)
        try:
            return sorted(r[0] for r in c.execute("select symbol from user_watchlists"))
        except sqlite3.OperationalError:
            return []
        finally:
            c.close()

    # ۱) بارِ اول: استخراج + مُهر
    build_db(os.path.join(work, "b1.db"), "baseline-1", ["خزر", "فملی"])
    pack(os.path.join(work, "b1.db"), lzma_path)
    bc.ensure_market_db()
    check(tag_of() == "baseline-1", "استخراجِ اولیه")
    stamp1 = bc._read_baseline_stamp()
    check(stamp1 == bc._sha256_file(lzma_path), "مُهرِ baseline نوشته شد")

    # ۲) بدونِ تغییر: نباید چیزی جابه‌جا شود
    bc.ensure_market_db()
    check(not any(n.endswith(".stale") for n in os.listdir(work)),
          "idempotent — با baselineِ یکسان دست نمی‌زند")
    check(bc._read_baseline_stamp() == stamp1, "مُهر دست‌نخورده ماند")

    # ۳) baselineِ تازه: جایگزین شود، واچ‌لیست بماند، قدیمی بایگانی شود
    build_db(os.path.join(work, "b2.db"), "baseline-2", ["خزر", "فملی", "وهمن"])
    pack(os.path.join(work, "b2.db"), lzma_path)
    bc.ensure_market_db()
    check(tag_of() == "baseline-2",
          "baselineِ تازه جایگزین شد (بدونِ این، آپدیتِ داده بی‌اثر است)")
    check(watch_of() == sorted(["خزر", "فملی"]),
          "واچ‌لیستِ کاربر از نسخهٔ قدیمی منتقل شد")
    check(any(n.endswith(".stale") for n in os.listdir(work)),
          "نسخهٔ قدیمی حذف نشد و بایگانی شد")
    check(bc._read_baseline_stamp() == bc._sha256_file(lzma_path), "مُهر تازه شد")

    # ۴) DBِ ناقص/خالی: بازسازی شود (باگِ v1.0.7/8 که تا ابد «داده نیست» می‌داد)
    empty = sqlite3.connect(bc.DB_PATH)
    empty.close()
    bc.ensure_market_db()
    c = sqlite3.connect("file:%s?mode=ro" % bc.DB_PATH, uri=True)
    have = {r[0] for r in c.execute("select name from sqlite_master where type='table'")}
    c.close()
    check(REQ <= have, "DBِ ناقص از market.db.lzma بازسازی شد")

    print("\n%d checks, %d failed" % (7, len(FAILED)))
    print("CUMULATIVE DB GUARD " + ("PASSED" if not FAILED else "FAILED"))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
