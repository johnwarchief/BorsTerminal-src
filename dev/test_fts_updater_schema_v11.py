# -*- coding: utf-8 -*-
"""آپدیتر باید با اسکیمای ۲۶ ستونیِ financial_statements هم‌خوان باشد.

قرارداد: `save_annual(conn, L, vals, meta, unit)` یک ردیف با هر ۲۶ ستون
می‌نویسد؛ ۲۱ مقدارِ موجود به همان ترتیبِ قبلی می‌مانند و ۵ مقدارِ مشتق
(is_audited, is_consolidated, fiscal_year, unit_norm, has_operating_sales)
در همین درج محاسبه می‌شوند. DB فقط در حافظه است — market.db هرگز لمس نمی‌شود.
"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "dev"))
import codal_fetcher as cf                      # noqa: E402
from codal_fts_updater import save_annual       # noqa: E402

c = sqlite3.connect(":memory:")
cf.create_schema(c)
cf.migrate_schema(c)
L = {"TracingNo": 900001, "Symbol": "TEST", "CompanyName": "تست",
     "Title": "صورت مالی سالانه حسابرسی شده", "LetterCode": "x",
     "PublishDateTime": "1405/07/01", "Url": "/Reports/Decision.aspx?x"}
vals = {k: 100.0 for k in cf.FS_KEYS}
vals.update({"revenue": 1000.0, "gross_profit": 500.0, "net_profit": 200.0,
             "basic_eps": 10.0})
meta = {"period": "12", "end": "1404/12/29"}
save_annual(c, L, vals, meta, "میلیون ریال")
row = c.execute("SELECT COUNT(*), is_audited, is_consolidated, fiscal_year, "
                "unit_norm, has_operating_sales FROM financial_statements "
                "WHERE tracing_no=900001").fetchone()
assert row[0] == 1 and row[2] == 0 and row[3] == "1404", row
assert row[1] == 1, row            # عنوان «حسابرسی شده» → is_audited=1
assert row[4] == "mrl", row        # «میلیون ریال» → unit_norm='mrl'
assert row[5] is None, row         # آپدیتر شاهدِ has_income ندارد → «نامعلوم»

# ۲۶ ستون، یک ردیف، و ۲۱ مقدارِ موجود بدون جابه‌جایی در ستونِ درست نشسته‌اند.
ncols = len(c.execute("PRAGMA table_info(financial_statements)").fetchall())
assert ncols == 26, ncols
assert c.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0] == 1
base = c.execute(
    "SELECT symbol, company_name, report_kind, period_months, period_end, "
    "revenue, gross_profit, net_profit, basic_eps, unit, url "
    "FROM financial_statements WHERE tracing_no=900001").fetchone()
assert base[0] == "TEST" and base[1] == "تست", base
assert base[2] == "Financial Statements" and base[3] == 12, base
assert base[4] == "1404/12/29", base
assert base[5] == 1000.0 and base[6] == 500.0 and base[7] == 200.0, base
assert base[8] == 10.0 and base[9] == "میلیون ریال", base
assert base[10] == "https://codal.ir/Reports/Decision.aspx?x", base
print("OK updater schema")
