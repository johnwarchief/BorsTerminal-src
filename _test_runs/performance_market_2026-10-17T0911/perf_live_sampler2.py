"""Live market-hours latency sampler v2 — one thread per endpoint.

v1 timed each call correctly but ran them sequentially, so a 60 s /api/screener
hang blinded every other endpoint for that window (a harness artifact, not a
product one). Here each endpoint keeps its own cadence in its own thread, so one
stall cannot hide the others. Read-only; never talks to TSETMC/CODAL directly.

Usage: python perf_live_sampler2.py --port 8000 --out live-8000-b.jsonl --minutes 150
"""
import argparse
import json
import threading
import time
import urllib.error
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8000)
ap.add_argument("--out", default="live-b.jsonl")
ap.add_argument("--minutes", type=float, default=150.0)
ap.add_argument("--timeout", type=float, default=90.0)
ARGS = ap.parse_args()

BASE = "http://127.0.0.1:%d" % ARGS.port
# path -> seconds between calls; kept at or above what one open UI tab already
# asks for, so the rig does not multiply the app's own traffic
PLAN = {
    "/api/market": 10,
    "/api/market/delta": 10,
    "/api/market/sync-state": 30,
    "/api/mstat/board": 30,
    "/api/screener": 60,
    "/api/funnel": 60,
    "/api/chart-db/%D8%B4%D9%BE%D9%86%D8%A7": 60,   # شپنا
}

_lock = threading.Lock()
_fh = open(ARGS.out, "a", encoding="utf-8")
_deadline = time.monotonic() + ARGS.minutes * 60.0
_counts = {}


def write(rec):
    with _lock:
        _fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        _fh.flush()


def one(path):
    t0 = time.monotonic()
    wall = time.time()
    rec = {"path": path, "wall": wall, "mono": round(t0, 3)}
    try:
        req = urllib.request.Request(BASE + path, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=ARGS.timeout) as r:
            body = r.read()
            rec["ms"] = round((time.monotonic() - t0) * 1000.0, 1)
            rec["http"] = r.status
            rec["bytes"] = len(body)
            ct = (r.headers.get("content-type") or "").split(";")[0]
            rec["ct"] = ct
            if "json" not in ct:                       # SPA fallback is not an endpoint
                rec["note"] = "NOT_JSON"
                return
            try:
                d = json.loads(body.decode("utf-8", "replace"))
            except Exception as e:
                rec["note"] = "unparseable:%s" % type(e).__name__
                return
            if isinstance(d, dict):
                meta = d.get("meta") if isinstance(d.get("meta"), dict) else {}
                for k in ("rev", "count", "status", "cached", "age_s", "took_ms",
                          "source", "mode", "server_time", "updated_at"):
                    if k in d:
                        rec["top_" + k] = d[k]
                for k in ("d_even", "h_even", "updated", "fetched_at", "stale",
                          "generated_at", "elapsed_ms", "build_ms"):
                    if k in meta:
                        rec["meta_" + k] = meta[k]
    except urllib.error.HTTPError as e:
        rec.update(ms=round((time.monotonic() - t0) * 1000.0, 1), http=e.code, bytes=0,
                   error="HTTPError")
    except Exception as e:
        rec.update(ms=round((time.monotonic() - t0) * 1000.0, 1), http=None, bytes=0,
                   error=type(e).__name__)
    finally:
        write(rec)


def loop(path, every):
    n = 0
    while time.monotonic() < _deadline:
        t0 = time.monotonic()
        one(path)
        n += 1
        with _lock:
            _counts[path] = n
        time.sleep(max(0.5, every - (time.monotonic() - t0)))


def main():
    threads = [threading.Thread(target=loop, args=(p, s), daemon=True) for p, s in PLAN.items()]
    for t in threads:
        t.start()
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(30)
            with _lock:
                write({"_heartbeat": True, "wall": time.time(),
                       "counts": dict(_counts),
                       "mono": round(time.monotonic(), 1)})
    except KeyboardInterrupt:
        pass
    with _lock:
        write({"_done": True, "wall": time.time(), "counts": dict(_counts)})
    _fh.close()


if __name__ == "__main__":
    main()
