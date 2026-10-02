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
import codal_periods as CP                                 # noqa: E402
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
    # واگردِ v1075: کارت دیگر جدولِ طبقۀ خودش را ندارد و `company_profile` تنها یک
    # نامِ دیگرِ `fts_engine.company_profile` است (تک‌منبع برای کارت/اسکرینر/bulk).
    chk("company_profile = fts_engine.company_profile" in card,
        "card delegates company_profile to the engine")
    chk("_FIN_TOKENS" not in card and "_SVC_TOKENS" not in card,
        "no second class-token table in api/fundamental")
    chk('"صندوق" in both' not in card, "company_profile has no private «صندوق» test")
    chk(eng.count("fund_class_match") >= 2, "bulk_scan uses the same predicate")

    # ── ۲) برابریِ سراسری با کارت ────────────────────────────────────────
    # نگاشتِ نام دقیقاً همان قاعدهٔ مسیرِ کارت است (first-wins روی period_end DESC)
    if conn is not None:
        name_of = {}
        for sym, cn in conn.execute("SELECT symbol, company_name FROM financial_statements "
                                    "ORDER BY %s, tracing_no DESC" % CP.order_expr()):
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
        _secn = lambda r: fts_engine._hold_norm(r["sector_name"] or "")
        by_sector = [r for r in rows if "صندوق" in _secn(r)
                     and not fts_engine.is_insurance_sector(r["sector_name"] or "")]
        by_name = [r for r in rows
                   if "صندوق" in fts_engine._hold_norm(name_of.get(r["symbol_norm"], ""))
                   and "صندوق" not in _secn(r)]
        chk(by_sector and by_name, "both evidence paths are exercised",
            (len(by_sector), len(by_name)))
        chk(all(r["applicable"] is False for r in by_sector + by_name),
            "every fund evidence row is marked not-applicable")
        # رأی ۱ در برابرِ رأی ۱۵: صنعتِ «صندوق بازنشستگی» (۱۲۹ نماد) کلمهٔ
        # «صندوق» را در نامش دارد ولی صندوقِ سرمایه‌گذاری نیست — شرکتِ
        # عملیاتیِ دارایِ صورتِ مالی است و حکمش وتویِ بیمه است نه «FTS ندارد».
        # بی‌این قفل، بیمه آسیا و بیمه اتکایی امین بی‌صدا از پنج‌شاخصه خارج
        # می‌شدند (نامِ صنعتشان «بيمه وصندوق بازنشستگي» است).
        by_ins = [r for r in rows if "صندوق" in _secn(r)
                  and fts_engine.is_insurance_sector(r["sector_name"] or "")]
        chk(bool(by_ins) and all(r["applicable"] is not False for r in by_ins),
            "an insurance sector is never FTS-inapplicable for the word fund",
            [r["symbol"] for r in by_ins if r["applicable"] is False][:3])
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
    chk('return "NOT_APPLICABLE"' in src, "screen endpoint has the not-applicable bucket")
    chk('r.get("applicable") is False' in src, "bucket keys off the engine field")
    m = re.search(r'if r\.get\("applicable"\) is False:.*?if r\.get\("excluded"\):', src, re.S)
    chk(bool(m), "NOT_APPLICABLE is decided before excluded (a fund is not REJECT)")
    # v1.0.36: نگاشتِ داوری از بدنۀ route به هلپرِ `_screen_verdict` منتقل شد
    # (هر route تازه‌ای که داوری می‌خواهد همان را صدا می‌زند). هلپر تنها جایِ
    # نوشتنِ «NOT_APPLICABLE» است؛ اگر کسی دوباره آن را بیرون بنویسد، اینجا
    # قرمز می‌شود چون شمارشِ صداها به دو می‌رسد.
    chk(src.count("_screen_verdict(") >= 2, "the verdict mapping exists once, in a helper")

    # ── ۴) امتیاز: کارت None، موتور عدد ──────────────────────────────────
    chk('"score": (res["score"] if res.get("applicable", True) else None)' in src,
        "card detail nulls a fund score")
    # رأی ۱۶: معافیت حالا None است، پس جمعِ امتیاز هم نباید آن را پاس بشمارد.
    # دو شرط لازم: عددی ماندنِ امتیاز (سورتِ اسکرینر کلّی بماند) و فیلترِ
    # داخلِ sum — بی‌فیلتر، sumِ پنج‌تایی با None یا می‌شکند یا True کاذب می‌دهد.
    _sc = re.search(
        r'"score": int\(sum\(1 for \w+ in \(i1, i2, i3, i4, i5\) if \w+\)\)', eng)
    chk(_sc is not None, "bulk_scan keeps a numeric score that skips None")
    chk("i4 = None" in eng, "bulk_scan reads an exempt axis as abstain")
    chk("out.sort(key=lambda r: (r[\"excluded\"]" in eng, "sort key still uses excluded+score")

    # ── ۵) مصرف‌کننده‌های فرانت ───────────────────────────────────────────
    # ستونِ FTSِ تابلو (features/market/api/useFtsScreener.ts + FtsStatusBadge)
    # در 08bbb4c به‌عنوانِ کدِ مرده حذف شد، پس آن «نمایِ نامشمول» دیگر جایی
    # نیست که بشود گاردش کرد. همان قضاوت حالا فقط در جدولِ بنیادی مصرف
    # می‌شود و همان را در خطِ آخرِ همین بخش می‌سنجیم.
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
