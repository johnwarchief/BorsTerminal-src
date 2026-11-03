#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 28: aligned factor-chain debugger classification (synthetic)."""
import csv
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


td = tempfile.mkdtemp(prefix="r28_chain_")
ref_path = os.path.join(td, "ref.jsonl")
payload_path = os.path.join(td, "payload.json")
dates = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-06", "2024-01-07"]
raw = [100, 100, 100, 100, 100]
adj = [100, 100, 90, 90, 81]          # ref steps at d2 (0.9) and d4 (0.9)
items = []
for typ, closes in (("type0", raw), ("type7", adj)):
    items.append({"asset_id": "1", "type": typ, "res": "D",
                  "bars": [{"utc": d + "T00:00:00Z", "open": c, "high": c,
                            "low": c, "close": c, "volume": 1}
                           for d, c in zip(dates, closes)]})
with open(ref_path, "w", encoding="utf-8") as fh:
    for it in items:
        fh.write(json.dumps(it, ensure_ascii=False) + "\n")
prod_f = [1.0, 1.0, 0.8, 0.72, 0.72]   # d2 differs (0.8 vs 0.9), d3 extra (0.9)
payload = {"asset_id": "1", "symbol": "TEST",
           "candles": [{"time": d, "open": 100, "high": 100, "low": 100,
                        "close": 100, "last": 100} for d in dates],
           "factors": [{"time": d, "factor": f} for d, f in zip(dates, prod_f)],
           "adjustEvents": [{"date": dates[2], "ratio": 0.8, "source": "x"},
                            {"date": dates[3], "ratio": 0.9, "source": "x"}]}
json.dump(payload, open(payload_path, "w", encoding="utf-8"), ensure_ascii=False)
out = os.path.join(td, "out")
r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "ra365_round28_chain_debug.py"),
                    "--payload", payload_path, "--ref", ref_path, "--out", out],
                   capture_output=True, text=True, encoding="utf-8")
ck(r.returncode == 0, "debugger runs on synthetic input", r.stderr[-200:])
rows = list(csv.DictReader(open(os.path.join(out, "chain-1.csv"), encoding="utf-8-sig")))
classes = {(x["date"], x["class"]) for x in rows}
ck((dates[2], "RATIO_DIFF") in classes, "a differing step is RATIO_DIFF", classes)
ck((dates[3], "EXTRA") in classes, "a product-only step is EXTRA", classes)
ck((dates[4], "REF_ONLY") in classes, "a reference-only step is REF_ONLY", classes)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
