"""db_gap_audit.py — بازرسیِ تکرارپذیرِ شکاف‌های دیتابیس بازار (فقط‌خواندنی، stdlib).

هدف: هر بار قبل از انتشار، «شکاف‌های داده» را عدد‌به‌عدد ببینیم تا نه UI و نه نشانگرهای
FTS با مقدارِ غایب توجیه‌نشده روبه‌رو نشوند. هیچ‌چیز را تغییر نمی‌دهد.

اجرا:
  python dev/db_gap_audit.py --db market.db
  python dev/db_gap_audit.py --db market.db --json out.json
"""
from __future__ import annotations
import argparse, json, os, sqlite3, sys

TABLES = ["instruments", "financial_statements", "monthly_sales", "market_watch", "daily_prices", "fts_results"]


def nulls(cur, table, cols):
    out = {}
    for c in cols:
        try:
            n = cur.execute(f'SELECT SUM(CASE WHEN "{c}" IS NULL THEN 1 ELSE 0 END) FROM "{table}"').fetchone()[0]
            t = cur.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            out[c] = {"nulls": n, "total": t}
        except Exception:
            pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--json")
    a = ap.parse_args()
    if not os.path.exists(a.db):
        print(f"[FAIL] db not found: {a.db}")
        return 2
    con = sqlite3.connect(a.db)
    cur = con.cursor()
    report = {"db": a.db, "integrity": None, "fk": None, "counts": {}, "nulls": {}, "coverage": {}, "flags": {}}

    report["integrity"] = cur.execute("PRAGMA integrity_check").fetchone()[0]
    fk = cur.execute("PRAGMA foreign_key_check").fetchall()
    report["fk"] = len(fk)

    for t in TABLES:
        try:
            report["counts"][t] = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except Exception:
            report["counts"][t] = None

    report["nulls"]["financial_statements"] = nulls(cur, "financial_statements",
        ["revenue", "gross_profit", "operating_profit", "net_profit", "total_equity", "capital", "basic_eps", "period_end"])
    report["nulls"]["monthly_sales"] = nulls(cur, "monthly_sales",
        ["monthly_revenue", "ytd_revenue", "monthly_revenue_prev", "ytd_revenue_prev", "monthly_volume", "ytd_volume", "period_end"])
    report["nulls"]["market_watch"] = nulls(cur, "market_watch", ["p_closing", "p_last", "eps", "pe", "price_yesterday"])

    # شاخص‌های پرچم‌دار
    try:
        report["flags"]["pe_zero"] = cur.execute("SELECT COUNT(*) FROM market_watch WHERE pe = 0").fetchone()[0]
        report["flags"]["pe_negative"] = cur.execute("SELECT COUNT(*) FROM market_watch WHERE pe < 0").fetchone()[0]
        report["flags"]["price_yesterday_sentinel_1"] = cur.execute("SELECT COUNT(*) FROM market_watch WHERE price_yesterday = 1").fetchone()[0]
    except Exception:
        pass
    # شکافِ نشانگر رشد: چند ردیفِ NULL با سابقهٔ سالِ قبل قابل پرکردن است
    try:
        report["coverage"]["growth_backfillable"] = cur.execute("""
            SELECT COUNT(*) FROM monthly_sales ms
            JOIN monthly_sales p ON p.symbol=ms.symbol AND p.month=ms.month AND p.year=ms.year-1
            WHERE ms.monthly_revenue_prev IS NULL AND p.monthly_revenue IS NOT NULL""").fetchone()[0]
    except Exception:
        pass
    try:
        report["coverage"]["fs_symbols"] = cur.execute("SELECT COUNT(DISTINCT symbol) FROM financial_statements").fetchone()[0]
        report["coverage"]["instruments_total"] = cur.execute("SELECT COUNT(*) FROM instruments").fetchone()[0]
    except Exception:
        pass
    con.close()

    print(f"integrity={report['integrity']}  foreign_key_violations={report['fk']}")
    print("counts:", json.dumps(report["counts"], ensure_ascii=False))
    for t, d in report["nulls"].items():
        print(f"\n[{t}] nulls")
        for c, v in d.items():
            print(f"  {c:24} {v['nulls']}/{v['total']}")
    print("\nflags:", json.dumps(report["flags"], ensure_ascii=False))
    print("coverage:", json.dumps(report["coverage"], ensure_ascii=False))

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n[json] wrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
