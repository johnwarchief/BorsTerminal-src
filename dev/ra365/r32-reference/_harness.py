#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared harness for the Round 32A reference-tool tests.

Prints the "result: N pass, M fail" / "P/T" pair that dev/run_all_tests.py
parses, and exits non-zero on the first failure count so a red suite is red.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TOOLS = os.path.join(ROOT, "tools", "ra365", "r32-reference")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

P = 0
F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   <- %s" % (detail,)) if detail else ""))


def report():
    print()
    print("result: %d pass, %d fail" % (P, F))
    print("%d/%d" % (P, P + F))
    sys.exit(0 if F == 0 else 1)


def tmp_csv(name, header, rows):
    """Write a small utf-8 CSV under the OS temp dir and return its path."""
    import csv
    import tempfile
    d = os.path.join(tempfile.gettempdir(), "r32-reference-tests")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path