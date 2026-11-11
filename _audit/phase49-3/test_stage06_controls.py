#!/usr/bin/env python3
"""Negative controls for stage06_verify_restored_capture.

A gate that cannot fail is not a gate. Stage06 decides whether 145 MB of
licensed bytes may be used at all, so every comparison it makes is exercised
here against a small synthetic capture whose correct answer is known
independently:

A. positive control -- the intact fixture passes all three comparisons, so a
   failure below means the gate bit, not that the harness is broken;
B. container layer -- wrong SHA-256, wrong size, absent file;
C. payload layer -- wrong payload digest, wrong per-type counts, one bar missing,
   wrong last date;
D. index layer -- inflated n, a symbol with no bars, a spelling that normalises
   to a different key (the alias join silently losing rows);
E. cohort layer -- a member absent from the index, a local window that the
   reference does not span, and a perturbed adjusted close that must change the
   recomputed factor chain;
F. gzip layer -- a flipped compressed byte and a truncated stream must both
   raise, proving the CRC/EOF check is live.

Run: PYTHONIOENCODING=utf-8 python _audit/phase49-3/test_stage06_controls.py
Writes only to a temporary directory, removed on exit. No repo file is touched,
no real capture is read, and no database is opened.
"""

import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "dev"))

from symbol_identity import key as standard_key  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location(
        "s6", os.path.join(HERE, "stage06_verify_restored_capture.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def bar(spell, aid, typ, res, day, close, volume=1000):
    return {"symbol": spell, "asset_id": aid, "type": typ,
            "adjust": "raw" if typ == "type0" else "adjusted",
            "resolution": res, "date": day, "open": close, "high": close,
            "low": close, "close": close, "volume": volume,
            "basis": "real_close"}


def fixture():
    """Two symbols, a real factor step, a zero raw day, a null close, W and M."""
    rows = []
    days = ["2020-01-0%d" % i for i in range(1, 7)]
    raw = [100.0, 100.0, 100.0, 100.0, 100.0, 0.0]
    adj = [50.0, 50.0, 25.0, 25.0, 25.0, 25.0]
    for i, d in enumerate(days):
        rows.append(bar("AAA", 1, "type0", "D", d, raw[i]))
        rows.append(bar("AAA", 1, "type7", "D", d, adj[i]))
    rows.append(bar("aaa", 1, "type0", "D", "2020-01-07", None))
    rows.append(bar("AAA", 1, "type0", "W", "2020-01-03", 100.0))
    rows.append(bar("AAA", 1, "type7", "M", "2020-01-31", 25.0))
    for i, d in enumerate(["2021-02-01", "2021-02-02", "2021-02-03"]):
        rows.append(bar("BBB", 2, "type0", "D", d, 200.0))
        rows.append(bar("BBB", 2, "type7", "D", d, 200.0))
    rows.sort(key=lambda r: (r["asset_id"], r["resolution"], r["type"],
                             r["date"]))
    return rows


def build_index(rows):
    """Independent re-implementation of the frozen index rules, for the fixture."""
    raw, adj, spellings, assets = {}, {}, {}, {}
    for r in rows:
        if r["resolution"] != "D":
            continue
        k = standard_key(r["symbol"])
        if not k or r["close"] is None:
            continue
        spellings.setdefault(k, set()).add(r["symbol"])
        assets.setdefault(k, set()).add(str(r["asset_id"]))
        tgt = raw if r["type"] == "type0" else adj
        tgt.setdefault(k, {})[r["date"]] = float(r["close"])
    out = {}
    for k in sorted(set(raw) | set(adj)):
        rr, aa = raw.get(k, {}), adj.get(k, {})
        chain = CHAIN(rr, aa)
        out[k] = {"key": k, "symbol": k, "raw_symbols": sorted(spellings[k]),
                  "asset_ids": sorted(assets[k]),
                  "type0": {"first": min(rr), "last": max(rr), "n": len(rr)},
                  "type7": {"first": min(aa), "last": max(aa), "n": len(aa)},
                  "date_conflicts": 0, **chain}
    return out


CHAIN = None  # bound to stage06.recompute_chain in main()


def expectations(rows, payload_sha):
    per_type, per_res = {}, {}
    for r in rows:
        per_type[r["type"]] = per_type.get(r["type"], 0) + 1
        per_res[r["resolution"]] = per_res.get(r["resolution"], 0) + 1
    dates = [r["date"] for r in rows if r["date"]]
    merged = {"bars_payload_sha256": payload_sha,
              "per_type": per_type, "per_resolution": per_res,
              "first_date": min(dates), "last_date": max(dates)}
    totals = {"merged_bars": len(rows), "merged_symbols": 2,
              "normalized_bars": len(rows), "duplicates_dropped": 0}
    return merged, totals, {"bars_merged": 0}


def cohort_fixture():
    return {"disjoint_from_previous_pilot": True,
            "members": [{"key": "aaa", "asset_id": "1", "expected_raw_rows": 6,
                         "ref_first": "2020-01-01", "ref_last": "2020-01-06",
                         "seed_first_date": "2020-01-02",
                         "seed_last_date": "2020-01-05"}]}


def main():
    global CHAIN
    m = _load()
    CHAIN = m.recompute_chain
    tmp = tempfile.mkdtemp(prefix="phase49-3-s6-controls-")
    results = {}
    diagnostics = {}
    try:
        rows = fixture()
        payload = b"".join((json.dumps(r, ensure_ascii=False, sort_keys=True)
                            + "\n").encode("utf-8") for r in rows)
        payload_sha = hashlib.sha256(payload).hexdigest()
        gz = os.path.join(tmp, "bars.ndjson.gz")
        with open(gz, "wb") as fh:
            fh.write(gzip.compress(payload, mtime=0))
        index = build_index(rows)
        merged, totals, extra = expectations(rows, payload_sha)
        cohort = cohort_fixture()
        s2k = {sp: k for k, rec in index.items() for sp in rec["raw_symbols"]}
        scan = m.scan_bars(gz, {"aaa"}, s2k)

        def bars_fail(sc, mg=merged, tt=totals, ex=extra):
            return m.check_bars(sc, mg, tt, ex)[1]

        def index_fail(ix, sc):
            return m.check_index(ix, sc, {"symbols": len(ix),
                                         "factor_changes": sum(
                                             len(r["factor_changes"])
                                             for r in ix.values()),
                                         "factor_days": sum(
                                             r["factor_days"]
                                             for r in ix.values())})[1]

        def cohort_fail(co, ix, sc):
            return m.check_cohort(co, ix, sc)[1]

        # A -- positive control: the intact fixture must pass everything.
        a_bars = bars_fail(scan)
        a_index = index_fail(index, scan)
        a_cohort = cohort_fail(cohort, index, scan)
        diagnostics = {"A_bars_pass": a_bars, "A_index_pass": a_index,
                       "A_cohort_pass": a_cohort}
        results["A_bars_pass"] = not a_bars
        results["A_index_pass"] = not a_index
        results["A_cohort_pass"] = not a_cohort
        results["A_cohort_fully_covered"] = m.check_cohort(
            cohort, index, scan)[0]["cohort_fully_covered"]
        results["A_payload_digest_correct"] = scan["payload_sha256"] == payload_sha
        results["A_chain_found_the_step"] = (
            index["aaa"]["factor_changes"][0]["date"] == "2020-01-03")
        results["A_zero_raw_day_counted"] = index["aaa"]["zero_raw_days"] == 1
        results["A_null_close_excluded"] = index["aaa"]["type0"]["n"] == 6

        # B -- container layer. The .gz digest is not the payload digest.
        with open(gz, "rb") as fh:
            container_sha = hashlib.sha256(fh.read()).hexdigest()
        container_size = os.path.getsize(gz)
        results["B_container_positive"] = not m.check_container(
            gz, container_sha, container_size, "pos")[1]
        results["B_container_and_payload_differ"] = container_sha != payload_sha
        results["B_wrong_sha_detected"] = bool(
            m.check_container(gz, "0" * 64, container_size, "x")[1])
        results["B_wrong_size_detected"] = bool(
            m.check_container(gz, container_sha, container_size + 1, "x")[1])
        results["B_absent_file_detected"] = bool(
            m.check_container(os.path.join(tmp, "nope"), container_sha, 1, "x")[1])

        # C -- payload layer.
        for tag, field, value in (
                ("digest", "payload_sha256", "f" * 64),
                ("per_type", "per_type", {"type0": 1, "type7": 1}),
                ("total", "bars_total", scan["bars_total"] - 1),
                ("last_date", "last_date", "2020-01-05")):
            sc = copy.deepcopy(scan)
            sc[field] = value
            results["C_wrong_%s_detected" % tag] = bool(bars_fail(sc))
        mg = dict(merged, bars_payload_sha256="e" * 64)
        results["C_recorded_digest_mismatch_detected"] = bool(bars_fail(scan, mg=mg))

        # D -- index layer.
        ix = copy.deepcopy(index)
        ix["aaa"]["type0"]["n"] += 1
        results["D_inflated_n_detected"] = bool(index_fail(ix, scan))
        sc = copy.deepcopy(scan)
        sc["_counts"].pop("bbb")
        results["D_symbol_without_bars_detected"] = bool(index_fail(index, sc))
        ix = copy.deepcopy(index)
        ix["aaa"]["raw_symbols"] = sorted(ix["aaa"]["raw_symbols"] + ["BBB"])
        results["D_alias_join_break_detected"] = bool(index_fail(ix, scan))
        ix = copy.deepcopy(index)
        ix["aaa"]["type7"]["last"] = "2020-01-05"
        results["D_window_mismatch_detected"] = bool(index_fail(ix, scan))

        # E -- cohort layer.
        co = copy.deepcopy(cohort)
        co["members"][0]["key"] = "ccc"
        results["E_member_absent_detected"] = bool(cohort_fail(co, index, scan))
        co = copy.deepcopy(cohort)
        co["members"][0]["seed_last_date"] = "2020-02-01"
        results["E_window_not_spanned_detected"] = bool(
            cohort_fail(co, index, scan))
        co = copy.deepcopy(cohort)
        co["members"][0]["expected_raw_rows"] = 7
        results["E_expected_rows_mismatch_detected"] = bool(
            cohort_fail(co, index, scan))
        sc = copy.deepcopy(scan)
        sc["_cohort_rows"]["aaa"]["type7"]["2020-01-04"] *= 1.5
        results["E_perturbed_close_changes_chain"] = bool(
            cohort_fail(cohort, index, sc))
        sc = copy.deepcopy(scan)
        sc["_cohort_rows"]["aaa"]["type7"].pop("2020-01-05")
        results["E_missing_type7_day_detected"] = bool(
            cohort_fail(cohort, index, sc))

        # F -- gzip layer: the instrument must see corruption.
        with open(gz, "rb") as fh:
            blob = fh.read()
        corrupt = os.path.join(tmp, "corrupt.ndjson.gz")
        mid = len(blob) // 2
        with open(corrupt, "wb") as fh:
            fh.write(blob[:mid] + bytes([blob[mid] ^ 0xFF]) + blob[mid + 1:])
        try:
            m.scan_bars(corrupt, {"aaa"}, s2k)
            results["F_corrupt_gzip_detected"] = False
        except Exception:
            results["F_corrupt_gzip_detected"] = True
        trunc = os.path.join(tmp, "trunc.ndjson.gz")
        with open(trunc, "wb") as fh:
            fh.write(blob[:len(blob) - 12])
        try:
            m.scan_bars(trunc, {"aaa"}, s2k)
            results["F_truncated_gzip_detected"] = False
        except Exception:
            results["F_truncated_gzip_detected"] = True
        results["F_intact_gzip_scans"] = m.scan_bars(
            gz, {"aaa"}, s2k)["bars_total"] == len(rows)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    failed = sorted(k for k, v in results.items() if not v)
    for k in sorted(results):
        print("%-4s %s" % ("OK" if results[k] else "FAIL", k))
    print("controls=%d passed=%d failed=%d"
          % (len(results), len(results) - len(failed), len(failed)))
    if failed:
        print("FAILED CONTROLS:", ", ".join(failed))
        for k in failed:
            if diagnostics.get(k):
                print("  %s -> %r" % (k, diagnostics[k]))
        return 1
    print("ALL CONTROLS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())