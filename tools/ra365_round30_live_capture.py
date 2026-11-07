#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 30: capture the live /api/chart handler for Stage D comparison.

Calls the exact handler behind `GET /api/chart/{symbol}` (after the route
wiring fix), one symbol at a time, and saves the response.  Uses BORS_DB from
the environment (must point at an isolated copy); no database writes are
performed by this tool itself.

Usage:
  BORS_DB=<isolated.db> python tools/ra365_round30_live_capture.py \
      --symbols "مفاخر,حفارس,..." --out D:/BorsTerminal-tmp/r30_live/payloads
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    import api.chart as C
    C.CHART_CACHE.clear()
    led = []
    for sym in [s.strip() for s in a.symbols.split(",") if s.strip()]:
        t = time.time()
        try:
            res = C.get_chart_visible(sym)
            state = res.get("status") or "UNKNOWN"
            path = os.path.join(a.out, sym + ".json")
            json.dump(res, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            state = "ERROR"
            path = ""
            res = {}
            print("ERR", sym, type(e).__name__, str(e)[:160], flush=True)
        led.append({"symbol": sym, "state": state, "path": path,
                    "candles": len(res.get("candles") or []),
                    "events": len(res.get("adjustEvents") or []),
                    "seconds": round(time.time() - t, 2)})
        print(sym, state, len(res.get("candles") or []),
              round(time.time() - t, 1), "s", flush=True)
    json.dump({"symbols": led}, open(os.path.join(a.out, "..", "live-ledger.json"),
                                     "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
