# -*- coding: utf-8 -*-
"""Classify every reference-only parity step (Round 4, P0-C)."""
import argparse
import collections
import csv
import datetime as dt
import json
import os
import sqlite3


def _d(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", required=True)
    ap.add_argument("--product", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    prod = {}
    for line in open(a.product, encoding="utf-8"):
        try:
            j = json.loads(line)
        except Exception:
            continue
        dates = sorted(str(c.get("time"))[:10] for c in (j.get("candles") or []))
        ev = {str(e.get("date"))[:10] for e in (j.get("adjustEvents") or [])}
        rej = {str(e.get("date"))[:10] for e in (j.get("adjustRejected") or [])}
        prod[j["symbol"]] = {"dates": set(dates), "first": dates[0] if dates else "",
                             "last": dates[-1] if dates else "", "events": ev,
                             "rejected": rej, "source": j.get("adjustSource")}

    con = sqlite3.connect("file:" + a.db + "?mode=ro", uri=True)
    rows = []
    for r in csv.DictReader(open(a.steps, encoding="utf-8-sig")):
        if r.get("kind") != "REF_ONLY":
            continue
        sym = r["symbol"]
        d = r["ref_date"]
        rec = prod.get(sym)
        out = {"symbol": sym, "asset_id": r["asset_id"], "ref_date": d,
               "ref_ratio": r["ref_ratio"], "product_source": (rec or {}).get("source", "")}
        if not rec:
            out["status"] = "NO_PRODUCT_SERIES"
            out["next_action"] = "mapping/product pull"
            rows.append(out)
            continue
        if not rec["first"] or d < rec["first"]:
            out["status"] = "BEFORE_PRODUCT_HISTORY"
            out["next_action"] = "extend history from an official source"
        elif d > rec["last"]:
            out["status"] = "AFTER_PRODUCT_HISTORY"
            out["next_action"] = "fresh pull"
        elif d not in rec["dates"]:
            out["status"] = "MISSING_PRODUCT_CANDLE"
            out["next_action"] = "check official daily row / no-trade contract"
        else:
            ins = con.execute(
                "SELECT ins_code FROM instruments WHERE l_val18=? "
                "ORDER BY updated_at DESC LIMIT 1", (sym,)).fetchone()
            ins = str(ins[0]) if ins else ""
            day = _d(d)
            lo = int((day - dt.timedelta(days=5)).strftime("%Y%m%d"))
            hi = int((day + dt.timedelta(days=5)).strftime("%Y%m%d"))
            n_pa = n_sc = n_fund = 0
            if ins:
                n_pa = con.execute(
                    "SELECT COUNT(*) FROM price_adjust_events WHERE ins_code=? AND d_even BETWEEN ? AND ?",
                    (ins, lo, hi)).fetchone()[0]
                n_sc = con.execute(
                    "SELECT COUNT(*) FROM share_change_events WHERE ins_code=? AND d_even BETWEEN ? AND ?",
                    (ins, lo, hi)).fetchone()[0]
                try:
                    n_fund = con.execute(
                        "SELECT COUNT(*) FROM fund_profit_events WHERE ins_code=? AND d_even BETWEEN ? AND ?",
                        (ins, lo, hi)).fetchone()[0]
                except Exception:
                    n_fund = 0
            out.update({"ins_code": ins, "ledger_pa": n_pa, "ledger_sc": n_sc,
                        "fund_events": n_fund})
            if n_fund:
                out["status"] = "FUND_EVENT_NOT_APPLIED"
                out["next_action"] = "inspect merge/filter of fund event"
            elif n_pa or n_sc:
                out["status"] = "OFFICIAL_ROW_NOT_APPLIED"
                out["next_action"] = "inspect sharpening/date matching"
            elif any(abs((_d(x) - day).days) <= 5 for x in rec["rejected"] if _d(x)):
                out["status"] = "FILTERED_BY_PRODUCT"
                out["next_action"] = "verify filter evidence"
            else:
                out["status"] = "NO_KNOWN_SOURCE_EVENT"
                out["next_action"] = "reference contract review"
        rows.append(out)
    con.close()
    fields = sorted({k for r in rows for k in r})
    with open(a.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader(); w.writerows(rows)
    print("rows", len(rows))
    print(collections.Counter(r["status"] for r in rows))


if __name__ == "__main__":
    main()
