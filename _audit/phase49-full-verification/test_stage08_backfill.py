#!/usr/bin/env python3
"""Prove the backfill plan: six mandated symbols, freshness window, ISO guard."""
import contextlib
import csv
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage08_backfill as S  # noqa: E402


def _read_symbols(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return [r["symbol"] for r in csv.DictReader(fh)]


def _write_ledger(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["symbol", "last_date", "final_status"])
        for r in rows:
            w.writerow([r["symbol"], r["last_date"], r["final_status"]])


def _plan_rows():
    return [
        {"symbol": "شنفت", "last_date": "2026-10-11",
         "final_status": "INSUFFICIENT_EVIDENCE"},
        {"symbol": "الف", "last_date": "2026-11-08",
         "final_status": "VERIFIED_WITH_EVENTS"},
        {"symbol": "ب", "last_date": "2026-09-01",
         "final_status": "INSUFFICIENT_EVIDENCE"},
    ]


def _brief_test():
    with tempfile.TemporaryDirectory() as tmp:
        six, fresh = S.plan(_plan_rows(), "2026-11-10", 30, tmp)
        assert six == ["شنفت"], six
        assert fresh == ["الف"], fresh
        assert _read_symbols(os.path.join(tmp, "symbols-six.csv")) == six
        assert _read_symbols(os.path.join(tmp, "symbols-freshness.csv")) == fresh


def _boundary_test():
    """Cutoff day is included, global_last day and older days are not."""
    rows = [
        {"symbol": "الف", "last_date": "2026-10-10", "final_status": "X"},
        {"symbol": "ب", "last_date": "2026-10-11", "final_status": "X"},
        {"symbol": "ج", "last_date": "2026-11-10", "final_status": "X"},
        {"symbol": "د", "last_date": "2026-11-09", "final_status": "X"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        six, fresh = S.plan(rows, "2026-11-10", 30, tmp)
        assert six == [], six
        assert fresh == ["ب", "د"], fresh


def _six_comes_from_status_test():
    """The six are planned by name, whatever their final_status says."""
    rows = [{"symbol": s, "last_date": "2026-06-01",
             "final_status": "VERIFIED_WITH_EVENTS"} for s in S.SIX]
    with tempfile.TemporaryDirectory() as tmp:
        six, fresh = S.plan(rows, "2026-11-10", 30, tmp)
        assert six == list(S.SIX), six
        assert fresh == [], fresh


def _malformed_date_test():
    """Non-canonical or empty last_date fails loudly, naming the row."""
    bad_values = ("2026-1-1", "20260101", "2026-13-45", "garbage", "")
    for bad in bad_values:
        rows = [{"symbol": "الف", "last_date": bad, "final_status": "X"}]
        with tempfile.TemporaryDirectory() as tmp:
            try:
                S.plan(rows, "2026-11-10", 30, tmp)
            except ValueError as exc:
                msg = str(exc)
                assert "row 2" in msg and "الف" in msg, (bad, msg)
                assert "last_date" in msg, (bad, msg)
                assert not os.path.exists(
                    os.path.join(tmp, "symbols-six.csv")), (bad, "wrote on error")
            else:
                raise AssertionError("accepted last_date %r" % (bad,))


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
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "ledger.csv")
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write("symbol,final_status\nالف,X\n")
        try:
            S.read_rows(path)
        except ValueError as exc:
            assert "last_date" in str(exc), str(exc)
        else:
            raise AssertionError("accepted a ledger without last_date")


def _cli_test():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "ledger.csv")
        rows = _plan_rows() + [
            {"symbol": s, "last_date": "2026-10-11", "final_status": "X"}
            for s in S.SIX if s != "شنفت"]
        _write_ledger(path, rows)
        out = os.path.join(tmp, "out")
        rc = S.main(["--symbol-ledger", path, "--global-last", "2026-11-10",
                     "--freshness-days", "30", "--out-dir", out])
        assert rc == 0, rc
        assert _read_symbols(os.path.join(out, "symbols-six.csv")) == list(S.SIX)
        assert _read_symbols(os.path.join(out, "symbols-freshness.csv")) == ["الف"]
        for name in ("symbols-six.csv", "symbols-freshness.csv"):
            with open(os.path.join(out, name), "rb") as fh:
                raw = fh.read()
            assert b"\r" not in raw, (name, "CRLF")
            assert raw.endswith(b"\n"), (name, "missing final LF")

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
    _malformed_date_test()
    _bad_global_last_test()
    _missing_column_test()
    _cli_test()
    print("BACKFILL PLAN TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
