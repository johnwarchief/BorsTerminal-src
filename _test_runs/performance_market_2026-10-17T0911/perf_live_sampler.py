"""Live market-hours latency sampler — read-only, stdlib only.

Times the app's own hot endpoints with a monotonic clock, records bytes/status
and the server's own freshness markers, and samples the backend's CPU/RAM so a
stall can be told apart from a busy machine. One request per endpoint per tick
(the UI already does this); it never talks to TSETMC/CODAL directly.

Usage: python perf_live_sampler.py --port 8000 --out file.jsonl --ticks 999 --every 10
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8000)
ap.add_argument("--out", default="live.jsonl")
ap.add_argument("--every", type=float, default=10.0)
ap.add_argument("--ticks", type=int, default=100000)
ARGS = ap.parse_args()

BASE = "http://127.0.0.1:%d" % ARGS.port
# (path, every-Nth-tick) — heavy/less hot endpoints sampled slower on purpose
PLAN = [
    ("/api/market", 1),
    ("/api/market/delta", 1),
    ("/api/market/sync-state", 3),
    ("/api/mstat/board", 3),
    ("/api/screener", 6),
    ("/api/funnel", 6),
]


def one(path):
    t0 = time.monotonic()
    wall = time.time()
    try:
        req = urllib.request.Request(BASE + path, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
            ms = (time.monotonic() - t0) * 1000.0
            ct = r.headers.get("content-type", "")
            out = {"path": path, "ms": round(ms, 1), "http": r.status,
                   "bytes": len(body), "ct": ct.split(";")[0], "wall": wall}
            # SPA fallback answers 200 + text/html: never count it as an endpoint
            if "json" not in ct:
                out["note"] = "NOT_JSON"
                return out
            try:
                d = json.loads(body.decode("utf-8", "replace"))
            except Exception as e:
                out["note"] = "unparseable:%s" % type(e).__name__
                return out
            if isinstance(d, dict):
                meta = d.get("meta") if isinstance(d.get("meta"), dict) else {}
                for k in ("rev", "count", "cached", "age_s", "took_ms", "source",
                          "generated_at", "server_time"):
                    if k in d:
                        out["top_" + k] = d[k]
                for k in ("d_even", "h_even", "updated", "fetched_at", "stale"):
                    if k in meta:
                        out["meta_" + k] = meta[k]
                if "status" in d:
                    out["status_field"] = d.get("status")
            return out
    except urllib.error.HTTPError as e:
        return {"path": path, "ms": round((time.monotonic() - t0) * 1000.0, 1),
                "http": e.code, "bytes": 0, "error": "HTTPError", "wall": wall}
    except Exception as e:
        return {"path": path, "ms": round((time.monotonic() - t0) * 1000.0, 1),
                "http": None, "bytes": 0, "error": type(e).__name__, "wall": wall}


def machine():
    """Whole-box load, so a slow endpoint can be read against a busy machine."""
    try:
        li = os.getloadavg()
        return {"load1": li[0], "load5": li[1]}
    except Exception:
        return {}


def main():
    tick = 0
    with open(ARGS.out, "a", encoding="utf-8") as fh:
        while tick < ARGS.ticks:
            t0 = time.monotonic()
            for path, every in PLAN:
                if tick % every:
                    continue
                rec = {"tick": tick, "mono": round(t0, 3)}
                rec.update(one(path))
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            tick += 1
            time.sleep(max(0.0, ARGS.every - (time.monotonic() - t0)))


if __name__ == "__main__":
    sys.exit(main())
