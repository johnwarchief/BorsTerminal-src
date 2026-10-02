# -*- coding: utf-8 -*-
"""`_audit/ind4_value_disagree_probe.py` — ریشۀ تنها ردیفِ قرمزِ گاردِ پاریتی.

`dev/fts_screener_card_parity_v10.py` درِ بندِ دوم یکِ واگراییِ «عدد-vs-N/A» می‌دهد:
`نشار` — موتور (bulk_scan) نسبتِ ۱۴۱۳٫۷۵ را می‌خواند، کارت (evaluate_v10) None
برمی‌گرداند در حالی که `na` هم False است. این اسکریپت همان یکِ نماد را از هر دو
مسیر می‌خواند و هر دو میان‌یابِ `annualized_sales` و `sales_to_marketcap` را
چاپ می‌کند. اجرا:  python _audit/ind4_value_disagree_probe.py [نماد]
"""
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import fts_engine
from api import fundamental as FD
from api.market import load_fts_config

SYM = sys.argv[1] if len(sys.argv) > 1 else "نشار"
conn = sqlite3.connect("file:market.db?mode=ro", uri=True)
cfg = load_fts_config()
key = fts_engine.norm_fa(SYM)
mcap, sector, total, info = FD._fts_market_ctx(conn, key)
print("sym=%s norm=%s mcap=%r sector=%r total=%r" % (SYM, key, mcap, sector, total))

card = FD.evaluate_v10(conn, key, mcap or 0.0, total, sector, cfg=cfg, company_name="")
v4 = (card.get("indicators") or {}).get("4") or {}
print("\nCARD indicators['4'] = %s" % json.dumps(v4, ensure_ascii=False)[:800])

ann = fts_engine.annualized_sales(conn, SYM)
print("\nannualized_sales = %s" % json.dumps(ann, ensure_ascii=False)[:500])

holdings_na = cfg.get("holdings_sales_na", True)
s2m = fts_engine.sales_to_marketcap(conn, SYM, mcap or 0.0,
                                   min_ratio=fts_engine._th(cfg, "sales_to_mcap_min"),
                                   annual=ann, sector=sector, holdings_na=holdings_na)
print("\nsales_to_marketcap (python) = %s" % (json.dumps(s2m, ensure_ascii=False)[:600]
                                              if s2m else None))
print("no_sales_concept = %r  holdings_na=%r" % (
    fts_engine.no_sales_concept(conn, SYM, sector, holdings_na=holdings_na), holdings_na))

eng = [r for r in fts_engine.bulk_scan(conn, cfg=cfg) if r["symbol_norm"] == key]
print("\nENGINE bulk row = %s" % (json.dumps(eng[0], ensure_ascii=False)[:900]
                                  if eng else "None"))

# ردیفِ خامِ بانک که هر دو مسیر از آن شروع می‌کنند
rows = conn.execute(
    "SELECT tracing_no, period_end, fiscal_year, revenue, gross_profit, has_operating_sales "
    "FROM financial_statements WHERE symbol=? ORDER BY period_end DESC LIMIT 6",
    (SYM,)).fetchall()
print("\nfinancial_statements rows:")
for r in rows:
    print("  ", r)
print("monthly_sales last 6:")
for r in conn.execute("SELECT period_end, year, month, monthly_revenue, ytd_revenue "
                      "FROM monthly_sales WHERE symbol=?"
                      " ORDER BY period_end DESC LIMIT 6", (SYM,)).fetchall():
    print("  ", r)
conn.close()
