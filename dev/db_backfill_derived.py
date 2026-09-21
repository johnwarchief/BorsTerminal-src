#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""پر کردنِ آفلاینِ ستون‌های مشتقِ FTS v2.2 — dev-only، روی یک کپی از market.db.

ستون‌هایی که migrate_schema اضافه کرد اما روی دیتایِ موجود NULL مانده‌اند:
  * financial_statements: is_audited, is_consolidated, fiscal_year, unit_norm
  * monthly_sales:         year, month (ردیف‌های قدیمی؛ ix_ms_sym_ym بی‌آن‌ها
                           بی‌فایده است)

قراردادها:
  * هیچ‌وقت روی market.db اصلی اجرا نمی‌شود؛ همیشه یک کپی (یا مسیری از طریقِ
    آرگومان). اگر مسیرِ داده‌شده خودِ market.db باشد، بدونِ --force رد می‌شود.
  * کاملاً آفلاین است — هیچ درخواستِ شبکه‌ای به کدال نمی‌زند.
  * یدم‌پذیر: فقط ردیف‌های NULL را پر می‌کند، اجرای مکرر تغییری نمی‌کند.
  * NULL = «نامعلوم»، نه ۰. is_audited=0 یعنی واقعاً حسابرسی‌نشده.
  * طبقه‌بندیِ عنوان/واحد دقیقاً از fts_engine می‌آید (منبع یگانه حقیقت).

استفاده:
    python dev/db_backfill_derived.py [path/to/copy.db] [--force]
    python dev/db_backfill_derived.py --selftest      # دیسکِ تازه + سناریوها
"""
import argparse
import lzma
import os
import sqlite3
import sys
import tempfile

# اجازهٔ importِ ماژول‌های ریشه از داخل dev/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import codal_fetcher as cf  # noqa: E402
import fts_engine as fe     # noqa: E402


def _fresh_copy():
    """یک کپیِ تازه و دست‌نخورده از market.db.lzma در temp — برای تست."""
    src = os.path.join(_ROOT, "market.db.lzma")
    if not os.path.exists(src):
        raise SystemExit(f"[FAIL] market.db.lzma not found: {src}")
    tmp = tempfile.mkdtemp(prefix="bors_backfill_")
    db = os.path.join(tmp, "copy.db")
    with lzma.open(src) as f, open(db, "wb") as out:
        out.write(f.read())
    return db


def _stats(conn):
    """پوششِ ستون‌های مشتق بعد از اجرا — برای راستی‌آزمایی."""
    out = {}
    out["fs_total"] = conn.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0]
    for col in ("is_audited", "is_consolidated", "fiscal_year", "unit_norm"):
        out[f"fs_{col}_null"] = conn.execute(
            f"SELECT COUNT(*) FROM financial_statements WHERE {col} IS NULL").fetchone()[0]
    out["ms_total"] = conn.execute("SELECT COUNT(*) FROM monthly_sales").fetchone()[0]
    out["ms_ym_null"] = conn.execute(
        "SELECT COUNT(*) FROM monthly_sales WHERE year IS NULL OR month IS NULL").fetchone()[0]
    out["unit_norm_dist"] = dict(conn.execute(
        "SELECT COALESCE(unit_norm,'(null)'), COUNT(*) FROM financial_statements "
        "GROUP BY unit_norm").fetchall())
    return out


def _verify_against_engine(conn):
    """هم‌خوانیِ ستونِ پرشده با همان توابعی که fts_engine در کوئری می‌زند.

    نمونه‌گیریِ تصادفیِ ۲۰۰ ردیف: اگر backfill با موتور disagrees یعنی
    منطقِ موازی ساخته‌ایم — باید ۰ اختلاف باشد.
    """
    import random
    rows = conn.execute(
        "SELECT title, is_audited, is_consolidated FROM financial_statements "
        "WHERE unit_norm IS NOT NULL ORDER BY RANDOM() LIMIT 200").fetchall()
    bad = 0
    for title, aud, con in rows:
        if (1 if fe._is_audited(title or "") else 0) != aud:
            bad += 1
        if (1 if fe._is_consolidated(title or "") else 0) != con:
            bad += 1
    return len(rows), bad


def run(db, force=False, label=""):
    """اجرای backfill روی db؛ برمی‌گرداند کدِ خروج (۰=موفق)."""
    if not os.path.exists(db):
        print(f"[FAIL] db not found: {db}")
        return 2
    real = os.path.normpath(os.path.join(_ROOT, "market.db"))
    if os.path.normpath(os.path.abspath(db)) == real and not force:
        print(f"[REFUSE] refusing to run on the live market.db without --force: {db}")
        return 3

    conn = sqlite3.connect(db, timeout=120)
    try:
        # مهاجرت باید قبل از backfill اجرا شود (ستون‌ها وجود داشته باشند).
        cf.create_schema(conn)
        cf.migrate_schema(conn)
        before = _stats(conn)
        print(f"[.. ] {label}before: fs unit_norm null={before['fs_unit_norm_null']}/"
              f"{before['fs_total']}  ms y/m null={before['ms_ym_null']}/{before['ms_total']}")

        st = cf.backfill_derived(conn, verbose=True)
        after = _stats(conn)
        print(f"[OK ] {label}after:  fs unit_norm null={after['fs_unit_norm_null']}/"
              f"{after['fs_total']}  ms y/m null={after['ms_ym_null']}/{after['ms_total']}")
        print(f"[OK ] unit_norm distribution: {after['unit_norm_dist']}")

        # ۱) یدم‌پذیری: اجرای دوم نباید هیچ ردیفی را واقعاً تغییر دهد.
        # نکته: fs_filled ردیف‌های NULL را می‌شمارد، و ردیف‌هایی که unit آنها
        # NULL است به‌حق unit_norm=NULL نگه‌می‌دارند → دوباره match می‌شوند ولی
        # تغییری نمی‌کنند. معیارِ درست: total_changesِ SQLite (جهشِ واقعی).
        before_changes = conn.execute("SELECT total_changes()").fetchone()[0]
        cf.backfill_derived(conn, verbose=False)
        mutated = conn.execute("SELECT total_changes()").fetchone()[0] - before_changes
        if mutated:
            print(f"[FAIL] NOT idempotent: second run mutated {mutated} rows")
            return 4
        print("[OK ] idempotent: second run mutated 0 rows")

        # ۲) هم‌خوانی با fts_engine (منبع یگانه حقیقت)
        n, bad = _verify_against_engine(conn)
        if bad:
            print(f"[FAIL] {bad}/{n*2} sampled fields disagree with fts_engine")
            return 5
        print(f"[OK ] {n} sampled rows agree with fts_engine._is_audited/_is_consolidated")

        # ۳) یکتاییِ کلیدِ اصلی و یکپارچگی
        dup = conn.execute(
            "SELECT COUNT(*) FROM (SELECT tracing_no FROM financial_statements "
            "GROUP BY tracing_no HAVING COUNT(*)>1)").fetchone()[0]
        ic = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if dup or ic != "ok":
            print(f"[FAIL] integrity: dups={dup} integrity_check={ic}")
            return 6
        print(f"[OK ] integrity_check={ic}, no duplicate tracing_no")

        # ۴) ایندکسِ جدید واقعاً قابلِ استفاده است (year دیگر NULL نیست)
        if before["ms_ym_null"] and after["ms_ym_null"] == 0:
            q = conn.execute(
                "SELECT COUNT(*) FROM monthly_sales INDEXED BY ix_ms_sym_ym "
                "WHERE symbol=(SELECT symbol FROM monthly_sales LIMIT 1)").fetchone()[0]
            print(f"[OK ] ix_ms_sym_ym usable (matched {q} rows for a sample symbol)")
        return 0
    finally:
        conn.close()


def selftest():
    """سناریوهایِ کوچک روی دیسکِ تازه: صحتِ طبقه‌بندی + NULL semantics."""
    db = os.path.join(tempfile.mkdtemp(prefix="bors_bb_st_"), "st.db")
    conn = sqlite3.connect(db, timeout=60)
    cf.create_schema(conn)
    cf.migrate_schema(conn)
    # unit با نوشتارِ عربی + ZWNJ (سخت‌ترین حالتِ واقعی)
    # ترتیب: FS_COLS = ۸ سرستون + FS_KEYS(۱۰) + unit/url/fetched_at
    #        + ۴ ستونِ مشتق (گام ۳۴: حالا موقعِ درج محاسبه می‌شوند)
    conn.execute(cf.FS_UPSERT, (1, "آ", "شرکت", "صورت‌های مالی سال مالی (حسابرسی شده)",
                                "Financial Statements", 12, "1404/12/29", "1405/03/01",
                                100.0, 20.0, 15.0, 8.0, 50.0, 25.0, 25.0, 10.0, 4.0, 1.0,
                                "کليه مبالغ به ميليون ريال است", "http://x", "2026")
                 + cf.fs_derived("صورت‌های مالی سال مالی (حسابرسی شده)", "1404/12/29",
                                 "کليه مبالغ به ميليون ريال است"))
    # حسابرسی‌نشده + اصلاحیه (و نه تلفیقی)
    conn.execute(cf.FS_UPSERT, (2, "ب", "شرکت", "اطلاعات میاندوره‌ای (حسابرسی نشده)(اصلاحیه)",
                                "Financial Statements", 6, "1404/06/31", "1405/01/01",
                                None, None, None, None, None, None, None, None, None, None,
                                "کلیه‌ی مبالغ به میلیون ريال می‌باشد", "http://y", "2026")
                 + cf.fs_derived("اطلاعات میاندوره‌ای (حسابرسی نشده)(اصلاحیه)",
                                 "1404/06/31", "کلیه‌ی مبالغ به میلیون ريال می‌باشد"))
    # تلفیقی + حسابرسی‌شده؛ unit نامعلوم → unit_norm باید NULL بماند
    conn.execute(cf.FS_UPSERT, (3, "ج", "شرکت", "صورت‌های مالی تلفیقی (حسابرسی شده)",
                                "Financial Statements", 12, "1403/12/30", "1404/01/01",
                                1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
                                None, "http://z", "2026")
                 + cf.fs_derived("صورت‌های مالی تلفیقی (حسابرسی شده)", "1403/12/30", None))
    # monthly_sales با year/month خالی (ردیفِ قدیمی) + حجم (F-01)
    conn.execute(cf.MS_UPSERT, (11, "آ", "ماهانه", "1404/12/29", None, None,
                                10.0, 120.0, 9.0, 100.0,
                                1.5, 18.0, "تن", "p", "e"))
    # حالتِ واقعیِ کشف‌شده روی market.db: period_end کل NULL است و تاریخ فقط
    # در عنوان است — با ارقامِ فارسی (ردیف‌های ۱۳۹۴ نمادِ خعمرا). بدونِ
    # fallbackِ عنوان، year/month برای همیشه NULL می‌ماند و ix_ms_sym_ym
    # آن‌ها را پوشش نمی‌دهد.
    conn.execute(cf.MS_UPSERT, (12, "خعمرا",
                                "گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به ۱۳۹۴/۰۹/۳۰",
                                None, None, None,
                                5.0, 50.0, 4.0, 40.0,
                                None, None, None, "p2", "e2"))
    # عنوان با دو فاصله قبل از تاریخ (ردیف‌های ۱۴۰۲ وسمهر)
    conn.execute(cf.MS_UPSERT, (13, "وسمهر",
                                "گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به  ۱۴۰۲/۱۰/۳۰",
                                None, None, None,
                                6.0, 60.0, 5.0, 50.0,
                                2.0, 22.0, "کیلوگرم", "p3", "e3"))
    conn.commit()

    st = cf.backfill_derived(conn, verbose=False)
    checks = []
    # گام ۳۴: ردیف‌های تازه با fs_derived درج می‌شوند، پس backfill_derived
    # دیگر نباید چیزی برای پر کردن پیدا کند (fs_filled=0). اگر >0 شد یعنی
    # پایپ‌لاینِ درج، ستونِ مشتق را جا انداخته — همان باگی که این گام
    # قرار بود برای همیشه ببندد.
    checks.append(("fs_filled=0 (insert path already populates derived)",
                   st["fs_filled"] == 0))
    # گام ۳۴: ردیف‌های تازه با fs_derived درج شده‌اند و نباید نیازی به
    # backfill داشته باشند — این همان قراردادی است که از این پس پایپ‌لاینِ
    # آپدیت رعایت می‌کند.
    checks.append(("row1 derived at insert (audited/consol/year/unit)",
                   conn.execute("SELECT is_audited,is_consolidated,fiscal_year,unit_norm "
                                "FROM financial_statements WHERE tracing_no=1").fetchone()
                   == (1, 0, "1404", "mrl")))
    checks.append(("row3 derived at insert (consol=1, unit NULL)",
                   conn.execute("SELECT is_consolidated,unit_norm FROM financial_statements "
                                "WHERE tracing_no=3").fetchone() == (1, None)))
    r1 = conn.execute("SELECT is_audited,is_consolidated,fiscal_year,unit_norm "
                      "FROM financial_statements WHERE tracing_no=1").fetchone()
    r2 = conn.execute("SELECT is_audited,is_consolidated,fiscal_year,unit_norm "
                      "FROM financial_statements WHERE tracing_no=2").fetchone()
    r3 = conn.execute("SELECT unit_norm FROM financial_statements WHERE tracing_no=3").fetchone()
    checks.append(("row1 audited=1 consol=0 year=1404 unit=mrl", r1 == (1, 0, "1404", "mrl")))
    checks.append(("row2 audited=0 (real unaudited, not unknown)", r2[0] == 0))
    checks.append(("row2 consolidated=0 (no تلفیقی token)", r2[1] == 0))
    checks.append(("row2 unit=mrl (ZWNJ+arabic variant)", r2[3] == "mrl"))
    checks.append(("row3 unit_norm NULL = unknown", r3[0] is None))
    r3b = conn.execute("SELECT is_audited,is_consolidated FROM financial_statements "
                       "WHERE tracing_no=3").fetchone()
    checks.append(("row3 audited=1 consol=1 (تلفیقی)", r3b == (1, 1)))
    ym = conn.execute("SELECT year,month FROM monthly_sales WHERE tracing_no=11").fetchone()
    checks.append(("ms year/month backfilled 1404/12", ym == (1404, 12)))
    # fallbackِ عنوان: period_end NULL ولی تاریخ فقط در عنوان است (ارقامِ فارسی)
    ym12 = conn.execute("SELECT year,month FROM monthly_sales WHERE tracing_no=12").fetchone()
    checks.append(("ms y/m from title when period_end NULL (fa digits)",
                   ym12 == (1394, 9)))
    ym13 = conn.execute("SELECT year,month FROM monthly_sales WHERE tracing_no=13").fetchone()
    checks.append(("ms y/m from title with double space", ym13 == (1402, 10)))
    # ستون‌های حجم (F-01): MS_UPSERT باید ۱۵ ستون را بدون جابه‌جایی بپذیرد
    vol = conn.execute("SELECT monthly_volume,ytd_volume,volume_unit "
                       "FROM monthly_sales WHERE tracing_no=11").fetchone()
    checks.append(("ms volume columns survive round-trip", vol == (1.5, 18.0, "تن")))
    vol13 = conn.execute("SELECT monthly_volume,volume_unit "
                         "FROM monthly_sales WHERE tracing_no=13").fetchone()
    checks.append(("ms volume unit per-row (کیلوگرم)", vol13 == (2.0, "کیلوگرم")))
    vol12 = conn.execute("SELECT monthly_volume,ytd_volume,volume_unit "
                         "FROM monthly_sales WHERE tracing_no=12").fetchone()
    checks.append(("ms volume NULL allowed (no volume in old reports)",
                   vol12 == (None, None, None)))
    # NULL semantics: is_audited واقعاً ۰ است نه NULL
    checks.append(("is_audited NOT NULL (0 means unaudited)",
                   conn.execute("SELECT COUNT(*) FROM financial_statements "
                                "WHERE is_audited IS NULL").fetchone()[0] == 0))
    ok = True
    for name, passed in checks:
        print(f"  [{'OK ' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    conn.close()
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="offline backfill of FTS v2.2 derived columns")
    ap.add_argument("db", nargs="?", help="path to a COPY of market.db")
    ap.add_argument("--force", action="store_true",
                    help="allow running on the live market.db (dangerous)")
    ap.add_argument("--selftest", action="store_true",
                    help="run small synthetic scenarios on a fresh disk")
    ap.add_argument("--fresh", action="store_true",
                    help="extract a pristine copy from market.db.lzma and backfill it")
    a = ap.parse_args()

    if a.selftest:
        print("[.. ] selftest on synthetic rows")
        rc = selftest()
        print(f"[{'DONE' if rc == 0 else 'FAIL'}] selftest rc={rc}")
        return rc

    if a.fresh or not a.db:
        db = _fresh_copy()
        print(f"[.. ] extracted pristine copy: {db}")
    else:
        db = os.path.abspath(a.db)
    rc = run(db, force=a.force, label="")
    print(f"[{'DONE' if rc == 0 else 'FAIL'}] backfill rc={rc}  db={db}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
