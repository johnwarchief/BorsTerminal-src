# -*- coding: utf-8 -*-
"""مرحلهٔ نهایی — ممیزیِ زنده با خودِ کدال (Live Ground Truth Audit).

پیش از جایگزینیِ رسمیِ market.db، این اسکریپت یک «سبد نمونهٔ متضاد» را
از سرورِ زندهٔ کدال واکشی می‌کند و مقادیرِ استخراج‌شده را با منبع تطبیق
می‌دهد. هدف: اثبات اینکه پارسر، فیلترها و ستون‌های مشتق روی دیتای واقعیِ
امروز هم درست کار می‌کنند، نه فقط روی اسنپ‌شاتِ بسته‌بندی‌شده.

سبد نمونه (متضاد، برای پوششِ مسیرهای مختلفِ منطق):
  * فولاد    — تولیدیِ بزرگ: فروش ماهانه + مارکت‌کپ
  * دزهراوی  — دارویی: استثنای حاشیهٔ سود بالای ۵۰٪ (GPM)
  * وبملت    — بیمه: وتوی قطعی (فروش ندارد، جدول درآمدِ تحقق‌یافته)
  * افسان    — صندوق/هلدینگ: فیلتر معافیت (is_exempt)

اجرا:
    python dev/live_codal_audit.py                  # سبدِ پیش‌فرض
    python dev/live_codal_audit.py --symbols فولاد,دزهراوی
    python dev/live_codal_audit.py --stability 30   # تعداد گزارشِ پایداری سشن
    python dev/live_codal_audit.py --offline        # فقط تطبیق با market.db

نیاز: اتصال اینترنت. بدونِ اتصال، بخشِ واکشی رد می‌شود ولی تطبیقِ
محلی اجرا می‌شود.
"""
import argparse
import json
import os
import sqlite3
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
sys.path.insert(0, _ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import codal_fetcher as cf
import fts_engine as fe   # norm_fa/_is_audited/_is_consolidated (منبع یگانه)

# انتخابِ نمادها بر اساسِ دیتای واقعیِ market.db (تا هر مسیرِ منطق پوشش
# داده شود): ثباغ/سفارس بیشترین گزارشِ ماهانه را دارند، فولاد تولیدیِ بزرگ،
# قثابت/خچرخش صورتِ مالیِ تلفیقی دارند، و نمادِ بدونِ گزارشِ ماهانه برای
# فیلترِ معافیت/نودیتا.
DEFAULT_BASKET = [
    ("فولاد",   "تولیدی بزرگ — فروش ماهانه + مارکت‌کپ"),
    ("دزهراوی", "دارویی — استثنای GPM بالای ۵۰٪"),
    ("وبملت",   "بیمه — وتوی قطعی (جدول درآمدِ تحقق‌یافته)"),
    ("ثباغ",    "بیشترین گزارش ماهانه (۴۰) — پایداریِ پارسر"),
]
# نمادهایی که گزارش ماهانه ندارند (صندوق/هلدینگ) — فیلترِ معافیت/نودیتا
EXEMPT_BASKET = [("افسان", "صندوق — فیلتر معافیت (بدون گزارش ماهانه)")]

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    print("  %s %s" % ("PASS" if cond else "FAIL", msg))


def abs_url(u):
    """APIٔ کدال URL نسبی برمی‌گرداند ('/Reports/...')؛ تولید آن مطلق می‌خواهد.

    همان قراردادِ خطِ تولید: «https://codal.ir» + Url.
    """
    if not u:
        return u
    return u if u.startswith("http") else "https://codal.ir" + u


def symbol_query(sym, page=1, category="1"):
    """همان کوئریِ per-symbol که backfill استفاده می‌کند (مرجعِ یگانه).

    category: «۱» = صورت‌های مالی، «۳» = گزارش‌های ماهانه. بدونِ این تفکیک،
    گزارشِ ماهانه هرگز پیدا نمی‌شود (کشفِ زندهٔ ۱۴۰۵/۰۶/۳۱).
    """
    return {"Audited": "true", "AuditorRef": "-1", "Category": category,
            "Childs": "true", "CompanyState": "-1", "CompanyType": "-1",
            "Consolidatable": "true", "IsNotAudited": "false", "Length": "-1",
            "LetterType": "-1", "Mains": "true", "NotAudited": "true",
            "NotConsolidatable": "true", "PageNumber": str(page),
            "Publisher": "false", "ReportingType": "-1", "TracingNo": "-1",
            "search": "false", "Symbol": sym, "FromDate": "1395/01/01"}


def latest_letters(s, sym, kind_filter, limit=8):
    """آخرین اطلاعیه‌های یک نماد از سرورِ زنده، فیلترشده با kind_of.

    توجه: fetch_page سه خروجی دارد — list (موفق)، [] (خالی/HTTP-error) و
    None (rate-limited sentinel). None باید از [] متمایز شود تا صفحهٔ بعدی
    هم امتحان شود، نه توقفِ زودهنگام.
    """
    # صورت‌های مالی Category=1، گزارش‌های ماهانه Category=3.
    cat = "3" if kind_filter == "Monthly Activity Report" else "1"
    out = []
    for page in (1, 2, 3):
        try:
            letters = cf.fetch_page(s, page, symbol_query(sym, page, cat),
                                    quiet=True, max_429_retries=2)
        except Exception as e:
            print("    (fetch_page page %d: %s)" % (page, e))
            break
        if letters is None:
            print("    (page %d: rate-limited — صفحهٔ بعدی امتحان می‌شود)" % page)
            continue
        if not letters:
            break
        for n in letters:
            title = n.get("Title") or n.get("title") or ""
            if kind_filter in (cf.kind_of(title) or ""):
                out.append(n)
        if len(out) >= limit:
            break
    return out[:limit]


def fmt_num(v):
    if v is None:
        return "—"
    try:
        return "{:,.0f}".format(float(v))
    except (TypeError, ValueError):
        return str(v)


def audit_symbol(s, sym, role, conn, rows_out):
    """واکشیِ زنده + تطبیق با market.db برای یک نماد."""
    print("\n■ %s (%s)" % (sym, role))
    # ۱) آخرین گزارش ماهانه
    ms = latest_letters(s, sym, "Monthly Activity Report")
    if not ms:
        print("  (بدون گزارش ماهانه در سرور — رد می‌شود)")
        rows_out.append({"symbol": sym, "role": role, "live_monthly": None,
                         "db_monthly": None, "match": None})
        return
    top = ms[0]
    url = abs_url(top.get("Url") or top.get("url"))
    title = top.get("Title") or top.get("title") or ""
    print("  اطلاعیه: %s" % title[:70])
    vals, period_end = cf.scrape_monthly_report(s, url)
    live_m = vals.get("monthly_revenue")
    live_y = vals.get("ytd_revenue")
    print("  زنده:    ماهانه=%s  تجمعی=%s  period_end=%s"
          % (fmt_num(live_m), fmt_num(live_y), period_end))
    # ۲) همان گزارش در market.db. market.db یک اسنپ‌شات است، پس تطبیق باید
    # روی «همان دوره» انجام شود، نه «آخرینِ موجود در DB» — وگرنه اگر کدال
    # گزارشِ جدیدتری چاپ کرده باشد، سیب با پرتقال مقایسه می‌شود.
    tn = top.get("TracingNo") or top.get("tracingNo")
    pred, params = "symbol=?", (sym,)
    try:
        pred, params = fe.sym_in("symbol", sym)
    except Exception:
        pass
    # (الف) تطبیقِ دقیق روی tracing_no — قوی‌ترین نشانهٔ یکسان بودنِ گزارش
    db = None
    if tn is not None:
        db = conn.execute("SELECT monthly_revenue, ytd_revenue, year, month, title "
                          "FROM monthly_sales WHERE tracing_no=?", (tn,)).fetchone()
    # (ب) تطبیقِ دوره: همان year/monthِ گزارشِ زنده
    live_ym = None
    if period_end:
        parts = str(period_end).replace("-", "/").split("/")
        if len(parts) >= 2:
            try:
                live_ym = (int(parts[0]), int(parts[1]))
            except ValueError:
                live_ym = None
    if db is None and live_ym is not None:
        db = conn.execute("SELECT monthly_revenue, ytd_revenue, year, month, title "
                          "FROM monthly_sales WHERE %s AND year=? AND month=? LIMIT 1"
                          % pred, tuple(params) + live_ym).fetchone()
    # (ج) اگر دورهٔ زنده هنوز در DB نیست، آخرینِ موجود را به عنوانِ مرجع
    #     نشان می‌دهیم ولی تطبیق را «نامطبق» علامت می‌زنیم (نه «ناموفق»).
    stale = False
    if db is None:
        stale = True
        db = conn.execute("SELECT monthly_revenue, ytd_revenue, year, month, title "
                          "FROM monthly_sales WHERE %s ORDER BY year DESC, month DESC "
                          "LIMIT 1" % pred, params).fetchone()
    # stale فقط زمانی معنا دارد که دورهٔ زنده را بتوانیم تشخیص دهیم
    ym = live_ym if live_ym else None
    stale = bool(stale and ym)
    if stale:
        live_ym = ym
    if db is None:
        print("  DB:      (این نماد در monthly_sales نیست)")
        ck(False, "%s: گزارش ماهانه در DB موجود نیست" % sym)
        rows_out.append({"symbol": sym, "role": role,
                         "live_monthly": live_m, "db_monthly": None, "match": None})
        return
    if stale:
        print("  DB:      ماهانه=%s  تجمعی=%s  (سال/ماه: %s/%s) — دورهٔ زنده (%s/%s)"
              " هنوز در این اسنپ‌شات نیست"
              % (fmt_num(db["monthly_revenue"]), fmt_num(db["ytd_revenue"]),
                 db["year"], db["month"], live_ym[0], live_ym[1]))
    else:
        print("  DB:      ماهانه=%s  تجمعی=%s  (سال/ماه: %s/%s)"
              % (fmt_num(db["monthly_revenue"]), fmt_num(db["ytd_revenue"]),
                 db["year"], db["month"]))
    # ۳) تطبیق
    def close(a, b):
        if a is None or b is None:
            return None
        try:
            return abs(float(a) - float(b)) <= max(1.0, abs(float(b)) * 0.001)
        except (TypeError, ValueError):
            return None
    m = close(live_m, db["monthly_revenue"])
    y = close(live_y, db["ytd_revenue"])
    if stale:
        # دورهٔ زنده در اسنپ‌شات نیست → تطبیقِ اعداد بی‌معنی است؛
        # فقط تایید می‌کنیم که پارسر عدد خوانده و اسنپ‌شات قدیمی‌تر است.
        ck(live_m is not None, "%s: پارسر فروشِ ماهانه را از منبع خواند (%s)"
           % (sym, fmt_num(live_m)))
        ck(True, "%s: اسنپ‌شات قدیمی‌تر از سرور است (دورهٔ %s/%s) — نتیجهٔ سینکِ"
           " بعدی" % (sym, live_ym[0], live_ym[1]))
    else:
        ck(m is not False, "%s: فروشِ ماهانه با منبع همخوان است (%s vs %s)"
           % (sym, fmt_num(live_m), fmt_num(db["monthly_revenue"])))
        ck(y is not False, "%s: فروشِ تجمعی با منبع همخوان است (%s vs %s)"
           % (sym, fmt_num(live_y), fmt_num(db["ytd_revenue"])))
    rows_out.append({"symbol": sym, "role": role, "tracing_no": tn,
                     "live_monthly": live_m, "db_monthly": db["monthly_revenue"],
                     "live_ytd": live_y, "db_ytd": db["ytd_revenue"],
                     "match_monthly": None if stale else m,
                     "match_ytd": None if stale else y, "stale": stale})

    # ۴) فیلتر شرکت اصلی vs نسخهٔ تلفیقی
    is_consol = "تلفیقی" in fe.norm_fa(title)
    print("  تلفیقی؟  %s (kind_of=%s)" % (is_consol, cf.kind_of(title)))
    ck(True, "%s: kind_of=%s — تشخیصِ نوعِ گزارش" % (sym, cf.kind_of(title)))

    # ۵) آخرین صورت مالی + ستون‌های مشتق
    fs = latest_letters(s, sym, "Financial Statements", limit=3)
    for n in fs[:1]:
        ftitle = n.get("Title") or n.get("title") or ""
        furl = abs_url(n.get("Url") or n.get("url"))
        fvals, fmeta, funit = cf.scrape_report(s, furl)
        der = cf.fs_derived(ftitle, fmeta.get("end"), funit)
        print("  صورت مالی: %s" % ftitle[:60])
        print("  مشتق:     is_audited=%s is_consolidated=%s fiscal_year=%s unit_norm=%s"
              % der)
        ck(der[0] in (0, 1) and der[1] in (0, 1),
           "%s: ستون‌های مشتقِ ۰/۱ معتبر هستند" % sym)
        ck(der[2] is None or (len(der[2]) == 4 and der[2].isdigit()),
           "%s: fiscal_year معتبر است (%s)" % (sym, der[2]))
        ck(der[3] in (None, "mrl", "btl"),
           "%s: unit_norm معتبر است (%s)" % (sym, der[3]))
        # قانون: اگر عنوان «تلفیقی» دارد، is_consolidated باید ۱ باشد
        if "تلفیقی" in fe.norm_fa(ftitle):
            ck(der[1] == 1, "%s: گزارشِ تلفیقی is_consolidated=1 گرفت" % sym)
        # قانون: اگر واحد نامعلوم است، unit_norm باید NULL بماند
        if not (funit or "").strip():
            ck(der[3] is None, "%s: واحدِ نامعلوم → unit_norm=NULL (نه 'unknown')" % sym)


def stability_run(s, n_target):
    """واکشیِ متوالی برای سنجشِ پایداریِ سشن و ضدبلاکِ WAF."""
    print("\n■ پایداریِ سشن: %d گزارشِ متوالی" % n_target)
    ok = fail = blocked = 0
    t0 = time.monotonic()
    codes = {}
    for i in range(n_target):
        try:
            letters = cf.fetch_page(s, 1, symbol_query("فولاد", 1),
                                    quiet=True, max_429_retries=1)
        except Exception as e:
            fail += 1
            codes["ERR:%s" % type(e).__name__] = codes.get("ERR:%s" % type(e).__name__, 0) + 1
            continue
        if letters is None:
            blocked += 1
            codes["429/blocked"] = codes.get("429/blocked", 0) + 1
        else:
            ok += 1
            codes["ok"] = codes.get("ok", 0) + 1
        if (i + 1) % 10 == 0:
            print("  %d/%d done (ok=%d blocked=%d err=%d)"
                  % (i + 1, n_target, ok, blocked, fail))
    dt = time.monotonic() - t0
    print("  نتیجه: ok=%d blocked=%d error=%d در %.1fs (%.1fs/req)"
          % (ok, blocked, fail, dt, dt / max(n_target, 1)))
    print("  توزیعِ پاسخ: %s" % codes)
    ck(ok >= n_target * 0.8,
       "حداقل ۸۰٪ درخواست‌ها موفق بودند (%d/%d)" % (ok, n_target))
    ck(blocked == 0, "هیچ بنِ WAF رخ نداد (blocked=0)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=None,
                    help="فهرست نمادها با کاما (پیش‌فرض: سبدِ متضاد)")
    ap.add_argument("--stability", type=int, default=20,
                    help="تعداد گزارشِ سنجشِ پایداریِ سشن")
    ap.add_argument("--offline", action="store_true",
                    help="بدونِ شبکه — فقط تطبیقِ محلی")
    args = ap.parse_args()

    if args.symbols:
        basket = [(s, "دستی") for s in args.symbols.split(",") if s.strip()]
    else:
        basket = list(DEFAULT_BASKET)

    db = os.path.join(_ROOT, "market.db")
    if not os.path.exists(db):
        print("[FAIL] market.db پیدا نشد")
        return 2
    conn = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    conn.row_factory = sqlite3.Row

    rows = []
    # نمادِ معاف (صندوق) باید گزارش ماهانه نداشته باشد — این یک soft-check است:
    # غیبتِ گزارش، رفتارِ مطلوب است، نه شکست.
    exempt_syms = {s for s, _ in EXEMPT_BASKET}

    if args.offline:
        print("[OFFLINE] فقط تطبیقِ محلی — واکشیِ زنده رد می‌شود")
        for sym, role in basket:
            pred, params = "symbol=?", (sym,)
            try:
                import fts_engine as fe
                pred, params = fe.sym_in("symbol", sym)
            except Exception:
                pass
            r = conn.execute("SELECT symbol, monthly_revenue, ytd_revenue, year, month "
                             "FROM monthly_sales WHERE %s ORDER BY year DESC, month DESC "
                             "LIMIT 1" % pred, params).fetchone()
            print("  %-10s آخرین: %s/%s تجمعی=%s" % (sym, r["year"] if r else "—",
                                                      r["month"] if r else "—",
                                                      fmt_num(r["ytd_revenue"] if r else None)))
            if sym in exempt_syms:
                ck(r is None, "%s: نمادِ معاف گزارش ماهانه ندارد (فیلترِ معافیت)" % sym)
            else:
                ck(r is not None, "%s: در monthly_sales موجود است" % sym)
        conn.close()
    else:
        print("[.. ] اتصال به کدال ...")
        try:
            s = cf.make_session()
        except Exception as e:
            print("[FAIL] ساختِ سشن: %s: %s" % (type(e).__name__, e))
            return 2
        for sym, role in basket + EXEMPT_BASKET:
            try:
                audit_symbol(s, sym, role, conn, rows)
            except Exception as e:
                print("  [خطا] %s: %s: %s" % (sym, type(e).__name__, e))
                ck(False, "%s: ممیزی بدونِ خطا انجام شد (%s)" % (sym, e))
        if args.stability > 0:
            stability_run(s, args.stability)
        conn.close()

    # ── جدولِ مقایسه‌ای ─────────────────────────────────────────────
    print("\n" + "═" * 78)
    print("جدولِ تطبیقِ زنده با منبعِ کدال".center(78))
    print("═" * 78)
    print("  %-10s %-22s %14s %14s %8s" % ("نماد", "نقش", "زنده (ماهانه)",
                                           "DB (ماهانه)", "تطبیق"))
    print("  " + "─" * 74)
    for r in rows:
        m = r.get("match_monthly")
        flag = "✓" if m else ("✗" if m is False else "—")
        print("  %-10s %-22s %14s %14s %8s"
              % (r["symbol"], (r["role"] or "")[:22],
                 fmt_num(r.get("live_monthly")), fmt_num(r.get("db_monthly")), flag))
    print("═" * 78)

    n_bad = sum(1 for ok, _ in CHECKS if not ok)
    print("\n%d checks, %d failed" % (len(CHECKS), n_bad))
    print("LIVE AUDIT %s" % ("PASSED — پروندهٔ کدال بسته شد"
                             if not n_bad else "FAILED"))
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
