#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 24: a shrinking live feed must not promote a fabricated base gap.

Measured case (1405-08-02): the TSETMC CSV for هجرت lost one historical
session (1577→1576 rows) and the jumper was read as a 1.6% base gap on
2023-03-28. The frozen reference has a 2023-03-27 candle and no step there,
and the fabricated event was written into `adjust_events`, shifting the
whole prior history. The guard: when a fetch has fewer bars than the last
healthy one, new unproven base gaps are provisional — they are not applied
and not cached. The verdict/meta writers are also idempotent, so a repeated
GET of unchanged data no longer rewrites the operational DB.
"""
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import api.chart as C  # noqa: E402

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


tmpdir = tempfile.mkdtemp(prefix="ra365_r24_shrink_")
db = os.path.join(tmpdir, "market.db")
sqlite3.connect(db).close()
C.DB_PATH = db
C.CHART_CACHE.clear()

SYM = "هجرت"
CACHED = [
    {"date": "2022-06-11", "ratio": 0.559429, "source": "base-price-discontinuity"},
    {"date": "2023-05-30", "ratio": 0.9081209247, "source": "priceAdjust"},
]
NEW = [
    {"date": "2022-06-11", "ratio": 0.559429, "source": "base-price-discontinuity"},
    {"date": "2023-03-28", "ratio": 0.983897, "source": "base-price-discontinuity"},
    {"date": "2023-05-30", "ratio": 0.9081209247, "source": "priceAdjust"},
    {"date": "2024-05-11", "ratio": 0.8772277228, "source": "priceAdjust"},
]

C._store_adjust_events(SYM, CACHED, "ledger+base-price-discontinuity")
ck(C._feed_shrank(SYM, 1576) is False,
   "an unknown symbol is never treated as shrunk", C._feed_shrank(SYM, 1576))
C._set_adj_cache_meta(SYM, 1577, "2019-08-10")
ck(C._feed_shrank(SYM, 1576) is True, "1576 < 1577 is a shrinking feed")
ck(C._feed_shrank(SYM, 1577) is False, "the same count is not shrinking")

kept, provisional = C._split_provisional_gaps(SYM, NEW)
kept_pairs = [(e["date"], round(float(e["ratio"]), 8)) for e in kept]
ck(kept_pairs == [("2022-06-11", 0.559429),
                  ("2023-05-30", 0.90812092),
                  ("2024-05-11", 0.87722772)], kept_pairs)
ck([(e["date"], e["ratio"]) for e in provisional] == [("2023-03-28", 0.983897)],
   "only the new unproven base gap becomes provisional", provisional)

times = ["2023-03-26", "2023-03-27", "2023-03-28", "2023-03-29"]
_, _, fac_kept, _, _ = C._canonical_adjustment(SYM, times, kept)
_, _, fac_all, _, _ = C._canonical_adjustment(SYM, times, NEW)
ck(abs(fac_kept[1] - fac_kept[2]) < 1e-12,
   "without the fabricated gap there is no step at 2023-03-28",
   (fac_kept[1], fac_kept[2]))
ck(abs(fac_all[1] / fac_kept[1] - 0.983897) < 1e-9,
   "the fabricated gap would have cut every earlier factor by 1.6%",
   fac_all[1] / fac_kept[1])

# Idempotent writers: a repeated GET of unchanged data commits nothing.
watcher = sqlite3.connect(db)
watcher.execute("PRAGMA busy_timeout=30000")
C._store_adjust_events(SYM, NEW, "ledger+base-price-discontinuity")
v1 = watcher.execute("PRAGMA data_version").fetchone()[0]
C._store_adjust_events(SYM, NEW, "ledger+base-price-discontinuity")
v2 = watcher.execute("PRAGMA data_version").fetchone()[0]
ck(v1 == v2, "a repeated identical adjust_events write commits nothing", (v1, v2))

C._set_adj_cache_meta(SYM, 1576, "2019-08-10")
m1 = watcher.execute("PRAGMA data_version").fetchone()[0]
C._set_adj_cache_meta(SYM, 1576, "2019-08-10")
m2 = watcher.execute("PRAGMA data_version").fetchone()[0]
ck(m1 == m2, "a repeated identical cache-meta write commits nothing", (m1, m2))
ck(C._feed_shrank(SYM, 1576) is False,
   "meta advances so the guard cannot stay locked forever")
watcher.close()

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
