"""Phase 4.9 — Python /api/chart-db E2E capture against an isolated DB copy.

Calls the same function the route serves, with BORS_DB pointing at a copy of the
restored Work DB and BORS_CORRECTIONS_DIR at the authoritative base pack. No
FastAPI startup event runs (import of api.chart only wires the router), so the
DB copy is not mutated by boot-time projection.

Outputs evidence/api-python-authoritative/<symbol>.json for comparison with the
Go endpoint captured from the live borsd server on the same DB content.
"""
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
CONT = os.path.join(ROOT, "_audit", "phase49", "continuation")
os.environ["BORS_DB"] = os.path.join(CONT, "api", "python", "market.db")
os.environ["BORS_CORRECTIONS_DIR"] = os.path.join(ROOT, "data", "ra365_corrections", "ra365-r32b-v2")
os.environ["BORS_NO_FETCH_LOOPS"] = "1"

sys.path.insert(0, ROOT)

import api.chart as C  # noqa: E402

OUT = os.path.join(CONT, "evidence", "api-python-authoritative")
os.makedirs(OUT, exist_ok=True)

SYMBOLS = sys.argv[1:] or ["فولاد", "وسکاب"]
report = []
for sym in SYMBOLS:
    t0 = time.time()
    try:
        res = C.get_chart_db_visible(sym)
    except Exception as e:  # keep the failure visible in the report
        report.append({"symbol": sym, "error": repr(e)})
        continue
    dt = round(time.time() - t0, 3)
    with open(os.path.join(OUT, sym + ".json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
    cap = (res.get("adjustCapability") or {}).get("corrections") or {}
    report.append({
        "symbol": sym,
        "status": res.get("status"),
        "count": res.get("count"),
        "candles": len(res.get("candles") or []),
        "events": len(res.get("adjustEvents") or []),
        "rejected": len(res.get("adjustRejected") or []),
        "mode": cap.get("mode"),
        "replace_steps": cap.get("replace_steps"),
        "liveInjected": res.get("liveInjected"),
        "seconds": dt,
    })
with open(os.path.join(OUT, "_summary.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
print(json.dumps(report, ensure_ascii=False, indent=1))
