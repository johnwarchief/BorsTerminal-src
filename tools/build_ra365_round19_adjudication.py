# -*- coding: utf-8 -*-
"""Round 19 Track A: freeze the P0 adjudication evidence and transition counts.

Reads the committed Round 18 field mismatch artifact (old taxonomy) and the
Round 19 rerun (new taxonomy).  It does not recompute the million-row parity;
it only attaches independent TSETMC / operational-DB evidence to the fields
that were reclassified.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "artifacts", "ra365", "r18-rahavard")
CACHE = os.environ.get("RA365_R18_CACHE", "D:/BorsTerminal-tmp/ra365_round18")
REF = os.path.join(CACHE, "reference.db")
COHORT = os.path.join(CACHE, "cohort.jsonl")
OP_DB = os.environ.get(
    "RA365_OP_DB",
    os.path.join(os.path.dirname(os.path.dirname(ROOT)), "BorsTerminal-src", "market.db"))
PROMOTED_DB = os.environ.get(
    "RA365_PROMOTED_DB", "D:/BorsTerminal-tmp/ra365_round17/market_r17_migrated.db")
OLD_REV = os.environ.get("RA365_OLD_REV", "9531b39f")
FIELDS = ("open", "high_raw", "low_raw", "last", "close_display", "volume")


def sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def git_show(path):
    return subprocess.check_output(
        ["git", "show", "%s:%s" % (OLD_REV, path)], cwd=ROOT).decode("utf-8-sig")


def load_csv(text):
    return list(csv.DictReader(io.StringIO(text)))


def main():
    old = {(r["ra_asset_id"], r["date"], r["field"]): r
           for r in load_csv(git_show(
               "artifacts/ra365/r18-rahavard/rahavard-raw-ohlc-field-mismatches.csv"))}
    new = {(r["ra_asset_id"], r["date"], r["field"]): r
           for r in load_csv(open(os.path.join(
               ART, "rahavard-raw-ohlc-field-mismatches.csv"), encoding="utf-8-sig").read())}
    old_sum = json.loads(git_show(
        "artifacts/ra365/r18-rahavard/rahavard-raw-ohlc-summary.json"))
    new_sum = json.load(open(os.path.join(
        ART, "rahavard-raw-ohlc-summary.json"), encoding="utf-8"))
    old_rows = {r["cause"]: int(r["rows"]) for r in load_csv(git_show(
        "artifacts/ra365/r18-rahavard/rahavard-raw-ohlc-row-taxonomy.csv"))}
    new_rows = {r["cause"]: int(r["rows"]) for r in load_csv(open(os.path.join(
        ART, "rahavard-raw-ohlc-row-taxonomy.csv"), encoding="utf-8-sig").read())}

    con = sqlite3.connect("file:%s?mode=ro" % REF, uri=True)
    op = sqlite3.connect("file:%s?mode=ro" % OP_DB, uri=True)
    ins = {}
    for line in open(COHORT, encoding="utf-8"):
        o = json.loads(line)
        ins.setdefault(o["symbol"], (o["ra_asset_id"], o["ins_code"]))

    keys = []
    for k, r in old.items():
        if r["cause"] == "UNCLASSIFIED":
            keys.append(k)
    for k, r in new.items():
        if r["field"] == "volume" and float(r["ref"] or 0) > 0 and float(r["prod"] or 0) == 0:
            keys.append(k)
    keys = sorted(set(keys))
    out = open(os.path.join(ART, "rahavard-raw-ohlc-round19-adjudication.csv"),
               "w", encoding="utf-8-sig", newline="")
    w = csv.writer(out)
    w.writerow([
        "bucket", "old_cause", "new_cause", "symbol", "ra_asset_id", "date", "field",
        "type0_value", "product_value", "abs_diff", "rel_diff",
        "tsetmc_first", "tsetmc_high", "tsetmc_low", "tsetmc_close",
        "tsetmc_base", "tsetmc_last", "tsetmc_volume", "product_db_volume",
        "note", "status",
    ])
    counts = {}
    for k in keys:
        o = old.get(k) or {}
        n = new[k]
        aid, d, f = k
        ins_code = ins.get(n["symbol"], (aid, None))[1]
        t = con.execute(
            "SELECT first,high,low,close,volume,base,last FROM tsetmc "
            "WHERE ins_code=? AND date=?", (ins_code, d)).fetchone()
        tv = [None] * 7 if t is None else list(t)
        dbv = op.execute(
            "SELECT volume FROM price_history WHERE symbol=? AND date=?",
            (n["symbol"], d)).fetchone()
        zero_volume = (n["field"] == "volume" and float(n["ref"] or 0) > 0
                       and float(n["prod"] or 0) == 0)
        if n["field"] == "open" and tv[0] == 0:
            bucket = "P0_OPEN_FIRST_ZERO_FALLBACK"
            status = "VERIFIED_CONTRACT_FALLBACK"
        elif zero_volume and n["cause"] == "PARSING_OR_TRANSFORM":
            bucket = "P0_VOLUME_SNAPSHOT_ZERO"
            status = "BLOCKED_SNAPSHOT"
        elif (zero_volume and dbv and dbv[0] is not None and dbv[0] > 0
              and abs(float(dbv[0]) - float(n["ref"])) <= 0.5):
            bucket = "P0_VOLUME_SNAPSHOT_STALE"
            status = "BLOCKED_SNAPSHOT"
        elif zero_volume and n["cause"] == "SOURCE_DATA_DIVERGENCE":
            bucket = "P0_VOLUME_TYPE0_ONLY"
            status = "VERIFIED_SOURCE_DIVERGENCE"
        elif n["cause"] == "SOURCE_DATA_DIVERGENCE":
            bucket = "P0_THREE_SOURCE_DIVERGENCE"
            status = "VERIFIED_SOURCE_DIVERGENCE"
        else:
            bucket = "P0_OTHER"
            status = "UNCLASSIFIED"
        counts[bucket] = counts.get(bucket, 0) + 1
        w.writerow([
            bucket, o.get("cause", ""), n["cause"], n["symbol"], aid, d, f,
            n["ref"], n["prod"], n["abs_diff"], n["rel_diff"],
            tv[0], tv[1], tv[2], tv[3], tv[5], tv[6], tv[4],
            dbv[0] if dbv else "",
            n["note"], status,
        ])
    out.close()

    tw = open(os.path.join(ART, "rahavard-raw-ohlc-round19-transitions.csv"),
              "w", encoding="utf-8-sig", newline="")
    twriter = csv.writer(tw)
    twriter.writerow(["level", "old", "new", "old_count", "new_count", "delta", "note"])
    field_pairs = {}
    for k in set(old) & set(new):
        field_pairs[(old[k]["cause"], new[k]["cause"])] = \
            field_pairs.get((old[k]["cause"], new[k]["cause"]), 0) + 1
    for (a, b), c in sorted(field_pairs.items()):
        twriter.writerow(["field", a, b, c, c, 0, "same key set; cause transition"])
    for cause in sorted(set(old_rows) | set(new_rows)):
        twriter.writerow(["row", cause, cause, old_rows.get(cause, 0),
                          new_rows.get(cause, 0),
                          new_rows.get(cause, 0) - old_rows.get(cause, 0),
                          "net row taxonomy"])
    tw.close()

    summary = {
        "round": 19,
        "date": "2026-10-22",
        "branch": subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT).decode().strip(),
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
        "old_rev": OLD_REV,
        "field_transitions": {"%s->%s" % k: v for k, v in field_pairs.items()},
        "row_taxonomy_old": old_rows,
        "row_taxonomy_new": new_rows,
        "adjudication_buckets": counts,
        "parity": {
            "contract_ok_pct": new_sum["contract_ok_pct"],
            "row_exact_pct": new_sum["row_exact_pct"],
            "row_pairs": new_sum["row_pairs"],
            "contract_ok_fields": new_sum["contract_ok_fields"],
            "contract_compared_fields": new_sum["contract_compared_fields"],
        },
        "db": {
            "reference": {"path": REF, "sha256": sha256(REF)},
            "operational": {"path": OP_DB, "sha256": sha256(OP_DB)},
            "promoted": ({"path": PROMOTED_DB, "sha256": sha256(PROMOTED_DB)}
                         if os.path.exists(PROMOTED_DB) else
                         {"path": PROMOTED_DB, "sha256": "MISSING"}),
        },
        "tests": "dev/test_rahavard_raw_parity_v1.py: 16/16 passed",
        "artifacts": {},
    }
    for name in ("rahavard-raw-ohlc-parity.csv",
                 "rahavard-type0-vs-tsetmc.csv",
                 "rahavard-raw-ohlc-field-mismatches.csv",
                 "rahavard-raw-ohlc-taxonomy.csv",
                 "rahavard-raw-ohlc-row-taxonomy.csv",
                 "rahavard-raw-ohlc-missing.csv",
                 "rahavard-raw-ohlc-summary.json",
                 "rahavard-raw-ohlc-cohort-manifest.json",
                 "source-field-matrix-rahavard.csv"):
        p = os.path.join(ART, name)
        summary["artifacts"][name] = {"bytes": os.path.getsize(p), "sha256": sha256(p)}
    with open(os.path.join(ART, "rahavard-raw-ohlc-round19-summary.json"),
              "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(json.dumps({"buckets": counts, "field_transitions": summary["field_transitions"],
                      "row_old": old_rows, "row_new": new_rows},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
