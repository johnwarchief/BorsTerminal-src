#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage B (finalization): build the full Method-A Rebuild correction pack.

Inputs
  * canonical product events per symbol (corrections disabled), from
    stageB_canonical_dump.py;
  * tracked r32b-v2 pack (replace/suppress steps + raw field corrections).
Rules (identical to ra365-phase49-rebuild-v1, generalized to all symbols):
  * pack replace_step on D overrides every product event on D;
  * pack suppress_step on D removes product events on D;
  * product events on other dates are kept (merged per date);
  * a product event within +-3 days of a pack replace with |ratio-1| <= 1%
    is the same action and is suppressed with evidence;
  * every step carries provenance; nothing is synthesized.
"""
import collections
import csv
import datetime
import gzip
import hashlib
import json
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVID = os.path.join(ROOT, "_audit", "phase49-finalization", "evidence")
CANON = os.path.join(EVID, "canonical")
BASE_PACK = os.path.join(ROOT, "data", "ra365_corrections", "ra365-r32b-v2")
OUT = os.path.join(ROOT, "_audit", "phase49-finalization", "packs", "rebuild-full-v1")
DB = os.path.join(ROOT, "_audit", "phase49-finalization", "db", "restored-work.db")
VERSION = "ra365-phase49-rebuild-full-v1"
NEAR_DAYS = 3
NEAR_TOL = 0.01


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def safe(name):
    return name.replace("/", "_").replace("\\", "_")


def load_pack():
    by = collections.defaultdict(lambda: {"replace": {}, "suppress": set()})
    for line in open(os.path.join(BASE_PACK, "factors.jsonl"), encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        sym = str(r.get("symbol") or "")
        if not sym:
            continue
        if r.get("action") == "suppress_step":
            by[sym]["suppress"].add(str(r["effective_date"])[:10])
        else:
            by[sym]["replace"][str(r["effective_date"])[:10]] = r
    raws = [l for l in open(os.path.join(BASE_PACK, "raw_ohlc.jsonl"),
                            encoding="utf-8") if l.strip()]
    manifest = json.load(open(os.path.join(BASE_PACK, "manifest.json"),
                              encoding="utf-8"))
    return by, raws, manifest


def load_canonical(sym):
    fn = os.path.join(CANON, safe(sym) + ".json.gz")
    if not os.path.exists(fn):
        return None
    with gzip.open(fn, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def ins_map():
    con = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
    out = {}
    for sym, ins in con.execute(
            "SELECT l_val18, ins_code FROM instruments WHERE l_val18 IS NOT NULL "
            "ORDER BY updated_at DESC"):
        if sym and ins:
            out.setdefault(sym, ins)
    con.close()
    return out


def days(a, b):
    return abs((datetime.date.fromisoformat(a) - datetime.date.fromisoformat(b)).days)


def build_symbol(sym, rec, rep, ins, mapping, conflicts):
    steps = []
    base = collections.defaultdict(list)
    for e in rec.get("applied_events") or []:
        d = str(e.get("date") or "")[:10]
        try:
            ratio = float(e.get("ratio"))
        except (TypeError, ValueError):
            continue
        if d and ratio > 0:
            base[d].append({"ratio": ratio, "source": e.get("source")})
    dates = sorted(set(base) | set(rep["replace"]) | set(rep["suppress"]))
    for d in dates:
        if d in rep["replace"]:
            r = rep["replace"][d]
            steps.append({
                "action": "replace_step", "effective_date": d,
                "ins_code": r.get("ins_code") or ins,
                "symbol": sym, "asset_id": r.get("asset_id") or "",
                "ratio": float(r["ratio"]), "class": r.get("class") or "PACK",
                "source": r.get("source") or "rahavard-reference-correction",
                "method": r.get("method") or "pack",
                "confidence": r.get("confidence") or "",
                "prod_ratio": r.get("prod_ratio"),
                "ref_ratio": r.get("ref_ratio"),
                "event_sig": r.get("event_sig") or "",
                "fields_used": r.get("fields_used") or "",
                "samples": r.get("samples"),
                "max_field_dev": r.get("max_field_dev"),
                "ref_bars_sha256": r.get("ref_bars_sha256") or "",
                "correction_version": VERSION,
                "created_at": "2026-11-10",
                "reason": "pack replace_step (reference-derived) wins over product",
                "prov_kind": "pack",
                "suppressed_product_events": len(base.get(d, [])),
            })
            for e in base.get(d, []):
                mapping.append({"symbol": sym, "date": d,
                                "decision": "suppressed-by-pack",
                                "ratio": e["ratio"], "source": e.get("source"),
                                "pack_ratio": float(r["ratio"]),
                                "pack_class": r.get("class") or ""})
            continue
        if d in rep["suppress"]:
            for e in base.get(d, []):
                mapping.append({"symbol": sym, "date": d,
                                "decision": "suppressed-by-pack",
                                "ratio": e["ratio"], "source": e.get("source"),
                                "pack_ratio": None, "pack_class": "SUPPRESS"})
            continue
        evs = base.get(d, [])
        if not evs:
            continue
        near = None
        for pd, row in rep["replace"].items():
            delta = days(d, pd)
            if 0 < delta <= NEAR_DAYS and row.get("ratio"):
                for e in evs:
                    if abs(e["ratio"] / float(row["ratio"]) - 1.0) <= NEAR_TOL:
                        near = (pd, row, delta)
                        break
            if near:
                break
        if near:
            pd, row, delta = near
            for e in evs:
                mapping.append({"symbol": sym, "date": d,
                                "decision": "suppressed-by-pack-near-date",
                                "ratio": e["ratio"], "source": e.get("source"),
                                "pack_ratio": row.get("ratio"),
                                "pack_class": "NEAR:" + str(row.get("class") or "")})
                conflicts.append({"symbol": sym, "product_date": d,
                                  "pack_date": pd, "delta_days": delta,
                                  "product_ratio": e["ratio"],
                                  "pack_ratio": row.get("ratio"),
                                  "resolution": "suppressed-by-pack-near-date"})
            continue
        ratio = 1.0
        srcs = []
        for e in evs:
            ratio *= e["ratio"]
            srcs.append(str(e.get("source") or "unknown"))
        steps.append({
            "action": "replace_step", "effective_date": d, "ratio": ratio,
            "ins_code": ins, "symbol": sym, "asset_id": "",
            "class": "PRODUCT", "source": "phase49-canonical-product-event",
            "method": "base-price-discontinuity+official-merge",
            "confidence": "product-discovered", "prod_ratio": ratio,
            "ref_ratio": None, "event_sig": "product",
            "fields_used": "", "samples": None, "max_field_dev": None,
            "ref_bars_sha256": "",
            "correction_version": VERSION, "created_at": "2026-11-10",
            "reason": "product event retained outside pack coverage",
            "prov_kind": "product", "product_events": srcs,
        })
        for e in evs:
            mapping.append({"symbol": sym, "date": d, "decision": "kept-product",
                            "ratio": e["ratio"], "source": e.get("source"),
                            "pack_ratio": None, "pack_class": ""})
    steps.sort(key=lambda s: s["effective_date"])
    # cumulative factor at each step: product of ratios of later steps
    # (factor applied to every candle strictly before the step date).
    cum = 1.0
    for s in reversed(steps):
        s["cum_factor_after"] = round(cum, 15)
        cum *= float(s["ratio"])
    return steps


def main():
    pack, raws, base_manifest = load_pack()
    ins = ins_map()
    os.makedirs(OUT, exist_ok=True)
    symbols = sorted(set(pack) | {
        f[:-len(".json.gz")] for f in os.listdir(CANON) if f.endswith(".json.gz")})
    # canonical file names are safe()-encoded; map back through summary
    summary = json.load(open(os.path.join(EVID, "canonical-summary.json"),
                             encoding="utf-8"))
    name_by_safe = {safe(s): s for s in summary["per_symbol"]}
    symbols = sorted(set(pack) | set(summary["per_symbol"]))
    mapping, conflicts, per_symbol = [], [], {}
    factor_lines = []
    missing_canon = []
    for sym in symbols:
        rec = summary["per_symbol"].get(sym) or load_canonical(sym)
        if rec is None:
            missing_canon.append(sym)
            continue
        steps = build_symbol(sym, rec, pack.get(sym, {"replace": {}, "suppress": set()}),
                             ins.get(sym, ""), mapping, conflicts)
        if not steps:
            continue
        for s in steps:
            factor_lines.append(json.dumps(s, ensure_ascii=False, sort_keys=True))
        fp = hashlib.sha256("\n".join(
            "%s|%.15g|%s" % (s["effective_date"], float(s["ratio"]), s["prov_kind"])
            for s in steps).encode("utf-8")).hexdigest()
        per_symbol[sym] = {
            "steps": len(steps),
            "pre2020": sum(1 for s in steps if s["effective_date"] < "2020-01-01"),
            "pack_steps": sum(1 for s in steps if s["prov_kind"] == "pack"),
            "product_steps": sum(1 for s in steps if s["prov_kind"] == "product"),
            "chain_fingerprint": fp,
        }
    factors_path = os.path.join(OUT, "factors.jsonl")
    with open(factors_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(factor_lines) + ("\n" if factor_lines else ""))
    raw_path = os.path.join(OUT, "raw_ohlc.jsonl")
    with open(raw_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(raws) + ("\n" if raws else ""))
    with open(os.path.join(OUT, "event-mapping.csv"), "w", encoding="utf-8",
              newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["symbol", "date", "decision", "ratio",
                                           "source", "pack_ratio", "pack_class"])
        w.writeheader()
        w.writerows(sorted(mapping, key=lambda r: (r["symbol"], r["date"])))
    with open(os.path.join(OUT, "near-date-conflicts.json"), "w", encoding="utf-8") as fh:
        json.dump(conflicts, fh, ensure_ascii=False, indent=1)
    raw_fields = collections.Counter()
    ambiguous = {}
    by_symbol_ins = collections.defaultdict(set)
    for line in raws:
        try:
            raw_fields[json.loads(line).get("field") or "?"] += 1
        except Exception:
            pass
    for line in factor_lines:
        r = json.loads(line)
        if r.get("symbol") and r.get("ins_code"):
            by_symbol_ins[r["symbol"]].add(r["ins_code"])
    for s, ins_set in by_symbol_ins.items():
        ins_set.discard("")
        if len(ins_set) > 1:
            ambiguous[s] = sorted(ins_set)
    manifest = {
        "schema": "ra365-correction-pack-v1",
        "version": VERSION,
        "correction_version": VERSION,
        "mode": "authoritative",
        "created_at": "2026-11-10",
        "tool": "phase49-finalization stageB_build_rebuild.py",
        "source": "rahavard_reference_frozen_v2 + phase49-canonical-product (owner-authenticated capture 2026-11-10)",
        "reference_sha256": os.environ.get("PHASE49_REF_SHA256", ""),
        "files": {"factors": "factors.jsonl", "raw_ohlc": "raw_ohlc.jsonl"},
        "base_pack": base_manifest.get("correction_version"),
        "base_pack_factors_sha256": sha256(os.path.join(BASE_PACK, "factors.jsonl")),
        "base_pack_raw_sha256": sha256(os.path.join(BASE_PACK, "raw_ohlc.jsonl")),
        "rules": {
            "pack_replace_wins_on_same_date": True,
            "pack_suppress_removes_same_date": True,
            "product_events_kept_off_pack_dates": True,
            "near_date_dedupe_days": NEAR_DAYS,
            "near_date_dedupe_ratio_tol": NEAR_TOL,
            "no_synthesized_events": True,
        },
        "semantics": {
            "mode": "authoritative: for a covered symbol the chain is built from replace_step rows; product events after as_of are kept",
            "replace_step": "suppress every product event on effective_date and insert one step with ratio",
            "raw_ohlc": "per-field historical display value from reference type0; never rewrites corporate events",
        },
        "counts": {
            "symbols": len(per_symbol),
            "steps": len(factor_lines),
            "replace_steps": len(factor_lines),
            "factor_replace_step": len(factor_lines),
            "factor_suppress_step": 0,
            "factor_assets": len(per_symbol),
            "factor_symbols": len(per_symbol),
            "pre2020_steps": sum(v["pre2020"] for v in per_symbol.values()),
            "pack_steps": sum(v["pack_steps"] for v in per_symbol.values()),
            "product_steps": sum(v["product_steps"] for v in per_symbol.values()),
            "raw_ohlc_rows": len(raws),
            "raw_fields": dict(raw_fields),
            "mapping_rows": len(mapping),
            "near_date_conflicts": len(conflicts),
            "missing_canonical": len(missing_canon),
        },
        "ambiguous_symbols": ambiguous,
        "dedupe": {"factor_merged": {}, "raw_conflicts": {}},
        "factors_sha256": sha256(factors_path),
        "raw_ohlc_sha256": sha256(raw_path),
        "file_sha256": {
            "factors": sha256(factors_path),
            "raw_ohlc": sha256(raw_path),
        },
        "per_symbol": per_symbol,
        "missing_canonical_examples": missing_canon[:30],
    }
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8",
              newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "_per_symbol.json"), "w", encoding="utf-8") as fh:
        json.dump(per_symbol, fh, ensure_ascii=False, indent=1)
    print(json.dumps(manifest["counts"], ensure_ascii=False, indent=1))
    print("factors_sha256", manifest["factors_sha256"])
    print("raw_ohlc_sha256", manifest["raw_ohlc_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
