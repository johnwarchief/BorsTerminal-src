#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Event-level mapping for the 30 Phase 4.8 symbols.

Inputs (all read-only):
  - DB adjust_events (stored product events)
  - tracked pack rows
  - evidence/api-no-corrections   (canonical product events)
  - evidence/api-authoritative-base / api-overlay-dedup / api-rebuild-v1
Outputs:
  - evidence/event-mapping-30.csv
  - evidence/event-summary-30.json
"""
import collections
import csv
import glob
import gzip
import json
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EVID = os.path.join(ROOT, "_audit", "phase49", "continuation", "evidence")
PACK = os.path.join(ROOT, "data", "ra365_corrections", "ra365-r32b-v2", "factors.jsonl")
DB = os.path.join(ROOT, "_audit", "phase49", "continuation", "db", "restored-work.db")
REBUILD_MAP = os.path.join(ROOT, "_audit", "phase49", "continuation", "packs",
                           "rebuild-v1", "_event_mapping.json")


def symbols30():
    return [r["symbol"] for r in csv.DictReader(
        open(os.path.join(ROOT, "_audit", "phase49", "continuation", "symbols30.csv"),
             encoding="utf-8-sig"))]


def pack_rows():
    by = collections.defaultdict(lambda: {"replace": {}, "suppress": {}})
    for line in open(PACK, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        sym = r.get("symbol")
        if not sym:
            continue
        if r.get("action") == "suppress_step":
            by[sym]["suppress"][r["effective_date"]] = r
        else:
            by[sym]["replace"][r["effective_date"]] = r
    return by


def load_api(label, sym):
    fn = os.path.join(EVID, "api-" + label, sym.replace("/", "_") + ".json.gz")
    if not os.path.exists(fn):
        return None
    with gzip.open(fn, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def main():
    syms = symbols30()
    pack = pack_rows()
    stored = collections.defaultdict(list)
    con = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
    for s, d, r in con.execute("SELECT symbol,date,ratio FROM adjust_events WHERE ratio>0"):
        stored[s].append((d, r))
    con.close()
    rebuild_map = json.load(open(REBUILD_MAP, encoding="utf-8"))
    rm = collections.defaultdict(list)
    for x in rebuild_map:
        if x["symbol"] in syms:
            rm[x["symbol"]].append(x)
    rows = []
    summary = {}
    for sym in syms:
        base = load_api("no-corrections", sym)
        auth = load_api("authoritative-base", sym)
        ovl = load_api("overlay-dedup", sym)
        reb = load_api("rebuild-v1", sym)
        pr = pack.get(sym, {"replace": {}, "suppress": {}})
        base_events = (base or {}).get("adjustEvents") or []
        auth_rej = (auth or {}).get("adjustRejected") or []
        auth_suppressed = [e for e in auth_rej
                           if e.get("factor_status") == "suppressed-by-rahavard-reference-correction"]
        ovl_suppressed = [e for e in (ovl or {}).get("adjustRejected") or []
                          if e.get("factor_status") == "suppressed-by-rahavard-reference-correction"]
        near = [e for e in ovl_suppressed if e.get("dedupe")]
        base_dates = collections.Counter(str(e.get("date"))[:10] for e in base_events)
        decisions = {x["date"]: x for x in rm.get(sym, [])}
        for d in sorted(set(base_dates) | set(pr["replace"]) | set(pr["suppress"])):
            in_rep = d in pr["replace"]
            in_sup = d in pr["suppress"]
            if in_rep:
                row = pr["replace"][d]
                decision = "suppressed-by-pack"
                pack_ratio = row["ratio"]
                pack_class = row.get("class")
                ref_ratio = row.get("ref_ratio")
                if base_dates.get(d):
                    for _ in range(base_dates[d]):
                        rows.append({"symbol": sym, "date": d, "decision": decision,
                                     "product_ratio": None, "pack_ratio": pack_ratio,
                                     "ref_ratio": ref_ratio, "pack_class": pack_class,
                                     "source": "product+pack"})
                else:
                    rows.append({"symbol": sym, "date": d, "decision": "pack-only",
                                 "product_ratio": None, "pack_ratio": pack_ratio,
                                 "ref_ratio": ref_ratio, "pack_class": pack_class,
                                 "source": "pack"})
            elif in_sup:
                for _ in range(max(1, base_dates.get(d, 0))):
                    rows.append({"symbol": sym, "date": d, "decision": "suppressed-by-pack",
                                 "product_ratio": None, "pack_ratio": None,
                                 "ref_ratio": None, "pack_class": "SUPPRESS",
                                 "source": "product+pack-suppress"})
            else:
                nd = next((e for e in near if str(e.get("date"))[:10] == d), None)
                for e in [e for e in base_events if str(e.get("date"))[:10] == d]:
                    rows.append({
                        "symbol": sym, "date": d,
                        "decision": "suppressed-near-pack" if nd else "kept-product",
                        "product_ratio": e.get("ratio"), "pack_ratio": None,
                        "ref_ratio": None, "pack_class": "",
                        "source": e.get("source") or "product"})
        summary[sym] = {
            "stored_product_events": len(stored.get(sym, [])),
            "canonical_product_events": len(base_events),
            "pack_replace_steps": len(pr["replace"]),
            "pack_suppress_steps": len(pr["suppress"]),
            "authoritative_applied": len((auth or {}).get("adjustEvents") or []),
            "authoritative_suppressed_product": len(auth_suppressed),
            "overlay_applied": len((ovl or {}).get("adjustEvents") or []),
            "overlay_suppressed_product": len(ovl_suppressed),
            "overlay_near_deduped": len(near),
            "rebuild_applied": len((reb or {}).get("adjustEvents") or []),
            "kept_product": sum(1 for e in base_events
                                if not (str(e.get("date"))[:10] in pr["replace"]
                                        or str(e.get("date"))[:10] in pr["suppress"])
                                and not any(str(e.get("date"))[:10] == str(n.get("date"))[:10]
                                            for n in near)),
            "first_event": min(base_dates) if base_dates else None,
            "last_event": max(base_dates) if base_dates else None,
        }
    out_csv = os.path.join(EVID, "event-mapping-30.csv")
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["symbol", "date", "decision", "product_ratio",
                                           "pack_ratio", "ref_ratio", "pack_class", "source"])
        w.writeheader()
        w.writerows(rows)
    tot = {k: sum(v[k] for v in summary.values())
           for k in ("stored_product_events", "canonical_product_events",
                     "pack_replace_steps", "pack_suppress_steps",
                     "authoritative_applied", "authoritative_suppressed_product",
                     "overlay_applied", "overlay_suppressed_product",
                     "overlay_near_deduped", "rebuild_applied", "kept_product")}
    report = {"symbols": len(syms), "totals": tot, "per_symbol": summary,
              "mapping_rows": len(rows)}
    out_json = os.path.join(EVID, "event-summary-30.json")
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print(json.dumps(report["totals"], ensure_ascii=False, indent=1))
    print("mapping rows:", len(rows))
    print("out:", out_csv, out_json)


if __name__ == "__main__":
    main()
