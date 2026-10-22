#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase-2 FTS API benchmark: GETs + the exact POST /api/funnel body the UI sends.

Read-only. Records cold/first call, min/p50/p95/max, gzip/raw bytes, ETag, and
POST conditional behavior (the UI currently sends no If-None-Match).

usage:
  python tools/performance/phase2_fts_api.py --reps 30 \
      --out artifacts/performance/phase2/fts-api-baseline.json
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FUNNEL_BODY = {
    "preset": "trend",
    "chain": [],
    "logic": "and",
    "fund_mode": "standard",
    "tech_chain": [],
    "strategy_settings": {},
    "exceptions": {},
    "drop_suffix": True,
}

GETS = [
    ("funnel registry", "/api/funnel/registry", 30),
    ("funnel trace فولاد", "/api/funnel/trace?symbol=%D9%81%D9%88%D9%84%D8%A7%D8%AF&preset=trend&chain=&fund_mode=standard&exceptions=%7B%7D&drop_suffix=true", 10),
    ("fts plan فولاد", "/api/fts/%D9%81%D9%88%D9%84%D8%A7%D8%AF", 10),
    ("fts config", "/api/fts/config", 30),
    ("key levels فولاد", "/api/chart/%D9%81%D9%88%D9%84%D8%A7%D8%AF/key-levels", 10),
    ("market closes", "/api/market/closes", 30),
    ("screener", "/api/screener", 10),
]


def _pct(v, q):
    s = sorted(v)
    return s[min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))]


def call(base, path, timeout=180.0, body=None, headers=None):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        method="POST" if body is not None else "GET",
        headers={
            "Accept-Encoding": "gzip",
            "User-Agent": "bors-phase2-fts/1",
            **({"Content-Type": "application/json"} if body is not None else {}),
            **(headers or {}),
        },
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw_wire = r.read()
            status = r.status
            etag = r.headers.get("ETag")
            xcache = r.headers.get("X-Cache")
    except urllib.error.HTTPError as e:
        raw_wire = e.read() or b""
        status = e.code
        etag = e.headers.get("ETag")
        xcache = e.headers.get("X-Cache")
    ms = (time.perf_counter() - t0) * 1000.0
    if raw_wire[:2] == b"\x1f\x8b":
        gz = len(raw_wire)
        try:
            raw = gzip.decompress(raw_wire)
        except OSError:
            raw = raw_wire
    else:
        gz = len(raw_wire)
        raw = raw_wire
    digest = None
    if body is None and status == 200:
        try:
            obj = json.loads(raw.decode("utf-8", "replace"))
            if isinstance(obj, dict):
                obj.pop("cached_for_ms", None)
            digest = hashlib.sha256(
                json.dumps(obj, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":")).encode("utf-8")).hexdigest()
        except Exception:
            digest = None
    return {"ms": ms, "status": status, "raw": len(raw), "gz": gz,
            "etag": etag, "x_cache": xcache, "digest": digest}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--reps", type=int, default=30)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = {
        "base": args.base,
        "git_commit": os.popen("git -C \"%s\" rev-parse HEAD" % ROOT.replace("\\", "/")).read().strip(),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "methods": "read-only GET/POST; POST body is the UI default funnel request",
        "gets": {}, "funnel_post": {},
    }

    for name, path, n in GETS:
        first = call(args.base, path)
        vals, statuses, digests = [], set(), set()
        for _ in range(n):
            r = call(args.base, path)
            vals.append(r["ms"])
            statuses.add(r["status"])
            if r["digest"]:
                digests.add(r["digest"])
            time.sleep(0.1)
        out["gets"][name] = {
            "path": path, "first_ms": round(first["ms"], 2),
            "first_status": first["status"], "first_raw": first["raw"],
            "first_gz": first["gz"], "first_etag": first["etag"],
            "p50_ms": round(statistics.median(vals), 2),
            "p95_ms": round(_pct(vals, 0.95), 2),
            "n": len(vals), "statuses": sorted(statuses),
            "digests": len(digests), "raw_bytes": first["raw"],
            "gzip_bytes": first["gz"],
        }
        print("%-20s first=%7.1fms p50=%7.1fms p95=%7.1fms status=%s raw=%s gz=%s etag=%s" % (
            name, first["ms"], out["gets"][name]["p50_ms"], out["gets"][name]["p95_ms"],
            sorted(statuses), first["raw"], first["gz"], bool(first["etag"])))

    # The exact POST the strategy tab sends. 10 repetitions: each body is ~7.5MB raw.
    first = call(args.base, "/api/funnel", body=FUNNEL_BODY)
    vals, digests, statuses = [], set(), set()
    last = first
    for _ in range(10):
        last = call(args.base, "/api/funnel", body=FUNNEL_BODY)
        vals.append(last["ms"])
        statuses.add(last["status"])
        if last["digest"]:
            digests.add(last["digest"])
        time.sleep(0.2)
    out["funnel_post"] = {
        "path": "/api/funnel", "body": FUNNEL_BODY,
        "first_ms": round(first["ms"], 2), "first_status": first["status"],
        "first_raw": first["raw"], "first_gz": first["gz"],
        "first_etag": first["etag"], "first_x_cache": first["x_cache"],
        "p50_ms": round(statistics.median(vals), 2),
        "p95_ms": round(_pct(vals, 0.95), 2),
        "n": len(vals), "statuses": sorted(statuses),
        "digests": len(digests), "raw_bytes": last["raw"], "gzip_bytes": last["gz"],
        "etag": last["etag"],
    }
    print("funnel POST          first=%7.1fms p50=%7.1fms p95=%7.1fms status=%s raw=%s gz=%s etag=%s" % (
        first["ms"], out["funnel_post"]["p50_ms"], out["funnel_post"]["p95_ms"],
        sorted(statuses), last["raw"], last["gz"], bool(last["etag"])))

    # Does the server support a conditional POST? The UI does not send one today.
    if last["etag"]:
        cond = call(args.base, "/api/funnel", body=FUNNEL_BODY,
                    headers={"If-None-Match": last["etag"]})
        out["funnel_post"]["conditional"] = {
            "status": cond["status"], "ms": round(cond["ms"], 2),
            "raw": cond["raw"], "gz": cond["gz"], "etag": cond["etag"],
        }
        print("funnel POST cond     status=%s ms=%.1f bytes=%s" % (
            cond["status"], cond["ms"], cond["gz"]))

    # GET path used by the UI after P2-R2 (same options in the query).
    from urllib.parse import urlencode
    get_path = "/api/funnel?" + urlencode({
        "preset": FUNNEL_BODY["preset"], "chain": "",
        "logic": FUNNEL_BODY["logic"], "fund_mode": FUNNEL_BODY["fund_mode"],
        "tech_chain": "", "strategy_settings": json.dumps(FUNNEL_BODY["strategy_settings"]),
        "exceptions": json.dumps(FUNNEL_BODY["exceptions"]),
        "drop_suffix": "true",
    })
    g_first = call(args.base, get_path)
    g_vals, g_digests, g_statuses = [], set(), set()
    g_last = g_first
    for _ in range(10):
        g_last = call(args.base, get_path)
        g_vals.append(g_last["ms"])
        g_statuses.add(g_last["status"])
        if g_last["digest"]:
            g_digests.add(g_last["digest"])
        time.sleep(0.2)
    out["funnel_get"] = {
        "path": get_path, "first_ms": round(g_first["ms"], 2),
        "first_raw": g_first["raw"], "first_gz": g_first["gz"],
        "first_etag": g_first["etag"],
        "p50_ms": round(statistics.median(g_vals), 2),
        "p95_ms": round(_pct(g_vals, 0.95), 2), "n": len(g_vals),
        "statuses": sorted(g_statuses), "digests": len(g_digests),
        "raw_bytes": g_last["raw"], "gzip_bytes": g_last["gz"], "etag": g_last["etag"],
    }
    if g_last["etag"]:
        gc = call(args.base, get_path, headers={"If-None-Match": g_last["etag"]})
        out["funnel_get"]["conditional"] = {
            "status": gc["status"], "ms": round(gc["ms"], 2),
            "gz": gc["gz"], "etag": gc["etag"],
        }
        print("funnel GET cond      status=%s ms=%.1f bytes=%s" % (
            gc["status"], gc["ms"], gc["gz"]))
    print("funnel GET           p50=%7.1fms p95=%7.1fms raw=%s gz=%s etag=%s" % (
        out["funnel_get"]["p50_ms"], out["funnel_get"]["p95_ms"], g_last["raw"], g_last["gz"], bool(g_last["etag"])))

    path = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("wrote", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
