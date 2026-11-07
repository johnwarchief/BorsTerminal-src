# -*- coding: utf-8 -*-
"""Merge a fresh pull over a base capture without accepting coverage regressions."""
import argparse
import collections
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--fresh", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary", default="")
    a = ap.parse_args()

    base = {}
    for line in open(a.base, encoding="utf-8"):
        j = json.loads(line)
        base[j["symbol"]] = j
    kept_fresh = kept_base = 0
    reasons = collections.Counter()
    for line in open(a.fresh, encoding="utf-8"):
        j = json.loads(line)
        sym = j["symbol"]
        old = base.get(sym)
        if not old:
            base[sym] = j; kept_fresh += 1
            continue
        old_live = not str(old.get("adjustSource") or "").startswith("local-")
        new_live = not str(j.get("adjustSource") or "").startswith("local-")
        old_n = len(old.get("candles") or [])
        new_n = len(j.get("candles") or [])
        if old_live and not new_live:
            reasons["fresh_fallback"] += 1
            continue
        if old_live and new_n < old_n * 0.95:
            reasons["fresh_truncated"] += 1
            continue
        base[sym] = j; kept_fresh += 1
    with open(a.out, "w", encoding="utf-8") as fh:
        for sym in sorted(base):
            fh.write(json.dumps(base[sym], ensure_ascii=False) + "\n")
    s = {"symbols": len(base), "fresh_kept": kept_fresh,
         "base_kept": len(base) - kept_fresh, "reasons": dict(reasons)}
    if a.summary:
        json.dump(s, open(a.summary, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(s, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
