# -*- coding: utf-8 -*-
# تکرارِ گاردِ بدنهٔ کش رویِ کدِ نهایی (v2): بندِ «۲۰» یک بار قرمز و بارِ بعد سبز شد.
# آستانه دست‌نخورده؛ فقط چند اجرایِ پیاپی با عددِ چاپ‌شده، تا علّتِ پرش داوری شود.
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a2_gzip_abba import PORT, RIG, WT, ready, restore, sha  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(WT, "api", "funnel.py")
V2_SHA = "bad4d71468f28d43d43d96fbf32c73133a193ecb8c86cd832cd8459c4b1054b9"
GUARD = os.path.join(WT, "dev", "funnel_body_cache_v1.py")
N = int(os.environ.get("REPEATS", "4"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", BORS_NO_FETCH_LOOPS="1")

LINE = re.compile(r"^(ok|FAIL)\s+(۱۸|۱۹|۲۰)\s+(.*)$")


def parse(log):
    rows = []
    for ln in io_read(log).splitlines():
        m = LINE.match(ln)
        if m:
            rows.append({"status": m.group(1), "item": ln.strip()})
    return rows


def io_read(p):
    import io
    return io.open(p, encoding="utf-8", errors="replace").read()


def hog_cpu(seconds=1.5):
    """ساعتِ فرایندِ بیرونیِ ۱۰۴۲۴ (متعلق به مأموریتِ دیگر، کشته نمی‌شود)."""
    try:
        a = _t10424()
        time.sleep(seconds)
        b = _t10424()
        return round((b - a) / seconds * 100.0, 1)
    except Exception as e:
        return "unavailable:%s" % type(e).__name__


def _t10424():
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.restype = wintypes.HANDLE
    h = kernel.OpenProcess(0x0400, False, 10424)
    if not h:
        raise OSError("no process")
    ct = wintypes.FILETIME()
    et = wintypes.FILETIME()
    kt = wintypes.FILETIME()
    if not kernel.GetProcessTimes(h, ctypes.byref(ct), ctypes.byref(et), ctypes.byref(kt), ctypes.byref(ct)):
        raise OSError("times")
    kernel.CloseHandle(h)
    return ((ct.dwHighDateTime << 32) + ct.dwLowDateTime) / 1e7


def main():
    res = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "funnel_sha": sha(SRC), "repeats": N}
    assert res["funnel_sha"] == V2_SHA, "api/funnel.py is not v2: %s" % res["funnel_sha"]
    res["db_pristine_before"] = restore()
    log = open(os.path.join(RIG, "rig-c20.out"), "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1",
                          "--port", str(PORT), "--log-level", "warning"], cwd=WT, env=ENV,
                         stdout=log, stderr=log)
    try:
        res["ready_s"] = ready()
        time.sleep(3)
        runs = []
        for k in range(1, N + 1):
            h = hog_cpu()
            t0 = time.time()
            lg = os.path.join(HERE, "p0-c20-run%d.txt" % k)
            with open(lg, "w", encoding="utf-8") as fh:
                rc = subprocess.run([sys.executable, "dev/funnel_body_cache_v1.py", "--port", str(PORT)],
                                    cwd=WT, stdout=fh, stderr=subprocess.STDOUT, env=ENV,
                                    timeout=1200).returncode
            txt = io_read(lg)
            runs.append({"run": k, "rc": rc, "dur_s": round(time.time() - t0, 1),
                         "hog_pct_one_core": h,
                         "green_red": (txt.count("\nok   "), txt.count("FAIL ")),
                         "timing_items": parse(lg),
                         "log": os.path.basename(lg)})
            print("run", k, "rc", rc, flush=True)
            time.sleep(2)
        res["runs"] = runs
    finally:
        p.terminate()
        try:
            p.wait(20)
        except subprocess.TimeoutExpired:
            p.kill()
        log.close()
    res["db_pristine_after"] = restore()
    res["funnel_sha_after"] = sha(SRC)
    with open(os.path.join(HERE, "p0-check20-repeat.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
