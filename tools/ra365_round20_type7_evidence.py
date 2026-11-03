# -*- coding: utf-8 -*-
"""Round 20: freeze the event-level evidence behind the type7 residual.

For each named event, report the product event ratio, the official TSETMC
ledger ratio (p_closing / p_closing_not_adjusted), the reference-implied
price ratio from type7/type0, and the Rahavard marks DPS when present.
Read-only; no production data is changed.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
OUT = os.path.join(ROOT, "artifacts", "ra365", "r20-fix")
TEHRAN = timezone(timedelta(hours=3, minutes=30))
CASES = [
    ("هجرت", "2024-05-08"),
    ("سغرب", "2026-05-31"),
    ("لخزر", "2026-07-27"),
    ("ومعادن", "2025-02-15"),
    ("ولانا", "2026-08-02"),
]


def td(b):
    s = str(b["utc"]).replace("Z", "+00:00")
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(TEHRAN).date().isoformat()


def dparse(s):
    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="_audit/ra365_ref_bars.json")
    ap.add_argument("--product", default="_audit/ra365_product_bars.json")
    ap.add_argument("--db", default="C:/Users/Johnkallnaya/Desktop/Borsterminal/BorsTerminal-src/market.db")
    args = ap.parse_args()
    R = json.load(open(args.ref, encoding="utf-8"))
    P = json.load(open(args.product, encoding="utf-8"))
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    out = []
    for sym, event_date in CASES:
        row = {"symbol": sym, "event_date": event_date}
        live = P[sym]["live"]
        evs = live.get("adjustEvents") or []
        near = min(evs, key=lambda e: abs((dparse(e["date"]) - dparse(event_date)).days)) if evs else None
        if near:
            row["product_event_date"] = str(near["date"])[:10]
            row["product_ratio"] = float(near["ratio"])
            row["product_days_from_case"] = abs((dparse(near["date"]) - dparse(event_date)).days)
        pa = con.execute(
            "SELECT d_even,p_closing,p_closing_not_adjusted,ratio,source FROM price_adjust_events "
            "WHERE symbol=? ORDER BY ABS(d_even-?) LIMIT 1",
            (sym, int(event_date.replace("-", "")))).fetchone()
        if pa:
            pa_date = str(pa[0])
            pa_iso = f"{pa_date[:4]}-{pa_date[4:6]}-{pa_date[6:]}"
            row["ledger_nearest_date"] = pa_iso
            if abs((dparse(pa_iso) - dparse(event_date)).days) <= 20:
                row["ledger_date"] = pa_iso
                row["ledger_p_closing"] = pa[1]
                row["ledger_p_closing_not_adjusted"] = pa[2]
                row["ledger_ratio"] = pa[3]
                row["ledger_source"] = pa[4]
            else:
                row["ledger_note"] = "nearest price_adjust row is outside the 20-day event window"
        sc = con.execute(
            "SELECT d_even,shares_old,shares_new,ratio,source FROM share_change_events "
            "WHERE symbol=? ORDER BY ABS(d_even-?) LIMIT 1",
            (sym, int(event_date.replace("-", "")))).fetchone()
        if sc:
            sc_date = str(sc[0])
            sc_iso = f"{sc_date[:4]}-{sc_date[4:6]}-{sc_date[6:]}"
            row["share_nearest_date"] = sc_iso
            if abs((dparse(sc_iso) - dparse(event_date)).days) <= 20:
                row["share_date"] = sc_iso
                row["share_old"] = sc[1]
                row["share_new"] = sc[2]
                row["share_ratio"] = sc[3]
        t0 = R["bars"].get(f"{sym}|type0|D") or {}
        t7 = R["bars"].get(f"{sym}|type7|D") or {}
        c0 = {td(b): b["c"] for b in (t0.get("bars") or []) if b.get("c")}
        c7 = {td(b): b["c"] for b in (t7.get("bars") or []) if b.get("c")}
        common = sorted(set(c0) & set(c7))
        before = [d for d in common if d < event_date]
        after = [d for d in common if d >= event_date]
        if before and after:
            b, a = before[-1], after[0]
            fb = c7[b] / c0[b]
            fa = c7[a] / c0[a]
            step = fa / fb if fb else None
            row.update({"ref_before_date": b, "ref_after_date": a,
                        "ref_factor_before": fb, "ref_factor_after": fa,
                        "ref_step": step,
                        "ref_implied_price_ratio": (1.0 / step) if step else None})
        marks = (R.get("meta") or {}).get("marks|" + sym) or {}
        data = (marks.get("json") or {}).get("data") or []
        dps = []
        for it in data:
            if it.get("type_id") == 3:
                d = str(it.get("date_time"))[:10]
                if abs((dparse(d) - dparse(event_date)).days) <= 20:
                    dps.append({"date": d, "dps": (it.get("dps") or {}).get("pure_dps")})
        row["marks_dps_near"] = dps
        out.append(row)
    con.close()
    json.dump(out, open(os.path.join(OUT, "type7-event-evidence.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for row in out:
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
