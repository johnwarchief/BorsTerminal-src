#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تفکیکِ هزینهٔ اولینِ فشارِ ربات: اسکنِ قیف یا خودِ ربات؟

بخشی از زنجیرۀ راستی‌آزماییِ مأموریتِ سرخطی/EasyTrader/ربات. مسیرها ازِ ریشۀ ریپو حساب می‌شوند، نه ازِ یکِ ماشینِ خاص.
"""
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import json
import os
import subprocess
import sys
import time
import urllib.request

EXE = os.path.join(ROOT, "dist", "BorsTerminal_Ultimate", "BorsTerminal_Ultimate.exe")
PORT = 8078
BASE = "http://127.0.0.1:%d" % PORT

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
env = dict(os.environ)
env.update({"BORS_PORTABLE": "1", "BORS_PORT": str(PORT),
            "PYTHONIOENCODING": "utf-8", "BORS_CODAL_OFFLINE": "1"})
logf = open(os.path.join(ROOT, "_audit", "cold_start_stdout.log"), "wb")
proc = subprocess.Popen([EXE], cwd=os.path.dirname(EXE), env=env,
                        stdout=logf, stderr=subprocess.STDOUT)


def call(method, path, body=None, timeout=600):
    data = json.dumps(body or {}).encode("utf-8") if method in ("POST", "PUT") else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    t = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return time.time() - t, json.loads(r.read().decode("utf-8", "replace"))


try:
    t0 = time.time()
    while time.time() - t0 < 240:
        try:
            call("GET", "/api/update/version", timeout=3)
            break
        except Exception:
            time.sleep(2)
    print("boot ok in %.1fs" % (time.time() - t0))

    d, r = call("PUT", "/api/bot/config", {"enabled": True, "chain": ["f_roobi"]})
    print("%.1fs  PUT /api/bot/config           enabled=%s" % (d, (r.get("config") or {}).get("enabled")))

    d, r = call("GET", "/api/funnel?preset=trend&chain=f_roobi", timeout=900)
    print("%.1fs  GET /api/funnel (COLD)        status=%s survivors=%s" %
          (d, r.get("status"), len(r.get("handover") or [])))

    d, r = call("GET", "/api/funnel?preset=trend&chain=f_roobi", timeout=900)
    print("%.1fs  GET /api/funnel (warm)        cached_for_ms=%s" %
          (d, (r.get("tech_scan") or {}).get("last_ms")))

    d, r = call("POST", "/api/bot/run", {}, timeout=900)
    run = r.get("run") or {}
    print("%.1fs  POST /api/bot/run (first)     inner_ms=%s bars=%s in=%s" %
          (d, run.get("ms"), run.get("bars"), run.get("symbols_in")))

    d, r = call("POST", "/api/bot/run", {}, timeout=900)
    run = r.get("run") or {}
    print("%.1fs  POST /api/bot/run (second)    inner_ms=%s signals=%s" %
          (d, run.get("ms"), sum(int(x.get("signals") or 0) for x in run.get("decisions") or [])))
finally:
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    logf.close()
