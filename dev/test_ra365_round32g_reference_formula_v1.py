#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32G: Rahavard's adjusted-performance formula, locked on live type7.

The reference series is not the exchange's price adjustment.  Measured on the
live type7/type0 bars (2026-10-26 capture) and the R14 fixture:

  cash dividend   back = close_ex / (close_ex + dps)
  rights issue    back = (N_old + N_new*S/P_eff) / (N_old + N_new)
  free shares     back = N_old / N_new
  fund payout     back = par / (par + dps), par = 10,000 rial

`close_ex` and `P_eff` are the event-time close (the price at which the
dividend/right is reinvested), not the pre-event close.  The exchange's
price-adjustment ratio (P-D)/P is a different series and must not be used for
the performance chain.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import adjustment_engine as AE  # noqa: E402

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   <- %s" % (detail,)) if detail else ""))


def factor(ev):
    return AE.event_factor(ev)


def close(got, want, tol, msg):
    ok = got is not None and abs(got - want) <= tol
    ck(ok, msg, "got=%r want=%r diff=%r" % (got, want,
                                            None if got is None else abs(got - want)))


# ── live type7 cases (R14 fixture, captured 2026-10-21) ─────────────────────
# آكو 2026-09-06: dps 3,244; close_ex 44,190; live type7 step 0.931610237382468.
r, s = factor({"kind": AE.KIND_CASH_DIVIDEND, "reference_price": 44190.0,
               "dividend_per_share": 3244.0})
ck(s == AE.OK, "آكو: status ok", s)
close(r, 0.931610237382468, 1e-15, "آكو: close_ex/(close_ex+dps) == live type7")

# The exchange's price formula would give 0.9265897 — reject it explicitly.
close(1.0 - 3244.0 / 44190.0, 0.926589726182394, 1e-15,
      "آكو: price-adjustment value is a different series (control)")

# فروي 2026-08-01: 4.5B -> 9.0B shares, S=1,000, P_eff=2,620; live 0.690839694656488.
r, s = factor({"kind": AE.KIND_CAPITAL_CONTRIBUTION,
               "previous_capital": 4_500_000_000.0,
               "new_capital": 9_000_000_000.0,
               "reference_price": 2620.0, "offer_price": 1000.0})
ck(s == AE.OK, "فروي: status ok", s)
close(r, 0.690839694656488, 1e-15, "فروي: rights formula at the effective close")

# ── fund payouts are priced on par, not on the market close ─────────────────
# هماي 2021-09-25: dps 472, par 10,000 -> exactly 1/1.0472 (live step 1.0472).
r, s = factor({"kind": AE.KIND_CASH_DIVIDEND, "reference_price": 10019.0,
               "dividend_per_share": 472.0, "par_value": 10000.0})
ck(s == AE.OK, "هماي: fund status ok", s)
close(r, 1.0 / 1.0472, 1e-15, "هماي: par/(par+dps) == 1/1.0472")

# Without par_value the same row is priced on the market close and differs.
r2, _ = factor({"kind": AE.KIND_CASH_DIVIDEND, "reference_price": 10019.0,
                "dividend_per_share": 472.0})
ck(abs(r2 - r) > 1e-6, "fund: par and market-close prices are distinguishable",
   (r, r2))

# ── share-only leg ─────────────────────────────────────────────────────────
r, s = factor({"kind": AE.KIND_SPLIT, "old_shares": 200.0, "new_shares": 700.0})
close(r, 200.0 / 700.0, 1e-15, "share: old/new")

# ── combined leg: share x dividend ─────────────────────────────────────────
r_share, _ = factor({"kind": AE.KIND_SPLIT, "old_shares": 200.0, "new_shares": 700.0})
r_div = 10000.0 / (10000.0 + 251.0)
r, _ = AE.chain_factors(
    ["2026-01-01"], [{"kind": AE.KIND_SPLIT, "date": "2026-06-01",
                      "old_shares": 200.0, "new_shares": 700.0},
                     {"kind": AE.KIND_CASH_DIVIDEND, "date": "2026-06-01",
                      "reference_price": 10239.0, "dividend_per_share": 251.0,
                      "par_value": 10000.0}])
close(r[0], r_share * r_div, 1e-15, "combined: share x fund dividend")

# ── guards stay (no fabricated neutral factor) ─────────────────────────────
for ev, want in (
        ({"kind": AE.KIND_CASH_DIVIDEND, "reference_price": 1000.0,
          "dividend_per_share": 1200.0}, "invalid:dividend>=reference_price"),
        ({"kind": AE.KIND_CASH_DIVIDEND, "reference_price": 1000.0,
          "dividend_per_share": 100.0, "par_value": 0.0}, "invalid:par_value<=0"),
        ({"kind": AE.KIND_CASH_DIVIDEND, "reference_price": 1000.0},
         "incomplete:dividend_per_share"),
):
    r, s = factor(ev)
    ck(r is None and s == want, "guard: %s" % want, (r, s))

print("\nresult: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
