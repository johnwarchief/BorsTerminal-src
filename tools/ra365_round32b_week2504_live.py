#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reference-internal week 2504: reference CSV + optional live capture.

The three keys are assets 8 (شپارس), 803 (تداوم), 804 (اعتماد), week
2017-12-30..2018-01-03.  The frozen reference W bar contradicts the reference's
own type7 D aggregation for that week.  This tool always emits the reference
values and, when --live is supplied, the live Rahavard values and comparison.
Without a live capture the live rows are explicit NOT_RUN_LOGIN_REQUIRED; no
fabricated values are written.

The live capture must be produced by tools/ra365_round32b_week2504_capture.js in
an authenticated Rahavard tab.  It returns bars only; no token/cookie is read,
printed or stored.
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = "D:/BorsTerminal-tmp/ra365_round32b_v3"
DEFAULT_REF = D + "/reference/ref_bars_v2.jsonl"
DEFAULT_COHORT = "D:/BorsTerminal-tmp/ra365_round18/cohort.jsonl"
REF_SHA = "4b1ecb4c1effc4d5770c42521d96a2540a9c9f7b471d7cc710cd034712a8c17c"
AIDS = ("8", "803", "804")
DATES = ("2017-12-30", "2017-12-31", "2018-01-01", "2018-01-02", "2018-01-03")


def tup(b):
    if isinstance(b, dict):
        return (str(b.get("utc"))[:10], b.get("open"), b.get("high"), b.get("low"),
                b.get("close"), b.get("volume"))
    return (str(b[0])[:10], b[1], b[2], b[3], b[4], b[5] if len(b) > 5 else None)


def agg(bars):
    rows = sorted((t for t in bars if t[0] in DATES), key=lambda x: x[0])
    if not rows:
        return None
    return {
        "date_start": rows[0][0], "date_end": rows[-1][0],
        "open": rows[0][1], "high": max(x[2] for x in rows if x[2] is not None),
        "low": min(x[3] for x in rows if x[3] is not None),
        "close": rows[-1][4], "volume": sum(x[5] or 0 for x in rows),
        "n": len(rows),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", default=DEFAULT_REF)
    ap.add_argument("--cohort", default=DEFAULT_COHORT)
    ap.add_argument("--live", default="")
    ap.add_argument("--out", default=D + "/live/reference-internal-live.csv")
    ap.add_argument("--probe", default=D + "/live/live-probe.json")
    ap.add_argument("--summary", default=D + "/live/reference-internal-live-summary.json")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    symbols = {}
    for line in open(a.cohort, encoding="utf-8"):
        d = json.loads(line)
        if str(d.get("ra_asset_id")) in AIDS:
            symbols[str(d["ra_asset_id"])] = d.get("symbol") or ""
    ref = {}
    with open(a.reference, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            aid = str(d.get("asset_id"))
            if aid not in AIDS or d.get("res") not in ("D", "W") or d.get("type") != "type7":
                continue
            bars = {t[0]: t for t in (tup(b) for b in d.get("bars") or []) if t[0]}
            ref.setdefault(aid, {})[d["res"]] = bars
    live = {}
    if a.live:
        try:
            j = json.load(open(a.live, encoding="utf-8"))
            for it in j.get("items") or []:
                aid = str(it.get("asset_id"))
                if aid in AIDS and it.get("type") == "type7":
                    live.setdefault(aid, {})[it.get("res")] = it
        except (OSError, ValueError):
            live = {}
    out = []
    summary = {"reference": a.reference, "reference_sha256": REF_SHA,
               "week": [DATES[0], DATES[-1]], "assets": []}
    for aid in AIDS:
        w = (ref.get(aid, {}).get("W") or {})
        wbar = next((w[d] for d in sorted(w) if "2017-12-28" <= d <= "2018-01-05"), None)
        dbar = list((ref.get(aid, {}).get("D") or {}).values())
        da = agg(dbar)
        rec = {"asset_id": aid, "symbol": symbols.get(aid, ""),
               "ref_w": None, "ref_d_agg": da, "live_status": "NOT_RUN_LOGIN_REQUIRED",
               "live_w": None, "live_d_agg": None,
               "reference_internal_contradiction": False,
               "reference_internal_diff_fields": []}
        if wbar:
            rec["ref_w"] = {"date": wbar[0], "open": wbar[1], "high": wbar[2],
                            "low": wbar[3], "close": wbar[4], "volume": wbar[5]}
            out.append([aid, rec["symbol"], "ref_W", wbar[0], wbar[0], wbar[1], wbar[2],
                        wbar[3], wbar[4], wbar[5], "ref_bars_v2.jsonl", REF_SHA,
                        "REFERENCE_ONLY", "type7 weekly bar"])
        if da:
            out.append([aid, rec["symbol"], "ref_D_agg", da["date_start"], da["date_end"],
                        da["open"], da["high"], da["low"], da["close"], da["volume"],
                        "ref_bars_v2.jsonl", REF_SHA, "REFERENCE_ONLY",
                        "type7 daily aggregate n=%d" % da["n"]])
            for t in sorted(dbar, key=lambda x: x[0]):
                if t[0] in DATES:
                    out.append([aid, rec["symbol"], "ref_D", t[0], t[0], t[1], t[2],
                                t[3], t[4], t[5], "ref_bars_v2.jsonl", REF_SHA,
                                "REFERENCE_ONLY", "type7 daily"])
            diffs = []
            for k in ("open", "high", "low", "close"):
                if (rec["ref_w"].get(k) is not None and da.get(k) is not None
                        and abs(float(rec["ref_w"][k]) - float(da[k])) > 0.5):
                    diffs.append(k)
            rec["reference_internal_diff_fields"] = diffs
            rec["reference_internal_contradiction"] = bool(diffs)
        if aid in live:
            it = live[aid]
            wl = [t for t in (tup(b) for b in it.get("W") or [])
                  if "2017-12-28" <= t[0] <= "2018-01-05"]
            dl = [t for t in (tup(b) for b in it.get("D") or []) if t[0] in DATES]
            rec["live_status"] = "LIVE" if it.get("status") == 200 else "LIVE_STATUS_%s" % it.get("status")
            if wl:
                b = wl[0]
                rec["live_w"] = {"date": b[0], "open": b[1], "high": b[2], "low": b[3],
                                 "close": b[4], "volume": b[5]}
                out.append([aid, rec["symbol"], "live_W", b[0], b[0], b[1], b[2], b[3],
                            b[4], b[5], "rahavard365 /api/v2/chart/bars", "", rec["live_status"],
                            "live type7 weekly"])
            for b in dl:
                out.append([aid, rec["symbol"], "live_D", b[0], b[0], b[1], b[2], b[3],
                            b[4], b[5], "rahavard365 /api/v2/chart/bars", "", rec["live_status"],
                            "live type7 daily"])
            if dl:
                rec["live_d_agg"] = agg(dl)
        else:
            out.append([aid, rec["symbol"], "live_W", DATES[0], DATES[-1], "", "", "", "",
                        "", "rahavard365 /api/v2/chart/bars", "", "NOT_RUN_LOGIN_REQUIRED",
                        "connector token 401; Brave login modal; Edge CDP absent"])
            out.append([aid, rec["symbol"], "live_D", DATES[0], DATES[-1], "", "", "", "",
                        "", "rahavard365 /api/v2/chart/bars", "", "NOT_RUN_LOGIN_REQUIRED",
                        "same blocker; no credentials/tokens used"])
        summary["assets"].append(rec)
    with open(a.out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["asset_id", "symbol", "kind", "date_start", "date_end", "open", "high",
                    "low", "close", "volume", "source", "source_sha256", "status", "note"])
        w.writerows(out)
    probe = {
        "attempted_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "week": [DATES[0], DATES[-1]],
        "connector": {"token_status": 401, "login_panel": True, "has_token": False},
        "brave": {"login_modal": True, "credentials_entered": False, "new_tab_closed": True},
        "edge_cdp": {"port_9333": False, "probe_profile_present": False},
        "decision": "NOT_RUN_LOGIN_REQUIRED",
        "no_credentials_or_tokens_used": True,
        "note": ("The live path needs the owner's authenticated Rahavard session; both drivable "
                 "targets were logged out and no credentials were touched. The reference W/D "
                 "contradiction is still measured offline; live rows are explicit NOT_RUN."),
    }
    json.dump(probe, open(a.probe, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(summary, open(a.summary, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"out": a.out, "probe": a.probe, "summary": a.summary,
                      "assets": summary["assets"]}, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
