# -*- coding: utf-8 -*-
"""Pick the symbols that stress the adjustment modes most.

Events are what the backend sees (base-price discontinuity in the TSETMC
history), so the ranking has to come from the app itself, not from the local
daily_prices table — that is only a short rolling window.
"""
import json
import sys
import time
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8001"
CANDIDATES = ["فولاد", "خودرو", "وسپنا", "شپنا", "فملی", "خگستر", "وتوسن", "پارس",
              "شبندر", "كروز", "وبهمن", "وغدير", "شگونا", "وحکمت", "سبهان", "غزوی"]


def main():
    top = []
    for sym in CANDIDATES:
        url = "%s/api/chart/%s" % (BASE, urllib.parse.quote(sym))
        t0 = time.time()
        try:
            with urllib.request.urlopen(url, timeout=240) as r:
                j = json.loads(r.read().decode())
        except Exception as e:
            print("%-9s ERR %s" % (sym, type(e).__name__))
            continue
        ev = j.get("adjustEvents") or []
        ratios = sorted(float(e["ratio"]) for e in ev)
        worst = ratios[0] if ratios else 1.0
        top.append((len(ev), sym, j.get("count"), j.get("adjustSource"), worst))
        print("  %-9s events=%-4d candles=%-6s worst_ratio=%.4f  (%.1fs)"
              % (sym, len(ev), j.get("count"), worst, time.time() - t0), flush=True)
    top.sort(reverse=True)
    print("\nranked:")
    for n, sym, cnt, src, worst in top:
        print("  %-9s %3d events  %s candles" % (sym, n, cnt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
