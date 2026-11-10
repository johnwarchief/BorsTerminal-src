#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage D: merge captured type0/type7 reference steps into the Rebuild pack.

Reference step semantics: q = type7.close / type0.close is a cumulative factor
that steps DOWN at an event date; our chain uses factor(t) = prod(ratio for
date > t), so the reference-implied price ratio is 1 / ref_step_ratio.

Decisions per symbol:
  * matching date (+-3 days): keep the pack ratio when it agrees within 1e-6,
    otherwise adopt the reference-implied ratio and record both;
  * reference step with no counterpart: insert it (verified);
  * our step with no reference step: keep it, mark unverified, report it;
  * symbols outside the capture: copy with validity by provenance.
"""
import argparse
import collections
import csv
import gzip
import hashlib
import importlib.util
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.join(ROOT, "_audit", "phase49-finalization", "packs", "rebuild-full-v1")
OUT = os.path.join(ROOT, "_audit", "phase49-finalization", "packs", "rebuild-full-v2")
EVID = os.path.join(ROOT, "_audit", "phase49-finalization", "evidence")
VERSION = "ra365-phase49-rebuild-full-v2"
REF_SHA_30 = "ab3b6a938684b088f4c01d7139ce3822118ecaf518bcdc8f61d40fe5d9912c7a"
REF_SHA_7 = "c2a3d253b27bcc41a541c23d51402c04e89476e8b9e13e68871e07bb9b63db65"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def load_parity_module():
    path = os.path.join(ROOT, "_audit", "phase49-finalization",
                        "stageC_reference_parity.py")
    spec = importlib.util.spec_from_file_location("pcr", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_group(norm_dir):
    pcr = load_parity_module()
    raw, adj = pcr.load_ref(os.path.join(norm_dir, "bars.ndjson.gz"))
    out = {}
    for sym in sorted(set(raw) | set(adj)):
        steps, levels = pcr.ref_regimes(sorted(set(raw.get(sym, {})) & set(adj.get(sym, {}))),
                                        raw.get(sym, {}), adj.get(sym, {}))
        ds = set(raw.get(sym, {})) | set(adj.get(sym, {}))
        out[sym] = {"steps": steps, "levels": levels,
                    "first": min(ds) if ds else None,
                    "last": max(ds) if ds else None}
    return out


def load_pack_steps():
    by = collections.defaultdict(list)
    for line in open(os.path.join(BASE, "factors.jsonl"), encoding="utf-8"):
        line = line.strip()
        if line:
            r = json.loads(line)
            by[r["symbol"]].append(r)
    return by


def days(a, b):
    return abs((__import__("datetime").date.fromisoformat(a) -
                __import__("datetime").date.fromisoformat(b)).days)


def merge_symbol(sym, steps, ref, decisions):
    if not ref:
        out = []
        for s in steps:
            row = dict(s)
            if row.get("prov_kind") == "pack":
                row["validity"] = "reconstructed_verified"
            else:
                row["validity"] = "unverified"
            row["correction_version"] = VERSION
            out.append(row)
        cum = 1.0
        for s in reversed(out):
            s["cum_factor_after"] = round(cum, 15)
            cum *= float(s["ratio"])
        return out
    ref_steps = ref.get("steps", [])
    ref_dates = [s["date"] for s in ref_steps]
    used = set()
    out = []
    for rs in ref_steps:
        rr = 1.0 / float(rs["ratio"])
        best = None
        for i, s in enumerate(steps):
            if i in used:
                continue
            d = days(s["effective_date"], rs["date"])
            if d <= 3 and (best is None or d < best[0]):
                best = (d, i)
        if best is None:
            row = {
                "action": "replace_step", "effective_date": rs["date"],
                "symbol": sym,
                "ratio": rr,
                "class": "REFERENCE",
                "source": "rahavard-type7-type0",
                "method": "reference-factor-step-v1",
                "confidence": "reference-verified",
                "ref_ratio": rr,
                "ref_level_before": rs["level_before"],
                "ref_level_after": rs["level_after"],
                "event_sig": "reference-step",
                "correction_version": VERSION,
                "created_at": "2026-11-10",
                "reason": "reference factor step missing from product/pack",
                "prov_kind": "reference",
                "validity": "verified",
            }
            decisions.append({"symbol": sym, "date": rs["date"], "decision": "insert-reference",
                              "ref_ratio": rr, "our_ratio": None})
        else:
            used.add(best[1])
            s = steps[best[1]]
            our = float(s["ratio"])
            rel = abs(our / rr - 1.0)
            keep_our = rel <= 1e-6 or s.get("prov_kind") == "pack" and rel <= 1e-6
            row = dict(s)
            row["ref_ratio"] = rr
            row["ref_level_before"] = rs["level_before"]
            row["ref_level_after"] = rs["level_after"]
            row["ref_date"] = rs["date"]
            row["validity"] = "verified" if rel <= 1e-3 else "verified"
            if best[0]:
                row["date_shifted_from"] = s["effective_date"]
                row["effective_date"] = rs["date"]
            if not keep_our:
                row["ratio"] = rr
                row["source"] = "rahavard-type7-type0"
                row["method"] = "reference-factor-step-v1"
                row["reason"] = ("product ratio replaced by reference-implied ratio "
                                 "(was %.12g, rel diff %.4g)" % (our, rel))
                decisions.append({"symbol": sym, "date": rs["date"],
                                  "decision": "replace-ratio", "ref_ratio": rr,
                                  "our_ratio": our, "rel": rel,
                                  "shift_days": best[0]})
            else:
                row["reason"] = s.get("reason") or "pack step confirmed by reference"
                decisions.append({"symbol": sym, "date": rs["date"],
                                  "decision": "confirm", "ref_ratio": rr,
                                  "our_ratio": our, "rel": rel,
                                  "shift_days": best[0]})
        row["correction_version"] = VERSION
        out.append(row)
    for i, s in enumerate(steps):
        if i in used:
            continue
        d = s["effective_date"]
        inside = ref.get("first") and ref.get("last") and ref["first"] <= d <= ref["last"]
        ratio = float(s["ratio"])
        if inside and abs(ratio - 1.0) > 0.001:
            # reference covers this date and shows no step: a material product
            # step here is contradicted by independent evidence -> invalid.
            decisions.append({"symbol": sym, "date": d,
                              "decision": "drop-contradicted", "ref_ratio": None,
                              "our_ratio": ratio})
            continue
        row = dict(s)
        row["validity"] = "unverified"
        row["reason"] = ((s.get("reason") or "")
                         + (" | tiny step below reference detection" if inside
                            else " | outside reference coverage"))
        row["correction_version"] = VERSION
        out.append(row)
        decisions.append({"symbol": sym, "date": d,
                          "decision": "keep-tiny-extra" if inside else "keep-outside-reference",
                          "ref_ratio": None, "our_ratio": ratio})
    out.sort(key=lambda r: r["effective_date"])
    cum = 1.0
    for s in reversed(out):
        s["cum_factor_after"] = round(cum, 15)
        cum *= float(s["ratio"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", action="append", required=True,
                    help="name:normalized_dir:bars_sha256")
    ap.add_argument("--group", required=True)
    args = ap.parse_args()
    ref, ref_shas, groups = {}, [], []
    for spec in args.capture:
        name, path, sha = spec.split(":", 2)
        groups.append(name)
        ref_shas.append(sha)
        for sym, rec in load_group(path).items():
            ref[sym] = rec
    base = load_pack_steps()
    decisions, per_symbol = [], {}
    factors = []
    symbols = sorted(set(base) | set(ref))
    for sym in symbols:
        steps = base.get(sym, [])
        merged = merge_symbol(sym, steps, ref.get(sym), decisions)
        if not merged:
            continue
        for s in merged:
            factors.append(json.dumps(s, ensure_ascii=False, sort_keys=True))
        per_symbol[sym] = {
            "steps": len(merged),
            "verified": sum(1 for s in merged if s.get("validity") == "verified"),
            "reconstructed_verified": sum(
                1 for s in merged if s.get("validity") == "reconstructed_verified"),
            "unverified": sum(1 for s in merged if s.get("validity") == "unverified"),
            "pre2020": sum(1 for s in merged if s["effective_date"] < "2020-01-01"),
        }
    os.makedirs(OUT, exist_ok=True)
    fp = os.path.join(OUT, "factors.jsonl")
    with open(fp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(factors) + "\n")
    raw_src = os.path.join(BASE, "raw_ohlc.jsonl")
    rp = os.path.join(OUT, "raw_ohlc.jsonl")
    with open(raw_src, encoding="utf-8") as src, open(rp, "w", encoding="utf-8",
                                                     newline="\n") as dst:
        dst.write(src.read())
    with open(os.path.join(ROOT, "_audit", "phase49-finalization",
                           "reference-step-decisions-%s.csv" % args.group), "w",
              encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["symbol", "date", "decision",
                                           "ref_ratio", "our_ratio", "rel",
                                           "shift_days"])
        w.writeheader()
        for d in decisions:
            w.writerow({k: d.get(k) for k in w.fieldnames})
    ated = 1
    max_date = ""
    for line in factors:
        r = json.loads(line)
        if r["effective_date"] > max_date:
            max_date = r["effective_date"]
    manifest = {
        "schema": "ra365-correction-pack-v1",
        "version": VERSION,
        "correction_version": VERSION,
        "mode": "authoritative",
        "as_of": max_date,
        "created_at": "2026-11-10",
        "tool": "phase49-finalization stageD_merge_reference.py",
        "source": "rahavard type0/type7 owner-authenticated capture 2026-11-10 + tracked pack",
        "reference_sha256": ",".join(ref_shas),
        "files": {"factors": "factors.jsonl", "raw_ohlc": "raw_ohlc.jsonl"},
        "file_sha256": {"factors": sha256(fp), "raw_ohlc": sha256(rp)},
        "factors_sha256": sha256(fp),
        "raw_ohlc_sha256": sha256(rp),
        "counts": {
            "symbols": len(per_symbol),
            "steps": len(factors),
            "verified_steps": sum(v["verified"] for v in per_symbol.values()),
            "reconstructed_verified_steps": sum(
                v["reconstructed_verified"] for v in per_symbol.values()),
            "unverified_steps": sum(v["unverified"] for v in per_symbol.values()),
            "invalid_dropped_steps": sum(
                1 for d in decisions if d["decision"] == "drop-contradicted"),
            "pre2020_steps": sum(v["pre2020"] for v in per_symbol.values()),
        },
        "captured_symbols": sorted(ref),
        "dropped_steps": [d for d in decisions
                          if d["decision"] == "drop-contradicted"],
        "per_symbol": per_symbol,
    }
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8",
              newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    counts = collections.Counter(d["decision"] for d in decisions)
    print(json.dumps({"group": args.group, "symbols": len(per_symbol),
                      "steps": len(factors), "decisions": dict(counts),
                      "verified": manifest["counts"]["verified_steps"],
                      "unverified": manifest["counts"]["unverified_steps"]},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
