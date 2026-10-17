"""همزمانیِ مسیرِ سردِ /api/market — یکِ ساختن یا N تا؟

چرا این سنجه لازم است: `_market_from_cache` درِ دو حالت `None` می‌دهد (کشِ
نداشته، و کهنه‌ترِ از `_MARKET_STALE_CEILING`) و `get_market` آن‌وقت **همگام و
بی‌قفل** می‌سازد. اگر شش پنل درِ یکِ لحظه همان درخواست را بزنند، شش بازسازیِ
۱٫۷ ثانیه‌ای رویِ یکِ CPU چهارهسته‌ای ساخته می‌شود. عددِ «چند تا ساخته شد» را
از سرِ خودِ سرویس می‌خوانیم: `X-Cache: MISS` یعنی همین درخواست ساخت،
`HIT/STALE` یعنی از بدنۀ دیگران برداشته است.

اجرا (ریگ را تازه بالا آورده باشید، کشِ سرد):
  python tools/perf_market_concurrency_probe.py --port 8020 --n 6
"""
import argparse
import json
import threading
import time
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8020)
ap.add_argument("--n", type=int, default=6)
ap.add_argument("--path", default="/api/market")
ap.add_argument("--out", default="")
ARGS = ap.parse_args()

URL = "http://127.0.0.1:%d%s" % (ARGS.port, ARGS.path)
results = []
lock = threading.Lock()
start = threading.Barrier(ARGS.n + 1)


def worker(i):
    start.wait()          # همه از یک لحظه بیرون بزنند (بی‌این، سنجه قفل می‌کرد)
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(URL, timeout=180) as r:
            body = r.read()
            rec = {"i": i, "ms": round((time.monotonic() - t0) * 1000, 1),
                   "http": r.status, "bytes": len(body),
                   "x_cache": r.headers.get("X-Cache"), "etag": r.headers.get("ETag"),
                   "ct": r.headers.get("content-type")}
    except Exception as e:
        rec = {"i": i, "ms": round((time.monotonic() - t0) * 1000, 1),
               "http": None, "error": type(e).__name__}
    with lock:
        results.append(rec)


def main():
    ts = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(ARGS.n)]
    for t in ts:
        t.start()
    start.wait()          # همه از یک لحظه بیرون بزنند
    t0 = time.monotonic()
    for t in ts:
        t.join(200)
    wall = round((time.monotonic() - t0) * 1000, 1)
    ms = sorted(r["ms"] for r in results)
    built = [r for r in results if r.get("x_cache") == "MISS"]
    out = {
        "port": ARGS.port, "path": ARGS.path, "n": ARGS.n,
        "wall_ms": wall, "per_request_ms": ms,
        "p50_ms": ms[len(ms) // 2] if ms else None,
        "max_ms": ms[-1] if ms else None,
        "builds_observed_MISS": len(built),
        "x_cache_counts": {k: sum(1 for r in results if r.get("x_cache") == k)
                           for k in {r.get("x_cache") for r in results}},
        "sum_of_server_seconds": round(sum(ms) / 1000.0, 2),
        "results": sorted(results, key=lambda r: r["i"]),
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if ARGS.out:
        with open(ARGS.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
