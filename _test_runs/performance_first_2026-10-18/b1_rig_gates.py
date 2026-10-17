# -*- coding: utf-8 -*-
# B1 (ریگ‌دار): گاردِ کشِ بدنهٔ قیف رویِ کدِ نهایی + گیتِ برابریِ خروجیِ ۲۷ مسیر (HEAD در برابرِ کدِ نهایی).
# جابه‌جاییِ api/funnel.py فقط با کپی و درستیِ هش، نه git checkout. پیش ازِ هر ریگ بانکِ pristine برمی‌گردد.
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a2_gzip_abba import PORT, PRISTINE, PRISTINE_SHA, RIG, WT, ready, restore, sha  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(WT, "api", "funnel.py")
HEAD_COPY = os.path.join(HERE, "a1-backup", "api_funnel.py")
HEAD_SHA = "0867f8814f578a24ca67dff2e0b6af7e8d91bded61236553526f6197997e54fb"
# اجرای اول (b1) رویِ کدِ بن‌بست‌دار بود؛ بازاجرا با برچسبِ دیگر شواهدِ آن را رونویسی نمی‌کند.
TAG = os.environ.get("RIG_TAG", "b1")
FINAL_COPY = os.path.join(HERE, "%s-after-src" % TAG, "api_funnel.py")
FINAL_SHA = os.environ.get("FINAL_SHA", "32eb1841d2501a9278ca1e75f776006a6c6355cf73bf9fabf226d159f86aa1db")
SNAP = "" if TAG == "b1" else "-" + TAG
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", BORS_NO_FETCH_LOOPS="1")
BASE = "http://127.0.0.1:%d" % PORT


def run(name, cmd, timeout=1800):
    log = os.path.join(HERE, "%s-%s.txt" % (TAG, name))
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as fh:
        fh.write("$ %s\n" % " ".join(cmd))
        fh.flush()
        rc = subprocess.run(cmd, cwd=WT, stdout=fh, stderr=subprocess.STDOUT, env=ENV, timeout=timeout).returncode
        fh.write("\nEXIT=%s\n" % rc)
    print(name, rc, round(time.time() - t0, 1), flush=True)
    return {"cmd": " ".join(cmd), "rc": rc, "dur_s": round(time.time() - t0, 1), "log": os.path.basename(log)}


def rig(tag):
    log = open(os.path.join(RIG, "rig-%s-%s.out" % (TAG, tag)), "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(PORT),
                          "--log-level", "warning"], cwd=WT, env=ENV, stdout=log, stderr=log)
    up = ready()
    return p, log, up


def stop(p, log):
    p.terminate()
    try:
        p.wait(20)
    except subprocess.TimeoutExpired:
        p.kill()
    log.close()
    time.sleep(2)


def put(src, want):
    shutil.copyfile(src, SRC)
    got = sha(SRC)
    assert got == want, "hash mismatch after copy: %s" % got
    return got


def main():
    res = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "tag": TAG, "final_sha": FINAL_SHA}
    assert sha(SRC) == FINAL_SHA, "api/funnel.py is not the final reviewed code"
    os.makedirs(os.path.dirname(FINAL_COPY), exist_ok=True)
    shutil.copyfile(SRC, FINAL_COPY)
    assert sha(FINAL_COPY) == FINAL_SHA and sha(HEAD_COPY) == HEAD_SHA and sha(PRISTINE) == PRISTINE_SHA
    try:
        # ۱) کدِ نهایی: گارد + snapshotِ «after»
        res["after_db_pristine"] = restore()
        p, log, up = rig("final")
        res["after_ready_s"] = up
        try:
            time.sleep(3)
            res["funnel_body_cache_final"] = run("funnel_body_cache_final",
                                                 [sys.executable, "dev/funnel_body_cache_v1.py", "--port", str(PORT)])
            res["equal_save_after"] = run("equal-save-after", [sys.executable, "dev/perf_output_equal_v1.py", "save",
                                                               "--base", BASE, "--tag", "after-perf-first" + SNAP])
        finally:
            stop(p, log)
        # ۲) کدِ HEAD: snapshotِ «before» (بانکِ pristine، همان ورودی)
        res["head_put_sha"] = put(HEAD_COPY, HEAD_SHA)
        res["before_db_pristine"] = restore()
        p, log, up = rig("head")
        res["before_ready_s"] = up
        try:
            time.sleep(3)
            res["equal_save_before"] = run("equal-save-before", [sys.executable, "dev/perf_output_equal_v1.py", "save",
                                                                 "--base", BASE, "--tag", "before-perf-first" + SNAP])
        finally:
            stop(p, log)
    finally:
        res["final_put_sha"] = put(FINAL_COPY, FINAL_SHA)
        res["final_restored_ok"] = res["final_put_sha"] == FINAL_SHA
    rep_name = "OUTPUT_EQUALITY_PERF_FIRST%s.json" % SNAP.upper().replace("-", "_")
    res["equal_check"] = run("equal-check", [sys.executable, "dev/perf_output_equal_v1.py", "check", "--before",
                                             "before-perf-first" + SNAP, "--after", "after-perf-first" + SNAP,
                                             "--report", rep_name])
    rep = os.path.join(WT, "_audit", "perf", rep_name)
    if os.path.exists(rep):
        shutil.move(rep, os.path.join(HERE, "%s-equal-check.json" % TAG))
    res["db_restored_after"] = restore()
    with open(os.path.join(HERE, "%s-rig-gates.json" % TAG), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
