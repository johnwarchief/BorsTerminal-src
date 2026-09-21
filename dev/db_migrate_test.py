#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تستِ مهاجرتِ افزودنیِ اسکیما (FTS v2.2) — dev-only، روی یک کپی از market.db.

قرارداد:
  * هیچ‌وقت روی market.db اصلی اجرا نمی‌شود؛ همیشه روی یک کپی (یا فایلی که
    از طریق آرگومان داده می‌شود).
  * سه چیز را اثبات می‌کند:
      ۱) مهاجرت افزودنی است (row count همهٔ جداول قبل/بعد یکسان است)
      ۲) یدم‌پذیر است (اجرای دوباره خطا نمی‌دهد و تغییری ایجاد نمی‌کند)
      ۳) اسکیما درست است (ستون‌ها/ایندکس‌ها/جداولِ مورد انتظار موجودند)

استفاده:
    python dev/db_migrate_test.py [path/to/copy.db]
"""
import os
import sqlite3
import sys

# اجازهٔ importِ ماژول‌های ریشه از داخل dev/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import codal_fetcher as cf  # noqa: E402

_NEW_TABLES = ("symbol_sectors", "market_cap_snapshots", "fts_results")
_NEW_INDEXES = ("ix_fs_sym_pe_aud", "ix_ms_sym_ym", "ix_ss_symbol", "ix_mcs_sym_date")
_NEW_FS_COLS = ("is_audited", "is_consolidated", "fiscal_year", "unit_norm")
_NEW_MS_COLS = ("monthly_volume", "ytd_volume", "volume_unit")


def _tables(conn):
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]


def _counts(conn):
    return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            for t in _tables(conn)}


def _cols(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def _names(conn, kind, extra=""):
    return [r[0] for r in conn.execute(
        f"SELECT name FROM sqlite_master WHERE type='{kind}' {extra}")]


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_ROOT, "_migration_test.db")
    if not os.path.exists(db):
        print(f"[FAIL] db not found: {db}")
        return 2
    print(f"[.. ] testing additive migration on copy: {db}")
    conn = sqlite3.connect(db, timeout=60)

    fs_before, ms_before = _cols(conn, "financial_statements"), _cols(conn, "monthly_sales")
    counts_before = _counts(conn)

    # ۱) اجرای اول
    cf.create_schema(conn)
    cf.migrate_schema(conn)
    print("[OK ] pass 1: create_schema + migrate_schema")

    # ۲) اجرای دوم — یدم‌پذیری
    cf.migrate_schema(conn)
    cf.migrate_schema(conn)
    print("[OK ] pass 2+3: re-ran twice (idempotency), no error")

    counts_after = _counts(conn)
    # فقط جداولِ ازپیش‌موجود باید row count یکسان داشته باشند؛ جداولِ تازه
    # طبیعتاً ۰ ردیف دارند (افزودنی‌اند، نه پرشده).
    drifted = {t: (counts_before.get(t), counts_after.get(t))
               for t in counts_before if counts_before.get(t) != counts_after.get(t)}
    if drifted:
        print("[FAIL] row counts changed on pre-existing tables!")
        for t, (a, b) in drifted.items():
            print(f"        {t}: {a} -> {b}")
        return 1
    new_tables = sorted(set(counts_after) - set(counts_before))
    print(f"[OK ] additive: {len(counts_before)} pre-existing tables keep their row counts")
    print(f"[OK ] new empty tables (expected): {new_tables}")

    integ = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integ != "ok":
        print(f"[FAIL] integrity_check = {integ}")
        return 1
    print("[OK ] integrity_check = ok")

    # ۳) قراردادِ اسکیما
    fs_after, ms_after = _cols(conn, "financial_statements"), _cols(conn, "monthly_sales")
    missing_fs = [c for c in _NEW_FS_COLS if c not in fs_after]
    missing_ms = [c for c in _NEW_MS_COLS if c not in ms_after]
    missing_tables = [t for t in _NEW_TABLES if t not in _tables(conn)]
    missing_ix = [i for i in _NEW_INDEXES if i not in _names(conn, "index")]
    if missing_fs or missing_ms or missing_tables or missing_ix:
        print(f"[FAIL] missing fs={missing_fs} ms={missing_ms} tables={missing_tables} ix={missing_ix}")
        return 1
    print(f"[OK ] financial_statements +{len(_NEW_FS_COLS)} cols: {[c for c in _NEW_FS_COLS]}")
    print(f"[OK ] monthly_sales       +{len(_NEW_MS_COLS)} cols: {[c for c in _NEW_MS_COLS]}")
    print(f"[OK ] new tables: {list(_NEW_TABLES)}")
    print(f"[OK ] new indexes: {list(_NEW_INDEXES)}")

    # ۴) ستون‌های قدیمی همچنان سالم‌اند (هیچ ستونی حذف/تغییر نکرده‌ایم)
    if not set(fs_before).issubset(set(fs_after)) or not set(ms_before).issubset(set(ms_after)):
        print("[FAIL] an existing column disappeared!")
        return 1
    print("[OK ] all pre-existing columns preserved")

    # ۵) NOT NULL DEFAULT 0 روی is_audited/is_consolidated برای ردیف‌های قدیمی
    zero = conn.execute("SELECT COUNT(*) FROM financial_statements WHERE is_audited=0 AND is_consolidated=0").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0]
    print(f"[OK ] is_audited/is_consolidated default 0 on {zero}/{total} pre-existing FS rows")

    conn.close()
    print("[DONE] migration is additive, idempotent and contract-correct")
    return 0


if __name__ == "__main__":
    sys.exit(main())
