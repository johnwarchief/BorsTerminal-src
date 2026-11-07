#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only HTTP benchmark for the UI paths BorsTerminal actually calls.

Derived from `_audit/perf/be_probe.py` (the prior mission's validated probe),
with three additions required by the 2026-10-22 six-round mission:
  * >=30 samples per important path, reported as min/p50/p95/max + raw samples;
  * environment/commit/DB provenance written next to the numbers;
  * machine-readable output, so before/after comparisons are computed from
    files, not typed by hand.

It only issues GETs. No database writes, no sync endpoints, no process kills.

usage:
  python tools/performance/bench_api.py --base http://127.0.0.1:8000 \
      --reps 30 --out artifacts/performance/2026-10-22/api-baseline.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import platform
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# (name, path, reps_override) — mirrors the UI request inventory in
# frontend/src (see `grep -rhoE "'/api/..."`), restricted to read-only GETs.
PATHS = [
    ("market full", "/api/market", None),
    ("market delta", "/api/market/delta?since=-1", None),
    ("market sync-state", "/api/market/sync-state", None),
    ("live-stats", "/api/live-stats", None),
    ("universe live", "/api/universe/live", None),
    ("mstat summary", "/api/mstat/summary", None),
    ("mstat board", "/api/mstat/board", 10),
    ("mstat mainwatch", "/api/mstat/mainwatch?group=eq_all&industry=", None),
    ("mstat treemap", "/api/mstat/treemap?group=eq_all&industry=&metric=volume", None),
    ("mstat tops", "/api/mstat/tops?group=eq_all", None),
    ("mstat histogram", "/api/mstat/histogram?group=eq_all", None),
    ("mstat timeline", "/api/mstat/timeline?mode=cum", None),
    ("mstat phases", "/api/mstat/phases", None),
    ("mstat smart-money", "/api/mstat/smart-money", None),
    ("mstat depth", "/api/mstat/depth?group=eq_all", None),
    ("mstat thermometer", "/api/mstat/thermometer?group=eq_all", None),
    ("mstat gold", "/api/mstat/gold?history_days=60", None),
    ("mstat indexcards", "/api/mstat/indexcards?days=60", None),
    ("mstat industries", "/api/mstat/industries", None),
    ("mstat clientsplit", "/api/mstat/clientsplit?tab=all", None),
    ("mstat orderflows", "/api/mstat/orderflows", None),
    ("mstat ownership", "/api/mstat/ownership", None),
    ("chart one symbol", "/api/chart/%D9%81%D9%88%D9%84%D8%A7%D8%AF", 10),
    ("chart second symbol", "/api/chart/%D8%AE%D9%88%D8%AF%D8%B1%D9%88", 10),
    ("fts one symbol", "/api/fts/%D9%81%D9%88%D9%84%D8%A7%D8%AF", 10),
    ("screener", "/api/screener", 10),
    ("fundamental one", "/api/fundamental/%D9%81%D9%88%D9%84%D8%A7%D8%AF", 10),
    ("fundamental quarters", "/api/fundamental/%D9%81%D9%88%D9%84%D8%A7%D8%AF/quarters", 10),
    ("funnel registry", "/api/funnel/registry", None),
    ("funnel stages", "/api/funnel", 10),
    ("fts config", "/api/fts/config", None),
    ("index tedpix", "/api/index/tedpix?limit=0", None),
    ("watchlist", "/api/watchlist", None),
    ("watchlist matrix", "/api/watchlist/matrix", 10),
    ("selection symbols", "/api/selection/symbols", None),
    ("selection portfolio", "/api/selection/portfolio", None),
    ("calendar upcoming", "/api/calendar/upcoming", None),
    ("notifications sources", "/api/notifications/sources", None),
    ("mstat series", "/api/mstat/series?symbols=%D8%AE%D9%88%D8%B2,%D9%81%D9%88%D9%84%D8%A7%D8%AF,%D8%AA%D8%A7%D9%BE%DB%8C%D8%B3%D8%AA%D8%A7&days=90", 10),
]


def _pct(vals, q):
    if not vals:
        return float("nan")
    s = sorted(vals)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def call(base, path, timeout=180.0):
    req = urllib.request.Request(
        base + path,
        headers={"Accept-Encoding": "gzip", "User-Agent": "bors-perf-bench/1"},
    )
    t0 = time.perf_counter()
    status, payload, etag, ctype = -1, b"", None, ""
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
    except Exception as e:  # noqa: BLE001
        return {"err": f"{type(e).__name__}: {e}", "ms": (time.perf_counter() - t0) * 1000.0}
    ms = (time.perf_counter() - t0) * 1000.0
    if payload[:2] == b"\x1f\x8b":
        gz = len(payload)
        try:
            raw = len(gzip.decompress(payload))
        except OSError:
            raw = gz
    else:
        gz = raw = len(payload)
    body = None
    if "json" in ctype:
        try:
            decoded = gzip.decompress(payload) if payload[:2] == b"\x1f\x8b" else payload
            body = json.loads(decoded.decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001
            body = None
    return {"ms": ms, "raw": raw, "gz": gz, "status": status, "etag": etag, "body": body}


def first_sample(base, name, path):
    """Pre-change values of a single process: data age/row count, not timing."""
    r = call(base, path)
    b = r.get("body")
    if not isinstance(b, dict):
        return None
    out = {}
    for key in ("rev", "count", "computed_at", "data_age_s", "payloadAgeS", "cache_age_sec"):
        if key in b:
            out[key] = b[key]
    if isinstance(b.get("meta"), dict):
        for key in ("session_day", "data_age_s", "last_sync", "asof"):
            if key in b["meta"]:
                out[f"meta.{key}"] = b["meta"][key]
    return out or None


def _git(*args):
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:  # noqa: BLE001
        return None


def _db_provenance():
    path = os.path.join(ROOT, "market.db")
    try:
        st = os.stat(path)
        return {"path": "market.db", "bytes": st.st_size, "mtime": st.st_mtime}
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--reps", type=int, default=30)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--only", default="")
    ap.add_argument("--extra-sample", action="store_true",
                    help="separately record the first (cold) call before warm-up")
    args = ap.parse_args()

    only = [s for s in args.only.split(",") if s.strip()]
    paths = [row for row in PATHS if not only or any(o.lower() in row[0].lower() for o in only)]

    health = call(args.base, "/api/live-stats", timeout=10)
    if health.get("status") != 200:
        print(f"backend not reachable at {args.base}: {health.get('err') or health.get('status')}")
        return 2

    result = {
        "label": args.label,
        "base": args.base,
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor(),
        "db": _db_provenance(),
        "warmup": "one full call per path before sampling (cold call recorded separately when --extra-sample)",
        "paths": {},
    }

    for name, path, override in paths:
        reps = override or args.reps
        print(f"\n== {name} ({reps} samples) ==")
        cold = call(args.base, path) if args.extra_sample else None
        runs = []
        for i in range(reps):
            r = call(args.base, path)
            if "err" in r:
                print(f"  ERROR {r['err']}")
                break
            runs.append(r)
            if i + 1 < reps:
                time.sleep(0.2)
        ok = [r for r in runs if "err" not in r]
        if not ok:
            result["paths"][name] = {"path": path, "error": runs[-1].get("err") if runs else "no samples"}
            continue
        ms = [r["ms"] for r in ok]
        entry = {
            "path": path,
            "reps": len(ok),
            "cold_ms": round(cold["ms"], 2) if cold and "ms" in cold else None,
            "min_ms": round(min(ms), 2),
            "p50_ms": round(statistics.median(ms), 2),
            "p95_ms": round(_pct(ms, 0.95), 2),
            "max_ms": round(max(ms), 2),
            "mean_ms": round(statistics.fmean(ms), 2),
            "samples_ms": [round(x, 2) for x in ms],
            "status": ok[0]["status"],
            "raw_bytes": ok[0]["raw"],
            "gzip_bytes": ok[0]["gz"],
            "etag": bool(ok[0]["etag"]),
        }
        if args.extra_sample:
            entry["first_sample_values"] = first_sample(args.base, name, path)
        result["paths"][name] = entry
        print(f"  p50={entry['p50_ms']:.1f}ms p95={entry['p95_ms']:.1f}ms "
              f"min={entry['min_ms']:.1f} max={entry['max_ms']:.1f} "
              f"raw={entry['raw_bytes']:,} gz={entry['gzip_bytes']:,}"
              + (f" cold={entry['cold_ms']}ms" if entry["cold_ms"] is not None else ""))

    out = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
