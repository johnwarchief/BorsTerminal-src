#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32D: reference-calendar W/M bars for the non-comparable keys.

Round 32B measured weekly/monthly parity on keys whose product daily date set
equals the reference daily date set.  2,858 W and 2,777 M keys failed that
test because one side had extra or missing days; they were excluded from the
100% claim.  This tool builds the missing side of the comparison from a fresh
Rahavard daily capture:

  * for every non-comparable key, aggregate the reference's own daily type7
    bars with the same week/month key and OHLCV rule used by the Round 32B
    audit (Saturday week, Jalali month);
  * emit one reference W/M bar per key, with its source, capture hash, the
    number of sessions and the date span;
  * keys with no reference daily bar are marked unavailable, never estimated.

The output is a small correction pack (5,635 bars), not a raw daily series:
the raw capture stays on D: and only this derived pack is referenced by the
measurement.  The bars are the reference's answer for dates the product
cannot build from its own incomplete calendar.

Usage:
  python tools/ra365_round32d_calendar.py \
      --captures D:/BorsTerminal-tmp/ra365_round32/calendar/captures \
      --noncomp artifacts/ra365/r32b/measure/noncomparable_wm.csv \
      --out D:/BorsTerminal-tmp/ra365_round32/calendar/pack \
      [--generated-at 2026-10-25T00:00:00+00:00]
"""
import argparse
import csv
import gzip
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ra365_round32b_audit import aggregate, month_key, week_key  # noqa: E402

SCHEMA = "ra365-wm-calendar-bar/1"
KEYFN = {"W": week_key, "M": month_key}


def _f(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _date(x):
    return str(x or "")[:10]


def load_captures(directory):
    """{asset_id: [(date, o,h,l,c,v), ...]} from the adjusted daily series."""
    out = defaultdict(dict)
    hashes = set()
    seq = []
    for fn in sorted(os.listdir(directory)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(directory, fn)
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        # The driver writes `input_sha256` only on some paths; the file hash is
        # always available and identifies the exact capture used for the pack.
        hashes.add(sha256_file(path))
        if doc.get("input_sha256"):
            hashes.add(doc["input_sha256"])
        for s in doc.get("series") or []:
            if s.get("resolution") != "D" or s.get("adjust") != "adjusted":
                continue
            aid = str(s.get("asset_id"))
            for b in s.get("bars") or []:
                d = _date(b.get("utc"))
                o = _f(b.get("open"))
                h = _f(b.get("high"))
                lo = _f(b.get("low"))
                c = _f(b.get("close"))
                v = _f(b.get("volume"))
                if not d or c is None:
                    continue
                out[aid][d] = (d, o, h, lo, c, v)
                seq.append((aid, d))
    return ({a: [rows[d] for d in sorted(rows)] for a, rows in out.items()},
            hashes)


def load_noncomp(path):
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            tf = r.get("timeframe")
            if tf not in KEYFN:
                continue
            try:
                key = int(r.get("key"))
            except (TypeError, ValueError):
                continue
            rows.append({"asset_id": str(r.get("asset_id")),
                         "symbol": r.get("symbol") or "",
                         "timeframe": tf, "key": key,
                         "prod_days": int(r.get("prod_days") or 0),
                         "ref_days": int(r.get("ref_days") or 0),
                         "missing_days": int(r.get("missing_days") or 0),
                         "extra_days": int(r.get("extra_days") or 0),
                         "reason": r.get("reason") or ""})
    return rows


def build_rows(noncomp, daily, ref_sha, generated_at):
    rows = []
    misses = Counter()
    for r in noncomp:
        bars = daily.get(r["asset_id"]) or []
        buckets = aggregate(bars, KEYFN[r["timeframe"]])
        cur = buckets.get(r["key"])
        if cur is None:
            misses["no_reference_days"] += 1
            rows.append({
                "schema": SCHEMA, "symbol_id": r["asset_id"],
                "symbol": r["symbol"], "timeframe": r["timeframe"],
                "key": r["key"], "date_from": None, "date_to": None,
                "open": None, "high": None, "low": None, "close": None,
                "volume": None, "n_sessions": 0,
                "source": "rahavard_reference_live_2026-10-25",
                "source_kind": "reference", "price_basis": "type7_adjusted",
                "method": "daily_type7_aggregation",
                "ref_bars_sha256": ref_sha,
                "generated_at": generated_at,
                "unavailable": ["no_reference_days"],
                "note": "the reference has no daily bar in this key; not estimated",
            })
            continue
        selected = [b for b in bars if KEYFN[r["timeframe"]](b[0]) == r["key"]]
        o, h, lo, c, v, _last = cur
        rows.append({
            "schema": SCHEMA, "symbol_id": r["asset_id"],
            "symbol": r["symbol"], "timeframe": r["timeframe"],
            "key": r["key"],
            "date_from": selected[0][0] if selected else None,
            "date_to": selected[-1][0] if selected else None,
            "open": o, "high": h, "low": lo, "close": c,
            "volume": v, "n_sessions": len(selected),
            "source": "rahavard_reference_live_2026-10-25",
            "source_kind": "reference", "price_basis": "type7_adjusted",
            "method": "daily_type7_aggregation",
            "ref_bars_sha256": ref_sha,
            "generated_at": generated_at,
            "unavailable": [],
            "note": ("built from the reference's own daily type7 bars on the "
                     "reference calendar; the product's incomplete calendar is "
                     "not used to estimate a missing day"),
        })
    return rows, misses


def write_ndjson_gz(path, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    parts = [json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows]
    with open(path, "wb") as fh:
        fh.write(gzip.compress("".join(parts).encode("utf-8"),
                               compresslevel=9, mtime=0))
    return len(rows)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--captures", required=True)
    ap.add_argument("--noncomp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--generated-at", default="")
    a = ap.parse_args()
    generated_at = a.generated_at or "1970-01-01T00:00:00+00:00"

    daily, hashes = load_captures(a.captures)
    noncomp = load_noncomp(a.noncomp)
    ref_sha = ",".join(sorted(hashes))
    rows, misses = build_rows(noncomp, daily, ref_sha, generated_at)

    os.makedirs(a.out, exist_ok=True)
    bars_path = os.path.join(a.out, "wm_calendar_bars.ndjson.gz")
    n = write_ndjson_gz(bars_path, rows)
    per_tf = Counter(r["timeframe"] for r in rows)
    built = Counter(r["timeframe"] for r in rows if not r["unavailable"])
    summary = {
        "schema": "ra365-wm-calendar-summary/1",
        "generated_at": generated_at,
        "captures": os.path.abspath(a.captures),
        "capture_sha256": sorted(hashes),
        "noncomparable_csv": os.path.abspath(a.noncomp),
        "assets_with_bars": len(daily),
        "keys": len(rows),
        "keys_per_timeframe": dict(per_tf),
        "built_per_timeframe": dict(built),
        "unavailable": dict(misses),
        "bars_file": os.path.basename(bars_path),
        "bars_sha256": sha256_file(bars_path),
        "rows": n,
    }
    with open(os.path.join(a.out, "wm-calendar-summary.json"), "w",
              encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
