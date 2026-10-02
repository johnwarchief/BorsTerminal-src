# -*- coding: utf-8 -*-
"""گاردِ پاریتیِ تمام‌سطحیِ مسیرهای موتور — `scan_symbol` ⇄ `bulk_scan`.

چرا این فایل متولد شد: گاردِ `fts_screener_card_parity_v10.py` مسیرِ تک‌نمادی را
رویِ یکِ **نمونه** (هر ۲۵ام) می‌سنجد و همین سه واگراییِ مرزی را ندید:

  * `bulk_scan` حکمِ شاخص ۳ و ۴ را با عددِ **گردشدۀ منتشرشده** می‌ساخت
    (۱۹٫۹۶٪ ⇒ ۲۰٫۰ ⇒ «≥۲۰٪»؛ ۰٫۳۲۹۹ ⇒ ۰٫۳۳ ⇒ «≥ ⅓×») در حالی که
    `gross_margin()`/`sales_to_marketcap()` با عددِ خام داوری می‌کنند
    (لخزر، كمينا، شرنگي، سجام، نمرينو، بپيوند).
  * کارت هم پتانسیل سود را از `round(...,1)` مقایسه می‌کرد.

قاعده: **آستانه با عددِ خام سنجیده می‌شود؛ گردکردن فقط برایِ نمایش است.**
این گارد هر ۹۲۱+ نماد را مقایسه می‌کند (~۲ دقیقه) و یکِ سنجهِ مرزیِ قطعیِ بی‌بانک
هم دارد تا اگر روزی مقایسه به عددِ گرد شده برگشت، همین‌جا قرمز شود.

اجرا:  python dev/fts_engine_paths_parity_v1076.py
"""
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import bors_config          # noqa: E402
import fts_engine as F      # noqa: E402

CHECKS = []


def ck(cond, msg, detail=""):
    CHECKS.append((bool(cond), msg, detail))
    print("  %s %s%s" % ("✓" if cond else "✗", msg, ("   ← " + detail) if detail else ""))


# ── ۱) سنجۀ مرزیِ قطعی (بی‌بانک): آستانه با عددِ خام، نمایش گرد ────────────
# فروشِ سالانۀ ۳٬۲۹۹٬۰۰۰ م.ر رویِ ارزشِ بازارِ ۱۰^۱۳ ⇒ نسبتِ خام ۰٫۳۲۹۹ — دقیقاً
# همان جایی که «گرد شده ≥ کف» با «خام ≥ کف» از هم جدا می‌شود.
_mcap = 10_000_000_000_000.0
_annual = {"annual_sales_mrl": 3_299_000.0, "annual_sales_bt": 329.9, "months_used": 12,
           "scale_factor": 1.0, "basis": "تست", "reconciled": True}
r = F.sales_to_marketcap(None, "آزمون", _mcap, min_ratio=0.33, annual=_annual,
                         sector="فلزات اساسي", _no_sales=set())
ck(r is not None and r["pass"] is False and r["sales_to_mcap"] == 0.33,
   "نسبتِ خام ۰٫۳۲۹۹ ⇒ pass=False و نمایش ۰٫۳۳ (گردکردن حکم را نمی‌سازد)",
   str(r and (r["sales_to_mcap"], r["pass"])))
# برایِ پتانسیل، فروش را جوری می‌گیریم که `(فروش × حاشیه) ÷ ارزش × ۱۰۰` دقیقاً
# رویِ مرزِ ۴۰٪ بایستد: ۱۰میلیون م.ر × ۱۰^۶ ÷ ۱۰^۱۳ = ۱٫۰، پس پتانسیل = خودِ حاشیه.
_annual_1x = dict(_annual, annual_sales_mrl=10_000_000.0, annual_sales_bt=10_000.0)
gm = {"margin_pct": 39.96, "na": False}
p = F.gross_profit_potential(None, "آزمون", _mcap, min_pct=40.0, gm=gm, annual=_annual_1x)
ck(p is not None and p["pass"] is False and p["potential_pct"] == 40.0,
   "پتانسیلِ خام ۳۹٫۹۶٪ ⇒ pass=False و نمایش ۴۰٫۰",
   str(p and (p["potential_pct"], p["pass"])))

# کارت هم باید همین حکم را بدهد (تک‌قاعده در هر دو مسیر)
from api import fundamental as FD      # noqa: E402
_v = FD.ind4_valuation(_annual_1x, gm, _mcap, th=FD.v10_thresholds())
ck(_v["potential_pass"] is False and _v["potential_pct"] == 40.0,
   "کارتِ جزئیات هم پتانسیل را با عددِ خام می‌سنجد (همان قاعدۀ موتور)",
   "pct=%s pass=%s" % (_v.get("potential_pct"), _v.get("potential_pass")))
_vs = FD.ind4_valuation(_annual, gm, _mcap, th=FD.v10_thresholds())
ck(_vs["sales_pass"] is False and _vs["sales_to_mcap"] == 0.33,
   "کارتِ جزئیات هم نسبتِ ۰٫۳۲۹۹ را پاس نمی‌کند و همان ۰٫۳۳ را نشان می‌دهد",
   "ratio=%s sales_pass=%s" % (_vs.get("sales_to_mcap"), _vs.get("sales_pass")))

# ── ۲) تمامِ سطحِ بازار: هر نماد، هر پنج محور + اعدادِ منتشرشده ────────────
if not os.path.isfile("market.db"):
    print("[SKIP] market.db نیست — پاریتیِ تمام‌سطحی اجرا نشد.")
    sys.exit(0)

conn = sqlite3.connect("file:market.db?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
try:
    cfg = json.load(open(bors_config.FTS_CONFIG_PATH, encoding="utf-8"))
    bulk = {r["symbol_norm"]: r for r in F.bulk_scan(conn, cfg=cfg)}
    total = F.mstat_engine.market_total_rials(conn)[0]
    print("bulk_scan: %d ردیف | تک‌نمادی روی همه" % len(bulk))
    score_bad = axis_bad = value_bad = 0
    first = []
    for key, br in bulk.items():
        s = F.scan_symbol(conn, br["symbol"], br["mcap"], total,
                          br["sector_name"] or "", cfg=cfg)
        p_ = s["passes"]
        axes = (p_["1_growth"], p_["2_eps_trend"], p_["3_gross_margin"],
                p_["4_sales_to_mcap"], p_["5_industry"])
        baxes = (br["i1_pass"], br["i2_pass"], br["i3_pass"], br["i4_pass"], br["i5_pass"])
        if s["score"] != br["score"]:
            score_bad += 1
            if len(first) < 5:
                first.append((br["symbol"], s["score"], br["score"]))
        if [bool(x) if x is not None else None for x in axes] != \
           [bool(x) if x is not None else None for x in baxes]:
            axis_bad += 1
        d = s["detail"]
        pair = (((d.get("sales_to_mcap") or {}).get("sales_to_mcap"), br["sales_to_mcap"]),
                (((d.get("profit_potential") or {}).get("potential_pct")),
                 br["profit_potential_pct"]),
                (((d.get("gross_margin") or {}).get("margin_pct")), br["gross_margin"]),
                (((d.get("growth") or {}).get("growth_pct")), br["rev_growth"]))
        if any(x != y for x, y in pair):
            value_bad += 1
            if len(first) < 5:
                first.append((br["symbol"], pair))
    ck(score_bad == 0, "امتیازِ scan_symbol == امتیازِ bulk_scan رویِ هر %d نماد" % len(bulk),
       "واگرا: %d %s" % (score_bad, first[:3]))
    ck(axis_bad == 0, "پنج محور یکی‌یکی هم‌خوان (نه فقط جمعِ امتیاز)", "واگرا: %d" % axis_bad)
    ck(value_bad == 0, "اعدادِ منتشرشده (نسبت/پتانسیل/حاشیه/رشد) هم‌خوان", "واگرا: %d" % value_bad)
finally:
    conn.close()

bad = [m for ok, m, _d in CHECKS if not ok]
print("\nنتیجه: %d سبز، %d قرمز" % (len(CHECKS) - len(bad), len(bad)))
sys.exit(1 if bad else 0)
