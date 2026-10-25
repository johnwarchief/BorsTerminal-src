#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Turn the full-gate log into a small machine-readable status file."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "artifacts", "ra365", "r32b", "gate")
LOG = os.path.join(ART, "full-gate.log")
OUT = os.path.join(ART, "gate-status.json")


def main():
    text = open(LOG, encoding="utf-8", errors="replace").read()
    ok = len(re.findall(r"^\s+OK\s+", text, re.M))
    fail = len(re.findall(r"^\s+FAIL\s+", text, re.M))
    skip = len(re.findall(r"^\s+SKIP\s+", text, re.M))
    passed = "ALL SUITES PASSED" in text
    protected = "NOT_MEASURED"
    m = re.search(r"PROTECTED_DB_UNCHANGED[^\n]*", text)
    if m:
        protected = m.group(0).strip()
    elif "PROTECTED_DB_CHANGED" in text:
        protected = "PROTECTED_DB_CHANGED"
    logical = ""
    m = re.search(r"logical_total=([0-9a-f]+)", text)
    if m:
        logical = m.group(1)
    failures = re.findall(r"^\s+FAIL\s+([^\n]*)", text, re.M)
    verdict = "ALL SUITES PASSED" if passed and fail == 0 else "FAILED"
    status = {
        "verdict": verdict,
        "ok": ok,
        "fail": fail,
        "skip": skip,
        "protected": protected,
        "logical_total": logical,
        "failures": failures[:50],
        "log": "artifacts/ra365/r32b/gate/full-gate.log",
    }
    json.dump(status, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(status, ensure_ascii=False, indent=1))
    return 0 if verdict == "ALL SUITES PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
