#!/usr/bin/env python3
"""Prove the backfill plan: six symbols, active freshness, explicit exclusions."""
import contextlib
import csv
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage08_backfill as S  # noqa: E402


def _read_symbols(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return [r["symbol"] for r in csv.DictReader(fh)]


def _read_excluded(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return {r["symbol"]: r["reason"] for r in csv.DictReader(fh)}


def _row(symbol, last_date="2026-11-08", asset_id="427",
         stale_status="stale", instrument_status="", sessions_behind="3"):
    return {"symbol": symbol, "last_date": last_date, "asset_id": asset_id,
            "stale_status": stale_status,
            "instrument_status": instrument_status,
            "sessions_behind": sessions_behind}


def _write_ledger(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(S.COLUMNS)
        for r in rows:
            w.writerow([r.get(c, "") for c in S.COLUMNS])


def _plan_rows():
    # The brief's case verbatim, extended with the fields the filters need.
    return [
        {"symbol": "شنفت", "last_date": "2026-10-11",
         "final_status": "INSUFFICIENT_EVIDENCE", "asset_id": "11",
         "stale_status": "stale", "instrument_status": "",
         "sessions_behind": "7"},
        {"symbol": "الف", "last_date": "2026-11-08",
         "final_status": "VERIFIED_WITH_EVENTS", "asset_id": "22",
         "stale_status": "recent", "instrument_status": "",
         "sessions_behind": "2"},
        {"symbol": "ب", "last_date": "2026-09-01",
         "final_status": "INSUFFICIENT_EVIDENCE", "asset_id": "33",
         "stale_status": "stale", "instrument_status": "",
         "sessions_behind": "9"},
    ]


def _brief_test():
    with tempfile.TemporaryDirectory() as tmp:
        six, fresh = S.plan(_plan_rows(), "2026-11-10", 30, tmp)
        assert six == ["شنفت"], six
        assert fresh == ["الف"], fresh
        assert _read_symbols(os.path.join(tmp, "symbols-six.csv")) == six
        assert _read_symbols(os.path.join(tmp, "symbols-freshness.csv")) == fresh
        excluded = _read_excluded(
            os.path.join(tmp, "symbols-freshness-excluded.csv"))
        assert excluded == {"ب": "OUT_OF_WINDOW"}, excluded


def _boundary_test():
    """Cutoff day is included, global_last day and older days are not."""
    rows = [
        _row("الف", last_date="2026-10-10"),
        _row("ب", last_date="2026-10-11"),
        _row("ج", last_date="2026-11-10"),
        _row("د", last_date="2026-11-09"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        six, fresh = S.plan(rows, "2026-11-10", 30, tmp)
        assert six == [], six
        assert fresh == ["ب", "د"], fresh
        excluded = _read_excluded(
            os.path.join(tmp, "symbols-freshness-excluded.csv"))
        assert excluded == {"الف": "OUT_OF_WINDOW",
                            "ج": "OUT_OF_WINDOW"}, excluded


def _six_comes_from_status_test():
    """The six are planned by name, whatever their row says."""
    rows = [{"symbol": s, "last_date": "garbage", "asset_id": "",
             "stale_status": "halted", "instrument_status": "ممنوع",
             "sessions_behind": "0"} for s in S.SIX]
    with tempfile.TemporaryDirectory() as tmp:
        six, fresh = S.plan(rows, "2026-11-10", 30, tmp)
        assert six == list(S.SIX), six
        assert fresh == [], fresh
        assert _read_excluded(
            os.path.join(tmp, "symbols-freshness-excluded.csv")) == {}


def _included_test():
    """Every freshness condition holds: the row is included, not excluded."""
    rows = [_row("الف", last_date="2026-10-11", asset_id="427",
                 stale_status="stale", instrument_status="مجاز",
                 sessions_behind="21")]
    capture = {S.key("الف"): "427"}
    with tempfile.TemporaryDirectory() as tmp:
        six, fresh = S.plan(rows, "2026-11-10", 30, tmp,
                            capture_plan=capture)
        assert six == [] and fresh == ["الف"], (six, fresh)
        assert _read_excluded(
            os.path.join(tmp, "symbols-freshness-excluded.csv")) == {}


def _no_asset_id_test():
    rows = [
        _row("الف", asset_id=""),
        _row("ب", asset_id="   "),
        _row("ج", asset_id="427"),  # not in the capture plan below
        _row("د", asset_id="999"),  # plan has 427 for د
    ]
    capture = {S.key("د"): "427"}
    with tempfile.TemporaryDirectory() as tmp:
        six, fresh = S.plan(rows, "2026-11-10", 30, tmp,
                            capture_plan=capture)
        assert six == [] and fresh == [], (six, fresh)
        excluded = _read_excluded(
            os.path.join(tmp, "symbols-freshness-excluded.csv"))
    assert excluded == {"الف": "NO_ASSET_ID", "ب": "NO_ASSET_ID",
                        "ج": "NO_ASSET_ID", "د": "NO_ASSET_ID"}, excluded


def _halted_test():
    rows = [
        _row("الف", stale_status="halted"),
        _row("ب", stale_status="stale"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        six, fresh = S.plan(rows, "2026-11-10", 30, tmp)
        assert six == [] and fresh == ["ب"], (six, fresh)
        assert _read_excluded(
            os.path.join(tmp, "symbols-freshness-excluded.csv")) == {
                "الف": "HALTED"}


def _forbidden_test():
    rows = [
        _row("الف", instrument_status="ممنوع"),
        _row("ب", instrument_status="ممنوع-متوقف"),
        _row("ج", instrument_status="ممنوع-محفوظ"),
        _row("د", instrument_status="مجاز"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        six, fresh = S.plan(rows, "2026-11-10", 30, tmp)
        assert six == [] and fresh == ["د"], (six, fresh)
        assert _read_excluded(
            os.path.join(tmp, "symbols-freshness-excluded.csv")) == {
                "الف": "FORBIDDEN_INSTRUMENT",
                "ب": "FORBIDDEN_INSTRUMENT",
                "ج": "FORBIDDEN_INSTRUMENT"}


def _no_missing_session_test():
    rows = [
        _row("الف", sessions_behind="0"),
        _row("ب", sessions_behind=""),
        _row("ج", sessions_behind="abc"),
        _row("د", sessions_behind="-3"),
        _row("ه", sessions_behind="1"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        six, fresh = S.plan(rows, "2026-11-10", 30, tmp)
        assert six == [] and fresh == ["ه"], (six, fresh)
        assert _read_excluded(
            os.path.join(tmp, "symbols-freshness-excluded.csv")) == {
                "الف": "NO_MISSING_SESSION", "ب": "NO_MISSING_SESSION",
                "ج": "NO_MISSING_SESSION", "د": "NO_MISSING_SESSION"}


def _bad_date_test():
    """Non-canonical or empty last_date is excluded as BAD_DATE, never skipped."""
    rows = [
        _row("الف", last_date="2026-1-1"),
        _row("ب", last_date="20260101"),
        _row("ج", last_date="2026-13-45"),
        _row("د", last_date="garbage"),
        _row("ه", last_date=""),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        six, fresh = S.plan(rows, "2026-11-10", 30, tmp)
        assert six == [] and fresh == [], (six, fresh)
        excluded = _read_excluded(
            os.path.join(tmp, "symbols-freshness-excluded.csv"))
        assert set(excluded.values()) == {"BAD_DATE"}, excluded
        assert len(excluded) == len(rows), excluded


def _out_of_window_test():
    rows = [
        _row("الف", last_date="2026-10-10"),
        _row("ب", last_date="2026-11-10"),
        _row("ج", last_date="2026-09-01"),
        _row("د", last_date="2027-01-01"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        six, fresh = S.plan(rows, "2026-11-10", 30, tmp)
        assert six == [] and fresh == [], (six, fresh)
        excluded = _read_excluded(
            os.path.join(tmp, "symbols-freshness-excluded.csv"))
        assert set(excluded.values()) == {"OUT_OF_WINDOW"}, excluded


def _precedence_test():
    """A row with several flaws is named by the first failed rule once."""
    rows = [
        _row("الف", last_date="garbage", stale_status="halted",
             asset_id="", sessions_behind="0"),
        _row("ب", last_date="2026-09-01", stale_status="halted"),
        _row("ج", asset_id="", stale_status="halted"),
        _row("د", stale_status="halted", instrument_status="ممنوع"),
        _row("ه", instrument_status="ممنوع", sessions_behind="0"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        six, fresh = S.plan(rows, "2026-11-10", 30, tmp)
        assert six == [] and fresh == [], (six, fresh)
        excluded = _read_excluded(
            os.path.join(tmp, "symbols-freshness-excluded.csv"))
    assert excluded == {"الف": "BAD_DATE", "ب": "OUT_OF_WINDOW",
                        "ج": "NO_ASSET_ID", "د": "HALTED",
                        "ه": "FORBIDDEN_INSTRUMENT"}, excluded


def _capture_plan_test():
    with tempfile.TemporaryDirectory() as tmp:
        good = os.path.join(tmp, "symbols.json")
        with open(good, "w", encoding="utf-8") as fh:
            json.dump([{"symbol": "الف", "asset_id": 427}], fh)
        assert S.read_capture_symbols(good) == {S.key("الف"): "427"}

        bad = os.path.join(tmp, "bad.json")
        for payload in ("not json", "{}", '[{"asset_id": 1}]',
                        '[{"symbol": "الف"}]'):
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write(payload)
            try:
                S.read_capture_symbols(bad)
            except ValueError:
                pass
            else:
                raise AssertionError("accepted capture plan %r" % (payload,))


def _bad_global_last_test():
    for bad in ("2026-1-1", "20260101", "garbage", None):
        with tempfile.TemporaryDirectory() as tmp:
            try:
                S.plan(_plan_rows(), bad, 30, tmp)
            except ValueError as exc:
                assert "global-last" in str(exc), (bad, str(exc))
            else:
                raise AssertionError("accepted global_last %r" % (bad,))


def _missing_column_test():
    for dropped in S.COLUMNS:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ledger.csv")
            kept = [c for c in S.COLUMNS if c != dropped]
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(",".join(kept) + "\n")
                fh.write(",".join("x" for _ in kept) + "\n")
            try:
                S.read_rows(path)
            except ValueError as exc:
                assert dropped in str(exc), (dropped, str(exc))
            else:
                raise AssertionError(
                    "accepted a ledger without %s" % (dropped,))


def _cli_test():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "ledger.csv")
        rows = _plan_rows() + [
            _row(s, last_date="2026-11-09", asset_id="1",
                 stale_status="stale", sessions_behind="1")
            for s in S.SIX if s != "شنفت"]
        _write_ledger(path, rows)
        symbols = os.path.join(tmp, "symbols.json")
        with open(symbols, "w", encoding="utf-8") as fh:
            json.dump([{"symbol": "الف", "asset_id": 22}], fh)
        out = os.path.join(tmp, "out")
        rc = S.main(["--symbol-ledger", path, "--global-last", "2026-11-10",
                     "--freshness-days", "30", "--capture-symbols", symbols,
                     "--out-dir", out])
        assert rc == 0, rc
        assert _read_symbols(os.path.join(out, "symbols-six.csv")) == list(S.SIX)
        assert _read_symbols(os.path.join(out, "symbols-freshness.csv")) == ["الف"]
        excluded = _read_excluded(
            os.path.join(out, "symbols-freshness-excluded.csv"))
        assert excluded == {"ب": "OUT_OF_WINDOW"}, excluded
        for name in ("symbols-six.csv", "symbols-freshness.csv",
                     "symbols-freshness-excluded.csv"):
            with open(os.path.join(out, name), "rb") as fh:
                raw = fh.read()
            assert b"\r" not in raw, (name, "CRLF")
            assert raw.endswith(b"\n"), (name, "missing final LF")
        with open(os.path.join(out, "symbols-freshness-excluded.csv"),
                  encoding="utf-8", newline="") as fh:
            assert next(csv.reader(fh)) == ["symbol", "reason"]

        # The capture gate is optional: without it a non-empty asset_id wins.
        out_no_gate = os.path.join(tmp, "out-no-gate")
        rc = S.main(["--symbol-ledger", path, "--global-last", "2026-11-10",
                     "--freshness-days", "30", "--out-dir", out_no_gate])
        assert rc == 0, rc
        assert _read_symbols(
            os.path.join(out_no_gate, "symbols-freshness.csv")) == ["الف"]

        # A ledger without all six is a plan that cannot be executed: fail,
        # write nothing, and say which symbols are absent.
        partial = os.path.join(tmp, "partial.csv")
        _write_ledger(partial, _plan_rows())
        out2 = os.path.join(tmp, "out2")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = S.main(["--symbol-ledger", partial, "--global-last",
                         "2026-11-10", "--out-dir", out2])
        assert rc == 2, rc
        assert "مارون" in err.getvalue(), err.getvalue()
        assert not os.path.exists(os.path.join(out2, "symbols-six.csv"))


def main():
    _brief_test()
    _boundary_test()
    _six_comes_from_status_test()
    _included_test()
    _no_asset_id_test()
    _halted_test()
    _forbidden_test()
    _no_missing_session_test()
    _bad_date_test()
    _out_of_window_test()
    _precedence_test()
    _capture_plan_test()
    _bad_global_last_test()
    _missing_column_test()
    _cli_test()
    print("BACKFILL PLAN TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
