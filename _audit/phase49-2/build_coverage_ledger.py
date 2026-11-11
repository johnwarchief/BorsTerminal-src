#!/usr/bin/env python3
"""Per-symbol coverage/quarantine ledger for Phase 4.9.2.

One row per history symbol. The old global blockers become per-symbol queue
reasons; a symbol is never blocked by another symbol's defect. The 30 pilot
symbols are READY only because the independent DB carries their raw series,
measured factors, adjusted candles and an exact reference verification.
"""
import csv
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGERS = os.path.join(ROOT, "_audit", "phase49-full-verification", "ledgers")
DB = os.path.join(ROOT, "_audit", "phase49-2", "db", "market.db")
PILOT = os.path.join(ROOT, "_audit", "phase49-2", "rahavard", "pilot-symbols.json")
UNMAPPED = os.path.join(ROOT, "_audit", "phase49-full-verification",
                        "capture-plan", "capture-unmapped.json")
OUT_CSV = os.path.join(ROOT, "_audit", "phase49-2", "ledgers",
                       "COVERAGE-STATUS.csv")
OUT_JSON = os.path.join(ROOT, "_audit", "phase49-2", "evidence",
                        "coverage-status.json")


def main():
    rows = list(csv.DictReader(open(os.path.join(
        LEDGERS, "HISTORY-COVERAGE-LEDGER.csv"), encoding="utf-8", newline="")))
    anomalies = list(csv.DictReader(open(os.path.join(
        LEDGERS, "anomaly-ledger.csv"), encoding="utf-8", newline="")))
    invalid = {}
    anomaly_count = {}
    for a in anomalies:
        anomaly_count[a["symbol"]] = anomaly_count.get(a["symbol"], 0) + 1
        if a["kind"] == "INVALID_OHLC":
            invalid[a["symbol"]] = invalid.get(a["symbol"], 0) + 1
    unmapped = {u["key"] for u in json.load(open(UNMAPPED, encoding="utf-8"))}
    pilot = {p["symbol"] for p in json.load(open(PILOT, encoding="utf-8"))}

    con = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
    pilot_stats = {}
    for sym in pilot:
        raw = con.execute(
            "SELECT COUNT(*),MIN(date),MAX(date) FROM reference_raw WHERE symbol=?",
            (sym,)).fetchone()
        f = con.execute(
            "SELECT COUNT(*),MIN(revision) FROM adjustment_factors WHERE symbol=?",
            (sym,)).fetchone()
        adj = con.execute(
            "SELECT COUNT(*),MAX(rel_error) FROM adjusted_candles ac "
            "JOIN adjustment_verification v ON v.symbol=ac.symbol AND v.date=ac.date "
            "WHERE ac.symbol=?", (sym,)).fetchone()
        ver = con.execute(
            "SELECT COUNT(*),SUM(CASE WHEN status='EXACT' THEN 1 ELSE 0 END) "
            "FROM adjustment_verification WHERE symbol=?", (sym,)).fetchone()
        kinds = dict(con.execute(
            "SELECT kind,COUNT(*) FROM adjustment_factors WHERE symbol=? "
            "GROUP BY kind", (sym,)).fetchall())
        audit = dict(con.execute(
            "SELECT reason,COUNT(*) FROM adjustment_factor_audit WHERE symbol=? "
            "GROUP BY reason", (sym,)).fetchall())
        pilot_stats[sym] = {
            "raw_rows": raw[0], "raw_first": raw[1], "raw_last": raw[2],
            "factors": f[0], "revision": f[1],
            "adjusted_rows": adj[0], "max_rel_error": adj[1],
            "verified": ver[0], "exact": ver[1], "kinds": kinds,
            "pack_audit": audit,
        }
    con.close()

    out = []
    summary = {}
    for r in rows:
        sym = r["symbol"]
        reason = ""
        if sym in pilot:
            status = "READY_PILOT"
        elif sym in unmapped:
            status, reason = "QUEUE_UNMAPPED_ASSET_ID", "NO_ASSET_ID"
        elif r["identity_status"] == "unresolved_no_instruments":
            status, reason = "QUEUE_NO_INSTRUMENTS", "NO_INSTRUMENTS_ROW"
        elif r["stale_status"] == "halted":
            status, reason = "QUEUE_HALTED", "INSTRUMENT_STATE_HALTED"
        elif r["ref_coverage"] == "none":
            status = "QUEUE_NO_REFERENCE"
            reason = ("NO_REFERENCE_WINDOW;NO_PACK_STEPS"
                      if r["step_rows"] == "0" else "NO_REFERENCE_WINDOW")
        else:
            status, reason = "QUEUE_REFERENCE_ONLY", "FACTORS_NOT_INGESTED"
        st = pilot_stats.get(sym, {})
        out.append({
            "symbol": sym, "status": status, "queue_reason": reason,
            "ref_coverage": r["ref_coverage"], "step_rows": r["step_rows"],
            "rows": r["rows"], "first_date": r["first_date"],
            "last_date": r["last_date"], "stale_status": r["stale_status"],
            "identity_status": r["identity_status"],
            "anomalies_legacy": anomaly_count.get(sym, 0),
            "invalid_ohlc_legacy": invalid.get(sym, 0),
            "pilot_raw_rows": st.get("raw_rows", ""),
            "pilot_raw_first": st.get("raw_first", ""),
            "pilot_raw_last": st.get("raw_last", ""),
            "pilot_factors": st.get("factors", ""),
            "pilot_adjusted_rows": st.get("adjusted_rows", ""),
            "pilot_verified_exact": ("%d/%d" % (st["exact"], st["verified"])
                                     if st else ""),
            "pilot_max_rel_error": st.get("max_rel_error", ""),
            "pilot_revision": st.get("revision", ""),
            "notes": _note(r, invalid, st),
        })
        summary[status] = summary.get(status, 0) + 1

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    fields = list(out[0].keys())
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    doc = {
        "schema": "phase49-2-coverage-status-v1",
        "rows": len(out),
        "status_counts": dict(sorted(summary.items(), key=lambda x: -x[1])),
        "named_cases": {
            sym: next((x for x in out if x["symbol"] == sym), None)
            for sym in ("شنفت", "طلا", "تپسي", "غشان", "ولانا")
        },
        "pilot": pilot_stats,
        "note": "READY_PILOT requires reference_raw + measured factors + "
                "adjusted candles + exact reference verification. Every other "
                "status is a queue reason, not a global gate.",
    }
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(json.dumps(doc["status_counts"], ensure_ascii=False, indent=1))
    print("named:", {k: (v or {}).get("status") for k, v in doc["named_cases"].items()})
    print("wrote", OUT_CSV, OUT_JSON)
    return 0


def _note(r, invalid, st):
    notes = []
    if invalid.get(r["symbol"]):
        notes.append("%d legacy invalid OHLC rows quarantined" % invalid[r["symbol"]])
    if st.get("pack_audit", {}).get("superseded_ratio"):
        notes.append("%d pack ratios superseded by the fresh reference"
                     % st["pack_audit"]["superseded_ratio"])
    if st.get("pack_audit", {}).get("missing_pack_step"):
        notes.append("%d reference steps absent from the old pack"
                     % st["pack_audit"]["missing_pack_step"])
    if st.get("kinds", {}).get("corporate_action_unclassified"):
        notes.append("%d measured events stay type-unclassified"
                     % st["kinds"]["corporate_action_unclassified"])
    return "; ".join(notes)


if __name__ == "__main__":
    sys.exit(main())
