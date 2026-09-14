#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/migrate_symbol_norm.py — یکدست‌سازی نوشتارِ ستون نماد (ك/ي عربی → ک/ی فارسی).

نتیجهٔ بازرسیِ 2026-09-14 روی branch master (چرا این اسکریپت به‌صورت پیش‌فرض
اجرا نمیشود و لایهٔ کوئری اصلاحِ اصلی است):
  * price_history.symbol : ۲۵۱۵ نماد، صفر تصادم پس از نرمالسازی → UPDATE امن است.
  * instruments.l_val18  : ۴۷۹۴ نماد، صفر تصادم → امن است، «ولی» همگامسازِ تابلو
    (test_tsetmc.py:677/883) در هر سینک l_val18 را با نوشتارِ خامِ TSETMC
    بازنویسی میکند → یکدستی بعد از نخستین بروزرسانی تابلو برمی‌گردد (drift).
  * financial_statements / monthly_sales : بهترتیب ۲۱ و ۲۷ گروهِ دو-نویشتاری دارند
    → UPDATE اینجا دو شرکت را ادغام میکند (عمداً پشتیبانی نمیشود).
  * test_tsetmc.py:557/568 روی `i.l_val18 = ph.symbol` JOIN میزند؛ اگر فقط
    price_history نرمال شود و instruments عربی بماند، آن JOIN میشکند و دلتای
    تاریخچهٔ همان نمادها بیصدا متوقف میشود.

پس خواندن‌ها با api/_core.sym_pred (→ fts_engine.sym_in) هر دو نوشتار را
میگیرند و این مهاجرت «اختیاری» است؛ آن را فقط وقتی اجرا کنید که نویسندههای
همگامسازی هم روی نوشتار نرمال نوشتن را یاد گرفته باشند.

استفاده:
    python scripts/migrate_symbol_norm.py                # dry-run (فقط گزارش)
    python scripts/migrate_symbol_norm.py --apply        # UPDATE داخل یک تراکنش
    python scripts/migrate_symbol_norm.py --apply --also-instruments

بازاجراپذیر (idempotent): اجرای دوم صفر تغییر گزارش میکند. ایندکس
ix_ph_sym_date2 (symbol, date DESC) توسط SQLite خودبهخود با UPDATE بهروز
میشود؛ تغییر اسکیمایی لازم نیست.
"""
from __future__ import annotations

import os
import sqlite3
import sys

# کنسولِ ویندوز معمولاً cp1252 است و پرینتِ نمادِ فارسی را میشکند — فقط خروجی.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bors_config import DB_PATH  # noqa: E402

KAF_AR, KAF_FA = "\u0643", "\u06a9"      # ك → ک
YEH_AR, YEH_FA = "\u064a", "\u06cc"      # ي → ی
HAMZA_YEH = "\u0649"                     # ى → ی
ZWNJ = "\u200c"


def norm(s):
    """ك→ک، ي/ى→ی، حذف ZWNJ و فاصلههای سر و ته — حفظ بقیهٔ حروف."""
    if s is None:
        return s
    return (str(s).replace(YEH_AR, YEH_FA).replace(KAF_AR, KAF_FA)
            .replace(HAMZA_YEH, YEH_FA).replace(ZWNJ, "").strip())


def migrate_table(conn, table, col):
    """نرمالسازی col در table؛ برمیگرداند (مقدارهای تغییرکرده، تصادمها).

    گارد تصادم: اگر نوشتارِ هدف از قبل با املای دیگری در همین ستون موجود باشد،
    آن مقدار عمداً رد میشود (تا دو شرکت ادغام نشوند) — لایهٔ کوئری هر دو را
    میگیرد و داده دستنخورده میماند.
    """
    distinct = [r[0] for r in conn.execute(f"SELECT DISTINCT {col} FROM {table}")
                if r[0] is not None]
    targets = {v: norm(v) for v in distinct if norm(v) != v}
    collisions = [(old, new, [v for v in distinct if v != old and norm(v) == new])
                  for old, new in targets.items()
                  if any(v != old and norm(v) == new for v in distinct)]
    applied = 0
    for old, new in targets.items():
        if any(c[0] == old for c in collisions):
            continue
        conn.execute(f"UPDATE {table} SET {col} = ? WHERE {col} = ?", (new, old))
        applied += 1
    return applied, collisions


def main(argv):
    apply = "--apply" in argv
    also_ins = "--also-instruments" in argv
    print(f"DB: {DB_PATH} | mode: {'APPLY' if apply else 'DRY-RUN'}")
    if not os.path.exists(DB_PATH):
        print("ERROR: market.db not found")
        return 2
    plan = [("price_history", "symbol")]
    if also_ins:
        plan.append(("instruments", "l_val18"))
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        # ---------- گزارش dry-run ----------
        for table, col in plan:
            distinct = [r[0] for r in conn.execute(f"SELECT DISTINCT {col} FROM {table}")
                        if r[0] is not None]
            need = sum(1 for v in distinct if norm(v) != v)
            print(f"[{table}.{col}] distinct={len(distinct)} | values needing rewrite: {need}")
        if not apply:
            print("dry-run: هیچ چیزی نوشته نشد. برای اعمال: --apply")
            return 0
        # ---------- اعمال داخل یک تراکنش ----------
        conn.execute("BEGIN")
        total, total_col = 0, 0
        for table, col in plan:
            ch, col_ = migrate_table(conn, table, col)
            total += ch
            total_col += len(col_)
            print(f"[{table}.{col}] normalized values: {ch} | collisions skipped: {len(col_)}")
            for old, new, rival in col_[:10]:
                print(f"    COLLISION {table}.{col}: {old!r} -> {new!r} (rival={rival!r})")
        conn.commit()
        print(f"done: {total} values normalized | {total_col} collisions skipped. "
              f"(idempotent — اجرای دوم = صفر تغییر)")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"ERROR rolled back: {type(e).__name__}: {e}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
