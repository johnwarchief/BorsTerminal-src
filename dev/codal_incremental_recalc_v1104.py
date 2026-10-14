#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/codal_incremental_recalc_v1104.py — گاردِ بندِ ۷: محاسبۀ افزایشیِ پنج شاخص.

خواستهٔ مأموریت: «اطلاعیهٔ جدید فقط نمادها و شاخص‌های متاثر را invalidate کند» و
«بی‌dependency tracking قابل‌اعتماد، محاسبۀ محافظه‌کارانۀ بیشتر بهتر از stale
result است». این گارد همان دو چیز را می‌سنجد — و دو دامِ واقعی:

  * اگر باطل‌کردن سراسری باشد، هر اطلاعیه کل `fts_results` را دور می‌ریزد و
    اسکرینر به محاسبۀ زندۀ ~۲۷ثانیه‌ای می‌افتد (شاهدِ تاریخی درِ EXE).
  * اگر محاسبه‌گر بی‌موفقیت هم علامت را پاک کند، «نتیجهٔ کهنه» جای
    «هنوز محاسبه نشده» را می‌گیرد و رابط رأیِ قدیمی نشان می‌دهد.

هیچ فرمول یا آستانه‌ای اینجا نوشته نمی‌شود؛ نقشۀ وابستگی همان
`codal_pipeline.AXES_BY_SOURCE` است و باطل‌کننده همان
`fts_engine.invalidate_fts_results`. بی‌شبکه، بی‌`market.db`.

اجرا:  PYTHONIOENCODING=utf-8 python dev/codal_incremental_recalc_v1104.py
خروجی: «N passed / M failed»، exit 0 یا 1
"""
from __future__ import annotations

import inspect
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["BORS_CODAL_OFFLINE"] = "1"

import codal_fetcher as CF                    # noqa: E402
import codal_pipeline as PL                   # noqa: E402
import fts_engine as FE                       # noqa: E402

PASS = FAIL = 0


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


def seed_materialized(c, syms):
    for i, sym in enumerate(syms):
        c.execute("INSERT OR REPLACE INTO fts_results (symbol, score, verdict,"
                  " computed_at) VALUES (?,?,?,?)",
                  (sym, 50 + i, "green", "2026-10-14 00:00:00"))
    c.commit()


def materialized(c):
    return sorted(r[0] for r in c.execute("SELECT symbol FROM fts_results"))


def main() -> int:
    # ── ۱) نقشۀ وابستگی: نوعِ داده ⇒ شاخص‌هایِ مشخص ───────────────────────
    m = PL.AXES_BY_SOURCE
    ck(set(m["financial_statements"]) == {"1_growth", "2_eps_trend",
                                         "3_gross_margin", "4_sales_to_mcap"},
       "صورتِ مالی چهار شاخص را متاثر می‌کند (رشد، EPS، حاشیه، فروش/ارزش)",
       m["financial_statements"])
    ck(set(m["monthly_sales"]) == {"1_growth", "4_sales_to_mcap"},
       "فروشِ ماهانه فقط رشد و فروش/ارزش را متاثر می‌کند", m["monthly_sales"])
    ck(set(m["instruments"]) == {"5_industry",},
       "دفترِ ابزار فقط فیلترِ صنعت را متاثر می‌کند", m["instruments"])
    ck(set(m["market_watch"]) == {"4_sales_to_mcap",},
       "تابلو فقط مخرجِ شاخصِ مقیاس‌سنج را عوض می‌کند", m["market_watch"])

    # ── ۲) باطل‌کردن فقط نمادِ متاثر، نه کل بازار ──────────────────────────
    c = fresh_db()
    seed_materialized(c, ["فولاد", "خودرو", "شپنا"])
    n_all_before = len(materialized(c))
    PL.dirty_mark(c, "فولاد", "financial_statements", reason="tracing_no=111")
    taken = PL.dirty_take(c)
    ck(list(taken) == ["فولاد"] and taken["فولاد"].count("1_growth") == 1,
       "یکِ علامت = یکِ نماد با همان فهرستِ شاخص‌ها", taken)
    # محاسبه‌گرِ پیش‌فرض: باطل‌کنندهٔ ردیفِ مادی‌شدهٔ همان نماد
    res = PL.recompute_dirty(c, taken)
    ck(res["recomputed"] == 1 and res["cache_invalidated"] == 1,
       "یکِ نماد ⇒ یکِ ردیفِ مادی‌شدۀ باطل‌شده", res)
    ck(materialized(c) == ["خودرو", "شپنا"],
       "ردیفِ نمادهایِ بی‌ربط دست‌نخورده ماند (بی‌ریختنِ کل جدول)",
       materialized(c))
    ck(n_all_before == 3, "کنترلِ اندازه: سه ردیفِاولیۀ تست داشتیم", n_all_before)

    # ── ۳) باطل‌کنندۀ مادی‌شده با `symbols` و بی‌آن (سازگاری) ──────────────
    n = FE.invalidate_fts_results(c, symbols=["خودرو"])
    ck(n == 1 and materialized(c) == ["شپنا"],
       "`invalidate_fts_results(conn, symbols=…)` همان نماد را می‌بَرد",
       (n, materialized(c)))
    seed_materialized(c, ["الف", "ب"])
    n2 = FE.invalidate_fts_results(c)
    ck(n2 == 3 and not materialized(c),
       "بی‌`symbols` رفتارِ دیروز (کل جدول، سه ردیفِ باقی‌مانده) دست‌نخورده است", n2)
    n3 = FE.invalidate_fts_results(c, symbols=["نبودم"])
    ck(n3 == 0, "نمادِ بی‌ردیف هیچ چیزی را پاک نمی‌کند", n3)

    # ── ۴) محاسبه‌گرِ شکست‌خورده ⇒ علامت می‌ماند (نتیجهٔ کهنه نه) ───────────
    c2 = fresh_db()
    seed_materialized(c2, ["فولاد", "خودرو"])
    PL.dirty_mark(c2, "فولاد", "monthly_sales", reason="tracing_no=222")
    PL.dirty_mark(c2, "خودرو", "financial_statements", reason="tracing_no=333")
    taken2 = PL.dirty_take(c2)
    ck(PL.dirty_count(c2) == 0, "dirty_take علامت‌ها را برداشت",
       PL.dirty_count(c2))

    def judge(conn, sym, axes):
        return sym != "خودرو"          # خودرو محاسبه نمی‌شود (خطای داده)

    res2 = PL.recompute_dirty(c2, taken2, judge=judge)
    ck(res2["recomputed"] == 1 and res2["failed"] == 1,
       "نامشخص/ناموفق از محاسبه‌شد جدا شمرده می‌شود", res2)
    ck(PL.dirty_count(c2) == 0,
       "در این لایه چیزی برنمی‌گردد (صرفاً شمارش) — بازگشتِ علامت کارِ run_cycle است",
       PL.dirty_count(c2))

    c3 = fresh_db()
    seed_materialized(c3, ["فولاد", "خودرو"])
    PL.dirty_mark(c3, "فولاد", "financial_statements", reason="tracing_no=444")
    PL.dirty_mark(c3, "خودرو", "financial_statements", reason="tracing_no=555")

    def cycle_recalc(conn, dirty):
        return PL.recompute_dirty(conn, dirty, judge=judge)

    out = PL.run_cycle(c3, "w-recalc", recalc=cycle_recalc, instruments=None,
                       now="2026-10-14 20:00:00")
    ck(out["recomputed"] == 1 and out["recalc_failed"] == 1,
       "چرخه شمارشِ محاسبه/شکست را از محاسبه‌گر می‌گیرد",
       {k: out[k] for k in ("recomputed", "recalc_failed", "cache_invalidated")})
    left = {r[0]: r[1] for r in c3.execute("SELECT symbol, reason FROM pipeline_dirty")}
    ck(list(left) == ["خودرو"],
       "نمادی که محاسبه نشد دوباره علامت می‌خود (نتیجهٔ کهنه جایِ «محاسبه‌نشده» نمی‌نشیند)",
       left)
    ck(left.get("خودرو") == "recalc-missed",
       "علتِ بازگشت درِ رکورد می‌ماند", left.get("خودرو"))
    ck(materialized(c3) == [],
       "نمادِ بی‌محاسبه هم ردیفِ مادی‌شدهاش را از دست می‌دهد ⇒ هیچ خواننده‌ای نتیجهٔ کهنه نمی‌گیرد",
       materialized(c3))

    # ── ۵) اصلاحیه و دورۀ قبل هم درِ وابستگی لحاظ می‌شوند ──────────────────
    c4 = fresh_db()
    seed_materialized(c4, ["فولاد"])
    PL.dirty_mark(c4, "فولاد", "financial_statements", reason="tracing_no=601")
    PL.dirty_mark(c4, "فولاد", "financial_statements", reason="tracing_no=602")
    rows = list(c4.execute("SELECT symbol, axis, reason FROM pipeline_dirty"))
    ck(len(rows) == 4 and all("tracing_no=" in (r[2] or "") for r in rows),
       "دو اطلاعیهٔ هم‌نماد (اصلی + اصلاحیه) با ردپایِ شناسه ثبت می‌مانند",
       [tuple(r) for r in rows])
    PL.dirty_mark(c4, "فولاد", "monthly_sales", reason="tracing_no=603")
    after = {r[0]: r[1] for r in c4.execute(
        "SELECT axis, reason FROM pipeline_dirty WHERE symbol='فولاد'")}
    ck(after.get("1_growth") == "tracing_no=603",
       "علامتِ تازه علتِ تازه می‌گیرد (نسخۀ آخرِ دلیل، نه انباشتِ بی‌پایان)", after)
    ck(len(after) == 4, "شاخصِ پنجم (فیلترِ صنعت) به‌خاطرِ صورتِ مالی علامت نمی‌خورد",
       sorted(after))

    # ── ۶) هیچ فرمول/آستانۀ تازۀ‌ای ساخته نمی‌شود ──────────────────────────
    src = inspect.getsource(PL.recompute_dirty)
    body = "\n".join(l for l in src.splitlines()
                     if not l.strip().startswith(("#", '"')))
    ck(not any(tok in body for tok in (">= 0.", "> 1.", "< 0.", "score =")),
       "بدنۀ recompute_dirty هیچ مقایسه/آستانه‌ای ندارد (فقط مصرفِ علامت‌ها)",
       [t for t in (">= 0.", "> 1.", "< 0.", "score =") if t in body])
    n_fs_before = int(c4.execute("SELECT COUNT(*) FROM financial_statements")
                      .fetchone()[0])
    PL.recompute_dirty(c4, PL.dirty_take(c4))
    ck(int(c4.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0])
       == n_fs_before,
       "محاسبۀ افزایشی هیچ ردیفِ canonical نمی‌نویسد (خواننده می‌خواند)", n_fs_before)

    # ── ۷) چرخه با `recalc="auto"` همان مسیرِ تولید را می‌زند ──────────────
    c5 = fresh_db()
    seed_materialized(c5, ["فولاد", "شپنا"])
    PL.dirty_mark(c5, "فولاد", "instruments", reason="instrument:new")
    out5 = PL.run_cycle(c5, "w-auto-recalc", recalc="auto", instruments=None,
                        now="2026-10-14 20:00:00")
    ck(out5["recomputed"] == 1 and materialized(c5) == ["شپنا"],
       "recalc='auto' ⇒ باطل‌کنندۀ واقعیِ همان نماد صدا زده می‌شود",
       (out5["recomputed"], materialized(c5)))
    ck(out5["dirty"] == 0,
       "علامتِ مصرف‌شده پاک می‌ماند و شمارشِ سلامت درست است", out5["dirty"])

    # ── ۸) شکستنِ کشِ خواننده: payload اسکرینر پس از مصرفِ dirty ────────────
    src2 = inspect.getsource(PL.recompute_dirty)
    ck("invalidate_screener_cache" in src2 and "drop_materialized=False" in src2,
       "باطل‌سازِ payload اسکرینر درِ همان مصرفِ dirty صدا زده می‌شود (بدونِ کشتنِ جدول)",
       [l.strip() for l in src2.splitlines() if "screener" in l][:2])
    ck("dropped" in src2,
       "و فقط وقتی چیزی واقعاً باطل شده (چرخۀ بی‌کار کش را خالی نمی‌کند)",
       "dropped" in src2)


    print("\n%d passed / %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
