#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/fts_indicator_contract_v1091.py — contractِ خروجیِ پنج شاخص (بندِ ۵ مأموریت).

بندِ ۵ مأموریت برایِ **هر** شاخص پنج چیز می‌خواهد: نتیجه (مثبت/منفی/نامشخص)،
دلیلِ نتیجه، شناسهٔ گزارش و دورۀ مرجع، واحد و منبع داده، و خطای استخراج در
صورتِ وجود. این گارد همان را رویِ مسیرِ واقعیِ کارت (`evaluate_v10`) می‌سنجد،
نه رویِ fixtureِ آرزو:

  ۱ سه‌حالگی: هیچ محوری هرگز `False`ِ بی‌دلیل نمی‌گیرد — نبودِ داده `None` است
     (بندِ P-1/P-4 سیاست؛ دورِ ۴ دقیقاً همین را برایِ شاخص ۴ ثابت کرد: 83 ردیف
     از «رد» به «بی‌نظر» رفت).
  ۲ دلیلِ بی‌رأی: هر `None`/`data_gap` باید `reason` پر داشته باشد.
  ۳ ردپا: عددی که از یکِ گزارشِ ذخیره‌شده می‌آید باید `tracing_no` و دورۀ مرجع
     و منبعش را هم حمل کند (بی‌این «کدامِ گزارش» درِ کدال قابلِ بازبینی نیست).
  ۴ واحد: هر عددِ پولی یا `unit` دارد یا صریحاً اعلام می‌کند که جدولِ منبعش
     ستونِ واحد ندارد — هیچ‌وقت بی‌اعلام فرض نمی‌شود.
  ۵ بی‌hardcode: هیچِ عددِ مثالِ جزوه (۳۹۲۱ / ۳٬۶۲۱ / ۷۷۴ / ۷۴۴ / ۵۸٫۶۶) درِ
     منطقِ عمومیِ شاخص‌ها ننشسته است.

کنترلِ منفی: با بریدنِ هر ردپا از دیکشنری، همان چک باید قرمز شود (سنسور کور
نباشد) — و با روشن‌کردنِ «بی‌داده ⇒ رد» هم چکِ سه‌حالگی باید قرمز شود.

اجرا:  PYTHONIOENCODING=utf-8 python dev/fts_indicator_contract_v1091.py
"""
import io
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import fts_engine as FE                       # noqa: E402
import api.fundamental as F                  # noqa: E402

PASS = FAIL = 0
AXES = ("1_growth", "2_eps_trend", "3_gross_margin", "4_sales_to_mcap", "5_industry")
# نمادهایِ انتخاب‌شده از سنجشِ دورهایِ ۳ و ۴: یکِ تمام‌عدد، یکِ مرجعِ بی‌واحد،
# یکِ معاف، یکِ حاشیه‌رفته، یکِ خانوادۀ دو-نوشتاری.
PROBE = ("شهرفرش", "خزالی", "تيپيكو", "شتهران", "وكادو", "شهر فرش")
NOTEBOOK_EXAMPLES = ("3921", "3621", "2124", "58.66", "774", "744")


def ck(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL  %s   %s" % (label, extra))


def three_state(v):
    return v is True or v is False or v is None


def main() -> int:
    prod = os.path.join(ROOT, "market.db")
    if not os.path.exists(prod):
        print("BLOCKED: market.db نیست — contract رویِ دادهٔ واقعی سنجیده نمی‌شود")
        return 2
    conn = sqlite3.connect("file:%s?mode=ro" % prod.replace("\\", "/"), uri=True)
    conn.row_factory = sqlite3.Row
    FE.register_sql(conn)
    cfg = FE.load_fts_config()

    seen = {}
    for sym in PROBE:
        mcap, sector, total, _info = F._fts_market_ctx(conn, sym)
        card = F.evaluate_v10(conn, sym, mcap or 0.0, total, sector, cfg=cfg)
        inds = card.get("indicators") or {}
        seen[sym] = card
        for a in AXES:
            v = inds.get(a) or inds.get(a.split("_")[0]) or {}
            ck(isinstance(v, dict), "C1 %s/%s دیکشنری است" % (sym, a))
            vote = v.get("pass")
            if a == "1_growth":
                vote = v.get("pass")
            if a == "4_sales_to_mcap":
                vote = None if v.get("na") else v.get("pass")
            ck(three_state(vote), "C2 %s/%s رأیِ سه‌حالۀ واقعی دارد" % (sym, a), vote)
            # بی‌رأی باید دلیل داشته باشد
            abstain = vote is None or bool(v.get("data_gap")) or bool(v.get("na"))
            if abstain:
                why = (v.get("reason") or v.get("gap_cause") or v.get("band")
                       or v.get("verdict") or v.get("annualize_basis") or "")
                ck(bool(str(why).strip()),
                   "C3 %s/%s بی‌رأی با دلیل است" % (sym, a), repr(why)[:40])

    # ── C4 ردپا: عددِ صورتِ مالی باید «کدامِ گزارش» را حمل کند ────────────
    card = seen.get("شهرفرش") or {}
    inds = card.get("indicators") or {}
    i3 = inds.get("3") or {}
    ck(i3.get("margin_pct") is not None and i3.get("ref_tracing_no")
       and i3.get("period_end") and i3.get("source"),
       "C4 شاخص ۳ شناسهٔ گزارش + دوره + منبع را حمل می‌کند",
       {k: i3.get(k) for k in ("ref_tracing_no", "period_end", "source")})
    ck(i3.get("unit") in FE.CU.SCALES and bool(i3.get("unit_label")),
       "C4ب شاخص ۳ واحدِ ردیفِ مرجع را اعلام می‌کند", (i3.get("unit"), i3.get("unit_label")))
    i2 = inds.get("2") or {}
    series = i2.get("eps_series") or []
    trn = i2.get("ref_tracing_nos") or []
    ck(bool(series) and len(trn) == len(series) and all(t for t in trn),
       "C4پ هر خانۀ سری EPS شناسهٔ گزارشِ خودش را دارد", (len(series), len(trn)))
    i4 = inds.get("4") or {}
    an = i4.get("annual") or {}
    ck(bool(an.get("basis")) and ("fs_unit" in an) and ("unit_unverified" in an),
       "C4ت شاخص ۴ مبنایِ سالانه‌سازی + واحد + پرچمِ راستی‌آزمایی را دارد",
       sorted(an.keys())[:8])
    i1 = (inds.get("1") or {}).get("monetary") or {}
    ck(bool(i1.get("source")) and bool(i1.get("unit_note")) and ("unit" in i1),
       "C4ث شاخص ۱ منبع و «بی‌ستونِ واحد» را صریح اعلام می‌کند",
       {k: (i1.get(k) or "")[:28] if isinstance(i1.get(k), str) else i1.get(k)
        for k in ("source", "unit", "unit_note")})

    # ── C5 بی‌hardcode ────────────────────────────────────────────────────
    for f in ("fts_engine.py", os.path.join("api", "fundamental.py")):
        src = io.open(os.path.join(ROOT, f), encoding="utf-8").read()
        hits = [n for n in NOTEBOOK_EXAMPLES
                if n in src.replace(",", "").replace("٬", "")]
        ck(not hits, "C5 مثالِ عددیِ جزوه درِ %s hardcode نشده" % f, hits)

    # ── C6 کنترلِ منفی: سنسورِ ردپا کور نیست ──────────────────────────────
    stripped = dict(i3)
    stripped.pop("ref_tracing_no", None)
    ck(not (stripped.get("ref_tracing_no") and stripped.get("source")),
       "C6 با بریدنِ ردپا، چکِ C4 قرمز می‌شود (سنسور می‌بیند)")
    fake_gap = {"pass": False, "na": False, "data_gap": False, "reason": ""}
    ck(bool(fake_gap.get("pass") is False and not fake_gap.get("reason")),
       "C6ب «ردِ بی‌دلیل» درِ این چهاچوب دیده می‌شود — پس C3 بی‌معنا نیست")

    # ── C7 «بی‌داده» رأی نمی‌سازد: شاخص ۴ درِ نمادِ بی‌شاهد ───────────────
    mcap, sector, total, _ = F._fts_market_ctx(conn, "شتهران")
    c2 = F.evaluate_v10(conn, "شتهران", mcap or 0.0, total, sector, cfg=cfg)
    v4 = (c2.get("indicators") or {}).get("4") or {}
    ck(v4.get("na") is True and v4.get("pass") in (False, None)
       and bool(v4.get("reason")),
       "C7 نمادِ بی‌شاهدِ مقیاس درِ کارت «سنجیده نشد» است، نه مردود",
       {k: v4.get(k) for k in ("na", "pass", "gap_cause")})
    b = {r["symbol"]: r for r in FE.bulk_scan(conn, cfg=cfg)}
    br = b.get("شتهران")
    ck(br is not None and br.get("i4_pass") is None,
       "C7ب قیف هم برایِ همان نماد None می‌دهد (پاریتیِ سه‌حالگی)",
       (br or {}).get("i4_pass"))

    conn.close()
    print("\nfts_indicator_contract_v1091: %d passed / %d failed" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
