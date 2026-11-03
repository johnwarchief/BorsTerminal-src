# -*- coding: utf-8 -*-
"""Reconstruct the Round-4 factor drop for the five symbols and the two controls."""
import argparse
import collections
import csv
import json
import os
import sqlite3


def load_product(path, symbols):
    out = {}
    for line in open(path, encoding="utf-8"):
        j = json.loads(line)
        if j.get("symbol") not in symbols:
            continue
        out[j["symbol"]] = {
            "candles": {str(c["time"])[:10]: c for c in (j.get("candles") or [])},
            "factors": {str(f["time"])[:10]: f["factor"] for f in (j.get("factors") or [])},
            "events": [(str(e.get("date"))[:10], e.get("ratio"), e.get("source"))
                       for e in (j.get("adjustEvents") or [])],
            "source": j.get("adjustSource"),
            "fetchedAt": j.get("fetchedAt"),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v3", required=True)
    ap.add_argument("--v4", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--v3-symbols", required=True)
    ap.add_argument("--v4-symbols", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    symbols = ["داسوه", "غپينو", "فاراك", "فولاژ", "غويتا", "غچين", "وبشهر"]
    p3 = load_product(a.v3, set(symbols))
    p4 = load_product(a.v4, set(symbols))
    s3 = {r["symbol"]: r for r in csv.DictReader(open(a.v3_symbols, encoding="utf-8-sig"))}
    s4 = {r["symbol"]: r for r in csv.DictReader(open(a.v4_symbols, encoding="utf-8-sig"))}

    ref0 = {}; ref7 = {}
    for line in open(a.ref, encoding="utf-8"):
        j = json.loads(line)
        sym = None
        for s in symbols:
            if str(j.get("asset_id")) == str(s4.get(s, {}).get("asset_id")):
                sym = s
                break
        if not sym:
            continue
        if j.get("type") == "type0" and j.get("res") == "D":
            ref0[sym] = {str(b[0])[:10]: b[4] for b in (j.get("bars") or [])}
        elif j.get("type") == "type7" and j.get("res") == "D":
            ref7[sym] = {str(b[0])[:10]: b[4] for b in (j.get("bars") or [])}

    con = sqlite3.connect("file:" + a.db + "?mode=ro", uri=True)
    rows = []
    for sym in symbols:
        q3, q4 = p3.get(sym, {}), p4.get(sym, {})
        c3, c4 = q3.get("candles", {}), q4.get("candles", {})
        f3, f4 = q3.get("factors", {}), q4.get("factors", {})
        common = sorted(set(c3) & set(c4))
        raw_diff = [d for d in common if c3[d].get("close") != c4[d].get("close")]
        fac_diff = [d for d in common if abs((f3.get(d) or 0) - (f4.get(d) or 0)) > 1e-9]
        ev3 = {(d, round(float(r or 0), 8)) for d, r, _s in q3.get("events", [])}
        ev4 = {(d, round(float(r or 0), 8)) for d, r, _s in q4.get("events", [])}
        ev_added = sorted(ev4 - ev3)
        ev_removed = sorted(ev3 - ev4)
        rf = {d: (ref7[sym][d] / ref0[sym][d]) for d in common
              if d in ref0.get(sym, {}) and ref0[sym].get(d)}
        err3 = [abs((f3[d] or 0) / rf[d] - 1) for d in common if d in rf and f3.get(d)]
        err4 = [abs((f4[d] or 0) / rf[d] - 1) for d in common if d in rf and f4.get(d)]
        ins = con.execute("SELECT ins_code FROM instruments WHERE l_val18=? "
                          "ORDER BY updated_at DESC LIMIT 1", (sym,)).fetchone()
        ins = str(ins[0]) if ins else ""
        pa = sc = 0
        if ins:
            pa = con.execute("SELECT COUNT(*) FROM price_adjust_events WHERE ins_code=?", (ins,)).fetchone()[0]
            sc = con.execute("SELECT COUNT(*) FROM share_change_events WHERE ins_code=?", (ins,)).fetchone()[0]
        cause = "UNVERIFIED"
        v3_local = str(q3.get("source") or "").startswith("local-")
        if v3_local and not str(q4.get("source") or "").startswith("local-"):
            cause = "SOURCE_REVISION:HISTORY_EXTENSION_FROM_LOCAL_FALLBACK"
        elif len(ev_added) == 1 and not raw_diff and not ev_removed:
            cause = "REFERENCE_SEMANTIC_DIFFERENCE:OFFICIAL_PRICE_ADJUST_NOT_MIRRORED"
        elif raw_diff and not ev_added and not ev_removed:
            cause = "RAW_DATA_CHANGED"
        elif ev_added or ev_removed:
            cause = "ADJUSTMENT_FACTOR_MISMATCH" if raw_diff else "CORPORATE_ACTION_TIMING"
        elif fac_diff and not raw_diff:
            cause = "REFERENCE_SEMANTIC_DIFFERENCE"
        rows.append({
            "symbol": sym, "asset_id": s4.get(sym, {}).get("asset_id"), "ins_code": ins,
            "ledger_price_adjust_rows": pa, "ledger_share_change_rows": sc,
            "v3_source": q3.get("source"), "v4_source": q4.get("source"),
            "v3_fetched_at": q3.get("fetchedAt"), "v4_fetched_at": q4.get("fetchedAt"),
            "v3_candles": len(c3), "v4_candles": len(c4),
            "v3_first": min(c3) if c3 else "", "v4_first": min(c4) if c4 else "",
            "raw_close_diff_dates": len(raw_diff),
            "raw_close_first_diff": raw_diff[0] if raw_diff else "",
            "raw_close_last_diff": raw_diff[-1] if raw_diff else "",
            "factor_diff_dates": len(fac_diff),
            "factor_first_diff": fac_diff[0] if fac_diff else "",
            "factor_last_diff": fac_diff[-1] if fac_diff else "",
            "events_added": len(ev_added), "events_removed": len(ev_removed),
            "events_added_sample": json.dumps(ev_added[:5], ensure_ascii=False),
            "events_removed_sample": json.dumps(ev_removed[:5], ensure_ascii=False),
            "median_err_v3_pct": round(100 * sorted(err3)[len(err3)//2], 4) if err3 else "",
            "median_err_v4_pct": round(100 * sorted(err4)[len(err4)//2], 4) if err4 else "",
            "factor_near_v3": s3.get(sym, {}).get("factor_near_pct"),
            "factor_near_v4": s4.get(sym, {}).get("factor_near_pct"),
            "cause": cause,
            "action": "keep fresh official/raw data" if cause in ("SOURCE_REVISION", "RAW_DATA_CHANGED")
                      else "inspect parser/event mapping",
        })
    con.close()
    with open(a.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(collections.Counter(r["cause"] for r in rows))
    for r in rows:
        print(r["symbol"], r["raw_close_diff_dates"], r["factor_diff_dates"],
              r["events_added"], r["events_removed"], r["factor_near_v3"], "->", r["factor_near_v4"], r["cause"])


if __name__ == "__main__":
    main()
