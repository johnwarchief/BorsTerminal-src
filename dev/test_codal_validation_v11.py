# -*- coding: utf-8 -*-
"""گیت‌های اعتبارسنجیِ staging — تستِ v11 (بدونِ شبکه، فقط DBهایِ موقت).

ستون‌هایِ هر سه جدول عیناً همان ستون‌هایِ واقعیِ `market.db` هستند:
  • `codal_notices`         — url/publish_date
  • `financial_statements`  — revenue/gross_profit/url/publish_date/period_end
  • `monthly_sales`         — monthly_revenue/ytd_revenue/pdf_url/excel_url/period_end
    (این جدول gross_profit و url و publish_date ندارد — اصلاحِ پلن)

هر سناریو یک جفت DB موقت در TMP می‌سازد؛ `market.db` عملیاتی هرگز باز/نوشته نمی‌شود.
"""
import os
import shutil
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "dev"))
from codal_validation import validate_staging  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DDL = """
CREATE TABLE codal_notices (
    tracing_no INTEGER, symbol TEXT, company_name TEXT, title TEXT,
    letter_code TEXT, publish_date TEXT, sent_date TEXT, url TEXT,
    fetched_at TEXT, pdf_url TEXT, excel_url TEXT);
CREATE TABLE financial_statements (
    tracing_no INTEGER, symbol TEXT, company_name TEXT, title TEXT,
    report_kind TEXT, period_months INTEGER, period_end TEXT,
    publish_date TEXT, revenue REAL, gross_profit REAL,
    operating_profit REAL, net_profit REAL, total_assets REAL,
    total_liabilities REAL, total_equity REAL, capital REAL,
    retained_earnings REAL, basic_eps REAL, unit TEXT, url TEXT,
    fetched_at TEXT, is_audited INTEGER, is_consolidated INTEGER,
    fiscal_year TEXT, unit_norm TEXT, has_operating_sales INTEGER);
CREATE TABLE monthly_sales (
    tracing_no INTEGER, symbol TEXT, title TEXT, period_end TEXT,
    year INTEGER, month INTEGER, monthly_revenue REAL, ytd_revenue REAL,
    monthly_revenue_prev REAL, ytd_revenue_prev REAL, pdf_url TEXT,
    excel_url TEXT, monthly_volume REAL, ytd_volume REAL, volume_unit TEXT);
"""

FS1 = {"tracing_no": 1, "symbol": "A", "title": "t", "period_end": "1404/12/29",
       "revenue": 100.0, "gross_profit": 50.0, "url": "https://codal.ir/fs/1",
       "publish_date": "1405/07/01"}
FS2 = {"tracing_no": 2, "symbol": "B", "title": "t", "period_end": "1405/06/31",
       "revenue": 200.0, "gross_profit": 80.0, "url": "https://codal.ir/fs/2",
       "publish_date": "1405/07/02"}
MS10 = {"tracing_no": 10, "symbol": "A", "title": "t", "period_end": "1405/06/31",
        "monthly_revenue": 30.0, "ytd_revenue": 100.0,
        "pdf_url": "https://codal.ir/ms/10", "excel_url": None}
CN100 = {"tracing_no": 100, "symbol": "A", "title": "t",
         "publish_date": "1405/07/01", "url": "https://codal.ir/n/100"}

TMP = tempfile.mkdtemp(prefix="codal_validation_v11_")
FAILS = []


def ck(cond, msg):
    print("  %s %s" % ("PASS" if cond else "FAIL", msg))
    if not cond:
        FAILS.append(msg)


def write_db(path, fs_rows=(), ms_rows=(), cn_rows=(), ddl=DDL):
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    conn.executescript(ddl)
    for table, rows in (("financial_statements", fs_rows),
                        ("monthly_sales", ms_rows),
                        ("codal_notices", cn_rows)):
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                              "AND name=?", (table,)).fetchone()
        if not exists:
            continue
        for row in rows:
            cols = list(row)
            conn.execute("INSERT INTO %s (%s) VALUES (%s)" % (
                table, ",".join(cols), ",".join("?" * len(cols))),
                [row[c] for c in cols])
    conn.commit()
    conn.close()


def pair(name):
    d = os.path.join(TMP, name)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "main.db"), os.path.join(d, "staging.db")


def add(path, table, row):
    conn = sqlite3.connect(path)
    cols = list(row)
    conn.execute("INSERT INTO %s (%s) VALUES (%s)" % (
        table, ",".join(cols), ",".join("?" * len(cols))),
        [row[c] for c in cols])
    conn.commit()
    conn.close()


def base_pair(name, stg_extra_fs=()):
    m, s = pair(name)
    write_db(m, [FS1], [MS10], [CN100])
    write_db(s, [FS1] + list(stg_extra_fs), [MS10], [CN100])
    return m, s


try:
    # ── ۱) مسیرِ سالم: یک ردیفِ FS اضافه در staging ──────────────────────────
    m, s = base_pair("happy", [FS2])
    r = validate_staging(m, s, None)
    ck(r["ok"] is True, "happy: ok is True (%r)" % (r["errors"],))
    ck(r["errors"] == [], "happy: errors empty (%r)" % (r["errors"],))
    ck(isinstance(r["warnings"], list), "happy: warnings is a list")
    ck(r["stats"]["codal_notices"] == {"main": 1, "staging": 1},
       "happy: notices counts main=1 staging=1 (%r)" % (r["stats"]["codal_notices"],))
    ck(r["stats"]["financial_statements"] == {"main": 1, "staging": 2},
       "happy: fs counts main=1 staging=2 (%r)" % (r["stats"]["financial_statements"],))
    ck(r["stats"]["monthly_sales"] == {"main": 1, "staging": 1},
       "happy: ms counts main=1 staging=1 (%r)" % (r["stats"]["monthly_sales"],))
    ck(r["stats"]["fs_latest"] == "1405/06/31",
       "happy: fs_latest=1405/06/31 (%r)" % (r["stats"]["fs_latest"],))
    ck(r["stats"]["ms_latest"] == "1405/06/31",
       "happy: ms_latest=1405/06/31 (%r)" % (r["stats"]["ms_latest"],))

    # ── ۲) فروشِ منفی در FS ─────────────────────────────────────────────────
    m, s = base_pair("neg_fs")
    add(s, "financial_statements",
        dict(FS2, tracing_no=3, revenue=-5.0, gross_profit=-10.0))
    r = validate_staging(m, s, None)
    ck(r["ok"] is False, "negative_revenue: ok is False")
    ck(any("negative_revenue" in e for e in r["errors"]),
       "negative_revenue: error code (%r)" % (r["errors"],))

    # ── ۳) tracing_no تکراری در هر سه جدول ──────────────────────────────────
    m, s = base_pair("dupes", [FS2])
    add(s, "financial_statements", dict(FS2, symbol="B2"))
    add(s, "monthly_sales", dict(MS10, symbol="A2"))
    add(s, "codal_notices", dict(CN100, symbol="A2"))
    r = validate_staging(m, s, None)
    ck(r["ok"] is False, "duplicate: ok is False")
    for t in ("codal_notices", "financial_statements", "monthly_sales"):
        ck(any("%s_duplicate_tracing_no" % t in e for e in r["errors"]),
           "duplicate: %s detected (%r)" % (t, r["errors"]))

    # ── ۴) provenance ناقص در FS ─────────────────────────────────────────────
    m, s = base_pair("fs_prov")
    add(s, "financial_statements",
        dict(FS2, tracing_no=3, url="", publish_date="1405/07/02"))
    r = validate_staging(m, s, None)
    ck(r["ok"] is False, "fs provenance: ok is False")
    ck(any("financial_statements" in e and "missing_provenance" in e
           for e in r["errors"]),
       "fs provenance: missing_provenance (%r)" % (r["errors"],))

    # ── ۵) gross_profit > revenue در FS ─────────────────────────────────────
    m, s = base_pair("fs_gross")
    add(s, "financial_statements",
        dict(FS2, tracing_no=3, revenue=100.0, gross_profit=150.0))
    r = validate_staging(m, s, None)
    ck(r["ok"] is False, "gross>revenue: ok is False")
    ck(any("gross_gt_revenue" in e for e in r["errors"]),
       "gross>revenue: error code (%r)" % (r["errors"],))

    # ── ۶) دورهٔ آینده در FS ────────────────────────────────────────────────
    m, s = base_pair("fs_future")
    add(s, "financial_statements", dict(FS2, tracing_no=3, period_end="1406/01/01"))
    r = validate_staging(m, s, None)
    ck(r["ok"] is False, "future FS: ok is False")
    ck(any("future_period" in e for e in r["errors"]),
       "future FS: future_period (%r)" % (r["errors"],))

    # ── ۷) پس‌رفتِ دوره در FS (بدونِ افتِ پوشش) ─────────────────────────────
    m, s = pair("fs_regress")
    write_db(m, [FS1, FS2], [MS10], [CN100])
    write_db(s, [FS1, dict(FS2, tracing_no=3, period_end="1404/12/30")],
             [MS10], [CN100])
    r = validate_staging(m, s, None)
    ck(r["ok"] is False, "fs regressed: ok is False")
    ck(any("fs_period_regressed" in e for e in r["errors"]),
       "fs regressed: fs_period_regressed (%r)" % (r["errors"],))

    # ── ۸) افتِ پوشش: staging کمتر از ۹۵٪ main ──────────────────────────────
    m, s = pair("coverage")
    main_fs = [dict(FS1, tracing_no=i, period_end="1405/06/01") for i in range(1, 41)]
    stg_fs = [dict(FS1, tracing_no=i, period_end="1405/06/01") for i in range(1, 31)]
    write_db(m, main_fs, [MS10], [CN100])
    write_db(s, stg_fs, [MS10], [CN100])
    r = validate_staging(m, s, None)
    ck(r["ok"] is False, "coverage: ok is False")
    ck(any("financial_statements_coverage_drop" in e for e in r["errors"]),
       "coverage: 30/40 detected (%r)" % (r["errors"],))
    ck(r["stats"]["financial_statements"] == {"main": 40, "staging": 30},
       "coverage: stats main=40 staging=30")

    # ── ۹) provenance ماهانه: نه pdf_url نه excel_url ───────────────────────
    m, s = base_pair("ms_prov")
    add(s, "monthly_sales",
        dict(MS10, tracing_no=11, pdf_url=None, excel_url=""))
    r = validate_staging(m, s, None)
    ck(r["ok"] is False, "ms provenance: ok is False")
    ck(any("monthly_sales" in e and "missing_provenance" in e
           for e in r["errors"]),
       "ms provenance: missing_provenance (%r)" % (r["errors"],))

    # ── ۱۰) فروشِ ماهانهٔ منفی (بدونِ gross>revenue روی این جدول) ────────────
    m, s = base_pair("ms_neg")
    add(s, "monthly_sales",
        dict(MS10, tracing_no=11, monthly_revenue=-1.0, ytd_revenue=10.0))
    r = validate_staging(m, s, None)
    ck(r["ok"] is False, "ms negative: ok is False")
    ck(any("negative_revenue" in e for e in r["errors"]),
       "ms negative: negative_revenue (%r)" % (r["errors"],))
    ck(not any("gross_gt_revenue" in e for e in r["errors"]),
       "ms negative: no gross_gt_revenue on monthly_sales")

    # ── ۱۱) دورهٔ آینده در MS ───────────────────────────────────────────────
    m, s = base_pair("ms_future")
    add(s, "monthly_sales", dict(MS10, tracing_no=11, period_end="1406/02/01"))
    r = validate_staging(m, s, None)
    ck(r["ok"] is False, "future MS: ok is False")
    ck(any("future_period" in e for e in r["errors"]),
       "future MS: future_period (%r)" % (r["errors"],))

    # ── ۱۲) پس‌رفتِ دوره در MS (بدونِ افتِ پوشش) ────────────────────────────
    m, s = pair("ms_regress")
    ms11 = dict(MS10, tracing_no=11, period_end="1405/07/30")
    write_db(m, [FS1], [MS10, ms11], [CN100])
    write_db(s, [FS1], [MS10, dict(MS10, tracing_no=12, period_end="1405/05/31")],
             [CN100])
    r = validate_staging(m, s, None)
    ck(r["ok"] is False, "ms regressed: ok is False")
    ck(any("ms_period_regressed" in e for e in r["errors"]),
       "ms regressed: ms_period_regressed (%r)" % (r["errors"],))

    # ── ۱۳) provenance ناقص در codal_notices ────────────────────────────────
    m, s = base_pair("cn_prov")
    add(s, "codal_notices",
        dict(CN100, tracing_no=101, url="", publish_date="1405/07/01"))
    r = validate_staging(m, s, None)
    ck(r["ok"] is False, "notices provenance: ok is False")
    ck(any("codal_notices" in e and "missing_provenance" in e
           for e in r["errors"]),
       "notices provenance: missing_provenance (%r)" % (r["errors"],))

    # ── ۱۴) جدولِ غایب در staging: خطا، نه کرش ──────────────────────────────
    m, s = pair("missing_table")
    write_db(m, [FS1], [MS10], [CN100])
    write_db(s, [FS1], [], [CN100])
    conn = sqlite3.connect(s)
    conn.execute("DROP TABLE monthly_sales")
    conn.commit()
    conn.close()
    r = validate_staging(m, s, None)
    ck(r["ok"] is False, "missing table: ok is False")
    ck(any("monthly_sales_missing_table" in e for e in r["errors"]),
       "missing table: reported (%r)" % (r["errors"],))
    ck(r["stats"]["monthly_sales"] == {"main": 1, "staging": 0},
       "missing table: staging count 0 in stats")
    ck(r["stats"]["ms_latest"] is None, "missing table: ms_latest is None")

    # ── ۱۵) ستونِ غایب در staging: خطا، نه کرش ──────────────────────────────
    m, s = base_pair("missing_col", [FS2])
    conn = sqlite3.connect(s)
    conn.execute("ALTER TABLE financial_statements DROP COLUMN revenue")
    conn.commit()
    conn.close()
    r = validate_staging(m, s, None)
    ck(r["ok"] is False, "missing column: ok is False")
    ck(any("financial_statements_missing_column:revenue" in e
           for e in r["errors"]),
       "missing column: reported (%r)" % (r["errors"],))
    ck(r["stats"]["financial_statements"] == {"main": 1, "staging": 2},
       "missing column: counts still reported")

    # ── ۱۶) جدولِ غایب در main: هشدار، بدونِ کرش ────────────────────────────
    m, s = pair("main_missing_table")
    write_db(m, [FS1], [MS10], [CN100])
    write_db(s, [FS1, FS2], [MS10], [CN100])
    conn = sqlite3.connect(m)
    conn.execute("DROP TABLE codal_notices")
    conn.commit()
    conn.close()
    r = validate_staging(m, s, None)
    ck(r["ok"] is True, "main missing table: staging still valid (%r)" % (r["errors"],))
    ck(any("codal_notices_main_missing_table" in w for w in r["warnings"]),
       "main missing table: warning (%r)" % (r["warnings"],))
    ck(r["stats"]["codal_notices"] == {"main": 0, "staging": 1},
       "main missing table: main count 0")

    # ── ۱۷) main غایب: هشدار و عدمِ ساختِ فایل ──────────────────────────────
    m, s = pair("main_absent")
    if os.path.exists(m):
        os.remove(m)
    write_db(s, [FS1, FS2], [MS10], [CN100])
    r = validate_staging(m, s, None)
    ck(r["ok"] is True, "main absent: staging still valid (%r)" % (r["errors"],))
    ck(not os.path.exists(m), "main absent: validator did not create main.db")
    ck(any("main_db_unavailable" in w for w in r["warnings"]),
       "main absent: warning (%r)" % (r["warnings"],))

    # ── ۱۸) staging غایب: خطا و عدمِ ساختِ فایل ─────────────────────────────
    m, s = pair("staging_absent")
    if os.path.exists(s):
        os.remove(s)
    write_db(m, [FS1], [MS10], [CN100])
    r = validate_staging(m, s, None)
    ck(r["ok"] is False, "staging absent: ok is False")
    ck(not os.path.exists(s), "staging absent: validator did not create staging.db")
    ck(any("staging_db_unavailable" in e for e in r["errors"]),
       "staging absent: error (%r)" % (r["errors"],))

    # ── ۱۹) last_good: فقط هشدار، هرگز کرش ─────────────────────────────────
    m, s = base_pair("last_good", [FS2])
    lg = {"latest_financial_period": "1405/01/01",
          "latest_monthly_period": "1405/01/01",
          "row_counts": {"codal_notices": 1, "financial_statements": 1,
                         "monthly_sales": 1}}
    r = validate_staging(m, s, lg)
    ck(r["ok"] is True, "last_good: ok stays True")
    ck(any("last_good_checked" in w for w in r["warnings"]),
       "last_good: checked warning (%r)" % (r["warnings"],))

    r = validate_staging(m, s, {"latest_financial_period": "1405/12/30"})
    ck(r["ok"] is True, "last_good ahead: ok stays True")
    ck(any("last_good_fs_period_ahead" in w for w in r["warnings"]),
       "last_good ahead: warning (%r)" % (r["warnings"],))

    r = validate_staging(m, s, {"row_counts": {"financial_statements": 100}})
    ck(r["ok"] is True, "last_good count drop: ok stays True")
    ck(any("last_good_count_drop" in w for w in r["warnings"]),
       "last_good count drop: warning (%r)" % (r["warnings"],))

    for junk in ("not-a-dict", 123, object()):
        r = validate_staging(m, s, junk)
        ck(r["ok"] is True, "last_good junk %r: ok stays True" % (type(junk).__name__,))
        ck(any("last_good" in w for w in r["warnings"]),
           "last_good junk %r: warning (%r)" % (type(junk).__name__, r["warnings"]))

    r = validate_staging(m, s, {})
    ck(r["ok"] is True, "last_good empty dict: ok stays True")
    ck(any("last_good_checked" in w for w in r["warnings"]),
       "last_good empty dict: checked warning")
finally:
    shutil.rmtree(TMP, ignore_errors=True)

if FAILS:
    print("FAIL %d validation gate assertion(s)" % len(FAILS))
    sys.exit(1)
print("OK validation gates")
