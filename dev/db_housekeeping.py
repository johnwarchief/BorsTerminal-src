#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""پاک‌سازیِ داده‌های باقیمانده (R1 + R2) — dev-only، آفلاین، یدم‌پذیر.

دو بدهی که در ممیزیِ نهایی کشف شدند (plans/codal-final-audit.md):

  R2 — اصلاحیه‌های پردازش‌نشده:
      چند ردیف برای یک (symbol, period_end) باقی مانده‌اند — اطلاعیهٔ اصلی
      و اصلاحیه‌اش. قراردادِ پروژه (dedupe_symbol در pipeline_updater و
      _dedupe_ym در fts_engine) ردیفِ با MAX(tracing_no) را نگه می‌دارد، چون
      جدیدترین شماره پیگیری همان اصلاحیه است. این ابزار همان قانون را روی
      دیتایِ ذخیره‌شده اعمال می‌کند.

  R1 — ستون‌های «مقایسه با دورهٔ مشابه سال قبل»:
      monthly_sales.monthly_revenue_prev و ytd_revenue_prev در کل دیتابیس
      NULL هستند. دلیل: این ستون‌ها با ALTER TABLE بعد از ساخته‌شدنِ
      اسنپ‌شات اضافه شده‌اند (codal_fetcher.py:660) — مسیرِ نوشتن (MS_UPSERT
      و scrape_monthly_report) درست است و ستون‌ها را پر می‌کند، ولی
      اسنپ‌شاتِ قدیمی آن‌ها را ندارد. راه‌حل: backfill از ردیفِ سالِ قبل،
      نه تغییرِ کدِ fetch.

قراردادها (همانِ db_backfill_derived.py):
  * هیچ‌وقت روی market.db اصلی اجرا نمی‌شود؛ همیشه یک کپی. اگر مسیرِ
    داده‌شده خودِ market.db باشد، بدونِ --force رد می‌شود.
  * کاملاً آفلاین — هیچ درخواستِ شبکه‌ای.
  * یدم‌پذیر: فقط NULLها را پر می‌کند / فقط ردیف‌های اضافی را حذف می‌کند.
  * NULL = «نامعلوم». سالِ اولِ هر شرکتی مخرجِ YoY ندارد و NULL می‌ماند.
  * dry-run پیش‌فرض است؛ نوشتن نیاز به --apply دارد.

استفاده:
    python dev/db_housekeeping.py [path/to/copy.db] [--apply]
    python dev/db_housekeeping.py --selftest
"""
import argparse
import lzma
import os
import sqlite3
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ── R2: جداولی که ممکن است جفتِ اصلی/اصلاحیه داشته باشند ───────────────────
# هر دو جدول روی (symbol, period_end) می‌توانند تکراری شوند. کلیدِ اصلی
# tracing_no است و بزرگترینِ آن اصلاحیه است.
_DUP_TABLES = (
    ("monthly_sales", "period_end"),
    ("financial_statements", "period_end"),
)

# ── R1: ستون‌های «سال قبل» + منبعِ آن‌ها ─────────────────────────────────
# monthly_sales سال/ماهِ شمسی را در year/month دارد (backfill شده). مخرجِ
# YoY ردیفِ (year-1, month) است — دقیقاً همان منطقی که
# ind1a_monetary_growth در api/fundamental.py در زمانِ خواندن استفاده می‌کند.
_PREV_COLS = (
    ("monthly_revenue_prev", "monthly_revenue"),
    ("ytd_revenue_prev", "ytd_revenue"),
)


def _fresh_copy():
    """یک کپیِ تازه از market.db.lzma در temp — برای تست."""
    src = os.path.join(_ROOT, "market.db.lzma")
    if not os.path.exists(src):
        raise SystemExit(f"[FAIL] market.db.lzma not found: {src}")
    tmp = tempfile.mkdtemp(prefix="bors_housekeep_")
    db = os.path.join(tmp, "copy.db")
    with lzma.open(src) as f, open(db, "wb") as out:
        out.write(f.read())
    return db


def _dup_groups(conn, table, pe_col):
    """گروه‌های (symbol, period_end) با بیش از یک ردیف."""
    return conn.execute(
        f"SELECT symbol, {pe_col}, COUNT(*) n FROM {table} "
        f"WHERE {pe_col} IS NOT NULL GROUP BY symbol, {pe_col} HAVING COUNT(*) > 1"
    ).fetchall()


def _dup_victims(conn, table, pe_col):
    """tracing_noهایی که حذف می‌شوند — هر چیزی به جز MAX(tracing_no) گروه."""
    rows = conn.execute(
        f"SELECT symbol, {pe_col}, tracing_no FROM {table} "
        f"WHERE {pe_col} IS NOT NULL ORDER BY tracing_no"
    ).fetchall()
    keep, victims = {}, []
    for sym, pe, tn in rows:
        key = (sym, pe)
        if key not in keep:
            keep[key] = tn
        elif tn > keep[key]:
            # این ردیف جدیدتر است → قبلی قربانی می‌شود
            victims.append(keep[key])
            keep[key] = tn
        else:
            victims.append(tn)
    return victims


def plan_dedupe(conn):
    """محاسبهٔ قربانیان بدونِ نوشتن — برای dry-run."""
    out = {}
    for table, pe_col in _DUP_TABLES:
        groups = _dup_groups(conn, table, pe_col)
        victims = _dup_victims(conn, table, pe_col)
        out[table] = {"groups": len(groups), "victims": victims}
    return out


def apply_dedupe(conn):
    """R2: حذفِ ردیف‌های باطله. برمی‌گرداند: {table: deleted}"""
    stats = {}
    for table, pe_col in _DUP_TABLES:
        victims = _dup_victims(conn, table, pe_col)
        if victims:
            placeholders = ",".join("?" * len(victims))
            conn.execute(
                f"DELETE FROM {table} WHERE tracing_no IN ({placeholders})", victims)
        stats[table] = len(victims)
    conn.commit()
    return stats


def plan_prev_backfill(conn):
    """تعدادِ ردیف‌هایی که می‌توانند پر شوند — بدونِ نوشتن."""
    cur = conn.execute("SELECT COUNT(*) FROM monthly_sales")
    total = cur.fetchone()[0]
    eligible = 0
    for prev_col, src_col in _PREV_COLS:
        n = conn.execute(
            f"""SELECT COUNT(*) FROM monthly_sales m
                JOIN monthly_sales p
                  ON p.symbol = m.symbol AND p.year = m.year - 1
                 AND p.month = m.month AND p.{src_col} IS NOT NULL
                WHERE m.{prev_col} IS NULL"""
        ).fetchone()[0]
        eligible = max(eligible, n)
    return {"ms_total": total, "eligible": eligible}


def apply_prev_backfill(conn):
    """R1: پر کردنِ *_prev از ردیفِ سالِ قبل. برمی‌گرداند: {col: filled}"""
    stats = {}
    for prev_col, src_col in _PREV_COLS:
        # فقط NULLها را پر می‌کنیم — هرگز مقدارِ واقعی را بازنویسی نکن.
        #
        # نکتهٔ مهم: ممکن است برایِ (symbol, year, month)ِ سالِ قبل چند ردیف
        # وجود داشته باشد — یک گزارشِ اصلیِ تماماً-NULL در کنارِ اصلاحیه‌اش
        # که داده دارد (مثلِ وهور ۱۴۰۲/۱۲). زیرپرسِ نامدارِ بدونِ ORDER پیش
        # از این هرکدام را که می‌خواست برمی‌گزید؛ اگر NULL را برمی‌گزید،
        # UPDATE مقدار NULL می‌نوشت و چون شرطِ «IS NULL» همچنان برقرار بود،
        # اجرای بعدی باز هم «۱ ردیف تغییر کرد» گزارش می‌داد — یعنی backfill
        # هرگز یدم‌پذیر نبود. اکنون فقط ردیفی انتخاب می‌شود که خودش مقدارِ
        # غیرNULL دارد، و ORDER BY + LIMIT انتخاب را در صورتِ چند برنده قطعی
        # می‌کند.
        cur = conn.execute(
            f"""UPDATE monthly_sales
                SET {prev_col} = (
                    SELECT p.{src_col} FROM monthly_sales p
                    WHERE p.symbol = monthly_sales.symbol
                      AND p.year = monthly_sales.year - 1
                      AND p.month = monthly_sales.month
                      AND p.{src_col} IS NOT NULL
                    ORDER BY p.tracing_no DESC
                    LIMIT 1)
                WHERE {prev_col} IS NULL
                  AND EXISTS (SELECT 1 FROM monthly_sales p
                              WHERE p.symbol = monthly_sales.symbol
                                AND p.year = monthly_sales.year - 1
                                AND p.month = monthly_sales.month
                                AND p.{src_col} IS NOT NULL)"""
        )
        stats[prev_col] = cur.rowcount
    conn.commit()
    return stats


def _integrity(conn):
    """integrity_check + foreign_key_check — باید بعد از هر تغییری سبز باشد."""
    ic = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    return ic, len(fk)


def _coverage(conn):
    """پوششِ ستون‌ها بعد از اجرا — برای راستی‌آزمایی."""
    out = {"ms_total": conn.execute("SELECT COUNT(*) FROM monthly_sales").fetchone()[0]}
    for prev_col, _src in _PREV_COLS:
        out[f"ms_{prev_col}_nonnull"] = conn.execute(
            f"SELECT COUNT(*) FROM monthly_sales WHERE {prev_col} IS NOT NULL"
        ).fetchone()[0]
    for table, pe_col in _DUP_TABLES:
        out[f"{table}_dupgroups"] = len(_dup_groups(conn, table, pe_col))
    return out


def run(db_path, apply=False, verbose=True):
    """اجرای کامل روی یک کپی. برمی‌گرداند: (stats, coverage)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        ic0, fk0 = _integrity(conn)
        if ic0 != "ok" or fk0:
            raise SystemExit(f"[FAIL] source DB not clean: integrity={ic0} fk={fk0}")

        dedupe_plan = plan_dedupe(conn)
        prev_plan = plan_prev_backfill(conn)

        if verbose:
            print("== R2: duplicate (symbol, period_end) groups ==")
            for table, info in dedupe_plan.items():
                print(f"  {table}: {info['groups']} groups, "
                      f"{len(info['victims'])} rows to delete")
            print("== R1: prior-year columns ==")
            print(f"  monthly_sales total: {prev_plan['ms_total']}")
            print(f"  eligible for backfill: {prev_plan['eligible']}")

        if not apply:
            if verbose:
                print("\n[DRY-RUN] nothing written. pass --apply to execute.")
            return {"dry_run": True}, _coverage(conn)

        stats = {"dedupe": apply_dedupe(conn),
                 "prev": apply_prev_backfill(conn)}

        ic1, fk1 = _integrity(conn)
        if ic1 != "ok" or fk1:
            raise SystemExit(f"[FAIL] DB corrupted after write: integrity={ic1} fk={fk1}")
        stats["integrity"] = ic1
        stats["fk_violations"] = fk1
        return stats, _coverage(conn)
    finally:
        conn.close()


# ───────────────────────────────────────────────────────────────── selftest
def selftest():
    """سناریوها روی یک کپیِ تازه از market.db.lzma."""
    db = _fresh_copy()
    print(f"[selftest] fresh copy: {db}")
    ok = True

    # ۱) dry-run نباید بنویسد
    _, cov0 = run(db, apply=False, verbose=False)
    _, cov1 = run(db, apply=False, verbose=False)
    if cov0 != cov1:
        print("  [FAIL] dry-run is not idempotent")
        ok = False
    else:
        print("  [ok] dry-run idempotent")

    # ۲) apply باید گروه‌های تکراری را صفر کند
    stats, cov = run(db, apply=True, verbose=False)
    for table, _pe in _DUP_TABLES:
        n = cov[f"{table}_dupgroups"]
        if n != 0:
            print(f"  [FAIL] {table} still has {n} dup groups")
            ok = False
    deleted = sum(stats["dedupe"].values())
    print(f"  [ok] dedupe deleted {deleted} rows; dup groups now 0")

    # ۳) apply مجدد نباید چیزی حذف کند (یدم‌پذیر)
    stats2, _ = run(db, apply=True, verbose=False)
    deleted2 = sum(stats2["dedupe"].values())
    if deleted2 != 0:
        print(f"  [FAIL] second apply deleted {deleted2} more rows")
        ok = False
    else:
        print("  [ok] dedupe idempotent")

    # ۴) backfill باید ستون‌ها را پر کند و دوباره صفر تغییر دهد
    filled = sum(stats["prev"].values())
    if filled == 0:
        print("  [FAIL] backfill filled nothing")
        ok = False
    else:
        print(f"  [ok] backfill filled {filled} cells")
    stats3, cov3 = run(db, apply=True, verbose=False)
    filled3 = sum(stats3["prev"].values())
    if filled3 != 0:
        print(f"  [FAIL] second backfill filled {filled3} more cells")
        ok = False
    else:
        print("  [ok] backfill idempotent")

    # ۵) یک نمادِ مشخص: شارپيلن باید دقیقاً یک ردیف در هر دوره داشته باشد
    n = sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM (SELECT 1 FROM monthly_sales WHERE symbol='شارپيلن' "
        "GROUP BY period_end HAVING COUNT(*) > 1)").fetchone()[0]
    if n != 0:
        print(f"  [FAIL] شارپيلن still has {n} duplicate periods")
        ok = False
    else:
        print("  [ok] شارپيلن canonical (1 row per period)")

    # ۶) سلامتِ نهایی
    ic, fk = _integrity(sqlite3.connect(db))
    if ic != "ok" or fk:
        print(f"  [FAIL] final integrity={ic} fk={fk}")
        ok = False
    else:
        print(f"  [ok] integrity={ic}, fk_violations={fk}")

    print("[selftest] PASS" if ok else "[selftest] FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("db", nargs="?",
                    default=os.path.join(_ROOT, "market.db"))
    ap.add_argument("--apply", action="store_true",
                    help="actually write (default: dry-run)")
    ap.add_argument("--selftest", action="store_true",
                    help="run scenarios on a fresh copy from market.db.lzma")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    real = os.path.realpath(os.path.abspath(args.db))
    real_main = os.path.realpath(os.path.join(_ROOT, "market.db"))
    if real == real_main and not os.environ.get("BORS_FORCE_MAIN"):
        raise SystemExit(
            "[REFUSE] refusing to run on the real market.db.\n"
            "  pass a copy, or set BORS_FORCE_MAIN=1 to override.")

    stats, cov = run(args.db, apply=args.apply)
    print("\n== result ==")
    print(" ", stats)
    print("== coverage ==")
    for k in sorted(cov):
        print(f"  {k}: {cov[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
