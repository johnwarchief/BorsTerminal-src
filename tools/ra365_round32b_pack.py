#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a versioned RA365 correction pack from the Round 32B audit CSVs.

The pack is deliberately *not* a copy of the reference series.  It contains:

  * event-level factor segments: one `replace_step` or `suppress_step` per
    effective date, with the target step ratio derived from the frozen
    reference factor (type7/type0) and verified against all four OHLC fields;
  * sparse per-field raw corrections for the dates where the product's raw
    candle differs from the reference type0 bar.

Both files carry the reference SHA-256, the correction version, the creation
time, the source/method and the per-row confidence.  The engine can therefore
apply, audit and reproduce every correction.

Usage:
  python tools/ra365_round32b_pack.py --audit-dir D:/.../audit_code \
      --out data/ra365_corrections/ra365-r32b-v1 --version ra365-r32b-v1
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_factor_rows(path):
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            ins = str(r.get("ins_code") or "").strip()
            date = str(r.get("effective_date") or "").strip()[:10]
            action = str(r.get("action") or "").strip()
            if not ins or not date or action not in ("replace_step", "suppress_step"):
                continue
            target = _float(r.get("target_ratio"))
            if action == "replace_step" and (target is None or target <= 0):
                continue
            rows.append({
                "ins_code": ins,
                "asset_id": r.get("asset_id") or "",
                "symbol": r.get("symbol") or "",
                "action": action,
                "effective_date": date,
                "ratio": target,
                "class": r.get("class") or "",
                "prod_date": r.get("prod_date") or "",
                "ref_date": r.get("ref_date") or "",
                "prod_ratio": _float(r.get("prod_ratio")),
                "ref_ratio": _float(r.get("ref_ratio")),
                "event_sig": r.get("event_sig") or "",
                "err_bucket": r.get("err_bucket") or "",
                "fields_used": r.get("fields_used") or "",
                "samples": _int(r.get("samples")),
                "max_field_dev": _float(r.get("max_field_dev")),
                "confidence": r.get("confidence") or "",
                "source": r.get("source") or "",
                "method": r.get("method") or "",
                "ref_bars_sha256": r.get("ref_bars_sha256") or "",
                "correction_version": r.get("correction_version") or "",
                "created_at": r.get("created_at") or "",
                "reason": r.get("reason") or "",
            })
    return rows


def read_raw_rows(path):
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            ins = str(r.get("ins_code") or "").strip()
            date = str(r.get("date") or "").strip()[:10]
            field = str(r.get("field") or "").strip()
            value = _float(r.get("reference_value"))
            if not ins or not date or not field or value is None:
                continue
            rows.append({
                "ins_code": ins,
                "asset_id": r.get("asset_id") or "",
                "symbol": r.get("symbol") or "",
                "date": date,
                "field": field,
                "value": value,
                "product_value": _float(r.get("product_value")),
                "abs_diff": _float(r.get("abs_diff")),
                "source": r.get("source") or "",
                "method": r.get("method") or "",
                "confidence": r.get("confidence") or "",
                "ref_bars_sha256": r.get("ref_bars_sha256") or "",
                "correction_version": r.get("correction_version") or "",
                "created_at": r.get("created_at") or "",
                "reason": r.get("reason") or "",
            })
    return rows


def dedupe_factors(rows):
    """One row per (ins_code, action, date); multiple replaces multiply.

    A reference factor date is one step.  If the audit emitted more than one
    replacement for the same date (e.g. several matched sub-steps), the target
    is the product of their ratios.  `suppress_step` on a date that also has a
    replacement is redundant and dropped.
    """
    out = {}
    merged = Counter()
    for r in rows:
        key = (r["ins_code"], r["action"], r["effective_date"])
        cur = out.get(key)
        if cur is None:
            out[key] = dict(r)
            continue
        merged[r["action"]] += 1
        if r["action"] == "replace_step":
            cur["ratio"] = (cur["ratio"] or 1.0) * r["ratio"]
            cur["class"] = "+".join(sorted(set(
                x for x in (cur.get("class"), r.get("class")) if x)))
            cur["reason"] = cur.get("reason") or r.get("reason")
            cur["prod_ratio"] = cur.get("prod_ratio")
            cur["ref_ratio"] = cur.get("ref_ratio")
    replace_dates = {(r["ins_code"], r["effective_date"])
                     for r in out.values() if r["action"] == "replace_step"}
    for key in list(out):
        ins, action, date = key
        if action == "suppress_step" and (ins, date) in replace_dates:
            del out[key]
    return sorted(out.values(), key=lambda r: (r["ins_code"], r["effective_date"],
                                               r["action"])), merged


def dedupe_raw(rows):
    out = {}
    conflicts = Counter()
    for r in rows:
        key = (r["ins_code"], r["date"], r["field"])
        if key in out and out[key]["value"] != r["value"]:
            conflicts[r["field"]] += 1
        out[key] = r
    return sorted(out.values(), key=lambda r: (r["ins_code"], r["date"], r["field"])), conflicts


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--version", default="ra365-r32b-v1")
    ap.add_argument("--created-at", default="")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    created_at = a.created_at or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    factors = read_factor_rows(os.path.join(a.audit_dir, "factor_corrections.csv"))
    raws = read_raw_rows(os.path.join(a.audit_dir, "raw_corrections.csv"))
    factors, merged = dedupe_factors(factors)
    raws, conflicts = dedupe_raw(raws)

    ref_sha = ""
    for r in factors:
        if r.get("ref_bars_sha256"):
            ref_sha = r["ref_bars_sha256"]
            break
    if not ref_sha:
        for r in raws:
            if r.get("ref_bars_sha256"):
                ref_sha = r["ref_bars_sha256"]
                break

    for r in factors:
        r["correction_version"] = a.version
        if not r.get("created_at"):
            r["created_at"] = created_at
        if not r.get("ref_bars_sha256"):
            r["ref_bars_sha256"] = ref_sha
    for r in raws:
        r["correction_version"] = a.version
        if not r.get("created_at"):
            r["created_at"] = created_at
        if not r.get("ref_bars_sha256"):
            r["ref_bars_sha256"] = ref_sha

    factors_path = os.path.join(a.out, "factors.jsonl")
    raws_path = os.path.join(a.out, "raw_ohlc.jsonl")
    write_jsonl(factors_path, factors)
    write_jsonl(raws_path, raws)

    counts = Counter()
    for r in factors:
        counts[r["action"]] += 1
    raw_counts = Counter(r["field"] for r in raws)
    by_symbol = Counter()
    by_asset = Counter()
    for r in factors:
        by_symbol[r["symbol"]] += 1
        by_asset[r["ins_code"]] += 1
    dup_symbols = {s: c for s, c in by_symbol.items() if c and sum(
        1 for x in factors if x["symbol"] == s and x["action"] == "replace_step") > 0}
    manifest = {
        "schema": "ra365-correction-pack-v1",
        "correction_version": a.version,
        "created_at": created_at,
        "tool": "tools/ra365_round32b_pack.py",
        "reference_sha256": ref_sha,
        "files": {
            "factors": "factors.jsonl",
            "raw_ohlc": "raw_ohlc.jsonl",
        },
        "file_sha256": {
            "factors": sha256(factors_path),
            "raw_ohlc": sha256(raws_path),
        },
        "counts": {
            "factor_replace_step": counts["replace_step"],
            "factor_suppress_step": counts["suppress_step"],
            "raw_fields": dict(raw_counts),
            "factor_assets": len(by_asset),
            "factor_symbols": len(by_symbol),
        },
        "dedupe": {"factor_merged": dict(merged), "raw_conflicts": dict(conflicts)},
        "semantics": {
            "replace_step": ("suppress every product event on effective_date and insert one "
                             "step with ratio; ratio is the reference-implied step"),
            "suppress_step": "suppress every product event on effective_date",
            "raw_ohlc": ("per-field historical display value from the frozen reference "
                         "type0 bar; never rewrites corporate events"),
        },
        "source": "rahavard_reference_frozen_v2 (owner-authenticated snapshot)",
        "usage": ("Derived factor segments and sparse per-field values only; no bulk raw "
                  "series redistribution."),
    }
    json.dump(manifest, open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps({"out": a.out, "manifest": manifest}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
