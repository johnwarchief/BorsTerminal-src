# a1_hol_probe.py — خطِ زمانِ درخواستِ ارزان درِ حینِ ساختِ سردِ قیف (POST در برابرِ GET)
# اجرا: PYTHONIOENCODING=utf-8 python a1_hol_probe.py --port 8020 --order PGGP --n 1
import argparse
import json
import statistics
import threading
import time
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8020)
ap.add_argument("--order", default="PGGP")
ap.add_argument("--n", type=int, default=1, help="درخواستِ هم‌زمانِ قیف درِ هر دور")
ap.add_argument("--cheap", default="/api/update/version")
ap.add_argument("--label", default="", help="شرحِ ریگ، مثلاً switchinterval=5ms")
ap.add_argument("--out", default="")
A = ap.parse_args()
BASE = "http://127.0.0.1:%d" % A.port


def call(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"} if data else {},
                                 method="POST" if data else "GET")
    t0 = time.perf_counter()
    r = urllib.request.urlopen(req, timeout=180)
    b = r.read()
    return t0, time.perf_counter(), r.status, r.headers.get("X-Cache"), b


def round_(verb):
    time.sleep(8.6)
    stop = threading.Event()
    samples = []

    def sampler():
        while not stop.is_set():
            t0, t1, st, _, _ = call(A.cheap)
            samples.append((t0, (t1 - t0) * 1000.0))
            time.sleep(0.05)
    fn = (lambda: call("/api/funnel", {"preset": "trend"})) if verb == "P" else \
         (lambda: call("/api/funnel?preset=trend"))
    res = [None] * A.n
    go = threading.Event()

    def one(i):
        go.wait()
        res[i] = fn()
    th = threading.Thread(target=sampler)
    th.start()
    time.sleep(0.3)
    ws = [threading.Thread(target=one, args=(i,)) for i in range(A.n)]
    for w in ws:
        w.start()
    tb = time.perf_counter()
    go.set()
    for w in ws:
        w.join()
    te = time.perf_counter()
    time.sleep(0.3)
    stop.set()
    th.join()
    during = [ms for (t0, ms) in samples if tb <= t0 <= te]
    before = [ms for (t0, ms) in samples if t0 < tb]
    try:
        tech = json.loads(res[0][4].decode()).get("tech_scan")
    except Exception:
        tech = None
    return {
        "verb": "POST" if verb == "P" else "GET",
        "cheap": A.cheap,
        "rig": A.label,
        "build_ms": round((te - tb) * 1000.0),
        "x_cache": [r[3] for r in res],
        "bytes": len(res[0][4]),
        "cheap_before_med": round(statistics.median(before), 1) if before else None,
        "cheap_during_n": len(during),
        "cheap_during_med": round(statistics.median(during), 1) if during else None,
        "cheap_during_max": round(max(during), 1) if during else None,
        "cheap_during_series": [round(x) for x in during],
        "tech_scan": tech,
    }


out = [round_(v) for v in A.order]
for r in out:
    print(json.dumps(r, ensure_ascii=False))
if A.out:
    with open(A.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
