# -*- coding: utf-8 -*-
"""dev/market_price_index_card_v1.py — کارتِ «قیمت وزنی ارزشی» = شاخصِ رسمی.

کشفِ ۲۰۲۶-۱۰-۲۰: عددِ ۳٬۰۵۵٫۸۷ در ره‌آورد **تغییرِ** شاخص بود، نه مقدارش؛
مقدار همان ۱٬۳۶۷٬۵۶۳٫۸۳ است که TSETMC در `Index/GetIndexB1LastAll` با
insCode 5798407779416661 می‌دهد. این گارد:
  ۱) کارتِ سوم را از `pi_*` می‌سازد و کارتِ چهارم را میانگینِ ارزشی نگه می‌دارد؛
  ۲) نبودِ pi را `available:false` می‌کند، نه صفر یا میانگینِ جایگزین؛
  ۳) نوشتنِ `save_market_index` را با/بدونِ price می‌سنجد و حفظِ مقدارِ قبلی
     را وقتی قیمتِ رسمی نرسیده ثابت می‌کند.
خالص است؛ شبکه/DB عملیاتی لازم ندارد.
"""
from __future__ import annotations

import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import mstat_engine as E  # noqa: E402
import mstat_panels as P  # noqa: E402
import test_tsetmc as T  # noqa: E402

CHECKS = []
FAILS = []


def ck(label, cond, detail=""):
    CHECKS.append(bool(cond))
    print(("  ok   " if cond else "  FAIL ") + label +
          (("  <- " + str(detail)) if not cond and detail else ""))
    if not cond:
        FAILS.append(label)


HIST = [
    {"d_even": 20261019, "q_tot_cap": 1.0e10, "q_tot_tran": 1.0e6,
     "idx_last": 8_000_000.0, "ew_last": 2_000_000.0, "z_tot_tran": 100},
    {"d_even": 20261020, "q_tot_cap": 2.0e10, "q_tot_tran": 2.0e6,
     "idx_last": 8_272_444.35, "ew_last": 2_251_347.23, "z_tot_tran": 120},
]
MI = {"d_even": 20261020, "last": 8_272_444.35, "change": 18_620.63, "pct": 0.23,
      "ew_last": 2_251_347.23, "ew_change": 28_573.75, "ew_pct": 1.29,
      "pi_last": 1_367_563.83, "pi_change": 3_078.59, "pi_pct": 0.23}


def cards_for(mi):
    old_hist, old_mi, old_total = P._index_history, E.market_index, E.market_total_rials
    try:
        P._index_history = lambda _c, _d: HIST
        E.market_index = lambda _c: mi
        E.market_total_rials = lambda _c: (2.4e16, "test")
        return P.index_cards(None)
    finally:
        P._index_history, E.market_index, E.market_total_rials = old_hist, old_mi, old_total


def card(out, key):
    return next((c for c in out["cards"] if c["key"] == key), None)


def main():
    out = cards_for(MI)
    ck("four cards: official price index and average are separate",
       len(out["cards"]) == 4, len(out["cards"]))
    vw = card(out, "value_weighted_price")
    ck("official card label is «قیمت وزنی ارزشی»", vw["label"] == "قیمت وزنی ارزشی", vw["label"])
    ck("official card value is the TSETMC price index",
       vw["value"] == 1_367_563.83, vw["value"])
    ck("official card change is 3,078.59 (not the value)",
       vw["change"] == 3_078.59, vw["change"])
    ck("official card unit is index, not Rial", vw["unit"] == "واحدِ شاخص", vw["unit"])
    ck("official formula names the official index",
       "GetIndexB1LastAll" in (vw["formula"] or "") or "رسمی" in (vw["formula"] or ""),
       vw["formula"])
    avg = card(out, "avg_traded_price")
    ck("average card is still present", avg is not None)
    ck("average card = q_tot_cap/q_tot_tran",
       avg and avg["value"] == 10_000.0, avg and avg["value"])
    ck("average card unit stays Rial", avg and avg["unit"] == "ریال", avg and avg["unit"])

    none_pi = dict(MI)
    for k in ("pi_last", "pi_change", "pi_pct"):
        none_pi.pop(k)
    out2 = cards_for(none_pi)
    vw2 = card(out2, "value_weighted_price")
    ck("missing official index -> unavailable, not zero",
       vw2 and vw2["available"] is False and vw2["value"] is None, vw2)
    ck("missing official index does not borrow the average",
       card(out2, "avg_traded_price")["value"] == 10_000.0)

    # ── نوشتن: price می‌نشیند و در نبودش مقدارِ همان روز حفظ می‌شود ─────────
    con = sqlite3.connect(":memory:")
    ov = {"indexLastValue": 8_272_444.35, "indexChange": 18_620.63,
          "indexEqualWeightedLastValue": 2_251_347.23,
          "indexEqualWeightedChange": 28_573.75, "marketState": "N"}
    ok = T.save_market_index(con, ov, 20261020, "2026-10-20 19:50:00",
                             price={"last": 1_367_563.83, "change": 3_078.59,
                                    "pct": 0.23})
    row = con.execute("SELECT pi_last, pi_change, pi_pct FROM market_index").fetchone()
    ck("save_market_index writes the official price index", ok and row[0] == 1_367_563.83, row)
    T.save_market_index(con, dict(ov, indexLastValue=8_272_500.0), 20261020,
                        "2026-10-20 19:51:00", price=None)
    row2 = con.execute("SELECT idx_last, pi_last FROM market_index").fetchone()
    ck("a later sync without the price index keeps the prior pi value",
       row2[0] == 8_272_500.0 and row2[1] == 1_367_563.83, row2)
    con.close()

    print("\n%d/%d passed" % (len(CHECKS) - len(FAILS), len(CHECKS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
