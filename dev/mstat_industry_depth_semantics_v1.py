# -*- coding: utf-8 -*-
"""dev/mstat_industry_depth_semantics_v1.py — نبودِ عمق صنعت صفر نیست.

باگِ بازتولیدشده در ممیزیِ 2026-10-20: `industries()` عمقِ هر ردیف را با
`bq_val or 0` جمع می‌کرد؛ صنعتی که هیچ نمادش عمق نداشت، `buy_queue_b_toman=0`
می‌گرفت و در UI «صف صفر» دیده می‌شد، نه «اندازه‌گیری‌نشده». این گارد خالص
است و `enrich` را با ردیف‌های ساختگی جای‌گذاری می‌کند؛ شبکه/DB لازم ندارد.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import mstat_engine as ME  # noqa: E402

CHECKS = []
FAILS = []


def ck(label, cond, detail=""):
    CHECKS.append(bool(cond))
    print(("  ok   " if cond else "  FAIL ") + label + (("  <- " + str(detail)) if not cond and detail else ""))
    if not cond:
        FAILS.append(label)


def row(sector, *, bq=None, sq=None, val=1e9, flow=0.0, pct=1.0):
    return {
        "ins_code": "I-" + sector,
        "cls": ME.PAPER_STOCK,
        "sector_name": sector,
        "pct": pct,
        "_m": {"val": val, "flow": flow, "bq_val": bq, "sq_val": sq},
    }


def main():
    rows = [
        row("بدون-عمق-a"),
        row("بدون-عمق-b"),
        row("با-عمق", bq=1e9, sq=2e9),
        row("ترکیبی-با-عمق", bq=1e9, sq=2e9),
        row("ترکیبی-بدون-عمق"),
    ]
    old = ME.enrich
    try:
        ME.enrich = lambda _conn: (rows, {})
        out = ME.industries(None)
    finally:
        ME.enrich = old
    by = {r["industry"]: r for r in out["rows"]}

    a = by["بدون-عمق-a"]
    ck("no-depth industry: buy queue is null, not 0", a["buy_queue_b_toman"] is None, a["buy_queue_b_toman"])
    ck("no-depth industry: sell queue is null, not 0", a["sell_queue_b_toman"] is None, a["sell_queue_b_toman"])
    ck("no-depth industry: depth_symbols is 0", a["depth_symbols"] == 0, a["depth_symbols"])

    b = by["با-عمق"]
    ck("depth industry: queue is propagated", b["buy_queue_b_toman"] == 0.1 and b["sell_queue_b_toman"] == 0.2,
       (b["buy_queue_b_toman"], b["sell_queue_b_toman"]))
    ck("depth industry: depth_symbols is 1", b["depth_symbols"] == 1, b["depth_symbols"])

    m = by["ترکیبی-با-عمق"]
    ck("mixed industry: only the available depth is summed", m["buy_queue_b_toman"] == 0.1,
       m["buy_queue_b_toman"])
    ck("mixed industry: depth coverage stays explicit", m["depth_symbols"] == 1, m["depth_symbols"])
    ck("negative control: null depth is not coerced to zero", a["buy_queue_b_toman"] != 0,
       a["buy_queue_b_toman"])

    print("\n%d/%d passed" % (len(CHECKS) - len(FAILS), len(CHECKS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
