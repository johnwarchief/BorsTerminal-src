"""باتریِ ثابتِ سنجشِ عملکردِ مسیرِ تابلو/قیف — برایِ مقایسۀ «قبل/بعد».

چرا اسکریپت و نه دستورهایِ دستی: «بعد» فقط وقتی قابلِ باور است که همان سناریو،
همان ترتیب، همان اندازهٔ درخواست و همان ساعتِ monotonic درِ هر دور تکرار شود.
هر دور یک JSON می‌نویسد و هیچ عددی از دورِ دیگر قرض گرفته نمی‌شود.

سردکردنِ کش بینِ دو دور لازم است ⇒ ریگ را با --restart ریستارت می‌کنیم
(فقط پروسه‌ای که خودمان بالا آورده‌ایم).

اجرا:
  python tools/perf_market_hours_bench.py --port 8020 --label before \
      --out _scratch/.../bench-before.json
"""
import argparse
import json
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8020)
ap.add_argument("--label", default="run")
ap.add_argument("--out", default="")
ap.add_argument("--repeat", type=int, default=5)
ARGS = ap.parse_args()

BASE = "http://127.0.0.1:%d" % ARGS.port
# همان مسیرهایی که رابطِ واقعی درِ نشستِ باز می‌زند؛ ترتیب ثابت
PATHS = ["/api/market", "/api/funnel", "/api/mstat/board", "/api/market/delta"]


def timed(path, accept_encoding=None, headers=None):
    h = {"Accept": "application/json"}
    if accept_encoding:
        h["Accept-Encoding"] = accept_encoding
    if headers:
        h.update(headers)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE + path, headers=h),
                                    timeout=180) as r:
            body = r.read()
            return {"path": path, "ms": round((time.perf_counter() - t0) * 1000, 1),
                    "http": r.status, "bytes": len(body),
                    "x_cache": r.headers.get("X-Cache"), "etag": r.headers.get("ETag"),
                    "encoding": r.headers.get("Content-Encoding")}
    except urllib.error.HTTPError as e:
        return {"path": path, "ms": round((time.perf_counter() - t0) * 1000, 1),
                "http": e.code, "bytes": 0, "error": "HTTPError"}
    except Exception as e:
        return {"path": path, "ms": round((time.perf_counter() - t0) * 1000, 1),
                "http": None, "bytes": 0, "error": type(e).__name__}


def pctl(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    return s[min(len(s) - 1, int(len(s) * q))]


def main():
    out = {"label": ARGS.label, "port": ARGS.port, "base": BASE,
           "started_wall": time.time(), "python": sys.version.split()[0],
           "orjson": True, "steps": []}
    try:
        import orjson  # noqa: F401
    except Exception:
        out["orjson"] = False

    # ۱) سرد: اولینِ درخواستِ بعدِ بالا آمدنِ ریگ (مسیرِ همگامِ build)
    cold = timed("/api/market", "identity")
    out["steps"].append({"phase": "cold-first-request", "identity": [cold]})

    # ۲) گرم، identity و gzip، رویِ هر مسیرِ پرتکرار
    for enc in ("identity", "gzip"):
        rows = [timed(p, enc) for p in PATHS for _ in range(ARGS.repeat)]
        by = {}
        for r in rows:
            by.setdefault(r["path"], []).append(r)
        out["steps"].append({"phase": "warm-" + enc, "repeat": ARGS.repeat,
                             "paths": {p: {"n": len(v),
                                           "p50_ms": pctl([x["ms"] for x in v], 0.5),
                                           "p95_ms": pctl([x["ms"] for x in v], 0.95),
                                           "max_ms": max(x["ms"] for x in v),
                                           "bytes": sorted({x.get("bytes") for x in v}),
                                           "x_cache": sorted({str(x.get("x_cache")) for x in v}),
                                           "encoding": sorted({str(x.get("encoding")) for x in v}),
                                           "errors": sorted({str(x.get("error")) for x in v if x.get("error")})}
                                       for p, v in by.items()}})

    # ۳) همزمانیِ ۶ درخواستِ کش‌خورده (هزینۀِ هرِ درخواست رویِ کش)
    conc = subprocess.run([sys.executable,
                           __file__.replace("perf_market_hours_bench.py",
                                            "perf_market_concurrency_probe.py"),
                           "--port", str(ARGS.port), "--n", "6"],
                          capture_output=True, text=True, timeout=600)
    try:
        out["steps"].append({"phase": "concurrent-6-cached",
                             **json.loads(conc.stdout)})
    except Exception:
        out["steps"].append({"phase": "concurrent-6-cached",
                             "raw": conc.stdout[-400:], "err": conc.stderr[-300:]})

    # ۴) ۳۰۴: بدنهٔ بی‌تغییر باید صفر بایت برگرداند
    etag = cold.get("etag")
    if etag:
        r304 = timed("/api/market", "identity", {"If-None-Match": etag})
        out["steps"].append({"phase": "conditional-304", "result": r304})

    out["summary"] = {"total_requests": sum(p["n"] for s in out["steps"]
                                            if s["phase"].startswith("warm-")
                                            for p in s["paths"].values())}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if ARGS.out:
        with open(ARGS.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
