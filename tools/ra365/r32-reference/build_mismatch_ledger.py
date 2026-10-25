#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every unmatched paired date, keyed so it can be looked up one row at a time.

The key is the one the round fixed:

    symbol_id | timeframe | date | price_basis

and each record carries both sides' fields, the per-field difference, the raw
values behind them, the effective ratios, whatever event evidence exists, the
source version on each side, and the cause the evidence supports.

Nothing is dropped from the denominator.  A paired date that passes is counted
as passing; a date that fails is written to the ledger; a date present on only
one side is written as a coverage record.  The ledger never removes a row to
raise a percentage.

`--mode disposition` reconciles the frozen 413,365-row mismatch count against
the families R30 recorded, naming the overlaps between R31's categories instead
of assuming they partition the set.

Usage
  python build_mismatch_ledger.py --mode ledger \
      --in _audit/RA365-PARITY-DIVERGE-2026-10-12.csv --kind parity-diverge --out <dir>
  python build_mismatch_ledger.py --mode disposition \
      --families artifacts/ra365/r30/attribution/families.csv --out <dir>
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import r32_evidence as EV  # noqa: E402
import r32_io as IO  # noqa: E402
import r32_schema as S  # noqa: E402

FIELDS = ("o", "h", "l", "c")

#: Contract tolerance (R26 parity contract, sections 3-2 and 4).
TOL_ABS = 0.5
TOL_REL = 1e-6
TICK = 1.0

#: The nearest R31 bucket, as a hint only: splitting a ratio gap into
#: base-gap / unproven-gap / dps / combined needs event evidence that these
#: frozen ledgers do not carry.
CAUSE_TO_R31 = {
    "rounding": "precision",
    "close_definition": "field-definition",
    "adjust_ratio": "ratio-gap",
    "raw_or_revision": "raw-revision",
    "missing_bar": "coverage",
    "unattributed": "unattributed",
}


def passes(prod, ref):
    """True when every compared field is inside the frozen tolerance."""
    for f in FIELDS:
        p, r = prod.get(f), ref.get(f)
        if p is None or r is None:
            return False, "field %s missing on one side" % f
        if abs(p - r) > max(TOL_ABS, TOL_REL * abs(r)):
            return False, "field %s outside tolerance" % f
    return True, ""


def cause_for(pair, prod, ref, diffs):
    """Name what the evidence supports - never a verdict about the market."""
    missing = [f for f in FIELDS if prod.get(f) is None or ref.get(f) is None]
    if missing:
        return "missing_bar", "field(s) %s absent on one side" % ",".join(missing)
    max_abs = max(d["abs"] for d in diffs.values())
    if max_abs <= TICK:
        return "rounding", "every field differs by at most one price unit (%.4g)" % max_abs
    close_only = all(d["pass"] for f, d in diffs.items() if f != "c") and not diffs["c"]["pass"]
    if close_only:
        return ("close_definition",
                "open/high/low agree; only close differs, so the two sides use a different "
                "close definition or a different session's close")
    raw = pair.get("prod_raw") or {}
    for side, raw_val in raw.items():
        if raw_val is None:
            continue
        for f in FIELDS:
            if ref.get(f) is not None and abs(raw_val - ref[f]) <= max(TOL_ABS, TOL_REL * abs(ref[f])):
                return ("raw_or_revision",
                        "the product's %s raw value equals the reference within tolerance while "
                        "the displayed value does not: a raw/adjusted or revision difference, "
                        "not a factor" % side)
    ratios = {f: (ref[f] / prod[f]) for f in FIELDS if prod.get(f) and ref.get(f)}
    if len(ratios) >= 2:
        vals = sorted(ratios.values())
        spread = (vals[-1] - vals[0]) / vals[0] if vals[0] else 0.0
        if spread <= 5e-4:
            return ("adjust_ratio",
                    "one effective ratio (%.8g) explains every field, and it is not 1: an "
                    "adjustment or base-price difference" % vals[len(vals) // 2])
        return ("unattributed",
                "fields disagree on the ratio (spread %.3g): the evidence does not name a cause"
                % spread)
    return "unattributed", "not enough fields to form a ratio"


def ledger_row(pair):
    prod = pair.get("prod") or {}
    ref = pair.get("ref") or {}
    diffs = {}
    for f in FIELDS:
        p, r = prod.get(f), ref.get(f)
        if p is None or r is None:
            diffs[f] = {"abs": None, "rel": None, "pass": False}
            continue
        ok = abs(p - r) <= max(TOL_ABS, TOL_REL * abs(r))
        diffs[f] = {"abs": round(abs(p - r), 6),
                    "rel": None if not r else round(abs(p - r) / abs(r), 12),
                    "pass": ok}
    ok, why = passes(prod, ref)
    basis = pair.get("basis") or "unknown"
    cause, evidence = cause_for(pair, prod, ref, diffs)
    ratios = {f: (round(ref[f] / prod[f], 12) if prod.get(f) and ref.get(f) else None)
              for f in FIELDS}
    return {
        "schema": S.SCHEMA_MISMATCH,
        "key": S.mismatch_key(pair["symbol_id"], pair["timeframe"], pair["date"], basis),
        "symbol_id": pair["symbol_id"],
        "symbol": pair["symbol"],
        "timeframe": pair["timeframe"],
        "date": pair["date"],
        "price_basis": basis,
        "adjust": pair.get("adjust") or "unknown",
        "arm": pair.get("arm"),
        "passes_contract": ok,
        "fail_reason": why,
        "prod": prod,
        "prod_raw": pair.get("prod_raw"),
        "ref": ref,
        "diff": diffs,
        "max_rel_diff": max((d["rel"] for d in diffs.values() if d["rel"] is not None), default=None),
        "effective_ratio_ref_over_prod": ratios,
        "event_evidence": pair.get("event") or [],
        "source_versions": {"ref": pair.get("source_ref"), "prod": pair.get("source_prod")},
        "cause": cause,
        "cause_evidence": evidence,
        "class_r31_hint": CAUSE_TO_R31.get(cause, "unattributed"),
        "provenance_rel_err": pair.get("proven_rel_err"),
    }


def build_ledger(pairs, out_dir, prefiltered=False, generated_at=None):
    rows, coverage = [], []
    stats = Counter()
    for pair in pairs:
        rec = ledger_row(pair)
        prod_null = all((pair.get("prod") or {}).get(f) is None for f in FIELDS)
        ref_null = all((pair.get("ref") or {}).get(f) is None for f in FIELDS)
        if prod_null or ref_null:
            coverage.append({"key": rec["key"], "date": rec["date"],
                             "side": "product" if prod_null else "reference"})
            stats["coverage_one_side"] += 1
        if rec["passes_contract"]:
            stats["pass"] += 1
        else:
            stats["fail"] += 1
            stats["cause:" + rec["cause"]] += 1
            rows.append(rec)
    path = os.path.join(out_dir, "mismatch_map.ndjson.gz")
    n = IO.write_ndjson_gz(path, rows)
    total = stats["pass"] + stats["fail"]
    notes = [
        "No row is removed from the denominator; passing rows are counted, not dropped.",
        "class_r31_hint is the nearest R31 bucket, not a ruling: splitting a ratio gap "
        "into base-gap / unproven-gap / dps / combined needs event evidence the frozen "
        "ledgers do not carry.",
    ]
    if prefiltered:
        notes.insert(1, "The input is a divergence ledger that already contains only the "
                        "rows that failed, so pass=0 is a property of the input, not a parity "
                        "measurement. Feed a full paired export to get a real pass rate.")
    summary = {
        "schema": S.SCHEMA_MISMATCH,
        "generated_at": generated_at or S.now_utc(),
        "key": "symbol_id|timeframe|date|price_basis",
        "input_prefiltered": prefiltered,
        "denominator": {
            "paired_compared": total,
            "pass": stats["pass"],
            "fail": stats["fail"],
            "pass_pct": round(100.0 * stats["pass"] / total, 4) if total else None,
            "coverage_one_side": stats["coverage_one_side"],
            "removed_from_denominator": 0,
        },
        "causes": {k.split(":", 1)[1]: v for k, v in sorted(stats.items())
                   if k.startswith("cause:")},
        "class_r31_hint": _hint_counts(rows),
        "by_basis": _group_counts(rows),
        "contract": {"price_abs": TOL_ABS, "price_rel": TOL_REL, "tick": TICK},
        "file": IO.file_entry(path, S.SCHEMA_MISMATCH, rows=n, rel="mismatch_map.ndjson.gz"),
        "notes": notes,
    }
    IO.write_json(os.path.join(out_dir, "mismatch-summary.json"), summary)
    return summary


def _hint_counts(rows):
    c = Counter(r["class_r31_hint"] for r in rows)
    return dict(sorted(c.items(), key=lambda kv: -kv[1]))


def _group_counts(rows):
    out = defaultdict(lambda: Counter())
    for r in rows:
        out["%s|%s" % (r["adjust"], r["price_basis"])][r["cause"]] += 1
    return {k: dict(sorted(v.items(), key=lambda kv: -kv[1])) for k, v in out.items()}


# --------------------------------------------------------------------------
# disposition: reconcile the frozen 413,365 against the R30 families
# --------------------------------------------------------------------------

FROZEN_TOTAL = {
    "r31_D_tolerance_mismatch": 413365,
    "r31_D_paired": 1194446,
    "r31_D_pass": 781081,
    "r30_failing": 491438,
    "r30_recovered": 74483,
    "r31_ref_only_D": 35826,
    "r31_product_only_D": 939725,
}

#: R31's prose categories and the step classes they live in.
R31_CATEGORY_OVERLAP = [
    ("base-gap", "RATIO_DIFF", "a base-price discontinuity the product records as a step"),
    ("unproven-gap", "RATIO_DIFF", "a step with no official row behind it"),
    ("reference-only", "REF_ONLY", "a step the reference has and the product does not; also a "
                                   "coverage bucket, so the two uses must not be summed"),
    ("product-only", "EXTRA", "a step the product has and the reference does not"),
    ("dps-fund-precision", "RATIO_DIFF", "same event, different amount; sub-tolerance-scale"),
    ("combined", "RATIO_DIFF", "share + DPS or base + DPS at one boundary; overlaps the legs"),
    ("raw-revision", "raw", "product TSETMC vs reference Rahavard raw history; not a factor"),
]


def disposition(families_path, out_dir, generated_at=None):
    """Partition the frozen failure count by family and name the overlaps."""
    rows = EV.read_csv(families_path)
    by_class = defaultdict(lambda: Counter())
    by_sig = defaultdict(lambda: Counter())
    total_affected = total_attributed = total_recovered = 0
    for r in rows:
        cls = r.get("class")
        sig = r.get("event_sig")
        steps = int(float(r.get("steps") or 0))
        affected = int(float(r.get("affected") or 0))
        attributed = int(float(r.get("attributed") or 0))
        recovered = int(float(r.get("recovered") or 0))
        by_class[cls]["steps"] += steps
        by_class[cls]["affected"] += affected
        by_class[cls]["attributed"] += attributed
        by_class[cls]["recovered"] += recovered
        by_sig[sig]["steps"] += steps
        by_sig[sig]["recovered"] += recovered
        total_affected += affected
        total_attributed += attributed
        total_recovered += recovered

    recovered_by_sig = {k: v["recovered"] for k, v in sorted(by_sig.items(),
                                                             key=lambda kv: -kv[1]["recovered"])}
    out = {
        "generated_at": generated_at or S.now_utc(),
        "frozen": FROZEN_TOTAL,
        "r30_families": {
            "families": len(rows),
            "affected_rows_sum": total_affected,
            "attributed_rows_sum": total_attributed,
            "recovered_rows_sum": total_recovered,
            "note": "affected is counted per step, so one failing row appears under every step "
                    "above it; these sums are an upper bound and must not be added to the "
                    "413,365 denominator",
        },
        "by_class": {k: dict(v) for k, v in sorted(by_class.items())},
        "recovered_by_event_signature": recovered_by_sig,
        "category_overlap": [
            {"category": c, "lives_in_class": cl, "meaning": m}
            for c, cl, m in R31_CATEGORY_OVERLAP
        ],
        "overlaps_found": _overlap_findings(rows),
        "disposition": _disposition_rows(by_sig),
        "reconciliation": {
            "r31_mismatch": FROZEN_TOTAL["r31_D_tolerance_mismatch"],
            "explained_by_r30_attribution_recovered": total_recovered,
            "remaining_after_r30_recovery": FROZEN_TOTAL["r31_D_tolerance_mismatch"] - total_recovered,
            "note": "R30's recovered count is the one-step counterfactual on the earlier "
                    "baseline (491,438 failing); R31 moved the baseline to 413,365 by fixing "
                    "the visible high/low. The two are not the same denominator, so the "
                    "difference is reported, not reconciled away.",
        },
    }
    IO.write_json(os.path.join(out_dir, "mismatch-disposition.json"), out)
    return out


def _overlap_findings(rows):
    """Categories that share a class, i.e. cannot be summed as if disjoint."""
    by_class = defaultdict(set)
    for r in rows:
        by_class[r.get("class")].add(r.get("event_sig"))
    findings = []
    for cls, sigs in sorted(by_class.items()):
        if len(sigs) > 1:
            findings.append({
                "class": cls,
                "event_signatures": sorted(sigs),
                "finding": "one class spans %d signatures; a row can satisfy several, so the "
                           "signatures are views of the same rows, not a partition" % len(sigs),
            })
    findings.append({
        "class": "REF_ONLY vs reference-only coverage",
        "event_signatures": ["no_event"],
        "finding": "R31 uses 'reference-only' both for a step class and for a coverage bucket "
                   "(35,826 D bars); the two counts describe different objects and must not be "
                   "added",
    })
    findings.append({
        "class": "raw-revision vs dps-fund-precision",
        "event_signatures": ["-"],
        "finding": "both land in the <0.01% bucket once the amount difference is small, so the "
                   "error bucket alone cannot separate them; the cause field in the ledger is "
                   "what separates them",
    })
    return findings


def _disposition_rows(by_sig):
    needs_evidence = {"base_gap", "unproven_gap", "no_event"}
    rows = []
    for sig, c in sorted(by_sig.items(), key=lambda kv: -kv[1]["recovered"]):
        if sig in needs_evidence:
            verdict = "needs an official ratio/S row or the owner's ruling; the ledger marks it unattributed"
        elif sig == "fund_dps":
            verdict = "needs the fund's declared DPS; the amount differs by 0.5-2.6%"
        elif sig in ("dps", "share", "pa"):
            verdict = "product has the event; the amount or the base candle differs"
        else:
            verdict = "combined legs; needs the official components"
        rows.append({"event_sig": sig, "steps": c["steps"], "recovered": c["recovered"],
                     "disposition": verdict})
    return rows


def main():
    ap = argparse.ArgumentParser(description="Build the R32 mismatch ledger.")
    ap.add_argument("--mode", default="ledger", choices=("ledger", "disposition"))
    ap.add_argument("--in", dest="in_path", default=None)
    ap.add_argument("--kind", default="parity-diverge", choices=("parity-diverge", "candle-diverge"))
    ap.add_argument("--pairs", default=None)
    ap.add_argument("--families", default=None)
    ap.add_argument("--prefiltered", action="store_true",
                    help="the input already contains only failing rows (a divergence ledger)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--generated-at", default=None)
    a = ap.parse_args()

    if a.mode == "disposition":
        if not a.families:
            print("--families is required in disposition mode")
            return 2
        out = disposition(a.families, a.out, a.generated_at)
        print("disposition written: r30 recovered=%d  r31 mismatch=%d"
              % (out["r30_families"]["recovered_rows_sum"],
                 out["frozen"]["r31_D_tolerance_mismatch"]))
        return 0

    if a.pairs:
        reader = IO.read_ndjson_gz if str(a.pairs).endswith(".gz") else IO.read_ndjson
        pairs = list(reader(a.pairs))
    elif a.in_path:
        pairs = (EV.pairs_from_parity_diverge(a.in_path) if a.kind == "parity-diverge"
                 else EV.pairs_from_candle_diverge(a.in_path))
    else:
        print("pass --pairs or --in")
        return 2
    summary = build_ledger(pairs, a.out, prefiltered=a.prefiltered, generated_at=a.generated_at)
    d = summary["denominator"]
    print("ledger: compared=%d pass=%d fail=%d (pass %.4f%%)  removed=%d"
          % (d["paired_compared"], d["pass"], d["fail"], d["pass_pct"] or 0,
             d["removed_from_denominator"]))
    print("causes: %r" % (summary["causes"],))
    return 0


if __name__ == "__main__":
    sys.exit(main())