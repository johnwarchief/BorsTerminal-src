import sys
import json
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

from api.chart import _fts_analyze_symbol

SYMBOLS = [
    "فولاد", "پارس", "خگستر", "شبندر", "شستا", "خودرو", "خساپا", "وبملت",
    "وبصادر", "فملی", "شپنا", "شتران", "وتجارت", "کگل", "کچاد", "تاپیکو",
    "وغدیر", "ومعادن", "وامید", "رمپنا"
]

results = []

for sym in SYMBOLS:
    try:
        res = _fts_analyze_symbol(sym)
        if res and res.get("status") == "success" and "fts" in res:
            analysis = res["fts"]
            if "trend" in analysis:
                tD = analysis["trend"]["D"]["trend"]
                tW = analysis["trend"]["W"]["trend"]
                
                mx = analysis["trend"].get("matrix", {})
                decision = mx.get("decision", "NA")
                setup = mx.get("setup", "NA")
                
                out_res = {
                    "Symbol": sym,
                    "Daily Engine": tD,
                    "Weekly Engine": tW,
                    "FTS Decision": decision,
                    "FTS Setup": setup
                }
                results.append(out_res)
                print(f"{sym} | Daily: {tD} | Weekly: {tW} | FTS: {decision} ({setup})")
            else:
                print(f"{sym} | Missing trend in fts")
        else:
            print(f"{sym} | Failed to analyze: {res.get('message') if res else 'None'}")
    except Exception as e:
        print(f"{sym} | Exception: {e}")

with open("_audit/20_symbol_validation.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
