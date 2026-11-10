#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage D: independent Open audit — reference type0 open vs DB open, by src.

Only facts are reported: equality, substitution pattern (open == previous
close), and per-row candidate corrections where the reference proves the DB
value wrong. No value is written to any DB here.
"""
import argparse
import collections
import csv
import gzip
import json
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "_audit", "phase49-finalization", "db", "restored-work.db")
EVID = os.path.join(ROOT, "_audit", "phase49-finalization", "evidence")


def skeleton(s):
    return str(s).translate(str.maketrans({"ي": "ی", "ك": "ک", "ى": "ی"}))


def load_ref(path):
    raw = collections.defaultdict(dict)
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if str(r.get("resolution")) != "D":
                continue
            typ = str(r.get("type"))
            if typ in ("type0", "raw"):
                raw[r["symbol"]][str(r["date"])] = r
    return raw


def db_rows(symbol):
    con = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
    names = {r[0] for r in con.execute("SELECT DISTINCT symbol FROM price_history")}
    real = symbol if symbol in names else None
    if real is None:
        cand = [n for n in names if skeleton(n) == skeleton(symbol)]
        real = cand[0] if len(cand) == 1 else None
    if real is None:
        con.close()
        return {}
    rows = con.execute(
        "SELECT date,open,high,low,close,volume,last,src FROM price_history "
        "WHERE symbol=? ORDER BY date", (real,)).fetchall()
    con.close()
    out, prev = {}, None
    for r in rows:
        out[str(r[0])] = {"open": r[1], "high": r[2], "low": r[3], "close": r[4],
                          "volume": r[5], "last": r[6], "src": r[7],
                          "prev_close": prev}
        prev = r[4]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--symbols", default="", help="optional CSV of symbols")
    args = ap.parse_args()
    ref = load_ref(os.path.join(args.ref, "bars.ndjson.gz"))
    only = [r["symbol"] for r in csv.DictReader(open(args.symbols, encoding="utf-8-sig"))] \
        if args.symbols else sorted(ref)
    out, corrections = {}, []
    for sym in only:
        db = db_rows(sym)
        by_src = collections.defaultdict(lambda: collections.Counter())
        first = {}
        for d, r in sorted(ref.get(sym, {}).items()):
            if d not in db:
                by_src["__missing__"]["ref_only"] += 1
                continue
            dv = db[d]
            ro, do = r.get("open"), dv.get("open")
            if ro is None or do is None:
                by_src[dv.get("src") or "?"]["null"] += 1
                continue
            src = dv.get("src") or "?"
            c = by_src[src]
            c["n"] += 1
            eq = abs(float(ro) - float(do)) <= 1.0
            if eq:
                c["ref_eq_db_open"] += 1
            else:
                c["ref_ne_db_open"] += 1
                if dv.get("prev_close") is not None and \
                        abs(float(do) - float(dv["prev_close"])) <= 1.0:
                    c["db_open_eq_prev_close"] += 1
                    c["provable_substitution"] += 1
                    corrections.append({
                        "symbol": sym, "date": d, "field": "open",
                        "db_value": do, "reference_value": ro,
                        "db_prev_close": dv["prev_close"], "src": src,
                        "reason": "db open equals previous close; reference type0 differs"})
                else:
                    c["other_difference"] += 1
            if not first:
                first = {"date": d, "ref_open": ro, "db_open": do, "src": src,
                         "eq": eq}
        out[sym] = {"per_src": {k: dict(v) for k, v in by_src.items()},
                    "first_row": first}
    os.makedirs(EVID, exist_ok=True)
    with open(os.path.join(EVID, "open-audit-%s.json" % args.label), "w",
              encoding="utf-8") as fh:
        json.dump({"ref": args.ref, "per_symbol": out,
                   "corrections": corrections}, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, "_audit", "phase49-finalization",
                           "open-corrections-%s.csv" % args.label), "w",
              encoding="utf-8", newline="") as fh:
        if corrections:
            w = csv.DictWriter(fh, fieldnames=list(corrections[0]))
            w.writeheader()
            w.writerows(corrections)
    total = sum(v.get("provable_substitution", 0)
                for s in out.values() for v in s["per_src"].values())
    print(json.dumps({"label": args.label, "symbols": len(only),
                      "provable_open_corrections": total,
                      "corrections": len(corrections)},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
