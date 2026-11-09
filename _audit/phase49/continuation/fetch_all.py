#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fetch /api/chart-db for the 30 Phase 4.8 symbols and store trimmed evidence.

Read-only GETs. Output: _audit/phase49/continuation/evidence/api-<label>/<symbol>.json.gz
"""
import argparse
import gzip
import json
import os
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EVID = os.path.join(ROOT, "_audit", "phase49", "continuation", "evidence")


def load_symbols(csv_path=None):
    if csv_path:
        import csv
        syms = []
        for r in csv.DictReader(open(csv_path, encoding="utf-8-sig")):
            if r.get("symbol") and r["symbol"] not in syms:
                syms.append(r["symbol"])
        return syms
    ev = json.load(open(os.path.join(ROOT, "tools", "phase48", "continuation",
                                     "evidence", "verify-api.json"), encoding="utf-8"))
    return [s["symbol"] for s in ev["per_symbol"]]


def api(path, token, timeout=300):
    req = urllib.request.Request(path, headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8159")
    ap.add_argument("--token-file", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--symbols-csv", default="")
    args = ap.parse_args()
    token = open(args.token_file, encoding="ascii").read().strip()
    outdir = os.path.join(EVID, "api-" + args.label)
    os.makedirs(outdir, exist_ok=True)
    syms = load_symbols(args.symbols_csv or None)
    index = []
    for i, sym in enumerate(syms, 1):
        url = args.api + "/api/chart-db/" + urllib.parse.quote(sym, safe="")
        p = api(url, token)
        trim = {
            "symbol": sym,
            "status": p.get("status"),
            "adjustSource": p.get("adjustSource"),
            "adjustCapability": p.get("adjustCapability"),
            "liveInjected": p.get("liveInjected"),
            "count": len(p.get("candles") or []),
            "factors": p.get("factors") or [],
            "adjustEvents": p.get("adjustEvents") or [],
            "adjustRejected": p.get("adjustRejected") or [],
        }
        fn = os.path.join(outdir, sym.replace("/", "_") + ".json.gz")
        with gzip.open(fn, "wt", encoding="utf-8") as fh:
            json.dump(trim, fh, ensure_ascii=False)
        index.append({"symbol": sym, "count": trim["count"],
                      "events": len(trim["adjustEvents"]),
                      "rejected": len(trim["adjustRejected"]),
                      "source": trim["adjustSource"],
                      "cap_mode": (trim["adjustCapability"] or {}).get("corrections", {}).get("mode")
                      if trim["adjustCapability"] else None,
                      "file": os.path.relpath(fn, ROOT).replace("\\", "/")})
        print("[%d/%d] %s count=%d events=%d rejected=%d" %
              (i, len(syms), sym, trim["count"], len(trim["adjustEvents"]),
               len(trim["adjustRejected"])), flush=True)
    with open(os.path.join(outdir, "_index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=1)
    print("saved", outdir)


if __name__ == "__main__":
    main()
