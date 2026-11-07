# -*- coding: utf-8 -*-
"""Ingest official TSETMC price-adjust flow rows into an isolated DB.

Only rows with an official share change within `--window` days are inserted by
default: their PA ratio is the official total price adjustment and must not be
treated as a cash dividend.  Idempotent on (ins_code, d_even).  Never writes the
operational DB: --db is required and must point to a copy.
"""
import argparse
import csv
import datetime as dt
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXED_FETCHED_AT = "2026-10-21T00:00:00"


def _iso(d):
    s = str(d)
    return f"{s[:4]}-{s[4:6]}-{s[6:]}" if len(s) == 8 else None


def _day_diff(a, b):
    try:
        return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)
    except Exception:
        return None


def load_flows(paths):
    rows = {}
    for path in paths:
        if not os.path.exists(path):
            continue
        j = json.load(open(path, encoding="utf-8"))
        for r in j.get("priceAdjust") or []:
            ins = str((r.get("instrument") or {}).get("insCode") or "")
            d = int(r.get("dEven") or 0)
            if not ins or not d or (ins, d) in rows:
                continue
            rows[(ins, d)] = {
                "ins": ins, "d": d, "pc": r.get("pClosing"),
                "pn": r.get("pClosingNotAdjusted"),
                "flow": (r.get("instrument") or {}).get("flow"),
            }
    return rows


def ingest(db, flow_paths, linked_only=True, window=10, out_csv=None, capital_only=False):
    con = sqlite3.connect(db, timeout=60)
    ins2sym = {}
    for ins, sym in con.execute("SELECT ins_code,l_val18 FROM instruments"):
        ins2sym.setdefault(str(ins), sym)
    shares = {}
    for ins, d, r in con.execute("SELECT ins_code,d_even,ratio FROM share_change_events"):
        if r is not None and abs(float(r) - 1.0) > 1e-9:
            shares.setdefault(str(ins), []).append((_iso(d), float(r)))
    rows = load_flows(flow_paths)
    audit = []
    inserted = skipped = 0
    for (ins, d), r in sorted(rows.items(), key=lambda x: (x[0][0], x[0][1])):
        if not r["pc"] or not r["pn"]:
            continue
        try:
            pa_ratio = float(r["pc"]) / float(r["pn"])
        except Exception:
            continue
        dt_iso = _iso(d)
        near = None
        for sd, sr in shares.get(ins, []):
            diff = _day_diff(sd, dt_iso) if dt_iso else None
            if diff is not None and diff <= window and (near is None or diff < near[0]):
                near = (diff, sd, sr)
        rec = {"ins_code": ins, "symbol": ins2sym.get(ins),
               "d_even": d, "pa_ratio": round(pa_ratio, 10),
               "share_date": near[1] if near else None,
               "share_ratio": round(near[2], 10) if near else None,
               "diff_days": near[0] if near else None,
               "event_type": "", "action": "SKIP"}
        if near:
            rec["event_type"] = ("CAPITAL" if abs(pa_ratio / near[2] - 1.0) <= 0.02
                                 else "COMBINED_OR_CONFLICT")
        if linked_only and not near:
            skipped += 1
            audit.append(rec)
            continue
        if capital_only and rec["event_type"] != "CAPITAL":
            skipped += 1
            audit.append(rec)
            continue
        con.execute(
            "INSERT OR REPLACE INTO price_adjust_events"
            "(ins_code,d_even,symbol,p_closing,p_closing_not_adjusted,"
            "corporate_type_code,ratio,source,fetched_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (ins, d, ins2sym.get(ins), float(r["pc"]), float(r["pn"]), None,
             round(pa_ratio, 10),
             "tsetmc_price_adjust_by_flow:linked" if near else "tsetmc_price_adjust_by_flow",
             FIXED_FETCHED_AT))
        rec["action"] = "INSERTED"
        inserted += 1
        audit.append(rec)
    con.commit()
    con.close()
    if out_csv:
        with open(out_csv, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(audit[0]) if audit else ["ins_code"])
            w.writeheader()
            w.writerows(audit)
    return {"inserted": inserted, "skipped_unlinked": skipped, "total": len(rows)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--flows", required=True, help="comma-separated flow JSON files")
    ap.add_argument("--linked-only", action="store_true")
    ap.add_argument("--capital-only", action="store_true")
    ap.add_argument("--window", type=int, default=10)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    res = ingest(a.db, [p for p in a.flows.split(",") if p], a.linked_only,
                 a.window, a.out or None, a.capital_only)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
