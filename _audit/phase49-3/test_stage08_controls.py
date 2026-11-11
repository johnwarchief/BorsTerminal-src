#!/usr/bin/env python3
"""Controls for stage08_runtime_readpath.

Stage08 decides whether the product read path serves the captured reference and
whether a covered zero-event symbol really loses the measured chain. These
controls prove that verdict on a synthetic DB whose correct answer is known:

A. positive -- a symbol with one real split is served over HTTP from
   reference_raw, takes the measured path, and its adjusted close matches type7
   exactly. The fixture DB is never passed through candlebuild, so this also
   proves adjusted_candles is not the Runtime read path.
B. zero-event -- a symbol whose raw and type7 closes are identical (q==1 on every
   day, therefore no factor rows) is still served its full reference history, but
   does NOT take the measured path. This is the پادا finding on a known fixture.
C. negative -- perturbing one reference_adjusted close in the DB must surface as
   an adjusted-close difference through the live API.
D. negative -- perturbing the served volume and raw close must surface as a
   volume mismatch and a close difference through the live API, with the oracle
   pinned to the original reference so both sides cannot move together.
E. the comparison gate itself downgrades a payload that deviates, and a payload
   with no reference provenance is not called PASS.

Only the PIDs this script starts are terminated. Nothing outside a temporary
directory is written; neither red-line DB is opened.

Run: PYTHONIOENCODING=utf-8 python _audit/phase49-3/test_stage08_controls.py
"""

import contextlib
import importlib.util
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "dev"))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, rel.replace("/", os.sep)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def bar(sym, day, close, volume=1000):
    return {"symbol": sym, "asset_id": 1, "type": "type0", "adjust": "raw",
            "resolution": "D", "date": day, "open": close, "high": close,
            "low": close, "close": close, "volume": volume,
            "basis": "real_close"}


def extraction():
    """AAA: 2:1 split on 2020-01-03, type7 flat at 50, q(last)==1.
    ZZZ: raw == type7 == 70 on every day, so q==1 throughout and no event."""
    days = ["2020-01-0%d" % i for i in range(1, 7)]
    raw, adj, ohlc = {}, {}, {}
    spec = {"AAA": ([100.0, 100.0, 50.0, 50.0, 50.0, 50.0], [50.0] * 6),
            "ZZZ": ([70.0] * 6, [70.0] * 6)}
    for sym, (rc, ac) in spec.items():
        raw[sym], adj[sym], ohlc[sym] = {}, {}, {}
        for i, d in enumerate(days):
            raw[sym][d] = bar(sym, d, rc[i])
            adj[sym][d] = ac[i]
            t7 = bar(sym, d, ac[i])
            t7["type"] = "type7"
            t7["adjust"] = "adjusted"
            ohlc[sym][d] = t7
    return {"raw": raw, "adj": adj, "adj_ohlc": ohlc, "quarantined": {},
            "non_daily_skipped": {}, "cohort_rows_scanned": 24}


@contextlib.contextmanager
def serve(m, db_path, tmp, port):
    """Start the shipped binary on a throwaway copy; terminate only that PID."""
    run = os.path.join(tmp, "run-%d" % port)
    os.makedirs(run, exist_ok=True)
    shutil.copy2(db_path, os.path.join(run, "market.db"))
    log = open(os.path.join(tmp, "server-%d.log" % port), "ab")
    m.PORT = port
    env = dict(os.environ, BORS_CORRECTIONS_DIR=os.path.join(
        ROOT, m.PACK_REL.replace("/", os.sep)))
    proc = subprocess.Popen(
        [os.path.join(ROOT, m.BIN_REL.replace("/", os.sep)),
         "--port", str(port), "--db-dir", run,
         "--no-shell", "--no-loops", "--server-only"],
        env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        tok = m.wait_server(os.path.join(run, "oc", "runtime", "api_token"),
                            "AAA", timeout=300)
        yield lambda sym: m.api(
            "/api/chart-db/" + urllib.parse.quote(sym, safe=""), tok)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=30)
        log.close()


def measure(m, db_path, query):
    con = sqlite3.connect("file:%s?mode=ro" % db_path.replace(os.sep, "/"), uri=True)
    frows = {s: n for s, n in con.execute(
        "SELECT symbol, COUNT(*) FROM adjustment_factors GROUP BY symbol")}
    out = {}
    for sym in ("AAA", "ZZZ"):
        raw, adj = m.reference(con, sym)
        out[sym] = m.compare(sym, query(sym), raw, adj, frows.get(sym, 0))
    con.close()
    return out


def main():
    m = _load("s8", "_audit/phase49-3/stage08_runtime_readpath.py")
    s7 = _load("s7", "_audit/phase49-3/stage07_cohort_candles.py")
    bin_path = os.path.join(ROOT, m.BIN_REL.replace("/", os.sep))
    if not os.path.exists(bin_path):
        print("FATAL: build %s first" % m.BIN_REL)
        return 2
    tmp = tempfile.mkdtemp(prefix="phase49-3-s8-controls-")
    results = {}
    diag = {}
    try:
        ex = extraction()
        cohort = {"members": [{"key": "aaa"}, {"key": "zzz"}]}
        db = os.path.join(tmp, "fixture.db")
        _rev, counts = s7.ingest(db, ex, cohort, {}, "0" * 64, "ctl",
                                 "2020-01-08T00:00:00Z", "2020-01-08T00:00:00Z")
        results["fixture_aaa_has_event"] = counts["adjustment_factors"] == 1
        con = sqlite3.connect(db)
        tables = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        built = con.execute("SELECT COUNT(*) FROM adjusted_candles").fetchone()[0] \
            if "adjusted_candles" in tables else 0
        con.close()
        results["fixture_never_built"] = built == 0

        with serve(m, db, tmp, 18094) as query:
            got = measure(m, db, query)
        a, z = got["AAA"], got["ZZZ"]
        diag["AAA"] = {k: a.get(k) for k in
                       ("status", "adjust_source", "candles", "reference_rows",
                        "adjusted_close_diff_rows", "adjusted_close_max_rel",
                        "raw_field_diff_rows", "volume_mismatch_rows",
                        "provenance_not_reference")}
        diag["ZZZ"] = {k: z.get(k) for k in
                       ("status", "adjust_source", "candles", "reference_rows",
                        "factor_rows_in_db", "measured_path", "factor_min",
                        "factor_max", "adjusted_close_diff_rows")}
        results["A_http_success"] = a["http_status"] == "success"
        results["A_serves_full_reference"] = (
            a["candles"] == 6 and a["reference_rows"] == 6)
        results["A_reference_provenance"] = not a["provenance_not_reference"]
        results["A_raw_fields_exact"] = not any(a["raw_field_diff_rows"].values())
        results["A_volume_constant"] = a["volume_mismatch_rows"] == 0
        results["A_measured_path"] = a["measured_path"] is True
        results["A_adjusted_close_exact"] = a["adjusted_close_diff_rows"] == 0
        results["A_status_pass"] = a["status"] == "PASS"
        results["A_no_adjusted_candles_needed"] = built == 0 and a["candles"] == 6

        results["B_zero_event_has_no_factor_rows"] = z["factor_rows_in_db"] == 0
        results["B_zero_event_still_served"] = (
            z["candles"] == 6 and z["reference_rows"] == 6)
        results["B_zero_event_reference_provenance"] = not z["provenance_not_reference"]
        results["B_zero_event_loses_measured_path"] = z["measured_path"] is False
        results["B_zero_event_not_called_pass"] = z["status"] == "PASS_RAW_ONLY"

        # C/D -- perturb the DB, restart, and prove the live API surfaces it.
        # Two directions of drift, each needing a different oracle pin:
        #   C: the reference target moved, the served value did not -> the
        #      oracle must read the perturbed DB.
        #   D: the served value moved, the reference did not -> the oracle must
        #      stay pinned to the original DB, otherwise both sides move
        #      together and the comparison is tautological.
        db_bad = os.path.join(tmp, "perturbed.db")
        shutil.copyfile(db, db_bad)
        con = sqlite3.connect(db_bad)
        con.execute("UPDATE reference_adjusted SET close=close*1.01 "
                    "WHERE symbol='AAA' AND date='2020-01-02'")
        con.execute("UPDATE reference_raw SET volume=volume+1 "
                    "WHERE symbol='ZZZ' AND date='2020-01-04'")
        con.execute("UPDATE reference_raw SET close=close*1.01 "
                    "WHERE symbol='ZZZ' AND date='2020-01-05'")
        con.commit()
        con.close()
        with serve(m, db_bad, tmp, 18095) as query:
            bad_target = measure(m, db_bad, query)
            bad_served = measure(m, db, query)
        ca = bad_target["AAA"]
        cz = bad_served["ZZZ"]
        diag["C"] = {k: ca.get(k) for k in
                     ("status", "adjusted_close_diff_rows", "adjusted_close_max_rel")}
        diag["D"] = {k: cz.get(k) for k in
                     ("status", "volume_mismatch_rows", "raw_field_diff_rows")}
        results["C_perturbed_close_detected"] = ca["adjusted_close_diff_rows"] == 1
        results["C_status_downgraded"] = ca["status"] == "PARTIAL"
        results["D_perturbed_volume_detected"] = cz["volume_mismatch_rows"] == 1
        results["D_perturbed_raw_close_detected"] = (
            cz["raw_field_diff_rows"].get("close") == 1)
        results["D_status_downgraded"] = cz["status"] == "PARTIAL"

        # E -- the gate itself, on a payload that never touched a server.
        con = sqlite3.connect(db)
        raw, adj = m.reference(con, "AAA")
        con.close()
        good = {"status": "success", "adjustSource": m.MEASURED_SRC,
                "candles": [dict(time=d, src=m.REFERENCE_SRC, **{
                    k: v[k] for k in ("open", "high", "low", "close", "volume")})
                    for d, v in sorted(raw.items())],
                "factors": [{"time": d, "factor": 0.5 if d < "2020-01-03" else 1.0}
                            for d in sorted(raw)]}
        base = m.compare("AAA", good, raw, adj, 1)
        results["E_synthetic_payload_passes"] = base["status"] == "PASS"
        wrong_src = dict(good, adjustSource="local-cache")
        results["E_non_measured_source_not_pass"] = (
            m.compare("AAA", wrong_src, raw, adj, 1)["status"] == "PASS_RAW_ONLY")
        bad_prov = dict(good, candles=[dict(c, src="legacy-unknown")
                                       for c in good["candles"]])
        results["E_foreign_provenance_rejected"] = (
            m.compare("AAA", bad_prov, raw, adj, 1)["status"] == "PARTIAL")
        short = dict(good, candles=good["candles"][:-1])
        results["E_truncated_history_rejected"] = (
            m.compare("AAA", short, raw, adj, 1)["status"] == "PARTIAL")
        err = m.compare("AAA", {"status": "error", "message": "boom"}, raw, adj, 1)
        results["E_error_payload_blocked"] = err["status"] == "BLOCKED"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    failed = sorted(k for k, v in results.items() if not v)
    for k in sorted(results):
        print("%-4s %s" % ("OK" if results[k] else "FAIL", k))
    print("controls=%d passed=%d failed=%d"
          % (len(results), len(results) - len(failed), len(failed)))
    if failed:
        print("FAILED CONTROLS:", ", ".join(failed))
        for k, v in diag.items():
            print("  diag %s: %s" % (k, v))
        return 1
    print("ALL CONTROLS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())