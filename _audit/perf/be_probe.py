"""PERF Stage 1b-B — endpoint baseline on the ACTUAL running runtimes.

For every endpoint the UI really calls, measures over N repetitions:
  * wall time (min / p50 / p95 / max)
  * raw body bytes and gzip bytes (Accept-Encoding: gzip)
  * ETag behaviour: a repeat with If-None-Match (304 cost vs full cost)
  * warm-vs-cold: the first call after a cache-busting window is reported apart

Nothing here writes to any database and nothing restarts a process. The
installed runtime (127.0.0.1:8001) is probed read-only through GETs only.

usage: PYTHONIOENCODING=utf-8 python _audit/perf/be_probe.py --reps 5
"""
import argparse
import gzip
import json
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque

POSTS = {}  # name -> (path, body) for POST endpoints


def _pct(vals, q):
    if not vals:
        return float("nan")
    s = sorted(vals)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def call(base, path, timeout=120.0):
    """GET path on base. Returns dict with ms, raw, gz, status, etag, body(first bytes)."""
    req = urllib.request.Request(
        base + urllib.parse.quote(path, safe="/?=&%,"),
        headers={"Accept-Encoding": "gzip", "User-Agent": "perf-probe/1"},
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = r.read()
            status = r.status
            etag = r.headers.get("ETag")
            ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        payload = e.read() or b""
        status = e.code
        etag = e.headers.get("ETag")
        ctype = e.headers.get("Content-Type", "")
    except Exception as e:                                    # noqa: BLE001
        return {"err": f"{type(e).__name__}: {e}", "ms": (time.perf_counter() - t0) * 1000.0}
    ms = (time.perf_counter() - t0) * 1000.0
    if payload[:2] == b"\x1f\x8b":
        gz = len(payload)
        try:
            raw = len(gzip.decompress(payload))
        except OSError:
            raw = gz
    else:
        gz = len(payload)
        raw = len(payload)
    body = None
    if "json" in ctype:
        try:
            body = json.loads(gzip.decompress(payload).decode("utf-8", "replace")
                              if payload[:2] == b"\x1f\x8b" else payload.decode("utf-8", "replace"))
        except Exception:                                     # noqa: BLE001
            body = None
    return {"ms": ms, "raw": raw, "gz": gz, "status": status, "etag": etag,
            "ctype": ctype, "body": body}


def conditional(base, path, etag):
    req = urllib.request.Request(
        base + urllib.parse.quote(path, safe="/?=&%,"),
        headers={"Accept-Encoding": "gzip", "If-None-Match": etag, "User-Agent": "perf-probe/1"},
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120.0) as r:
            n = len(r.read())
            return {"ms": (time.perf_counter() - t0) * 1000.0, "status": r.status, "bytes": n}
    except urllib.error.HTTPError as e:
        return {"ms": (time.perf_counter() - t0) * 1000.0, "status": e.code, "bytes": 0}
    except Exception as e:                                    # noqa: BLE001
        return {"ms": (time.perf_counter() - t0) * 1000.0, "status": -1, "bytes": 0,
                "err": f"{type(e).__name__}: {e}"}


def probe(base, name, path, reps, summarize=None):
    runs = []
    for i in range(reps):
        r = call(base, path)
        runs.append(r)
        if "err" in r:
            break
        if i + 1 < reps:
            time.sleep(0.35)                                  # let the 45s caches behave like real use, not a hammer
    ok = [r for r in runs if "err" not in r]
    out = {"name": name, "path": path, "reps": len(ok), "err": runs[-1].get("err")}
    if not ok:
        print(f"  {name:<28} ERROR {out['err']}")
        return out
    ms = [r["ms"] for r in ok]
    out.update(first_ms=ms[0], min_ms=min(ms), p50=_pct(ms, 0.50), p95=_pct(ms, 0.95),
               max_ms=max(ms), raw=ok[0]["raw"], gz=ok[0]["gz"], status=ok[0]["status"],
               etag=bool(ok[0]["etag"]))
    if ok[0]["etag"]:
        out["reval"] = conditional(base, path, ok[0]["etag"])
    if summarize and ok[0]["body"] is not None:
        out["extra"] = summarize(ok[0]["body"])
    print(f"  {name:<28} {ok[0]['status']}  first={ms[0]:7.0f}ms p50={out['p50']:7.0f} "
          f"p95={out['p95']:7.0f} max={max(ms):7.0f}  raw={out['raw']:>9,} gz={out['gz']:>8,}"
          + (f"  etag304={out['reval']['status']}/{out['reval']['bytes']}B@{out['reval']['ms']:.0f}ms"
             if out.get("reval") else "")
          + (f"  {out['extra']}" if out.get("extra") else ""))
    return out


def concurrent(base, path, n):
    """n simultaneous identical GETs — what several tabs/observers do."""
    res = deque(maxlen=n)

    def worker():
        res.append(call(base, path))
    ths = [threading.Thread(target=worker) for _ in range(n)]
    t0 = time.perf_counter()
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    wall = (time.perf_counter() - t0) * 1000.0
    ms = [r["ms"] for r in res if "err" not in r]
    return wall, (min(ms) if ms else -1), (max(ms) if ms else -1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--only", default="")
    ap.add_argument("--dev-only", action="store_true",
                    help="skip the installed runtime (its code is untouched)")
    args = ap.parse_args()

    bases = {"dev-8000": "http://127.0.0.1:8000", "installed-8001": "http://127.0.0.1:8001"}
    if args.dev_only:            # the installed build is untouched code
        bases = {k: v for k, v in bases.items() if k == "dev-8000"}
    results = {}

    for bname, base in bases.items():
        if not call(base, "/api/live-stats", timeout=5.0).get("status"):
            print(f"[{bname}] not reachable, skipping")
            continue
        print(f"\n=== {bname}  {base}  ({args.reps} reps each) ===")
        rows = []
        rows.append(probe(base, "market full", "/api/market", args.reps,
                          lambda b: f"rows={len(b.get('data') or [])} rev={b.get('rev')}"))
        # delta needs a REAL since from the UI path
        m = call(base, "/api/market")
        rev = (m.get("body") or {}).get("rev")
        if isinstance(rev, int):
            rows.append(probe(base, "market delta(since=rev)", f"/api/market/delta?since={rev}",
                              args.reps, lambda b: f"status={b.get('status')} rows={len(b.get('rows') or [])}"))
            rows.append(probe(base, "market delta(stale rev)", f"/api/market/delta?since={rev + 10**7}",
                              2))
        else:
            print("  !! no numeric rev in /api/market — delta not measured")
        rows.append(probe(base, "market sync-state", "/api/market/sync-state", args.reps))
        rows.append(probe(base, "live-stats", "/api/live-stats", args.reps))
        rows.append(probe(base, "mstat board", "/api/mstat/board", args.reps))
        rows.append(probe(base, "mstat summary", "/api/mstat/summary", args.reps))
        rows.append(probe(base, "mstat mainwatch", "/api/mstat/mainwatch?group=eq_all&industry=", args.reps))
        rows.append(probe(base, "mstat treemap", "/api/mstat/treemap?group=eq_all&industry=&metric=volume", args.reps))
        rows.append(probe(base, "mstat tops", "/api/mstat/tops?group=eq_all", args.reps))
        rows.append(probe(base, "mstat histogram", "/api/mstat/histogram?group=eq_all", args.reps))
        rows.append(probe(base, "mstat timeline", "/api/mstat/timeline?mode=cum", args.reps))
        rows.append(probe(base, "mstat phases", "/api/mstat/phases", args.reps))
        rows.append(probe(base, "mstat smart-money", "/api/mstat/smart-money", args.reps))
        rows.append(probe(base, "mstat depth", "/api/mstat/depth?group=eq_all", args.reps))
        rows.append(probe(base, "mstat thermometer", "/api/mstat/thermometer?group=eq_all", args.reps))
        rows.append(probe(base, "mstat gold", "/api/mstat/gold?history_days=60", args.reps))
        rows.append(probe(base, "mstat indexcards", "/api/mstat/indexcards?days=60", args.reps))
        rows.append(probe(base, "mstat industries", "/api/mstat/industries", args.reps))
        rows.append(probe(base, "chart one symbol", "/api/chart/خوز", 3))
        rows.append(probe(base, "chart second symbol", "/api/chart/فولاد", 3))
        rows.append(probe(base, "chart same symbol again", "/api/chart/خوز", 3))
        rows.append(probe(base, "chart key-levels", "/api/chart/خوز/key-levels", 2))
        rows.append(probe(base, "mstat series (3 sym)", "/api/mstat/series?symbols=خوز,فولاد,تاپيستا&days=90", 2))
        rows.append(probe(base, "fts one symbol", "/api/fts/خوز", 2))
        rows.append(probe(base, "screener", "/api/screener", 3))
        rows.append(probe(base, "funnel registry", "/api/funnel/registry", 3))
        rows.append(probe(base, "fts config", "/api/fts/config", 3))
        rows.append(probe(base, "fundamental one", "/api/fundamental/خوز", 3))
        rows.append(probe(base, "index tedpix", "/api/index/tedpix?limit=0", 3))
        rows.append(probe(base, "watchlist", "/api/watchlist", 3))

        # concurrency: identical requests at once (multi-tab / multi-observer)
        for path, label in (("/api/market", "market x4"), ("/api/mstat/board", "mstat board x4")):
            wall, lo, hi = concurrent(base, path, 4)
            print(f"  {label:<28} 4 concurrent: wall={wall:7.0f}ms  fastest={lo:7.0f} slowest={hi:7.0f}")
            results.setdefault(bname, {})[label] = {"wall_ms": wall, "min_ms": lo, "max_ms": hi}
        results[bname] = {r["name"]: {k: v for k, v in r.items() if k != "body"} for r in rows if r}

    with open("_audit/perf/BE_BASELINE.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("\nwrote _audit/perf/BE_BASELINE.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
