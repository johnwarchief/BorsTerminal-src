# -*- coding: utf-8 -*-
"""Rhythm + gzip-policy probe for `/api/funnel` and `/api/market`.

The before/after bench fires samples back-to-back, which is *not* how the
interface polls. This probe answers the questions the bench cannot:

  1. At the UI's real rhythms (5s during a technical scan, 20s in session,
     300s closed) does the funnel body cache actually hit, and is the served
     body byte-identical?
  2. Across the TTL, what exactly changes in the body — data, or only the
     `as_of` stamp? (This is why an ETag can exist and still never repeat.)
  3. Does a conditional request actually return 304 with zero bytes, per
     method? The interface calls the funnel with POST, which never revalidates.
  4. Wire bytes vs decoded bytes per gzip level, with the decoded hash proving
     the level changes the stream and never the payload.
  5. Server RSS and CPU-time deltas around the whole sequence.

usage: python tools/perf_cache_rhythm_gzip_probe.py --port 8020 --pid 1234 \
           --label gz1 --out probe.json
"""
import argparse
import gzip
import hashlib
import io
import json
import subprocess
import time
import urllib.error
import urllib.request

AP = argparse.ArgumentParser()
AP.add_argument("--port", type=int, default=8020)
AP.add_argument("--pid", type=int, default=0)
AP.add_argument("--label", default="gz1")
AP.add_argument("--out", default="")
AP.add_argument("--ttl", type=float, default=8.0, help="TTL_S of the funnel cache")
ARGS = AP.parse_args()

BASE = "http://127.0.0.1:%d" % ARGS.port

# همان بدنه‌ای که رابط می‌فرستد (features/master/api/useFtsFunnel.ts:163-172)
FUNNEL_BODY = {"preset": "trend", "chain": [], "logic": "and",
               "fund_mode": "standard", "exceptions": {}, "drop_suffix": True}

VOLATILE = ("as_of", "computed_at", "generated_at", "server_now", "now", "ts", "age_ms",
            "payload_age_s", "asof_wall", "elapsed")


def strip_volatile(obj):
    """عمقاً کلیدهایِ مُهرِ زمان را حذف می‌کند تا بماند «داده عوض شد یا فقط ساعت»."""
    if isinstance(obj, dict):
        return {k: strip_volatile(v) for k, v in sorted(obj.items()) if k not in VOLATILE}
    if isinstance(obj, list):
        return [strip_volatile(v) for v in obj]
    return obj


def canon_sha(obj):
    return hashlib.sha256(json.dumps(strip_volatile(obj), sort_keys=True,
                                     ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def raw_sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


def rss_cpu(pid):
    if not pid:
        return {}
    ps = ("$p=Get-Process -Id %d;"
          " '{0}|{1}' -f [int]$p.TotalProcessorTime.TotalMilliseconds,$p.WorkingSet64" % pid)
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        cpu_ms, ws = out.split("|")
        return {"cpu_ms": int(cpu_ms), "rss_mb": round(int(ws) / 1048576.0, 1)}
    except Exception as e:
        return {"cpu_error": type(e).__name__}


def main():
    res = {"label": ARGS.label, "base": BASE, "ttl_assumed": ARGS.ttl,
           "funnel_body": FUNNEL_BODY, "steps": []}

    def step(name, method, path, body=None, gz=True, headers=None, sleep_before=0.0):
        if sleep_before:
            time.sleep(sleep_before)
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(BASE + path,
                                         data=(json.dumps(body).encode() if body else None),
                                         headers={"Accept": "application/json",
                                                  **({"Accept-Encoding": "gzip"} if gz else {}),
                                                  **({"Content-Type": "application/json"} if body else {}),
                                                  **(headers or {})},
                                         method=method)
            with urllib.request.urlopen(req, timeout=180) as r:
                blob = r.read()
                status, hd = r.status, {k.lower(): v for k, v in r.headers.items()}
        except urllib.error.HTTPError as e:
            blob = b"" if e.code == 304 else e.read()
            status, hd = e.code, {k.lower(): v for k, v in e.headers.items()}
        ms = round((time.perf_counter() - t0) * 1000, 1)
        wire = len(blob)
        if hd.get("content-encoding") == "gzip":
            blob = gzip.decompress(blob)
        dec = json.loads(blob.decode("utf-8")) if blob else None
        res["steps"].append({"name": name, "method": method, "path": path, "gzip": gz,
                             "ms": ms, "status": status, "wire_bytes": wire,
                             "enc": hd.get("content-encoding", "identity"),
                             "x_cache": hd.get("x-cache", ""), "etag": hd.get("etag", ""),
                             "decoded_bytes": len(blob),
                             "raw_sha": raw_sha(blob) if blob else "",
                             "data_sha": canon_sha(dec) if dec is not None else "",
                             "as_of": (dec or {}).get("as_of") if isinstance(dec, dict) else None})

    start = rss_cpu(ARGS.pid)

    # ── ریتمِ واقعیِ قیف ────────────────────────────────────────────────────
    step("funnel-1-cold", "POST", "/api/funnel", FUNNEL_BODY)
    step("funnel-2-at+2s", "POST", "/api/funnel", FUNNEL_BODY, sleep_before=2.0)
    step("funnel-3-at+4s", "POST", "/api/funnel", FUNNEL_BODY, sleep_before=2.0)
    step("funnel-4-at+6s-5s-rhythm", "POST", "/api/funnel", FUNNEL_BODY, sleep_before=2.0)
    step("funnel-5-after-ttl", "POST", "/api/funnel", FUNNEL_BODY, sleep_before=ARGS.ttl + 2.0)
    step("funnel-6-after-ttl-again", "POST", "/api/funnel", FUNNEL_BODY, sleep_before=ARGS.ttl + 2.0)

    # ──_ETag/304 رویِ GET (همان مسیری که http.ts revalidate می‌کند) ──────────
    step("funnel-get-1", "GET", "/api/funnel?preset=trend&chain=")
    etag = res["steps"][-1]["etag"]
    step("funnel-get-2-conditional", "GET", "/api/funnel?preset=trend&chain=",
         headers={"If-None-Match": etag})
    step("funnel-post-conditional", "POST", "/api/funnel", FUNNEL_BODY,
         headers={"If-None-Match": etag})

    # ── سطحِ فشرده‌سازی: بایتِ سیم در برابرِ بایتِ تجزیه‌شده ─────────────────
    step("market-identity", "GET", "/api/market", gz=False)
    step("market-gzip", "GET", "/api/market")
    step("market-conditional-304", "GET", "/api/market",
         headers={"If-None-Match": res["steps"][-1]["etag"]})
    step("funnel-identity", "POST", "/api/funnel", FUNNEL_BODY, gz=False)
    step("funnel-gzip-again", "POST", "/api/funnel", FUNNEL_BODY)

    end = rss_cpu(ARGS.pid)

    s = {x["name"]: x for x in res["steps"]}
    res["verdict"] = {
        "funnel_hit_within_ttl": [bool(s["funnel-2-at+2s"]["x_cache"] == "HIT"),
                                  bool(s["funnel-3-at+4s"]["x_cache"] == "HIT"),
                                  bool(s["funnel-4-at+6s-5s-rhythm"]["x_cache"] == "HIT")],
        "funnel_body_identical_within_ttl":
            s["funnel-1-cold"]["raw_sha"] == s["funnel-4-at+6s-5s-rhythm"]["raw_sha"],
        "funnel_new_body_after_ttl":
            s["funnel-1-cold"]["raw_sha"] != s["funnel-5-after-ttl"]["raw_sha"],
        "funnel_data_identical_after_ttl":
            s["funnel-1-cold"]["data_sha"] == s["funnel-5-after-ttl"]["data_sha"],
        "as_of_changed_after_ttl":
            s["funnel-1-cold"]["as_of"] != s["funnel-5-after-ttl"]["as_of"],
        "etag_repeats_within_ttl":
            s["funnel-2-at+2s"]["etag"] == s["funnel-4-at+6s-5s-rhythm"]["etag"],
        "get_conditional_returns_304": s["funnel-get-2-conditional"]["status"] == 304,
        "post_conditional_returns_304": s["funnel-post-conditional"]["status"] == 304,
        "market_304_wire_bytes": s["market-conditional-304"]["wire_bytes"],
        "gzip_decodes_identically_market":
            s["market-identity"]["raw_sha"] == s["market-gzip"]["raw_sha"],
        "gzip_decodes_identically_funnel":
            s["funnel-identity"]["raw_sha"] == s["funnel-gzip-again"]["raw_sha"],
        "wire_market": {"identity": s["market-identity"]["wire_bytes"],
                        "gzip": s["market-gzip"]["wire_bytes"]},
        "wire_funnel": {"identity": s["funnel-identity"]["wire_bytes"],
                        "gzip": s["funnel-gzip-again"]["wire_bytes"]},
        "ms_market": {"identity": s["market-identity"]["ms"], "gzip": s["market-gzip"]["ms"]},
        "ms_funnel_cold": {"identity": s["funnel-identity"]["ms"],
                           "gzip": s["funnel-gzip-again"]["ms"]},
    }
    res["server_start"] = start
    res["server_end"] = end
    if start.get("cpu_ms") is not None and end.get("cpu_ms") is not None:
        res["verdict"]["server_cpu_ms_during_probe"] = end["cpu_ms"] - start["cpu_ms"]
        res["verdict"]["server_rss_mb_after"] = end.get("rss_mb")
        res["verdict"]["server_rss_mb_before"] = start.get("rss_mb")

    text = json.dumps(res, ensure_ascii=False, indent=1)
    if ARGS.out:
        io.open(ARGS.out, "w", encoding="utf-8").write(text)
    print(json.dumps(res["verdict"], ensure_ascii=False, indent=1))
    print("steps:")
    for x in res["steps"]:
        print("  %-30s %-4s %s %6s ms  wire=%-9s dec=%-9s xc=%-8s etag=%s" % (
            x["name"], x["method"], x["status"], x["ms"], x["wire_bytes"],
            x["decoded_bytes"], x["x_cache"], (x["etag"] or "-")[:18]))


if __name__ == "__main__":
    main()
