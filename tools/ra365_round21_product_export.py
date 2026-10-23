# -*- coding: utf-8 -*-
"""Round 21: export the live product chart payload for one symbol (read-only copy DB)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset-id", required=True)
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.environ["BORS_DB"] = a.db
    os.environ.setdefault("BORS_NO_FETCH_LOOPS", "1")
    import api.chart as CH
    CH.DB_PATH = a.db
    db_sha_before = sha(a.db)
    t0 = time.time()
    res = CH.get_chart_tsetmc(a.symbol)
    elapsed = round(time.time() - t0, 3)
    candles = res.get("candles") or []
    payload = {
        "asset_id": a.asset_id,
        "symbol_request": a.symbol,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "elapsed_sec": elapsed,
        "db": a.db,
        "db_sha256_after": sha(a.db),
        "status": res.get("status"),
        "adjustSource": res.get("adjustSource"),
        "priceBasis": res.get("priceBasis"),
        "priceBasisRequested": res.get("priceBasisRequested"),
        "priceBasisReason": res.get("priceBasisReason"),
        "adjustCapability": res.get("adjustCapability"),
        "adjustEvents": res.get("adjustEvents"),
        "adjustRejected": res.get("adjustRejected"),
        "corporateEvents": res.get("corporateEvents"),
        "candles": candles,
        "volumes": res.get("volumes"),
        "factors": res.get("factors"),
        "count": len(candles),
        "message": res.get("message"),
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(json.dumps({
        "asset_id": a.asset_id, "symbol": a.symbol, "status": res.get("status"),
        "count": len(candles), "adjustSource": res.get("adjustSource"),
        "basis": res.get("priceBasis"), "reason": res.get("priceBasisReason"),
        "first": candles[-1].get("time") if candles else None,
        "last": candles[0].get("time") if candles else None,
        "db_sha_changed": db_sha_before != payload["db_sha256_after"],
        "elapsed_sec": elapsed,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
