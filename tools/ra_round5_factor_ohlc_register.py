# -*- coding: utf-8 -*-
"""Per-symbol factor/OHLC scenario register for Round 5."""
import argparse
import collections
import csv
import json
import sqlite3


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", required=True)
    ap.add_argument("--steps", required=True)
    ap.add_argument("--five", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    steps = collections.defaultdict(list)
    for r in csv.DictReader(open(a.steps, encoding="utf-8-sig")):
        steps[r["symbol"]].append(r)
    five = {r["symbol"]: r for r in csv.DictReader(open(a.five, encoding="utf-8-sig"))}
    con = sqlite3.connect("file:" + a.db + "?mode=ro", uri=True)
    rows = []
    for r in csv.DictReader(open(a.symbols, encoding="utf-8-sig")):
        sym = r["symbol"]
        ins_row = con.execute(
            "SELECT ins_code FROM instruments WHERE l_val18=? ORDER BY updated_at DESC LIMIT 1",
            (sym,)).fetchone()
        ins = str(ins_row[0]) if ins_row else ""
        pa = sc = fe = 0
        if ins:
            pa = con.execute("SELECT COUNT(*) FROM price_adjust_events WHERE ins_code=?", (ins,)).fetchone()[0]
            sc = con.execute("SELECT COUNT(*) FROM share_change_events WHERE ins_code=?", (ins,)).fetchone()[0]
            try:
                fe = con.execute("SELECT COUNT(*) FROM fund_profit_events WHERE ins_code=?", (ins,)).fetchone()[0]
            except Exception:
                fe = 0
        st = steps.get(sym, [])
        ref_only = sum(1 for x in st if x.get("kind") == "REF_ONLY")
        prod_only = sum(1 for x in st if x.get("kind") == "PROD_ONLY")
        pair = sum(1 for x in st if x.get("kind") == "PAIR")
        mismatch = sum(1 for x in st if x.get("kind") == "PAIR"
                       and abs(_f(x.get("ratio_diff")) or 0) > 0.0005)
        raw = _f(r.get("raw_ok_pct")) or 0
        close_bad = (_f(r.get("close_p95")) or 0) > 0 or (_f(r.get("close_max")) or 0) > 0
        f_near = _f(r.get("factor_near_pct")) or 0
        f_ok = _f(r.get("factor_ok_pct")) or 0
        fn_near = _f(r.get("factor_norm_near_pct")) or 0
        func = _f(r.get("func_ok_pct")) or 0
        pre = _f(r.get("pre_history_offset")) or 1
        if sym in five:
            scenario = "SOURCE_REVISION_FIVE"
            cause = five[sym]["cause"]
            evidence = f"v3→v4 raw_diff={five[sym]['raw_close_diff_dates']}, events_added={five[sym]['events_added']}"
        elif raw >= 99 and f_near < 99:
            scenario = "RAW_OK_FACTOR_DIFF"
            cause = ("REFERENCE_SEMANTIC_DIFFERENCE:PRE_HISTORY_OFFSET" if abs(pre - 1) > 0.001
                     else "ADJUSTMENT_FACTOR_MISMATCH" if (pa or sc or fe)
                     else "UNVERIFIED")
            evidence = f"raw={raw:.2f}, factor_near={f_near:.2f}, pre={pre:.6f}"
        elif raw < 99 and f_near >= 99 and close_bad:
            scenario = "RAW_DIFF_FACTOR_OK"
            cause = "RAW_PRICE_MISMATCH"
            evidence = f"raw={raw:.2f}, close_p95={r.get('close_p95')}, factor_near={f_near:.2f}"
        elif raw < 99 and f_near >= 99:
            scenario = "SESSION_HIGH_LOW_ONLY"
            cause = "REFERENCE_SEMANTIC_DIFFERENCE:SESSION_HIGH_LOW"
            evidence = f"raw={raw:.2f}, close_p95={r.get('close_p95')}, factor_near={f_near:.2f}"
        elif raw < 99 and f_near < 99:
            scenario = "BOTH_DIFF" if close_bad else "FACTOR_DIFF_WITH_HIGH_LOW_NOISE"
            cause = ("REFERENCE_SEMANTIC_DIFFERENCE:PRE_HISTORY_OFFSET" if abs(pre - 1) > 0.001
                     else "RAW_PRICE_MISMATCH" if close_bad and not (pa or sc or fe)
                     else "ADJUSTMENT_FACTOR_MISMATCH")
            evidence = f"raw={raw:.2f}, close_p95={r.get('close_p95')}, factor_near={f_near:.2f}, events={pa+sc+fe}"
        elif abs(pre - 1) > 0.001:
            scenario = "HISTORY_OFFSET"
            cause = "REFERENCE_SEMANTIC_DIFFERENCE:PRE_HISTORY_OFFSET"
            evidence = f"pre={pre:.6f}"
        else:
            scenario = "MATCHED"
            cause = "MATCHED"
            evidence = f"raw={raw:.2f}, factor_near={f_near:.2f}"
        rows.append({
            "asset_id": r.get("asset_id"), "symbol": sym, "class": r.get("class"),
            "ins_code": ins, "basis": r.get("basis"), "adjust_source": r.get("adjust_source"),
            "raw_ok_pct": raw, "factor_ok_pct": f_ok, "factor_near_pct": f_near,
            "factor_norm_near_pct": fn_near, "func_ok_pct": func,
            "pre_history_offset": pre, "constant_pre_history_offset": r.get("constant_pre_history_offset"),
            "step_pairs": pair, "ref_only_steps": ref_only, "prod_only_steps": prod_only,
            "step_ratio_mismatch": mismatch, "price_adjust_rows": pa,
            "share_change_rows": sc, "fund_events": fe,
            "product_first": r.get("product_history_start"), "ref_first": r.get("ref_history_start"),
            "scenario": scenario, "cause": cause, "evidence": evidence,
            "action": "keep official source; document semantic difference" if "SEMANTIC" in cause
                      else "inspect mapping/parser" if scenario.startswith("RAW") else "source archive",
        })
    con.close()
    with open(a.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("rows", len(rows))
    print(collections.Counter(r["scenario"] for r in rows))
    print(collections.Counter(r["cause"] for r in rows).most_common(10))


if __name__ == "__main__":
    main()
