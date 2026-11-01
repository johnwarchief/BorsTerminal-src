#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""گیتِ B6: مسیرهایِ پورت‌شدهٔ همگام‌سازی، وضعیت و کنترل خزنده‌ها.

شامل دو بخشِ سنجش:
۱. B-G1 (Read & Contract Parity):
   برابریِ مسیرهای خواندنی وضعیت سینک، وضعیت دانلود دیتابیس کدال، دیاگ سیستم،
   تریگرهای آفلاین بازار و کدال و ذخیره اسنپ‌شات بازار.
۲. B-G3 (Supervision & Control Parity):
   برابریِ رفتاری فرامین کنترلی خزندهٔ کدال (pause, resume, stop)، ثبتِ فایل
   کنترلی `codal_control.json` در هر دو پوشهٔ ایزوله، و رعایتِ عدم اجرای
   حلقه‌های شبکه‌ای بیرونی در فاز A طبق تصمیمات مصوب مالک (§۱۵.۴).

قواعدِ شکست‌ناپذیر:
- بانک‌هایِ اصلی ریشه هرگز لمس نمی‌شوند (root_before == root_after).
- اجرای تست فقط روی کپی‌های موقتی در پوشهٔ ایزوله.
- مقایسهٔ مو‌به‌مو با تلورانس عددی صفر (delta_zero).
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import gate_b1 as base                                        # noqa: E402
import gate_b2a as engine                                     # noqa: E402

ROOT = base.ROOT
GO = base.GO
CASES = os.path.join(HERE, "cases_b6.json")
OUT = os.environ.get("BORS_B6_OUT") or os.path.join(ROOT, "_audit", "parity", "B6.json")
CONTRACT = (os.environ.get("BORS_B6_CONTRACT")
            or os.path.join(ROOT, "_audit", "parity", "B6-contract.json"))
GO_PORT = int(os.environ.get("BORS_B6_GO_PORT", "8312"))
PY_PORT = int(os.environ.get("BORS_B6_PY_PORT", "8313"))
ROOT_DBS = engine.ROOT_DBS

B6_REQUIRED_ROUTES = {
    "/api/sync/status",
    "/api/sync/codal/db-status",
    "/api/sync/diagnose",
    "/api/mstat/snapshot",
    "/api/codal/control",
    "/api/sync/market",
    "/api/sync/codal",
    "/api/sync/codal/fts-refresh",
    "/api/sync/codal/db-download",
}


def pick_port(preferred, taken):
    for port in range(preferred, preferred + engine.PORT_SCAN):
        if port in taken:
            continue
        if base.port_free(port):
            return port
    raise RuntimeError("no free port near %d" % preferred)


def template_of(path):
    pure = path.split("?", 1)[0]
    return pure


def run_control_verification(py_dir: str, go_dir: str) -> tuple[bool, list[str]]:
    """سنجش رفتاری B-G3: فایل codal_control.json باید پس از آخرین فرمان وجود داشته باشد."""
    problems = []
    py_ctrl_file = os.path.join(py_dir, "codal_control.json")
    go_ctrl_file = os.path.join(go_dir, "codal_control.json")

    if not os.path.exists(py_ctrl_file):
        problems.append("python codal_control.json was not created")
    if not os.path.exists(go_ctrl_file):
        problems.append("go codal_control.json was not created")

    if os.path.exists(py_ctrl_file) and os.path.exists(go_ctrl_file):
        try:
            with open(py_ctrl_file, "r", encoding="utf-8") as f:
                py_data = json.load(f)
            with open(go_ctrl_file, "r", encoding="utf-8") as f:
                go_data = json.load(f)

            if py_data.get("cmd") != go_data.get("cmd"):
                problems.append("control command mismatch: py=%r go=%r" %
                                (py_data.get("cmd"), go_data.get("cmd")))
        except Exception as e:
            problems.append("failed to parse codal_control.json: %s" % e)

    return len(problems) == 0, problems


def main():
    commit = base.run(["git", "rev-parse", "--short", "HEAD"])[1].strip()
    print("gate B6 running against commit %s" % commit)
    root_before = engine.root_fingerprint()
    before_sidecars = base.sidecar_state()

    tmp = tempfile.mkdtemp(prefix="bors_gate_b6_")
    procs = []
    result = 2

    try:
        taken = set()
        go_port = pick_port(GO_PORT, taken)
        taken.add(go_port)
        py_port = pick_port(PY_PORT, taken)
        fell_back = (go_port, py_port) != (GO_PORT, PY_PORT)

        py_dir = os.path.join(tmp, "py")
        go_dir = os.path.join(tmp, "go")
        os.makedirs(py_dir, exist_ok=True)
        os.makedirs(go_dir, exist_ok=True)

        for name in base.DB_NAMES:
            src = os.path.join(ROOT, name)
            if not os.path.exists(src):
                continue
            for dst_dir in (go_dir, py_dir):
                try:
                    check = base.snapshot_db(src, os.path.join(dst_dir, name))
                except Exception as err:
                    print("snapshot copy unusable: %s: %s" % (name, err))
                    return 2
                if check != ["ok"]:
                    print("quick_check failed for %s copy: %s" % (name, check))
                    return 2

        db_prints = base.db_fingerprint(os.path.join(go_dir, "market.db"))
        if db_prints != base.db_fingerprint(os.path.join(py_dir, "market.db")):
            print("the two market.db copies are not identical")
            return 2
        frozen_ok = True

        py_env = os.environ.copy()
        py_env["BORS_DATA_DIR"] = py_dir
        py_env["BORS_PARITY_PORT"] = str(py_port)
        py_env["BORS_NO_FETCH_LOOPS"] = "1"
        py_env["BORS_CODAL_OFFLINE"] = "1"
        py_env["BORS_CODAL_AUTO"] = "0"

        py_log = open(os.path.join(tmp, "py.log"), "w", encoding="utf-8")
        procs.append((subprocess.Popen([sys.executable, base.SERVE], cwd=ROOT, env=py_env,
                                       stdout=py_log, stderr=subprocess.STDOUT), py_log))
        if not base.wait_json("http://127.0.0.1:%d/openapi.json" % py_port, 90.0,
                              lambda b: True):
            print("python server did not become ready")
            return 2

        go_log = open(os.path.join(tmp, "go.log"), "w", encoding="utf-8")
        go_proc = subprocess.Popen(
            [base.BORSD, "--port", str(go_port), "--read-only", "--no-loops",
             "--db-dir", go_dir], cwd=ROOT, stdout=go_log, stderr=subprocess.STDOUT)
        procs.append((go_proc, go_log))
        if not base.wait_json("http://127.0.0.1:%d/healthz" % go_port, 15.0,
                              lambda b: b.get("status") == "ok"):
            print("go server did not become ready")
            return 2
        _, _, health_body = base.http_get("http://127.0.0.1:%d/healthz" % go_port)
        health = json.loads(health_body)
        if os.path.normcase(os.path.normpath(health.get("data_dir", ""))) != \
                os.path.normcase(os.path.normpath(go_dir)):
            print("healthz is not from this gate's server")
            return 2

        py_url = "http://127.0.0.1:%d" % py_port
        go_url = "http://127.0.0.1:%d" % go_port

        with open(CASES, encoding="utf-8") as f:
            spec = json.load(f)
        cases = spec["cases"]
        case_count = len(cases)

        dynamic = os.path.join(tmp, "cases_b6_run.json")
        with open(dynamic, "w", encoding="utf-8") as f:
            json.dump({"cases": cases, "db_sha256": db_prints["market.db"]}, f, ensure_ascii=False)

        # ۱) اجرای B-G1 (Read & Contract Parity):
        rc, log = base.run([base.PARITY, "--py", py_url, "--go", go_url,
                            "--cases", dynamic,
                            "--db", os.path.join(go_dir, "market.db"),
                            "--out", CONTRACT, "--commit", commit])
        print(log.strip())
        if rc == 2:
            print("contract batch could not run")
            return 2
        with open(CONTRACT, encoding="utf-8") as f:
            contract = json.load(f)
        contract_ok = contract["failed"] == 0 and contract["passed"] == case_count
        max_delta = max([c.get("max_delta") or 0.0 for c in contract["cases"]] or [0.0])
        delta_zero = max_delta == 0.0

        pairs = [(c.get("status_py"), c.get("status_go")) for c in contract["cases"]]
        allowed = {(200, 200)}
        statuses_ok = bool(pairs) and all(p in allowed for p in pairs)
        wanted = sorted(c["name"] for c in cases)
        ran = sorted(c["name"] for c in contract["cases"])
        coverage_ok = wanted == ran
        failed_cases = [{"name": c["name"], "diffs": c.get("diffs") or []}
                        for c in contract["cases"] if not c.get("pass")]

        answered = set(template_of(c["path"]) for c in contract["cases"]
                       if c.get("status_go") == 200)
        routes_ok = B6_REQUIRED_ROUTES.issubset(answered)

        # ۲) اجرای B-G3 (Supervision & Control Verification):
        control_ok, control_problems = run_control_verification(py_dir, go_dir)

        base.stop(procs)
        go_db_unchanged = base.db_fingerprint(os.path.join(go_dir, "market.db")) == db_prints
        root_after = engine.root_fingerprint()
        root_untouched = root_before == root_after
        sidecar_problem = base.sidecar_problem(before_sidecars, base.sidecar_state())

        checks = {
            "contract": contract_ok,
            "delta_zero": delta_zero,
            "statuses_200": statuses_ok,
            "case_coverage": coverage_ok,
            "routes_b6_covered": routes_ok,
            "control_parity_bg3": control_ok,
            "go_market_read_only": go_db_unchanged,
            "root_untouched": root_untouched,
            "frozen_copies": frozen_ok,
            "sidecar_untouched": not sidecar_problem,
        }

        payload = {
            "commit": commit,
            "python": sys.version.split()[0],
            "ports": {"py": py_port, "go": go_port, "preferred_py": PY_PORT,
                      "preferred_go": GO_PORT, "fell_back": fell_back},
            "db": {"market_sha256": db_prints["market.db"],
                   "frozen_ok": frozen_ok, "go_market_unchanged": go_db_unchanged,
                   "root_before": root_before, "root_after": root_after,
                   "root_untouched": root_untouched},
            "sidecar": {"ok": not sidecar_problem, "problem": sidecar_problem or ""},
            "statuses": {"pairs": sorted("%s/%s" % p for p in set(pairs)),
                         "ok": statuses_ok},
            "contract": {"passed": contract["passed"], "failed": contract["failed"],
                         "cases": case_count, "max_delta": max_delta,
                         "report": os.path.relpath(CONTRACT, ROOT), "ok": contract_ok,
                         "failed_cases": failed_cases},
            "control_verification": {
                "ok": control_ok,
                "problems": control_problems,
            },
            "answered_templates": sorted(answered),
            "checks": checks,
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(OUT, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print("checks: " + " ".join("%s=%s" % kv for kv in checks.items()))
        print("contract %d/%d | max_delta=%s | control_ok=%s"
              % (contract["passed"], case_count, max_delta, control_ok))
        for row in failed_cases:
            print("FAILED %s: %s" % (row["name"], "; ".join(row["diffs"][:4])))
        for p in control_problems:
            print("CONTROL %s" % p)
        result = 0 if all(checks.values()) else 1
    finally:
        base.stop(procs)
        problem = base.sidecar_problem(before_sidecars, base.sidecar_state())
        if problem:
            print("sidecar guard failed: %s" % problem)
            result = 2
        if result != 0:
            engine.dump_logs(tmp)
        shutil.rmtree(tmp, ignore_errors=True)
    if result == 0:
        print("sidecar guard ok")
    return result


if __name__ == "__main__":
    sys.exit(main())
