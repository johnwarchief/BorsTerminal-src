# -*- coding: utf-8 -*-
"""scripts/build_codal_snapshot.py — ساخت asset دیتابیس کدال برای ریلیز گیت‌هاب.

یک snapshot باریک از market.db می‌سازد (فقط سه جدول کدال: codal_notices،
financial_statements، monthly_sales + ایندکس‌هایشان) و آن را lzma می‌کند.
خروجی ``codal.db.lzma`` باید روی ریلیزِ مخزن توزیع آپلود شود تا دکمهٔ
«بروزرسانی دیتابیس کدال» در اپ (api/_sync_codal.py → CODAL_DB_URL) آن را از
``releases/latest/download/codal.db.lzma`` بگیرد و در market.db کاربر merge
کند (INSERT OR REPLACE با PK=tracing_no — افزاینده و idempotent).

استفاده:
    python scripts/build_codal_snapshot.py [path/to/market.db] [-o codal.db.lzma]
    python scripts/sign_setup.py codal.db.lzma          # → codal.db.lzma.sig (minisign)
    gh release upload v1.0.18 codal.db.lzma codal.db.lzma.sig \
        --repo johnwarchief/BorsTerminal --clobber

بدون .sig معتبر، worker سمت اپ (verify_minisign با UPDATE_PUBKEY) دانلود را رد
می‌کند — هر دو فایل باید با هم و هم‌نسخه آپلود شوند.
"""
import argparse
import lzma
import os
import shutil
import sqlite3
import sys

TABLES = ("codal_notices", "financial_statements", "monthly_sales")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db", nargs="?", default=os.path.join(ROOT, "market.db"))
    ap.add_argument("-o", "--out", default=os.path.join(ROOT, "codal.db.lzma"))
    args = ap.parse_args()

    if not os.path.isfile(args.db):
        print("[-] market.db not found: %s" % args.db)
        return 2
    tmp_db = args.out + ".raw.db"
    if os.path.exists(tmp_db):
        os.remove(tmp_db)

    src = sqlite3.connect(args.db)
    dst = sqlite3.connect(tmp_db)
    try:
        # schema: CREATE TABLE + CREATE INDEX هر سه جدول، verbatim از مبدأ
        for t in TABLES:
            rows = src.execute(
                "SELECT sql FROM main.sqlite_master "
                "WHERE tbl_name=? AND sql IS NOT NULL ORDER BY type DESC",
                (t,)).fetchall()
            if not rows:
                print("[-] table %s missing in source db" % t)
                return 1
            for (ddl,) in rows:
                dst.execute(ddl)
        dst.commit()
        dst.close()

        # data copy با ATTACH — یک تراکنش، بدون بارگذاری ردیف‌ها در حافظه
        src.execute("ATTACH DATABASE ? AS out", (tmp_db,))
        total = 0
        for t in TABLES:
            n = src.execute(
                "INSERT INTO out.%s SELECT * FROM main.%s" % (t, t)).rowcount
            total += n
            print("[+] %-22s %7d rows" % (t, n))
        src.commit()
        src.execute("DETACH DATABASE out")
    finally:
        src.close()

    chk = sqlite3.connect(tmp_db)
    ic = chk.execute("PRAGMA integrity_check").fetchone()
    chk.execute("VACUUM")
    chk.close()
    if not ic or ic[0] != "ok":
        print("[-] snapshot integrity_check failed: %r" % (ic,))
        return 1
    raw_size = os.path.getsize(tmp_db)

    with open(tmp_db, "rb") as f_in, lzma.open(args.out, "wb", preset=9) as f_out:
        shutil.copyfileobj(f_in, f_out, 1 << 20)
    os.remove(tmp_db)
    print("[+] %s — %d rows, raw %.1f MB -> lzma %.1f MB"
          % (args.out, total, raw_size / 1e6, os.path.getsize(args.out) / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
