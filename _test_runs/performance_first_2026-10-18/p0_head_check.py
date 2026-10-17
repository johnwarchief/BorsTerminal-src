# -*- coding: utf-8 -*-
# گاردِ بدنهٔ قیف رویِ ریگ، یک دور، پس از افزودنِ بندِ ۲۱ (HEAD ⇒ ۳۰۴).
# باتریِ کاملِ آفلاین پیش ازِ این افزودن اجرا شد (بدونِ سرور، این گارد درِ باتری SKIPPED می‌شود،
# پس نتیجۀ باتری دست‌نخورده می‌ماند)؛ این اجرا مدرکِ مستقیمِ همان بندِ تازه است.
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a2_gzip_abba import PORT, WT, ready, restore, sha  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(WT, "api", "funnel.py")
V2_SHA = "bad4d71468f28d43d43d96fbf32c73133a193ecb8c86cd832cd8459c4b1054b9"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", BORS_NO_FETCH_LOOPS="1")
ROUNDS = int(os.environ.get("ROUNDS", "2"))


def main():
    assert sha(SRC) == V2_SHA, "api/funnel.py is not the final code"
    res = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "funnel_sha": sha(SRC),
           "db_pristine_before": restore(), "rounds": []}
    log = open(os.path.join(HERE, "rig-head-check.out"), "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1",
                          "--port", str(PORT), "--log-level", "warning"], cwd=WT, env=ENV,
                         stdout=log, stderr=log)
    try:
        res["ready_s"] = ready()
        time.sleep(3)
        for k in range(1, ROUNDS + 1):
            lg = os.path.join(HERE, "p0v3-guard-%d.txt" % k)
            t0 = time.time()
            with open(lg, "w", encoding="utf-8") as fh:
                rc = subprocess.run([sys.executable, "dev/funnel_body_cache_v1.py", "--port", str(PORT)],
                                    cwd=WT, stdout=fh, stderr=subprocess.STDOUT, env=ENV,
                                    timeout=900).returncode
            txt = open(lg, encoding="utf-8", errors="replace").read()
            head_line = [t for t in txt.splitlines() if t.startswith(("ok   ۲۱", "FAIL ۲۱"))]
            res["rounds"].append({"round": k, "rc": rc, "dur_s": round(time.time() - t0, 1),
                                  "head_check": head_line[0][:220] if head_line else None,
                                  "green": txt.count("\nok   ") + (1 if txt.startswith("ok ") else 0),
                                  "red": txt.count("FAIL "), "log": os.path.basename(lg)})
            print("round", k, rc, flush=True)
    finally:
        p.terminate()
        try:
            p.wait(20)
        except subprocess.TimeoutExpired:
            p.kill()
        log.close()
    res["db_pristine_after"] = restore()
    with open(os.path.join(HERE, "p0v3-guard.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))
    return 0 if all(r["rc"] == 0 for r in res["rounds"]) else 1


if __name__ == "__main__":
    sys.exit(main())
