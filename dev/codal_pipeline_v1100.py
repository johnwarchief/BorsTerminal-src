#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/codal_pipeline_v1100.py — گاردِ خطِ دریافت خودکار کدال (Stage 1/2/5/7).

چرا این گارد هست: خودکارسازی یعنی «صف، checkpoint و بازیابی» — و هر سه با
چیزهایی قاطی می‌شوند که درِ تستِ سبزِ معمولی دیده نمی‌شوند:

  * اگر «سطری درِ codal_extracted هست» همان «پردازش‌شده» باشد، صف برایِ همیشه
    کر می‌شود (کارِ کشف‌شده هرگز انجام نمی‌شود).
  * اگر checkpoint پیش از تمام‌شدنِ کارها جلو برود، قطعِ شبکه یعنی از دست
    رفتنِ اطلاعیه‌ها.
  * اگر claim قفل نداشته باشد، دو worker همان گزارش را دو بار scrape می‌کنند.
  * اگر `INSERT OR REPLACE` رویِ سطرِ موجود برود، ستون‌هایِ صف پاک می‌شوند.

همه بی‌شبکه: `discover`/`scrape`/`recalc` تزریق می‌شوند و همان کدِ تولید اجرا
می‌شود (نه یک مسیرِ نمایشی). بانکِ عملیاتی هیچ‌وقت باز نمی‌شود.

اجرا:  PYTHONIOENCODING=utf-8 python dev/codal_pipeline_v1100.py
خروجی: هر بررسی یکِ خط PASS/FAIL + جمعِ «N passed / M failed»؛ exit 0 یا 1
"""
from __future__ import annotations

import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import codal_fetcher as CF                    # noqa: E402
import codal_periods as CP                    # noqa: E402
import codal_pipeline as PL                   # noqa: E402

PASS = FAIL = 0
FS_TITLE = "اطلاعات و صورتهای مالی سال مالی منتهی به ۱۴۰۴/۱۲/۲۹ (حسابرسی شده)"
MS_TITLE = "گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به ۱۴۵/۰۶/۳۱"
FUND_TITLE = "اطلاعات و صورتهای مالی صندوق سرمایه گذاری قابل معامله (ETF)"


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("PASS %s" % what)
    else:
        FAIL += 1
        print("FAIL %s%s" % (what, ("   ← " + str(detail)) if detail else ""))


def fresh_db():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    CF.create_schema(c)
    CF.migrate_schema(c)
    c.execute("CREATE TABLE IF NOT EXISTS instruments (ins_code TEXT PRIMARY KEY,"
              " l_val18 TEXT, l_val30 TEXT, sector_name TEXT, paper_type INTEGER)")
    return c


def notice(c, tn, sym, title=FS_TITLE, pub="1405/07/20 10:00:00"):
    c.execute("INSERT OR REPLACE INTO codal_notices (tracing_no, symbol, company_name,"
              " title, letter_code, publish_date, sent_date, url, fetched_at,"
              " pdf_url, excel_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (tn, sym, sym, title, "1", pub, "", "https://codal.ir/Reports?a=%d" % tn,
               "2026-10-13 00:00:00", "", ""))


def fs_scrape(n):
    """scraperِ فیکِ صورتِ مالی — همان FS_KEYS، همان fs_derived."""
    vals = {k: None for k in CF.FS_KEYS}
    vals.update({"revenue": 1000.0, "gross_profit": 400.0, "net_profit": 200.0,
                 "basic_eps": 50.0})
    pe, _src = CP.derive("1404-12-29", n[3])
    row = ((n[0], n[1], n[2], n[3], "Financial Statements", 12, pe, n[5])
           + tuple(vals.get(k) for k in CF.FS_KEYS)
           + ("کليه مبالغ به ميليون ريال است", n[7], PL.now_s())
           + CF.fs_derived(n[3], pe, "کليه مبالغ به ميليون ريال است", 0))
    return "fs", row, "ok"


def ms_scrape(n):
    pe, _src = CP.derive("1405/06/31", n[3])
    y, m = CP.ym(pe)
    row = (n[0], n[1], n[3], pe, y, m, 100.0, 600.0, None, 500.0, None, None, None,
           n[9], n[10])
    return "ms", row, "ok"


def auto_scrape(n):
    """تقسیمِ کار با خودِ `kind_of` — همان چیزی که `_scrape_one` می‌کند."""
    return ms_scrape(n) if CF.kind_of(n[3]) == "Monthly Activity Report" else fs_scrape(n)


def boom_scrape(n):
    return CF.kind_of(n[3]), None, "failed"


def main() -> int:
    # ── ۱) طرحِ اسکیما: ستون‌هایِ صف رویِ دفترِ موجود + جدول‌هایِ حالت ──────
    c = fresh_db()
    lcols = {r[1] for r in c.execute("PRAGMA table_info(codal_extracted)")}
    need = {n for n, _t in CF._LEDGER_QUEUE_COLS}
    ck(need <= lcols, "مهاجرتِ افزودنی ستون‌هایِ صف را رویِ codal_extracted می‌نشاند",
       sorted(need - lcols))
    tabs = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    ck({"pipeline_cursor", "pipeline_runs", "pipeline_dirty", "pipeline_lock"} <= tabs,
       "چهار جدولِ حالت ساخته شده‌اند (صف، cursor، dirty، lock)")
    c2 = fresh_db()
    PL.ensure_schema(c2)
    PL.ensure_schema(c2)
    ck(True, "مهاجرت یدم‌پذیر است (اجرای دوباره بی‌خطا)")

    # ── ۲) enqueue: یکِ اطلاعیه = یکِ کار، بی‌تکرار ────────────────────────
    n_added = PL.enqueue(c, [(7001, "fs"), (7001, "fs"), (7002, "ms")])
    ck(n_added == 2, "enqueueِ دوباره همان tracing_no کارِ دوم نمی‌سازد", n_added)
    ck(PL.counts(c)["queued"] == 2, "کارهایِ تازه درِ حالت queued می‌مانند",
       PL.counts(c))

    # ── ) «پردازش‌شده» فقط حالتِ پایان‌یافته است (صف نباید کر شود) ────────
    notice(c, 7001, "فولاد", FS_TITLE)
    notice(c, 7002, "خودرو", MS_TITLE)
    processed, _fs_done, _ms_done = CF.derived_state(c)
    ck(7001 not in processed and 7002 not in processed,
       "derived_state کارِ queued را «پردازش‌شده» نمی‌شمارد", sorted(processed))
    pend = [r[0] for r in CF.pending_notices(c)]
    ck(7001 in pend and 7002 in pend,
       "pending_notices کارِ queued را درِ صف نگه می‌دارد", pend)
    # کنترلِ منفی: اگر تعریفِ «تمام‌شده» حذف شود، سنسور باید قرمز شود
    legacy = {r[0] for r in c.execute("SELECT tracing_no FROM codal_extracted")}
    ck(7001 in legacy,
       "دام: سطرِ دفتر از لحظۀ کشف وجود دارد — پس تعریفِ قدیمی دقیقاً همین صف را می‌کشت",
       sorted(legacy))

    # ── ) چرخۀ کامل: کشف ← پردازش ← نوشتنِ canonical ← علامتِ dirty ───────
    recalc_seen = {}

    def recalc(conn, dirty):
        recalc_seen.clear()
        recalc_seen.update(dirty)
        return {"recomputed": len(dirty), "cache_invalidated": 1}

    r = PL.run_cycle(c, "w-test", discover=lambda conn: {"found": 2},
                     scrape=auto_scrape, budget=10, recalc=recalc)
    ck(r["skipped"] is None and r["error"] is None, "چرخه بی‌خطا تمام شد",
       r.get("error"))
    ck(r["done"] == 2 and r["processed"] == 2, "هر دو اطلاعیه پردازش شد", r)
    fs = [tuple(x) for x in c.execute(
        "SELECT tracing_no, symbol, period_end, unit_norm, revenue FROM"
        " financial_statements")]
    ms = [tuple(x) for x in c.execute(
        "SELECT tracing_no, symbol, period_end, ytd_revenue FROM monthly_sales")]
    ck(fs == [(7001, "فولاد", "1404" + chr(47) + "12" + chr(47) + "29", "mrl", 1000.0)],
       "ردیفِ صورتِ مالی با مقیاسِ درست از خودِ منبع نوشته شد", fs)
    ck(len(ms) == 1 and ms[0][0] == 7002 and ms[0][3] == 600.0,
       "فروشِ ماهانه از همان UPSERTِ canonical می‌نشیند", ms)
    ck(set(recalc_seen) == {"فولاد", "خودرو"},
       "محاسبهٔ مجدد فقط نمادهایِ علامت‌خورده را می‌گیرد", sorted(recalc_seen))
    ck(PL.dirty_count(c) == 0, "علامت‌هایِ dirty پس از مصرف پاک می‌شوند",
       PL.dirty_count(c))

    # ── ۵) وابستگیِ هر شاخص به نوعِ داده (نقشۀ dirty) ─────────────────────
    axes_fs = set(PL.AXES_BY_SOURCE["financial_statements"])
    axes_ms = set(PL.AXES_BY_SOURCE["monthly_sales"])
    axes_ins = set(PL.AXES_BY_SOURCE["instruments"])
    ck("2_eps_trend" in axes_fs and "3_gross_margin" in axes_fs and "4_sales_to_mcap" in axes_fs,
       "صورتِ مالی → EPS سه‌ساله، حاشیه و فروش÷ارزش علامت می‌خورد", axes_fs)
    axes_ms2 = {"1_growth", "4_sales_to_mcap"}
    ck(axes_ms == axes_ms2, "فروشِ ماهانه → رشد فروش و فروش÷ارزش", axes_ms)
    ck(axes_ins == {"5_industry"}, "صنعتِ تابلو فقط محور ۵ را علامت می‌خورد", axes_ins)
    c3 = fresh_db()
    PL.dirty_mark(c3, "فولاد", "instruments", "sector")
    got = PL.dirty_take(c3)
    ck(got == {"فولاد": ["5_industry"]}, "علامتِ صنعت شاخص‌هایِ دیگر را آلوده نمی‌کند", got)

    # ── ) یدم‌پذیری: اجرایِ دوباره همان چرخه نتیجه را دو نمی‌کند ──────────
    r2 = PL.run_cycle(c, "w-test", discover=lambda conn: {"found": 0},
                      scrape=auto_scrape, budget=10, recalc=recalc)
    ck(c.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0] == 1
       and c.execute("SELECT COUNT(*) FROM monthly_sales").fetchone()[0] == 1,
       "اجرایِ دوباره رویِ همان داده ردیفِ تکراری یا عددِ تکراری نمی‌سازد",
       (r2["processed"], r2["done"]))
    ck(r2["processed"] == 0, "اجرایِ دوم کاری درِ صف نمی‌بیند (همه پایان‌یافته‌اند)",
       r2["processed"])

    # ── ) اصلاحیه: دو اطلاعیهٔ هم‌دوره هر دو می‌مانند و مرجع یکی می‌شود ────
    notice(c, 7003, "فولاد", FS_TITLE)            # همان نماد، همان دوره،tn تازه
    PL.enqueue(c, [(7003, "fs")])
    r3 = PL.run_cycle(c, "w-test", scrape=auto_scrape, budget=10, recalc=recalc)
    rows = c.execute("SELECT tracing_no, revenue FROM financial_statements"
                     " WHERE symbol='فولاد' ORDER BY tracing_no").fetchall()
    ck(len(rows) == 2, "اصلاحیه ردیفِ تاریخی را حذف نمی‌کند (حفظِ تاریخچه)",
       [tuple(x) for x in rows])
    ck(r3["done"] == 1, "اصلاحیه پردازش شد و علامتِ dirty گرفت", r3)
    import fts_engine as FE
    ref = FE.reference_annual(c, "فولاد", need="margin")
    ck(ref and int(ref.get("tracing_no") or 0) in (7001, 7003),
       "انتخابِ مرجع از لایۀ خواندن می‌آید، نه از آخرین نوشتن",
       (ref or {}).get("tracing_no"))

    # ── ۸) خطای شبکه: checkpoint جلو نمی‌رود و کار دوباره تلاش می‌شود ──────
    c4 = fresh_db()
    notice(c4, 8001, "فولاد", FS_TITLE)
    r4 = PL.run_cycle(c4, "w1", scrape=boom_scrape, budget=5)
    cnt = PL.counts(c4)
    ck(cnt["failed"] == 1 and cnt["queued"] == 0,
       "شکستِ شبکه حالتِ failed می‌گیرد (نه done، نه حذف)", cnt)
    ck(r4["checkpoint_after"] is None,
       "با کارِ باز، checkpoint جلو نمی‌رود (بازیابی ممکن می‌ماند)",
       r4["checkpoint_after"])
    row = c4.execute("SELECT attempts, next_attempt_at, error_kind FROM codal_extracted"
                     " WHERE tracing_no=8001").fetchone()
    ck(row["attempts"] == 1 and row["next_attempt_at"] and row["error_kind"] == "network",
       "تعدادِ تلاش، زمانِ تلاشِ بعد و علت از هم جدا ثبت می‌شوند", tuple(row))
    # بلافاصله نباید دوباره تلاش شود (backoff)
    ck(PL.claim(c4, "w1", limit=5) == [], "backoff واقعاً کار را عقب می‌اندازد")
    # با گذشتِ زمانِ backoff دوباره قابلِ گرفتن است
    future = "2099-01-01 00:00:00"
    ck(len(PL.claim(c4, "w1", limit=5, now=future)) == 1,
       "پس از مهلتِ backoff کار دوباره قابلِ تلاش است")
    # بودجه تمام → unresolved (نه بی‌نهایت retry)
    for _ in range(6):
        PL.mark_failed(c4, 8001, error_kind="network", last_error="429")
        PL.claim(c4, "w1", limit=5, now=future)
    st = c4.execute("SELECT state FROM codal_extracted WHERE tracing_no=8001").fetchone()
    ck(st["state"] == "unresolved", "بودجۀ تلاش تمام شود → unresolved (نه صفِ ابدی)",
       st["state"])

    # ── ۹) دو worker هم‌زمان: یکِ کار فقط یک‌بار گرفته می‌شود ───────────────
    c5 = fresh_db()
    notice(c5, 9001, "فولاد", FS_TITLE)
    PL.enqueue(c5, [(9001, "fs")])
    a = PL.claim(c5, "A", limit=5)
    b = PL.claim(c5, "B", limit=5)
    ck(len(a) == 1 and b == [], "claimِ هم‌زمان فقط به یکِ worker کار می‌دهد", (a, b))
    ck(PL.lock_acquire(c5, "codal_pipeline", "A")
       and not PL.lock_acquire(c5, "codal_pipeline", "B"),
       "قفلِ worker نگه دو process را از اجرایِ هم‌زمانِ یکِ خط باز می‌دارد")
    ck(PL.run_cycle(c5, "B", scrape=auto_scrape, budget=5)["skipped"] == "locked",
       "workerِ دوم چرخه را تکرار نمی‌کند (skipped=locked)")

    # ── ۰) restart درِ میانهٔ کار: claimِ بی‌صاحب دوباره صف می‌شود ─────────
    c6 = fresh_db()
    notice(c6, 9101, "فولاد", FS_TITLE)
    PL.enqueue(c6, [(9101, "fs")])
    PL.claim(c6, "dead-worker", limit=5)          # claim، بی‌اتمام (کرش)
    ck(PL.counts(c6)["running"] == 1, "کارِ در حال اجرا 'running' است")
    released = PL.release_stale(c6, older_than_s=-1)   # «همه قدیمی‌اند»
    ck(released == 1 and PL.counts(c6)["queued"] == 1,
       "claimِ بی‌صاحب دوباره به صف برمی‌گردد (کار گم نمی‌شود)", PL.counts(c6))
    r6 = PL.run_cycle(c6, "w-new", scrape=auto_scrape, budget=5)
    ck(r6["done"] == 1 and c6.execute(
        "SELECT COUNT(*) FROM financial_statements").fetchone()[0] == 1,
       "پس از بازیابی، همان کار یک‌بار و کامل انجام می‌شود", r6)

    # ── ۱۱) catch-up: بودجه محدود، صفِ بزرگ تهی می‌شود ولی نه یک‌باره ──────
    c7 = fresh_db()
    for i in range(12):
        notice(c7, 9200 + i, "فولاد%d" % i, FS_TITLE)
    PL.enqueue(c7, [(9200 + i, "fs") for i in range(12)])
    r7 = PL.run_cycle(c7, "w", scrape=auto_scrape, budget=4)
    ck(r7["processed"] == 4 and PL.counts(c7)["queued"] == 8,
       "بودجۀ چرخه واقعاً کار را محدود می‌کند (بی‌قفل‌شدن UI)",
       (r7["processed"], PL.counts(c7)["queued"]))
    for _ in range(3):
        PL.run_cycle(c7, "w", scrape=auto_scrape, budget=4)
    ck(PL.counts(c7)["queued"] == 0 and PL.counts(c7)["done"] == 12,
       "چرخه‌هایِ متوالی صف را تا تهی ادامه می‌دهند", PL.counts(c7))

    # ── ۱۲) صندوق/مشتق مثلِ شرکتِ عملیاتی فرض نمی‌شود ──────────────────────
    c8 = fresh_db()
    notice(c8, 9301, "ابن sina", FUND_TITLE)
    c8.execute("INSERT INTO instruments (ins_code, l_val18, l_val30, sector_name,"
               " paper_type) VALUES ('IC1','ابن sina','صندوق سرمايه گذاري','صندوق', 4)")
    pend8 = [r[0] for r in CF.pending_notices(c8)]
    ck(9301 not in pend8,
       "صندوق وارد صفِ استخراجِ صورتِ مالی نمی‌شود (بودجه را بی‌فایده نمی‌خورد)", pend8)

    # ── ۱۳) گزارشِ چرخه: شمارش‌ها از جدول، و شکست به‌حسابِ موفقیت نمی‌آید ───
    lr = PL.last_run(c4, cycle="cycle")
    ck(lr and lr["failed"] >= 1 and lr["error"] is None,
       "شمارشِ شکست از خودِ حالت‌هایِ صف خوانده می‌شود",
       (lr or {}).get("failed"))
    c9 = fresh_db()
    rid = PL.run_start(c9, "cycle", "w", checkpoint_before="1405/07/19")
    PL.run_update(c9, rid, found=1, enqueued=1)
    PL.run_finish(c9, rid, error="RuntimeError: boom")
    h = PL.health(c9)
    ck(h["last_successful_sync"] is None,
       "چرخۀ شکست‌خورده هرگز «آخرین همگام‌سازی موفق» نمی‌شود",
       h["last_successful_sync"])
    ck(h["last_attempt"] and h["last_attempt"]["error"],
       "علت شکست درِ وضعیتِ قابل‌مشاهده می‌ماند", (h["last_attempt"] or {}).get("error"))

    # ── ۱۴) کنترلِ منفیِ کلی: اگر «تمام‌شده» را گسترش دهیم، بندِ ۳ می‌میرد ──
    wide = CF.ledger_terminal_sql().replace("'done','empty','unresolved'",
                                            "'done','empty','unresolved','queued'")
    q_ids = {r[0] for r in c.execute(
        "SELECT tracing_no FROM codal_extracted WHERE %s" % wide)}
    ck(7001 in q_ids,
       "دامِ سنسور: با تعریفِ معیوب، صف «پردازش‌شده» می‌شود (بندِ ۳ عملاً تست می‌شود)",
       sorted(q_ids))

    for conn in (c, c2, c3, c4, c5, c6, c7, c8, c9):
        conn.close()
    print("%d passed / %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
