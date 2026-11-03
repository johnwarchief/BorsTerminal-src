#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 27: timeframe audit contract (D/W/M) regression tests."""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

spec = importlib.util.spec_from_file_location("aud", os.path.join(ROOT, "tools", "ra365_round27_audit.py"))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


ck(A.week_key("2024-03-23") == A.week_key("2024-03-27"),
   "Saturday and Wednesday share one weekly bucket")
ck(A.week_key("2024-03-22") != A.week_key("2024-03-23"),
   "Friday closes the previous weekly bucket")

ck(A.month_key("2026-09-23") == A.month_key("2026-10-22"),
   "Mehr 1405 spans 2026-09-23 … 2026-10-22")
ck(A.month_key("2026-10-23") != A.month_key("2026-10-22"),
   "Aban 1405 starts on 2026-10-23")
ck(A.month_key("2014-03-21") == 1393 * 12 + 0,
   "2014-03-21 is 1 Farvardin 1393", A.month_key("2014-03-21"))

rows = [
    ("2024-03-23", 10, 12, 9, 11, 100),
    ("2024-03-24", 11, 15, 10, 14, 200),
    ("2024-03-27", 14, 14, 8, 9, 300),
]
w = A.aggregate(rows, A.week_key)
bar = list(w.values())[0]
ck(bar[:5] == [10, 15, 8, 9, 600] and bar[5] == "2024-03-27",
   "weekly OHLCV = first/max/min/last/sum with the last stamp", bar)

m = A.aggregate([("2026-09-23", 5, 6, 4, 5, 10), ("2026-10-22", 5, 7, 3, 6, 20)], A.month_key)
ck(list(m.values())[0][:5] == [5, 7, 3, 6, 30],
   "monthly aggregation joins by the Jalali key", list(m.values())[0])

f = {"2024-03-23": 0.5, "2024-03-24": 0.5, "2024-03-27": 0.25}
fa = A.reanchor(f, "2024-03-27")
ck(abs(fa["2024-03-27"] - 1.0) < 1e-12 and abs(fa["2024-03-23"] / 2.0 - 1.0) < 1e-12,
   "re-anchoring sets the anchor factor to 1 and preserves ratios", fa)

raw = [("2024-03-23", 10, 12, 9, 11, 100), ("2024-03-24", 11, 15, 10, 14, 200)]
fac = {"2024-03-23": 0.5, "2024-03-24": 0.25}
adj_daily = [(d, o * fac[d], h * fac[d], l * fac[d], c * fac[d], v) for d, o, h, l, c, v in raw]
w_raw = A.aggregate(raw, A.week_key)
w_adj = A.aggregate(adj_daily, A.week_key)
b_raw, b_adj = list(w_raw.values())[0], list(w_adj.values())[0]
ck(abs(b_adj[0] - b_raw[0] * 0.5) < 1e-12 and abs(b_adj[3] - b_raw[3] * 0.25) < 1e-12,
   "adjusted weekly bars aggregate daily adjusted values, not one factor for the week",
   (b_raw, b_adj))

ref = {A.week_key("2024-03-27"): ("2024-03-27", 10, 15, 8, 9, 600)}
res = A.compare_series(w, ref, contract=False)
ck(res["rows"] == 1 and res["row_ok"] == 1,
   "a product week pairs with the reference week by key", res)
# month pairing uses the key, not the stamp (stamp lives outside the key)
mm = A.compare_series({"k": [1, 2, 0, 1, 5, "2026-10-22"]},
                      {"k": ("2026-09-23", 1, 2, 0, 1, 5)}, contract=False)
ck(mm["row_ok"] == 1, "monthly comparison ignores the display stamp", mm)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
