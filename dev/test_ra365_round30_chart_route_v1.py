#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 30: the live chart route must be wired to the live handler.

The Round 29 base left `@router.get("/api/chart/{symbol}")` on the helper
`_candle_closings(candles)`, so the OpenAPI schema required a `candles` query
and `GET /api/chart/فولاد` could never reach `get_chart_tsetmc`.  The market
chart component calls exactly this route.  The guard is structural (no
network, no DB rows): the path parameter must be the symbol and the route
must not require a candles query.  `/api/chart-db/{symbol}` stays intact.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import app as APP  # noqa: E402

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


spec = APP.app.openapi()
chart = spec["paths"]["/api/chart/{symbol}"]["get"]
params = [(p.get("name"), p.get("in"), bool(p.get("required")))
          for p in chart.get("parameters", [])]
ck(("symbol", "path", True) in params,
   "the live chart route exposes the symbol path parameter", params)
ck(not any(name == "candles" for name, _where, _req in params),
   "the live chart route does not require a candles query", params)

db = spec["paths"]["/api/chart-db/{symbol}"]["get"]
dbp = [(p.get("name"), p.get("in"), bool(p.get("required")))
       for p in db.get("parameters", [])]
ck(("symbol", "path", True) in dbp and not any(n == "candles" for n, _w, _r in dbp),
   "the database chart route keeps its symbol path parameter", dbp)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
