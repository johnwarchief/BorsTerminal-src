# -*- coding: utf-8 -*-
# F1 اثباتِ زنده: نشانِ تازگیِ بیلدِ اصلاح‌شده رویِ ریگِ :8020 با بانکِ pristine (تابلویِ ۲۰۲۶۱۰۱۴).
# بازوی pastday: ساعتِ میخکوبِ ۲۰۲۶-۱۰-۱۷ ۱۰:۰۰ ⇒ باید stale باشد. بازوی sameday (کنترل): ۲۰۲۶-۱۰-۱۴ ۱۰:۰۰ ⇒ باید live بماند.
# هیچ دریافتِ TSETMC/CODAL (BORS_NO_FETCH_LOOPS=1) و هیچ پویشی جز ریتمِ خودِ برنامه نیست.
import glob
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a2_gzip_abba import BASE, PORT, PRISTINE, PRISTINE_SHA, RIG, WT, ready, restore, sha  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.join(HERE, "f1-live")
FIX_SHA = "c84a0689453aabda74b033ac70f8797c959d628bbd004aa47a5106a6409656eb"
SRC = os.path.join(WT, "frontend", "src", "shared", "lib", "feedFreshness.ts")
DIST = os.path.join(WT, "frontend", "dist")
MON_S = 75
ARMS = [("pastday", "2026-10-17T10:00:00+03:30", "stale"), ("sameday", "2026-10-14T10:00:00+03:30", "live")]
FIX_RE = re.compile(r"getFullYear\(\)\*1e4\+\(\w+\.getMonth\(\)\+1\)\*100\+\w+\.getDate\(\)")


def dist_has_fix():
    hits = []
    for p in glob.glob(os.path.join(DIST, "assets", "*.js")):
        with open(p, encoding="utf-8", errors="replace") as fh:
            if FIX_RE.search(fh.read()):
                hits.append(os.path.basename(p))
    idx = os.path.join(DIST, "index.html")
    return {"files_with_fix": hits, "index_mtime": time.strftime("%Y-%m-%d %H:%M:%S",
                                                                time.localtime(os.path.getmtime(idx)))}


def badge(d):
    ev = [json.loads(x) for x in open(os.path.join(d, "events.jsonl"), encoding="utf-8") if x.strip()]
    smp = [r for r in ev if r.get("k") == "smp" and r.get("fresh") is not None]
    ages = [int(r["data_age_ms"]) for r in smp if r.get("data_age_ms")]
    return {"n": len(smp), "fresh": dict(Counter(r["fresh"] for r in smp)),
            "labels": dict(Counter(r.get("label") for r in smp)),
            "data_age_ms_min": min(ages) if ages else None, "data_age_ms_max": max(ages) if ages else None,
            "routes": dict(Counter(r.get("route") for r in smp))}


def one(name, clock, want):
    d = os.path.join(EV, name)
    os.makedirs(d, exist_ok=True)
    rec = {"arm": name, "clock": clock, "expect": want, "db_pristine": restore()}
    env = dict(os.environ, BORS_NO_FETCH_LOOPS="1", PYTHONIOENCODING="utf-8")
    log = open(os.path.join(RIG, "rig-f1-%s.out" % name), "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(PORT),
                          "--log-level", "warning"], cwd=WT, env=env, stdout=log, stderr=log)
    rec["pid"] = p.pid
    try:
        up = ready()
        rec["ready_s"] = round(up, 1) if up else None
        if up is None:
            rec["error"] = "rig not ready"
            return rec
        time.sleep(3.0)
        with open(os.path.join(d, "monitor-console.txt"), "w", encoding="utf-8") as fh:
            rec["monitor_exit"] = subprocess.run(
                ["node", os.path.join(WT, "tools", "perf_market_open_monitor.mts"), "--url", BASE, "--out", d,
                 "--duration", str(MON_S), "--journey", "market:%d" % MON_S, "--warm-after", "25", "--clock", clock],
                cwd=WT, stdout=fh, stderr=fh, timeout=MON_S + 120,
                env=dict(os.environ, PYTHONIOENCODING="utf-8", MSYS_NO_PATHCONV="1")).returncode
        rec["badge"] = badge(d)
        f = rec["badge"]["fresh"]
        rec["pass"] = bool(f) and set(f) == {want}
        return rec
    finally:
        p.terminate()
        try:
            p.wait(20)
        except subprocess.TimeoutExpired:
            p.kill()
        log.close()
        time.sleep(2)


def main():
    assert sha(SRC) == FIX_SHA, "feedFreshness.ts is not the fixed code"
    assert sha(PRISTINE) == PRISTINE_SHA
    res = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "dist": dist_has_fix(), "arms": []}
    if not res["dist"]["files_with_fix"]:
        res["error"] = "frontend/dist does not contain the fix; rebuild first"
    else:
        for name, clock, want in ARMS:
            res["arms"].append(one(name, clock, want))
    res["db_restored_after"] = restore()
    res["verdict"] = "PASS" if res["arms"] and all(a.get("pass") for a in res["arms"]) else "FAIL"
    os.makedirs(EV, exist_ok=True)
    with open(os.path.join(HERE, "f1-badge-live.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
