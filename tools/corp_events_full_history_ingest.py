#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ingest the full TSETMC corporate-action history into an isolated DB.

Round 15's collector used GetPriceAdjustByFlow/1/500 (5-year cap) and
GetInstrumentShareChangeByFlow/1/14 (14-day window).  The source accepts
much larger windows: /1/20000 returns rows back to 2008 and the share
endpoint returns the full history.  This tool reads cached API responses
(or fetches one page per flow) and writes them into a DB copy.

Never point --db at the operational DB.  Existing tables not named below
are untouched; INSERT OR REPLACE is idempotent by (ins_code, d_even).
"""
import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
import time
import urllib.request

UA = "BorsTerminal-R16-research/1.0"
PA_FLOW_URL = "https://cdn.tsetmc.com/api/ClosingPrice/GetPriceAdjustByFlow/%d/20000"
SH_FLOW_URL = ("https://cdn.tsetmc.com/api/Instrument/"
               "GetInstrumentShareChangeByFlow/%d/20000")
CACHE = "D:/BorsTerminal-tmp/ra365_round16"
PA_CACHE = ["price_adjust_20000.json", "price_adjust_flow2.json"]
SH_CACHE = ["share_5000.json", "share_flow2.json"]


def fetch(url, path):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    with open(path, "wb") as fh:
        fh.write(body)
    return json.loads(body)


def load_cache(names, kind):
    rows = []
    for name in names:
        path = os.path.join(CACHE, name)
        if not os.path.exists(path):
            print("missing cache:", path)
            continue
        j = json.load(open(path, encoding="utf-8"))
        rows.extend(j.get(kind) or [])
    return rows


def parse_pa(rows, now):
    out = {}
    for r in rows:
        inst = r.get("instrument") or {}
        ins = str(inst.get("insCode") or r.get("insCode") or "")
        try:
            d = int(r["dEven"])
            pc = float(r["pClosing"])
            pn = float(r["pClosingNotAdjusted"])
        except (KeyError, TypeError, ValueError):
            continue
        if not ins or not pc or not pn:
            continue
        out[(ins, d)] = (ins, d, inst.get("lVal18AFC") or r.get("lVal18AFC"),
                         pc, pn, r.get("corporateTypeCode"),
                         round(pc / pn, 8), "tsetmc_price_adjust_by_flow", now)
    return list(out.values())


def parse_sh(rows, now):
    out = {}
    for r in rows:
        ins = str(r.get("insCode") or "")
        try:
            d = int(r["dEven"])
            old = float(r["numberOfShareOld"])
            new = float(r["numberOfShareNew"])
        except (KeyError, TypeError, ValueError):
            continue
        if not ins or not old or not new:
            continue
        out[(ins, d)] = (ins, d, r.get("lVal18AFC"), old, new,
                         round(old / new, 8),
                         "tsetmc_share_change_by_flow", now)
    return list(out.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--fetch", action="store_true",
                    help="fetch missing pages (2 PA + 2 SH) before ingesting")
    ap.add_argument("--stay", type=float, default=4.0)
    a = ap.parse_args()
    if "rahavard-full-universe" in a.db.replace("\\", "/"):
        print("REFUSED: operational DB path")
        return 2
    os.makedirs(CACHE, exist_ok=True)
    if a.fetch:
        for flow in (1, 2):
            fetch(PA_FLOW_URL % flow, os.path.join(CACHE, PA_CACHE[flow - 1]))
            time.sleep(a.stay)
        for flow in (1, 2):
            fetch(SH_FLOW_URL % flow, os.path.join(CACHE, SH_CACHE[flow - 1]))
            time.sleep(a.stay)
    pa = parse_pa(load_cache(PA_CACHE, "priceAdjust"),
                  dt.datetime.now().isoformat(timespec="seconds"))
    sh = parse_sh(load_cache(SH_CACHE, "instrumentShareChange"),
                  dt.datetime.now().isoformat(timespec="seconds"))
    print("parsed PA", len(pa), "SH", len(sh))
    con = sqlite3.connect(a.db)
    try:
        con.executemany(
            "INSERT OR REPLACE INTO price_adjust_events VALUES (?,?,?,?,?,?,?,?,?)",
            pa)
        con.executemany(
            "INSERT OR REPLACE INTO share_change_events VALUES (?,?,?,?,?,?,?,?)",
            sh)
        con.commit()
        for t in ("price_adjust_events", "share_change_events"):
            n, lo, hi = con.execute(
                "SELECT COUNT(*), MIN(d_even), MAX(d_even) FROM " + t).fetchone()
            print(t, n, lo, hi)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
