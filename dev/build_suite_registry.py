#!/usr/bin/env python3
"""Create/merge dev/suite_registry.json from the runner's SUITES lists."""
from __future__ import annotations

import argparse
import json
import os

from suite_registry_guard import REGISTRY, parse_suites


def merge(existing, suites):
    out = existing if existing else {"schema": 1, "suites": {}}
    out["schema"] = 1
    kept = {}
    for script, info in suites.items():
        cur = out["suites"].get(script, {})
        kept[script] = {
            "script": script,
            "label": info["label"],
            "kind": info["kind"],
            "category": cur.get("category", "UNCLASSIFIED"),
            "disposition": cur.get("disposition", "UNCLASSIFIED"),
            "profile": cur.get("profile", "legacy"),
            "go_equivalent": cur.get("go_equivalent"),
            "ts_equivalent": cur.get("ts_equivalent"),
            "reason": cur.get("reason", ""),
            "retirement_date": cur.get("retirement_date"),
        }
    out["suites"] = dict(sorted(kept.items()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    existing = json.load(open(REGISTRY, encoding="utf-8")) if os.path.isfile(REGISTRY) else None
    reg = merge(existing, parse_suites())
    if args.write:
        with open(REGISTRY, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(reg, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        print("wrote %d entries -> %s" % (len(reg["suites"]), REGISTRY))
    else:
        print(json.dumps(reg, ensure_ascii=False, indent=1)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
