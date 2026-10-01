# -*- coding: utf-8 -*-
"""What the three adjustment modes MUST show, computed from our own backend.

Reproduces frontend/.../nahayatnegar/lib/adjustments.ts exactly
(applyAdjustmentToCandles + toPerformanceSeries) so the live UI can be checked
against numbers, not impressions.
"""
import datetime as dt
import json
import sys
import urllib.parse
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001"
SYMBOL = sys.argv[2] if len(sys.argv) > 2 else "فولاد"
DATES = sys.argv[3:] or ["2026-09-30", "2025-08-06", "2025-03-13",
                         "2024-02-28", "2015-09-27", "2007-03-11"]


def factor(ratio):
    return min(max(ratio, 0.0001), 50.0) if ratio > 0 else 1.0


def main():
    url = "%s/api/chart/%s" % (BASE, urllib.parse.quote(SYMBOL))
    with urllib.request.urlopen(url, timeout=240) as r:
        j = json.loads(r.read().decode())
    candles = j.get("candles") or []
    events = [e for e in (j.get("adjustEvents") or [])
              if e.get("date") and 0.02 < float(e.get("ratio") or 0) < 50]
    ev_ts = {dt.datetime.strptime(e["date"], "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
             .timestamp() * 1000: factor(float(e["ratio"])) for e in events}
    by_date = {c.get("time"): c for c in candles}
    first = candles[-1] if candles else None          # the API returns newest first
    base_close = float(first["close"]) if first else 0.0

    print("symbol=%s candles=%d events_kept=%d/%d  series_base(%s)=%s"
          % (SYMBOL, len(candles), len(ev_ts), len(j.get("adjustEvents") or []),
             first.get("time") if first else "-", base_close))

    for d in DATES:
        c = by_date.get(d)
        if not c:
            print("  %s  (no candle)" % d)
            continue
        ts = dt.datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp() * 1000
        cum = 1.0
        for e_ts, f in ev_ts.items():
            if ts < e_ts:
                cum *= f
        raw = float(c["close"])
        combined = round(raw * cum)
        perf = round(combined / base_close * 100, 2) if base_close > 0 else raw
        print("  %s  raw=%-10s x%.8f  combined=%-10s  performance=%s"
              % (d, int(raw), cum, int(combined), perf))

    print("\n  (performance is rebased on the FIRST candle of the loaded window; "
          "changing the visible range changes the axis, by design)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
