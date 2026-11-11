#!/usr/bin/env python3
"""Recover the baseline-unverified 1,358 step set from the pack + ledger.

The committed step ledger does not carry the pack `validity` column; the pack
does. stage03 writes ledger rows in exactly `load_steps()` order (factors.jsonl,
then manifest dropped_steps), so validity is attached by row index after proving
the 1:1 identity on (symbol, effective_date, ratio).
"""
import csv
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACK = os.path.join(ROOT, "data", "ra365_corrections",
                    "ra365-phase49-rebuild-full-v2")
LEDGER = os.path.join(ROOT, "_audit", "phase49-full-verification", "ledgers",
                      "ADJUSTMENT-EVIDENCE-LEDGER.csv")
OUT = os.path.join(ROOT, "_audit", "phase49-2", "evidence",
                   "baseline-unverified-steps.json")


def load_steps(pack):
    """Mirror of stage03_step_ledger.load_steps (same order, same fields)."""
    out = []
    with open(os.path.join(pack, "factors.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    manifest = json.load(open(os.path.join(pack, "manifest.json"), encoding="utf-8"))
    for raw in manifest.get("dropped_steps", []):
        r = dict(raw)
        r["validity"] = "invalid_dropped"
        r["effective_date"] = r.get("date")
        r["ratio"] = r.get("our_ratio")
        out.append(r)
    return out


def _num(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def main():
    steps = load_steps(PACK)
    rows = list(csv.DictReader(open(LEDGER, encoding="utf-8", newline="")))
    if len(steps) != len(rows):
        raise SystemExit("rows %d != steps %d" % (len(rows), len(steps)))

    identity_mismatch = []
    for i, (s, r) in enumerate(zip(steps, rows)):
        if str(s.get("symbol") or "") != str(r.get("symbol") or ""):
            identity_mismatch.append((i, "symbol", s.get("symbol"), r.get("symbol")))
        if str(s.get("effective_date") or "")[:10] != str(r.get("effective_date") or ""):
            identity_mismatch.append((i, "date", s.get("effective_date"),
                                      r.get("effective_date")))
        a, b = _num(s.get("ratio")), _num(r.get("ratio"))
        if a is None or b is None or abs(a - b) > 1e-12:
            identity_mismatch.append((i, "ratio", s.get("ratio"), r.get("ratio")))
        if len(identity_mismatch) > 10:
            break
    if identity_mismatch:
        raise SystemExit("pack/ledger index identity failed: %r" % (identity_mismatch,))

    by_validity = Counter(str(s.get("validity")) for s in steps)
    expected = {"verified": 622, "reconstructed_verified": 6300,
                "unverified": 1358, "invalid_dropped": 28}
    if dict(by_validity) != expected:
        raise SystemExit("pack validity %r != %r"
                         % (dict(by_validity), expected))

    subset = []
    for s, r in zip(steps, rows):
        if str(s.get("validity")) != "unverified":
            continue
        subset.append({
            "index": len(subset),
            "symbol": r["symbol"], "ins_code": r["ins_code"],
            "asset_id": r["asset_id"], "effective_date": r["effective_date"],
            "action": r["action"], "ratio": r["ratio"],
            "ref_ratio": r["ref_ratio"], "prod_ratio": r["prod_ratio"],
            "final_status": r["final_status"], "evidence_tier": r["evidence_tier"],
            "method": r["method"], "comparison_result": r["comparison_result"],
            "discrepancy_cause": r["discrepancy_cause"],
            "evidence_ref": r["evidence_ref"], "notes": r["notes"],
        })
    if len(subset) != 1358:
        raise SystemExit("subset %d != 1358" % len(subset))

    status = Counter(r["final_status"] for r in subset)
    unverified_statuses = ("INSUFFICIENT_EVIDENCE", "CONFLICT_RATIO",
                           "CONFLICT_DUPLICATE", "PARTIAL_REFERENCE",
                           "PARTIAL_OFFICIAL", "RECONSTRUCTED_AUDITED")
    still = sum(v for k, v in status.items() if k in unverified_statuses)
    became = sum(v for k, v in status.items() if k.startswith("VERIFIED_"))
    if still != 1179 or became != 179:
        raise SystemExit("split %d+%d != 1179+179" % (still, became))

    symbols = Counter(r["symbol"] for r in subset)
    out = {
        "schema": "phase49-2-baseline-unverified-steps-v1",
        "pack": os.path.relpath(PACK, ROOT).replace("\\", "/"),
        "ledger": os.path.relpath(LEDGER, ROOT).replace("\\", "/"),
        "pack_validity_counts": dict(sorted(by_validity.items())),
        "subset_rows": len(subset),
        "subset_status": dict(sorted(status.items())),
        "still_unverified": still,
        "became_verified": became,
        "became_verified_split": {
            "VERIFIED_MULTI_SOURCE": status.get("VERIFIED_MULTI_SOURCE", 0),
            "VERIFIED_OFFICIAL": status.get("VERIFIED_OFFICIAL", 0),
            "VERIFIED_REFERENCE": status.get("VERIFIED_REFERENCE", 0),
        },
        "subset_symbols": len(symbols),
        "rows": subset,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(json.dumps({k: v for k, v in out.items() if k != "rows"},
                     ensure_ascii=False, indent=1))
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
