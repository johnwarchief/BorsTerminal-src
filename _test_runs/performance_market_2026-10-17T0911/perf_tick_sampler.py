"""تک‌نخ، timeoutِ کوتاه: هیچ اندپوینتی حلقه را کور نمی‌کند (نسخۀ ۲ بی‌صدا خوابید)."""
import json, sys, time, urllib.request, urllib.error
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
OUT = sys.argv[2] if len(sys.argv) > 2 else "ticks.jsonl"
MINUTES = float(sys.argv[3]) if len(sys.argv) > 3 else 60
PATHS = ["/api/market/delta", "/api/market", "/api/mstat/board", "/api/market/sync-state"]
deadline = time.monotonic() + MINUTES * 60
fh = open(OUT, "a", encoding="utf-8")
while time.monotonic() < deadline:
    for p in PATHS:
        t0 = time.perf_counter()
        try:
            r = urllib.request.urlopen("http://127.0.0.1:%d%s" % (PORT, p), timeout=12)
            b = r.read()
            rec = {"wall": time.time(), "path": p, "ms": round((time.perf_counter()-t0)*1000, 1),
                   "http": r.status, "bytes": len(b), "xc": r.headers.get("X-Cache")}
        except urllib.error.HTTPError as e:
            rec = {"wall": time.time(), "path": p, "ms": round((time.perf_counter()-t0)*1000, 1),
                   "http": e.code, "bytes": 0}
        except Exception as e:
            rec = {"wall": time.time(), "path": p, "ms": round((time.perf_counter()-t0)*1000, 1),
                   "http": None, "error": type(e).__name__}
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n"); fh.flush()
    time.sleep(20)
fh.close()
