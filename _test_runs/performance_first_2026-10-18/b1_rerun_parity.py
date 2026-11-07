# -*- coding: utf-8 -*-
# بازاجرایِ تنهایِ همان سوئیتِ قرمزِ باتری (TimeoutExpired در ۶۰۰s) با زمان‌سنجی و نمونه‌برداریِ CPU،
# برایِ نسبت‌دادنِ علت — اجرایِ اول همان‌طور که بود مستند می‌ماند و این جایگزینش نیست.
import ctypes
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WT, "tools"))
from perf_winproc import ProcSampler  # noqa: E402

SUITE = "dev/fts_engine_paths_parity_v1076.py"
HOG = 10424
TIMEOUT = 600
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")


class _FT(ctypes.Structure):
    _fields_ = [("lo", ctypes.c_uint32), ("hi", ctypes.c_uint32)]


def sys_times():
    i, k, u = _FT(), _FT(), _FT()
    ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u))
    f = lambda t: (t.hi << 32) | t.lo  # noqa: E731
    return f(i), f(k) + f(u)


def main():
    log = os.path.join(HERE, "b1-rerun-paths-parity.txt")
    samples = []
    try:
        hog = ProcSampler(HOG)
    except OSError:
        hog = None
    t0 = time.perf_counter()
    start = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(log, "w", encoding="utf-8") as fh:
        fh.write("$ %s %s\n" % (sys.executable, SUITE))
        fh.flush()
        p = subprocess.Popen([sys.executable, SUITE], cwd=WT, stdout=fh, stderr=subprocess.STDOUT, env=ENV)
        child = ProcSampler(p.pid)
        prev = {"sys": sys_times(), "child": child.read(), "hog": hog.read() if hog else None}
        rc = None
        while True:
            try:
                rc = p.wait(5.0)
            except subprocess.TimeoutExpired:
                rc = None
            now = {"sys": sys_times(), "child": child.read(), "hog": hog.read() if hog else None}
            di, dt = now["sys"][0] - prev["sys"][0], now["sys"][1] - prev["sys"][1]
            wall = now["child"]["mono"] - prev["child"]["mono"]
            row = {"t_s": round(time.perf_counter() - t0, 1),
                   "sys_cpu_pct": round(100.0 * (dt - di) / dt, 1) if dt else None}
            if now["child"]["cpu_ms"] is not None and prev["child"]["cpu_ms"] is not None:
                row["child_pct_core"] = round((now["child"]["cpu_ms"] - prev["child"]["cpu_ms"]) / (wall * 10.0), 1)
            if hog and now["hog"]["cpu_ms"] is not None:
                row["hog_pct_core"] = round((now["hog"]["cpu_ms"] - prev["hog"]["cpu_ms"]) / (wall * 10.0), 1)
            samples.append(row)
            prev = now
            if rc is not None:
                break
            if time.perf_counter() - t0 > TIMEOUT:
                p.kill()
                rc = "TIMEOUT"
                break
        dur = round(time.perf_counter() - t0, 1)
        fh.write("\nEXIT=%s\n" % rc)
    tail = open(log, encoding="utf-8").read().splitlines()[-12:]

    def stat(key):
        v = sorted(s[key] for s in samples if s.get(key) is not None)
        return {"n": len(v), "median": v[len(v) // 2] if v else None, "max": v[-1] if v else None}

    res = {"suite": SUITE, "start": start, "dur_s": dur, "rc": rc, "battery_timeout_s": TIMEOUT,
           "hog_pid": HOG, "hog_alive": bool(hog and hog.alive()), "sys_cpu_pct": stat("sys_cpu_pct"),
           "child_pct_core": stat("child_pct_core"), "hog_pct_core": stat("hog_pct_core"),
           "tail": tail, "samples": samples}
    with open(os.path.join(HERE, "b1-rerun-paths-parity.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "samples"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
