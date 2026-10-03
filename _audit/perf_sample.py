# -*- coding: utf-8 -*-
"""_audit/perf_sample.py — نمونۀ مصرفِ زنده (بی‌تغییرِ هیچ رفتاری)

برداشت از همان برنامۀ نصب‌شدۀ کاربر: CPU/RAMِ فرایندِ برنامه و فرایندهایِ
WebView2، شمارۀ درخواست/تأخیر/حجمِ پاسخ از خودِ API، و نرخِ چرخه/نوشتنِ SQLite
از `/api/live-stats`. تنها چیزی که اضافه می‌کند چند GETِ اندازه‌گیر است — هیچ
`--apply`، هیچ نوشتن، هیچ ری‌استارتی ندارد.

مصرف GPU/VRAM: از `typeperf` خوانده می‌شود؛ اگر شمارندۀ ویندوز درِ این سیستم
نباشد صریحاً «اندازه‌گیری‌نشده» ثبت می‌شود (نه حدس).
"""
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.request

import orjson
import psutil

BASE = os.environ.get("PERF_BASE", "http://127.0.0.1:8001")
SECONDS = int(os.environ.get("PERF_SECONDS", "300"))
OUT = os.environ.get("PERF_OUT", "_audit/perf_sample.json")
PIDS = [int(x) for x in os.environ.get("PERF_PIDS", "").split(",") if x.strip()]


def gpu_sample():
    """یکِ نمونهٔ کوتاهِ `typeperf` از شمارندۀ GPU Engineِ ویندوز (best-effort)."""
    try:
        p = subprocess.run(["typeperf", "\\GPU Engine(*)\\Utilization Percentage",
                            "-sc", "2"], capture_output=True, text=True, timeout=25)
        lines = [l for l in p.stdout.splitlines() if '"' in l and "PDH" not in l]
        vals = []
        for l in lines[-40:]:
            for tok in l.split('","'):
                t = tok.strip('",')
                try:
                    v = float(t)
                    if 0.0 < v < 100.0:
                        vals.append(v)
                except ValueError:
                    pass
        top = sorted(enumerate(vals), key=lambda kv: -kv[1])[:5]
        return {"ok": bool(vals), "sum_pct": round(sum(vals), 2),
                "top5_pct": [round(v, 2) for _, v in top]}
    except Exception as e:
        return {"ok": False, "err": str(e)[:160]}


def get(path):
    t = time.perf_counter()
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        b = r.read()
    return (time.perf_counter() - t) * 1000.0, len(b), json.loads(b)


def main():
    procs = []
    for p in PIDS:
        try:
            root = psutil.Process(p)
            procs.append(root)
            # درختِ کاملِ برنامه: backend + میزبانِ WebView2 + رندرها/پردازۀ GPU
            procs.extend(root.children(recursive=True))
        except Exception:
            pass
    if not procs:
        procs = [p for p in psutil.process_iter()
                 if (p.name() or "").lower().startswith(("borsterminal", "msedgewebview2"))]
    for p in procs:
        try:
            p.cpu_percent(None)
        except Exception:
            pass
    api_ms, api_bytes, dl_ms, dl_bytes, cycles, wr, seen, rows = ([] for _ in range(8))
    dumps_ms, loads_ms, odumps_ms = [], [], []
    cpu_tot, rss_tot = [], []
    prev = None
    gpus = []
    t_end = time.time() + SECONDS
    n = 0
    while time.time() < t_end:
        n += 1
        try:
            st = get("/api/live-stats")[2]["data"]
            if prev:
                cycles.append(max(0, st["cycles"] - prev["cycles"]))
                wr.append(max(0, st["rows_written"] - prev["rows_written"]))
                seen.append(max(0, st["rows_seen"] - prev["rows_seen"]))
                rows.append(st["last_changed"])
            prev = st
        except Exception as e:
            print("live-stats failed:", e)
        if n % 3 == 0:
            ms, nb, body = get("/api/market")
            api_ms.append(ms)
            api_bytes.append(nb)
            # parsing/serializationِ سمتِ کلاینت رویِ همان بدنه (قریبِ کاریِ مرورگر)
            t0 = time.time()
            txt = json.dumps(body)
            dumps_ms.append((time.time() - t0) * 1000.0)
            t0 = time.time()
            json.loads(txt)
            loads_ms.append((time.time() - t0) * 1000.0)
            t0 = time.time()
            orjson.dumps(body)
            odumps_ms.append((time.time() - t0) * 1000.0)
            ms2, nb2, b2 = get("/api/market/delta?since=%d" % (body.get("rev") or 0))
            dl_ms.append(ms2)
            dl_bytes.append(nb2)
            try:
                ms3, nb3, _ = get("/api/mstat/depth?group=eq_all")
            except Exception:
                pass
        if n % 15 == 2:
            gpus.append(gpu_sample())
        rss = cpu = 0.0
        for p in procs:
            try:
                rss += p.memory_info().rss / 1e6
                cpu += p.cpu_percent(None)
            except Exception:
                pass
        cpu_tot.append(cpu); rss_tot.append(rss)
        if n % 5 == 0:
            print("[%4ds] cpu%%=%.0f rss=%.0fMB cycles/2s=%s changed=%s api=%sms"
                  % (int(time.time() - (t_end - SECONDS)), cpu, rss,
                     cycles[-1] if cycles else "-", rows[-1] if rows else "-",
                     "%.0f" % api_ms[-1] if api_ms else "-"))
        time.sleep(max(0.0, 2.0 - (time.time() % 2.0)))

    def s(v):
        v = [x for x in v if x is not None]
        return {"n": len(v), "median": round(statistics.median(v), 2) if v else None,
                "p95": round(sorted(v)[int(len(v) * 0.95)], 2) if v else None,
                "max": round(max(v), 2) if v else None} if v else {"n": 0}

    gpu_ok = [g for g in gpus if g.get("ok")]
    per_proc = []
    for q in procs:
        try:
            per_proc.append({"pid": q.pid, "name": q.name(),
                             "rss_mb": round(q.memory_info().rss / 1e6, 1),
                             "cpu_pct": round(q.cpu_percent(None), 1)})
        except Exception:
            pass
    per_proc.sort(key=lambda d: -d["rss_mb"])
    out = {"base": BASE, "seconds": SECONDS, "procs": len(procs),
           "root_pids": PIDS, "tree_rss_mb_sum": round(sum(d["rss_mb"] for d in per_proc), 1),
           "top_procs": per_proc[:10], "process_cpu_pct": s(cpu_tot),
           "process_rss_mb": s(rss_tot),
           "cycles_delta_per_2s": s(cycles), "rows_written_per_2s": s(wr),
           "rows_seen_per_2s": s(seen), "last_changed_per_cycle": s(rows),
           "api_market_ms": s(api_ms), "api_market_bytes": s(api_bytes),
           "client_json_dumps_ms": s(dumps_ms), "client_json_loads_ms": s(loads_ms),
           "client_orjson_dumps_ms": s(odumps_ms),
           "api_delta_ms": s(dl_ms), "api_delta_bytes": s(dl_bytes),
           "gpu": {"samples": len(gpus), "ok": len(gpu_ok),
                   "median_sum_pct": (statistics.median([g["sum_pct"] for g in gpu_ok])
                                      if gpu_ok else None),
                   "max_sum_pct": (max([g["sum_pct"] for g in gpu_ok]) if gpu_ok else None),
                   "first": gpus[0] if gpus else None},
           "written_at": time.strftime("%F %T")}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
