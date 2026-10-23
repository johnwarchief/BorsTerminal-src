# -*- coding: utf-8 -*-
"""Classify every ETF distribution step against the official fund portal records.

Match key = (canonical asset, Jalali profit month), because the portal records the
monthly profit date and the reference step is the session after it.  The output is
the Gate-A inventory: no step is dropped, each has a status and its evidence.
"""
import argparse
import collections
import csv
import datetime as dt
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from ra_parity import g2j  # noqa: E402


def _ym(date_str):
    d = dt.date.fromisoformat(str(date_str)[:10])
    jy, jm, _ = g2j(d.year, d.month, d.day)
    return f"{jy}/{jm:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", required=True)
    ap.add_argument("--canonical", required=True)
    ap.add_argument("--sources", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    src = json.load(open(a.sources, encoding="utf-8"))
    portal_assets = {str(f.get("asset_id")) for f in src.get("funds", []) if f.get("endpoint")}
    no_dist_assets = {str(f.get("asset_id")) for f in src.get("funds", []) if f.get("no_distributions")}
    zero_months = {(str(f.get("asset_id")), m)
                   for f in src.get("funds", []) for m in (f.get("zero_profit_months") or [])}
    ins_by_asset = collections.defaultdict(set)
    for r in csv.DictReader(open(a.canonical, encoding="utf-8-sig")):
        if r.get("ra_asset_id"):
            ins_by_asset[str(r["ra_asset_id"])].add(str(r["ins_code"]))

    con = sqlite3.connect("file:" + a.db + "?mode=ro", uri=True)
    official = {}
    official_by_asset = {}
    for asset, ins_codes in ins_by_asset.items():
        for ins in ins_codes:
            try:
                rows = con.execute(
                    "SELECT d_even, profit_date, unit_profit, ratio, source, source_id"
                    " FROM fund_profit_events WHERE ins_code=?", (ins,)).fetchall()
            except Exception:
                rows = []
            for d, pdate, unit, ratio, source, sid in rows:
                key = (asset, str(pdate).rsplit("/", 1)[0])
                rec = {"d_even": d, "profit_date": pdate, "unit_profit": unit,
                       "ratio": ratio, "source": source, "source_id": sid, "ins_code": ins}
                official.setdefault(key, []).append(rec)
                official_by_asset.setdefault(asset, []).append(rec)
    con.close()

    steps = list(csv.DictReader(open(a.steps, encoding="utf-8-sig")))
    out = []
    for r in steps:
        asset = str(r["asset_id"])
        ym = _ym(r["date"])
        rec = dict(r, profit_month=ym)
        # اول تطبیقِ نزدیکیِ تاریخِ اثر (month-end records often land on the next
        # month's first session), بعد تطبیقِ ماهِ سود.
        step_d = int(str(r["date"]).replace("-", ""))
        near = [h for h in official_by_asset.get(asset, [])
                if abs(int(h["d_even"]) - step_d) <= 7]
        hits = near if near else official.get((asset, ym), [])
        # یک ردیف به ازای هر (profit_date, amount)؛ variant‌ها تکرار می‌شوند.
        uniq = {(h["profit_date"], h["unit_profit"]): h for h in hits}
        rec["official_events"] = len(uniq)
        if len(uniq) == 1:
            h = next(iter(uniq.values()))
            rec.update(official_profit_date=h["profit_date"],
                       official_unit_profit=h["unit_profit"],
                       official_ratio=h["ratio"], official_source=h["source"],
                       official_source_id=h["source_id"])
            try:
                ref = float(r["ref_ratio"])
                rec["official_ratio_diff_pct"] = round((ref - float(h["ratio"])) / float(h["ratio"]) * 100, 6)
            except Exception:
                rec["official_ratio_diff_pct"] = ""
            diff = abs(float(rec.get("official_ratio_diff_pct") or 0))
            rec["status"] = ("RESOLVED_OFFICIAL_SOURCE" if diff <= 2.0
                             else "REFERENCE_CONTRACT_UNCLEAR")
        elif len(uniq) > 1:
            rec["status"] = "DUPLICATE_OR_INVALID_EVENT"
        elif (asset, ym) in zero_months:
            rec["status"] = "REFERENCE_CONTRACT_UNCLEAR:OFFICIAL_ZERO_DISTRIBUTION"
        elif asset in no_dist_assets:
            rec["status"] = "SOURCE_GAP_CONFIRMED:NO_DISTRIBUTION_POLICY"
        elif asset in portal_assets:
            rec["status"] = "SOURCE_GAP_CONFIRMED:NO_OFFICIAL_EVENT_FOR_MONTH"
        else:
            rec["status"] = "SOURCE_GAP_CONFIRMED:NO_PORTAL_ENTRY"
        out.append(rec)

    fields = sorted({k for r in out for k in r})
    with open(a.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(out)
    print(collections.Counter(r["status"] for r in out))
    print("assets", len({r["asset_id"] for r in out}))


if __name__ == "__main__":
    main()
