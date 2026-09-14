# -*- coding: utf-8 -*-
"""
pipeline_updater.py — Dynamic Updater (Task 2) + validation (Task 4) — EXPLORATORY
پیاده‌سازی Trial-and-Error: تست FromDate-based per-symbol update, سپس مقایسه.
"""
import sys, os, json, time, sqlite3, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import codal_fetcher as cf

DB = cf.DB_PATH
QUERY = dict(cf.QUERY)
HDRS = cf._headers() if hasattr(cf, "_headers") else {"User-Agent": "Mozilla/5.0"}


def last_publish(sym):
    conn = sqlite3.connect(DB, timeout=60)
    r = conn.execute("SELECT MAX(publish_date) FROM codal_notices WHERE symbol=?", (sym,)).fetchone()
    conn.close()
    if not r or not r[0]:
        return None
    # نرمال‌سازی رقم‌های فارسی/عربی → ASCII (وگرنه FromDate → HTTP 400)
    v = str(r[0])
    v = v.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    return v[:10]  # فقط تاریخ (YYYY/MM/DD)


def fetch_with_fromdate(sym, cat, from_date):
    """یک صفحه با FromDate — فقط گزارش‌های جدید/اصلاح‌شده."""
    q = dict(QUERY, Symbol=sym, Category=str(cat), LetterType="-1")
    if from_date:
        q["FromDate"] = from_date
    sess = cf.make_session()
    return cf.fetch_page(sess, 1, q, quiet=True, max_429_retries=2)


def update_symbol(sym, from_date=None):
    """Dynamic update: FromDate = آخرین PublishDate موجود → فقط دلتا.
    نماد بدون FS/MS (تازه‌کار) → از_date=None → کل تاریخچه (discovery کامل)."""
    conn0 = sqlite3.connect(DB, timeout=60)
    has_fs = conn0.execute("SELECT 1 FROM financial_statements WHERE symbol=? LIMIT 1", (sym,)).fetchone()
    has_ms = conn0.execute("SELECT 1 FROM monthly_sales WHERE symbol=? LIMIT 1", (sym,)).fetchone()
    conn0.close()
    if from_date is None and (has_fs or has_ms):
        from_date = last_publish(sym)
    if not (has_fs or has_ms):
        from_date = None   # تازه‌کار: کل تاریخچه
    out = {"symbol": sym, "from_date": from_date}
    got = 0
    for cat in ("1", "3"):
        rows = fetch_with_fromdate(sym, cat, from_date)
        if rows is None:
            out["blocked"] = True
            return out
        got += len(rows)
        if rows:
            # تبدیل dict از API → tuple مطابق NOTICE_UPSERT (مثل feed_sync)
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_rows = []
            for x in rows:
                t = x.get("TracingNo")
                if t is None:
                    continue
                title = (x.get("Title") or "").strip()
                if cf.SAVE_USEFUL_ONLY and not cf._positive_title(title):
                    continue
                pdf_raw = (x.get("PdfUrl") or "").strip()
                excel_raw = (x.get("ExcelUrl") or "").strip()
                if pdf_raw and not pdf_raw.startswith("http"):
                    pdf_raw = "https://codal.ir/" + pdf_raw
                if excel_raw and not excel_raw.startswith("http"):
                    excel_raw = "https://codal.ir/" + excel_raw
                new_rows.append((t, (x.get("Symbol") or "").strip(),
                                 (x.get("CompanyName") or "").strip(), title,
                                 (x.get("LetterCode") or "").strip(),
                                 (x.get("PublishDateTime") or "").strip(),
                                 (x.get("SentDateTime") or "").strip(),
                                 "https://codal.ir" + (x.get("Url") or ""),
                                 now, pdf_raw, excel_raw))
            conn = sqlite3.connect(DB, timeout=60, isolation_level=None)
            try:
                known_pe = {r[0] for r in conn.execute(
                    "SELECT DISTINCT period_end FROM financial_statements WHERE symbol=?", (sym,))}
                known_ms_pe = {r[0] for r in conn.execute(
                    "SELECT DISTINCT period_end FROM monthly_sales WHERE symbol=?", (sym,))}
                nf, nm = cf._deep_extract(new_rows, known_pe, known_ms_pe, {}, {}, conn)
                out[f"cat{cat}"] = {"rows": len(new_rows), "fs": nf, "ms": nm}
            finally:
                conn.close()
    out["delta_rows"] = got
    return out


def dedupe_symbol(sym):
    """Task 2 — RECALCULATION: هر period_end فقط آخرین tracing_no (اصلاحیهٔ جدید).
    قدیمی‌ها پاک می‌شوند بدون آسیب به سایر دوره‌ها/نمادها. خروجی: تعداد حذف."""
    conn = sqlite3.connect(DB, timeout=60, isolation_level=None)
    try:
        removed = 0
        # FS: برنده آخرین
        latest = dict(conn.execute(
            "SELECT period_end, MAX(tracing_no) FROM financial_statements "
            "WHERE symbol=? AND period_end IS NOT NULL GROUP BY period_end", (sym,)).fetchall())
        for pe, mx in latest.items():
            cur = conn.execute(
                "DELETE FROM financial_statements WHERE symbol=? AND period_end=? AND tracing_no<>?",
                (sym, pe, mx))
            removed += cur.rowcount
        conn.commit()
        # MS: برنده آخرین (ماهانه‌ها هم اصلاحیه دارند)
        latest_ms = dict(conn.execute(
            "SELECT period_end, MAX(tracing_no) FROM monthly_sales "
            "WHERE symbol=? AND period_end IS NOT NULL GROUP BY period_end", (sym,)).fetchall())
        removed_ms = 0
        for pe, mx in latest_ms.items():
            cur = conn.execute(
                "DELETE FROM monthly_sales WHERE symbol=? AND period_end=? AND tracing_no<>?",
                (sym, pe, mx))
            removed_ms += cur.rowcount
        conn.commit()
        return removed + removed_ms
    finally:
        conn.close()


def sanity_fs(sym):
    """Cross-Verification داخلی (Task 4): ریاضی روی داده‌های خام قبل از بازیابی."""
    conn = sqlite3.connect(DB, timeout=60)
    rows = conn.execute(
        "SELECT period_end, revenue, net_profit, total_assets, total_equity, gross_profit "
        "FROM financial_statements WHERE symbol=? AND net_profit IS NOT NULL "
        "ORDER BY period_end DESC LIMIT 1", (sym,)).fetchall()
    conn.close()
    checks = []
    for r in rows:
        pe, rev, npf, ta, te, gp = r
        ok_profit_le_asset = (ta is None) or (npf is not None and ta is not None and abs(npf) <= ta * 1.05)
        # حاشیه ناخالص منطقی: 0..100%
        margin_ok = (gp is None or rev is None) or (-0.5 <= gp / rev <= 1.5)
        checks.append({"symbol": sym, "period": pe, "net_profit": npf, "total_assets": ta,
                       "margin_ratio": round(gp / rev, 3) if gp and rev else None,
                       "ok_profit_le_asset": bool(ok_profit_le_asset),
                       "ok_margin_range": bool(margin_ok)})
    return checks


def main():
    # ── Task 2: 3 نماد موجود (از میان دارای FS) ──
    conn = sqlite3.connect(DB, timeout=60)
    syms = [r[0] for r in conn.execute(
        "SELECT DISTINCT symbol FROM financial_statements LIMIT 10")]
    conn.close()
    pick = syms[:3]
    print("=== UPDATE existing:", pick)
    for s in pick:
        res = update_symbol(s)
        print(json.dumps(res, ensure_ascii=False))
        time.sleep(2)
    # ── Task 4: sanity ──
    print("=== SANITY:")
    for s in pick:
        print(json.dumps(sanity_fs(s), ensure_ascii=False))
        time.sleep(1)


if __name__ == "__main__":
    main()
