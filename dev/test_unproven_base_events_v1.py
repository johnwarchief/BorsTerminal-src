# -*- coding: utf-8 -*-
"""Regression: unproven base-price gaps must not enter the adjustment chain.

Reproduces the two measured false events before the filter:
  * شپارس 2020-05-26 — positive base gap (ratio 1.01761), no ledger row, Rahavard
    has no step; the old chain shifted all prior history by +1.76%.
  * اعتماد 2024-04-24 — sub-0.5% fund base gap (ratio 1.001051), no ledger row,
    Rahavard has no step; the old chain shifted prior history by +0.105%.

The filter is only for source=base-price-discontinuity; official ledger rows
(priceAdjust/shareChange) are never dropped.
"""
import io, os, sqlite3, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

tmp = tempfile.mkdtemp(prefix="unproven_")
DB = os.path.join(tmp, "t.db")
con = sqlite3.connect(DB)
con.execute("CREATE TABLE instruments (ins_code TEXT, l_val18 TEXT, l_val30 TEXT, "
            "paper_type INTEGER, sector_name TEXT, updated_at TEXT)")
con.execute("CREATE TABLE boards (ins_code TEXT, board INTEGER)")
con.executemany("INSERT INTO instruments VALUES (?,?,?,?,?,?)", [
    ("100", "شپارس", "پارس", 1, "سيمان", "2026-01-01"),
    ("200", "اعتماد", "اعتماد", 8, "صندوق سرمايه گذاري قابل معامله", "2026-01-01"),
    ("300", "تداوم", "تداوم", 8, "صندوق سرمايه گذاري قابل معامله", "2026-01-01"),
    ("400", "اراد201", "مرابحه عام دولت201-ش.خ", 2, "اوراق", "2026-01-01"),
    ("500", "ضموج637", "اختيارخ فملي-26000-1405/10/09", 8, "صندوق", "2026-01-01"),
    ("600", "وتوسمح", "ح . سرمايه گذاري توسعه ملي", 4, "سرمايه گذاريها", "2026-01-01"),
])
con.commit(); con.close()

import bors_config
bors_config.DB_PATH = DB
import api.chart as CH
CH.DB_PATH = DB

checks, fails = 0, 0


def check(name, cond, detail=""):
    global checks, fails
    checks += 1
    if cond:
        print(f"  OK   {name}")
    else:
        fails += 1
        print(f"  FAIL {name}  {detail}")


def rows_with_gap(ratio, n=25, price=100.0):
    """n daily rows with base==prev close except the last gap (VOL>0)."""
    out = []
    for i in range(n):
        base = price
        if i == n - 1:
            base = round(price * ratio, 6)
        out.append({"time": f"2020-01-{i + 1:02d}", "base": base, "close": price, "vol": 1.0})
    return out


def discovered(symbol, ratio, price=100.0):
    ev, anchored = CH._adjust_events_from_rows(rows_with_gap(ratio, price=price))
    kept, rejected = CH._filter_unproven_base_events(symbol, ev)
    return ev, anchored, kept, rejected


print("[1] discovery reproduces the false events")
ev_pos, anchored_pos, _, rej_pos = discovered("شپارس", 1.01761)
check("stock positive base gap is discovered before filtering",
      anchored_pos and any(abs(float(e["ratio"]) - 1.01761) < 1e-5 for e in ev_pos),
      str(ev_pos))
check("stock positive gap is rejected after filtering",
      len(rej_pos) == 1 and rej_pos[0]["factor_status"] == "unproven-positive-base-gap",
      str(rej_pos))

ev_fund, anchored_fund, _, rej_fund = discovered("اعتماد", 1.001051, price=68000.0)
check("fund micro gap is discovered before filtering",
      anchored_fund and any(abs(float(e["ratio"]) - 1.001051) < 1e-6 for e in ev_fund),
      str(ev_fund))
check("fund positive micro gap is rejected as an unproven positive gap",
      len(rej_fund) == 1 and rej_fund[0]["factor_status"] == "unproven-positive-base-gap",
      str(rej_fund))

print("[2] real actions and real distributions stay")
_, _, kept_stock, rej_stock = discovered("شپارس", 0.985)
check("stock distribution (ratio 0.985) is kept", len(kept_stock) == 1 and not rej_stock,
      str(kept_stock) + str(rej_stock))
_, _, kept_fund, rej_fund2 = discovered("تداوم", 0.985, price=68000.0)
check("fund distribution (ratio 0.985) is kept", len(kept_fund) == 1 and not rej_fund2,
      str(kept_fund) + str(rej_fund2))
_, _, kept_bond, rej_bond = discovered("اراد201", 0.984222, price=980000.0)
check("bond base gap (ratio 0.984222) is rejected by the bond-name rule",
      not kept_bond and len(rej_bond) == 1
      and rej_bond[0]["factor_status"] == "bond-base-gap",
      str(kept_bond) + str(rej_bond))
_, _, kept_option, rej_option = discovered("ضموج637", 0.984222, price=50000.0)
check("option base gap (ratio 0.984222) is rejected by the option-name rule",
      not kept_option and len(rej_option) == 1
      and rej_option[0]["factor_status"] == "option-base-gap",
      str(kept_option) + str(rej_option))
_, _, kept_right, rej_right = discovered("وتوسمح", 0.984222, price=5000.0)
check("right base gap (ratio 0.984222) is rejected by the rights rule",
      not kept_right and len(rej_right) == 1
      and rej_right[0]["factor_status"] == "right-base-gap",
      str(kept_right) + str(rej_right))

print("[3] ledger-corroborated events are never filtered")
official = [
    {"date": "2020-01-25", "ratio": 1.2, "source": "shareChange"},
    {"date": "2020-01-25", "ratio": 1.001, "source": "priceAdjust"},
    {"date": "2020-01-25", "ratio": 1.01761, "source": ""},
]
kept, rejected = CH._filter_unproven_base_events("اعتماد", official)
check("shareChange/priceAdjust kept; empty source treated as unconfirmed base gap",
      len(kept) == 2 and len(rejected) == 1
      and rejected[0]["factor_status"] == "unproven-positive-base-gap",
      str(kept) + str(rejected))

print(f"\n{checks - fails}/{checks} checks passed")
sys.exit(0 if fails == 0 else 1)
