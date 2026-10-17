# -*- coding: utf-8 -*-
# parity مستقل و بی‌سقف: گیتِ کامل درِ run_all_tests رویِ سقفِ ۶۰۰s این پرونده را TIMEOUT می‌دهد؛
# این اجرا ثابت می‌کند آهستگیِ خودش است یا عیبِ کد. بانک پیش/پس بررسی و درِ لزوم برگردانده می‌شود.
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a2_gzip_abba import WT, restore, sha  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = "dev/fts_engine_paths_parity_v1076.py"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", BORS_NO_FETCH_LOOPS="1")


def main():
    res = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "cmd": "python " + SCRIPT,
           "db_pristine_before": restore()}
    log = os.path.join(HERE, "p0v2-parity.txt")
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as fh:
        fh.write("$ python %s   (بدونِ سقفِ زمان؛ سقفِ گیت ۶۰۰s بود)\n" % SCRIPT)
        fh.flush()
        rc = subprocess.run([sys.executable, SCRIPT], cwd=WT, stdout=fh, stderr=subprocess.STDOUT,
                            env=ENV).returncode
    res["rc"] = rc
    res["dur_s"] = round(time.time() - t0, 1)
    res["log"] = os.path.basename(log)
    res["db_sha_after"] = sha(os.path.join(WT, "market.db"))[:16]
    res["db_restored"] = restore()
    txt = open(log, encoding="utf-8", errors="replace").read().splitlines()
    res["tail"] = [t for t in txt if t.strip()][-6:]
    with open(os.path.join(HERE, "p0v2-parity.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    sys.exit(main())
