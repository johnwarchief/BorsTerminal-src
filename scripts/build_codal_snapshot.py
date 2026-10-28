# -*- coding: utf-8 -*-
"""scripts/build_codal_snapshot.py — ساخت asset دیتابیس کدال برای ریلیز گیت‌هاب.

یک snapshot باریک از market.db می‌سازد (فقط سه جدول کدال: codal_notices،
financial_statements، monthly_sales + ایندکس‌هایشان) و آن را lzma می‌کند.
خروجی ``codal.db.lzma`` باید روی ریلیزِ مخزن توزیع آپلود شود تا دکمهٔ
«بروزرسانی دیتابیس کدال» در اپ (api/_sync_codal.py → CODAL_DB_URL) آن را از
``releases/latest/download/codal.db.lzma`` بگیرد و در market.db کاربر merge
کند (INSERT OR REPLACE با PK=tracing_no — افزاینده و idempotent).

کنارِ lzma یک ``<out>.meta.json`` هم نوشته می‌شود: sha256 و اندازۀ همان فایل،
تازه‌ترین دورۀ صورت‌های مالی و فروشِ ماهانه، شمارشِ سه جدول، و
``min_client_version`` که از ``bors_config.APP_VERSION`` می‌آید.

استفاده:
    python scripts/build_codal_snapshot.py [path/to/market.db] [-o codal.db.lzma]
    python scripts/build_codal_snapshot.py -o codal.db.lzma --meta codal.meta.json
    python scripts/sign_setup.py codal.db.lzma          # → codal.db.lzma.sig (minisign)
    gh release upload v1.0.19 codal.db.lzma codal.db.lzma.sig \
        --repo johnwarchief/BorsTerminal --clobber

بدون .sig معتبر، worker سمت اپ (verify_minisign با UPDATE_PUBKEY) دانلود را رد
می‌کند — هر دو فایل باید با هم و هم‌نسخه آپلود شوند.
"""
import argparse
import datetime
import hashlib
import json
import lzma
import os
import pathlib
import shutil
import sqlite3
import sys

TABLES = ("codal_notices", "financial_statements", "monthly_sales")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)       # برای import bors_config در اجرای CLI

import bors_config  # noqa: E402

SCHEMA_VERSION = 1


class SnapshotError(RuntimeError):
    """ساختِ snapshot ممکن نشد (جدولِ غایب، خرابیِ integrity، …)."""


def _sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _read_meta(db_path, sha256, size):
    """متادیتای اسنپ‌شات را از DBِ مبدأ می‌خواند (فقط‌خواندنی)."""
    uri = pathlib.Path(os.path.abspath(db_path)).as_uri() + "?mode=ro"
    src = sqlite3.connect(uri, uri=True)
    try:
        latest_fs = src.execute(
            "SELECT MAX(period_end) FROM financial_statements").fetchone()[0]
        latest_ms = src.execute(
            "SELECT MAX(period_end) FROM monthly_sales").fetchone()[0]
        row_counts = {t: src.execute(
            "SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in TABLES}
    except sqlite3.Error as exc:
        raise SnapshotError(
            "cannot read periods/row counts from %s: %s" % (db_path, exc)) from exc
    finally:
        src.close()
    return {
        "schema_version": SCHEMA_VERSION,
        "published_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        "latest_financial_period": latest_fs,
        "latest_monthly_period": latest_ms,
        "row_counts": row_counts,
        "sha256": sha256,
        "size": size,
        "min_client_version": bors_config.APP_VERSION,
        "calendar_version": "",
    }


def build_snapshot(db_path, out_lzma, out_meta):
    """lzmaِ سه‌جدولی + متادیتای کنارش را می‌سازد و meta را برمی‌گرداند.

    خطاهای قابل‌انتظار (جدولِ غایب، integrity) ``SnapshotError`` می‌دهند؛
    ``main()`` آن را به پیام و کدِ خروجِ غیرصفر تبدیل می‌کند.
    """
    if not os.path.isfile(db_path):
        raise SnapshotError("source db not found: %s" % db_path)

    tmp_db = out_lzma + ".raw.db"
    if os.path.exists(tmp_db):
        os.remove(tmp_db)

    try:
        total = 0
        src = dst = None
        try:
            src = sqlite3.connect(db_path)
            dst = sqlite3.connect(tmp_db)
            # schema: CREATE TABLE + CREATE INDEX هر سه جدول، verbatim از مبدأ
            for t in TABLES:
                rows = src.execute(
                    "SELECT sql FROM main.sqlite_master "
                    "WHERE tbl_name=? AND sql IS NOT NULL ORDER BY type DESC",
                    (t,)).fetchall()
                if not rows:
                    raise SnapshotError("table %s missing in source db" % t)
                for (ddl,) in rows:
                    dst.execute(ddl)
            dst.commit()
            dst.close()
            dst = None

            # data copy با ATTACH — یک تراکنش، بدون بارگذاری ردیف‌ها در حافظه
            src.execute("ATTACH DATABASE ? AS out", (tmp_db,))
            for t in TABLES:
                n = src.execute(
                    "INSERT INTO out.%s SELECT * FROM main.%s" % (t, t)).rowcount
                total += n
                print("[+] %-22s %7d rows" % (t, n))
            src.commit()
            src.execute("DETACH DATABASE out")
        finally:
            if dst is not None:
                dst.close()
            if src is not None:
                src.close()

        chk = sqlite3.connect(tmp_db)
        try:
            ic = chk.execute("PRAGMA integrity_check").fetchone()
            chk.execute("VACUUM")
        finally:
            chk.close()
        if not ic or ic[0] != "ok":
            raise SnapshotError("snapshot integrity_check failed: %r" % (ic,))
        raw_size = os.path.getsize(tmp_db)

        with open(tmp_db, "rb") as f_in, \
                lzma.open(out_lzma, "wb", preset=9) as f_out:
            shutil.copyfileobj(f_in, f_out, 1 << 20)
    finally:
        if os.path.exists(tmp_db):
            os.remove(tmp_db)

    print("[+] %s — %d rows, raw %.1f MB -> lzma %.1f MB"
          % (out_lzma, total, raw_size / 1e6, os.path.getsize(out_lzma) / 1e6))

    # متادیتا بعد از lzma: sha256/size همان بایت‌های روی دیسک‌اند.
    size = os.path.getsize(out_lzma)
    sha256 = _sha256_file(out_lzma)
    meta = _read_meta(db_path, sha256, size)
    with open(out_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print("[+] %s — sha256 %s, %d bytes" % (out_meta, sha256, size))
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db", nargs="?", default=os.path.join(ROOT, "market.db"))
    ap.add_argument("-o", "--out", default=os.path.join(ROOT, "codal.db.lzma"))
    ap.add_argument("--meta", default=None,
                    help="meta JSON path (default: <out>.meta.json)")
    args = ap.parse_args()

    if not os.path.isfile(args.db):
        print("[-] market.db not found: %s" % args.db)
        return 2
    out_meta = args.meta or (args.out + ".meta.json")
    try:
        build_snapshot(args.db, args.out, out_meta)
    except SnapshotError as exc:
        print("[-] %s" % exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
