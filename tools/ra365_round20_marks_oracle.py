# -*- coding: utf-8 -*-
"""Round 20: validate the Rahavard adjustment formulas against its own marks.

Read-only reference audit.  It uses the frozen marks sample, the frozen
type0/type7 bars and the TSETMC official closing.  It does not write a market
DB and does not claim the unverified contribution price.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "artifacts", "ra365", "r20")
MARKS = os.path.join(ROOT, "artifacts", "ra365", "r20", "rahavard-marks-18.json")
MAN = os.path.join(ROOT, "_audit", "RAHAVARD-FULL-UNIVERSE-MANIFEST-v2-2026-10-20.csv")
REF = "D:/BorsTerminal-tmp/ra365_round18/reference.db"


def dps_ratio(close_ex, dps):
    """Rahavard DPS price ratio; exact on the 18-symbol marks sample."""
    close_ex = float(close_ex)
    dps = float(dps)
    if close_ex <= 0 or dps < 0:
        return None
    return close_ex / (close_ex + dps)


def reserve_ratio(pv, nw):
    """Reserve-only capital increase: previous shares / new shares."""
    pv = float(pv); nw = float(nw)
    return pv / nw if pv > 0 and nw > 0 else None


def contribution_ratio(pv, nw, cp, pp, P, par=1000.0):
    """Structural rights/mixed formula; ``par`` alone is not a verified S.

    Returns None when the subscription price cannot be established.  Callers
    must keep this result UNVERIFIED rather than treating par as observed S.
    """
    if P is None:
        return None
    pv = float(pv); nw = float(nw); P = float(P)
    inc = nw - pv
    if pv <= 0 or nw <= 0 or P <= 0 or inc < 0:
        return None
    paid = inc * (float(cp) + float(pp)) / 100.0 * float(par)
    return (pv * P + paid) / (nw * P)


def load_manifest():
    return {r["symbol"]: r for r in csv.DictReader(open(MAN, encoding="utf-8-sig"))}


def bars(con, aid):
    t0 = {r[0]: {"open": r[1], "high": r[2], "low": r[3], "close": r[4]}
          for r in con.execute(
              "SELECT date,open,high,low,close FROM type0 WHERE ra_asset_id=?", (aid,))}
    t7 = {r[0]: {"close": r[1]} for r in con.execute(
        "SELECT date,close FROM type7 WHERE ra_asset_id=?", (aid,))}
    ds = sorted(set(t0) & set(t7))
    fac = [(d, t7[d]["close"] / t0[d]["close"]) for d in ds
           if t0[d]["close"]]
    steps = []
    for i in range(1, len(fac)):
        ratio = fac[i - 1][1] / fac[i][1]
        if abs(ratio - 1.0) > 0.0005:
            steps.append((fac[i][0], ratio))
    return t0, steps


def nearest_step(steps, date_s, window=15):
    d = dt.date.fromisoformat(date_s)
    best = None
    for sd, ratio in steps:
        try:
            diff = abs((dt.date.fromisoformat(sd) - d).days)
        except ValueError:
            continue
        if diff <= window and (best is None or diff < best[0]):
            best = (diff, sd, ratio)
    return best


def main():
    os.makedirs(ART, exist_ok=True)
    marks = json.load(open(MARKS, encoding="utf-8"))
    man = load_manifest()
    con = sqlite3.connect("file:%s?mode=ro" % REF, uri=True)
    rows = []
    summary = {"dps": {"total": 0, "exact": 0, "near": 0, "unmatched": 0, "combined": 0},
               "reserve": {"total": 0, "exact": 0, "near": 0, "unmatched": 0, "combined": 0},
               "contribution": {"total": 0, "exact": 0, "near": 0,
                                 "unverified": 0, "unmatched": 0}}
    for sym, obj in marks.items():
        m = man.get(sym)
        if not m:
            continue
        aid = str(m["ra_asset_id"])
        ins = str(m["ins_code"])
        t0, steps = bars(con, aid)
        tdates = sorted(t0)
        tsc = {r[0]: r[1] for r in con.execute(
            "SELECT date,close FROM tsetmc WHERE ins_code=?", (ins,)) if r[1]}
        cc_dates = [x.get("d") for x in obj.get("cc") or [] if x.get("d")]
        dps_dates = [x.get("d") for x in obj.get("dps") or [] if x.get("d")]

        def near_date(d, dates, window=10):
            try:
                dd = dt.date.fromisoformat(d)
            except ValueError:
                return False
            for other in dates:
                try:
                    if abs((dt.date.fromisoformat(other) - dd).days) <= window:
                        return True
                except ValueError:
                    pass
            return False

        for ev in obj.get("dps") or []:
            hit = nearest_step(steps, ev["d"])
            if not hit:
                summary["dps"]["unmatched"] += 1
                continue
            sd, ref_ratio = hit[1], hit[2]
            close_ex = tsc.get(sd)
            if close_ex is None:
                close_ex = t0.get(sd, {}).get("close")
            calc = dps_ratio(close_ex, ev["dps"]) if close_ex else None
            err = abs(calc / ref_ratio - 1.0) if calc else None
            summary["dps"]["total"] += 1
            combined = near_date(ev["d"], cc_dates)
            if combined:
                summary["dps"]["combined"] += 1
            elif err is not None and err <= 1e-6:
                summary["dps"]["exact"] += 1
            elif err is not None and err <= 0.01:
                summary["dps"]["near"] += 1
            rows.append({"symbol": sym, "kind": "dps", "event": ev["d"],
                         "step": sd, "dps": ev["dps"], "close_ex": close_ex,
                         "reference_ratio": ref_ratio, "formula_ratio": calc,
                         "abs_error": err,
                         "status": "COMBINED_WITH_CC" if combined else
                         ("EXACT" if err is not None and err <= 1e-6
                          else "NEAR" if err is not None and err <= 0.01
                          else "MISMATCH")})
        for ev in obj.get("cc") or []:
            hit = nearest_step(steps, ev["d"])
            if not hit:
                summary["reserve" if not (ev.get("cp") or ev.get("pp")) else
                        "contribution"]["unmatched"] += 1
            pv = float(ev["pv"]); nw = float(ev["nw"])
            if not hit:
                rows.append({"symbol": sym, "kind": "cc", "event": ev["d"],
                             "step": None, "reference_ratio": None,
                             "formula_ratio": None, "abs_error": None,
                             "status": "NO_NEAR_STEP"})
                continue
            sd, ref_ratio = hit[1], hit[2]
            share = pv / nw
            is_reserve = not (ev.get("cp") or ev.get("pp"))
            if is_reserve:
                calc = reserve_ratio(pv, nw)
                err = abs(calc / ref_ratio - 1.0)
                combined = near_date(ev["d"], dps_dates)
                summary["reserve"]["total"] += 1
                if combined:
                    summary["reserve"]["combined"] += 1
                elif err <= 1e-6:
                    summary["reserve"]["exact"] += 1
                elif err <= 0.01:
                    summary["reserve"]["near"] += 1
                status = ("COMBINED_WITH_DPS" if combined else
                          "EXACT" if err <= 1e-6 else "NEAR" if err <= 0.01 else "MISMATCH")
            else:
                # S is not published in marks; use par only to expose the gap.
                prev = [x for x in tdates if x < ev["d"]]
                P = t0[prev[-1]]["close"] if prev else None
                cp = float(ev.get("cp") or 0.0)
                pp = float(ev.get("pp") or 0.0)
                inc = nw - pv
                calc = (pv * P + inc * (cp + pp) / 100.0 * 1000.0) / (nw * P) \
                    if P else None
                err = abs(calc / ref_ratio - 1.0) if calc else None
                summary["contribution"]["total"] += 1
                if err is not None and err <= 1e-6:
                    summary["contribution"]["exact"] += 1
                elif err is not None and err <= 0.01:
                    summary["contribution"]["near"] += 1
                else:
                    summary["contribution"]["unverified"] += 1
                status = ("UNVERIFIED" if err is None or err > 1e-6
                          else "EXACT")
            rows.append({"symbol": sym, "kind": "cc", "event": ev["d"],
                         "step": sd, "cp": ev.get("cp"), "pp": ev.get("pp"),
                         "rp": ev.get("rp"), "reference_ratio": ref_ratio,
                         "formula_ratio": calc, "abs_error": err,
                         "status": status})
    con.close()
    with open(os.path.join(ART, "marks-oracle.csv"), "w",
              encoding="utf-8-sig", newline="") as f:
        fields = ["symbol", "kind", "event", "step", "cp", "pp", "rp", "dps",
                  "close_ex", "reference_ratio", "formula_ratio", "abs_error", "status"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    out = {"source": MARKS, "symbols": len(marks), "rows": len(rows),
           "summary": summary,
           "note": "Contribution events need the subscription price S; marks only expose percentages. "
                   "They are not promoted to a verified formula."}
    json.dump(out, open(os.path.join(ART, "marks-oracle.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
