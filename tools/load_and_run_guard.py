#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اجازۀ یکِ گارد زیرِ بارِ CPU (نسبت‌دادنِ سُرخی‌هایِ زمان‌بندی)

بخشی از زنجیرۀ راستی‌آزماییِ مأموریتِ سرخطی/EasyTrader/ربات. مسیرها ازِ ریشۀ ریپو حساب می‌شوند، نه ازِ یکِ ماشینِ خاص.
"""
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import multiprocessing
import os
import subprocess
import sys
import threading
import time

GUARD = sys.argv[1] if len(sys.argv) > 1 else "dev/easytrader_adapter_v1113.py"
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
OUT = os.path.join(ROOT, "_audit", "load_run_%s.txt" % os.path.basename(GUARD).replace(".py", ""))


def burn(stop_at):
    while time.time() < stop_at:
        pass


def workers(n):
    return [multiprocessing.Process(target=burn, args=(time.time() + SECS,)) for _ in range(n)]


if __name__ == "__main__":
    n = multiprocessing.cpu_count()
    procs = workers(n)
    for p in procs:
        p.start()
    # also spin threads inside this process so the GIL contended too
    th = [threading.Thread(target=burn, args=(time.time() + SECS,), daemon=True) for _ in range(4)]
    for t in th:
        t.start()
    time.sleep(1.0)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    t0 = time.time()
    r = subprocess.run([sys.executable, GUARD], cwd=ROOT, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=SECS + 900)
    txt = r.stdout.decode("utf-8", "replace")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(txt)
    fails = [l for l in txt.splitlines() if l.strip().startswith("FAIL")]
    tail = [l for l in txt.splitlines() if "passed" in l]
    print("load-run exit=%d wall=%.0fs" % (r.returncode, time.time() - t0))
    print("summary:", tail[-1] if tail else "(no summary line)")
    for l in fails:
        print("  ->", l.strip()[:150])
    print("full output:", OUT)
    for p in procs:
        p.join()
