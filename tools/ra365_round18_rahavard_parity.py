# -*- coding: utf-8 -*-
"""Round 18 Track A continuation - exhaustive Rahavard type0 raw OHLC parity.

The frozen Rahavard snapshot (ref_bars_v2.jsonl) is compared row by row with
the actual BorsTerminal chart candles.  TSETMC raw is used only as an
independent oracle to prove what type0 fields mean and to adjudicate
divergences; it is not substituted for Rahavard.

Outputs are versioned under artifacts/ra365/r18-rahavard/ and never overwrite
the earlier r18 TSETMC artifacts.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import sqlite3
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.environ.get("RA365_R18_CACHE", "D:/BorsTerminal-tmp/ra365_round18")
ART = os.path.join(ROOT, "artifacts", "ra365", "r18-rahavard")
REF_FILE = os.path.join(os.path.dirname(os.path.dirname(ROOT)), "_scratch",
                        "ra_fup_2026_10_20", "ref_bars_v2.jsonl")
PROD_FILE = os.path.join(os.path.dirname(os.path.dirname(ROOT)), "_scratch",
                         "ra_round3", "product_live_final_v4.jsonl")
DB = os.path.join(CACHE, "reference.db")
COHORT = os.path.join(CACHE, "cohort.jsonl")
ABS = 0.5
REL_ROUND = 0.0005


def fa_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(a, b):
    if b in (None, 0):
        return None
    return abs(a - b) / abs(b)


def status(ref, prod):
    if ref is None or prod is None:
        return "NULL"
    ref = float(ref); prod = float(prod)
    if ref == prod:
        return "EXACT"
    d = abs(ref - prod)
    if d <= ABS:
        return "TOL"
    if ref and d / abs(ref) <= REL_ROUND:
        return "ROUNDING"
    return "DIFF"


def widen(o, h, l, c):
    body = [x for x in (o, c) if x]
    hi = max([h] + body) if h else (max(body) if body else 0.0)
    lo = min([l] + body) if l else (min(body) if body else 0.0)
    return hi, lo


def iso_key(d):
    s = str(d)[:10]
    return s if len(s) == 10 else None


def classify(field, ref, prod, t0, tsetmc, product_basis, product_close,
             near_dates, type0_flat, type0_bad_geom):
    """Evidence-backed single primary cause for a contract-field mismatch."""
    try:
        reff = float(ref); prodf = float(prod)
    except (TypeError, ValueError):
        return "UNCLASSIFIED", "LOW", "non-numeric"
    d = abs(reff - prodf); r = rel(prodf, reff)
    if field == "volume" and prodf == 0 and reff > 0:
        return ("PARSING_OR_TRANSFORM", "MEDIUM",
                "product volume is zero while type0 source volume is positive")
    if reff and any(abs(prodf / reff - k) <= 0.001
                    for k in (10, 100, 1000, 0.1, 0.01, 0.001)):
        return "PRICE_SCALE_OR_UNIT", "HIGH", "ratio=%.6f" % (prodf / reff)
    if r is not None and r <= REL_ROUND:
        return "PRECISION_OR_ROUNDING", "HIGH", "relative diff <= 0.05%"
    if type0_flat and field in ("open", "high_raw", "low_raw"):
        return ("CANDLE_GEOMETRY", "HIGH",
                "type0 O=H=L=C flat bar; only close/last is reliable")
    if type0_bad_geom and field in ("high_raw", "low_raw"):
        return ("CANDLE_GEOMETRY", "HIGH",
                "type0 H/L outside body; product widen() repairs geometry")
    if type0_flat and field in ("high_raw", "low_raw"):
        return ("CANDLE_GEOMETRY", "MEDIUM",
                "type0 O=H=L=C (flat/no-trade bar); product contract widens")
    if field == "open" and tsetmc is not None:
        if abs(prodf - tsetmc["first"]) <= ABS and abs(reff - tsetmc["first"]) > ABS:
            return ("SOURCE_DATA_DIVERGENCE", "HIGH",
                    "product open matches TSETMC FIRST, type0 does not")
    if field in ("last", "close_display", "volume") and tsetmc is not None:
        tv = (tsetmc["last"] if field in ("last", "close_display")
              else tsetmc["volume"])
        if tv is not None and abs(prodf - tv) <= ABS and abs(reff - tv) > ABS:
            return ("SOURCE_DATA_DIVERGENCE", "HIGH",
                    "product %s matches TSETMC, type0 does not" % field)
    if field in ("high_raw", "low_raw") and tsetmc is not None:
        th = tsetmc["high"] if field == "high_raw" else tsetmc["low"]
        if th is not None and abs(prodf - th) <= ABS and abs(reff - th) > ABS:
            return ("SOURCE_DATA_DIVERGENCE", "HIGH",
                    "product %s matches TSETMC, type0 does not" % field)
    if field == "close_display" and product_basis != "last":
        return ("FIELD_MAPPING", "HIGH",
                "display basis=%s while type0 close is last" % product_basis)
    # A neighboring type0 date that carries the product value is date mapping.
    for nd, row in near_dates:
        v = None
        if field == "open": v = row.get("open")
        elif field == "high_raw": v = row.get("high")
        elif field == "low_raw": v = row.get("low")
        elif field in ("last", "close_display"): v = row.get("close")
        elif field == "volume": v = row.get("volume")
        if v is not None and abs(v - prodf) <= ABS:
            return ("DATE_MAPPING", "MEDIUM",
                    "product value matches type0 neighboring date %s" % nd)
    # If current TSETMC agrees with type0, the product snapshot is older/revised.
    if tsetmc is not None:
        tval = (tsetmc["first"] if field == "open" else
                tsetmc["high"] if field == "high_raw" else
                tsetmc["low"] if field == "low_raw" else
                tsetmc["last"] if field in ("last", "close_display") else
                tsetmc["volume"])
        if tval is not None and abs(tval - reff) <= ABS and abs(tval - prodf) > ABS:
            return ("HISTORICAL_REVISION", "MEDIUM",
                    "type0/TSETMC agree, product snapshot differs")
    return "UNCLASSIFIED", "LOW", "abs=%.4f rel=%s" % (d, r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    os.makedirs(ART, exist_ok=True)
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    # Type0/type7 are already unique by (asset,date) in reference.db.
    totals = Counter()
    tax = defaultdict(lambda: {"assets": set(), "rows": 0, "dates": set(),
                               "fields": 0, "samples": [], "conf": Counter()})
    row_tax = defaultdict(lambda: {"assets": set(), "dates": set(), "rows": 0})
    parity_path = os.path.join(ART, "rahavard-raw-ohlc-parity.csv")
    sem_path = os.path.join(ART, "rahavard-type0-vs-tsetmc.csv")
    miss_path = os.path.join(ART, "rahavard-raw-ohlc-missing.csv")
    field_path = os.path.join(ART, "rahavard-raw-ohlc-field-mismatches.csv")
    pf = open(parity_path, "w", encoding="utf-8-sig", newline="")
    pw = csv.writer(pf)
    fields = ("open", "high_raw", "low_raw", "last", "close_display", "volume")
    pw.writerow(["ra_asset_id", "symbol", "ins_code", "basis", "product_count",
                 "type0_rows", "tsetmc_rows", "common_pc", "common_ct",
                 "row_pairs", "row_exact", "row_tol", "row_exact_pct", "row_tol_pct",
                 "literal_high_exact", "literal_low_exact", "literal_row_exact",
                 "literal_row_tol", "contract_cmp", "contract_ok", "contract_ok_pct", "last_null",
                 "type0_flat", "type0_bad_geom", "type7_diff_rows",
                 "product_only_outside", "product_only_inside",
                 "product_only_no_trade", "product_only_tradable",
                 "product_only_rahavard_omission", "product_only_unverified",
                 "type0_only_outside", "type0_only_no_trade", "type0_only_tradable",
                 "type0_only_rahavard_date", "type0_only_product_omission",
                 "close_official_vs_type0_diff", "status"] +
                [f"{f}_{s}" for f in fields for s in ("cmp", "exact", "tol", "diff", "null")])
    sf = open(sem_path, "w", encoding="utf-8-sig", newline="")
    sw = csv.writer(sf)
    sw.writerow(["ra_asset_id", "symbol", "ins_code", "type0_rows", "common_ct",
                 "close_last_cmp", "close_last_exact", "close_official_cmp",
                 "close_official_exact", "open_first_cmp", "open_first_exact",
                 "open_base_cmp", "open_base_exact", "high_cmp", "high_exact",
                 "low_cmp", "low_exact", "vol_cmp", "vol_exact",
                 "flat", "bad_geom", "type7_diff_rows"])
    mf = open(miss_path, "w", encoding="utf-8-sig", newline="")
    mw = csv.writer(mf)
    mw.writerow(["ra_asset_id", "symbol", "date", "category", "source",
                 "high", "low", "close", "volume"])
    xf = open(field_path, "w", encoding="utf-8-sig", newline="")
    xw = csv.writer(xf)
    xw.writerow(["ra_asset_id", "symbol", "date", "field", "ref", "prod",
                 "abs_diff", "rel_diff", "basis", "cause", "confidence", "note"])
    n_miss = n_field = 0
    n_assets = 0
    for line in open(COHORT, encoding="utf-8"):
        if args.limit and n_assets >= args.limit:
            break
        j = json.loads(line)
        n_assets += 1
        aid = j["ra_asset_id"]; sym = j["symbol"]; ins = j["ins_code"]
        basis = j.get("basis") or "last"
        P = {r[0]: {"open": r[1], "high": r[2], "low": r[3], "close": r[4],
                    "closing": r[5], "last": r[6], "high_raw": r[7],
                    "low_raw": r[8], "volume": r[9]}
             for r in j["candles"]}
        C = {}
        for r in con.execute(
                "SELECT date,open,high,low,close,volume FROM type0 WHERE ra_asset_id=?",
                (aid,)):
            C[r[0]] = {"open": r[1], "high": r[2], "low": r[3],
                       "close": r[4], "volume": r[5]}
        T = {r[0]: {"first": r[1], "high": r[2], "low": r[3], "close": r[4],
                    "volume": r[5], "base": r[6], "last": r[7]}
             for r in con.execute(
                 "SELECT date,first,high,low,close,volume,base,last FROM tsetmc "
                 "WHERE ins_code=?", (ins,))}
        C7 = {r[0]: r[1] for r in con.execute(
            "SELECT date,close FROM type7 WHERE ra_asset_id=?", (aid,))}
        counts = Counter()
        for f in fields:
            counts[(f, "cmp")] = 0
        row_pairs = row_exact = row_tol = 0
        lit_high = lit_low = lit_row = lit_tol = 0
        row_causes = []
        last_null = flat = bad = t7diff = 0
        close_official_diff = 0
        # type0 vs TSETMC semantics
        sem = Counter()
        for d, c in C.items():
            t = T.get(d)
            if not t:
                continue
            sem["common"] += 1
            if c["open"] == c["high"] == c["low"] == c["close"]:
                sem["flat"] += 1
                flat += 1
            if c["high"] < max(c["open"], c["close"]) or \
                    c["low"] > min(c["open"], c["close"]):
                sem["bad"] += 1
                bad += 1
            for name, refv, prodv in (
                    ("close_last", t["last"], c["close"]),
                    ("close_official", t["close"], c["close"]),
                    ("open_first", t["first"], c["open"]),
                    ("open_base", t["base"], c["open"]),
                    ("high", t["high"], c["high"]),
                    ("low", t["low"], c["low"]),
                    ("vol", t["volume"], c["volume"])):
                st = status(refv, prodv)
                sem[(name, "cmp")] += 0 if st == "NULL" else 1
                sem[(name, st.lower())] += 1
            if d in C7 and status(c["close"], C7[d]) == "DIFF":
                t7diff += 1
        # type0 vs product: contract-aware raw comparison
        for d in sorted(set(P) & set(C)):
            c = P[d]; z = C[d]
            # Parser contract: type0 literal O/H/L plus the independent official
            # CLOSE.  Type0 close is LAST, not the parser body close.
            t = T.get(d)
            official_close = (t["close"] if t and t.get("close") is not None
                              else c["closing"] if c.get("closing") is not None
                              else z["close"])
            hi, lo = widen(z["open"], z["high"], z["low"], official_close)
            checks = {
                "open": (z["open"], c["open"]),
                "high_raw": (hi, c["high_raw"] if c["high_raw"] is not None else c["high"]),
                "low_raw": (lo, c["low_raw"] if c["low_raw"] is not None else c["low"]),
                "last": (z["close"], c["last"]),
                "close_display": (z["close"], c["close"]),
                "volume": (z["volume"], c["volume"]),
            }
            row_ok = True; row_tol_ok = True
            row_causes = []
            core = ("open", "high_raw", "low_raw", "last", "volume")
            lit_h = status(z["high"], c["high"])
            lit_l = status(z["low"], c["low"])
            if lit_h == "EXACT": lit_high += 1
            if lit_l == "EXACT": lit_low += 1
            if lit_h == "EXACT" and lit_l == "EXACT" and \
                    status(z["open"], c["open"]) == "EXACT" and \
                    status(z["close"], c["last"]) == "EXACT":
                lit_row += 1
            if lit_h in ("EXACT", "TOL") and lit_l in ("EXACT", "TOL") and \
                    status(z["open"], c["open"]) in ("EXACT", "TOL") and \
                    status(z["close"], c["last"]) in ("EXACT", "TOL"):
                lit_tol += 1
            for f, (ref, prod) in checks.items():
                st = status(ref, prod)
                counts[(f, "cmp")] += 0 if st == "NULL" else 1
                counts[(f, st.lower())] += 1
                if st in ("EXACT", "TOL"):
                    counts[(f, "ok")] += 1
                else:
                    if f in core:
                        row_ok = False
                    if st != "NULL":
                        refv = float(ref); prodv = float(prod)
                        cause, conf, note = classify(
                            f, refv, prodv, z, T.get(d), basis, c["close"],
                            [], c["open"] == c["high"] == c["low"] == c["close"],
                            z["high"] < max(z["open"], z["close"]) or
                            z["low"] > min(z["open"], z["close"]))
                        tax[cause]["assets"].add(aid); tax[cause]["rows"] += 1
                        tax[cause]["dates"].add((aid, d))
                        tax[cause]["fields"] += 1; tax[cause]["conf"][conf] += 1
                        if f in core:
                            row_causes.append(cause)
                        if len(tax[cause]["samples"]) < 4:
                            tax[cause]["samples"].append([sym, d, f, ref, prod, note])
                        if n_field < 200000:
                            xw.writerow([aid, sym, d, f, ref, prod, abs(refv - prodv),
                                         rel(prodv, refv), basis, cause, conf, note])
                            n_field += 1
                if f in core and st not in ("EXACT", "TOL"):
                    row_tol_ok = False
                if f == "last" and st == "NULL":
                    last_null += 1
            if c["closing"] is not None and status(z["close"], c["closing"]) == "DIFF":
                close_official_diff += 1
            comp_core = all(checks[f][0] is not None and checks[f][1] is not None
                            for f in core)
            if comp_core and row_ok:
                row_exact += 1
            if comp_core and row_tol_ok:
                row_tol += 1
            if comp_core and not row_ok and row_causes:
                prio = ("INSTRUMENT_MAPPING", "DATE_MAPPING", "SOURCE_DATA_DIVERGENCE",
                        "HISTORICAL_REVISION", "CANDLE_GEOMETRY", "FIELD_MAPPING",
                        "PARSING_OR_TRANSFORM", "PRECISION_OR_ROUNDING",
                        "PRICE_SCALE_OR_UNIT", "UNCLASSIFIED")
                pc = next((x for x in prio if x in row_causes), row_causes[0])
                row_tax[pc]["assets"].add(aid); row_tax[pc]["dates"].add((aid, d))
                row_tax[pc]["rows"] += 1
            if comp_core:
                row_pairs += 1
        # coverage / missing bars
        ponly_out = ponly_in = ponly_nt = ponly_tr = 0
        ponly_ra = ponly_unv = 0
        zonly_out = zonly_nt = zonly_tr = 0
        zonly_date = zonly_prod = 0
        cmin = min(C) if C else None; cmax = max(C) if C else None
        pmin = min(P) if P else None; pmax = max(P) if P else None
        for d in set(P) - set(C):
            if cmin and cmax and cmin <= d <= cmax:
                ponly_in += 1
                p = P[d]
                if (p.get("volume") or 0) == 0:
                    ponly_nt += 1
                    cat = "PRODUCT_ONLY_NO_TRADE"
                else:
                    ponly_tr += 1
                    t = T.get(d)
                    if t and t["high"] > 0 and t["low"] > 0 and t["volume"] > 0:
                        ponly_ra += 1
                        cat = "PRODUCT_ONLY_RAHAVARD_OMISSION"
                    else:
                        ponly_unv += 1
                        cat = "PRODUCT_ONLY_UNVERIFIED"
                if n_miss < 50000:
                    mw.writerow([aid, sym, d, cat, "BorsTerminal",
                                 p.get("high"), p.get("low"), p.get("close"),
                                 p.get("volume")])
                    n_miss += 1
            else:
                ponly_out += 1
        for d in set(C) - set(P):
            z = C[d]
            if pmin and pmax and pmin <= d <= pmax:
                if z["volume"] == 0 or z["high"] <= 0 or z["low"] <= 0:
                    zonly_nt += 1
                    cat = "TYPE0_ONLY_NO_TRADE"
                else:
                    zonly_tr += 1
                    t = T.get(d)
                    if t and t["high"] > 0 and t["low"] > 0 and t["volume"] > 0:
                        zonly_prod += 1
                        cat = "TYPE0_ONLY_PRODUCT_OMISSION"
                    else:
                        zonly_date += 1
                        cat = "TYPE0_ONLY_RAHAVARD_DATE"
            else:
                zonly_out += 1
                cat = "TYPE0_OUTSIDE_PRODUCT_RANGE"
            if n_miss < 50000:
                mw.writerow([aid, sym, d, cat, "Rahavard",
                             z["high"], z["low"], z["close"], z["volume"]])
                n_miss += 1
        contract_cmp = sum(counts[(f, "cmp")] for f in fields)
        contract_ok = sum(counts[(f, "ok")] for f in fields)
        pw.writerow([aid, sym, ins, basis, len(P), len(C), len(T),
                     len(set(P) & set(C)), sem["common"], row_pairs, row_exact,
                     row_tol, round(100 * row_exact / row_pairs, 4) if row_pairs else "",
                     round(100 * row_tol / row_pairs, 4) if row_pairs else "",
                     lit_high, lit_low, lit_row, lit_tol,
                     contract_cmp, contract_ok,
                     round(100 * contract_ok / contract_cmp, 4) if contract_cmp else "",
                     last_null, flat, bad, t7diff, ponly_out, ponly_in,
                     ponly_nt, ponly_tr, ponly_ra, ponly_unv,
                     zonly_out, zonly_nt, zonly_tr, zonly_date, zonly_prod,
                     close_official_diff,
                     "ok" if contract_cmp and contract_ok / contract_cmp >= 0.999
                     else "attention"] +
                    [x for f in fields for x in
                     (counts[(f, "cmp")], counts[(f, "exact")], counts[(f, "tol")],
                      counts[(f, "diff")], counts[(f, "null")])])
        sw.writerow([aid, sym, ins, len(C), sem["common"],
                     sem[("close_last", "cmp")], sem[("close_last", "exact")],
                     sem[("close_official", "cmp")], sem[("close_official", "exact")],
                     sem[("open_first", "cmp")], sem[("open_first", "exact")],
                     sem[("open_base", "cmp")], sem[("open_base", "exact")],
                     sem[("high", "cmp")], sem[("high", "exact")],
                     sem[("low", "cmp")], sem[("low", "exact")],
                     sem[("vol", "cmp")], sem[("vol", "exact")],
                     sem["flat"], sem["bad"], t7diff])
        for k, v in [("row_pairs", row_pairs), ("row_exact", row_exact),
                     ("row_tol", row_tol), ("contract_cmp", contract_cmp),
                     ("contract_ok", contract_ok), ("last_null", last_null),
                     ("flat", flat), ("bad_geom", bad), ("type7_diff", t7diff),
                     ("product_only_inside", ponly_in),
                     ("product_only_outside", ponly_out),
                     ("product_only_no_trade", ponly_nt),
                     ("product_only_tradable", ponly_tr),
                     ("product_only_rahavard_omission", ponly_ra),
                     ("product_only_unverified", ponly_unv),
                     ("type0_only_outside", zonly_out),
                     ("type0_only_no_trade", zonly_nt),
                     ("type0_only_tradable", zonly_tr),
                     ("type0_only_rahavard_date", zonly_date),
                     ("type0_only_product_omission", zonly_prod),
                     ("close_official_diff", close_official_diff)]:
            totals[k] += v
        for f in fields:
            for s in ("cmp", "exact", "tol", "diff", "null", "ok"):
                totals[(f, s)] += counts[(f, s)]
        totals["assets"] += 1
        totals["lit_high"] += lit_high; totals["lit_low"] += lit_low
        totals["lit_row"] += lit_row; totals["lit_tol"] += lit_tol
        if C:
            totals["type0_assets"] += 1
        if totals["assets"] % 250 == 0:
            print("  %d assets" % totals["assets"], flush=True)
    pf.close(); sf.close(); mf.close(); xf.close()
    con.close()
    # aggregate type0 semantics exact percentages
    sem_tot = Counter()
    for r in csv.DictReader(open(sem_path, encoding="utf-8-sig")):
        for k in ("close_last_cmp", "close_last_exact", "close_official_cmp",
                  "close_official_exact", "open_first_cmp", "open_first_exact",
                  "open_base_cmp", "open_base_exact", "high_cmp", "high_exact",
                  "low_cmp", "low_exact", "vol_cmp", "vol_exact", "flat",
                  "bad_geom", "type7_diff_rows"):
            try:
                sem_tot[k] += int(r[k] or 0)
            except ValueError:
                pass
    tax_path = os.path.join(ART, "rahavard-raw-ohlc-taxonomy.csv")
    with open(tax_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cause", "confidence", "assets", "dates", "field_mismatches",
                    "share_of_contract_rows_pct", "samples"])
        n = sum(v["rows"] for v in tax.values()) or 1
        for k in sorted(tax, key=lambda x: -tax[x]["rows"]):
            v = tax[k]
            w.writerow([k, (v["conf"].most_common(1) or [("", 0)])[0][0],
                        len(v["assets"]), len(v["dates"]), v["fields"],
                        round(100.0 * v["rows"] / n, 4),
                        json.dumps(v["samples"][:3], ensure_ascii=False)])
    with open(os.path.join(ART, "rahavard-raw-ohlc-row-taxonomy.csv"), "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cause", "assets", "dates", "rows"])
        for k in sorted(row_tax, key=lambda x: -row_tax[x]["rows"]):
            v = row_tax[k]
            w.writerow([k, len(v["assets"]), len(v["dates"]), v["rows"]])
    summary = {
        "assets": totals["assets"],
        "type0_assets": totals["type0_assets"],
        "contract_compared_fields": totals["contract_cmp"],
        "contract_ok_fields": totals["contract_ok"],
        "contract_ok_pct": round(100.0 * totals["contract_ok"] /
                                 max(1, totals["contract_cmp"]), 4),
        "row_pairs": totals["row_pairs"], "row_exact": totals["row_exact"],
        "row_tol": totals["row_tol"],
        "row_exact_pct": round(100.0 * totals["row_exact"] /
                               max(1, totals["row_pairs"]), 4),
        "row_tol_pct": round(100.0 * totals["row_tol"] /
                             max(1, totals["row_pairs"]), 4),
        "literal_high_exact_pct": round(100.0 * totals["lit_high"] /
                                        max(1, totals["row_pairs"]), 4),
        "literal_low_exact_pct": round(100.0 * totals["lit_low"] /
                                       max(1, totals["row_pairs"]), 4),
        "literal_row_exact_pct": round(100.0 * totals["lit_row"] /
                                       max(1, totals["row_pairs"]), 4),
        "literal_row_tol_pct": round(100.0 * totals["lit_tol"] /
                                     max(1, totals["row_pairs"]), 4),
        "row_taxonomy": {k: {"assets": len(v["assets"]),
                              "dates": len(v["dates"]), "rows": v["rows"]}
                          for k, v in row_tax.items()},
        "product_only_inside": totals["product_only_inside"],
        "product_only_outside": totals["product_only_outside"],
        "product_only_no_trade": totals["product_only_no_trade"],
        "product_only_tradable": totals["product_only_tradable"],
        "product_only_rahavard_omission": totals["product_only_rahavard_omission"],
        "product_only_unverified": totals["product_only_unverified"],
        "type0_only_outside": totals["type0_only_outside"],
        "type0_only_no_trade": totals["type0_only_no_trade"],
        "type0_only_tradable": totals["type0_only_tradable"],
        "type0_only_rahavard_date": totals["type0_only_rahavard_date"],
        "type0_only_product_omission": totals["type0_only_product_omission"],
        "last_null": totals["last_null"],
        "type0_flat": totals["flat"],
        "type0_bad_geom": totals["bad_geom"],
        "type7_diff_rows": totals["type7_diff"],
        "close_official_diff": totals["close_official_diff"],
        "type0_vs_tsetmc": {
            "common": sem_tot["close_last_cmp"],
            "close_last_exact_pct": round(100.0 * sem_tot["close_last_exact"] /
                                          max(1, sem_tot["close_last_cmp"]), 4),
            "close_official_exact_pct": round(100.0 * sem_tot["close_official_exact"] /
                                             max(1, sem_tot["close_official_cmp"]), 4),
            "open_first_exact_pct": round(100.0 * sem_tot["open_first_exact"] /
                                          max(1, sem_tot["open_first_cmp"]), 4),
            "open_base_exact_pct": round(100.0 * sem_tot["open_base_exact"] /
                                         max(1, sem_tot["open_base_cmp"]), 4),
            "high_exact_pct": round(100.0 * sem_tot["high_exact"] /
                                    max(1, sem_tot["high_cmp"]), 4),
            "low_exact_pct": round(100.0 * sem_tot["low_exact"] /
                                   max(1, sem_tot["low_cmp"]), 4),
            "vol_exact_pct": round(100.0 * sem_tot["vol_exact"] /
                                   max(1, sem_tot["vol_cmp"]), 4),
            "flat": sem_tot["flat"], "bad_geom": sem_tot["bad_geom"],
        },
        "taxonomy": {k: {"assets": len(v["assets"]), "dates": len(v["dates"]),
                         "field_mismatches": v["fields"]} for k, v in tax.items()},
    }
    with open(os.path.join(ART, "rahavard-raw-ohlc-summary.json"), "w",
              encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    manifest = {
        "round": "ra365-r18-rahavard",
        "created_at": dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "sources": {
            "rahavard": {"file": REF_FILE, "sha256": fa_sha(REF_FILE),
                        "type": "type0 D (raw) and type7 D (adjusted)",
                        "frozen_at": "2026-10-20"},
            "product": {"file": PROD_FILE, "sha256": fa_sha(PROD_FILE),
                        "description": "actual BorsTerminal chart candles snapshot"},
            "tsetmc_oracle": {"db": DB, "sha256": fa_sha(DB),
                              "role": "independent field-semantic oracle, not a Rahavard substitute"},
            "cohort": {"file": COHORT, "sha256": fa_sha(COHORT)},
        },
        "definitions": {
            "open": "product open vs type0 open (first trade)",
            "high_raw": "product parser-stage high vs widen(type0 open,H,L,close)",
            "low_raw": "product parser-stage low vs widen(type0 open,H,L,close)",
            "last": "product last vs type0 close; type0 close=LAST proven vs TSETMC",
            "close_display": "product displayed close vs type0 close (basis-aware)",
            "volume": "product volume vs type0 volume",
        },
        "summary": summary,
        "artifacts": {},
    }
    for name in ("rahavard-raw-ohlc-parity.csv",
                 "rahavard-type0-vs-tsetmc.csv",
                 "rahavard-raw-ohlc-missing.csv",
                 "rahavard-raw-ohlc-field-mismatches.csv",
                 "rahavard-raw-ohlc-taxonomy.csv",
                 "rahavard-raw-ohlc-row-taxonomy.csv",
                 "rahavard-raw-ohlc-summary.json"):
        p = os.path.join(ART, name)
        manifest["artifacts"][name] = {"sha256": fa_sha(p),
                                       "bytes": os.path.getsize(p)}
    with open(os.path.join(ART, "rahavard-raw-ohlc-cohort-manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
