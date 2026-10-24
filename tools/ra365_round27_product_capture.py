#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 27: fresh full-history product capture with the current engine core.

For every asset in the 2,595-asset manifest this tool replays the cached
TSETMC daily CSV through the current code path: parser → base-gap discovery
→ ledger sharpening → unproven-gap filter → canonical adjustment
(share-leg dedupe, combined DPS, long-gap share changes) → factors. It does
not call the network and does not write the database; only SELECTs the
adjustment tables from an isolated DB copy.

The output is a timestamped per-asset payload plus a capture ledger with an
explicit state for every asset. `--db` chooses the data arm (rows table vs
legacy); `--resume` skips assets already written.

Usage:
  python tools/ra365_round27_product_capture.py \
      --cache D:/BorsTerminal-tmp/ra365_round18/cache/tsetmc_csv \
      --cohort D:/BorsTerminal-tmp/ra365_round18/cohort.jsonl \
      --db D:/BorsTerminal-tmp/r22_test/market.db \
      --out D:/BorsTerminal-tmp/r27_live/product_rows [--limit N] [--resume]
"""
import argparse
import csv
import hashlib
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--cohort", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--shard", default="0/1", help="i/n — process every n-th asset starting at i")
    ap.add_argument("--asset-id", default="", help="comma-separated asset ids to capture")
    a = ap.parse_args()
    os.environ["BORS_DB"] = a.db
    os.environ.setdefault("BORS_NO_FETCH_LOOPS", "1")
    import symbol_identity as SI
    _slot_cache = {}
    _orig_slot = SI._slot
    def _static_slot(conn):
        # read-only capture: the DB never changes, so build the identity map once
        key = getattr(conn, "database", None) or "db"
        slot = _slot_cache.get(key)
        if slot is None:
            slot = _orig_slot(conn)
            _slot_cache[key] = slot
        return slot
    SI._slot = _static_slot
    import api.chart as C
    C.DB_PATH = a.db
    os.makedirs(a.out, exist_ok=True)
    ledger_path = os.path.join(a.out, "capture-ledger.csv")
    done = set()
    if a.resume and os.path.exists(ledger_path):
        for r in csv.DictReader(open(ledger_path, encoding="utf-8-sig")):
            if r.get("state") == "SUCCESS":
                done.add(str(r["ra_asset_id"]))
    mode = "a" if a.resume and os.path.exists(ledger_path) else "w"
    lf = open(ledger_path, mode, encoding="utf-8-sig", newline="")
    lw = csv.writer(lf)
    if mode == "w":
        lw.writerow(["ra_asset_id", "symbol", "ins_code", "state", "candles",
                     "events", "source", "csv_sha256", "error"])
    only = {x.strip() for x in a.asset_id.split(",") if x.strip()}
    shard_i, shard_n = (int(x) for x in a.shard.split("/"))
    n = 0
    idx = -1
    t0 = time.time()
    for line in open(a.cohort, encoding="utf-8"):
        d = json.loads(line)
        aid = str(d.get("ra_asset_id"))
        sym = d.get("symbol") or ""
        ins = str(d.get("ins_code") or "")
        if only and aid not in only:
            continue
        idx += 1
        if shard_n > 1 and idx % shard_n != shard_i:
            continue
        if a.limit and n >= a.limit:
            break
        n += 1
        if aid in done:
            continue
        out_path = os.path.join(a.out, aid + ".json")
        csv_path = os.path.join(a.cache, ins + ".csv")
        if not os.path.exists(csv_path):
            lw.writerow([aid, sym, ins, "NO_TSETMC_CACHE", 0, 0, "", "", ""])
            continue
        try:
            text = open(csv_path, encoding="utf-8", errors="replace").read()
            candles, volumes, all_rows = C._parse_tsetmc_csv(text)
            if not candles:
                lw.writerow([aid, sym, ins, "EMPTY_PRODUCT", 0, 0, "", sha(csv_path), ""])
                continue
            adj, anchored = C._adjust_events_from_rows(all_rows)
            adj, sharp_n, amb_n = C._sharpen_events_with_ledger(sym, adj)
            times = [str(c["time"])[:10] for c in candles]
            adj, false_rej = C._filter_unproven_base_events(sym, adj, times=times)
            closings = C._candle_closings(candles)
            applied, rejected, factors, chain, cov = C._canonical_adjustment(
                sym, times, adj, closings=closings, gap_closings=closings)
            rejected = list(rejected) + list(false_rej)
            payload = {
                "asset_id": aid, "symbol": sym, "ins_code": ins,
                "priceBasis": "last", "priceBasisRequested": "last",
                "adjustSource": ("ledger+base-price-discontinuity"
                                 if any(e.get("source") in ("priceAdjust", "shareChange")
                                        for e in applied)
                                 else "base-price-discontinuity" if applied
                                 else "no-adjustment-event"),
                "candles": candles, "volumes": volumes,
                "factors": [{"time": t, "factor": f} for t, f in zip(times, factors)],
                "adjustEvents": applied, "adjustRejected": rejected,
                "adjustCapability": {"sharpened": sharp_n, "ambiguous": amb_n,
                                     "coverage": cov},
                "provenance": {
                    "engine": "current-main",
                    "csv_sha256": sha(csv_path),
                    "db_sha256": sha(a.db),
                    "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "path": "tsetmc_csv replay; no live bar; no network",
                },
            }
            json.dump(payload, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
            lw.writerow([aid, sym, ins, "SUCCESS", len(candles), len(applied),
                         payload["adjustSource"], sha(csv_path), ""])
        except Exception as e:  # noqa: BLE001
            lw.writerow([aid, sym, ins, "ERROR", 0, 0, "", "", str(e)[:200]])
        if n % 200 == 0:
            lf.flush()
            print("captured", n, "in", round(time.time() - t0, 1), "s", flush=True)
    lf.close()
    print("done", n, "assets in", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
