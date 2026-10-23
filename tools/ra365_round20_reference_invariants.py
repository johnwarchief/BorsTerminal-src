# -*- coding: utf-8 -*-
"""Round 20: reproduce the reference/snapshot invariants used by the report.

Reads the frozen Rahavard snapshot (type0/type7) and the product snapshot
without writing either.  Two invariants are re-derived from raw files:

* type0/type7 volume equality on every common (asset, date);
* product snapshot record/asset counts by status.
"""
from __future__ import annotations

import argparse
import io
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "artifacts", "ra365", "r20")


def reference_volumes(path: str):
    type0: dict[tuple[str, str], float] = {}
    type7: dict[tuple[str, str], float] = {}
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            typ = rec.get("type")
            if rec.get("res") != "D":
                continue
            target = type0 if typ == "type0" else type7 if typ == "type7" else None
            if target is None:
                continue
            asset = str(rec.get("asset_id"))
            for bar in rec.get("bars") or []:
                if isinstance(bar, dict):
                    day = str(bar.get("utc") or "")[:10]
                    volume = bar.get("volume")
                elif isinstance(bar, list) and len(bar) >= 6:
                    day = str(bar[0] or "")[:10]
                    volume = bar[5]
                else:
                    continue
                if not day:
                    continue
                target[(asset, day)] = volume
    common = type0.keys() & type7.keys()
    equal = sum(1 for k in common if type0[k] == type7[k])
    return len(common), equal


def product_counts(path: str):
    status = Counter()
    assets = set()
    records = 0
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            records += 1
            status[str(rec.get("status"))] += 1
            assets.add(rec.get("symbol"))
    return records, len(assets), dict(status)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="C:/Users/Johnkallnaya/Desktop/Borsterminal/"
                                    "_scratch/ra_fup_2026_10_20/ref_bars_v2.jsonl")
    ap.add_argument("--product", default="C:/Users/Johnkallnaya/Desktop/Borsterminal/"
                                         "_scratch/ra_round3/product_live_final_v4.jsonl")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    common, equal = reference_volumes(args.ref)
    vol = {"type0_type7_common": common, "volume_equal": equal,
           "pct": round(100.0 * equal / common, 6) if common else None}
    with open(os.path.join(OUT, "reference-volume-parity.json"), "w", encoding="utf-8") as f:
        json.dump(vol, f, ensure_ascii=False, indent=1)
    records, assets, status = product_counts(args.product)
    count = {"source": args.product, "records": records, "assets": assets, "status": status}
    with open(os.path.join(OUT, "product-snapshot-count.json"), "w", encoding="utf-8") as f:
        json.dump(count, f, ensure_ascii=False, indent=1)
    print(json.dumps({"volume": vol, "product": count}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
