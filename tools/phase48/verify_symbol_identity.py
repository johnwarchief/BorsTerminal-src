#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_symbol_identity.py — S6: prove the 30-symbol join is identity-based.

The reference capture names series by display symbol and asset_id; the local
chart resolves a symbol to `instruments.ins_code` through `symbol_identity`
(`sym_pred`). This tool checks both sides agree and that the reference series
for a symbol carries exactly one asset_id:

  * reference metadata (`symbols.json` from the capture) -> ins_code;
  * local resolver `api.chart._ins_code_for(symbol)` -> ins_code;
  * reference bars -> exactly one asset_id per (symbol, resolution, type).

Exit 0 only when all symbols match. No network, read-only local DB.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-dir", required=True, help="directory containing market.db")
    ap.add_argument("--ref-symbols", required=True, help="capture symbols.json (symbol/ins_code/asset_id)")
    ap.add_argument("--bars", required=True, help="normalized bars.ndjson.gz")
    ap.add_argument("--out", required=True)
    ap.add_argument("--md", default="")
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="p48-identity-")
    for name in ("market.db", "user.db"):
        p = os.path.join(args.db_dir, name)
        if os.path.exists(p):
            shutil.copyfile(p, os.path.join(tmp, name))
    os.environ["BORS_DATA_DIR"] = tmp
    os.environ["BORS_CHART_CDN"] = "off"
    os.environ["BORS_NO_FETCH_LOOPS"] = "1"
    os.environ.setdefault("BORS_CODAL_OFFLINE", "1")
    os.environ.setdefault("BORS_CODAL_AUTO", "0")
    import api.chart as ch
    import symbol_identity as SI

    ref_meta = {r["symbol"]: r for r in json.load(open(args.ref_symbols, encoding="utf-8"))}
    asset_ids = {}
    with gzip.open(args.bars, "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            sym = r["symbol"]
            asset_ids.setdefault(sym, set()).add(int(r["asset_id"]))

    out = {"symbols": {}, "matched": 0, "failed": 0}
    lines = ["| نماد | ins_code مرجع | ins_code محلی | asset_id مرجع | هویت |",
             "| --- | --- | --- | --- | --- |"]
    for sym, meta in ref_meta.items():
        local = ch._ins_code_for(sym)
        ref_code = str(meta.get("ins_code") or "")
        ids = sorted(asset_ids.get(sym) or [])
        ok = bool(local) and str(local) == ref_code and len(ids) == 1 and \
            int(meta.get("asset_id") or -1) == ids[0] and \
            SI.key(sym) == SI.key(meta["symbol"])
        out["symbols"][sym] = {"ref_ins_code": ref_code, "local_ins_code": local,
                               "ref_asset_id": meta.get("asset_id"), "bar_asset_ids": ids,
                               "identity_key": SI.key(sym), "ok": ok}
        out["matched" if ok else "failed"] += 1
        lines.append(f"| {sym} | {ref_code} | {local} | {ids[0] if ids else ''} | "
                     + ("**PASS**" if ok else "**FAIL**") + " |")
    out["all_ok"] = out["failed"] == 0
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    if args.md:
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    print("matched", out["matched"], "failed", out["failed"])
    return 0 if out["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
