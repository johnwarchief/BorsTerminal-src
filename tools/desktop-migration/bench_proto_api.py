#!/usr/bin/env python3
"""Focused read-only API probe for the two M1 prototype pages.

The full tools/performance/bench_api.py covers 39 paths; this probe isolates
the paths the market board and technical page actually call, so shell runs and
data-path numbers share one small, repeatable sample set.

usage:
  python tools/desktop-migration/bench_proto_api.py --base http://127.0.0.1:8102 \
      --reps 10 --out artifacts/desktop-migration/api-proto.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import statistics
import time
import urllib.parse
import urllib.request


def fetch(url: str) -> tuple[int, int, int, float, bytes]:
    req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip", "Accept": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=180) as res:
        raw = res.read()
        status = res.status
        enc = (res.headers.get("Content-Encoding") or "").lower()
        transfer = len(raw)
        body = gzip.decompress(raw) if "gzip" in enc else raw
    return status, transfer, len(body), (time.perf_counter() - t0) * 1000, body


def pct(values, q):
    vals = sorted(values)
    return round(vals[min(len(vals) - 1, int(q * len(vals)))], 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8102")
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--out", default="artifacts/desktop-migration/api-proto.json")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    rev = None
    try:
        status, _, _, _, body = fetch(base + "/api/market/delta?since=-1")
        rev = json.loads(body).get("rev")
    except Exception:
        pass

    symbol = urllib.parse.quote("فولاد")
    paths = [
        ("version", "/api/update/version"),
        ("market full", "/api/market"),
        ("market delta", f"/api/market/delta?since={rev if rev is not None else -1}"),
        ("market row", f"/api/market/row?symbol={symbol}"),
        ("chart", f"/api/chart/{symbol}"),
        ("history fallback", f"/api/history/{symbol}"),
    ]

    out = {"base": base, "reps": args.reps, "rev": rev, "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "paths": []}
    for name, path in paths:
        samples, transfer, decoded, status_code = [], [], [], None
        try:
            status, t, d, ms, _ = fetch(base + path)  # warm cache / measure cold separately
            status_code = status
            cold_ms = round(ms, 1)
            for _ in range(args.reps):
                status, t, d, ms, _ = fetch(base + path)
                samples.append(ms)
                transfer.append(t)
                decoded.append(d)
                status_code = status
            out["paths"].append({
                "name": name,
                "path": path,
                "status": status_code,
                "coldMs": cold_ms,
                "minMs": round(min(samples), 1),
                "p50Ms": pct(samples, 0.5),
                "p95Ms": pct(samples, 0.95),
                "maxMs": round(max(samples), 1),
                "transferKB": round(statistics.median(transfer) / 1024),
                "decodedKB": round(statistics.median(decoded) / 1024),
                "samplesMs": [round(x, 1) for x in samples],
            })
            print(name, out["paths"][-1]["p50Ms"], out["paths"][-1]["p95Ms"], out["paths"][-1]["transferKB"])
        except Exception as exc:
            out["paths"].append({"name": name, "path": path, "error": str(exc)[:400]})
            print(name, "ERROR", exc)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("OUT", args.out)


if __name__ == "__main__":
    main()
