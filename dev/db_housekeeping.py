#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""پاک‌سازیِ داده‌های باقیمانده (R1 + R2) — dev-only، آفلاین، یدم‌پذیر.

دو بدهی که در ممیزیِ نهایی کشف شدند (plans/codal-final-audit.md):

  R2 — گروه‌های چندردیفه برای بازبینی:
      بیش از یک tracing_no در (symbol, period_end) به‌تنهایی ثابت نمی‌کند
      ingest تکراری رخ داده؛ ممکن است اطلاعیه‌های مستقل/تلفیقی/اصلاحیه باشند.
      `period_winners` مرجعِ نمایشی را انتخاب می‌کند، اما housekeeping حقِ حذف
      فیزیکیِ اطلاعیه‌های متمایز را ندارد. تا اثباتِ هویتِ تکراری، حذف خودکار صفر است.

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
import atexit
import contextlib
import lzma
import os
import shutil
import sqlite3
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ── R2: جداولی که ممکن است جفتِ اصلی/اصلاحیه داشته باشند ───────────────────
# هر دو جدول روی (symbol, period_end) می‌توانند تکراری شوند؛ برندۀ هر گروه را
# `codal_fetcher.period_winners` تعیین می‌کند (بی‌قاعدهٔ دوم درِ این فایل).
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
    """یک کپیِ تازه از market.db.lzma در temp — برای تست.

    پاک‌کردن به `atexit` سپرده می‌شود، نه فقط به انتهای `--selftest`: اجرایِ
    ساده (dry-run) که سوئیتِ کامل هر دور صدا می‌زند ۱۴۸ مگابایت در %TEMP%
    جا می‌گذاشت (پنج اجرایِ این دور = ۷۰۷ مگابایت).
    """
    src = os.path.join(_ROOT, "market.db.lzma")
    if not os.path.exists(src):
        raise SystemExit(f"[FAIL] market.db.lzma not found: {src}")
    tmp = tempfile.mkdtemp(prefix="bors_housekeep_")
    atexit.register(shutil.rmtree, tmp, True)
    db = os.path.join(tmp, "copy.db")
    with lzma.open(src) as f, open(db, "wb") as out:
        out.write(f.read())
    return db


def _dup_groups(conn, table, pe_col):
    """گروه‌های (symbol, period_end) با بیش از یک ردیف — با **همان** تعریفِ
    «ردیفِ دوره‌دار» در `codal_periods` (بی‌predicaleِ دومِ `IS NOT NULL`)."""
    import codal_periods as CP
    return conn.execute(
        f"SELECT symbol, {pe_col}, COUNT(*) n FROM {table} "
        f"WHERE {CP.DATED_SQL} GROUP BY symbol, {pe_col} HAVING COUNT(*) > 1"
    ).fetchall()


def _dup_victims(conn, table, pe_col):
    """نامزد حذف خودکار برنمی‌گرداند؛ گروه چندردیفه فقط سیگنال بازبینی است.

    tracing_no کلید اصلیِ هر اطلاعیه است. تفاوت tracing_noها یعنی هویتِ منبع
    متفاوت است؛ بدون اثباتی مستقل که دو ردیف یک اطلاعیهٔ واحد را بازنمایی کنند،
    حذف خودکار مجاز نیست. گروه‌بندیِ دوره فقط برای گزارشِ _dup_groups است.
    """
    if (table, pe_col) not in _DUP_TABLES:
        raise ValueError(f"unsupported duplicate audit target: {table}.{pe_col}")
    return []


def plan_dedupe(conn):
    """محاسبهٔ قربانیان بدونِ نوشتن — برای dry-run."""
    out = {}
    for table, pe_col in _DUP_TABLES:
        groups = _dup_groups(conn, table, pe_col)
        victims = _dup_victims(conn, table, pe_col)
        out[table] = {"groups": len(groups), "victims": victims}
    return out


def apply_dedupe(conn):
    """R2: حفظِ رکوردهای منبع؛ هیچ حذف خودکاری از گروه‌بندیِ دوره انجام نمی‌دهد."""
    # عمداً هیچ DELETE اجرا نمی‌شود. گروه‌های چندردیفه در plan_dedupe فقط برای
    # بازبینی‌اند؛ حذف در آینده نیازمند اثباتِ هویتِ یک اطلاعیهٔ تکراری است.
    return {table: 0 for table, _pe_col in _DUP_TABLES}


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
    """پوششِ ستون‌ها بعد از اجرا — برای راستی‌آزمایی.

    شمارِ «بی‌دوره» از همان `codal_periods.undated_counts` خوانده می‌شود که هر
    consumerِ دیگر می‌خواند؛ این فایل کوئریِ شمارشِ خودش را ندارد. بعضی guardها
    عمداً فقط یکی از جدول‌های داده را می‌سازند؛ نبودِ جدول با صفرِ جعلی اشتباه نمی‌شود.
    """
    import codal_periods as CP
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    out = {
        "fs_total": (conn.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0]
                     if "financial_statements" in tables else None),
        "ms_total": (conn.execute("SELECT COUNT(*) FROM monthly_sales").fetchone()[0]
                     if "monthly_sales" in tables else None),
    }
    ms_cols = ({r[1] for r in conn.execute("PRAGMA table_info(monthly_sales)")}
               if "monthly_sales" in tables else set())
    for prev_col, _src in _PREV_COLS:
        out[f"ms_{prev_col}_nonnull"] = (
            conn.execute(f"SELECT COUNT(*) FROM monthly_sales WHERE {prev_col} IS NOT NULL").fetchone()[0]
            if prev_col in ms_cols else None
        )
    for table, pe_col in _DUP_TABLES:
        out[f"{table}_dupgroups"] = (
            len(_dup_groups(conn, table, pe_col)) if table in tables else None
        )
    out["undated"] = CP.undated_counts(conn)
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
            print("== R2: multi-notice (symbol, period_end) review groups ==")
            for table, info in dedupe_plan.items():
                print(f"  {table}: {info['groups']} groups, "
                      f"{len(info['victims'])} automatic deletions (disabled without identity proof)")
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

    # ۲) چندردیفه‌بودن فقط برای بازبینی است؛ apply حق ندارد اطلاعیه مستقل را حذف کند.
    stats, cov = run(db, apply=True, verbose=False)
    deleted = sum(stats["dedupe"].values())
    retain_keys = ("fs_total", "ms_total", "financial_statements_dupgroups", "monthly_sales_dupgroups")
    if deleted != 0:
        print(f"  [FAIL] automatic dedupe deleted {deleted} distinct-source rows")
        ok = False
    for key in retain_keys:
        if cov.get(key) != cov0.get(key):
            print(f"  [FAIL] source retention changed {key}: {cov0.get(key)} -> {cov.get(key)}")
            ok = False
    if not deleted and all(cov.get(k) == cov0.get(k) for k in retain_keys):
        print("  [ok] apply retained all notice rows; multi-notice groups remain reviewable")

    # ۳) apply مجدد باید هم idempotent و هم غیرمخرب بماند.
    stats2, cov2 = run(db, apply=True, verbose=False)
    deleted2 = sum(stats2["dedupe"].values())
    if deleted2 != 0 or any(cov2.get(k) != cov.get(k) for k in retain_keys):
        print(f"  [FAIL] second apply changed retained data: deleted={deleted2}")
        ok = False
    else:
        print("  [ok] second apply preserved rows and review groups")

    # ۴) backfill باید ستون‌ها را پر کند و دوباره صفر تغییر دهد.
    #
    # نکته: اسنپ‌شاتِ واقعیِ market.db.lzma ممکن است از قبل کاملاً backfill
    # شده باشد (این ابزار رویِ خودِ DB اجرا شده). در آن حالت اجرای دوبارهٔ
    # backfill مشروعاً «صفر» تغییر می‌دهد و تستِ «باید پر شود» بی‌معنا می‌شود.
    # پس اول رویِ کپی یک شکافِ مصنوعی می‌سازیم: فقط ردیف‌هایی را NULL می‌کنیم
    # که مخرجِ سالِ قبلشان موجود است؛ سپس خروجیِ backfill باید دقیقاً همان‌ها
    # را پر کند و اجرای بعدی صفر تغییر بدهد.
    gap_conn = sqlite3.connect(db)
    gap_conn.execute("PRAGMA foreign_keys = ON")
    gap = 0
    for prev_col, src_col in _PREV_COLS:
        cur = gap_conn.execute(
            f"""UPDATE monthly_sales SET {prev_col} = NULL
                WHERE {prev_col} IS NOT NULL
                  AND EXISTS (SELECT 1 FROM monthly_sales p
                              WHERE p.symbol = monthly_sales.symbol
                                AND p.year = monthly_sales.year - 1
                                AND p.month = monthly_sales.month
                                AND p.{src_col} IS NOT NULL)""")
        gap += cur.rowcount
    gap_conn.commit()
    gap_conn.close()
    print(f"  [setup] artificial prev-year gap: {gap} cells nulled")
    if gap == 0:
        print("  [FAIL] no eligible rows to backfill (snapshot has no prior-year data)")
        ok = False

    stats, cov = run(db, apply=True, verbose=False)
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

    # ۵) انتخاب مرجع برای نمایش از نگهداریِ تمام اطلاعیه‌های منبع جداست.
    print("  [ok] source retention is separate from reference-row selection")

    # ۶) سلامتِ نهایی
    with contextlib.closing(sqlite3.connect(db)) as k6:
        ic, fk = _integrity(k6)
    if ic != "ok" or fk:
        print(f"  [FAIL] final integrity={ic} fk={fk}")
        ok = False
    else:
        print(f"  [ok] integrity={ic}, fk_violations={fk}")

    print("[selftest] PASS" if ok else "[selftest] FAIL")
    # کپیِ آزمون ~۱۴۰ مگابایت است و پیش‌تر هیچ‌وقت پاک نمی‌شد؛ ۳۳ اجرایِ این
    # selftest ≈ ۴٫۶ گیگابایت درِ %TEMP% جا گذاشته بود. `ignore_errors=True`
    # حذفِ ناکام را بی‌صدا می‌کرد (ویندوز تا هندلِ اتصال باز است پاک نمی‌کند) —
    # حالا اتصال‌ها بسته‌اند و خطا صادقانه چاپ می‌شود؛ `atexit` هم ضمناً ثبت شده.
    try:
        shutil.rmtree(os.path.dirname(db))
        print(f"[selftest] copy removed: {db}")
    except OSError as e:
        print(f"[selftest] copy left behind ({db}): {e}")
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
