#!/usr/bin/env python3
"""Record CI for one exact commit into the preserved evidence chain.

CI-FINAL-RESULTS.json is bound to the artifact commit and is never overwritten:
a file cannot contain CI results about itself.  Every later commit's CI is
recorded separately here, reusing fetch_ci's per-job and base-attribution logic
unchanged so the three success flags stay separate and a report-only failure is
still compared suite-by-suite against the base commit.

Usage:  python record_ci_for_commit.py --sha <40-char commit> [--no-wait]
Output: _audit/phase49-3/evidence/CI-<first 8>.json
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import fetch_ci


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sha", required=True)
    ap.add_argument("--no-wait", action="store_true")
    args = ap.parse_args()
    sha = args.sha.strip()
    if len(sha) != 40:
        sys.exit("FATAL: --sha must be a full 40-character commit SHA")
    out = os.path.join(HERE, "evidence", "CI-%s.json" % sha[:8])
    if os.path.exists(out):
        sys.exit("FATAL: %s already exists; preserved CI records are never"
                 " overwritten" % out)
    fetch_ci.OUT = out
    sys.argv = ["fetch_ci.py", "--sha", sha]
    if args.no_wait:
        sys.argv.append("--no-wait")
    rc = fetch_ci.main()
    print("RECORDED=%s rc=%d" % (out, rc), flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())