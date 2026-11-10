#!/usr/bin/env python3
"""Tests for stage05_symbol_ledger - one row per price_history symbol.

Every test builds a throw-away SQLite file so the real Seed DB is never
touched. The first case is the brief's case; the rest pin the rulings that the
brief alone does not cover: the key join with spelling aliases, the 82
duplicate effective dates, the 1,468 symbols without an instruments row, the
duplicate instruments keys, the five/six mission statuses, the halted vs stale
split, the reference full-window rule, the official-positive-only rule, and
the history_validity reconciliation.

The CLI failure paths are negative controls: they run in a captured stream,
assert the ``SYMBOL LEDGER FAIL`` message and the non-zero return code, and
report the capture as expected. A leaking ``FAIL`` line can never reach a
green run, and a swallowed assertion cannot go unnoticed because every case
is reported by name and the process exits non-zero on the first failure.
"""
import contextlib
import csv
import datetime
import io
import json
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import stage05_symbol_ledger as S  # noqa: E402

RULES_PATH = os.path.join(ROOT, "dev", "phase49_status_rules.json")

SPEC_FIELDS = [
    "symbol", "ins_code", "asset_id", "instrument_status", "first_date",
    "last_date", "rows", "trading_sessions", "source_coverage",
    "raw_ohlc_valid", "adjusted_available", "evidence_tier", "event_coverage",
    "ref_coverage", "stale_status", "gaps", "anomalies",
    "verification_method", "final_status", "remaining_blocker",
]

PH_DDL = ("CREATE TABLE price_history(symbol TEXT,date TEXT,open REAL,"
          "high REAL,low REAL,close REAL,volume REAL,last REAL,value REAL,"
          "src TEXT)")
INS_DDL = ("CREATE TABLE instruments(ins_code TEXT,l_val18 TEXT,l_val30 TEXT,"
           "paper_type INTEGER,isin TEXT,updated_at TEXT)")
STATE_DDL = ("CREATE TABLE instrument_state(ins_code TEXT,d_even INTEGER,"
             "c_etaval_title TEXT)")
HV_DDL = ("CREATE TABLE history_validity(symbol TEXT,status TEXT,"
          "factor_steps INTEGER,factor_verified INTEGER,"
          "factor_reconstructed INTEGER,factor_unverified INTEGER)")


def new_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    con.execute(PH_DDL)
    con.execute(INS_DDL)
    con.execute(STATE_DDL)
    con.execute(HV_DDL)
    return con, path


def drop(con, path):
    con.close()
    try:
        os.unlink(path)
    except OSError:
        pass


def add_prices(con, symbol, dates, close=10.0, volume=1.0, src="legacy-unknown"):
    for d in dates:
        con.execute(
            "INSERT INTO price_history VALUES(?,?,?,?,?,?,?,?,NULL,?)",
            (symbol, d, close, close, close, close, volume, close, src))
    con.commit()


def add_instrument(con, ins_code, name, isin=None, paper_type=1,
                   updated_at="2026-01-01"):
    con.execute("INSERT INTO instruments VALUES(?,?,?,?,?,?)",
                (ins_code, name, name, paper_type, isin, updated_at))
    con.commit()


def step(symbol, date, status, ratio=0.9, tier="I1"):
    return {"symbol": symbol, "effective_date": date, "final_status": status,
            "ratio": ratio, "evidence_tier": tier, "ins_code": "",
            "asset_id": ""}


def full_ref(first="2026-01-01", last="2026-01-02", changes=None):
    return {"type0": {"first": first, "last": last, "n": 2},
            "type7": {"first": first, "last": last, "n": 2},
            "factor_changes": list(changes or [])}


def test_brief_case():
    con, path = new_db()
    try:
        add_instrument(con, "1", "الف")
        add_prices(con, "الف", ["2026-01-01", "2026-01-02", "2026-01-04"])
        row = S.symbol_row(
            con, "الف", steps={}, reference={},
            calendar={"2026-01-01", "2026-01-02", "2026-01-03",
                      "2026-01-04"})
        assert row["symbol"] == "الف" and row["ins_code"] == "1", row
        assert row["rows"] == 3 and row["gaps"] == 1, row
        assert row["final_status"] in ("INSUFFICIENT_EVIDENCE",
                                       "VERIFIED_NO_APPLICABLE_EVENT"), row
        assert row["stale_status"] == "fresh", row
        assert row["key"] == S.key("الف"), row
    finally:
        drop(con, path)


def test_fields_carry_raw_symbol_and_isin():
    assert set(SPEC_FIELDS) <= set(S.FIELDS), set(SPEC_FIELDS) - set(S.FIELDS)
    for extra in ("key", "isin", "identity_status", "validity_status",
                  "validity_factor_steps", "validity_delta", "latest_session",
                  "sessions_behind"):
        assert extra in S.FIELDS, extra
    assert set(S.MISSION_STATUSES) == {
        "VERIFIED_WITH_EVENTS", "VERIFIED_NO_APPLICABLE_EVENT",
        "RECONSTRUCTED_VERIFIED", "CONFLICT", "BLOCKED_SOURCE",
        "INSUFFICIENT_EVIDENCE"}
    frozen = json.load(open(RULES_PATH, encoding="utf-8"))
    assert set(frozen["symbol_status_precedence"]) == set(S.MISSION_STATUSES)


def test_step_status_rollup():
    con, path = new_db()
    try:
        add_instrument(con, "1", "الف")
        add_prices(con, "الف", ["2026-01-01", "2026-01-02"])
        cal = {"2026-01-01", "2026-01-02"}
        r = S.symbol_row(con, "الف", [
            step("الف", "2020-01-01", "VERIFIED_OFFICIAL", tier="O1"),
            step("الف", "2020-06-01", "VERIFIED_REFERENCE", tier="R1"),
        ], {}, cal)
        assert r["final_status"] == "VERIFIED_WITH_EVENTS", r
        assert r["factor_steps"] == 2 and r["factor_verified"] == 2, r
        assert r["evidence_tier"] == "O1+R1", r
        assert r["remaining_blocker"] == "", r

        r = S.symbol_row(con, "الف", [
            step("الف", "2020-01-01", "RECONSTRUCTED_AUDITED"),
            step("الف", "2020-06-01", "VERIFIED_OFFICIAL", tier="O1"),
        ], {}, cal)
        assert r["final_status"] == "RECONSTRUCTED_VERIFIED", r
        assert "NO_INDEPENDENT_EVIDENCE" in r["remaining_blocker"], r

        r = S.symbol_row(con, "الف", [
            step("الف", "2020-01-01", "PARTIAL_OFFICIAL", tier="O1"),
            step("الف", "2020-06-01", "VERIFIED_OFFICIAL", tier="O1"),
        ], {}, cal)
        assert r["final_status"] == "INSUFFICIENT_EVIDENCE", r
        assert "PARTIAL_OFFICIAL" in r["remaining_blocker"], r

        r = S.symbol_row(con, "الف", [
            step("الف", "2020-01-01", "CONFLICT_RATIO", ratio=0.5, tier="O1"),
            step("الف", "2020-06-01", "VERIFIED_OFFICIAL", tier="O1"),
        ], {}, cal)
        assert r["final_status"] == "CONFLICT", r
        assert "STEP_CONFLICT" in r["remaining_blocker"], r
        assert r["factor_conflict"] == 1 and r["factor_verified"] == 1, r

        r = S.symbol_row(con, "الف", [
            step("الف", "2020-01-01", "INVALID_DROPPED"),
        ], {}, cal)
        assert r["final_status"] == "INSUFFICIENT_EVIDENCE", r
        assert r["factor_steps"] == 0 and r["factor_invalid_dropped"] == 1, r
        assert "ONLY_INVALID_DROPPED_STEPS" in r["remaining_blocker"], r
    finally:
        drop(con, path)


def test_reference_window_rule():
    con, path = new_db()
    try:
        add_instrument(con, "1", "الف")
        add_prices(con, "الف", ["2026-01-01", "2026-01-02"])
        cal = {"2026-01-01", "2026-01-02"}

        r = S.symbol_row(con, "الف", [], {"الف": full_ref()}, cal)
        assert r["final_status"] == "VERIFIED_NO_APPLICABLE_EVENT", r
        assert r["ref_coverage"] == "full", r
        assert r["no_event_basis"] == "R1_FULL_WINDOW", r
        assert r["evidence_tier"] == "R1", r
        assert r["verification_method"] == "reference-window", r

        r = S.symbol_row(con, "الف", [],
                         {"الف": full_ref(first="2026-01-02")}, cal)
        assert r["final_status"] == "INSUFFICIENT_EVIDENCE", r
        assert r["ref_coverage"] == "partial", r
        assert "REFERENCE_WINDOW_PARTIAL" in r["remaining_blocker"], r

        r = S.symbol_row(con, "الف", [], {"الف": full_ref(
            changes=[{"date": "2026-01-02", "ratio_change": 0.5}])}, cal)
        assert r["final_status"] == "INSUFFICIENT_EVIDENCE", r
        assert "REFERENCE_FACTOR_CHANGES_WITHOUT_STEPS" in \
            r["remaining_blocker"], r

        r = S.symbol_row(con, "الف", [], {}, cal)
        assert r["final_status"] == "INSUFFICIENT_EVIDENCE", r
        assert "NO_REFERENCE_WINDOW" in r["remaining_blocker"], r
    finally:
        drop(con, path)


def test_identity_join_and_no_instruments():
    con, path = new_db()
    try:
        add_instrument(con, "1", "الف")
        add_prices(con, "الف", ["2026-01-01"])
        add_prices(con, "ب", ["2026-01-01"])
        cal = {"2026-01-01"}

        r = S.symbol_row(con, "ب", [], {}, cal)
        assert r["ins_code"] == "" and r["isin"] == "", r
        assert r["identity_status"] == "unresolved_no_instruments", r
        assert r["final_status"] == "INSUFFICIENT_EVIDENCE", r
        assert "SYMBOL_IDENTITY_MISMATCH" in r["remaining_blocker"], r

        r = S.symbol_row(con, "ب", [], {}, cal, asset_map={
            S.key("ب"): {"asset_id": 77, "ins_code": "88"}})
        assert r["identity_status"] == "resolved_capture_plan", r
        assert r["ins_code"] == "88" and r["asset_id"] == "77", r
    finally:
        drop(con, path)


def test_duplicate_instruments_key_uses_isin_preference():
    con, path = new_db()
    try:
        add_instrument(con, "1", "دوگانه072", isin=None, paper_type=2,
                       updated_at="2026-01-01")
        add_instrument(con, "2", "دوگانه072", isin="IRB3PH030791",
                       paper_type=1, updated_at="2026-02-01")
        add_prices(con, "دوگانه072", ["2026-01-01"])
        r = S.symbol_row(con, "دوگانه072", [], {}, {"2026-01-01"})
        assert r["ins_code"] == "2", r
        assert r["isin"] == "IRB3PH030791", r
        assert r["instrument_candidates"] == 2, r
        assert r["identity_status"] == "resolved_instruments_ambiguous", r
    finally:
        drop(con, path)


def test_alias_step_merge_and_validity_delta():
    con, path = new_db()
    try:
        add_instrument(con, "1", "تاپيكو")
        add_prices(con, "تاپيكو", ["2026-01-01"])
        con.execute("INSERT INTO history_validity(symbol,status,factor_steps,"
                    "factor_verified,factor_reconstructed,factor_unverified) "
                    "VALUES(?,?,?,?,?,?)",
                    ("تاپيكو", "reconstructed_verified", 1, 0, 1, 0))
        con.commit()
        steps = [
            step("تاپيكو", "2020-01-01", "RECONSTRUCTED_AUDITED", 0.9),
            step("تاپیکو", "2020-01-01", "INSUFFICIENT_EVIDENCE", 0.9),
            step("تاپیکو", "2019-01-01", "VERIFIED_OFFICIAL", 0.8,
                 tier="O1"),
        ]
        r = S.symbol_row(con, "تاپيكو", steps, {}, {"2026-01-01"})
        assert r["factor_steps"] == 2, r
        assert r["step_rows"] == 3, r
        assert r["alias_duplicate_dates"] == 1, r
        assert r["alias_only_steps"] == 1, r
        assert r["alias_ratio_conflicts"] == 0, r
        assert r["factor_reconstructed"] == 1, r
        assert r["factor_verified"] == 1, r
        assert r["final_status"] == "RECONSTRUCTED_VERIFIED", r
        assert r["validity_factor_steps"] == 1, r
        assert r["validity_delta"] == 1, r
        assert r["validity_match"] == "alias_steps_omitted", r
    finally:
        drop(con, path)


def test_alias_ratio_conflict_is_a_conflict():
    con, path = new_db()
    try:
        add_instrument(con, "1", "تاپيكو")
        add_prices(con, "تاپيكو", ["2026-01-01"])
        steps = [
            step("تاپيكو", "2021-01-01", "VERIFIED_OFFICIAL", 0.9, tier="O1"),
            step("تاپیکو", "2021-01-01", "VERIFIED_OFFICIAL", 0.8, tier="O1"),
        ]
        r = S.symbol_row(con, "تاپيكو", steps, {}, {"2026-01-01"})
        assert r["factor_steps"] == 1, r
        assert r["alias_duplicate_dates"] == 1, r
        assert r["alias_ratio_conflicts"] == 1, r
        assert r["factor_conflict"] == 1, r
        assert r["final_status"] == "CONFLICT", r
    finally:
        drop(con, path)


def test_stale_recent_halted():
    con, path = new_db()
    try:
        cal = []
        d = datetime.date(2026, 1, 1)
        while d <= datetime.date(2026, 1, 30):
            cal.append(d.isoformat())
            d += datetime.timedelta(days=1)
        for code, name in (("1", "الف"), ("2", "ب"), ("3", "و"),
                           ("4", "ز"), ("5", "ح")):
            add_instrument(con, code, name)
        add_prices(con, "الف", ["2026-01-30"])
        add_prices(con, "ب", ["2026-01-28"])
        add_prices(con, "و", ["2025-12-01"])
        add_prices(con, "ز", ["2025-12-01"])
        add_prices(con, "ح", ["2026-01-30"])
        con.execute("INSERT INTO instrument_state VALUES(?,?,?)",
                    ("4", 20251231, "ممنوع-متوقف"))
        con.execute("INSERT INTO instrument_state VALUES(?,?,?)",
                    ("5", 20251231, "ممنوع"))
        con.commit()

        r = S.symbol_row(con, "الف", [], {}, cal)
        assert (r["stale_status"], r["sessions_behind"]) == ("fresh", 0), r
        r = S.symbol_row(con, "ب", [], {}, cal)
        assert (r["stale_status"], r["sessions_behind"]) == ("recent", 2), r
        r = S.symbol_row(con, "و", [], {}, cal)
        assert r["stale_status"] == "stale", r
        assert r["stale_basis"] == "calendar", r
        r = S.symbol_row(con, "ز", [], {}, cal)
        assert r["stale_status"] == "halted", r
        assert r["stale_basis"] == "instrument_state", r
        assert r["instrument_status"] == "ممنوع-متوقف", r
        assert r["instrument_state_date"] == "2025-12-31", r
        r = S.symbol_row(con, "ح", [], {}, cal)
        assert r["stale_status"] == "fresh", r
        assert r["stale_basis"] == "calendar_over_state", r
    finally:
        drop(con, path)


def test_official_positive_only_and_event_coverage():
    con, path = new_db()
    try:
        add_instrument(con, "1", "ط")
        add_prices(con, "ط", ["2026-01-01"])
        cal = {"2026-01-01"}
        official = {S.key("ط"): {
            "o1": 2, "o2": 1,
            "events": [{"date": "2026-01-01", "ratio": 0.5,
                        "table": "share_change_events"}]}}
        r = S.symbol_row(con, "ط", [], {}, cal, official_counts=official)
        assert r["final_status"] == "INSUFFICIENT_EVIDENCE", r
        assert r["official_o1"] == 2 and r["official_o2"] == 1, r
        assert r["official_o1_in_range"] == 1, r
        assert r["event_coverage"] == "none;O1=2;O2=1", r
        assert "OFFICIAL_EVENT_WITHOUT_STEP:1" in r["remaining_blocker"], r

        # A full reference window is still allowed to prove "no applicable
        # event" even when a non-price official event exists.
        ref = {"ط": full_ref(first="2026-01-01", last="2026-01-01")}
        r = S.symbol_row(con, "ط", [], ref, cal, official_counts=official)
        assert r["final_status"] == "VERIFIED_NO_APPLICABLE_EVENT", r
        assert r["no_event_basis"] == "R1_FULL_WINDOW", r

        # A verified step keeps the symbol verified; the official event does
        # not downgrade the step evidence.
        r = S.symbol_row(con, "ط", [
            step("ط", "2020-01-01", "VERIFIED_OFFICIAL", tier="O1")],
            {}, cal, official_counts=official)
        assert r["final_status"] == "VERIFIED_WITH_EVENTS", r
        assert r["remaining_blocker"] == "", r
    finally:
        drop(con, path)


def run_cli(args):
    """Invoke the CLI with both streams captured; ``(rc, stdout, stderr)``."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = S.main(list(args))
    return rc, out.getvalue(), err.getvalue()


def test_cli_end_to_end():
    con, db_path = new_db()
    work = tempfile.mkdtemp(prefix="stage05_")
    cwd = os.getcwd()
    try:
        add_instrument(con, "1", "الف")
        add_prices(con, "الف", ["2026-01-01", "2026-01-02"])
        add_prices(con, "ب", ["2026-01-01"])
        con.close()

        steps_path = os.path.join(work, "steps.csv")
        with open(steps_path, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=[
                "symbol", "ins_code", "asset_id", "effective_date", "action",
                "ratio", "prod_ratio", "ref_ratio", "cum_factor_after",
                "provenance", "method", "evidence_tier", "evidence_ref",
                "comparison_result", "discrepancy_cause", "final_status",
                "risk_score", "notes"])
            w.writeheader()
            w.writerow({"symbol": "الف", "ins_code": "1", "asset_id": "7",
                        "effective_date": "2020-01-01", "action": "step",
                        "ratio": "0.9", "prod_ratio": "0.9",
                        "ref_ratio": "0.9", "cum_factor_after": "0.9",
                        "provenance": "pack", "method": "m",
                        "evidence_tier": "O1", "evidence_ref": "",
                        "comparison_result": "MATCH",
                        "discrepancy_cause": "",
                        "final_status": "VERIFIED_OFFICIAL",
                        "risk_score": "0", "notes": ""})
        ref_path = os.path.join(work, "ref.json")
        json.dump({}, open(ref_path, "w", encoding="utf-8"))
        asset_path = os.path.join(work, "asset.json")
        json.dump([{"symbol": "الف", "asset_id": 427, "ins_code": "1",
                    "source": "test", "basis": "real_close"}],
                  open(asset_path, "w", encoding="utf-8"))
        out_path = os.path.join(work, "out.csv")
        counts_path = os.path.join(work, "counts.json")
        manifest_path = os.path.join(work, "manifest.json")
        args = ["--db", db_path, "--steps", steps_path,
                "--reference", ref_path, "--asset-map", asset_path,
                "--out", out_path, "--counts", counts_path]
        rc, out, err = run_cli(
            args + ["--manifest", manifest_path, "--expect-symbols", "2"])
        assert rc == 0, (rc, err)
        assert "symbol ledger: 2 rows" in out, out
        with open(out_path, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 2, len(rows)
        assert rows[0]["symbol"] == "الف" and rows[0]["asset_id"] == "427"
        assert "key" in rows[0] and "isin" in rows[0], rows[0].keys()
        counts = json.load(open(counts_path, encoding="utf-8"))
        assert counts["rows"] == 2, counts
        assert sum(counts["by_final_status"].values()) == 2, counts
        manifest = json.load(open(manifest_path, encoding="utf-8"))
        assert manifest["stage"] == "stage05_symbol_ledger", manifest

        # Negative control: an under-sized universe must fail closed. The
        # message is asserted here and never leaks into the green output.
        rc, out, err = run_cli(
            args + ["--manifest", "", "--expect-symbols", "3"])
        assert rc == 2, (rc, out, err)
        assert out == "", out
        assert err.startswith(
            "SYMBOL LEDGER FAIL: expected 3 symbols, found 2"), err
        print("negative control (expected): --expect-symbols 3 rejected "
              "with rc=2 and the SYMBOL LEDGER FAIL message", flush=True)
    finally:
        os.chdir(cwd)
        try:
            con.close()
        except Exception:
            pass
        drop(sqlite3.connect(db_path), db_path)
        for name in os.listdir(work):
            try:
                os.unlink(os.path.join(work, name))
            except OSError:
                pass
        os.rmdir(work)


def test_missing_input_fails_closed():
    """A missing required input blocks the run instead of fabricating rows."""
    con, db_path = new_db()
    work = tempfile.mkdtemp(prefix="stage05_")
    cwd = os.getcwd()
    try:
        add_instrument(con, "1", "الف")
        add_prices(con, "الف", ["2026-01-01"])
        con.close()
        counts_path = os.path.join(work, "counts.json")
        rc, out, err = run_cli([
            "--db", db_path,
            "--steps", os.path.join(work, "does-not-exist.csv"),
            "--out", os.path.join(work, "out.csv"),
            "--counts", counts_path, "--manifest", ""])
        assert rc == 2, (rc, out, err)
        assert out == "", out
        assert err.startswith("SYMBOL LEDGER FAIL:"), err
        assert not os.path.exists(counts_path), counts_path
        print("negative control (expected): missing steps input rejected "
              "with rc=2 and no counts written", flush=True)
    finally:
        os.chdir(cwd)
        try:
            con.close()
        except Exception:
            pass
        drop(sqlite3.connect(db_path), db_path)
        for name in os.listdir(work):
            try:
                os.unlink(os.path.join(work, name))
            except OSError:
                pass
        os.rmdir(work)


TESTS = [
    test_brief_case,
    test_fields_carry_raw_symbol_and_isin,
    test_step_status_rollup,
    test_reference_window_rule,
    test_identity_join_and_no_instruments,
    test_duplicate_instruments_key_uses_isin_preference,
    test_alias_step_merge_and_validity_delta,
    test_alias_ratio_conflict_is_a_conflict,
    test_stale_recent_halted,
    test_official_positive_only_and_event_coverage,
    test_cli_end_to_end,
    test_missing_input_fails_closed,
]


def main():
    for test in TESTS:
        try:
            test()
        except Exception as exc:  # report the case, never exit green
            print("SYMBOL LEDGER TESTS FAIL: %s: %s"
                  % (test.__name__, exc), file=sys.stderr, flush=True)
            return 1
        print("ok - %s" % test.__name__, flush=True)
    print("SYMBOL LEDGER TESTS OK (%d cases)" % len(TESTS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
