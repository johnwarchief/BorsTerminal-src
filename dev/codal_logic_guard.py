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
  F-05   صنایع دستوری/آزاد — استثنای دارویی **خاموشِ پیش‌فرض** (کلیدش در جزوه
         نیست؛ رأیِ مالک ۱۴۰۵-۰۷-۱۱) و پهنایِ رشد ماهانه **نمایشی** است، نه درگاه

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
import codal_periods as CP  # noqa: E402

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
            "AND %s %s LIMIT 1" % (CP.DATED_SQL, CP.latest_order_sql())).fetchone()
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

    # ── F-05: استثنای دارویی — **خاموشِ پیش‌فرض** (رأیِ مالک ۱۴۰۵-۰۷-۱۱) ─────
    # «pharma_margin_exempt_min» درِ جزوه نیست؛ پس دارو نه خودکار معاف می‌شود نه
    # خودکار رد. این سه چک همان حکم را قفل می‌کنند: با کانفیگِ خالی، GPM هرچه باشد
    # داوری «خنثی» است؛ فقط وقتی مالک کلید را non-zero کند شاخۀ استثنا کار می‌کند.
    ck(F.sector_filter("مواد و محصولات دارویی")["verdict"] == "neutral",
       "F-05 دارو با GPM نامعلوم: neutral (نه وتوی سخت)")
    ck(F.sector_filter("مواد و محصولات دارویی", gpm=55.0)["verdict"] == "neutral",
       "F-05 دارو با GPM ۵۵٪ هم neutral می‌ماند (کلید خاموش ⇒ استثنای خودکار نداریم)")
    ck(F.sector_filter("مواد و محصولات دارویی", gpm=20.0)["verdict"] == "neutral",
       "F-05 دارو با GPM ۲۰٪ رد نمی‌شود (نبودِ قانونِ جزوه ≠ وتو)")
    ck(F.sector_filter("مواد و محصولات دارویی", cfg={"pharma_margin_exempt_min": 50.0},
                       gpm=55.0)["verdict"] == "free",
       "F-05 اگر مالک کلید را روشن کند، شاخۀ استثنا همان ۵۰٪ را می‌خواند (free)")
    ck(F.sector_filter("مواد و محصولات دارویی", cfg={"pharma_margin_exempt_min": 50.0},
                       gpm=20.0)["verdict"] == "mandatory",
       "F-05 با کلیدِ روشن و GPM زیرِ آستانه: mandatory (سلوکِ قبلیِ انتخابی)")

    # ── F-01/۱ب: پهنای رشد **نمایشی** است، نه درگاهِ امتیاز ────────────────
    # جزوه برایِ «breadth» هیچ فرمول یا آستانه‌ای ندارد. سریِ ساختگیِ زیر رشد
    # ریالیِ خوب دارد ولی فقط ۱ از ۶ ماه بهتر شده — با گیتِ پیشین ۱ب «رد»
    # می‌شد؛ حالا pass است و پهنا فقط درِ payload دیده می‌شود.
    from api import fundamental as _FD          # importِ محلی (خارج از مسیرِ موتور)
    _mem = sqlite3.connect(":memory:")
    _mem.execute("CREATE TABLE monthly_sales (tracing_no INTEGER PRIMARY KEY,"
                 " symbol TEXT, title TEXT, period_end TEXT, year INTEGER, month INTEGER,"
                 " monthly_revenue REAL, ytd_revenue REAL, ytd_revenue_prev REAL)")
    _now = {1: 100.0, 2: 100.0, 3: 100.0, 4: 100.0, 5: 100.0, 6: 300.0}
    _prev = {1: 110.0, 2: 110.0, 3: 110.0, 4: 110.0, 5: 110.0, 6: 90.0}
    _tn = 0
    for _y, _src in ((1405, _now), (1404, _prev)):
        _cum = 0.0
        for _m in range(1, 7):
            _tn += 1
            _cum += _src[_m]
            _mem.execute("INSERT INTO monthly_sales VALUES (?,?,?,?,?,?,?,?,?)",
                         (_tn, "آزمون", "گزارش فعالیت ماهانه", "%d/%02d/30" % (_y, _m),
                          _y, _m, _src[_m], _cum, None))
    _mem.commit()
    _ser = _FD.monthly_series(_mem, "آزمون")
    _mon = {"year": 1405, "months": 6, "monetary_pct": 66.7}
    _th = _FD.v10_thresholds()
    _prof = F.company_profile("فلزات اساسی")
    _v = _FD.ind1b_volume_growth(_mem, "آزمون", monetary=_mon, series=_ser,
                                 th=_th, profile=_prof)
    _br = _v.get("breadth") or {}
    ck(_br.get("ratio") is not None and _br["ratio"] < _th["volume_breadth_min"],
       "F-01 ۱ب: پهنا واقعاً کم است (%s از %s) — سناریوی تست ساخته شد"
       % (_br.get("improved_months"), _br.get("compared_months")))
    ck(bool(_v.get("pass")) is True,
       "F-01 ۱ب باوجودِ پهنای کم pass می‌شود (رشد واقعی %+.1f٪ ≥ %g٪) — پهنا درگاه نیست"
       % (_v.get("real_pct") or 0.0, _th["volume_growth_min"]))
    ck("note_breadth" in _v and _v.get("breadth"),
       "F-01 ۱ب: پهنا درِ payload برایِ نمایش ماند (نه درِ داوری)")
    _mem.close()

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
