#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Phase 4.9.1 C5 — thin runner for the Seed Candidate parity/product checks.

Executes, records and classifies (never rewrites) the brief's harnesses:

  1. dev/test_phase49_correction_parity_v1.py     (Python fixture, 76 checks)
  2. go test ./internal/chart -run 'TestPhase49|TestAdjustEngine' -v
  3. stageE_engine_parity_new.py                  (Python<->Go, 30 symbols)
  4. go test ./internal/chart -run ChartDB -v     (no false Live/Verified)
  5. `npx vitest run src/features/chart`          (source label assertion)
  6. stageE_product_tests_new.py                  (clean/merge/restart/MA/W/M)

Writes tracked evidence:
  evidence/parity.json          (checks 1-5)
  evidence/product-tests.json   (product harness checks + SHA provenance)

A harness that cannot import a missing dependency is recorded as NOT_MEASURED
with its traceback; it is never reported as PASS. `--parity-only` regenerates
only evidence/parity.json and leaves the product evidence untouched.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVID = os.path.join(ROOT, "_audit", "phase49-full-verification", "evidence")
DB = os.path.join(ROOT, "_audit", "phase49-full-verification", "seed", "market.db")
SEED_LZMA = DB + ".lzma"
BIN = os.path.join(ROOT, "_audit", "phase49-full-verification", "borsd.exe")
PACK = os.path.join(ROOT, "data", "ra365_corrections",
                    "ra365-phase49-rebuild-full-v2")
REF_BARS = os.path.join(ROOT, "_audit", "phase49-full-verification", "captures",
                        "bars-all.ndjson.gz")
ENGINE_OUT = os.path.join(ROOT, "_audit", "phase49-full-verification",
                          "engine-parity-30.json")
PRODUCT_OUT = os.path.join(ROOT, "_audit", "phase49-full-verification", "db",
                           "product-test-report.json")
UPGRADE_DB = os.path.join(ROOT, "_audit", "phase49-full-verification", "db",
                          "product-test", "upgrade", "market.db")
PY_FIXTURE = os.path.join(ROOT, "dev", "test_phase49_correction_parity_v1.py")
ENGINE_HARNESS = os.path.join(ROOT, "_audit", "phase49-full-verification",
                              "stageE_engine_parity_new.py")
PRODUCT_HARNESS = os.path.join(ROOT, "_audit", "phase49-full-verification",
                               "stageE_product_tests_new.py")

MISSING_DEPS = ("fastapi", "numpy", "pandas")


def rel(path):
    return os.path.relpath(path, ROOT).replace("\\", "/")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd, cwd=ROOT, timeout=3600):
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout,
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return {
        "cmd": cmd,
        "cwd": rel(cwd),
        "returncode": proc.returncode,
        "duration_s": round(time.time() - t0, 1),
        "stdout": proc.stdout.decode("utf-8", "replace"),
        "stderr": proc.stderr.decode("utf-8", "replace"),
    }


def missing_dependency(text):
    for dep in MISSING_DEPS:
        if re.search(r"No module named '%s'" % re.escape(dep), text):
            return dep
    return None


def tail(text, n=40):
    return "\n".join(text.strip().splitlines()[-n:])


def db_count(db, sql, args=()):
    con = sqlite3.connect(db)
    try:
        return con.execute(sql, args).fetchone()[0]
    finally:
        con.close()


def weekday_iso(d):
    import datetime
    y, w, _ = datetime.date.fromisoformat(d).isocalendar()
    return "%04d-W%02d" % (y, w)


def product_checks(report, seed_facts):
    tests = report.get("tests") or {}
    checks = {}

    def add(name, ok, detail):
        checks[name] = {"pass": bool(ok), "detail": detail}

    clean = tests.get("clean_install") or {}
    st = clean.get("seed_state") or {}
    chart = clean.get("chart") or {}
    wm = clean.get("wm") or {}
    add("clean_extraction",
        st.get("status") == "applied" and st.get("mode") == "extract"
        and clean.get("db_rows") == seed_facts["price_history_rows"]
        and clean.get("provenance_rows") == seed_facts["provenance_rows"]
        and clean.get("validity_rows") == seed_facts["validity_rows"],
        {"seed_state": {k: st.get(k) for k in ("status", "mode", "price_history_rows")},
         "db_rows": clean.get("db_rows"),
         "provenance_rows": clean.get("provenance_rows"),
         "validity_rows": clean.get("validity_rows")})
    add("clean_chart_db",
        chart.get("count") == seed_facts["foolad_rows"]
        and chart.get("first") == seed_facts["foolad_first"]
        and chart.get("last") == seed_facts["foolad_last"],
        {"chart": chart, "seed": seed_facts["foolad"]})
    add("clean_daily_reference",
        (chart.get("adj_sample_n") or 0) > 0,
        {"adj_sample_n": chart.get("adj_sample_n"),
         "adj_sample_max_rel": chart.get("adj_sample_max_rel"),
         "adj_sample_median_rel": chart.get("adj_sample_median_rel")})
    add("clean_weekly",
        (wm.get("W") or {}).get("count", 0) > 0
        and (wm.get("W") or {}).get("last") == weekday_iso(chart["last"][:10]),
        wm.get("W"))
    add("clean_monthly",
        (wm.get("M") or {}).get("count", 0) > 0
        and (wm.get("M") or {}).get("last") == chart["last"][:7],
        wm.get("M"))

    up = tests.get("upgrade_merge") or {}
    ust = up.get("state") or {}
    uchart = up.get("chart") or {}
    uwm = up.get("wm") or {}
    add("upgrade_merge",
        ust.get("status") == "applied" and ust.get("mode") == "merge"
        and up.get("rows") == seed_facts["price_history_rows"]
        and up.get("provenance_rows") == seed_facts["provenance_rows"],
        {"state": ust, "rows": up.get("rows"),
         "provenance_rows": up.get("provenance_rows")})
    add("user_data_preservation",
        up.get("modified_row_kept") is True and up.get("watchlist_kept") is True,
        {"modified_row_kept": up.get("modified_row_kept"),
         "watchlist_kept": up.get("watchlist_kept")})
    add("upgrade_chart_db",
        uchart.get("count") == seed_facts["foolad_rows"]
        and uchart.get("first") == seed_facts["foolad_first"]
        and uchart.get("last") == seed_facts["foolad_last"],
        {"chart": uchart, "seed": seed_facts["foolad"]})
    add("upgrade_weekly",
        (uwm.get("W") or {}).get("last") == weekday_iso(uchart["last"][:10]),
        uwm.get("W"))
    add("upgrade_monthly",
        (uwm.get("M") or {}).get("last") == uchart["last"][:7],
        uwm.get("M"))

    ma = tests.get("ma_full_history") or {}
    add("ma_full_history",
        (ma.get("count") or 0) == 4 and "ma" in (ma.get("keys") or []),
        ma)

    dups = None
    if os.path.exists(UPGRADE_DB):
        dups = db_count(UPGRADE_DB,
                        "SELECT COUNT(*) FROM (SELECT symbol,date FROM price_history "
                        "GROUP BY symbol,date HAVING COUNT(*) > 1)")
    r = tests.get("restart_idempotent") or {}
    rchart = r.get("chart") or {}
    add("restart_idempotent",
        r.get("same") is True and (dups == 0)
        and rchart.get("count") == seed_facts["foolad_rows"],
        {"rows_before": r.get("rows_before"), "rows_after": r.get("rows_after"),
         "duplicate_symbol_dates": dups, "restart_state_reason": r.get("state_reason"),
         "restart_chart_count": rchart.get("count")})
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parity-only", action="store_true",
                    help="regenerate evidence/parity.json only; leave product evidence")
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    generated = time.strftime("%Y-%m-%dT%H:%M:%S")
    commit = run(["git", "rev-parse", "HEAD"])["stdout"].strip()
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])["stdout"].strip()

    seed_facts = {
        "price_history_rows": db_count(DB, "SELECT COUNT(*) FROM price_history"),
        "provenance_rows": db_count(DB, "SELECT COUNT(*) FROM raw_history_corrections"),
        "validity_rows": db_count(DB, "SELECT COUNT(*) FROM history_validity"),
        "foolad_rows": db_count(DB, "SELECT COUNT(*) FROM price_history WHERE symbol='فولاد'"),
        "foolad_first": db_count(DB, "SELECT MIN(date) FROM price_history WHERE symbol='فولاد'"),
        "foolad_last": db_count(DB, "SELECT MAX(date) FROM price_history WHERE symbol='فولاد'"),
    }
    seed_facts["foolad"] = {"rows": seed_facts["foolad_rows"],
                            "first": seed_facts["foolad_first"],
                            "last": seed_facts["foolad_last"]}

    default_python = None
    for cand in ("python", "python3"):
        probe = run([cand, "-c", "import fastapi, numpy; print(fastapi.__version__, numpy.__version__)"],
                    timeout=120)
        default_python = {"cmd": cand, "returncode": probe["returncode"],
                          "stdout": probe["stdout"].strip(),
                          "stderr": probe["stderr"].strip()}
        if probe["returncode"] == 0 or "No module named" in probe["stderr"]:
            break
    environment = {
        "interpreter": sys.executable,
        "python_version": sys.version.split()[0],
        "fastapi_numpy_probe_python": default_python,
        "go": run(["go", "version"])["stdout"].strip(),
    }

    inputs = {
        "seed_db": {"path": rel(DB), "sha256": sha256_file(DB)},
        "seed_lzma": {"path": rel(SEED_LZMA), "sha256": sha256_file(SEED_LZMA)},
        "borsd": {"path": rel(BIN), "sha256": sha256_file(BIN)},
        "pack": {"path": rel(PACK),
                 "manifest_sha256": sha256_file(os.path.join(PACK, "manifest.json")),
                 "factors_sha256": sha256_file(os.path.join(PACK, "factors.jsonl")),
                 "raw_ohlc_sha256": sha256_file(os.path.join(PACK, "raw_ohlc.jsonl"))},
        "reference_bars": {"path": rel(REF_BARS), "sha256": sha256_file(REF_BARS)},
    }

    # 1) Python fixture parity -------------------------------------------------
    pyfix = run([sys.executable, PY_FIXTURE])
    m = re.search(r"(\d+) passed / (\d+) failed", pyfix["stdout"])
    passed, failed = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    pyfix_check = {
        "status": "PASS" if pyfix["returncode"] == 0 and failed == 0 and passed else "FAIL",
        "passed": passed, "failed": failed,
        "command": "python dev/test_phase49_correction_parity_v1.py",
        "interpreter": sys.executable,
        "artifact": rel(PY_FIXTURE),
        "output_tail": tail(pyfix["stdout"]),
        "stderr": pyfix["stderr"].strip()[:2000],
    }
    # 1b) the same fixture with the default `python` on PATH, exactly as the
    # brief spells the command (this interpreter lacks fastapi/numpy, but the
    # fixture does not import them).
    pyfix_default = None
    if default_python:
        probe = run([default_python["cmd"], PY_FIXTURE])
        m = re.search(r"(\d+) passed / (\d+) failed", probe["stdout"])
        pyfix_default = {
            "status": "PASS" if probe["returncode"] == 0 and m and m.group(2) == "0"
                      else "FAIL",
            "passed": int(m.group(1)) if m else None,
            "failed": int(m.group(2)) if m else None,
            "command": "python dev/test_phase49_correction_parity_v1.py",
            "interpreter": default_python["cmd"],
            "output_tail": tail(probe["stdout"]),
            "stderr": probe["stderr"].strip()[:2000],
        }

    # 2) Go parity suites ------------------------------------------------------
    gocmd = ["go", "test", "./internal/chart", "-run", "TestPhase49|TestAdjustEngine", "-v"]
    gotest = run(gocmd, cwd=os.path.join(ROOT, "backend-go"))
    go_passes = re.findall(r"^--- PASS: (\S+)", gotest["stdout"], re.M)
    go_fails = re.findall(r"^--- FAIL: (\S+)", gotest["stdout"], re.M)
    go_check = {
        "status": "PASS" if gotest["returncode"] == 0 and not go_fails else "FAIL",
        "command": "cd backend-go && go test ./internal/chart -run "
                   "'TestPhase49|TestAdjustEngine' -v",
        "matched_tests": go_passes,
        "failed_tests": go_fails,
        "note": "the pattern matches TestPhase49ParityFixture; the adjustment "
                "engine suite is named TestAdjustmentEngine (not matched here)",
        "output_tail": tail(gotest["stdout"]),
        "stderr": gotest["stderr"].strip()[:2000],
    }

    # 2b) Step 3: no false verified/live label from /api/chart-db --------------
    gcdb = run(["go", "test", "./internal/chart", "-run", "ChartDB", "-v"],
               cwd=os.path.join(ROOT, "backend-go"), timeout=1800)
    gcdb_passes = re.findall(r"^--- PASS: (\S+)", gcdb["stdout"], re.M)
    gcdb_fails = re.findall(r"^--- FAIL: (\S+)", gcdb["stdout"], re.M)
    label_check = {
        "status": "PASS" if gcdb["returncode"] == 0 and not gcdb_fails else "FAIL",
        "command": "cd backend-go && go test ./internal/chart -run 'ChartDB' -v",
        "matched_tests": gcdb_passes, "failed_tests": gcdb_fails,
        "test_file": "backend-go/internal/chart/phase49_labels_test.go",
        "contract": "history_validity.status='unverified' must not yield "
                    "verified:true / live:true anywhere in the payload",
        "output_tail": tail(gcdb["stdout"]),
        "stderr": gcdb["stderr"].strip()[:2000],
    }

    # 3) Engine parity against the new candidate -------------------------------
    for path in (ENGINE_OUT,):
        if os.path.exists(path):
            os.remove(path)
    eng = run([sys.executable, ENGINE_HARNESS])
    miss = missing_dependency(eng["stderr"] + eng["stdout"])
    if miss:
        engine_check = {"status": "NOT_MEASURED", "missing_dependency": miss,
                        "command": "python _audit/phase49-full-verification/"
                                   "stageE_engine_parity_new.py",
                        "interpreter": sys.executable,
                        "traceback": tail(eng["stderr"] or eng["stdout"], 25)}
    elif eng["returncode"] == 0 and os.path.exists(ENGINE_OUT):
        er = json.load(open(ENGINE_OUT, encoding="utf-8"))
        engine_check = {
            "status": "PASS" if not er.get("mismatches") and er.get("symbols") == 30
                      and er.get("passed") == 30 else "FAIL",
            "command": "python _audit/phase49-full-verification/"
                       "stageE_engine_parity_new.py",
            "interpreter": sys.executable,
            "symbols": er.get("symbols"), "passed": er.get("passed"),
            "mismatches": er.get("mismatches"),
            "artifact": rel(ENGINE_OUT),
            "per_symbol": er.get("per_symbol"),
            "output_tail": tail(eng["stdout"]),
        }
    else:
        engine_check = {"status": "FAIL", "command": "python _audit/phase49-full-verification/"
                        "stageE_engine_parity_new.py", "returncode": eng["returncode"],
                        "output_tail": tail(eng["stdout"]), "stderr": tail(eng["stderr"])}

    # 3b) Step 3: Vitest source assertion (frontend deps may be absent) --------
    fe = os.path.join(ROOT, "frontend-v2")
    vitest_mjs = os.path.join(fe, "node_modules", "vitest", "vitest.mjs")
    node = shutil.which("node")
    if not os.path.exists(vitest_mjs) or not node:
        missing = []
        if not os.path.exists(os.path.join(fe, "node_modules")):
            missing.append("frontend-v2/node_modules absent; `npm ci --offline` fails "
                           "ENOTCACHED for zustand@5.0.16, then for vitest")
        elif not os.path.exists(vitest_mjs):
            missing.append("vitest not installed in frontend-v2/node_modules")
        if not node:
            missing.append("node not on PATH")
        vitest_check = {
            "status": "NOT_MEASURED",
            "missing_dependency": "; ".join(missing),
            "command": "cd frontend-v2 && npx vitest run src/features/chart",
            "source_test": "frontend-v2/src/features/chart/__tests__/chartLabels.test.ts",
            "source_test_committed": os.path.exists(os.path.join(
                fe, "src", "features", "chart", "__tests__", "chartLabels.test.ts")),
        }
    else:
        vit = run([node, vitest_mjs, "run", "src/features/chart"], cwd=fe, timeout=1800)
        vitest_check = {
            "status": "PASS" if vit["returncode"] == 0 else "FAIL",
            "command": "cd frontend-v2 && npx vitest run src/features/chart",
            "source_test": "frontend-v2/src/features/chart/__tests__/chartLabels.test.ts",
            "output_tail": tail(vit["stdout"] + vit["stderr"]),
        }

    parity = {
        "schema": "phase49-full-verification-parity-v1",
        "generated_at": generated, "commit": commit, "branch": branch,
        "environment": environment, "inputs": inputs,
        "checks": {
            "python_fixture_parity": pyfix_check,
            "python_fixture_parity_default_python": pyfix_default,
            "go_parity_suites": go_check,
            "chartdb_labels": label_check,
            "engine_parity_30_symbols": engine_check,
            "vitest_chart": vitest_check,
        },
    }
    with open(os.path.join(EVID, "parity.json"), "w", encoding="utf-8") as fh:
        json.dump(parity, fh, ensure_ascii=False, indent=1)
    print("PARITY:", json.dumps({k: (v or {}).get("status")
                                 for k, v in parity["checks"].items()}, ensure_ascii=False))
    if args.parity_only:
        print("PARITY-ONLY: product evidence left untouched")
        return 0

    # 4) Product harness -------------------------------------------------------
    if os.path.exists(PRODUCT_OUT):
        os.remove(PRODUCT_OUT)
    prod = run([sys.executable, PRODUCT_HARNESS], timeout=7200)
    miss = missing_dependency(prod["stderr"] + prod["stdout"])
    if miss:
        product = {"schema": "phase49-full-verification-product-tests-v1",
                   "status": "NOT_MEASURED", "missing_dependency": miss,
                   "traceback": tail(prod["stderr"] or prod["stdout"], 25)}
    elif prod["returncode"] == 0 and os.path.exists(PRODUCT_OUT):
        raw = json.load(open(PRODUCT_OUT, encoding="utf-8"))
        try:
            checks = product_checks(raw, seed_facts)
            status = "PASS" if all(c["pass"] for c in checks.values()) else "FAIL"
        except Exception as exc:  # noqa: BLE001 — record, never crash without evidence
            checks = {"harness_evaluation": {
                "pass": False, "detail": "evaluation error: %r" % (exc,)}}
            status = "FAIL"
        product = {
            "schema": "phase49-full-verification-product-tests-v1",
            "status": status,
            "command": "python _audit/phase49-full-verification/"
                       "stageE_product_tests_new.py",
            "artifact": {"raw": rel(PRODUCT_OUT)},
            "checks": checks,
            "harness_report": raw,
        }
    else:
        product = {"schema": "phase49-full-verification-product-tests-v1",
                   "status": "FAIL", "returncode": prod["returncode"],
                   "output_tail": tail(prod["stdout"]), "stderr": tail(prod["stderr"])}
    product.update({"generated_at": generated, "commit": commit, "branch": branch,
                    "environment": {"interpreter": sys.executable},
                    "inputs": inputs, "seed_facts": seed_facts})
    with open(os.path.join(EVID, "product-tests.json"), "w", encoding="utf-8") as fh:
        json.dump(product, fh, ensure_ascii=False, indent=1)

    print("PARITY:", json.dumps({k: v.get("status") for k, v in parity["checks"].items()},
                                ensure_ascii=False))
    print("PRODUCT:", product.get("status"),
          json.dumps({k: v.get("pass") for k, v in (product.get("checks") or {}).items()},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
