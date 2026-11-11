#!/usr/bin/env python3
"""Phase 4.9.3 stage06: verify the owner-restored capture bytes before any use.

The mission was BLOCKED_CAPTURE_REQUIRED because the licensed paired type0/type7
bytes were absent from this machine. The owner restored them through Git LFS on
a separate branch. A transfer report is a claim, not evidence: this stage
re-derives every number from the bytes themselves and publishes nothing if any
check fails.

Three layers are verified separately and never conflated:

* pointer   -- the ~130-byte LFS pointer committed on the owner's branch, read
  with ``git cat-file`` only. No checkout happens; no working tree is touched.
* container -- the real object in the shared LFS store: SHA-256 of the ``.gz``
  file plus its byte size.
* payload   -- SHA-256 of the *decompressed* NDJSON, gzip CRC, and an independent
  recount of every bar by type / resolution / identity key / date.

The recount is joined to the restored reference index on the project's identity
key for all 759 symbols, and the frozen 30-symbol cohort additionally gets its
factor chain recomputed from the restored bars and compared to the index. Index
presence alone is not coverage: type0 AND type7 must both span the local window.

Inputs are pinned by SHA-256. No clock value enters the payload; run time and
any materialisation action live only in the manifest. Reruns are byte-identical.
Fail-closed: on any mismatch the stage exits 2 and writes no output.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
_DEV = os.path.join(ROOT, "dev")
while _DEV in sys.path:
    sys.path.remove(_DEV)
sys.path.insert(0, _DEV)  # dev/symbol_identity wins over the root shim

from symbol_identity import key as symbol_key  # noqa: E402

CAPTURE_SUMMARY = "_audit/phase49-full-verification/evidence/capture-summary.json"
COHORT = "_audit/phase49-3/evidence/COHORT-SELECTION.json"
BARS_REL = "_audit/phase49-full-verification/captures/bars-all.ndjson.gz"
INDEX_REL = "_audit/phase49-full-verification/captures/reference-index-all.json"

EXPECTED_SHA = {
    CAPTURE_SUMMARY:
        "6cbeb62811f42d143a9d6b5c10324e2eae57b6914e8f875a3ee0e50d6154da8b",
    COHORT:
        "857573dd33676d18fda6243806786690eec70abbf8bcee965d48d825eaa77901",
}

OWNER_BRANCH = "mission/phase49-3-capture-lfs-2026-11-11"
OWNER_REF = "refs/remotes/github/" + OWNER_BRANCH
OWNER_TIP = "e887a1236f5cc4f9501a48e416c5748fc33646b9"
OWNER_FILES_COMMIT = "18dd46a71445d2e69141d0113cd1419d82575fbe"
BASE_COMMIT = "e09ccd95d51c94082640cda75ef3de2b2008f9d2"

# Frozen Phase 4.9 tolerance, quoted for the record. Never re-tuned here.
FACTOR_EXACT = 1e-3

OUT = "_audit/phase49-3/evidence/RESTORED-CAPTURE-VERIFICATION.json"
MANIFEST = "_audit/phase49-3/manifests/stage06-verify-restored-capture.json"

CHUNK = 1 << 20


def git(*args):
    proc = subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8")
    if proc.returncode != 0:
        sys.exit("FATAL: git %s failed: %s"
                 % (" ".join(args), proc.stderr.strip()))
    return proc.stdout.strip()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(rel):
    with io.open(os.path.join(ROOT, rel.replace("/", os.sep)),
                 encoding="utf-8") as fh:
        return json.load(fh)


def write_json(rel, obj):
    path = os.path.join(ROOT, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    return sha256_file(path)


def parse_pointer(text):
    """Return (oid, size) for an LFS pointer, or None for a real blob."""
    if not text.startswith("version https://git-lfs.github.com/spec/v1"):
        return None
    oid = size = None
    for line in text.splitlines():
        if line.startswith("oid sha256:"):
            oid = line[len("oid sha256:"):].strip()
        elif line.startswith("size "):
            size = int(line[5:].strip())
    if oid is None or size is None:
        sys.exit("FATAL: malformed LFS pointer")
    return oid, size


def lfs_object(store, oid):
    return os.path.join(store, "lfs", "objects", oid[0:2], oid[2:4], oid)


# --------------------------------------------------------------------------
# layer 1+2: pointer and container
# --------------------------------------------------------------------------

def check_container(path, expected_sha, expected_size, label):
    """Hash a real file and compare to the pinned expectation."""
    report = {"label": label, "path": path.replace(os.sep, "/"),
              "present": os.path.exists(path)}
    failures = []
    if not report["present"]:
        failures.append("%s: file absent: %s" % (label, path))
        return report, failures
    report["size_bytes"] = os.path.getsize(path)
    report["sha256"] = sha256_file(path)
    report["expected_sha256"] = expected_sha
    report["expected_size_bytes"] = expected_size
    report["sha256_match"] = report["sha256"] == expected_sha
    report["size_match"] = report["size_bytes"] == expected_size
    if not report["sha256_match"]:
        failures.append("%s: sha256 %s != expected %s"
                        % (label, report["sha256"], expected_sha))
    if not report["size_match"]:
        failures.append("%s: size %d != expected %d"
                        % (label, report["size_bytes"], expected_size))
    return report, failures


# --------------------------------------------------------------------------
# layer 3: independent recount of the decompressed payload
# --------------------------------------------------------------------------

def scan_bars(path, cohort_keys, spelling_to_key):
    """One streaming pass: payload digest, gzip CRC, and a full recount.

    ``cohort_keys`` rows additionally keep their daily date->close maps so the
    factor chain can be recomputed for the frozen 30 without a second pass.
    """
    h = hashlib.sha256()
    per_type = collections.Counter()
    per_res = collections.Counter()
    per_type_res = collections.Counter()
    adjust_vals = collections.Counter()
    basis_vals = collections.Counter()
    date_counts = collections.Counter()
    spellings = collections.defaultdict(set)
    assets = collections.defaultdict(set)
    spellings_all = collections.defaultdict(set)
    counts = collections.defaultdict(lambda: collections.Counter())
    finite = collections.defaultdict(lambda: collections.Counter())
    window = {}
    unmapped = collections.Counter()
    cohort_rows = {k: {"type0": {}, "type7": {}} for k in cohort_keys}
    total = null_close = ohlc_null = ohlc_inverted = null_volume = 0
    adjacent_dupes = out_of_order = 0
    prev = None
    first = last = None

    with gzip.open(path, "rb") as fh:   # CRC is checked by gzip at EOF
        for line in fh:
            h.update(line)
            if not line.strip():
                continue
            row = json.loads(line)
            total += 1
            typ = str(row.get("type") or "")
            adjust = row.get("adjust")
            if typ == "type0" or adjust == "raw":
                st = "type0"
            elif typ == "type7" or adjust == "adjusted":
                st = "type7"
            else:
                st = None
            res = str(row.get("resolution") or "")
            per_type[st or "UNCLASSIFIED"] += 1
            per_res[res or "NONE"] += 1
            per_type_res["%s/%s" % (st or "UNCLASSIFIED", res or "NONE")] += 1
            adjust_vals[str(adjust)] += 1
            basis_vals[str(row.get("basis"))] += 1

            spelling = str(row.get("symbol") or "")
            k = spelling_to_key.get(spelling)
            if k is None:
                k = symbol_key(spelling)
                unmapped[spelling] += 1
            if k:
                spellings_all[k].add(spelling)
                if st:
                    counts[k]["%s/%s" % (st, res)] += 1

            day = str(row.get("date") or "")
            if day:
                if first is None or day < first:
                    first = day
                if last is None or day > last:
                    last = day
                if res == "D":
                    date_counts[day] += 1

            close = row.get("close")
            try:
                close_f = float(close)
            except (TypeError, ValueError):
                close_f = None
            if close_f is None or not math.isfinite(close_f):
                null_close += 1
                close_f = None
            ohlc = [row.get(f) for f in ("open", "high", "low", "close")]
            if any(v is None for v in ohlc):
                ohlc_null += 1
            else:
                try:
                    if float(row["high"]) < float(row["low"]):
                        ohlc_inverted += 1
                except (TypeError, ValueError):
                    pass
            if row.get("volume") is None:
                null_volume += 1

            ident = (row.get("asset_id"), res, st, day)
            if prev is not None:
                if ident == prev:
                    adjacent_dupes += 1
                elif ident < prev:
                    out_of_order += 1
            prev = ident

            if (res == "D" and st and k and day and close_f is not None):
                # The frozen index only ever sees daily rows with a finite
                # close, so spellings/asset ids must be collected under that
                # same rule or the comparison below invents a mismatch.
                spellings[k].add(spelling)
                aid = row.get("asset_id")
                if aid not in (None, ""):
                    assets[k].add(str(aid))
                finite[k][st] += 1
                w = window.get((k, st))
                if w is None:
                    window[(k, st)] = [day, day]
                else:
                    if day < w[0]:
                        w[0] = day
                    if day > w[1]:
                        w[1] = day
                if k in cohort_rows:
                    cohort_rows[k][st].setdefault(day, close_f)

    return {
        "payload_sha256": h.hexdigest(),
        "gzip_crc_verified": True,
        "bars_total": total,
        "per_type": dict(per_type),
        "per_resolution": dict(per_res),
        "per_type_resolution": dict(per_type_res),
        "adjust_values": dict(adjust_vals),
        "basis_values": dict(basis_vals),
        "first_date": first,
        "last_date": last,
        "distinct_dates_daily": len(date_counts),
        "bars_on_last_date": date_counts.get(last, 0),
        "last_date_daily_bars": date_counts.get(last, 0),
        "symbols_identity_keys": len(counts),
        "raw_spellings_all_rows": sum(len(v) for v in spellings_all.values()),
        "raw_spellings_daily_finite_rows": sum(len(v) for v in spellings.values()),
        "null_or_nonfinite_close_rows": null_close,
        "ohlc_null_rows": ohlc_null,
        "ohlc_high_below_low_rows": ohlc_inverted,
        "null_volume_rows": null_volume,
        "adjacent_duplicate_identity_rows": adjacent_dupes,
        "out_of_order_identity_rows": out_of_order,
        "unmapped_spelling_rows": sum(unmapped.values()),
        "unmapped_spellings": dict(unmapped),
        "_counts": {k: dict(v) for k, v in counts.items()},
        "_finite": {k: dict(v) for k, v in finite.items()},
        "_window": {"%s|%s" % kk: v for kk, v in window.items()},
        "_spellings": {k: sorted(v) for k, v in spellings.items()},
        "_assets": {k: sorted(v) for k, v in assets.items()},
        "_cohort_rows": cohort_rows,
        "_date_counts_tail": dict(sorted(date_counts.items())[-5:]),
    }


def check_bars(scan, merged, totals, extra):
    """Compare the independent recount to the recorded Phase 4.9 evidence."""
    failures = []
    checks = {}

    def eq(name, actual, expected):
        ok = actual == expected
        checks[name] = {"actual": actual, "expected": expected, "ok": ok}
        if not ok:
            failures.append("bars %s: %r != recorded %r"
                            % (name, actual, expected))

    eq("payload_sha256", scan["payload_sha256"], merged["bars_payload_sha256"])
    eq("bars_total", scan["bars_total"], totals["merged_bars"])
    eq("per_type", scan["per_type"], merged["per_type"])
    eq("per_resolution", scan["per_resolution"], merged["per_resolution"])
    eq("first_date", scan["first_date"], merged["first_date"])
    eq("last_date", scan["last_date"], merged["last_date"])
    eq("symbols_identity_keys", scan["symbols_identity_keys"],
       totals["merged_symbols"])
    eq("merged_equals_normalized_plus_extra", scan["bars_total"],
       totals["normalized_bars"] + extra["bars_merged"])
    eq("per_type_sums_to_total", sum(scan["per_type"].values()),
       scan["bars_total"])
    eq("per_resolution_sums_to_total", sum(scan["per_resolution"].values()),
       scan["bars_total"])
    eq("adjacent_duplicate_identity_rows",
       scan["adjacent_duplicate_identity_rows"], totals["duplicates_dropped"])
    return checks, failures


# --------------------------------------------------------------------------
# index vs recount, all symbols
# --------------------------------------------------------------------------

def check_index(index, scan, expected_index):
    failures = []
    counts = scan["_counts"]
    finite = scan["_finite"]
    window = scan["_window"]
    spellings = scan["_spellings"]
    assets = scan["_assets"]

    agg = {
        "symbols": len(index),
        "factor_changes": sum(len(r["factor_changes"]) for r in index.values()),
        "factor_days": sum(r["factor_days"] for r in index.values()),
        "date_conflicts": sum(r["date_conflicts"] for r in index.values()),
        "zero_raw_days": sum(r["zero_raw_days"] for r in index.values()),
    }
    checks = {}
    for name, exp in (("symbols", expected_index["symbols"]),
                      ("factor_changes", expected_index["factor_changes"]),
                      ("factor_days", expected_index["factor_days"])):
        ok = agg[name] == exp
        checks[name] = {"actual": agg[name], "expected": exp, "ok": ok}
        if not ok:
            failures.append("index %s: %d != recorded %d"
                            % (name, agg[name], exp))

    # The join itself is validated: every recorded spelling must normalise to
    # the key it is filed under, or the comparison below would be meaningless.
    join_bad = []
    for k, rec in index.items():
        if rec.get("key") != k:
            join_bad.append({"key": k, "reason": "record key field differs"})
        for sp in rec.get("raw_symbols", []):
            if symbol_key(sp) != k:
                join_bad.append({"key": k, "spelling": sp,
                                 "reason": "spelling normalises elsewhere"})
    checks["identity_join_valid"] = {"bad": len(join_bad), "ok": not join_bad}
    if join_bad:
        failures.append("index identity join invalid for %d entries: %r"
                        % (len(join_bad), join_bad[:5]))

    per_symbol = []
    mismatch = collections.Counter()
    for k in sorted(index):
        rec = index[k]
        row = {"key": k}
        for st in ("type0", "type7"):
            w = window.get("%s|%s" % (k, st))
            n = finite.get(k, {}).get(st, 0)
            exp = rec[st]
            same_n = n == exp["n"]
            same_first = (w[0] if w else None) == exp["first"]
            same_last = (w[1] if w else None) == exp["last"]
            row[st] = {"counted_daily_finite": n, "index_n": exp["n"],
                       "counted_first": w[0] if w else None,
                       "counted_last": w[1] if w else None,
                       "index_first": exp["first"], "index_last": exp["last"],
                       "match": same_n and same_first and same_last}
            if not same_n:
                mismatch["n"] += 1
            if not same_first:
                mismatch["first"] += 1
            if not same_last:
                mismatch["last"] += 1
        sp_ok = spellings.get(k, []) == sorted(rec.get("raw_symbols", []))
        aid_ok = assets.get(k, []) == sorted(rec.get("asset_ids", []))
        row["spellings_match"] = sp_ok
        row["asset_ids_match"] = aid_ok
        if not sp_ok:
            mismatch["spellings"] += 1
        if not aid_ok:
            mismatch["asset_ids"] += 1
        row["all_match"] = (row["type0"]["match"] and row["type7"]["match"]
                            and sp_ok and aid_ok)
        per_symbol.append(row)

    absent_in_bars = sorted(set(index) - set(counts))
    absent_in_index = sorted(set(counts) - set(index))
    checks["symbols_in_index_absent_from_bars"] = {
        "count": len(absent_in_bars), "keys": absent_in_bars[:20],
        "ok": not absent_in_bars}
    checks["symbols_in_bars_absent_from_index"] = {
        "count": len(absent_in_index), "keys": absent_in_index[:20],
        "ok": not absent_in_index}
    if absent_in_bars:
        failures.append("%d index symbols have no bars: %r"
                        % (len(absent_in_bars), absent_in_bars[:10]))
    if absent_in_index:
        failures.append("%d bar symbols are absent from the index: %r"
                        % (len(absent_in_index), absent_in_index[:10]))
    checks["per_symbol_mismatch_counts"] = dict(mismatch)
    checks["per_symbol_all_match"] = sum(1 for r in per_symbol if r["all_match"])
    checks["per_symbol_total"] = len(per_symbol)
    if mismatch:
        failures.append("index/bars per-symbol mismatches: %r" % dict(mismatch))
    return checks, failures, agg, per_symbol


# --------------------------------------------------------------------------
# cohort: coverage plus an independently recomputed factor chain
# --------------------------------------------------------------------------

def recompute_chain(raw_days, adj_days):
    """Replicate the frozen stage02 factor rule on restored daily closes."""
    common = sorted(set(raw_days) & set(adj_days))
    previous = None
    exact = within = changes = zero = undefined = factor_days = 0
    events = []
    for day in common:
        rr = raw_days[day]
        if rr == 0:
            zero += 1
            continue
        factor = adj_days[day] / rr
        if not math.isfinite(factor):
            continue
        factor_days += 1
        if previous is not None:
            if previous == 0:
                undefined += 1
            else:
                ratio = factor / previous
                if not math.isfinite(ratio):
                    undefined += 1
                elif ratio == 1.0:
                    exact += 1
                elif abs(ratio - 1.0) > FACTOR_EXACT:
                    events.append({"date": day, "factor": factor,
                                   "ratio_change": ratio})
                    changes += 1
                else:
                    within += 1
        previous = factor
    return {"factor_days": factor_days, "factor_exact": exact,
            "factor_within_0.1pct": within, "factor_changes": events,
            "factor_undefined_ratio": undefined, "zero_raw_days": zero}


def check_cohort(cohort, index, scan):
    failures = []
    members = cohort["members"]
    rows = []
    tot0 = tot7 = tot_exp = 0
    chain_ok = 0
    for m in members:
        k = m["key"]
        rec = index.get(k)
        r = {"key": k, "asset_id": m["asset_id"],
             "expected_raw_rows": m["expected_raw_rows"],
             "present_in_index": rec is not None}
        tot_exp += m["expected_raw_rows"]
        if rec is None:
            failures.append("cohort %s: absent from restored index" % k)
            rows.append(r)
            continue
        counted = scan["_counts"].get(k, {})
        n0 = scan["_finite"].get(k, {}).get("type0", 0)
        n7 = scan["_finite"].get(k, {}).get("type7", 0)
        tot0 += n0
        tot7 += n7
        w0 = scan["_window"].get("%s|type0" % k)
        w7 = scan["_window"].get("%s|type7" % k)
        r["type0_daily_bars"] = n0
        r["type7_daily_bars"] = n7
        r["type0_all_resolution_bars"] = sum(
            v for kk, v in counted.items() if kk.startswith("type0/"))
        r["type7_all_resolution_bars"] = sum(
            v for kk, v in counted.items() if kk.startswith("type7/"))
        r["index_type0"] = rec["type0"]
        r["index_type7"] = rec["type7"]
        r["expected_raw_rows_match"] = (n0 == m["expected_raw_rows"]
                                        and n7 == m["expected_raw_rows"])
        r["ref_window_match"] = (
            rec["type0"]["first"] == m["ref_first"]
            and rec["type0"]["last"] == m["ref_last"]
            and rec["type7"]["first"] == m["ref_first"]
            and rec["type7"]["last"] == m["ref_last"])
        # Coverage is a span guarantee on BOTH series over the local window.
        r["covers_local_window"] = bool(
            w0 and w7
            and w0[0] <= m["seed_first_date"] and w0[1] >= m["seed_last_date"]
            and w7[0] <= m["seed_first_date"] and w7[1] >= m["seed_last_date"])
        r["paired_type0_type7"] = bool(n0 > 0 and n7 > 0)
        r["bars_on_capture_last_date"] = {
            "type0": int(m["ref_last"] in scan["_cohort_rows"][k]["type0"]),
            "type7": int(m["ref_last"] in scan["_cohort_rows"][k]["type7"]),
        }
        mine = recompute_chain(scan["_cohort_rows"][k]["type0"],
                              scan["_cohort_rows"][k]["type7"])
        diffs = {}
        for f in ("factor_days", "factor_exact", "factor_within_0.1pct",
                  "factor_undefined_ratio", "zero_raw_days"):
            if mine[f] != rec[f]:
                diffs[f] = {"recomputed": mine[f], "index": rec[f]}
        if mine["factor_changes"] != rec["factor_changes"]:
            a = {(e["date"], e["factor"], e["ratio_change"])
                 for e in mine["factor_changes"]}
            b = {(e["date"], e["factor"], e["ratio_change"])
                 for e in rec["factor_changes"]}
            diffs["factor_changes"] = {
                "recomputed_count": len(mine["factor_changes"]),
                "index_count": len(rec["factor_changes"]),
                "only_recomputed": sorted(a - b)[:5],
                "only_index": sorted(b - a)[:5]}
        r["chain_recomputed"] = {kk: vv for kk, vv in mine.items()
                                 if kk != "factor_changes"}
        r["chain_recomputed"]["factor_changes_count"] = len(mine["factor_changes"])
        r["chain_matches_index"] = not diffs
        if diffs:
            r["chain_diffs"] = diffs
            failures.append("cohort %s: recomputed chain differs: %r"
                            % (k, sorted(diffs)))
        else:
            chain_ok += 1
        for flag in ("expected_raw_rows_match", "ref_window_match",
                     "covers_local_window", "paired_type0_type7"):
            if not r[flag]:
                failures.append("cohort %s: %s is False" % (k, flag))
        rows.append(r)

    fully = all(r.get("expected_raw_rows_match") and r.get("ref_window_match")
                and r.get("covers_local_window") and r.get("paired_type0_type7")
                and r.get("chain_matches_index") for r in rows)
    summary = {
        "members": len(members),
        "present_in_index": sum(1 for r in rows if r["present_in_index"]),
        "type0_daily_bars_total": tot0,
        "type7_daily_bars_total": tot7,
        "expected_raw_rows_total": tot_exp,
        "expected_raw_rows_total_match": tot0 == tot7 == tot_exp,
        "chain_matches_index_count": chain_ok,
        "cohort_fully_covered": bool(fully),
        "disjoint_from_previous_pilot": cohort["disjoint_from_previous_pilot"],
    }
    if not summary["expected_raw_rows_total_match"]:
        failures.append("cohort totals: type0=%d type7=%d expected=%d"
                        % (tot0, tot7, tot_exp))
    if not fully:
        failures.append("cohort is NOT fully covered by the restored capture")
    return summary, failures, rows


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--materialize", action="store_true",
                    help="after every check passes, copy the verified bytes "
                         "into the gitignored capture path and re-hash them")
    ap.add_argument("--lfs-store", default=None,
                    help="git common dir holding lfs/objects (default: derive)")
    args = ap.parse_args()

    started = time.time()
    failures = []

    for rel, exp in EXPECTED_SHA.items():
        got = sha256_file(os.path.join(ROOT, rel.replace("/", os.sep)))
        if got != exp:
            sys.exit("FATAL: pinned input %s has sha256 %s, expected %s"
                     % (rel, got, exp))

    summary = read_json(CAPTURE_SUMMARY)
    cohort = read_json(COHORT)
    merged = summary["merged"]
    totals = summary["totals"]
    extra = summary["extra"]

    store = args.lfs_store or git("rev-parse", "--git-common-dir")
    if not os.path.isabs(store):
        store = os.path.join(ROOT, store)
    store = os.path.normpath(store)

    tip = git("rev-parse", OWNER_REF)
    if tip != OWNER_TIP:
        sys.exit("FATAL: owner branch tip %s != pinned %s" % (tip, OWNER_TIP))
    parent = git("rev-parse", OWNER_TIP + "^")
    if parent != OWNER_FILES_COMMIT:
        sys.exit("FATAL: owner files commit %s != pinned %s"
                 % (parent, OWNER_FILES_COMMIT))
    head = git("rev-parse", "HEAD")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")

    pointers = {}
    containers = {}
    for rel, exp_sha, exp_size in (
            (BARS_REL, merged["bars_container_sha256"], None),
            (INDEX_REL, merged["reference_index_all"]["sha256"], None)):
        blob = git("cat-file", "blob", "%s:%s" % (OWNER_TIP, rel))
        p = parse_pointer(blob)
        if p is None:
            sys.exit("FATAL: %s on the owner branch is not an LFS pointer" % rel)
        oid, size = p
        pointers[rel] = {"committed_blob_bytes": len(blob.encode("utf-8")),
                         "oid_sha256": oid, "size_bytes": size,
                         "oid_matches_recorded_evidence": oid == exp_sha}
        if oid != exp_sha:
            failures.append("%s: pointer oid %s != recorded evidence %s"
                            % (rel, oid, exp_sha))
        obj = lfs_object(store, oid)
        rep, bad = check_container(obj, exp_sha, size, "container:" + rel)
        containers[rel] = rep
        failures.extend(bad)

    bars_path = lfs_object(store, merged["bars_container_sha256"])
    index_path = lfs_object(store, merged["reference_index_all"]["sha256"])
    if failures:
        print("FAIL (container layer), nothing written:")
        for f in failures:
            print("  -", f)
        return 2

    with io.open(index_path, encoding="utf-8") as fh:
        index = json.load(fh)

    cohort_keys = {m["key"] for m in cohort["members"]}
    spelling_to_key = {}
    for k, rec in index.items():
        for sp in rec.get("raw_symbols", []):
            spelling_to_key[sp] = k

    print("scanning %d bytes of container ..." % os.path.getsize(bars_path),
          flush=True)
    scan = scan_bars(bars_path, cohort_keys, spelling_to_key)
    print("  bars=%d payload=%s" % (scan["bars_total"],
                                    scan["payload_sha256"][:16]), flush=True)

    bar_checks, bad = check_bars(scan, merged, totals, extra)
    failures.extend(bad)
    idx_checks, bad, idx_agg, per_symbol = check_index(
        index, scan, merged["reference_index_all"])
    failures.extend(bad)
    cohort_summary, bad, cohort_rows = check_cohort(cohort, index, scan)
    failures.extend(bad)

    if failures:
        print("FAIL (%d problems), nothing written:" % len(failures))
        for f in failures[:40]:
            print("  -", f)
        return 2

    public_scan = {k: v for k, v in scan.items() if not k.startswith("_")}
    payload = {
        "schema": "phase49-3-restored-capture-verification-v1",
        "mission": "Phase 4.9.3 coverage expansion",
        "status": "PASS",
        "base_commit": BASE_COMMIT,
        "mission_branch": branch,
        "mission_head_at_run": head,
        "owner_source": {
            "branch": OWNER_BRANCH,
            "ref": OWNER_REF,
            "tip_commit": tip,
            "files_commit": parent,
            "read_method": "git cat-file blob; no checkout, no working tree "
                           "of the owner branch was created",
            "pointers": pointers,
        },
        "lfs_store": store.replace(os.sep, "/"),
        "containers": containers,
        "bars_recount": public_scan,
        "bars_checks": bar_checks,
        "index_aggregates": idx_agg,
        "index_checks": idx_checks,
        "index_per_symbol": per_symbol,
        "cohort_summary": cohort_summary,
        "cohort_members": cohort_rows,
        "frozen_tolerances": {"FACTOR_EXACT": FACTOR_EXACT},
        "recorded_evidence_input": {
            "path": CAPTURE_SUMMARY, "sha256": EXPECTED_SHA[CAPTURE_SUMMARY]},
        "cohort_input": {"path": COHORT, "sha256": EXPECTED_SHA[COHORT]},
        "honesty": {
            "container_vs_payload":
                "container_sha256 is the .gz file; payload_sha256 is the "
                "decompressed NDJSON. Both are checked; neither stands in for "
                "the other.",
            "transfer_report_is_not_evidence":
                "the owner's LFS-TRANSFER-VERIFICATION.json was not used as "
                "input. Every number here was re-derived from the bytes.",
            "index_presence_is_not_coverage":
                "coverage requires type0 AND type7 to span the local window; "
                "a symbol merely listed in the index is not called covered.",
            "no_candles_computed":
                "this stage verifies bytes and counts only. No factor was "
                "written to any database, no candle was built, and neither "
                "red-line DB was opened.",
            "recount_scope":
                "the factor chain was recomputed for the frozen 30 only, not "
                "for all 759 symbols; the other 729 were compared on counts, "
                "windows, spellings and asset ids.",
        },
    }

    manifest = {
        "stage": "stage06_verify_restored_capture",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(time.time() - started, 3),
        "mission_head_at_run": head,
        "materialize_requested": bool(args.materialize),
        "exit_code": 0,
    }

    if args.materialize:
        mat = {}
        for rel, src in ((BARS_REL, bars_path), (INDEX_REL, index_path)):
            dst = os.path.join(ROOT, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            got = sha256_file(dst)
            exp = containers[rel]["sha256"]
            ignored = subprocess.run(
                ["git", "check-ignore", "-q", rel], cwd=ROOT,
                capture_output=True).returncode == 0
            mat[rel] = {"destination_sha256": got,
                        "destination_size_bytes": os.path.getsize(dst),
                        "matches_verified_source": got == exp,
                        "gitignored": ignored}
            if got != exp or not ignored:
                print("FATAL: materialisation of %s failed (hash_match=%s "
                      "ignored=%s)" % (rel, got == exp, ignored))
                return 2
        manifest["materialized"] = mat

    out_sha = write_json(OUT, payload)
    manifest["payload_sha256"] = out_sha
    manifest["payload_path"] = OUT
    man_sha = write_json(MANIFEST, manifest)

    print("PASS  bars=%d  symbols=%d  payload=%s"
          % (scan["bars_total"], scan["symbols_identity_keys"],
             scan["payload_sha256"]))
    print("      index symbols=%d factor_changes=%d factor_days=%d"
          % (idx_agg["symbols"], idx_agg["factor_changes"],
             idx_agg["factor_days"]))
    print("      per-symbol all_match=%d/%d"
          % (idx_checks["per_symbol_all_match"], idx_checks["per_symbol_total"]))
    print("      cohort type0=%d type7=%d expected=%d chain_ok=%d/%d fully=%s"
          % (cohort_summary["type0_daily_bars_total"],
             cohort_summary["type7_daily_bars_total"],
             cohort_summary["expected_raw_rows_total"],
             cohort_summary["chain_matches_index_count"],
             cohort_summary["members"], cohort_summary["cohort_fully_covered"]))
    print("wrote %s (%s)" % (OUT, out_sha[:16]))
    print("wrote %s (%s)" % (MANIFEST, man_sha[:16]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())