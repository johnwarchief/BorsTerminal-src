#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32D: reference-calendar W/M bar builder.

Synthetic, no network, no DB:
  * a week/month bar is the same OHLCV aggregate the audit uses;
  * a key with no reference daily bar is unavailable, never estimated;
  * the gzip output is byte-deterministic for the same input.
"""
import csv
import gzip
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import ra365_round32d_calendar as D  # noqa: E402
from ra365_round32b_audit import month_key, week_key  # noqa: E402

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   <- %s" % (detail,)) if detail else ""))


def capture(root, bars):
    d = os.path.join(root, "captures")
    os.makedirs(d, exist_ok=True)
    doc = {"input_sha256": "test-capture-sha", "series": [{
        "asset_id": 1, "symbol": "TEST", "resolution": "D",
        "adjust": "adjusted", "basis": "real_close", "status": 200,
        "bars": bars,
    }]}
    with open(os.path.join(d, "shard01.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    return d


def noncomp(root, rows):
    p = os.path.join(root, "noncomp.csv")
    fields = ["asset_id", "symbol", "timeframe", "key", "prod_days",
              "ref_days", "missing_days", "extra_days", "corrected_pass",
              "reason"]
    with open(p, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return p


def bar(date, o, h, l, c, v):
    return {"utc": date + "T00:00:00Z", "open": o, "high": h, "low": l,
            "close": c, "volume": v}


def main():
    tmp = tempfile.mkdtemp(prefix="r32d_test_")
    try:
        # 2026-10-03 is a Saturday; the week key is shared by 10-03..10-09.
        bars = [
            bar("2026-10-03", 10.0, 12.0, 9.0, 11.0, 100),
            bar("2026-10-04", 11.0, 15.0, 8.0, 14.0, 200),
            bar("2026-10-07", 14.0, 16.0, 13.0, 15.0, 300),
            bar("2026-10-10", 15.0, 17.0, 14.0, 16.0, 400),
        ]
        cap = capture(tmp, bars)
        wk = week_key("2026-10-04")
        mk = month_key("2026-10-04")
        csvp = noncomp(tmp, [
            {"asset_id": 1, "symbol": "TEST", "timeframe": "W", "key": wk,
             "prod_days": 4, "ref_days": 3, "missing_days": 0,
             "extra_days": 1, "corrected_pass": 0, "reason": "extra_product_days"},
            {"asset_id": 1, "symbol": "TEST", "timeframe": "M", "key": mk,
             "prod_days": 4, "ref_days": 4, "missing_days": 0,
             "extra_days": 0, "corrected_pass": 0, "reason": "none"},
            {"asset_id": 1, "symbol": "TEST", "timeframe": "W", "key": wk + 5,
             "prod_days": 0, "ref_days": 0, "missing_days": 0,
             "extra_days": 0, "corrected_pass": 0, "reason": "none"},
        ])

        daily, hashes = D.load_captures(cap)
        ck(hashes == {"test-capture-sha"}, "capture hash is carried", hashes)
        rows, misses = D.build_rows(D.load_noncomp(csvp), daily,
                                    "test-capture-sha", "2026-10-25T00:00:00+00:00")
        ck(len(rows) == 3, "one row per non-comparable key", len(rows))
        w = [r for r in rows if r["timeframe"] == "W" and r["key"] == wk][0]
        ck(w["open"] == 10.0 and w["high"] == 16.0 and w["low"] == 8.0
           and w["close"] == 15.0 and w["volume"] == 600.0,
           "weekly OHLCV is first/max/min/last/sum", w)
        ck(w["n_sessions"] == 3 and w["date_from"] == "2026-10-03"
           and w["date_to"] == "2026-10-07", "weekly span is recorded", w)
        m = [r for r in rows if r["timeframe"] == "M"][0]
        ck(m["open"] == 10.0 and m["high"] == 17.0 and m["low"] == 8.0
           and m["close"] == 16.0 and m["volume"] == 1000.0,
           "monthly OHLCV is first/max/min/last/sum", m)
        missing = [r for r in rows if r["key"] == wk + 5][0]
        ck(missing["unavailable"] == ["no_reference_days"]
           and missing["open"] is None and missing["close"] is None,
           "a key with no reference day is unavailable, not estimated", missing)
        ck(misses.get("no_reference_days") == 1, "the miss is counted", misses)

        # Deterministic gzip: the same rows produce the same bytes.
        p1 = os.path.join(tmp, "a.ndjson.gz")
        p2 = os.path.join(tmp, "b.ndjson.gz")
        D.write_ndjson_gz(p1, rows)
        D.write_ndjson_gz(p2, rows)
        b1 = open(p1, "rb").read()
        b2 = open(p2, "rb").read()
        ck(b1 == b2, "gzip output is byte-deterministic")
        got = [json.loads(line) for line in gzip.decompress(b1).decode("utf-8").splitlines()]
        ck(len(got) == 3 and got[0]["schema"] == D.SCHEMA,
           "the pack rows are readable and schema-tagged", got[0].get("schema"))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print("result: %d pass, %d fail" % (P, F))
    print("%d/%d" % (P, P + F))
    sys.exit(0 if F == 0 else 1)


if __name__ == "__main__":
    main()
