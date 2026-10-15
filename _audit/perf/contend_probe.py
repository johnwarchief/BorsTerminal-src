"""PERF Stage 9 — contention probe: does non-essential background work slow the UI path?

The only heavy non-essential work left in the app is the boot-time screener bulk scan
(~900 symbols of live evaluate_v10, one core, ~2 minutes on this laptop). A low-resource
profile is only worth adding if that scan actually degrades the requests the UI waits for.

This probe measures the same UI-path endpoints three times — before the scan, while the
scan is running, and after it — and records the backend process CPU-seconds consumed in
each window so the load is provable, not assumed. Nothing here writes any database; the
cold scan is the app's own read-only startup warm (verified: no INSERT/UPDATE/DELETE on
that path, and it only rewrites its own regenerable JSON cache).

usage (from BorsTerminal-src, dev backend on 127.0.0.1:8000):
  PYTHONIOENCODING=utf-8 python _audit/perf/contend_probe.py --tag IDLE_A --pid 2700
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from be_probe import call, probe  # noqa: E402

BASE = "http://127.0.0.1:8000"

# فقط مسیرهایِ واقعیِ UI؛ اسکرینرِ عمداً حذف است چون وسطِ اسکنِ گرم تا ۳۰۰s بلاک می‌شود
# و سنجِ رقابت نیست، و sync-state هم خودش PowerShell می‌سازد و بارِ CPU را آلوده می‌کند.
PATHS = [
    ("market", "/api/market"),
    ("mstat board", "/api/mstat/board"),
    ("mstat summary", "/api/mstat/summary"),
    ("mstat mainwatch", "/api/mstat/mainwatch?group=eq_all&industry="),
    ("mstat treemap", "/api/mstat/treemap?group=eq_all&industry=&metric=volume"),
    ("mstat industries", "/api/mstat/industries"),
    ("mstat phases", "/api/mstat/phases"),
    ("mstat smart-money", "/api/mstat/smart-money"),
    ("chart cached", "/api/chart/خوز"),
    ("funnel registry", "/api/funnel/registry"),
    # /api/index/tedpix عمداً اینجا نیست: پروکسی به منبعِ بیرونی است و تأخیرش
    # (در این سنجش ۵۰۲ با ۶۳ ثانیه) ساعتِ CPU این ماشین را نشان نمی‌دهد؛
    # در baseline مرحلۀ ۱b با همان عدد آمده است.
]

def cpu_seconds(pid):
    """CPU-seconds the backend process has burned in total (Windows kernel counter)."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Process -Id {0}).TotalProcessorTime.TotalSeconds".format(pid)],
            capture_output=True, text=True, timeout=20).stdout.strip()
        return float(out)
    except Exception:
        return float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="label for this window (IDLE_A / HOT / IDLE_C)")
    ap.add_argument("--pid", type=int, default=0, help="backend PID, for the CPU-seconds sample")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--out", default="_audit/perf/CONTEND.json")
    args = ap.parse_args()

    if not call(BASE, "/api/live-stats", timeout=5.0).get("status"):
        print("dev backend not reachable on %s" % BASE)
        return 2

    cpu0 = cpu_seconds(args.pid) if args.pid else float("nan")
    t0 = time.time()
    rows = []
    for name, path in PATHS:
        r = probe(BASE, name, path, args.reps)
        if r:
            rows.append(r)
    elapsed = time.time() - t0
    cpu1 = cpu_seconds(args.pid) if args.pid else float("nan")

    out = {"tag": args.tag, "ran_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "window_s": round(elapsed, 1),
           "backend_cpu_s_in_window": round(cpu1 - cpu0, 2) if args.pid else None,
           "rows": [{k: v for k, v in r.items() if k not in ("body",)} for r in rows]}

    existing = {}
    if os.path.exists(args.out):
        try:
            with open(args.out, encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = {}
    existing[args.tag] = out
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=1)

    med = sorted(r["p50"] for r in rows)
    print("\n[%s] window=%.0fs  backend_cpu=%.1fs  total_p50_sum=%.0fms  median=%.0fms"
          % (args.tag, elapsed, out["backend_cpu_s_in_window"] or float("nan"),
             sum(r["p50"] for r in rows), med[len(med) // 2] if med else float("nan")))
    print("wrote %s#%s" % (args.out, args.tag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
