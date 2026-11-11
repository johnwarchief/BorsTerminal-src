#!/usr/bin/env python3
"""Per-event parity ledger: every reference change vs the engine before/after.

Reference changes come from the fresh type7/type0 capture (pilot-analysis).
The before state is the shipped Phase 4.9.1 engine on the Seed; the after state
is the same engine preferring the measured factors + reference raw. Pack
status is the old pack's view of each reference change.
"""
import csv
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AUD = os.path.join(ROOT, "_audit", "phase49-2")
ANALYSIS = os.path.join(AUD, "rahavard", "pilot-analysis.json")
BEFORE = os.path.join(AUD, "rahavard", "engine-parity-before.json")
AFTER = os.path.join(AUD, "rahavard", "engine-parity-after.json")
DB = os.path.join(AUD, "db", "market.db")
OUT_CSV = os.path.join(AUD, "ledgers", "EVENT-PARITY.csv")
OUT_JSON = os.path.join(AUD, "evidence", "event-parity.json")


def main():
    analysis = {s["symbol"]: s for s in json.load(
        open(ANALYSIS, encoding="utf-8"))["symbols"]}
    before = {s["symbol"]: s for s in json.load(
        open(BEFORE, encoding="utf-8"))["symbols"]}
    after = {s["symbol"]: s for s in json.load(
        open(AFTER, encoding="utf-8"))["symbols"]}
    con = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
    kinds = {}
    for sym, d, kind, ratio in con.execute(
            "SELECT symbol,date,kind,ratio FROM adjustment_factors"):
        kinds[(sym, d)] = (kind, ratio)
    con.close()

    rows = []
    counts = {"pack": {}, "before": {}, "after": {}}
    for sym, a in sorted(analysis.items()):
        b = before[sym]
        f = after[sym]
        b_missing = {x["date"] for x in b["missing_engine_steps"]}
        b_ratio = {x["date"]: x for x in b["ratio_diffs"]}
        f_missing = {x["date"] for x in f["missing_engine_steps"]}
        f_ratio = {x["date"]: x for x in f["ratio_diffs"]}
        for ch in a["changes"]:
            d = ch["date"]
            kind, ratio = kinds.get((sym, d), ("UNKNOWN", None))
            pack_status = ch["status"]
            if d in b_missing:
                bstat = "MISSING_IN_ENGINE"
            elif d in b_ratio:
                bstat = "WRONG_RATIO"
            else:
                bstat = "MATCH"
            if d in f_missing:
                fstat = "MISSING_IN_ENGINE"
            elif d in f_ratio:
                fstat = "WRONG_RATIO"
            else:
                fstat = "MATCH"
            pack_detail = ""
            if ch.get("pack_match"):
                pm = ch["pack_match"]
                pack_detail = "%s|%s|%s" % (pm.get("event_sig"), pm.get("date"),
                                            pm.get("ratio"))
            rows.append({
                "symbol": sym, "date": d,
                "reference_ratio": "%.17g" % ch["implied_ratio"],
                "kind": kind, "factor_ratio": ratio,
                "pack_status": pack_status, "pack_detail": pack_detail,
                "before_status": bstat, "after_status": fstat,
            })
            counts["pack"][pack_status] = counts["pack"].get(pack_status, 0) + 1
            counts["before"][bstat] = counts["before"].get(bstat, 0) + 1
            counts["after"][fstat] = counts["after"].get(fstat, 0) + 1
        # engine-only changes in the before state (bogus/stale pack steps that
        # survived into the engine)
        for x in b["extra_engine_steps"]:
            rows.append({
                "symbol": sym, "date": x["date"], "reference_ratio": "",
                "kind": "NO_REFERENCE_CHANGE", "factor_ratio": "",
                "pack_status": "EXTRA_ENGINE_STEP",
                "pack_detail": "engine factor %.17g has no reference change" % x["ratio"],
                "before_status": "ENGINE_EXTRA", "after_status": "",
            })
            counts["before"]["ENGINE_EXTRA"] = counts["before"].get(
                "ENGINE_EXTRA", 0) + 1

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    doc = {
        "schema": "phase49-2-event-parity-v1",
        "events": len(rows),
        "counts": counts,
        "before_max_rel": {s["symbol"]: s["max_rel"] for s in before.values()},
        "after_max_rel": {s["symbol"]: s["max_rel"] for s in after.values()},
        "after_all_exact": all((s["max_rel"] or 0) <= 1e-6
                               for s in after.values()),
    }
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(json.dumps(doc["counts"], ensure_ascii=False, indent=1))
    print("events", len(rows), "after_all_exact", doc["after_all_exact"])
    print("wrote", OUT_CSV, OUT_JSON)
    return 0


if __name__ == "__main__":
    sys.exit(main())
