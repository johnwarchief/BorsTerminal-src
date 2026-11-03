# -*- coding: utf-8 -*-
"""Merge Round-3 live pulls over the Round-2 capture, one record per symbol.

Newer fresh files win; the base capture is used only where no fresh record exists.
Every output record records `_round3_source` so the report can state which cohort
was refreshed and which is the same-day v2 snapshot.
"""
import argparse
import collections
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--fill", action="append", default=[])
    ap.add_argument("--fresh", action="append", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary", default="")
    a = ap.parse_args()

    by_symbol = {}

    def load(path, replace):
        if not os.path.exists(path):
            print("missing", path)
            return
        n = added = 0
        for line in open(path, encoding="utf-8"):
            try:
                j = json.loads(line)
            except Exception:
                continue
            sym = j.get("symbol")
            if not sym:
                continue
            j["_round3_source"] = os.path.basename(path)
            n += 1
            if sym in by_symbol and not replace:
                continue
            if sym in by_symbol and replace and by_symbol[sym].get("_round3_source") != os.path.basename(a.base):
                # two fresh files: keep the newer fetch
                if str(j.get("fetchedAt") or "") < str(by_symbol[sym].get("fetchedAt") or ""):
                    continue
            by_symbol[sym] = j
            added += 1
        print(path, n, "kept", added)

    load(a.base, replace=True)
    for path in a.fill:
        load(path, replace=False)
    for path in a.fresh:
        load(path, replace=True)

    with open(a.out, "w", encoding="utf-8") as fh:
        for sym in sorted(by_symbol):
            fh.write(json.dumps(by_symbol[sym], ensure_ascii=False) + "\n")
    summary = {
        "symbols": len(by_symbol),
        "by_source": dict(collections.Counter(j.get("_round3_source") for j in by_symbol.values())),
        "status": dict(collections.Counter(j.get("status") for j in by_symbol.values())),
        "live_basis_last": sum(1 for j in by_symbol.values()
                               if j.get("status") == "success"
                               and j.get("priceBasis") == "last"
                               and not str(j.get("adjustSource") or "").startswith("local-")),
    }
    if a.summary:
        json.dump(summary, open(a.summary, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
