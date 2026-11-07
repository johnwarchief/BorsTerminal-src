# A2 بازوی مرورگری: gzip ۱ در برابرِ ۵ از دیدِ کاربر (ABBA، هر دور ریگِ تازه + بانکِ pristine).
# هر دور: ریگِ :8020 (BORS_NO_FETCH_LOOPS=1, BORS_GZIP_LEVEL=n) → sampler (CPU/RAM) → پایشگرِ مرورگری
# (ساعتِ میخکوب برای ریتمِ پویشِ ساعتِ بازار؛ بارِ سرد + reloadِ گرم + ریتمِ عادیِ برنامه) → اسکرولِ برنامه‌ای
# بی‌میخکوب → تحلیل. هیچ دریافتِ TSETMC/CODAL و هیچ پویشِ اضافه‌ای جز ریتمِ خودِ برنامه نیست.
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a2_gzip_abba import BASE, LEVEL, PORT, PRISTINE, PRISTINE_SHA, RIG, WT, ready, restore, sha  # noqa: E402

EV = os.path.join(WT, "_test_runs", "performance_first_2026-10-18", "a2b")
HERE = os.path.dirname(os.path.abspath(__file__))
ORDER = sys.argv[1] if len(sys.argv) > 1 else "ABBABAAB"
MON_S = 110
CLOCK = "2026-10-17T10:00:00+03:30"


def run(cmd, log, timeout):
    with open(log, "w", encoding="utf-8") as fh:
        return subprocess.run(cmd, cwd=WT, stdout=fh, stderr=fh, timeout=timeout,
                              env=dict(os.environ, PYTHONIOENCODING="utf-8", MSYS_NO_PATHCONV="1")).returncode


def one_round(i, arm):
    level = LEVEL[arm]
    d = os.path.join(EV, "round-%02d-%s-gz%d" % (i, arm, level))
    os.makedirs(d, exist_ok=True)
    rec = {"round": i, "arm": arm, "gzip_level": level, "db_pristine": restore(), "dir": os.path.relpath(d, WT)}
    env = dict(os.environ, BORS_NO_FETCH_LOOPS="1", PYTHONIOENCODING="utf-8", BORS_GZIP_LEVEL=str(level))
    log = open(os.path.join(RIG, "rig-a2b-%d-%s.out" % (i, arm)), "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1",
                          "--port", str(PORT), "--log-level", "warning"], cwd=WT, env=env, stdout=log, stderr=log)
    rec["pid"] = p.pid
    smp = None
    try:
        up = ready()
        rec["ready_s"] = round(up, 1) if up else None
        if up is None:
            rec["error"] = "rig not ready"
            return rec
        time.sleep(3.0)
        smp = subprocess.Popen([sys.executable, os.path.join(WT, "tools", "perf_market_open_sampler.py"), "--port", str(PORT),
                                "--out", os.path.join(d, "sampler.jsonl"), "--interval", "2", "--top-every", "30",
                                "--duration", str(MON_S + 60)], cwd=WT,
                               stdout=open(os.path.join(d, "sampler-console.txt"), "w", encoding="utf-8"),
                               stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        time.sleep(2.0)
        rec["monitor_exit"] = run(["node", os.path.join(WT, "tools", "perf_market_open_monitor.mts"), "--url", BASE,
                                   "--out", d, "--duration", str(MON_S), "--journey", "market:%d" % MON_S,
                                   "--warm-after", "25", "--clock", CLOCK], os.path.join(d, "monitor-console.txt"), MON_S + 120)
        rec["scroll_exit"] = run(["node", os.path.join(HERE, "a2_scroll_probe.mts"), "--url", BASE,
                                  "--out", os.path.join(d, "scroll.json")], os.path.join(d, "scroll-console.txt"), 180)
        open(os.path.join(d, "STOP"), "w").close()
        smp.wait(30)
        rec["analyze_exit"] = run([sys.executable, os.path.join(WT, "tools", "perf_market_open_analyze.py"),
                                   "--events", os.path.join(d, "events.jsonl"), "--sampler", os.path.join(d, "sampler.jsonl"),
                                   "--date", "2026-10-17", "--out", os.path.join(d, "analysis")],
                                  os.path.join(d, "analyze-console.txt"), 120)
        rec.update(summarize(d))
        return rec
    finally:
        if smp and smp.poll() is None:
            smp.kill()
        p.terminate()
        try:
            p.wait(20)
        except subprocess.TimeoutExpired:
            p.kill()
        log.close()
        time.sleep(2)


def summarize(d):
    out = {}
    a = json.load(open(os.path.join(d, "analysis.json"), encoding="utf-8"))
    out["loads"] = {x["name"]: {"rows_ready_ms": x["rows_ready_ms"], "fcp_ms": x["fcp_ms"], "dcl_ms": x["dcl_ms"]}
                    for x in a["loads"]}
    lt = [v for v in a["long_tasks"].values()]
    out["long_tasks"] = {"n": sum(v["n"] for v in lt), "total_ms": sum(v["total_ms"] for v in lt),
                         "max_ms": max((v["max_ms"] for v in lt), default=0)}
    fam = a["families"]
    for f, key in (("/api/funnel", "funnel"), ("/api/market", "market"), ("/api/market/delta", "delta"),
                   ("/api/screener", "screener")):
        s = (fam.get(f) or {}).get("all")
        if s:
            out[key] = {"n": s["n"], "x_cache": s["x_cache"], "errors": s["errors"], "dur_ms": s["dur_ms"],
                        "ttfb_ms": s["ttfb_ms"], "json_ms": s["json_ms"], "wire_bytes_total": s["wire_bytes_total"],
                        "wire_bytes": s["wire_bytes"], "enc": s["enc"]}
    srv = list(a["server"].values())
    cpu = [x for v in srv for x in [v["cpu_pct_one_core"]] if x.get("n")]
    out["server"] = {"cpu_pct_one_core_median": [c["median"] for c in cpu], "cpu_pct_one_core_max": [c["max"] for c in cpu],
                     "ws_mb_max": max((v["ws_mb_max"] for v in srv), default=None),
                     "private_mb_max": max((v["private_mb_max"] for v in srv), default=None)}
    out["hogs"] = a["cpu_hogs_ge50pct"]
    out["console_errors"] = a["console"]["n"]
    sp = os.path.join(d, "scroll.json")
    out["scroll"] = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else None
    return out


def main():
    os.makedirs(EV, exist_ok=True)
    assert sha(PRISTINE) == PRISTINE_SHA, "pristine تغییر کرده"
    allr = []
    for i, arm in enumerate(ORDER):
        r = one_round(i, arm)
        allr.append(r)
        print(json.dumps({k: r.get(k) for k in ("round", "arm", "gzip_level", "db_pristine", "ready_s", "monitor_exit",
                                               "scroll_exit", "analyze_exit", "loads", "long_tasks", "error")},
                         ensure_ascii=False), flush=True)
        with open(os.path.join(EV, "a2b-all-rounds.json"), "w", encoding="utf-8") as fh:
            json.dump(allr, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
