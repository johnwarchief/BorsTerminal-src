# -*- coding: utf-8 -*-
# B2: بیلدِ دسکتاپ ازِ مسیرِ رسمیِ مخزن (scripts/build_all.py) رویِ venv_build، با ثبتِ وضعیتِ منبع و هشِ آرتیفکت.
# آرتیفکتِ آزمایشی است، نه ریلیز: هیچ tag/latest.json/نصبی لمس نمی‌شود.
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, "..", ".."))
PY = os.path.join(WT, "venv_build", "Scripts", "python.exe")
DIST = os.path.join(WT, "dist", "BorsTerminal_Ultimate")
EXE = os.path.join(DIST, "BorsTerminal_Ultimate.exe")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
SRC_FILES = ["api/funnel.py", "app.py", "frontend/src/shared/api/http.ts", "dev/funnel_body_cache_v1.py",
             "tools/perf_cache_rhythm_gzip_probe.py", "frontend/src/shared/lib/feedFreshness.ts",
             "frontend/src/shared/components/FreshnessBadge.tsx",
             "frontend/src/features/market/components/MarketStatusPanel.tsx",
             "frontend/src/__tests__/m1-ux-integrity.spec.tsx"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def git(*a):
    return subprocess.run(["git", *a], cwd=WT, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def run(name, cmd, timeout):
    log = os.path.join(HERE, "b2-%s.txt" % name)
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as fh:
        fh.write("$ %s\n" % " ".join(cmd))
        fh.flush()
        rc = subprocess.run(cmd, cwd=WT, stdout=fh, stderr=subprocess.STDOUT, env=ENV, timeout=timeout).returncode
        fh.write("\nEXIT=%s\n" % rc)
    return {"cmd": " ".join(os.path.relpath(c, WT) if os.path.isabs(c) else c for c in cmd), "rc": rc,
            "dur_s": round(time.time() - t0, 1), "log": os.path.basename(log)}


def main():
    res = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "head": git("rev-parse", "HEAD"),
           "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
           "diff_stat_vs_head": git("diff", "--stat", "HEAD"),
           "src_sha256": {f: sha(os.path.join(WT, f)) for f in SRC_FILES},
           "py": subprocess.run([PY, "-c", "import sys,numpy,pandas;print(sys.version.split()[0],numpy.__version__,"
                                 "pandas.__version__)"], capture_output=True, text=True).stdout.strip()}
    res["check_build_env"] = run("check_build_env", [PY, "scripts/check_build_env.py"], 600)
    res["build_all"] = run("build_all", [PY, "scripts/build_all.py"], 3600)
    if os.path.exists(EXE):
        n, size = 0, 0
        for root, _, files in os.walk(DIST):
            for f in files:
                n += 1
                size += os.path.getsize(os.path.join(root, f))
        res["dist"] = {"path": os.path.relpath(DIST, WT), "files": n, "bytes": size,
                       "exe": os.path.relpath(EXE, WT), "exe_bytes": os.path.getsize(EXE), "exe_sha256": sha(EXE),
                       "exe_mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(EXE)))}
    res["src_sha256_after_build"] = {f: sha(os.path.join(WT, f)) for f in SRC_FILES}
    res["src_unchanged_by_build"] = res["src_sha256_after_build"] == res["src_sha256"]
    with open(os.path.join(HERE, "b2-build.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: res.get(k) for k in ("head", "py", "check_build_env", "build_all", "dist",
                                              "src_unchanged_by_build")}, ensure_ascii=False))
    return 0 if res["build_all"]["rc"] == 0 and "dist" in res else 1


if __name__ == "__main__":
    sys.exit(main())
