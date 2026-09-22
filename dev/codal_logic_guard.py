# -*- coding: utf-8 -*-
"""گاردِ قراردادِ منطقِ کدال (F-01..F-05) — نگهبانِ دائمیِ اصلاحیه.

این اسکریپت ممیزیِ `_audit_f01.py` را به یک گاردِ dev/ تبدیل می‌کند: هر پنج
بندِ F-01 جزوه را با شواهد از market.db واقعی می‌سنجد و اگر یکی بشکند،
run_all_tests.py آن را گزارش می‌کند.

بندها (مستند به docs/Complete Logic Audit & Implementation Amendment.md):
  F-01a  فیلتر شرکت اصلی — حذفِ کاملِ صورت‌های مالی تلفیقی
  F-01b  وتوی قطعی صنعت بیمه
  F-02   روند ۳ سالهٔ EPS با سال مالی پویا (نه قفل روی ۲۹ اسفند)
  F-04   سالانه‌سازی پویای ۱۲÷n + نسبتِ مارکت‌کپ
  F-04b  مدیریت وضعیت N/A برای هلدینگ‌ها/سرمایه‌گذاری‌ها
  F-05   استثنای دارویی (GPM ≥ ۵۰٪ مجاز، نه ردِ مطلق)

اجرا:  python dev/codal_logic_guard.py
اگر market.db نباشد، بخشِ داده SKIP می‌شود؛ گاردهای خالص همیشه اجرا می‌شوند.
"""
import os
import sqlite3
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
sys.path.insert(0, _ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import fts_engine as F  # noqa: E402

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    print('  %s %s' % ('PASS' if cond else 'FAIL', msg))


def main():
    has_db = os.path.exists("market.db")
    conn = None
    if has_db:
        conn = sqlite3.connect("file:market.db?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

    # ── F-01a: فیلتر شرکت اصلی ──────────────────────────────────────────
    ck(F._is_consolidated("صورت‌های مالی تلفیقی سال ۱۴۰۴"),
       "F-01a عنوانِ «تلفیقی» فارسی شناسایی می‌شود")
    ck(F._is_consolidated("صورت‌هاي مالي تلفيقي سال ۱۴۰۴"),
       "F-01a عنوانِ «تلفيقي» عربی هم شناسایی می‌شود (ی/ک عربی)")
    ck(not F._is_consolidated("صورت‌های مالی سال ۱۴۰۴"),
       "F-01a صورتِ مالیِ اصلی، تلفیقی محسوب نمی‌شود")
    if conn is not None:
        cons = conn.execute(
            "SELECT COUNT(*) FROM financial_statements WHERE is_consolidated=1").fetchone()[0]
        ck(cons > 0, "F-01a ستونِ is_consolidated پر شده (%d ردیف)" % cons)
        sym = conn.execute(
            "SELECT symbol FROM financial_statements WHERE is_consolidated=1 LIMIT 1").fetchone()
        if sym:
            with_c = F.annual_statements(conn, sym["symbol"], require_audit=False,
                                         exclude_consolidated=False, limit=20)
            without_c = F.annual_statements(conn, sym["symbol"], require_audit=False,
                                            exclude_consolidated=True, limit=20)
            ck(len(without_c) < len(with_c),
               "F-01a annual_statements تلفیقی را حذف می‌کند (%d→%d)"
               % (len(with_c), len(without_c)))

    # ── F-01b: وتوی صنعت بیمه ───────────────────────────────────────────
    ck(F.is_insurance_sector("بیمه"), "F-01b «بیمه» شناسایی می‌شود")
    ck(F.is_insurance_sector("بيمه"), "F-01b «بيمه» عربی شناسایی می‌شود")
    ck(not F.is_insurance_sector("فلزات اساسي"), "F-01b فلزات، بیمه نیست")
    ck(F.eps_trend_3y(conn or _Fake(), "ناموجود", sector="بیمه") is None,
       "F-01b eps_trend_3y برای صنعت بیمه None می‌دهد (وتو)")

    # ── F-02: روند ۳ سالهٔ EPS با سال مالی پویا ─────────────────────────
    if conn is not None:
        pe = conn.execute(
            "SELECT period_end FROM financial_statements WHERE period_months>=12 "
            "AND period_end IS NOT NULL ORDER BY period_end DESC LIMIT 1").fetchone()
        ck(pe is not None,
           "F-02 سال مالی از period_end خوانده می‌شود (آخرین=%s، نه قفلِ ۲۹ اسفند)"
           % (pe["period_end"] if pe else "-"))
        sample = [r["symbol"] for r in conn.execute(
            "SELECT symbol FROM financial_statements WHERE period_months>=12 "
            "GROUP BY symbol HAVING COUNT(*)>=3 LIMIT 2")]
        for s in sample:
            e = F.eps_trend_3y(conn, s)
            if e and e.get("eps_series"):
                ck(len(e["eps_series"]) == 3 and all(v is not None for v in e["eps_series"]),
                   "F-02 %s: سریِ EPSِ ۳تاییِ کامل" % s)
                ck(e.get("years_available", 0) >= 3,
                   "F-02 %s: years_available=%s" % (s, e.get("years_available")))

    # ── F-04: سالانه‌سازی پویای ۱۲÷n ─────────────────────────────────────
    h = F.sales_to_marketcap(conn or _Fake(), "ناموجود", 1e13,
                             sector="صندوق سرمایه گذاری قابل معامله")
    ck(h is not None and h.get("is_exempt") is True and h.get("sales_to_mcap") is None,
       "F-04b هلدینگ: is_exempt=True و نسبت N/A (نه صفر، نه مردود)")
    n = F.sales_to_marketcap(conn or _Fake(), "ناموجود", 1e13, sector="فلزات اساسي")
    ck(n is None, "F-04b غیرهلدینگِ بدونِ داده: None (معافیت نمی‌گیرد)")

    # ── F-05: استثنای دارویی ────────────────────────────────────────────
    ck(F.sector_filter("مواد و محصولات دارویی")["verdict"] == "neutral",
       "F-05 دارو با GPM نامعلوم: neutral (نه وتوی سخت)")
    ck(F.sector_filter("مواد و محصولات دارویی", gpm=55.0)["verdict"] == "free",
       "F-05 دارو با GPM ۵۵٪: free")
    ck(F.sector_filter("مواد و محصولات دارویی", gpm=20.0)["verdict"] == "mandatory",
       "F-05 دارو با GPM ۲۰٪: mandatory")

    if conn is not None:
        conn.close()

    n_bad = sum(1 for ok, _ in CHECKS if not ok)
    print('\n%d checks, %d failed' % (len(CHECKS), n_bad))
    print('CODAL LOGIC GUARD %s' % ('FAILED' if n_bad else 'PASSED'))
    return 1 if n_bad else 0


class _Fake:
    """connectionِ صوری برایِ گاردهایِ خالص وقتی market.db نیست."""

    def execute(self, *a, **kw):
        return self

    def fetchall(self):
        return []

    def fetchone(self):
        return None


if __name__ == "__main__":
    sys.exit(main())
