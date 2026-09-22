"""backfill_prev_revenue.py — پرکردن آفلاینِ ستون‌های «دورهٔ مشابه سال قبل» (غیرمخرب).

چرا: نشانگر «۱ رشد کدال» به `monthly_revenue_prev` / `ytd_revenue_prev` وابسته است.
نویسندهٔ اصلی (`codal_fts_updater`) این ستون‌ها را وقتی پر می‌کند که ردیفِ سالِ قبل
از قبل در جدول باشد. اگر ترتیبِ درج رعایت نشده باشد، ردیف‌هایی که داده‌ی سال قبلشان
موجود است بی‌دلیل NULL می‌مانند. این اسکریپت فقط همان‌ها را پر می‌کند و هیچ عدد دیگری
را بازنویسی نمی‌کند (مقدارِ موجود دست‌نخورده می‌ماند).

اجرا (روی یک کپی؛ پیش‌فرض dry-run):
  python dev/backfill_prev_revenue.py --db market.db --dry-run
  python dev/backfill_prev_revenue.py --db market.db --apply
"""
from __future__ import annotations
import argparse, os, sqlite3, sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--apply", dest="dry_run", action="store_false")
    a = ap.parse_args()
    if not os.path.exists(a.db):
        print(f"[FAIL] db not found: {a.db}")
        return 2
    con = sqlite3.connect(a.db)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    def count(sql):
        return cur.execute(sql).fetchone()[0]

    # فقط ردیف‌هایی که ستونشان NULL است و ردیفِ year-1/month متناظر وجود دارد.
    mr_candidates = count("""
        SELECT COUNT(*) FROM monthly_sales ms
        JOIN monthly_sales p
          ON p.symbol = ms.symbol AND p.month = ms.month AND p.year = ms.year - 1
        WHERE ms.monthly_revenue_prev IS NULL AND p.monthly_revenue IS NOT NULL
    """)
    ytd_candidates = count("""
        SELECT COUNT(*) FROM monthly_sales ms
        JOIN monthly_sales p
          ON p.symbol = ms.symbol AND p.month = ms.month AND p.year = ms.year - 1
        WHERE ms.ytd_revenue_prev IS NULL AND p.ytd_revenue IS NOT NULL
    """)
    print(f"[info] monthly_revenue_prev backfillable: {mr_candidates}")
    print(f"[info] ytd_revenue_prev     backfillable: {ytd_candidates}")

    if a.dry_run:
        print("[dry-run] no changes written. pass --apply to write.")
        return 0

    cur.execute("""
        UPDATE monthly_sales AS ms
        SET monthly_revenue_prev = (
            SELECT p.monthly_revenue FROM monthly_sales p
            WHERE p.symbol = ms.symbol AND p.month = ms.month AND p.year = ms.year - 1
              AND p.monthly_revenue IS NOT NULL LIMIT 1)
        WHERE ms.monthly_revenue_prev IS NULL
          AND EXISTS (SELECT 1 FROM monthly_sales p
                      WHERE p.symbol = ms.symbol AND p.month = ms.month
                        AND p.year = ms.year - 1 AND p.monthly_revenue IS NOT NULL)
    """)
    mr_done = cur.rowcount
    cur.execute("""
        UPDATE monthly_sales AS ms
        SET ytd_revenue_prev = (
            SELECT p.ytd_revenue FROM monthly_sales p
            WHERE p.symbol = ms.symbol AND p.month = ms.month AND p.year = ms.year - 1
              AND p.ytd_revenue IS NOT NULL LIMIT 1)
        WHERE ms.ytd_revenue_prev IS NULL
          AND EXISTS (SELECT 1 FROM monthly_sales p
                      WHERE p.symbol = ms.symbol AND p.month = ms.month
                        AND p.year = ms.year - 1 AND p.ytd_revenue IS NOT NULL)
    """)
    ytd_done = cur.rowcount
    con.commit()

    mr_left = count("SELECT COUNT(*) FROM monthly_sales WHERE monthly_revenue_prev IS NULL")
    ytd_left = count("SELECT COUNT(*) FROM monthly_sales WHERE ytd_revenue_prev IS NULL")
    print(f"[apply] monthly_revenue_prev filled: {mr_done} (null-left: {mr_left})")
    print(f"[apply] ytd_revenue_prev     filled: {ytd_done} (null-left: {ytd_left})")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
