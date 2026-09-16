#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fts_screener_card_parity_v10.py — پاریتیِ اسکرینر و کارت جزئیات (v10).

قاعدهٔ سختِ سند v10 (بالای api/fundamental.py): «منبع واحد حقیقت» مسیر
کارت جزئیات است و هیچ مسیرِ خواندنی — از جمله /api/screener — حق ندارد
امتیاز/پرچم را جدا حساب کند یا ارزش بازار را دوباره بسازد.

این اسکریپت هر ردیفِ اسکرینر را با همان evaluate_v10 (همان مسیر کارت) دوباره
محاسبه می‌کند و امتیاز/پنج پاس/excluded را مقایسه می‌کند. روی دیتابیسِ کامل
باید صفر ناهم‌خوانی بدهد؛ اگر market.db نبود، با پیام «بدون داده» رد می‌شود
(نه شکست کاذب).

Run:  python dev/fts_screener_card_parity_v10.py
Exit: 0 اگر همه‌ی ردیف‌ها هم‌راستا بودند (یا دیتابیس نبود)؛ 1 در غیر این صورت.
"""
import os
import sqlite3
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

DB = "market.db"
if not os.path.isfile(DB):
    print("[SKIP] %s نیست — «بدون دادهٔ محلی»؛ پاریتی اجرا نشد." % DB)
    sys.exit(0)

import fts_engine                       # noqa: E402
from api import fundamental as F        # noqa: E402
from api import screener as S           # noqa: E402
from api.market import load_fts_config  # noqa: E402

AX = ("1_growth", "2_eps_trend", "3_gross_margin", "4_sales_to_mcap", "5_industry")

cfg = load_fts_config()
res = S.get_screener()
rows = res.get("data") or []
print("اسکرینر: %d ردیف" % len(rows))

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cname_of = {}
for sym, cn in conn.execute("SELECT symbol, company_name FROM financial_statements "
                            "ORDER BY period_end DESC"):
    k = fts_engine.norm_fa(sym)
    if k and k not in cname_of:
        cname_of[k] = cn or ""

checked = 0
mismatches = []
for r in rows:
    key = r.get("symbol_norm") or fts_engine.norm_fa(r["symbol"])
    mcap, sector, total, _info = F._fts_market_ctx(conn, key)
    card = F.evaluate_v10(conn, key, mcap or 0.0, total, sector, cfg=cfg,
                          company_name=cname_of.get(key, ""))
    checked += 1
    sp = [bool(r["i1_pass"]), bool(r["i2_pass"]), bool(r["i3_pass"]),
          bool(r["i4_pass"]), bool(r["i5_pass"])]
    cp = [bool(card["passes"][k]) for k in AX]
    if r["score"] != card["score"] or sp != cp or bool(r["excluded"]) != bool(card["excluded"]):
        mismatches.append((r["symbol"], r["score"], sp, bool(r["excluded"]),
                           card["score"], cp, bool(card["excluded"])))

print("بررسی‌شده: %d | ناهم‌خوانی: %d" % (checked, len(mismatches)))
for sym, ss, sp, se, cs, cp, ce in mismatches[:15]:
    print("  ✗ %-14s اسکرینر=%d %s exc=%s | کارت=%d %s exc=%s"
          % (sym, ss, "".join("1" if x else "0" for x in sp), se,
             cs, "".join("1" if x else "0" for x in cp), ce))

if mismatches:
    print("RESULT: FAIL — اسکرینر و کارت جزئیات هم‌راستا نیستند.")
    sys.exit(1)
print("RESULT: PASS — امتیاز/پرچم اسکرینر == کارت جزئیات برای هر %d ردیف." % checked)
sys.exit(0)
