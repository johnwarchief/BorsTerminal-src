"""dev/repair_fund_revenue.py — پاک‌کردنِ فروشِ تاریخِ مصرف‌شده در ردیف‌های صندوق

چرا: پارسِ فعلی دیگر «سود سهام» را فروش نمی‌گذارد (dev/test_fund_revenue_v1027
همین را قفل می‌کند)، ولی ردیف‌هایی که با نسخهٔ قدیمی ذخیره شده‌اند همان عددِ
غلط را carry می‌کنند — مثل آلا 1404/09/30 که فروشش 21,390 است، یعنی ردیفِ
«سود سهام»ِ سالِ قبل، در حالی که سود خالصِ همان دوره 3,839,775 است.

تشخیصِ بی‌نیاز از شبکه: برای صندوق، «جمع درآمدها» همیشه ≥ سود خالص است
(سود خالص = جمع درآمدها − هزينه‌ها). پس هر ردیفِ صندوقی که فروشش از سود خالصِ
خودش کمتر باشد، فروشش ردیفِ جمع نیست → باید خالی شود. این قاعده هیچ عددِ
سالمی را نمی‌زند (ساحل: 17,150,873 ≥ 16,720,645 می‌ماند).

پیش‌نمایش (پیش‌فرض):   python dev/repair_fund_revenue.py
اعمال + بکاپِ جدول:    python dev/repair_fund_revenue.py --apply

بازگشت: ردیف‌های دست‌خورده در جدولِ financial_statements_rev_backup می‌مانند:
  UPDATE financial_statements SET revenue=(SELECT b.revenue FROM financial_statements_rev_backup b WHERE b.tracing_no=financial_statements.tracing_no)
"""
import argparse
import sqlite3
import sys

WHERE = ("ifnull(has_operating_sales,-1)=0 AND revenue IS NOT NULL "
         "AND net_profit IS NOT NULL AND net_profit > 0 AND revenue < net_profit")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    con = sqlite3.connect(args.db)
    rows = con.execute(
        "SELECT tracing_no, symbol, period_end, revenue, net_profit "
        "FROM financial_statements WHERE " + WHERE).fetchall()
    print("%d ردیف صندوق فروشِ کوچک‌تر از سود خالص دارد (محال است)" % len(rows))
    for r in rows[:8]:
        print("   ", r[1], r[2], "revenue=%s net=%s" % (f"{r[3]:,.0f}", f"{r[4]:,.0f}"))
    if len(rows) > 8:
        print("    … و %d تای دیگر" % (len(rows) - 8))

    if not args.apply:
        print("\nپیش‌نمایش؛ چیزی عوض نشد. برای اعمال --apply بدهید.")
        return 0

    con.execute("CREATE TABLE IF NOT EXISTS financial_statements_rev_backup "
                "(tracing_no INTEGER PRIMARY KEY, symbol TEXT, period_end TEXT, "
                " revenue REAL, repaired_at TEXT DEFAULT (datetime('now')))")
    con.executemany("INSERT OR REPLACE INTO financial_statements_rev_backup "
                    "(tracing_no, symbol, period_end, revenue) VALUES (?,?,?,?)",
                    [(r[0], r[1], r[2], r[3]) for r in rows])
    con.executemany("UPDATE financial_statements SET revenue=NULL WHERE tracing_no=?",
                    [(r[0],) for r in rows])
    con.commit()
    left = con.execute("SELECT count(*) FROM financial_statements WHERE " + WHERE).fetchone()[0]
    print("\n%d ردیف NULL شد؛ باقی‌ماندهٔ محال = %d" % (len(rows), left))
    return 0 if left == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
