#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 15: the DPS ledger row may be applied twice when its source ratio and
the recomputed DPS ratio differ by more than the 2% same-action tolerance.

Identity rule under test: a kept approximate event whose ratio equals the
official pre-event PA ratio (`_source_ratio`) of a DPS row is the same action,
even when the recomputed DPS leg moved >2% because the stock moved on the
ex-date.  The applied ratio stays the DPS leg; only the duplicate is dropped.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import adjustment_engine as AE  # noqa: E402
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


def official(date, ratio, source_ratio, dps=None):
    ev = {"date": date, "ratio": ratio, "source": "tsetmc_price_adjust_by_flow",
          "_dps": True, "_source_ratio": source_ratio,
          "_ledger_key": (date, "priceAdjust")}
    if dps is not None:
        ev["dividend_per_share"] = dps
    return ev


# سخاش 2026-05-23: source 0.82668187, ex-date close 9130 + DPS 1520
# → DPS leg 0.8572769953; reference type7 step is the DPS leg.
merged = C._merge_official_price_adjust(
    [{"date": "2026-05-23", "ratio": 0.82668187, "source": "priceAdjust"}],
    [official("2026-05-23", 0.8572769953, 0.82668187, 1520.0)])
ck(len(merged) == 1 and abs(merged[0]["ratio"] - 0.8572769953) < 1e-12,
   "سخاش: source ratio matches the ledger row, so the DPS leg wins",
   merged)

# فسبزوار 2026-05-23 (event row 2026-04-19, snapped across the halt).
merged = C._merge_official_price_adjust(
    [{"date": "2026-05-23", "ratio": 0.82701603, "source": "priceAdjust"}],
    [official("2026-05-23", 0.8468468468, 0.82701603, 6800.0)])
ck(len(merged) == 1 and abs(merged[0]["ratio"] - 0.8468468468) < 1e-12,
   "فسبزوار: snapped duplicate still identified by the source ratio", merged)

# A discovered base gap carries the same identity; it must be replaced too.
merged = C._merge_official_price_adjust(
    [{"date": "2026-05-23", "ratio": 0.82668187,
      "source": "base-price-discontinuity"}],
    [official("2026-05-23", 0.8572769953, 0.82668187, 1520.0)])
ck(len(merged) == 1 and merged[0]["source"] == "tsetmc_price_adjust_by_flow",
   "base gap with the official source ratio is replaced by the DPS leg", merged)

# Beyond 2% and NOT the ledger's source ratio: still a distinct event.
# The source is priceAdjust (not a base gap), so the Round 7 unconditional
# base-gap rule cannot mask the new identity check.
merged = C._merge_official_price_adjust(
    [{"date": "2026-05-23", "ratio": 0.70, "source": "priceAdjust"}],
    [official("2026-05-23", 0.750923, 0.74)])
ck(len(merged) == 2, "a gap that is not the ledger source ratio stays distinct",
   merged)

# A share change on the same effective date explains the kept ratio: never
# swallow a capital action even if it numerically matches the source ratio.
merged = C._merge_official_price_adjust(
    [{"date": "2026-07-26", "ratio": 0.750923, "source": "priceAdjust"}],
    [official("2026-07-26", 0.987542, 0.750923)],
    share_changes=[("2026-07-26", 0.750923)])
ck(len(merged) == 2,
   "share-change-attributed capital event is not swallowed", merged)

# The 5-day merge window is unchanged.
merged = C._merge_official_price_adjust(
    [{"date": "2026-05-10", "ratio": 0.82668187, "source": "priceAdjust"}],
    [official("2026-05-23", 0.8572769953, 0.82668187)])
ck(len(merged) == 2, "source-ratio identity does not widen the 5-day window",
   merged)

# Without the official source ratio the old 2% rule is the only identity.
merged = C._merge_official_price_adjust(
    [{"date": "2026-05-23", "ratio": 0.82668187, "source": "priceAdjust"}],
    [{"date": "2026-05-23", "ratio": 0.8572769953,
      "source": "tsetmc_price_adjust_by_flow", "_dps": True}])
ck(len(merged) == 2, "no source-ratio evidence ⇒ old behaviour is preserved",
   merged)

# آکو Round 10 regression: old priceAdjust 0.91744287 vs DPS 0.93161024.
merged = C._merge_official_price_adjust(
    [{"date": "2026-09-06", "ratio": 0.91744287, "source": "priceAdjust"}],
    [official("2026-09-06", 0.93161024, 0.91744287, 3244.0)])
ck(len(merged) == 1 and abs(merged[0]["ratio"] - 0.93161024) < 1e-12,
   "آکو: DPS leg still replaces the old priceAdjust ratio", merged)

# Two valid DPS rows with different amounts stay distinct.
merged = C._merge_official_price_adjust(
    [{"date": "2020-01-07", "ratio": 0.9831957547,
      "source": "fund-portal:test", "dividend_per_share": 171.0}],
    [official("2020-01-08", 0.9995003, 0.9831957547, 5.0)])
ck(len(merged) == 2, "different DPS amounts remain distinct", merged)

# Chain/date contract: the event affects only dates strictly before it.
factors, _prov = AE.chain_factors(
    ["2026-05-20", "2026-05-23", "2026-05-24"],
    [{"kind": AE.KIND_SOURCE_RATIO, "date": "2026-05-23",
      "ratio": 0.8572769953}])
ck(abs(factors[0] - 0.8572769953) < 1e-12 and factors[1] == 1.0
   and factors[2] == 1.0,
   "event applies to candles before its effective date only", factors)

# Round 12 regression: reverse/repeated share noise stays filtered.
out = C._filter_share_changes([("2026-04-12", 0.41666667),
                               ("2026-07-08", 2.4),
                               ("2026-07-12", 0.41666667)])
ck([d for d, _r in out] == ["2026-04-12"],
   "Round 12 share filter is intact", out)


# ── Combined action already contained in one observed base gap ──────────────
# بشهاب 2026-07-14: gap 0.634824 = share 0.66666667 × official leg 0.95163241.
merged = C._merge_official_price_adjust(
    [{"date": "2026-07-14", "ratio": 0.634824,
      "source": "base-price-discontinuity"}],
    [{"date": "2026-07-14", "ratio": 0.95163241,
      "source": "tsetmc_price_adjust_by_flow",
      "_source_ratio": 0.95163241}],
    share_changes=[("2026-07-13", 0.66666667)])
ck(len(merged) == 1 and merged[0]["ratio"] == 0.634824,
   "بشهاب: gap already contains share × official leg", merged)

# بمپنا 2025-04-27: gap 0.440061 = share 0.4922293 × official 0.89377845.
merged = C._merge_official_price_adjust(
    [{"date": "2025-04-27", "ratio": 0.440061,
      "source": "base-price-discontinuity"}],
    [{"date": "2025-04-27", "ratio": 0.89377845,
      "source": "tsetmc_price_adjust_by_flow",
      "_source_ratio": 0.89377845}],
    share_changes=[("2025-04-26", 0.4922293)])
ck(len(merged) == 1 and merged[0]["ratio"] == 0.440061,
   "بمپنا: gap already contains share × official leg", merged)

# No share change witness: the official row is a distinct action.
merged = C._merge_official_price_adjust(
    [{"date": "2025-04-27", "ratio": 0.440061,
      "source": "base-price-discontinuity"}],
    [{"date": "2025-04-27", "ratio": 0.89377845,
      "source": "tsetmc_price_adjust_by_flow",
      "_source_ratio": 0.89377845}],
    share_changes=[])
ck(len(merged) == 2, "combined rule requires a share witness", merged)

# The gap must equal share × official leg, not merely be nearby.
merged = C._merge_official_price_adjust(
    [{"date": "2025-04-27", "ratio": 0.50,
      "source": "base-price-discontinuity"}],
    [{"date": "2025-04-27", "ratio": 0.89377845,
      "source": "tsetmc_price_adjust_by_flow",
      "_source_ratio": 0.89377845}],
    share_changes=[("2025-04-26", 0.4922293)])
ck(len(merged) == 2, "gap not equal to share × official leg stays distinct", merged)

# Two official rows claiming one gap are ambiguous: both are kept.
merged = C._merge_official_price_adjust(
    [{"date": "2026-07-14", "ratio": 0.634824,
      "source": "base-price-discontinuity"}],
    [{"date": "2026-07-14", "ratio": 0.95163241,
      "source": "tsetmc_price_adjust_by_flow",
      "_source_ratio": 0.95163241},
     {"date": "2026-07-14", "ratio": 0.95163241,
      "source": "priceAdjust",
      "_source_ratio": 0.95163241}],
    share_changes=[("2026-07-13", 0.66666667)])
ck(len(merged) == 2 and merged[0]["ratio"] == 0.634824,
   "two official claims: gap kept and one official row survives", merged)

# A typed share row is never swallowed by the combined rule.
merged = C._merge_official_price_adjust(
    [{"date": "2026-07-14", "ratio": 0.634824, "source": "shareChange"}],
    [{"date": "2026-07-14", "ratio": 0.95163241,
      "source": "tsetmc_price_adjust_by_flow",
      "_source_ratio": 0.95163241}],
    share_changes=[("2026-07-13", 0.66666667)])
ck(len(merged) == 2, "typed share row is not swallowed", merged)


# ── Evidence-gated gap window: suspension puts the gap 6-9 days after ────────
# حسير 2023-03-11: gap 0.501085, ledger share 0.5 on 2023-03-05 (6 days).
out = C._sharpen_share_gaps(
    [{"date": "2023-03-11", "ratio": 0.501085,
      "source": "base-price-discontinuity"}],
    [], [("2023-03-05", 0.5)], evidence_dates={"2023-03-05"})
ck(abs(out[0]["ratio"] - 0.5) < 1e-12 and out[0]["source"] == "shareChange",
   "evidence-backed 6-day gap is sharpened", out)

# كپرور 2022-04-12: gap 0.316574, ledger share 0.31578947 on 2022-04-04 (8d).
out = C._sharpen_share_gaps(
    [{"date": "2022-04-12", "ratio": 0.316574,
      "source": "base-price-discontinuity"}],
    [], [("2022-04-04", 0.31578947)], evidence_dates={"2022-04-04"})
ck(abs(out[0]["ratio"] - 0.31578947) < 1e-12,
   "evidence-backed 8-day gap is sharpened", out)

# Evidence on a distant date still locks the row.
out = C._sharpen_share_gaps(
    [{"date": "2023-03-11", "ratio": 0.501085,
      "source": "base-price-discontinuity"}],
    [], [("2023-03-05", 0.5)], evidence_dates={"2023-04-20"})
ck(out[0]["ratio"] == 0.501085, "evidence date gate is intact", out)

# A gap outside the 0.5% ratio gate is not a share-only action.
out = C._sharpen_share_gaps(
    [{"date": "2023-03-11", "ratio": 0.60,
      "source": "base-price-discontinuity"}],
    [], [("2023-03-05", 0.5)], evidence_dates={"2023-03-05"})
ck(out[0]["ratio"] == 0.60, "ratio gate is intact", out)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
