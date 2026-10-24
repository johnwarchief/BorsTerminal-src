# -*- coding: utf-8 -*-
"""Guard: /api/chart/{symbol} must be served by get_chart_tsetmc.

A helper inserted between the decorator and its function silently moved the
route onto `_candle_closings` (origin/main 01ded7d). FastAPI then treated the
helper's `candles` argument as a required input and every chart request died
with 422; the UI still painted a canvas and the FTS strip, so only an HTTP call
caught it. This guard is structural and offline.
"""
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import api.chart as C  # noqa: E402

CHECKS = []


def ck(label, ok, detail=""):
    CHECKS.append(bool(ok))
    print(("OK   " if ok else "FAIL ") + label + (("  ⟨%s⟩" % detail) if detail else ""))


PATH = "/api/chart/{symbol}"
routes = [r for r in C.router.routes if getattr(r, "path", None) == PATH]
ck("exactly one chart route", len(routes) == 1, "n=%d" % len(routes))
route = routes[0] if routes else None
ep = getattr(route, "endpoint", None)
ck("chart endpoint is get_chart_tsetmc", ep is C.get_chart_tsetmc,
   getattr(ep, "__name__", "?"))
ck("chart route is GET", "GET" in (getattr(route, "methods", set()) or set()))
ck("chart endpoint takes symbol", "symbol" in inspect.signature(ep).parameters
   if ep else False)
ck("_candle_closings is not exposed as a route",
   all(getattr(r, "endpoint", None) is not C._candle_closings
       for r in C.router.routes))
ck("key-levels route still present",
   any(getattr(r, "path", None) == "/api/chart/{symbol}/key-levels"
       for r in C.router.routes))
# FastAPI's aggregate router is lazy in this version (_IncludedRouter), so the
# module-level route table is the authoritative place to catch a misattached
# decorator; the production app includes this same router object unchanged.

failed = len(CHECKS) - sum(CHECKS)
print("\nchart route guard: %d passed / %d failed" % (sum(CHECKS), failed))
sys.exit(1 if failed else 0)
