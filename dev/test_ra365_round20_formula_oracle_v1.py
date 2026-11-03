#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 20: keep the proven Rahavard formulas separate from the unverified ones."""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

spec = importlib.util.spec_from_file_location(
    "r20marks", os.path.join(ROOT, "tools", "ra365_round20_marks_oracle.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


def close(a, b, eps=1e-6):
    return a is not None and b is not None and abs(float(a) - float(b)) <= eps


def main():
    ck(close(M.dps_ratio(17190, 1020), 17190 / (17190 + 1020)),
       "DPS: close_ex/(close_ex+dps)")
    ck(close(M.dps_ratio(16950, 10000), 0.62894249),
       "DPS: سهرمز 2026 sample is exact", M.dps_ratio(16950, 10000))
    ck(M.dps_ratio(0, 100) is None and M.dps_ratio(100, -1) is None,
       "DPS: invalid inputs never fabricate a ratio")

    ck(close(M.reserve_ratio(2367650648000, 3311362648000), 0.71500796),
       "reserve: pv/nw is exact", M.reserve_ratio(2367650648000, 3311362648000))
    ck(M.reserve_ratio(0, 100) is None, "reserve: zero previous shares is refused")

    r = M.contribution_ratio(1000, 1500, 100, 0, 2000)
    ck(close(r, (1000 * 2000 + 500 * 1000) / (1500 * 2000)),
       "contribution: structural formula with a documented S/P", r)
    ck(M.contribution_ratio(1000, 1500, 100, 0, None) is None,
       "contribution: missing reference price is not guessed")
    ck(M.contribution_ratio(1500, 1000, 100, 0, 2000) is None,
       "contribution: new<previous is refused")

    print("\n%d passed, %d failed" % (P, F))
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
