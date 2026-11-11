#!/usr/bin/env python3
"""Negative controls for stage07_cohort_candles.

Stage07 decides whether the new 30-symbol group passes candle-level acceptance.
These controls prove that verdict is earned, on a small synthetic capture whose
correct answer is known independently:

A. positive control -- a two-symbol fixture with one real split ingests, builds
   with the shipped binary and comes back PASS with constant volume, so a
   PARTIAL on the real cohort means something;
B. quarantine -- a bar on the capture day is excluded and counted, a bar before
   it is kept;
C. a perturbed adjusted close must be detected as a close difference;
D. a perturbed volume must be detected as a volume-constancy failure;
E. an event with no pack witness stays corporate_action_unclassified, and one
   with a matching pack step is classified -- proving the classifier is neither
   always-guessing nor always-blind;
F. a broken input SHA pin aborts before any working DB is created;
G. a type7 series that violates the anchor invariant is detected as a close
   difference -- the same failure the first version of fixture A produced.

Run: PYTHONIOENCODING=utf-8 python _audit/phase49-3/test_stage07_controls.py
Writes only to a temporary directory, removed on exit. No repo file is touched,
no real capture is read, and neither red-line DB is opened.
"""

import copy
import gzip
import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "dev"))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, rel.replace("/", os.sep)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def bar(sym, typ, day, close, volume=1000):
    return {"symbol": sym, "asset_id": 1, "type": typ,
            "adjust": "raw" if typ == "type0" else "adjusted",
            "resolution": "D", "date": day, "open": close, "high": close,
            "low": close, "close": close, "volume": volume,
            "basis": "real_close"}


def fixture(capture_day="2020-01-07", break_anchor=False):
    """A 2:1 split on 2020-01-03, plus a capture-day bar to quarantine.

    The type7 close on the last day must equal the raw close: chainFactors
    anchors factor=1 on the largest date (canonical.go:1484), so the stored
    q_after/q_before ratios telescope to 1/q(t) only when q(last)==1. The real
    cohort satisfies this on 30/30 symbols. break_anchor violates it on purpose
    for control G.
    """
    days = ["2020-01-0%d" % i for i in range(1, 7)]
    raw_close = [100.0, 100.0, 50.0, 50.0, 50.0, 50.0]
    adj_close = [25.0] * 6 if break_anchor else [50.0] * 6
    raw, adjm, ohlc = {}, {}, {}
    quarantined = {}
    for sym in ("AAA", "BBB"):
        raw[sym], adjm[sym], ohlc[sym] = {}, {}, {}
        for i, d in enumerate(days):
            raw[sym][d] = bar(sym, "type0", d, raw_close[i])
            adjm[sym][d] = adj_close[i]
            ohlc[sym][d] = bar(sym, "type7", d, adj_close[i])
        qd = capture_day
        quarantined["type0"] = quarantined.get("type0", 0) + 1
        quarantined["type7"] = quarantined.get("type7", 0) + 1
        raw[sym][qd] = bar(sym, "type0", qd, raw_close[-1])
        adjm[sym][qd] = adj_close[-1]
        ohlc[sym][qd] = bar(sym, "type7", qd, adj_close[-1])
    return {"raw": raw, "adj": adjm, "adj_ohlc": ohlc,
            "quarantined": quarantined, "non_daily_skipped": {},
            "cohort_rows_scanned": 2 * (len(days) + 1) * 2}


def stripped(ex, capture_day):
    """Apply the same quarantine rule the extractor uses, for the fixture."""
    out = copy.deepcopy(ex)
    for sym in list(out["raw"]):
        for d in list(out["raw"][sym]):
            if d >= capture_day:
                del out["raw"][sym][d]
        for d in list(out["adj"][sym]):
            if d >= capture_day:
                del out["adj"][sym][d]
                del out["adj_ohlc"][sym][d]
    return out


def main():
    m = _load("s7", "_audit/phase49-3/stage07_cohort_candles.py")
    bin_path = os.path.join(ROOT, m.BIN_REL.replace("/", os.sep))
    if not os.path.exists(bin_path):
        print("FATAL: build %s first" % m.BIN_REL)
        return 2
    tmp = tempfile.mkdtemp(prefix="phase49-3-s7-controls-")
    results = {}
    try:
        cohort = {"members": [{"key": "aaa"}, {"key": "bbb"}]}
        cap_sha = hashlib.sha256(b"fixture").hexdigest()
        now = "2020-01-08T00:00:00Z"
        ex_full = fixture()
        ex = stripped(ex_full, "2020-01-07")

        # A -- positive control through the real binary.
        db = os.path.join(tmp, "a.db")
        rev, counts = m.ingest(db, ex, cohort, {}, cap_sha, "ctl-a", now, now)
        build = m.run_build(db, bin_path)
        par = m.parity(db, ex)
        results["A_build_ran"] = build["symbols"] == 2
        results["A_all_pass"] = all(r["status"] == "PASS"
                                    for r in par["per_symbol"])
        results["A_close_exact"] = par["close_diff_rows"] == 0
        results["A_volume_constant"] = par["volume_mismatch_rows"] == 0
        results["A_rows_match"] = par["rows_total"] == 12
        results["A_factor_step_found"] = counts["adjustment_factors"] == 2
        # The fixture must itself satisfy the invariant the engine anchors on,
        # otherwise A measures a broken fixture instead of a working engine.
        results["A_anchor_invariant"] = all(
            ex["raw"][s][max(ex["raw"][s])]["close"] == ex["adj"][s][max(ex["adj"][s])]
            for s in ex["raw"])
        results["A_revision_stable"] = rev == m.ingest(
            os.path.join(tmp, "a2.db"), ex, cohort, {}, cap_sha,
            "ctl-a", now, now)[0]

        # B -- quarantine rule.
        results["B_capture_day_excluded"] = all(
            "2020-01-07" not in ex["raw"][s] for s in ex["raw"])
        results["B_prior_day_kept"] = all(
            "2020-01-06" in ex["raw"][s] for s in ex["raw"])
        results["B_quarantine_counted"] = ex_full["quarantined"] == {
            "type0": 2, "type7": 2}
        # B -- the real extractor, on a tiny gz it can actually read.
        gz = os.path.join(tmp, "bars.ndjson.gz")
        lines = []
        for sym in ("AAA", "BBB"):
            for d in ("2020-01-06", "2020-01-07"):
                lines.append(bar(sym, "type0", d, 100.0))
                lines.append(bar(sym, "type7", d, 25.0))
            w = bar(sym, "type0", "2020-01-03", 100.0)
            w["resolution"] = "W"
            lines.append(w)
        with gzip.open(gz, "wb") as fh:
            for r in lines:
                fh.write((json.dumps(r, ensure_ascii=False) + "\n").encode("utf-8"))
        got = m.extract_cohort(gz, {"aaa", "bbb"},
                               {"AAA": "aaa", "BBB": "bbb"}, "2020-01-07")
        results["B_extractor_excludes_capture_day"] = all(
            "2020-01-07" not in got["raw"][s] for s in got["raw"])
        results["B_extractor_keeps_prior_day"] = all(
            "2020-01-06" in got["raw"][s] for s in got["raw"])
        results["B_extractor_counts_quarantine"] = got["quarantined"] == {
            "type0": 2, "type7": 2}
        results["B_extractor_skips_non_daily"] = got["non_daily_skipped"] == {"W": 2}
        results["B_extractor_scanned_all"] = got["cohort_rows_scanned"] == len(lines)

        # C -- a perturbed close must be seen.
        db_c = os.path.join(tmp, "c.db")
        shutil.copyfile(db, db_c)
        con = sqlite3.connect(db_c)
        con.execute("UPDATE adjusted_candles SET close=close*1.01 "
                    "WHERE symbol='AAA' AND date='2020-01-02'")
        con.commit()
        con.close()
        pc = m.parity(db_c, ex)
        results["C_perturbed_close_detected"] = pc["close_diff_rows"] == 1
        results["C_status_downgraded"] = any(
            r["status"] == "PARTIAL" for r in pc["per_symbol"])

        # D -- a perturbed volume must be seen.
        db_d = os.path.join(tmp, "d.db")
        shutil.copyfile(db, db_d)
        con = sqlite3.connect(db_d)
        con.execute("UPDATE adjusted_candles SET volume=volume+1 "
                    "WHERE symbol='BBB' AND date='2020-01-04'")
        con.commit()
        con.close()
        pd = m.parity(db_d, ex)
        results["D_perturbed_volume_detected"] = pd["volume_mismatch_rows"] == 1
        results["D_close_still_exact"] = pd["close_diff_rows"] == 0

        # E -- classification is evidence-based, not guessed.
        ch = {"date": "2020-01-03", "ratio": 0.5, "q_before": 2.0, "q_after": 1.0}
        kind_none, link_none, _, _ = m.ING.classify(
            "AAA", ch, ex["raw"]["AAA"], [], [], [])
        results["E_no_witness_stays_unclassified"] = (
            kind_none == "corporate_action_unclassified" and not link_none)
        step = {"date": "2020-01-03", "ratio": 0.5, "event_sig": "share",
                "class": "capital_increase"}
        kind_hit, link_hit, _, _ = m.ING.classify(
            "AAA", ch, ex["raw"]["AAA"], [], [], [step])
        results["E_pack_witness_classifies"] = (
            kind_hit == "capital_increase" and link_hit.get("pack") == step)
        far = dict(step, date="2020-06-01")
        kind_far, _, _, _ = m.ING.classify(
            "AAA", ch, ex["raw"]["AAA"], [], [], [far])
        results["E_out_of_window_not_matched"] = (
            kind_far == "corporate_action_unclassified")
        wrong = dict(step, ratio=3.0)
        kind_wrong, _, _, _ = m.ING.classify(
            "AAA", ch, ex["raw"]["AAA"], [], [], [wrong])
        results["E_wrong_ratio_not_matched"] = (
            kind_wrong == "corporate_action_unclassified")

        # F -- a broken pin aborts before any DB is created.
        target = os.path.join(ROOT, m.DB_REL.replace("/", os.sep))
        existed = os.path.exists(target)
        real_sha = m.S6.sha256_file
        m.S6.sha256_file = lambda p: "0" * 64
        try:
            m.main()
            results["F_broken_pin_aborts"] = False
        except SystemExit as exc:
            results["F_broken_pin_aborts"] = (
                exc.code != 0 and "pinned input" in str(exc.code))
        finally:
            m.S6.sha256_file = real_sha
        results["F_no_db_created"] = (os.path.exists(target) == existed)

        # G -- the anchor invariant is load-bearing: break it and every close
        # must be flagged. Known answer: raw 100,100,50,50,50,50 against a flat
        # type7 of 25 gives q(last)=2, so all 6 rows per symbol differ.
        ex_g = stripped(fixture(break_anchor=True), "2020-01-07")
        db_g = os.path.join(tmp, "g.db")
        m.ingest(db_g, ex_g, cohort, {}, cap_sha, "ctl-g", now, now)
        build_g = m.run_build(db_g, bin_path)
        pg = m.parity(db_g, ex_g)
        results["G_anchor_violation_detected"] = pg["close_diff_rows"] == 12
        results["G_status_downgraded"] = all(
            r["status"] == "PARTIAL" for r in pg["per_symbol"])
        results["G_engine_flags_mismatch"] = build_g["mismatch_rows"] == 12
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    failed = sorted(k for k, v in results.items() if not v)
    for k in sorted(results):
        print("%-4s %s" % ("OK" if results[k] else "FAIL", k))
    print("controls=%d passed=%d failed=%d"
          % (len(results), len(results) - len(failed), len(failed)))
    if failed:
        print("FAILED CONTROLS:", ", ".join(failed))
        return 1
    print("ALL CONTROLS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())