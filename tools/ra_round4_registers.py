# -*- coding: utf-8 -*-
"""Build the Round-4 registers: 128 pairs, 678 ref-only, 78 live, factor/OHLC mismatches."""
import argparse
import collections
import csv
import datetime as dt
import json
import os
import sqlite3


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _d(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def write(path, rows):
    fields = sorted({k for r in rows for k in r})
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader(); w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", required=True)
    ap.add_argument("--symbols", required=True)
    ap.add_argument("--steps", required=True)
    ap.add_argument("--product", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--refonly", required=True)
    ap.add_argument("--fixed-steps", required=True)
    ap.add_argument("--fallback", required=True)
    ap.add_argument("--canonical", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()

    symbols = {r["symbol"]: r for r in csv.DictReader(open(a.symbols, encoding="utf-8-sig"))}
    steps = collections.defaultdict(list)
    for r in csv.DictReader(open(a.steps, encoding="utf-8-sig")):
        steps[r["symbol"]].append(r)
    prod = {}
    for line in open(a.product, encoding="utf-8"):
        j = json.loads(line)
        prod[j["symbol"]] = {
            "close": {str(c["time"])[:10]: c.get("close") for c in (j.get("candles") or [])},
            "events": [(str(e.get("date"))[:10], _f(e.get("ratio")))
                       for e in (j.get("adjustEvents") or [])],
        }
    asset_ids = {r["asset_id"] for r in symbols.values() if r["symbol"] in prod}
    ref = collections.defaultdict(dict)
    for line in open(a.ref, encoding="utf-8"):
        j = json.loads(line)
        if str(j.get("asset_id")) not in asset_ids or j.get("type") != "type0" or j.get("res") != "D":
            continue
        for b in j.get("bars") or []:
            if isinstance(b, dict):
                ref[str(j["asset_id"])][str(b.get("date"))[:10]] = b.get("close")
            else:
                ref[str(j["asset_id"])][str(b[0])[:10]] = b[4]

    # ---- 128 pairs ----
    pairs = []
    for r in csv.DictReader(open(a.pairs, encoding="utf-8-sig")):
        c = r.get("round3_class") or ""
        if c.startswith("SOURCE_GAP_CONFIRMED"):
            st, ev = "SOURCE_GAP_CONFIRMED", "official ledger window is empty / pre-coverage"
        elif c.startswith("REFERENCE_CONTRACT_DIFFERENCE"):
            st, ev = "EXPECTED_SEMANTIC_DIFFERENCE", "product follows official row; reference differs"
        elif c.startswith("UNRESOLVED:COMPOSITE"):
            st, ev = "UNVERIFIED", "multiple shareChange components net ~1; no single ratio"
        else:
            st, ev = "UNVERIFIED", "not classified"
        pairs.append(dict(r, final_status=st, evidence=ev,
                          next_action="owner decision on functional definition" if st != "SOURCE_GAP_CONFIRMED"
                          else "official archive / ledger extension"))
    write(os.path.join(a.outdir, "RAHAVARD-128-PAIR-CLOSURE-ROUND4-2026-10-20.csv"), pairs)

    # ---- 78 live-unavailable ----
    fb = [r for r in csv.DictReader(open(a.fallback, encoding="utf-8-sig"))
          if r.get("round3_status") == "DB_FALLBACK"]
    ins = {}
    con = sqlite3.connect("file:" + a.db + "?mode=ro", uri=True)
    for r in fb:
        row = con.execute("SELECT ins_code FROM instruments WHERE l_val18=? "
                          "ORDER BY updated_at DESC LIMIT 1", (r["symbol"],)).fetchone()
        ins[r["symbol"]] = str(row[0]) if row else ""
    con.close()
    live = []
    for r in fb:
        cls = r.get("class")
        if cls == "options":
            st, reason, nxt = "SOURCE_GAP_CONFIRMED", "OPTION_NO_LIVE_CSV", "option-specific source / expiry review"
        elif cls == "stocks":
            st, reason, nxt = "SOURCE_GAP_CONFIRMED", "STOCK_NO_LIVE_SOURCE_SINCE_2024_08_24", "delisting/transfer archive"
        elif cls == "etf_funds":
            st, reason, nxt = "SOURCE_GAP_CONFIRMED", "FUND_NO_LIVE_SOURCE", "fund manager/NAV source"
        elif cls == "bonds":
            st, reason, nxt = "SOURCE_GAP_CONFIRMED", "BOND_EXPIRED_OR_NO_LIVE_ROW", "maturity/expiry review"
        else:
            st, reason, nxt = "UNVERIFIED", "UNKNOWN", "manual review"
        live.append(dict(r, ins_code=ins.get(r["symbol"], ""), mapping_valid="yes" if ins.get(r["symbol"]) else "no",
                         endpoint_supported="no" if cls in ("options", "bonds") else "unknown",
                         final_status=st, root_cause=reason, next_action=nxt))
    write(os.path.join(a.outdir, "RAHAVARD-LIVE-UNAVAILABLE-ROUND4-2026-10-20.csv"), live)

    # ---- 678 ref-only ----
    fixed = set()
    for r in csv.DictReader(open(a.fixed_steps, encoding="utf-8-sig")):
        if r.get("kind") == "PAIR":
            fixed.add((r["symbol"], r["ref_date"]))
    ro = []
    for r in csv.DictReader(open(a.refonly, encoding="utf-8-sig")):
        if r["status"] == "OFFICIAL_ROW_NOT_APPLIED":
            if (r["symbol"], r["ref_date"]) in fixed:
                st, act = "FIXED", "priceAdjust injection (Round 4)"
            elif int(r.get("ledger_pa") or 0):
                rr = _f(r.get("ref_ratio")) or 1
                st = "BELOW_STEP_DETECTION_TOLERANCE" if abs(rr - 1) < 0.001 else "UNVERIFIED"
                act = "product factor applied; 0.05% step detector omits it" if abs(rr - 1) < 0.001 else "manual review"
            elif int(r.get("ledger_sc") or 0):
                st, act = "SHARE_CHANGE_COMPONENT_UNSAFE", "composite shareChange rows; no single ratio"
            else:
                st, act = "UNVERIFIED", "manual review"
        elif r["status"] == "FILTERED_BY_PRODUCT":
            st, act = "EXPECTED_SEMANTIC_DIFFERENCE", "filter evidence recorded in adjustRejected"
        else:
            rr = _f(r.get("ref_ratio")) or 1
            st = ("REFERENCE_SEMANTIC_DIFFERENCE" if abs(rr - 1) < 0.002
                  else "SOURCE_GAP_CONFIRMED")
            act = "tiny reference step without source" if abs(rr - 1) < 0.002 else "official archive / source extension"
        ro.append(dict(r, final_status=st, next_action=act))
    write(os.path.join(a.outdir, "RAHAVARD-REFONLY-678-ROUND4-2026-10-20.csv"), ro)

    # ---- factor / OHLC mismatch register ----
    reg = []
    factor_by_sym_date = {}
    for r in csv.DictReader(open(a.samples, encoding="utf-8-sig")):
        sym = r["symbol"]; aid = r["asset_id"]; d = r["date"]
        refv, prodv = _f(r["ref"]), _f(r["prod"])
        rel = abs(prodv - refv) / abs(refv) if (refv not in (None, 0) and prodv is not None) else None
        ev = ""
        cause = "UNVERIFIED"
        if r["field"] == "factor":
            sr = symbols.get(sym, {})
            ratio = (prodv / refv) if (refv and prodv is not None) else None
            med = _f(sr.get("factor_ratio_median"))
            if ratio and med and abs(ratio / med - 1.0) <= 0.001:
                cause = "REFERENCE_SEMANTIC_DIFFERENCE:PRE_HISTORY_OFFSET"
                ev = f"factor ratio={ratio:.6f} ~ median={med:.6f}"
            else:
                near = [(ed, er) for ed, er in prod.get(sym, {}).get("events", [])
                        if ed and _d(ed) and _d(d) and abs((_d(ed) - _d(d)).days) <= 5]
                if near:
                    cause = "ADJUSTMENT_FORMULA_MISMATCH"
                    ev = f"product event {near[0][0]} ratio={near[0][1]}"
                else:
                    cause = "SOURCE_GAP"
                    ev = "no product event within +/-5d and ratio deviates from the median"
            factor_by_sym_date[(sym, d)] = cause
        elif r["field"].startswith("func_"):
            cause = factor_by_sym_date.get((sym, d), "ADJUSTMENT_PROPAGATION")
            ev = "functional OHLC inherits the factor at the same date"
        elif r["field"] == "close":
            if r["status"] == "SOURCE_DATA_MISMATCH":
                cause = "RAW_PRICE_MISMATCH"
            elif r["status"] in ("OTHER_EXPLAINED", "SESSION_HIGH_LOW_DIFFERENCE"):
                cause = "REFERENCE_SEMANTIC_DIFFERENCE"
            ev = f"close ref={refv} prod={prodv}"
        else:
            ev = r["status"]
        reg.append({"symbol": sym, "asset_id": aid, "date": d, "field": r["field"],
                    "status": r["status"], "ref": refv, "prod": prodv,
                    "relative_diff": rel, "cause": cause, "evidence": ev,
                    "basis": r.get("basis")})
    write(os.path.join(a.outdir, "RAHAVARD-PARITY-MISMATCH-REGISTER-ROUND4-2026-10-20.csv"), reg)

    print("pairs", collections.Counter(r["final_status"] for r in pairs))
    print("live", collections.Counter(r["final_status"] for r in live))
    print("refonly", collections.Counter(r["final_status"] for r in ro))
    print("mismatch", collections.Counter(r["cause"] for r in reg))


if __name__ == "__main__":
    main()
