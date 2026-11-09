#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""compare_raw.py — S4: raw candle parity D/W/M for the 30-symbol mission set.

Bors side: the canonical local-db daily series (same candles /api/chart-db
serves), read from a throwaway copy of the lab DB.
Rahavard side: the normalized type0 (raw) capture.

Join rules (verified against the reference on 2026-11-09):
  * D — exact date.
  * W — Saturday-anchored week key (the reference stamps the week's Saturday).
  * M — Jalali month key (the reference stamps the first day of the Jalali month).
Close basis: the reference `type0` close is the last trade price, so it is
compared with the local `last` column; where that column is NULL the local
`closing` is compared too and the row is labelled, never silently dropped.

Output: JSON + a compact Markdown summary. No network, no writes to the lab DB.
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
    delta = (d.weekday() + 2) % 7  # Saturday anchor
    return (d - dt.timedelta(days=delta)).isoformat()


def month_key(date_str: str):
    import wm_calendar as WMC
    d = dt.date.fromisoformat(date_str[:10])
    jy, jm, _ = WMC.g2j(d.year, d.month, d.day)
    return f"{jy:04d}-{jm:02d}"


def load_ref(path: str, adjust: str = "raw"):
    ref = {}
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("adjust") != adjust:
                continue
            ref.setdefault((r["symbol"], r["resolution"]), []).append(r)
    for rows in ref.values():
        rows.sort(key=lambda x: x["date"])
    return ref


def aggregate(daily, keyf):
    buckets = {}
    for c in daily:
        d = str(c["time"])[:10]
        k = keyf(d)
        b = buckets.get(k)
        if b is None:
            b = {"open": c["open"], "high": c["high"], "low": c["low"],
                 "close": c.get("last"), "closing": c.get("closing") or c.get("close"),
                 "volume": 0.0, "first": d, "last_date": d}
            buckets[k] = b
        b["high"] = max(b["high"], c["high"])
        b["low"] = min(b["low"], c["low"])
        b["close"] = c.get("last")
        b["closing"] = c.get("closing") or c.get("close")
        b["volume"] += c.get("volume") or 0
        b["last_date"] = d
    return buckets


def cmp_num(a, b):
    if a is None or b is None:
        return None
    a, b = float(a), float(b)
    return {"abs": abs(a - b), "rel": (abs(a - b) / abs(b)) if b else None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-dir", required=True)
    ap.add_argument("--symbols", required=True, help="CSV with symbol column")
    ap.add_argument("--ref", required=True, help="normalized bars.ndjson.gz")
    ap.add_argument("--out", required=True)
    ap.add_argument("--md", default="")
    ap.add_argument("--adjust", default="raw", choices=("raw", "adjusted"))
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="p45-raw-")
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
    ref = load_ref(args.ref, args.adjust)
    out = {"symbols": {}, "adjust": args.adjust,
           "rules": {"D": "exact date", "W": "saturday week key",
                     "M": "jalali month key",
                     "close": "reference close = last trade price (raw/adjusted)"}}
    for sym in symbols:
        body = ch.get_chart_db(sym)
        cands = [c for c in (body.get("candles") or []) if not c.get("live_forming")]
        if args.adjust == "adjusted":
            daily = [c for c in ch._fts_scaled(cands, body.get("factors") or [],
                                               body.get("volumes") or [])
                     if not c.get("live_forming")]
        else:
            daily = cands
        sym_out = {"bars_bors": len(daily), "status": body.get("status")}
        if daily:
            sym_out["bors_range"] = [daily[0]["time"], daily[-1]["time"]]
        sym_out["resolutions"] = {}
        bors_D = {str(c["time"])[:10]: c for c in daily}
        for res, keyf in (("D", None), ("W", week_key), ("M", month_key)):
            rows = ref.get((sym, res), [])
            if rows:
                if "ref_range" not in sym_out:
                    sym_out["ref_range"] = [rows[0]["date"], rows[-1]["date"]]
                else:
                    sym_out["ref_range"][0] = min(sym_out["ref_range"][0], rows[0]["date"])
                    sym_out["ref_range"][1] = max(sym_out["ref_range"][1], rows[-1]["date"])
            if res == "D":
                b = bors_D
                r = {x["date"]: x for x in rows}
            else:
                b = aggregate(daily, keyf)
                r = {keyf(x["date"]): x for x in rows}
            common = sorted(set(b) & set(r), key=str)
            stats = {"bors": len(b), "ref": len(r), "common": len(common),
                     "only_bors": len(set(b) - set(r)), "only_ref": len(set(r) - set(b)),
                     "open_match": 0, "open_mismatch": 0,
                     "high_match": 0, "high_mismatch": 0,
                     "low_match": 0, "low_mismatch": 0, "low_auction": 0,
                     "close_by_last": 0, "close_by_closing": 0, "close_other": 0,
                     "last_missing": 0, "volume_match": 0, "volume_mismatch": 0,
                     "examples": []}
            for k in common:
                bb, rr = b[k], r[k]
                anchor = bb if res == "D" else bors_D.get(bb["last_date"], {})
                if anchor.get("last") is None:
                    stats["last_missing"] += 1
                bad = []
                for f, match_key, mix_key in (("open", "open_match", "open_mismatch"),
                                              ("high", "high_match", "high_mismatch")):
                    if float(bb[f]) == float(rr[f]):
                        stats[match_key] += 1
                    else:
                        stats[mix_key] += 1
                        bad.append((f, bb[f], rr[f]))
                bclose = bb.get("last") if res == "D" else bb.get("close")
                closing = float(bb.get("closing") or 0)
                if float(bb["low"]) == float(rr["low"]):
                    stats["low_match"] += 1
                else:
                    stats["low_mismatch"] += 1
                    if bclose is not None and float(bb["low"]) == float(bclose):
                        stats["low_auction"] += 1
                    bad.append(("low", bb["low"], rr["low"]))
                if bclose is not None and float(bclose) == float(rr["close"]):
                    stats["close_by_last"] += 1
                elif closing == float(rr["close"]):
                    stats["close_by_closing"] += 1
                else:
                    stats["close_other"] += 1
                    bad.append(("close", bclose if bclose is not None else bb.get("closing"),
                                rr["close"]))
                if float(bb["volume"]) == float(rr["volume"]):
                    stats["volume_match"] += 1
                else:
                    stats["volume_mismatch"] += 1
                    bad.append(("volume", bb["volume"], rr["volume"]))
                if bad and len(stats["examples"]) < 8:
                    stats["examples"].append({
                        "key": str(k), "bors_date": bb.get("first", k),
                        "ref_date": rr["date"], "diffs": [
                            {"field": f, "bors": bv, "ref": rv,
                             **({"diff": cmp_num(bv, rv)} if cmp_num(bv, rv) else {})}
                            for f, bv, rv in bad]})
            sym_out["resolutions"][res] = stats
        out["symbols"][sym] = sym_out
        print(sym, sym_out.get("bars_bors"), {res: (s["common"], s["open_mismatch"],
              s["high_mismatch"], s["low_mismatch"], s["low_auction"],
              s["close_by_last"], s["close_by_closing"], s["close_other"],
              s["volume_mismatch"]) for res, s in sym_out["resolutions"].items()},
              flush=True)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    if args.md:
        lines = ["| نماد | D مشترک | open بد | high بد | low بد | low=حراج | "
                 "close=last | close=closing | close دیگر | حجم بد | "
                 "W مشترک | W low بد | M مشترک | M low بد |",
                 "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | "
                 "--- | --- | --- | --- |"]
        for sym, so in out["symbols"].items():
            d = so["resolutions"].get("D", {})
            w = so["resolutions"].get("W", {})
            m = so["resolutions"].get("M", {})
            lines.append(f"| {sym} | {d.get('common',0)} | {d.get('open_mismatch',0)} | "
                         f"{d.get('high_mismatch',0)} | {d.get('low_mismatch',0)} | "
                         f"{d.get('low_auction',0)} | {d.get('close_by_last',0)} | "
                         f"{d.get('close_by_closing',0)} | {d.get('close_other',0)} | "
                         f"{d.get('volume_mismatch',0)} | {w.get('common',0)} | "
                         f"{w.get('low_mismatch',0)} | {m.get('common',0)} | "
                         f"{m.get('low_mismatch',0)} |")
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    print("written", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
