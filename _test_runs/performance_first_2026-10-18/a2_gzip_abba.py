# a2_gzip_abba.py — gzip سطحِ ۱ در برابرِ ۵، کنترل‌شده و تکرارشونده.
#
# هر دور: پردازشِ تازهٔ ریگِ :8020 با BORS_NO_FETCH_LOOPS=1، بانکِ pristine (sha256 بررسی‌شده)،
# همان بارِ کاری با همان ترتیب و همان نرخ. فقط سطحِ gzip عوض می‌شود. ترتیب ABBA BAAB.
# فاز‌ها: سرد (اولین قیف + اولین تابلو) → ریتمِ گرمِ ۶۰ ثانیه‌ای. نمونه‌گیرِ ارزان هر ۱۰۰ms
# انسدادِ حلقه را می‌سنجد (GZipMiddleware رویِ نخِ حلقه فشرده می‌کند).
# فقط ریگِ خودم؛ :8000/:8010 دست نمی‌خورند.
import gzip
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

WT = r"C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf"
EV = os.path.join(WT, "_test_runs", "performance_first_2026-10-18", "a2")
RIG = r"C:\Users\Johnkallnaya\AppData\Local\Temp\bors_rig"
PRISTINE = os.path.join(RIG, "market.db.pristine")
PRISTINE_SHA = "9d557a533fc51e8356528da634e2f468154ad85625cdace713f6fb434eeb4f34"
DB = os.path.join(WT, "market.db")
PORT = 8020
BASE = "http://127.0.0.1:%d" % PORT
ORDER = sys.argv[1] if len(sys.argv) > 1 else "ABBABAAB"
LEVEL = {"A": 1, "B": 5}
FUNNEL_BODY = {"preset": "trend", "chain": [], "logic": "and",
               "fund_mode": "standard", "exceptions": {}, "drop_suffix": True}
WARM_S = 60.0

sys.path.insert(0, os.path.join(WT, "tools"))
from perf_winproc import ProcSampler  # noqa: E402


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def restore():
    for suf in ("-wal", "-shm"):
        if os.path.exists(DB + suf):
            os.remove(DB + suf)
    shutil.copyfile(PRISTINE, DB)
    return sha(DB) == PRISTINE_SHA


def ready(timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(BASE + "/api/watchlist", timeout=3).read()
            return time.time() - t0
        except Exception:
            time.sleep(0.5)
    return None


def req(name, method, path, body=None, gz=True):
    h = {"Accept": "application/json"}
    if gz:
        h["Accept-Encoding"] = "gzip"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    t0 = time.perf_counter()
    try:
        resp = urllib.request.urlopen(r, timeout=180)
        th = time.perf_counter()
        blob = resp.read()
        status, hd = resp.status, {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as e:
        th = time.perf_counter()
        blob = e.read() or b""
        status, hd = e.code, {k.lower(): v for k, v in e.headers.items()}
    except Exception as e:
        return {"name": name, "error": type(e).__name__, "ms": (time.perf_counter() - t0) * 1000}
    t1 = time.perf_counter()
    wire = len(blob)
    enc = hd.get("content-encoding", "identity")
    t2 = time.perf_counter()
    dec = gzip.decompress(blob) if enc == "gzip" else blob
    inflate_ms = (time.perf_counter() - t2) * 1000
    # بدنهٔ قیفِ ازِ‌کش کلیدِ آخرِ `cached_for_ms` دارد؛ برایِ هم‌سنجیِ داده کنار گذاشته می‌شود
    bare = dec
    i = dec.rfind(b',"cached_for_ms":')
    if i > 0 and dec.endswith(b"}"):
        bare = dec[:i] + b"}"
    return {"name": name, "method": method, "path": path, "status": status, "enc": enc,
            "x_cache": hd.get("x-cache", ""), "wire_bytes": wire, "decoded_bytes": len(dec),
            "ttfb_ms": round((th - t0) * 1000, 1), "ms": round((t1 - t0) * 1000, 1),
            "client_inflate_ms": round(inflate_ms, 1),
            "decoded_sha": hashlib.sha256(bare).hexdigest()[:16], "t_rel": t0}


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 1)


def summ(xs):
    return {"n": len(xs), "median": pct(xs, 0.5), "p95": pct(xs, 0.95), "max": round(max(xs), 1) if xs else None}


def one_round(i, arm):
    level = LEVEL[arm]
    ok_db = restore()
    env = dict(os.environ, BORS_NO_FETCH_LOOPS="1", PYTHONIOENCODING="utf-8", BORS_GZIP_LEVEL=str(level))
    log = open(os.path.join(RIG, "rig-a2-%d-%s.out" % (i, arm)), "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1",
                          "--port", str(PORT), "--log-level", "warning"], cwd=WT, env=env, stdout=log, stderr=log)
    rec = {"round": i, "arm": arm, "gzip_level": level, "db_pristine": ok_db, "pid": p.pid}
    try:
        up = ready()
        rec["ready_s"] = round(up, 1) if up else None
        if up is None:
            rec["error"] = "rig not ready"
            return rec
        ps = ProcSampler(p.pid)
        ext = ProcSampler(10424) if _alive(10424) else None
        time.sleep(3.0)
        steps = []
        # ── سرد ─────────────────────────────────────────────────────────────
        a0 = ps.read()
        steps.append(req("cold-funnel", "POST", "/api/funnel", FUNNEL_BODY))
        steps.append(req("cold-market", "GET", "/api/market"))
        a1 = ps.read()
        rec["cold_cpu_ms"] = round(a1["cpu_ms"] - a0["cpu_ms"], 1)
        # ── گرم: ریتمِ ثابت، هم‌زمان با نمونه‌گیرِ ارزان و CPU/RAM ─────────
        stop = threading.Event()
        cheap, mem = [], []

        def cheap_loop():
            while not stop.is_set():
                t0 = time.perf_counter()
                try:
                    urllib.request.urlopen(BASE + "/api/mstat/phase", timeout=30).read()
                    cheap.append((t0, (time.perf_counter() - t0) * 1000))
                except Exception:
                    cheap.append((t0, None))
                time.sleep(0.1)

        def mem_loop():
            while not stop.is_set():
                mem.append(ps.read())
                time.sleep(0.5)
        th = [threading.Thread(target=cheap_loop), threading.Thread(target=mem_loop)]
        time.sleep(8.6)          # ورودیِ سردِ قیف منقضی شود تا ریتم ازِ MISS شروع شود
        b0 = ps.read()
        e0 = ext.read() if ext else None
        for t in th:
            t.start()
        tstart = time.perf_counter()
        sched = []
        for k in range(int(WARM_S // 10)):
            sched.append((k * 10.0, "funnel-miss", "POST", "/api/funnel", FUNNEL_BODY))
            sched.append((k * 10.0 + 2.0, "funnel-hit", "POST", "/api/funnel", FUNNEL_BODY))
        for k in range(int(WARM_S // 5)):
            sched.append((k * 5.0 + 1.0, "market", "GET", "/api/market", None))
        sched.sort(key=lambda x: x[0])
        lock = threading.Lock()
        workers = []

        def fire(at, name, m, path, body):
            d = tstart + at - time.perf_counter()
            if d > 0:
                time.sleep(d)
            r = req(name, m, path, body)
            r["at_s"] = at
            with lock:
                steps.append(r)
        for s in sched:
            w = threading.Thread(target=fire, args=s)
            w.start()
            workers.append(w)
        for w in workers:
            w.join()
        b1 = ps.read()
        e1 = ext.read() if ext else None
        stop.set()
        for t in th:
            t.join()
        warm_wall = b1["mono"] - b0["mono"]
        rec["warm_wall_s"] = round(warm_wall, 1)
        rec["warm_cpu_ms"] = round(b1["cpu_ms"] - b0["cpu_ms"], 1)
        rec["warm_cpu_pct_of_core"] = round((b1["cpu_ms"] - b0["cpu_ms"]) / (warm_wall * 10.0), 1)
        rec["ext_10424_cpu_pct_of_core"] = (round((e1["cpu_ms"] - e0["cpu_ms"]) / (warm_wall * 10.0), 1)
                                           if ext else None)
        rec["ws_mb_max"] = round(max(m["ws_mb"] for m in mem), 1)
        rec["ws_mb_median"] = round(statistics.median(m["ws_mb"] for m in mem), 1)
        rec["peak_ws_mb"] = round(b1["peak_ws_mb"], 1)
        rec["private_mb_end"] = round(b1["private_mb"], 1)
        cl = [ms for (_, ms) in cheap if ms is not None]
        rec["cheap_mstat_phase_ms"] = summ(cl)
        rec["cheap_errors"] = sum(1 for (_, ms) in cheap if ms is None)
        by = {}
        for s in steps:
            by.setdefault(s["name"], []).append(s)
        rec["paths"] = {}
        for name, xs in by.items():
            good = [x for x in xs if "error" not in x]
            rec["paths"][name] = {
                "n": len(xs), "errors": len(xs) - len(good),
                "status": sorted({x["status"] for x in good}),
                "x_cache": [x["x_cache"] for x in good],
                "ms": summ([x["ms"] for x in good]),
                "ttfb_ms": summ([x["ttfb_ms"] for x in good]),
                "client_inflate_ms": summ([x["client_inflate_ms"] for x in good]),
                "wire_bytes": summ([x["wire_bytes"] for x in good]),
                "wire_bytes_total": sum(x["wire_bytes"] for x in good),
                "decoded_bytes_total": sum(x["decoded_bytes"] for x in good),
                "decoded_sha": sorted({x["decoded_sha"] for x in good}),
            }
        rec["steps"] = [{k: v for k, v in s.items() if k != "t_rel"} for s in steps]
        ps.close()
        return rec
    finally:
        p.terminate()
        try:
            p.wait(20)
        except subprocess.TimeoutExpired:
            p.kill()
        log.close()
        time.sleep(2)


def _alive(pid):
    try:
        s = ProcSampler(pid)
        a = s.alive()
        s.close()
        return a
    except OSError:
        return False


def main():
    os.makedirs(EV, exist_ok=True)
    assert sha(PRISTINE) == PRISTINE_SHA, "pristine تغییر کرده"
    out = []
    for i, arm in enumerate(ORDER):
        r = one_round(i, arm)
        out.append(r)
        with open(os.path.join(EV, "round-%02d-%s-gz%d.json" % (i, arm, LEVEL[arm])), "w", encoding="utf-8") as fh:
            json.dump(r, fh, ensure_ascii=False, indent=1)
        p = r.get("paths", {})
        print(i, arm, "gz%d" % LEVEL[arm], "ready", r.get("ready_s"), "cpu%", r.get("warm_cpu_pct_of_core"),
              "ext10424%", r.get("ext_10424_cpu_pct_of_core"), "ws_max", r.get("ws_mb_max"),
              "cheap", r.get("cheap_mstat_phase_ms"),
              "miss", (p.get("funnel-miss") or {}).get("ms"), "hit", (p.get("funnel-hit") or {}).get("ms"),
              "market", (p.get("market") or {}).get("ms"), "err", r.get("error"), flush=True)
    with open(os.path.join(EV, "a2-all-rounds.json"), "w", encoding="utf-8") as fh:
        json.dump([{k: v for k, v in r.items() if k != "steps"} for r in out], fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
