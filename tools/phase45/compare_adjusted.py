#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""compare_adjusted.py — S6: adjusted (type7) parity against Rahavard.

Two independent measurements per symbol:
  1. factor parity — local canonical factor f(d) vs the reference's own
     type7/type0 ratio on the same day (this is the adjustment engine).
  2. adjusted-bar parity — local scaled OHLC (raw x f, rounded to rial the way
     the chart renders it) vs the reference's fractional type7 OHLC, with a
     half-rial rounding tolerance.

Volume convention: the reference type7 bar keeps the raw volume, the local
scaled series divides by the factor; the script measures both relations
instead of assuming one.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def week_key(date_str: str) -> str:
    d = dt.date.fromisoformat(date_str[:10])
    return (d - dt.timedelta(days=(d.weekday() + 2) % 7)).isoformat()


def month_key(date_str: str) -> str:
    import wm_calendar as WMC
    d = dt.date.fromisoformat(date_str[:10])
    jy, jm, _ = WMC.g2j(d.year, d.month, d.day)
    return f"{jy:04d}-{jm:02d}"


def agg(rows, keyf, close_key):
    out = {}
    for c in rows:
        d = str(c["time"])[:10]
        k = keyf(d)
        b = out.get(k)
        if b is None:
            b = {"open": c["open"], "high": c["high"], "low": c["low"],
                 "close": c.get(close_key), "volume": 0.0}
            out[k] = b
        b["high"] = max(b["high"], c["high"])
        b["low"] = min(b["low"], c["low"])
        b["close"] = c.get(close_key)
        b["volume"] += c.get("volume") or 0
    return out


def close_within(a, b, tol=0.5):
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-dir", required=True)
    ap.add_argument("--symbols", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--md", default="")
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="p45-adj-")
    for name in ("market.db", "user.db"):
        p = os.path.join(args.db_dir, name)
        if os.path.exists(p):
            shutil.copyfile(p, os.path.join(tmp, name))
    os.environ["BORS_DATA_DIR"] = tmp
    os.environ["BORS_CHART_CDN"] = "off"
    os.environ["BORS_NO_FETCH_LOOPS"] = "1"
    os.environ.setdefault("BORS_CODAL_OFFLINE", "1")
    os.environ.setdefault("BORS_CODAL_AUTO", "0")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    import api.chart as ch

    with open(args.symbols, encoding="utf-8-sig") as fh:
        symbols = [r["symbol"] for r in csv.DictReader(fh)]
    ref = {}
    with gzip.open(args.ref, "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            ref.setdefault((r["symbol"], r["adjust"], r["resolution"]), []).append(r)
    out = {"symbols": {}, "tolerances": {"ohlc_rial": 0.5, "factor_rel": 1e-6}}
    for sym in symbols:
        body = ch.get_chart_db(sym)
        cands = [c for c in (body.get("candles") or []) if not c.get("live_forming")]
        scaled = [c for c in ch._fts_scaled(cands, body.get("factors") or [],
                                            body.get("volumes") or [])
                  if not c.get("live_forming")]
        fac = {str(f["time"])[:10]: float(f["factor"]) for f in (body.get("factors") or [])}
        rawD = {x["date"]: x for x in ref.get((sym, "raw", "D"), [])}
        adjD = {x["date"]: x for x in ref.get((sym, "adjusted", "D"), [])}
        sD = {str(c["time"])[:10]: c for c in scaled}
        common = sorted(set(rawD) & set(adjD) & set(sD))
        so = {"common": len(common), "factor_mismatch": 0, "factor_max_rel": 0.0,
              "ohlc_ok": 0, "ohlc_mismatch": 0, "close_ok": 0, "close_mismatch": 0,
              "vol_scaled_equals_raw": 0, "vol_scaled_equals_ref": 0,
              "vol_other": 0, "examples": [], "resolutions": {}}
        for d in common:
            fr = (float(adjD[d]["close"]) / float(rawD[d]["close"])
                  if rawD[d].get("close") else None)
            fb = fac.get(d)
            if fr and fb:
                rel = abs(fb / fr - 1.0)
                if rel > 1e-6:
                    so["factor_mismatch"] += 1
                    so["factor_max_rel"] = max(so["factor_max_rel"], rel)
            s = sD[d]
            ok = all(close_within(s[f], adjD[d][f]) for f in ("open", "high", "low"))
            if ok:
                so["ohlc_ok"] += 1
            else:
                so["ohlc_mismatch"] += 1
                if len(so["examples"]) < 6:
                    so["examples"].append({"date": d, "bors": {f: s[f] for f in
                        ("open", "high", "low")}, "ref": {f: adjD[d][f] for f in
                        ("open", "high", "low")}})
            cl = s.get("last") if s.get("last") is not None else s.get("closing")
            if close_within(cl, adjD[d]["close"]):
                so["close_ok"] += 1
            else:
                so["close_mismatch"] += 1
            k = fac.get(d, 1.0) or 1.0
            if abs(float(s["volume"]) * k - float(rawD[d]["volume"])) <= 0.5:
                so["vol_scaled_equals_raw"] += 1
            elif abs(float(s["volume"]) - float(adjD[d]["volume"])) <= 0.5:
                so["vol_scaled_equals_ref"] += 1
            else:
                so["vol_other"] += 1
        # W/M: local aggregation of the scaled series vs reference adjusted bars
        refAdjByRes = {res: {x["date"]: x for x in ref.get((sym, "adjusted", res), [])}
                       for res in ("W", "M")}
        for res, keyf, close_key in (("W", week_key, "last"), ("M", month_key, "last")):
            rb = {keyf(x["date"]): x for x in ref.get((sym, "adjusted", res), [])}
            lb = agg(scaled, keyf, close_key)
            keys = sorted(set(rb) & set(lb), key=str)
            st = {"common": len(keys), "ohlc_ok": 0, "ohlc_mismatch": 0,
                  "close_ok": 0, "close_mismatch": 0, "examples": []}
            for k in keys:
                a, b = lb[k], rb[k]
                ok = all(close_within(a[f], b[f]) for f in ("open", "high", "low"))
                if ok:
                    st["ohlc_ok"] += 1
                else:
                    st["ohlc_mismatch"] += 1
                    if len(st["examples"]) < 4:
                        st["examples"].append({"key": str(k),
                                               "bors": {f: a[f] for f in ("open", "high", "low")},
                                               "ref": {f: b[f] for f in ("open", "high", "low")}})
                cl = a.get("close") if a.get("close") is not None else a.get("closing")
                if close_within(cl, b["close"]):
                    st["close_ok"] += 1
                else:
                    st["close_mismatch"] += 1
            so["resolutions"][res] = st
        out["symbols"][sym] = so
        print(sym, "common", so["common"], "facBad", so["factor_mismatch"],
              f"maxrel {so['factor_max_rel']:.2e}", "ohlcOk", so["ohlc_ok"],
              "closeOk", so["close_ok"], "vol=raw", so["vol_scaled_equals_raw"],
              "vol=ref", so["vol_scaled_equals_ref"],
              {r: (v["common"], v["ohlc_ok"], v["close_ok"])
               for r, v in so["resolutions"].items()}, flush=True)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    if args.md:
        lines = ["| نماد | D مشترک | ضریب بد | بیشینهٔ اختلاف | OHLC در گردکردن | "
                 "close در گردکردن | حجم=خام | W OHLC | M OHLC |",
                 "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for sym, so in out["symbols"].items():
            w = so["resolutions"].get("W", {})
            m = so["resolutions"].get("M", {})
            lines.append(f"| {sym} | {so['common']} | {so['factor_mismatch']} | "
                         f"{so['factor_max_rel']:.2e} | {so['ohlc_ok']} | "
                         f"{so['close_ok']} | {so['vol_scaled_equals_raw']} | "
                         f"{w.get('ohlc_ok',0)}/{w.get('common',0)} | "
                         f"{m.get('ohlc_ok',0)}/{m.get('common',0)} |")
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    print("written", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
