#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build the Method A 'full correction pack rebuild' from:
  - the tracked r32b-v2 pack steps (reference-derived), and
  - canonical product events (API with corrections disabled), which already
    include official ledger merges and unproven-event filtering.

Rules
  * pack replace_step on date D: overrides every product event on D;
  * pack suppress_step on date D: removes every product event on D;
  * product events on other dates are kept (they are the only evidence for
    pre-2020 steps), merged per date if several share the effective date;
  * every output step carries provenance; no factor is synthesized.

Outputs under _audit/phase49/continuation/packs/rebuild-v1 plus an event
mapping CSV/JSON report.
"""
import collections
import csv
import hashlib
import gzip
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EVID = os.path.join(ROOT, "_audit", "phase49", "continuation", "evidence")
BASE_PACK = os.path.join(ROOT, "data", "ra365_corrections", "ra365-r32b-v2")
OUT = os.path.join(ROOT, "_audit", "phase49", "continuation", "packs", "rebuild-v1")
NO_CORR = os.path.join(EVID, "api-no-corrections")
VERSION = "ra365-phase49-rebuild-v1"
NEAR_DAYS = 3
NEAR_TOL = 0.01


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_pack():
    rows = [json.loads(l) for l in open(os.path.join(BASE_PACK, "factors.jsonl"),
                                        encoding="utf-8") if l.strip()]
    by = collections.defaultdict(lambda: {"replace": {}, "suppress": set()})
    for r in rows:
        sym = r.get("symbol") or ""
        if not sym:
            continue
        if r.get("action") == "suppress_step":
            by[sym]["suppress"].add(r["effective_date"])
        else:
            by[sym]["replace"][r["effective_date"]] = r
    raws = [l for l in open(os.path.join(BASE_PACK, "raw_ohlc.jsonl"),
                            encoding="utf-8") if l.strip()]
    manifest = json.load(open(os.path.join(BASE_PACK, "manifest.json"), encoding="utf-8"))
    return by, raws, manifest


def load_events(sym):
    fn = os.path.join(NO_CORR, sym.replace("/", "_") + ".json.gz")
    if not os.path.exists(fn):
        return None
    with gzip.open(fn, "rt", encoding="utf-8") as fh:
        p = json.load(fh)
    by_date = collections.defaultdict(list)
    for e in p.get("adjustEvents") or []:
        d = str(e.get("date") or "")[:10]
        try:
            r = float(e.get("ratio"))
        except (TypeError, ValueError):
            continue
        if d and r > 0:
            by_date[d].append(e)
    return dict(by_date), p


def ins_codes():
    con = sqlite3.connect(os.path.join(ROOT, "_audit", "phase49", "continuation", "db",
                                       "restored-work.db"))
    out = {}
    for sym, ins in con.execute("SELECT l_val18, ins_code FROM instruments "
                                "ORDER BY updated_at DESC"):
        if sym and ins:
            out.setdefault(sym, ins)
    con.close()
    return out


def build_symbol(sym, pack_syms, mapping, conflicts, ins_map):
    ev = load_events(sym)
    if ev is None:
        return None
    base, payload = ev
    rep = pack_syms.get(sym, {"replace": {}, "suppress": set()})
    dates = sorted(set(base) | set(rep["replace"]) | set(rep["suppress"]))
    steps = []
    for d in dates:
        in_rep = d in rep["replace"]
        in_sup = d in rep["suppress"]
        if in_rep:
            r = rep["replace"][d]
            steps.append({
                "action": "replace_step", "effective_date": d,
                "ins_code": r.get("ins_code") or ins_map.get(sym, ""),
                "asset_id": r.get("asset_id") or "",
                "ratio": float(r["ratio"]), "class": r.get("class") or "PACK",
                "source": r.get("source") or "rahavard-reference-correction",
                "method": r.get("method") or "pack",
                "confidence": r.get("confidence") or "",
                "prod_ratio": r.get("prod_ratio"),
                "ref_ratio": r.get("ref_ratio"),
                "event_sig": r.get("event_sig") or "",
                "fields_used": r.get("fields_used") or "",
                "samples": r.get("samples"), "max_field_dev": r.get("max_field_dev"),
                "ref_bars_sha256": r.get("ref_bars_sha256") or "",
                "correction_version": VERSION,
                "created_at": r.get("created_at") or "",
                "reason": "pack replace_step (reference-derived) wins over product",
                "prov_kind": "pack",
                "suppressed_product_events": len(base.get(d, [])),
            })
            for e in base.get(d, []):
                mapping.append({"symbol": sym, "date": d, "decision": "suppressed-by-pack",
                                "ratio": e.get("ratio"), "source": e.get("source"),
                                "pack_ratio": float(r["ratio"]), "pack_class": r.get("class")})
            continue
        if in_sup:
            for e in base.get(d, []):
                mapping.append({"symbol": sym, "date": d, "decision": "suppressed-by-pack",
                                "ratio": e.get("ratio"), "source": e.get("source"),
                                "pack_ratio": None, "pack_class": "SUPPRESS"})
            continue
        evs = base.get(d, [])
        if not evs:
            continue
        near = None
        for pd_, row_ in rep["replace"].items():
            delta = abs((__import__("datetime").date.fromisoformat(d) -
                         __import__("datetime").date.fromisoformat(pd_)).days)
            if 0 < delta <= NEAR_DAYS and row_.get("ratio"):
                for e_ in evs:
                    if abs(float(e_["ratio"]) / float(row_["ratio"]) - 1.0) <= NEAR_TOL:
                        near = (pd_, row_, delta)
                        break
            if near:
                break
        if near:
            pd_, row_, delta = near
            for e_ in evs:
                mapping.append({"symbol": sym, "date": d,
                                "decision": "suppressed-by-pack-near-date",
                                "ratio": e_.get("ratio"), "source": e_.get("source"),
                                "pack_ratio": row_.get("ratio"),
                                "pack_class": "NEAR:" + str(row_.get("class"))})
            continue
        ratio = 1.0
        srcs = []
        for e in evs:
            ratio *= float(e["ratio"])
            srcs.append(str(e.get("source") or "unknown"))
        steps.append({
            "action": "replace_step", "effective_date": d, "ratio": ratio,
            "ins_code": ins_map.get(sym, ""), "asset_id": "",
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
                            "ratio": e.get("ratio"), "source": e.get("source"),
                            "pack_ratio": None, "pack_class": ""})
    # near-date diagnostics (no automatic change here; build_symbol already
    # suppressed provable same-action events on neighbouring days)
    pack_dates = sorted(rep["replace"])
    for d in sorted(base):
        if d in rep["replace"] or d in rep["suppress"]:
            continue
        for pd in pack_dates:
            delta = abs((__import__("datetime").date.fromisoformat(d) -
                         __import__("datetime").date.fromisoformat(pd)).days)
            if 0 < delta <= 7:
                conflicts.append({"symbol": sym, "product_date": d,
                                  "pack_date": pd, "delta_days": delta,
                                  "product_ratio": base[d][0].get("ratio"),
                                  "pack_ratio": rep["replace"][pd].get("ratio")})
    steps.sort(key=lambda s: s["effective_date"])
    return steps


def main():
    pack_syms, raws, base_manifest = load_pack()
    syms = []
    for csv_path in (os.path.join(ROOT, "_audit", "ADJUSTED-FACTOR-STEPS.csv"),
                     os.path.join(ROOT, "_audit", "phase49", "continuation", "symbols30.csv")):
        for r in csv.DictReader(open(csv_path, encoding="utf-8-sig")):
            s = r.get("symbol")
            if s and s not in syms:
                syms.append(s)
    os.makedirs(OUT, exist_ok=True)
    mapping, conflicts = [], []
    ins_map = ins_codes()
    factors_out = []
    per_symbol = {}
    for sym in syms:
        steps = build_symbol(sym, pack_syms, mapping, conflicts, ins_map)
        if steps is None:
            print("SKIP (no canonical events):", sym)
            continue
        for s in steps:
            row = dict(s)
            row["symbol"] = sym
            factors_out.append(row)
        per_symbol[sym] = {"steps": len(steps),
                           "pack": sum(1 for s in steps if s["prov_kind"] == "pack"),
                           "product": sum(1 for s in steps if s["prov_kind"] == "product")}
    fp = os.path.join(OUT, "factors.jsonl")
    with open(fp, "w", encoding="utf-8") as fh:
        for r in factors_out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    rp = os.path.join(OUT, "raw_ohlc.jsonl")
    with open(rp, "w", encoding="utf-8") as fh:
        for line in raws:
            fh.write(line)
    manifest = dict(base_manifest)
    manifest.update({
        "correction_version": VERSION,
        "created_at": "2026-11-10",
        "mode": "authoritative",
        "source": "phase49 rebuild: tracked r32b-v2 pack steps + canonical product events",
        "method": "pack wins on its dates; product events retained elsewhere",
        "files": {"factors": "factors.jsonl", "raw_ohlc": "raw_ohlc.jsonl"},
        "file_sha256": {"factors": sha256(fp), "raw_ohlc": sha256(rp)},
        "reference_sha256": base_manifest.get("reference_sha256") or "",
        "symbols_rebuilt": len(per_symbol),
        "counts": {"replace_step": len(factors_out),
                   "from_pack": sum(1 for r in factors_out if r["prov_kind"] == "pack"),
                   "from_product": sum(1 for r in factors_out if r["prov_kind"] == "product")},
    })
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "_event_mapping.json"), "w", encoding="utf-8") as fh:
        json.dump(mapping, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "_per_symbol.json"), "w", encoding="utf-8") as fh:
        json.dump(per_symbol, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "_near_date_conflicts.json"), "w", encoding="utf-8") as fh:
        json.dump(conflicts, fh, ensure_ascii=False, indent=1)
    mp = os.path.join(OUT, "_event_mapping.csv")
    with open(mp, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["symbol", "date", "decision", "ratio",
                                           "source", "pack_ratio", "pack_class"])
        w.writeheader()
        w.writerows(mapping)
    print(json.dumps({"symbols": len(per_symbol), "steps": len(factors_out),
                      "from_pack": manifest["counts"]["from_pack"],
                      "from_product": manifest["counts"]["from_product"],
                      "near_date_conflicts": len(conflicts),
                      "per_symbol": per_symbol}, ensure_ascii=False, indent=1))
    print("out:", OUT)


if __name__ == "__main__":
    main()
