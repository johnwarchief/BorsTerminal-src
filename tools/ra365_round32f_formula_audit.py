#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R32F: measure how much of the reference factor chain the *formula* reproduces
from official sources, and what remains pack-only.

Inputs are read-only:
  • the R32B correction pack (reference-derived steps),
  • official TSETMC full-history price-adjust / share-change JSON captures,
  • optionally an isolated DB carrying `fund_profit_events`.

No network, no writes to the operational DB.  The output is a JSON summary with
per-family step accuracy and official coverage; raw official rows are not copied.

Definitions
-----------
step accuracy   |prod_ratio - ratio| buckets, where `prod_ratio` is the product's
                own step ratio at the same date (the formula's output).
official cover  an official PA/SH row within ±7 days whose ratio agrees with the
                reference to <=1e-6.
fund agreement  the portal's (P-D)/P ratio vs the product step and vs the
                reference step; the portal dates are the first session after the
                distribution date, so same-date matching is attempted first.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PACK = os.path.join(ROOT, "data", "ra365_corrections",
                            "ra365-r32b-v2", "factors.jsonl")


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _date_from_int(v):
    s = str(int(v))
    return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def _date_from_iso(s):
    return dt.date(*map(int, str(s)[:10].split("-")))


def _bucket(diff):
    if diff is None:
        return "no_prod"
    if diff <= 1e-9:
        return "exact"
    if diff <= 1e-6:
        return "le1e-6"
    if diff <= 1e-4:
        return "le1e-4"
    return "gt1e-4"


def load_pack(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_official(directory):
    spec = {
        "pa": ("pa_flow1.json", "pa_flow2.json", "priceAdjust"),
        "sh": ("sh_flow1.json", "sh_flow2.json", "instrumentShareChange"),
    }
    out = {}
    meta = {}
    for kind, (f1, f2, key) in spec.items():
        rows = []
        hashes = {}
        for name in (f1, f2):
            path = os.path.join(directory, name)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as fh:
                raw = fh.read()
            hashes[name] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            rows.extend(json.loads(raw).get(key) or [])
        # PA may emit several rows for the same (ins, date); their ratio is a
        # product, so the inner default must be 1.0 (0.0 would swallow every
        # same-date row).  SH assigns a single ratio directly.
        table = collections.defaultdict(lambda: collections.defaultdict(lambda: 1.0))
        dates = []
        for r in rows:
            if kind == "pa":
                inst = r.get("instrument") or {}
                ins = str(inst.get("insCode") or r.get("insCode") or "")
                try:
                    d = _date_from_int(r["dEven"])
                    pc = float(r["pClosing"])
                    pn = float(r["pClosingNotAdjusted"])
                except (KeyError, TypeError, ValueError):
                    continue
                if not ins or not pc or not pn:
                    continue
                table[ins][d] *= pc / pn
                dates.append(d)
            else:
                ins = str(r.get("insCode") or "")
                try:
                    d = _date_from_int(r["dEven"])
                    old = float(r["numberOfShareOld"])
                    new = float(r["numberOfShareNew"])
                except (KeyError, TypeError, ValueError):
                    continue
                if not ins or not old or not new:
                    continue
                table[ins][d] = old / new
                dates.append(d)
        out[kind] = table
        meta[kind] = {
            "rows": len(rows),
            "instruments": len(table),
            "range": [str(min(dates)), str(max(dates))] if dates else [None, None],
            "files": hashes,
        }
    return out, meta


def load_funds(db_path):
    if not db_path or not os.path.exists(db_path):
        return {}, {}
    con = sqlite3.connect("file:%s?mode=ro" % db_path.replace("\\", "/"), uri=True)
    try:
        rows = con.execute(
            "SELECT ins_code, d_even, unit_profit, reference_price, ratio, source"
            " FROM fund_profit_events").fetchall()
    finally:
        con.close()
    table = collections.defaultdict(dict)
    for ins, d, unit, ref, ratio, source in rows:
        if ratio is None:
            continue
        table[str(ins)][_date_from_int(d)] = {
            "ratio": float(ratio), "unit": unit, "reference": ref, "source": source}
    meta = {"db": os.path.basename(db_path), "rows": len(rows), "instruments": len(table),
            "files": {os.path.basename(db_path): _sha(db_path)}
            if os.path.exists(db_path) else {}}
    return table, meta


def best_official(table, ins, date, tol):
    """Ratio of the official row nearest to `date` within `tol` days, or None."""
    best = None
    for d, value in table.get(ins, {}).items():
        dd = abs((d - date).days)
        if dd <= tol and (best is None or dd < best[0]):
            ratio = value["ratio"] if isinstance(value, dict) else value
            best = (dd, ratio)
    return None if best is None else best[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default=DEFAULT_PACK)
    ap.add_argument("--official-dir", required=True)
    ap.add_argument("--fund-db", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tol-days", type=int, default=7)
    ap.add_argument("--agree", type=float, default=1e-6)
    a = ap.parse_args()

    pack = load_pack(a.pack)
    steps = [r for r in pack if r.get("action") == "replace_step"]
    official, official_meta = load_official(a.official_dir)
    funds, fund_meta = load_funds(a.fund_db)

    fam = collections.defaultdict(collections.Counter)
    fund_cmp = collections.Counter()
    fund_rows = []
    for r in steps:
        sig = r.get("event_sig") or "?"
        ref = float(r["ratio"])
        prod = r.get("prod_ratio")
        date = _date_from_iso(r["effective_date"])
        ins = str(r.get("ins_code") or "")
        c = fam[sig]
        c["n"] += 1
        c[_bucket(None if prod is None else abs(float(prod) - ref))] += 1

        pa = best_official(official["pa"], ins, date, a.tol_days)
        sh = best_official(official["sh"], ins, date, a.tol_days)
        if pa is not None:
            c["pa_hit"] += 1
            if abs(pa - ref) <= a.agree:
                c["pa_agree"] += 1
        if sh is not None:
            c["sh_hit"] += 1
            if abs(sh - ref) <= a.agree:
                c["sh_agree"] += 1
        if pa is None and sh is None:
            c["no_official"] += 1

        f = funds.get(ins, {}).get(date)
        if f is not None:
            c["fund_hit"] += 1
            official_ratio = float(f["ratio"])
            if prod is not None and abs(official_ratio - float(prod)) <= a.agree:
                fund_cmp["official_vs_product_agree"] += 1
            if abs(official_ratio - ref) <= a.agree:
                fund_cmp["official_vs_reference_agree"] += 1
            fund_cmp["fund_steps_with_official"] += 1
            fund_rows.append({
                "symbol": r.get("symbol"), "date": r["effective_date"],
                "reference": ref, "product": prod,
                "official": official_ratio,
                "product_diff": None if prod is None else abs(official_ratio - float(prod)),
                "reference_diff": abs(official_ratio - ref),
            })

    total = collections.Counter()
    for c in fam.values():
        total.update(c)

    pack_path = os.path.relpath(a.pack, ROOT) if os.path.abspath(
        a.pack).startswith(os.path.abspath(ROOT)) else a.pack
    summary = {
        "schema": "ra365-round32f-formula-audit-v1",
        "pack": {"path": pack_path.replace("\\", "/"), "sha256": _sha(a.pack),
                 "rows": len(pack), "steps": len(steps)},
        "official": official_meta,
        "fund_db": fund_meta,
        "tolerance_days": a.tol_days,
        "agreement_tolerance": a.agree,
        "totals": dict(total),
        "families": {k: dict(v) for k, v in sorted(fam.items(),
                                                   key=lambda kv: -kv[1]["n"])},
        "fund_comparison": dict(fund_cmp),
        "fund_samples": sorted(fund_rows, key=lambda x: -(x["reference_diff"] or 0))[:12],
        "notes": [
            "prod_ratio is the product's own step at the reference date; it is the "
            "formula output before the correction pack.",
            "pa_hit/sh_hit count official rows within tolerance_days; pa_agree/"
            "sh_agree require the official ratio to match the reference within "
            "agreement_tolerance.",
            "fund_dps steps compare the portal's (P-D)/P with the product step and "
            "the reference step; the portal convention is market-price based.",
        ],
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    print(json.dumps({"totals": summary["totals"],
                      "fund_comparison": summary["fund_comparison"]},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
