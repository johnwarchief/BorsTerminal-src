"""#50 — does the screener agree with the detail card on a symbol's EPS trend?

Two engines answer the same question: fts_engine.bulk_scan backs /api/screener
and /api/fundamental/screen, while api/fundamental.py's own five-layer
implementation backs /api/fundamental/{symbol}. They disagree for symbols whose
only 3-year EPS history comes from consolidated statements — the screener treats
consolidated as "not our basis" (per the notebook) and the detail card accepts it
as relaxed evidence. This script prints both answers side by side.
"""
import json
import os
import sqlite3
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fts_engine  # noqa: E402

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "market.db")
if len(sys.argv) > 1 and sys.argv[1].endswith(".db"):
    DB, SYMS = sys.argv[1], sys.argv[2:]
else:
    SYMS = sys.argv[1:] or ["مبين"]

API = os.environ.get("BORS_API", "http://127.0.0.1:8001")

con = sqlite3.connect("file:%s?mode=ro" % DB.replace("?", "%3F"), uri=True)
try:
    bulk = {r.get("symbol", "").strip(): r for r in fts_engine.bulk_scan(con)}
finally:
    con.close()

for sym in SYMS:
    b = bulk.get(sym) or {}
    try:
        with urllib.request.urlopen(API + "/api/fundamental/" + urllib.parse.quote(sym), timeout=120) as r:
            d = json.load(r)
    except Exception as e:
        d, e = None, repr(e)
    detail_pass = ((d or {}).get("passes") or {}).get("2_eps_trend")
    i2 = ((d or {}).get("indicators") or {}).get("2") or {}
    print("=" * 70)
    print("symbol        :", sym)
    print("screener      : i2_pass=%s eps_data_gap=%s series=%s score=%s"
          % (b.get("i2_pass"), b.get("eps_data_gap"), b.get("eps_series"), b.get("score")))
    print("detail card   : 2_eps_trend=%s score=%s | consolidated_used=%s relaxed_evidence=%s audited_only=%s"
          % (detail_pass, (d or {}).get("score"), i2.get("consolidated_used"),
             i2.get("relaxed_evidence"), i2.get("audited_only")))
    print("verdict       :", "AGREE" if detail_pass == b.get("i2_pass") else "DIVERGED (basis of consolidated EPS)")
