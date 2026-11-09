#!/usr/bin/env python3
"""make_symbols.py — فهرستِ نمادهایِ ۳۰گانه را به ورودیِ درایورِ ضبط تبدیل می‌کند."""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--basis", default="real_close")
    args = ap.parse_args()
    with io.open(args.csv, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    out = []
    for row in rows:
        asset = str(row.get("asset_id") or "").strip()
        if not asset:
            print("missing asset_id: %s" % row.get("symbol"), file=sys.stderr)
            return 2
        out.append({"asset_id": int(asset) if asset.isdigit() else asset,
                    "symbol": row["symbol"], "ins_code": row["ins_code"],
                    "stratum": row["stratum"], "basis": args.basis})
    out.sort(key=lambda r: (str(r["asset_id"]), r["symbol"]))
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with io.open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("wrote %d symbols -> %s" % (len(out), args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
