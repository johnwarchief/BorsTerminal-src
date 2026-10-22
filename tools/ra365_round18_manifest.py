# -*- coding: utf-8 -*-
"""Assemble the Round 18 machine-readable manifest from the actual artifacts."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.environ.get("RA365_R18_CACHE", "D:/BorsTerminal-tmp/ra365_round18")
ART = os.path.join(ROOT, "artifacts", "ra365", "r18")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def jload(name, default=None):
    p = os.path.join(ART, name)
    if not os.path.exists(p):
        return default or {}
    return json.load(open(p, encoding="utf-8"))


def main():
    manifest = jload("raw-ohlc-cohort-manifest.json")
    summary = jload("raw-ohlc-summary.json")
    tax = jload("raw-ohlc-taxonomy-summary.json")
    layers = jload("layer-joint-summary.json")
    fallback = jload("fallback-display-parity-summary.json")
    repair = jload("price-history-repair-manifest-second.json")
    fetch = list(csv.DictReader(open(os.path.join(CACHE, "fetch-status.csv"),
                                     encoding="utf-8-sig")))
    fstat = Counter(r["status"] for r in fetch)
    type0 = Counter()
    for r in csv.DictReader(open(os.path.join(ART, "raw-ohlc-type0-parity.csv"),
                                 encoding="utf-8-sig")):
        for k in ("type0_rows", "common", "flat_bars", "close_last_cmp",
                  "close_last_exact", "close_closing_cmp", "close_closing_exact",
                  "open_cmp", "open_exact", "high_cmp", "high_exact",
                  "low_cmp", "low_exact", "volume_cmp", "volume_exact",
                  "row_exact", "row_tol"):
            try:
                type0[k] += int(r[k] or 0)
            except (TypeError, ValueError):
                pass
    refdb = os.path.join(CACHE, "reference.db")
    con = sqlite3.connect(f"file:{refdb}?mode=ro", uri=True)
    ref_rows = con.execute("SELECT COUNT(*) FROM tsetmc").fetchone()[0]
    ref_assets = con.execute("SELECT COUNT(DISTINCT ins_code) FROM tsetmc").fetchone()[0]
    t0_rows = con.execute("SELECT COUNT(*) FROM type0").fetchone()[0]
    t7_rows = con.execute("SELECT COUNT(*) FROM type7").fetchone()[0]
    con.close()
    manifest.update({
        "phase": "measured",
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "fetch": {
            "instruments": len(fetch), "status": dict(fstat),
            "cache": os.path.join(CACHE, "cache", "tsetmc_csv"),
            "status_csv": os.path.join(CACHE, "fetch-status.csv"),
            "variant_status_csv": os.path.join(CACHE, "fetch-variants-status.csv"),
            "workers": 6, "failures": fstat.get("FAILED", 0),
        },
        "reference": {
            "db": refdb, "db_sha256": sha(refdb) if os.path.exists(refdb) else "",
            "tsetmc_rows": ref_rows, "instruments": ref_assets,
            "type0_rows": t0_rows, "type7_rows": t7_rows,
            "raw_full_gz": os.path.join(ART, "raw_ohlc_reference.csv.gz"),
            "raw_registry": os.path.join(ART, "raw_ohlc_reference.csv"),
            "field_semantics": {
                "first": "first trade (chart open source)",
                "high": "daily high", "low": "daily low",
                "close": "official closing (پایانی; anchor)",
                "last": "last trade (type0 close)",
                "base": "previous close/base <OPEN>, never chart open",
                "volume": "daily volume",
            },
        },
        "raw_measure": summary,
        "type0_check": dict(type0),
        "taxonomy": tax,
        "layers": layers,
        "fallback_repair": {
            "cause": "price_history rows are mostly src=NULL/board; 10,448 base-as-open rows "
                     "across 271 assets; board snapshots can be stale vs published TSETMC",
            "scope": "2,595 measured symbols, existing per-symbol date ranges only",
            "published_rows_written": repair.get("upserted"),
            "added_rows": repair.get("added"),
            "replaced_rows": repair.get("replaced"),
            "integrity_check": repair.get("integrity_check"),
            "idempotent_second_run_sha": repair.get("db_sha256"),
            "db_copy": os.path.join(CACHE, "market_r18_repaired.db"),
            "before_after": fallback,
            "operational_db_touched": False,
        },
        "artifacts": {},
    })
    for name in ("raw-ohlc-parity.csv", "raw-ohlc-row-mismatches.csv",
                 "raw-ohlc-mismatch-taxonomy.csv", "raw-ohlc-coverage.csv",
                 "raw-ohlc-mismatch-samples.csv", "raw-ohlc-cohort-manifest.json",
                 "raw-ohlc-summary.json", "source-field-matrix.csv",
                 "layer-decomposition.csv", "regression-layer-link.csv",
                 "fallback-display-parity-before.csv",
                 "fallback-display-parity-after.csv",
                 "price-history-repair.csv", "raw_ohlc_reference.csv"):
        p = os.path.join(ART, name)
        if os.path.exists(p):
            manifest["artifacts"][name] = {"sha256": sha(p),
                                           "bytes": os.path.getsize(p)}
    with open(os.path.join(ART, "raw-ohlc-cohort-manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: manifest[k] for k in ("phase", "fetch", "reference") if k in manifest},
                     ensure_ascii=False)[:1200])
    print(json.dumps({"raw_measure": summary, "taxonomy": tax, "fallback": fallback},
                     ensure_ascii=False)[:1500])


if __name__ == "__main__":
    main()
