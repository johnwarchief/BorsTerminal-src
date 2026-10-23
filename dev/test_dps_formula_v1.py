#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DPS / capital-change factor formula (Round 7).

Proven on the reference: for a cash dividend, the factor price-ratio is
`close_ex / (close_ex + dps)` where close_ex is the CLOSING price (پایانی) on
the ex-date and dps the cash dividend per share. For a reserve-based capital
increase the ratio is `previous_capital / new_capital`.

The numbers below are the measured reference steps and the TSETMC CSV closes.
"""
import os
import sys

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


# (symbol, ex-date, close(پایانی), dps, reference price-ratio)
DPS_CASES = [
    ("درازي", "2024-03-13", 17190.0, 1020.0, 0.94398682),
    ("درازي", "2025-03-25", 17730.0, 900.0, 0.95169082),
    ("درازي", "2026-05-23", 11190.0, 1400.0, 0.88880064),
    ("سهرمز", "2026-02-22", 16950.0, 10000.0, 0.62894249),
    ("غانيزان", "2026-07-22", 6460.0, 1300.0, 0.83247423),
    ("كربن", "2026-06-21", 5850.0, 3480.0, 0.62700965),
    ("حبندر", "2026-07-08", 6990.0, 2930.0, 0.70463710),
    ("سشمال", "2026-05-20", 11140.0, 4745.0, 0.70129053),
    ("سهرمز", "2024-02-04", 24660.0, 3790.0, 0.86678383),
    ("سهرمز", "2025-02-04", 59510.0, 7650.0, 0.88609291),
    ("كربن", "2025-06-29", 13150.0, 1480.0, 0.89883800),
    ("حشكوه", "2023-07-29", 8250.0, 16.0, 0.99806436),
    ("كنور", "2023-06-18", 22240.0, 1800.0, 0.92512479),
    ("ثنام", "2023-07-19", 2246.0, 10.0, 0.99556738),
    ("شسپا", "2026-07-26", 15550.0, 2000.0, 0.88604),
    ("كلر", "2026-07-18", 9830.0, 1087.0, 0.900431),
]
for sym, d, cl, dps, ref in DPS_CASES:
    got = cl / (cl + dps)
    ck(abs(got / ref - 1) < 1e-6,
       "DPS %s %s: close=%.0f dps=%.0f -> %.8f == ref %.8f" % (sym, d, cl, dps, got, ref),
       "diff=%.2e" % (got / ref - 1))

# Round 8 regression fixtures: the five pre-2024 steps in the seven symbols
# that the product still treats as base-price gaps. DPS amounts are identified
# by Rahavard timescale_marks (reference evidence, not yet official ingest);
# they are here to lock the reference formula, not to claim provenance.
MARKS_DPS_CASES = [
    ("حخزر", "2023-07-08", 54000.0, 6300.0, 0.8955223880597015),
    ("سپاها", "2022-11-21", 8780.0, 1770.0, 0.832227),
    ("كلوند", "2021-07-07", 20350.0, 1870.0, 0.915842),
    ("پخش", "2023-05-23", 26000.0, 1200.0, 0.955882),
    ("وبشهر", "2026-07-13", 4640.0, 480.0, 0.90625),
]
for sym, d, cl, dps, ref in MARKS_DPS_CASES:
    got = cl / (cl + dps)
    ck(abs(got / ref - 1) < 1e-6,
       "marks-DPS %s %s: close=%.0f dps=%.0f -> %.8f == ref %.8f" % (sym, d, cl, dps, got, ref),
       "diff=%.2e" % (got / ref - 1))

# Reserve-based capital increase: ratio = previous_capital / new_capital.
CC_CASES = [
    ("ثنام", 2367650648000.0, 3311362648000.0, 0.71500796),
    ("حشكوه", 1726640000000.0, 2000000000000.0, 0.86332000),
    ("ولانا", 100000000000.0, 300000000000.0, 0.33333333),
]
for sym, pv, nw, ref in CC_CASES:
    got = pv / nw
    ck(abs(got / ref - 1) < 1e-6,
       "CC %s: pv/nw = %.8f == ref %.8f" % (sym, got, ref), "diff=%.2e" % (got / ref - 1))

# An official DPS row supersedes a discovered gap at the same action...
rejected = []
merged = C._merge_official_price_adjust(
    [{"date": "2026-02-21", "ratio": 0.62895, "source": "base-price-discontinuity"}],
    [{"date": "2026-02-22", "ratio": 0.62894249, "source": "tsetmc_price_adjust_by_flow",
      "_dps": True, "_ledger_key": ("2026-02-17", "priceAdjust")}],
    rejected=rejected)
ck(len(merged) == 1 and merged[0]["source"] == "tsetmc_price_adjust_by_flow",
   "DPS official row replaces the matching overlapping base-price gap", merged)

# Same-day duplicate: the distance is 0, which must still count as "near"
# (regression for `_day_diff(...) or 999` treating 0 as unknown).
merged = C._merge_official_price_adjust(
    [{"date": "2026-02-22", "ratio": 0.62895, "source": "base-price-discontinuity"}],
    [{"date": "2026-02-22", "ratio": 0.62894249, "source": "tsetmc_price_adjust_by_flow",
      "_dps": True, "_ledger_key": ("2026-02-17", "priceAdjust")}])
ck(len(merged) == 1, "same-day DPS duplicate is dropped", merged)

# Two official rows for the same action (دانيك 2026-08-24) must collapse.
merged = C._merge_official_price_adjust(
    [],
    [{"date": "2026-08-24", "ratio": 0.87873402, "source": "priceAdjust"},
     {"date": "2026-08-24", "ratio": 0.8818436126,
      "source": "tsetmc_price_adjust_by_flow"}])
ck(len(merged) == 1, "two official rows within 1% are one action", merged)

# The same DPS may carry two base-price ratios 1.44% apart (شسپا 2026:
# 0.873257 from the old row vs 0.886040 from the ex-date closing).
merged = C._merge_official_price_adjust(
    [],
    [{"date": "2026-07-26", "ratio": 0.87325729, "source": "priceAdjust"},
     {"date": "2026-07-26", "ratio": 0.886039886,
      "source": "tsetmc_price_adjust_by_flow"}])
ck(len(merged) == 1, "two official rows 1.44% apart are one action", merged)

# A 24% capital event on the same day is distinct and must survive.
merged = C._merge_official_price_adjust(
    [],
    [{"date": "2026-07-26", "ratio": 0.750923, "source": "base-price-discontinuity"},
     {"date": "2026-07-26", "ratio": 0.987542, "source": "tsetmc_price_adjust_by_flow"}])
ck(len(merged) == 2, "same-day rows 24% apart are distinct actions", merged)

# A base gap that equals DPS*CC already contains the DPS: the separate DPS
# must be suppressed (حخزر 2026-07-26: gap 0.827433, DPS 0.983225, CC 0.84).
merged = C._merge_official_price_adjust(
    [{"date": "2026-07-26", "ratio": 0.827433, "source": "base-price-discontinuity"}],
    [{"date": "2026-07-26", "ratio": 0.9832253778, "source": "tsetmc_price_adjust_by_flow",
      "_dps": True, "_ledger_key": ("2026-07-18", "priceAdjust")}],
    share_changes=[("2026-07-26", 0.84)])
ck(len(merged) == 1 and merged[0]["source"] == "base-price-discontinuity",
   "combined gap suppresses the DPS it already contains", merged)

# CC-only gap (بورس 2026-07-26) keeps both.
merged = C._merge_official_price_adjust(
    [{"date": "2026-07-26", "ratio": 0.750923, "source": "base-price-discontinuity"}],
    [{"date": "2026-07-26", "ratio": 0.987542, "source": "tsetmc_price_adjust_by_flow",
      "_dps": True, "_ledger_key": ("2026-07-22", "priceAdjust")}],
    share_changes=[("2026-07-26", 0.75)])
ck(len(merged) == 2, "CC-only gap keeps the separate DPS", merged)

# Two valid DPS-like rows with different amounts are distinct, even if their
# price ratios are within 2% (fund DPS 171 vs priceAdjust DPS 5).
merged = C._merge_official_price_adjust(
    [{"date": "2020-01-07", "ratio": 0.9831957547, "source": "fund-portal:test",
      "dividend_per_share": 171.0}],
    [{"date": "2020-01-08", "ratio": 0.9995003, "source": "test",
      "dividend_per_share": 5.0}])
ck(len(merged) == 2, "different DPS amounts in one window are distinct", merged)

# Matching amounts and a 0.11% ratio gap are the same action.
merged = C._merge_official_price_adjust(
    [{"date": "2024-12-23", "ratio": 0.896926, "source": "fund-portal:test",
      "dividend_per_share": 18540.0}],
    [{"date": "2024-12-24", "ratio": 0.895907, "source": "test",
      "dividend_per_share": 18540.0}])
ck(len(merged) == 1, "same amount and ratio within 2% is one action", merged)

# An official capital/combined row must replace an approximate base gap,
# not lose to it (the official ratio is the source of truth).
merged = C._merge_official_price_adjust(
    [{"date": "2026-07-26", "ratio": 0.7500, "source": "base-price-discontinuity"}],
    [{"date": "2026-07-26", "ratio": 0.750923,
      "source": "tsetmc_price_adjust_by_flow"}])
ck(len(merged) == 1 and merged[0]["source"] == "tsetmc_price_adjust_by_flow",
   "official row replaces an approximate base gap", merged)

# A gap more than 2% away is a distinct action.
merged = C._merge_official_price_adjust(
    [{"date": "2026-07-26", "ratio": 0.70, "source": "base-price-discontinuity"}],
    [{"date": "2026-07-26", "ratio": 0.750923,
      "source": "tsetmc_price_adjust_by_flow"}])
ck(len(merged) == 2, "base gap more than 2% away stays distinct", merged)

# A newly computed official DPS must replace an old priceAdjust ratio for the
# same action (آكو 2026-09-06: 0.91744 old vs 0.93161 closing formula).
merged = C._merge_official_price_adjust(
    [{"date": "2026-09-06", "ratio": 0.91744287, "source": "priceAdjust"}],
    [{"date": "2026-09-06", "ratio": 0.93161024,
      "source": "tsetmc_price_adjust_by_flow",
      "_dps": True, "dividend_per_share": 3244.0}])
ck(len(merged) == 1 and merged[0]["ratio"] == 0.93161024,
   "official DPS replaces the old priceAdjust ratio", merged)

# ...but a base gap with a materially different ratio is a distinct action when
# an official share change explains it (بورس 2026-07-22: DPS=55 + CC 24T→32T).
merged = C._merge_official_price_adjust(
    [{"date": "2026-07-26", "ratio": 0.750923, "source": "base-price-discontinuity"}],
    [{"date": "2026-07-26", "ratio": 0.987542, "source": "tsetmc_price_adjust_by_flow",
      "_dps": True, "_ledger_key": ("2026-07-22", "priceAdjust")}],
    share_changes=[("2026-07-26", 0.75)])
ck(len(merged) == 2, "nearby DPS keeps a share-change-attributed capital event", merged)

# ...and an unattributable gap in the same window stays dropped (Round 7 rule).
merged = C._merge_official_price_adjust(
    [{"date": "2026-07-26", "ratio": 0.750923, "source": "base-price-discontinuity"}],
    [{"date": "2026-07-26", "ratio": 0.987542, "source": "tsetmc_price_adjust_by_flow",
      "_dps": True, "_ledger_key": ("2026-07-22", "priceAdjust")}],
    share_changes=[])
ck(len(merged) == 1, "unattributable same-window base gap is treated as duplicate", merged)

# ...and a non-DPS official row does NOT drop a distant discovered gap.
merged = C._merge_official_price_adjust(
    [{"date": "2026-02-21", "ratio": 0.907613, "source": "base-price-discontinuity"}],
    [{"date": "2026-02-22", "ratio": 0.62894249, "source": "shareChange"}])
ck(len(merged) == 2, "non-DPS official row keeps a distinct discovered event", merged)

# Distinct ledger rows are still kept.
merged = C._merge_official_price_adjust(
    [{"date": "2025-01-10", "ratio": 0.95, "source": "shareChange",
      "_ledger_key": ("2025-01-09", "shareChange")}],
    [{"date": "2025-03-10", "ratio": 0.90, "source": "tsetmc_price_adjust_by_flow",
      "_ledger_key": ("2025-03-09", "priceAdjust")}])
ck(len(merged) == 2, "distinct ledger rows are both kept", merged)

# Event dates snap to the first effective candle (suspension duplicate guard).
ck(C._effective_event_dates([{"date": "2023-06-24"}],
   ["2023-06-19", "2023-07-08"])[0]["date"] == "2023-07-08",
   "event date snaps across a suspension", C._effective_event_dates(
       [{"date": "2023-06-24"}], ["2023-06-19", "2023-07-08"]))
ck(C._effective_event_dates([{"date": "2026-07-26"}],
   ["2026-07-26", "2026-07-27"])[0]["date"] == "2026-07-26",
   "trading-day event stays on its own date", None)
ck(C._effective_event_dates([{"date": "2027-01-01"}],
   ["2026-12-30"])[0]["date"] == "2027-01-01",
   "event after the last candle is not moved backwards", None)

# Official PA typing: a share-linked row is capital/combined and keeps the
# official PA ratio; a DPS-only row uses the proven closing formula.
r, is_dps, et = C._classify_pa_event(0.7509, 55.0, 4360.0, "2026-07-26",
                                    [("2026-07-26", 0.75)])
ck(r == 0.7509 and not is_dps and et == "capital",
   "share-linked PA row stays capital", (r, is_dps, et))
r, is_dps, et = C._classify_pa_event(0.7406, 55.0, 4360.0, "2026-07-26",
                                    [("2026-07-26", 0.75)])
ck(r == 0.7406 and not is_dps and et == "combined",
   "share x DPS explains the PA ratio as combined", (r, is_dps, et))
r, is_dps, et = C._classify_pa_event(0.99, 55.0, 4360.0, "2026-07-26",
                                    [("2026-07-26", 0.80)])
ck(is_dps and et == "dps", "separate share change leaves the PA row a DPS",
   (r, is_dps, et))
r, is_dps, et = C._classify_pa_event(0.9875, 55.0, 4360.0, "2026-07-26", [])
ck(abs(r - 4360.0 / (4360.0 + 55.0)) < 1e-9 and is_dps and et == "dps",
   "PA row without share stays a DPS event", (r, is_dps, et))
r, is_dps, et = C._classify_pa_event(0.99, None, None, "2026-07-26", [])
ck(r == 0.99 and not is_dps and et == "unverified",
   "PA row without DPS/share is unverified", (r, is_dps, et))
r, is_dps, et = C._classify_pa_event(0.9995, 5.0, None, "2020-01-08", [])
ck(r == 0.9995 and is_dps and et == "dps-unverified",
   "DPS without closing keeps its type and amount", (r, is_dps, et))

# Share-change noise: reverse rows (>1) and a repeated identical ratio
# within 180 days must not become a second capital event.
out = C._filter_share_changes([("2026-04-12", 0.41666667),
                               ("2026-07-08", 2.4),
                               ("2026-07-12", 0.41666667)])
ck([d for d, _r in out] == ["2026-04-12"],
   "reverse/repeated share rows are filtered", out)
out = C._filter_share_changes([("2025-01-01", 0.5),
                               ("2026-08-01", 0.5)])
ck(len(out) == 2, "identical ratio far apart is a distinct event", out)
out = C._filter_share_changes([("2026-01-01", 1.2)])
ck(len(out) == 1 and out[0][1] == 1.2,
   "single ratio>1 without an inverse is kept", out)
out = C._filter_share_changes([("2026-01-01", 0.8), ("2026-03-01", 0.8)])
ck(len(out) == 2, "repeated ratio without a reverse row is independent", out)
out = C._filter_share_changes([("2026-01-01", 0.8), ("2026-02-01", 1.25)])
ck(len(out) == 1 and out[0][1] == 0.8,
   "reverse pair drops only the >1 side", out)

# Share-only capital increase: an approximate base gap is replaced by the
# official share ratio only when both describe the same action (<=0.5% apart)
# and no official priceAdjust row already covers it.
EV = [{"date": "2021-01-10", "ratio": 0.102885,
       "source": "base-price-discontinuity"}]
out = C._sharpen_share_gaps([dict(e) for e in EV], [],
                            [("2021-01-10", 0.10301418)],
                            evidence_dates={"2021-01-10"})
ck(out[0]["ratio"] == 0.10301418 and out[0]["source"] == "shareChange",
   "reserve share ratio sharpens the same-action gap", out)
out = C._sharpen_share_gaps([dict(e) for e in EV], [],
                            [("2021-01-10", 0.10301418)])
ck(out[0]["ratio"] == 0.102885 and out[0]["source"] == "base-price-discontinuity",
   "no official no-cash evidence leaves the gap untouched", out)
out = C._sharpen_share_gaps([dict(e) for e in EV], [],
                            [("2021-01-10", 0.10301418)],
                            evidence_dates={"2020-12-01"})
ck(out[0]["ratio"] == 0.102885,
   "evidence on another date does not unlock this share row", out)
out = C._sharpen_share_gaps([dict(e) for e in EV],
                            [{"date": "2021-01-11", "ratio": 0.10301418}],
                            [("2021-01-10", 0.10301418)],
                            evidence_dates={"2021-01-10"})
ck(out[0]["ratio"] == 0.102885 and out[0]["source"] == "base-price-discontinuity",
   "official PA row keeps the gap untouched", out)
PAID = [{"date": "2020-08-09", "ratio": 0.761534,
         "source": "base-price-discontinuity"}]
out = C._sharpen_share_gaps([dict(e) for e in PAID], [],
                            [("2020-08-05", 0.75)],
                            evidence_dates={"2020-08-05"})
ck(out[0]["ratio"] == 0.761534,
   "paid-in gap (value effect above tolerance) is not sharpened", out)
out = C._sharpen_share_gaps([dict(e) for e in EV], [],
                            [("2021-01-25", 0.10301418)],
                            evidence_dates={"2021-01-25"})
ck(out[0]["ratio"] == 0.102885,
   "share row outside the 5-day window is not used", out)
TWO = [{"date": "2021-01-10", "ratio": 0.102885,
        "source": "base-price-discontinuity"},
       {"date": "2021-01-11", "ratio": 0.1030,
        "source": "base-price-discontinuity"}]
out = C._sharpen_share_gaps([dict(e) for e in TWO], [],
                            [("2021-01-10", 0.10301418)],
                            evidence_dates={"2021-01-10"})
ck(all(e["source"] == "base-price-discontinuity" for e in out),
   "two gaps claiming one share row stay untouched", out)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)