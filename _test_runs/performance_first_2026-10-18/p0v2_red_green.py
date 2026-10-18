# -*- coding: utf-8 -*-
# P0 v2: گاردِ بن‌بست رویِ نسخهٔ معیوب قرمز و رویِ v2 سبز؛ سپس شش گاردِ قیف رویِ v2 با هشِ بانک پیش/پس.
# جابه‌جاییِ api/funnel.py فقط با کپی و درستیِ هش؛ هر گاردی که بانک را عوض کند با pristine برگردانده می‌شود.
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a2_gzip_abba import PRISTINE_SHA, WT, restore, sha  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(WT, "api", "funnel.py")
DB = os.path.join(WT, "market.db")
V2_SHA = "bad4d71468f28d43d43d96fbf32c73133a193ecb8c86cd832cd8459c4b1054b9"
V2_COPY = os.path.join(HERE, "p0v2-after-src", "api_funnel.py")
BUG_COPY = os.path.join(HERE, "b1-after-src", "api_funnel.py")
BUG_SHA = "32eb1841d2501a9278ca1e75f776006a6c6355cf73bf9fabf226d159f86aa1db"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
SUITES = ["dev/funnel_registry_v1.py", "dev/funnel_engine_v1.py", "dev/funnel_preset_distinct_v1.py",
          "dev/test_screener_funnel_gate_v1.py", "dev/test_mainwatch_flags_v1.py",
          "dev/test_funnel_warm_deadlock_v1.py"]


def put(src, want):
    shutil.copyfile(src, SRC)
    got = sha(SRC)
    assert got == want, "hash mismatch after copy: %s" % got
    return got


def run(script, log):
    t0 = time.time()
    with open(os.path.join(HERE, log), "w", encoding="utf-8") as fh:
        fh.write("$ python %s   (api/funnel.py sha %s)\n" % (script, sha(SRC)))
        fh.flush()
        rc = subprocess.run([sys.executable, script], cwd=WT, env=ENV, stdout=fh, stderr=subprocess.STDOUT,
                            timeout=600).returncode
        fh.write("\nEXIT=%s\n" % rc)
    return {"script": script, "rc": rc, "dur_s": round(time.time() - t0, 1), "log": log}


def main():
    assert sha(SRC) == V2_SHA, "api/funnel.py is not v2"
    os.makedirs(os.path.dirname(V2_COPY), exist_ok=True)
    shutil.copyfile(SRC, V2_COPY)
    assert sha(V2_COPY) == V2_SHA and sha(BUG_COPY) == BUG_SHA
    res = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "v2_sha": V2_SHA, "bug_sha": BUG_SHA,
           "db_pristine_before": restore()}
    try:
        put(BUG_COPY, BUG_SHA)
        res["red_bug"] = run("dev/test_funnel_warm_deadlock_v1.py", "p0v2-deadlock-red-bug.txt")
    finally:
        res["v2_put_sha"] = put(V2_COPY, V2_SHA)
    res["green_v2"] = run("dev/test_funnel_warm_deadlock_v1.py", "p0v2-deadlock-green-v2.txt")
    res["suites"] = []
    for s in SUITES:
        before = sha(DB)
        r = run(s, "p0v2-suite-%s.txt" % os.path.basename(s)[:-3])
        r["db_sha_before"], r["db_sha_after"] = before[:16], sha(DB)[:16]
        r["db_changed"] = r["db_sha_before"] != r["db_sha_after"]
        if r["db_changed"]:
            r["db_restored"] = restore()
        res["suites"].append(r)
    res["db_pristine_after"] = sha(DB) == PRISTINE_SHA
    res["src_final_is_v2"] = sha(SRC) == V2_SHA
    res["verdict"] = ("RED_GREEN_OK" if res["red_bug"]["rc"] != 0 and res["green_v2"]["rc"] == 0
                      and all(x["rc"] == 0 for x in res["suites"]) else "NOT_OK")
    with open(os.path.join(HERE, "p0v2-red-green.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res["verdict"] == "RED_GREEN_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
