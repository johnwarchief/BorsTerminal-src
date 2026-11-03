# -*- coding: utf-8 -*-
"""Map the real TTL window of `/api/funnel` and the hit rate at each UI rhythm.

The before/after bench fired samples back-to-back; the interface polls at 5s
(technical scan queued), 20s (open session) or 300s (closed). This probe asks
one request per second for `--seconds` and records, against the first build,
whether the answer came from the body cache and what `as_of` it carried.
"""
import argparse
import json
import re
import time
import urllib.error
import urllib.request

AP = argparse.ArgumentParser()
AP.add_argument("--port", type=int, default=8020)
AP.add_argument("--seconds", type=int, default=14)
AP.add_argument("--rhythm", type=float, default=0, help="فاصلۀ پولینگِ ثانیه؛ ۰ = مرزِ TTL")
AP.add_argument("--polls", type=int, default=10)
AP.add_argument("--out", default="")
ARGS = AP.parse_args()

BASE = "http://127.0.0.1:%d" % ARGS.port
BODY = {"preset": "trend", "chain": [], "logic": "and", "fund_mode": "standard",
        "exceptions": {}, "drop_suffix": True}


def one():
    req = urllib.request.Request(BASE + "/api/funnel", data=json.dumps(BODY).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            blob, hd, status = r.read(), {k.lower(): v for k, v in r.headers.items()}, r.status
    except urllib.error.HTTPError as e:
        blob, hd, status = e.read(), {k.lower(): v for k, v in e.headers.items()}, e.code
    ms = (time.perf_counter() - t0) * 1000.0
    # `as_of` مُهرِ زمانِ همانِ ساخت است؛ اگر عوض شود یعنی بدنه واقعاً دوباره
    # ساخته شده، نه اینکه کشِ کهنه سرو شده باشد.
    m = re.search(rb'"as_of"\s*:\s*"?(\d+)"?', blob)
    return {"ms": round(ms, 1), "status": status, "bytes": len(blob),
            "xc": hd.get("x-cache", ""), "etag": hd.get("etag", ""),
            "as_of": m.group(1).decode() if m else None}


def main():
    # حالتِ ۱: مرزِ واقعیِ TTL با یکِ درخواست در ثانیه
    if ARGS.rhythm <= 0:
        first = one()
        t_first = time.monotonic()
        rows = [dict(offset_s=0.0, **first)]
        for _ in range(ARGS.seconds):
            time.sleep(1.0)
            rows.append(dict(offset_s=round(time.monotonic() - t_first, 2), **one()))
        hits = [r["offset_s"] for r in rows if r["xc"] == "HIT"]
        miss = [r["offset_s"] for r in rows if r["xc"] == "MISS"]
        out = {"mode": "boundary", "first_etag": first["etag"], "first_as_of": first["as_of"],
               "hit_offsets_s": hits, "miss_offsets_s": miss,
               "last_hit_offset": (max(hits) if hits else None),
               "first_miss_offset": (min(miss) if miss else None), "rows": rows}
    else:
        # حالتِ ۲: ریتمِ واقعیِ رابط — N پولینگ با فاصلۀ T ثانیه، شمارشِ HIT/MISS
        t_first = time.monotonic()
        rows = []
        for _ in range(ARGS.polls):
            rows.append(dict(offset_s=round(time.monotonic() - t_first, 2), **one()))
            time.sleep(ARGS.rhythm)
        xc = {}
        for r in rows:
            xc[r["xc"] or "-"] = xc.get(r["xc"] or "-", 0) + 1
        out = {"mode": "rhythm", "rhythm_s": ARGS.rhythm, "polls": ARGS.polls,
               "x_cache_counts": xc,
               "distinct_etags": len(set(r["etag"] for r in rows)),
               "distinct_as_of": len(set(r["as_of"] for r in rows)),
               "ms_list": [r["ms"] for r in rows], "rows": rows}
    text = json.dumps(out, ensure_ascii=False, indent=1)
    if ARGS.out:
        io_open(ARGS.out, text)
    for r in out["rows"]:
        print("  +%6.2fs %-4s %7.1f ms xc=%-5s as_of=%s etag=%s" % (
            r["offset_s"], r["status"], r["ms"], r["xc"], r["as_of"], r["etag"][:14]))
    if out["mode"] == "boundary":
        print("last HIT at +%ss ; first MISS at +%ss (documented TTL_S = 8.0)" % (
            out["last_hit_offset"], out["first_miss_offset"]))
    else:
        n = out["polls"]
        hit = out["x_cache_counts"].get("HIT", 0)
        print("rhythm %ss x %s polls -> HIT %s / MISS %s ; distinct bodies %s (as_of %s)" % (
            out["rhythm_s"], n, hit, n - hit, out["distinct_etags"], out["distinct_as_of"]))


def io_open(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


if __name__ == "__main__":
    main()
