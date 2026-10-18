# -*- coding: utf-8 -*-
# F1 red/green: تستِ «تابلویِ نشستِ پیشین ⇒ stale» رویِ کدِ اصلاح‌شده سبز، رویِ کدِ HEAD قرمز، و پس ازِ بازگردانی سبز.
# جابه‌جاییِ feedFreshness.ts فقط با کپی و درستیِ هش؛ هیچ git checkout. نباید هم‌زمان با باتریِ پایتون اجرا شود.
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, "..", ".."))
FE = os.path.join(WT, "frontend")
SRC = os.path.join(FE, "src", "shared", "lib", "feedFreshness.ts")
HEAD_COPY = os.path.join(HERE, "f1-backup", "feedFreshness.ts")
HEAD_SHA = "2e258ab8125011997b280b57561d0b96a92755dbd5bd4c2dbef4386304ed73b1"
FIX_COPY = os.path.join(HERE, "f1-after", "feedFreshness.ts")
FIX_SHA = "c84a0689453aabda74b033ac70f8797c959d628bbd004aa47a5106a6409656eb"
SPEC = "src/__tests__/m1-ux-integrity.spec.tsx"
NPX = "npx.cmd" if os.name == "nt" else "npx"


def sha(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def put(src, want):
    shutil.copyfile(src, SRC)
    got = sha(SRC)
    assert got == want, "hash mismatch after copy: %s" % got
    return got


def vitest(tag):
    log = os.path.join(HERE, "f1-vitest-%s.txt" % tag)
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as fh:
        fh.write("$ npx vitest run %s  (feedFreshness.ts sha=%s)\n" % (SPEC, sha(SRC)))
        fh.flush()
        rc = subprocess.run([NPX, "vitest", "run", SPEC, "--reporter=verbose"], cwd=FE, stdout=fh,
                            stderr=subprocess.STDOUT, timeout=600).returncode
        fh.write("\nEXIT=%s\n" % rc)
    txt = open(log, encoding="utf-8").read()
    m = re.search(r"Tests\s+(.+)", txt)
    fails = re.findall(r"^\s*[×✗x]\s+(.+)$", txt, re.M)
    return {"rc": rc, "dur_s": round(time.time() - t0, 1), "tests_line": m.group(1).strip() if m else None,
            "failed_titles": fails, "log": os.path.basename(log)}


def main():
    assert sha(SRC) == FIX_SHA, "feedFreshness.ts is not the fixed code"
    assert sha(HEAD_COPY) == HEAD_SHA and sha(FIX_COPY) == FIX_SHA
    res = {"at": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        res["green_fixed"] = vitest("1-green-fixed")
        res["head_put_sha"] = put(HEAD_COPY, HEAD_SHA)
        res["red_head"] = vitest("2-red-head")
    finally:
        res["fix_put_sha"] = put(FIX_COPY, FIX_SHA)
    res["green_restored"] = vitest("3-green-restored")
    res["verdict"] = ("RED_GREEN_OK" if res["green_fixed"]["rc"] == 0 and res["red_head"]["rc"] != 0
                      and res["green_restored"]["rc"] == 0 else "RED_GREEN_BROKEN")
    with open(os.path.join(HERE, "f1-red-green.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res["verdict"] == "RED_GREEN_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
