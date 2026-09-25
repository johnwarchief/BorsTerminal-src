#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/fund_not_applicable_v1028.py — صندوق هیچ‌جا «مردود» نمی‌شود (رأی ۱۵).

چرا: رأی ۱۵ فقط در کارتِ جزئیات اجرا می‌شد. جدولِ غربالگری
(/api/fundamental/screen) همان نماد را REJECTED می‌گفت، ستونِ FTSِ تابلو
(resolveFtsStatus) آن را «تأیید» می‌گفت اگر excluded نبود، و دروازهٔ مستر
(isSuperFundamental) می‌توانست صندوق را سوپربنیادی بخواند. یک نماد، سه جواب.

این گارد چهار چیز را الزامی می‌کند:
  ۱) تک‌مرجع بودن طبقهٔ صندوق (fts_engine.fund_class_match) در سه مسیر؛
  ۲) برابریِ «applicable» بین bulk_scan و کارت (company_profile) روی تمامِ بانک؛
  ۳) حکمِ NOT_APPLICABLE در /api/fundamental/screen و نبودِ آن برای تولیدی‌ها؛
  ۴) اینکه امتیازِ عددی در bulk_scan دست‌نخورده مانده (sort نمی‌شکند) در حالی
     که کارت امتیازِ صندوق را None می‌دهد.

خروج: ۰ = همه درست، ۱ = واگرایی.
اجرا:  python dev/fund_not_applicable_v1028.py
"""
import io
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import fts_engine                                          # noqa: E402
import api.fundamental as fundamental                       # noqa: E402

PASS = FAIL = 0


def chk(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL  %s %s" % (label, extra))


def _read(rel):
    with io.open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def _real_bank():
    """market.db کنارِ EXE/ریپو؛ در CI نیست → بخشِ دیتا SKIP می‌شود (همان
    قراردادِ dev/mstat_local_v975.py: گاردهای استاتیک همیشه، دیتا اگر بود)."""
    for cand in (os.path.join(ROOT, "market.db"), os.path.join(ROOT, "..", "market.db")):
        if os.path.isfile(cand):
            return cand
    return None


def main():
    db = _real_bank()
    conn = sqlite3.connect("file:%s?mode=ro" % db, uri=True) if db else None
    conn_row = conn
    cfg = fts_engine.load_fts_config(os.path.join(ROOT, "fts_thresholds.json"))
    rows = fts_engine.bulk_scan(conn, cfg=cfg) if conn is not None else []
    if conn is None:
        print("SKIP: market.db not found — برابریِ سراسری روی بانکِ واقعی نخوانده شد")
    else:
        chk(len(rows) > 500, "bulk_scan produced rows", len(rows))

    # ── ۱) تک‌مرجع ────────────────────────────────────────────────────────
    eng = _read("fts_engine.py")
    card = _read(os.path.join("api", "fundamental.py"))
    chk("def fund_class_match(" in eng, "engine has one fund predicate")
    chk("fts_engine.fund_class_match(sector, company_name)" in card,
        "company_profile uses the engine predicate")
    chk('"صندوق" in both' not in card, "company_profile has no private «صندوق» test")
    chk(eng.count("fund_class_match") >= 2, "bulk_scan uses the same predicate")

    # ── ۲) برابریِ سراسری با کارت ────────────────────────────────────────
    # نگاشتِ نام دقیقاً همان قاعدهٔ مسیرِ کارت است (first-wins روی period_end DESC)
    if conn is not None:
        name_of = {}
        for sym, cn in conn.execute("SELECT symbol, company_name FROM financial_statements "
                                    "ORDER BY period_end DESC"):
            k = fts_engine.norm_fa(sym)
            if k and k not in name_of:
                name_of[k] = cn or ""
        bad = []
        n_na = 0
        for r in rows:
            key = r["symbol_norm"]
            want = fundamental.company_profile(r.get("sector_name", ""),
                                               name_of.get(key, ""))["kind"] != "fund"
            if bool(r.get("applicable", True)) != want:
                bad.append((r["symbol"], want, r.get("applicable")))
            if not want:
                n_na += 1
        chk(not bad, "bulk_scan ⇄ card agree on every symbol", bad[:4])
        chk(n_na > 50, "the fund class is actually present in the bank", n_na)
        # طبقه‌بندی باید از صنعت *یا* نامِ شرکت بیاید، نه فقط یکی‌شان
        by_sector = [r for r in rows if "صندوق" in fts_engine._hold_norm(r["sector_name"])]
        by_name = [r for r in rows
                   if "صندوق" in fts_engine._hold_norm(name_of.get(r["symbol_norm"], ""))
                   and "صندوق" not in fts_engine._hold_norm(r["sector_name"])]
        chk(by_sector and by_name, "both evidence paths are exercised",
            (len(by_sector), len(by_name)))
        chk(all(r["applicable"] is False for r in by_sector + by_name),
            "every fund evidence row is marked not-applicable")
        chk_conn = conn
    else:
        chk_conn = None
        # بی‌بانک هم تک‌مرجعِ نام‌ها سنجیده می‌شود (بدونِ SQL)
        chk(fundamental.company_profile("صندوق سرمایه‌گذاری", "ایکس")["kind"] == "fund",
            "sector alone classifies a fund")
        chk(fundamental.company_profile("سرمایه گذاریها", "صندوق بازنشستگی آ")["kind"] == "fund",
            "company name alone classifies a fund")
        chk(fundamental.company_profile("فلزات", "فولاد")["kind"] != "fund",
            "a producer is never a fund")

    # ── ۳) مسیرِ اسکرین ──────────────────────────────────────────────────
    src = _read(os.path.join("api", "fundamental.py"))
    chk('vrd = "NOT_APPLICABLE"' in src, "screen endpoint has the not-applicable bucket")
    chk('r.get("applicable") is False' in src, "bucket keys off the engine field")
    m = re.search(r'if r\.get\("applicable"\) is False:.*?elif is_excluded:', src, re.S)
    chk(bool(m), "NOT_APPLICABLE is decided before excluded (a fund is not REJECT)")

    # ── ۴) امتیاز: کارت None، موتور عدد ──────────────────────────────────
    chk('"score": (res["score"] if res.get("applicable", True) else None)' in src,
        "card detail nulls a fund score")
    chk(re.search(r'"mcap": mcap, "score": int\(sum\(\[i1, i2, i3, i4, i5\]\)\)', eng)
        is not None, "bulk_scan keeps a numeric score (sort stays total)")
    chk("out.sort(key=lambda r: (r[\"excluded\"]" in eng, "sort key still uses excluded+score")

    # ── ۵) مصرف‌کننده‌های فرانت ───────────────────────────────────────────
    screener = _read(os.path.join("frontend", "src", "features", "market", "api",
                                  "useFtsScreener.ts"))
    chk("hit.applicable === false" in screener,
        "tape FTS column has a not-applicable view")
    gates = _read(os.path.join("frontend", "src", "features", "master", "lib",
                               "strictGates.ts"))
    chk("ftsApplicable(fund)" in gates, "master gate refuses a non-applicable symbol")
    sig = _read(os.path.join("frontend", "src", "features", "fundamental", "signals",
                             "fundamentalSignals.ts"))
    chk("notApplicableSignal" in sig, "fundamental agent emits a neutral not-applicable signal")
    screen_schema = _read(os.path.join("frontend", "src", "features", "fundamental",
                                       "api", "useFtsScreen.ts"))
    chk("applicable: z.boolean().nullish()" in screen_schema,
        "screen row schema carries applicable")

    if conn_row is not None:
        conn_row.close()
    print("fund-not-applicable: %d pass / %d fail" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
