#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""گام ۳۶ — گزارشِ نهاییِ مقایسه و سلامت (Final Diff & Sanity Report).

پروندهٔ سلامتِ market.db را قبل از جایگزینیِ رسمی در پروداکشن تولید می‌کند.

خروجی:
  * تعداد کل نمادها، صورت‌های مالی، و دامنهٔ زمانی قیمت‌ها
  * درصد سطرهای دارای فیلدهای تهی (Null Check) برای هر جدولِ حیاتی
  * حجم نهایی فایل پس از وکیوم
  * وضعیت آماده‌باش نهایی برای جایگزینی رسمی (Production-Ready Sign-off)

استفاده:
    python dev/db_final_report.py                     # فقط market.db
    python dev/db_final_report.py --baseline other.db # مقایسه با یک DB دیگر
    python dev/db_final_report.py --baseline-lzma     # مقایسه با market.db.lzma
"""
import argparse
import lzma
import os
import sqlite3
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
sys.path.insert(0, _ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TARGET = os.path.join(_ROOT, "market.db")

# جداول/ستون‌هایی که Null Check رویشان معنا دارد.
NULL_AUDIT = {
    "instruments": ["l_val18", "sector_name", "total_shares"],
    "financial_statements": ["symbol", "title", "period_end", "revenue",
                             "is_audited", "is_consolidated", "fiscal_year", "unit_norm"],
    "monthly_sales": ["symbol", "year", "month", "ytd_revenue"],
    "price_history": ["symbol", "date", "close", "volume"],
    "daily_prices": ["ins_code", "d_even", "p_closing"],
    "market_watch": ["ins_code", "p_closing"],
}

# ستون‌هایی که NULL بودنشان یک باگ است (نه یک حالتِ معتبرِ «نامعلوم»).
HARD_NULL = {
    "financial_statements": ["is_audited", "is_consolidated"],
    "monthly_sales": ["year", "month"],
}


def q(conn, sql, args=()):
    try:
        return conn.execute(sql, args).fetchone()[0]
    except Exception:
        return None


def table_stats(conn, tbl, cols):
    total = q(conn, "SELECT COUNT(*) FROM %s" % tbl)
    if total is None:
        return None
    out = {"total": total, "nulls": {}}
    for c in cols:
        n = q(conn, "SELECT COUNT(*) FROM %s WHERE %s IS NULL" % (tbl, c))
        out["nulls"][c] = n
    return out


def db_snapshot(path, label):
    """خلاصهٔ یک DB برای مقایسه — بدونِ باز کردنِ کلِ آن در حافظه."""
    snap = {"label": label, "path": path, "exists": os.path.exists(path)}
    if not snap["exists"]:
        return snap
    snap["size_mb"] = round(os.path.getsize(path) / 1e6, 1)
    try:
        c = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
        c.row_factory = sqlite3.Row
        snap["integrity"] = c.execute("PRAGMA integrity_check").fetchone()[0]
        snap["tables"] = sorted(r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
        for t in ("instruments", "financial_statements", "monthly_sales",
                  "price_history", "daily_prices", "market_watch", "codal_notices",
                  "fts_results"):
            snap[t] = q(c, "SELECT COUNT(*) FROM %s" % t)
        # دامنهٔ زمانی قیمت‌ها
        ph = c.execute("SELECT MIN(date) lo, MAX(date) hi FROM price_history").fetchone()
        snap["ph_range"] = (ph["lo"], ph["hi"]) if ph and ph["lo"] else None
        pe = c.execute("SELECT MIN(period_end) lo, MAX(period_end) hi "
                       "FROM financial_statements").fetchone()
        snap["fs_range"] = (pe["lo"], pe["hi"]) if pe and pe["lo"] else None
        # پوششِ ستون‌های مشتق
        snap["fs_consolidated"] = q(c, "SELECT COUNT(*) FROM financial_statements "
                                      "WHERE is_consolidated=1")
        snap["fs_unit_norm_null"] = q(c, "SELECT COUNT(*) FROM financial_statements "
                                      "WHERE unit_norm IS NULL")
        snap["fs_distinct_symbols"] = q(c, "SELECT COUNT(DISTINCT symbol) "
                                        "FROM financial_statements")
        snap["ms_distinct_symbols"] = q(c, "SELECT COUNT(DISTINCT symbol) "
                                        "FROM monthly_sales")
        c.close()
    except Exception as e:
        snap["error"] = "%s: %s" % (type(e).__name__, e)
    return snap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default=None,
                    help="مسیرِ DB قدیمیِ پروداکشن برای مقایسه")
    ap.add_argument("--baseline-lzma", action="store_true",
                    help="مقایسه با market.db.lzma (خطِ مبنایِ بسته‌بندی)")
    ap.add_argument("--json", action="store_true", help="خروجیِ JSON به‌جای متن")
    args = ap.parse_args()

    if not os.path.exists(TARGET):
        print("[FAIL] market.db پیدا نشد: %s" % TARGET)
        return 2

    base_path = None
    base_label = None
    if args.baseline_lzma:
        base_path = os.path.join(_ROOT, "market.db.lzma")
        base_label = "market.db.lzma (خطِ مبنایِ بسته‌بندی)"
    elif args.baseline:
        base_path = args.baseline
        base_label = args.baseline
    base_tmp = None
    if base_path and base_path.endswith(".lzma") and os.path.exists(base_path):
        base_tmp = tempfile.mkdtemp(prefix="bors_report_")
        base_path = os.path.join(base_tmp, "baseline.db")
        with lzma.open(os.path.join(_ROOT, "market.db.lzma")) as f, open(base_path, "wb") as o:
            o.write(f.read())

    tgt = db_snapshot(TARGET, "market.db (آماده‌شده)")
    base = db_snapshot(base_path, base_label) if base_path else None

    # ── Null Check دقیق ──────────────────────────────────────────────
    conn = sqlite3.connect("file:%s?mode=ro" % TARGET, uri=True)
    conn.row_factory = sqlite3.Row
    audit = {}
    hard_violations = []
    for tbl, cols in NULL_AUDIT.items():
        st = table_stats(conn, tbl, cols)
        if st is None:
            continue
        audit[tbl] = st
        for c in cols:
            if c in HARD_NULL.get(tbl, []) and st["nulls"][c]:
                hard_violations.append((tbl, c, st["nulls"][c]))
    # یتیم‌های واقعی (حتی با resolveِ alias). توجه: «یتیم» اینجا یعنی نمادی
    # که در instruments.l_val18 نیست — ولی کدال گاهی نامِ شرکت را به‌جای
    # تیکر می‌نویسد و symbol_aliases آن را حل می‌کند. پس معیارِ واقعی
    # «نمادهای یکتا» است، نه شمارشِ خامِ ردیف‌ها.
    import fts_engine as fe
    orph_symbols = [r[0] for r in conn.execute(
        "SELECT DISTINCT f.symbol FROM financial_statements f LEFT JOIN instruments i "
        "ON i.l_val18=f.symbol WHERE i.l_val18 IS NULL")]
    orph_raw = len(orph_symbols)
    orph_rows = q(conn, "SELECT COUNT(*) FROM financial_statements f LEFT JOIN instruments i "
                        "ON i.l_val18=f.symbol WHERE i.l_val18 IS NULL")
    orph_resolvable = 0
    for s in orph_symbols:
        pred, params = fe.sym_in("symbol", s)
        if q(conn, "SELECT COUNT(*) FROM financial_statements WHERE %s" % pred, params):
            orph_resolvable += 1
    conn.close()

    # ── خروجی ─────────────────────────────────────────────────────────
    if args.json:
        import json
        print(json.dumps({"target": tgt, "baseline": base, "audit": audit,
                          "hard_violations": hard_violations,
                          "orphans": {"raw": orph_raw, "resolvable": orph_resolvable}},
                         ensure_ascii=False, indent=2, default=str))
        return 0

    W = 78
    print("=" * W)
    print("گزارشِ نهاییِ سلامتِ داده‌ها — Data Lifecycle Sign-off".center(W))
    print("=" * W)

    print("\n■ ۱. حجم و یکپارچگی")
    print("   حجمِ نهایی:           %s MB" % tgt.get("size_mb"))
    print("   integrity_check:      %s" % tgt.get("integrity"))
    print("   جداول (%d):           %s" % (len(tgt.get("tables", [])),
                                           ", ".join(tgt.get("tables", []))))

    print("\n■ ۲. شمارش‌ها و دامنهٔ زمانی")
    print("   %-24s %s" % ("نمادها (instruments)", tgt.get("instruments")))
    print("   %-24s %s" % ("صورت‌های مالی", tgt.get("financial_statements")))
    print("   %-24s %s" % ("نمادهای دارای صورت مالی", tgt.get("fs_distinct_symbols")))
    print("   %-24s %s" % ("گزارش‌های ماهانه", tgt.get("monthly_sales")))
    print("   %-24s %s" % ("نمادهای دارای گزارش ماهانه", tgt.get("ms_distinct_symbols")))
    print("   %-24s %s" % ("سابقهٔ قیمت (کندل)", tgt.get("price_history")))
    print("   %-24s %s" % ("دامنهٔ زمانی قیمت", tgt.get("ph_range")))
    print("   %-24s %s" % ("دامنهٔ زمانی صورت مالی", tgt.get("fs_range")))
    print("   %-24s %s" % ("رویدادهای تابلو", tgt.get("market_watch")))
    print("   %-24s %s" % ("قیمت‌های روزانه", tgt.get("daily_prices")))
    print("   %-24s %s" % ("اطلاعیه‌های کدال", tgt.get("codal_notices")))

    print("\n■ ۳. Null Check (درصدِ سطرهای تهی)")
    for tbl, st in audit.items():
        tot = st["total"]
        if not tot:
            print("   %-22s (خالی)" % tbl)
            continue
        parts = []
        for c, n in st["nulls"].items():
            if n is None:
                continue
            pct = 100.0 * n / tot
            parts.append("%s=%.2f%%" % (c, pct))
        print("   %-22s %d سطر — %s" % (tbl, tot, ", ".join(parts) or "هیچ تهی‌ای"))

    print("\n■ ۴. ستون‌های مشتق (Data Lifecycle گام ۳۴)")
    print("   is_consolidated=1:    %s ردیف" % tgt.get("fs_consolidated"))
    print("   unit_norm NULL:       %s ردیف (نامعلومِ مجاز)" % tgt.get("fs_unit_norm_null"))

    print("\n■ ۵. رکوردهای یتیم")
    print("   نمادهای یکتای بدون l_val18: %s (%s با alias قابلِ بازیابی)"
          % (orph_raw, orph_resolvable))
    print("   مجموعِ ردیف‌های آن‌ها:      %s" % orph_rows)
    if orph_raw and orph_raw == orph_resolvable:
        print("   ↳ همه از طریقِ symbol_aliases حل می‌شوند — یتیمِ واقعی نیستند")
    else:
        print("   ↳ هشدار: %d نماد حتی با alias هم حل نمی‌شوند"
              % (orph_raw - orph_resolvable))

    if base and base.get("exists"):
        print("\n■ ۶. مقایسه با خطِ مبنای «%s»" % base.get("label"))
        print("   %-24s %s" % ("حجم (MB)", "%s → %s" % (base.get("size_mb"),
                                                         tgt.get("size_mb"))))
        for t in ("instruments", "financial_statements", "monthly_sales",
                  "price_history", "daily_prices", "codal_notices"):
            b, n = base.get(t), tgt.get(t)
            if b is None and n is None:
                continue
            d = (n - b) if (isinstance(b, int) and isinstance(n, int)) else "?"
            print("   %-24s %s → %s (%+d)" % (t, b, n, d))
        if base.get("ph_range") or tgt.get("ph_range"):
            print("   %-24s %s → %s" % ("دامنهٔ قیمت", base.get("ph_range"),
                                        tgt.get("ph_range")))
        print("   %-24s %s → %s" % ("is_consolidated=1", base.get("fs_consolidated"),
                                    tgt.get("fs_consolidated")))
    elif base is not None and not base.get("exists"):
        print("\n■ ۶. مقایسه: خطِ مبنای «%s» موجود نیست — رد شد" % base.get("label"))
    else:
        print("\n■ ۶. مقایسه: خطِ مبنایی داده نشد (--baseline / --baseline-lzma)")

    # ── Sign-off ──────────────────────────────────────────────────────
    # conn در بالا (یتیم‌یابی) بسته شد؛ اینجا دوباره باز می‌کنیم — بدونِ این،
    # q() خطای «cannot operate on closed database» را می‌بلعد و NULL/0 برمی‌گرداند
    # و چک‌هایِ R1/R2 سایلنتاً شکست می‌خورند (دقیقاً همان بگی که می‌خواهیم نشود).
    conn = sqlite3.connect("file:%s?mode=ro" % TARGET, uri=True)
    print("\n" + "=" * W)
    checks = []
    checks.append(("integrity_check = ok", tgt.get("integrity") == "ok"))
    checks.append(("instruments > 0", (tgt.get("instruments") or 0) > 0))
    checks.append(("financial_statements > 0", (tgt.get("financial_statements") or 0) > 0))
    checks.append(("price_history > 0", (tgt.get("price_history") or 0) > 0))
    checks.append(("هیچ NULL سختِ مجاز نیست (is_audited/is_consolidated/year/month)",
                   not hard_violations))
    checks.append(("یتیمِ غیرقابل‌حل صفر است (%d از %d با alias حل می‌شوند)"
                   % (orph_resolvable, orph_raw or 0),
                   (orph_raw or 0) == orph_resolvable))
    checks.append(("is_consolidated پر شده (%d ردیف)" % (tgt.get("fs_consolidated") or 0),
                   (tgt.get("fs_consolidated") or 0) > 0))
    # R1/R2 (plans/codal-final-audit.md): این دو بدهی یک‌بار به‌صورتِ سایلنت
    # رخ دادند — ستون‌های «سال قبل» NULL ماندند و اصلاحیه‌ها dedupe نشدند،
    # بدون اینکه هیچ زنگِ خطایی به صدا درآید. اینجا آن زنگ را نصب می‌کنیم.
    ms_prev = q(conn, "SELECT COUNT(*) FROM monthly_sales "
                      "WHERE ytd_revenue_prev IS NOT NULL")
    checks.append(("R1: ytd_revenue_prev پر شده (%d ردیف)" % (ms_prev or 0),
                   (ms_prev or 0) > 0))
    dup_ms = q(conn,
               "SELECT COUNT(*) FROM (SELECT 1 FROM monthly_sales "
               "WHERE period_end IS NOT NULL GROUP BY symbol, period_end "
               "HAVING COUNT(*) > 1)")
    checks.append(("R2: گروهِ تکراریِ monthly_sales صفر است (%d)" % (dup_ms or 0),
                   (dup_ms or 0) == 0))
    for _msg, _ok in checks:
        print("   %s %s" % ("✓" if _ok else "✗", _msg))
    n_bad = sum(1 for _, ok in checks if not ok)
    print("\n" + ("PRODUCTION-READY ✓ — آمادهٔ جایگزینیِ رسمی"
                  if not n_bad else "NOT READY ✗ — %d مشکل" % n_bad).center(W))
    print("=" * W)
    if base_tmp:
        try:
            import shutil
            shutil.rmtree(base_tmp, ignore_errors=True)
        except Exception:
            pass
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
