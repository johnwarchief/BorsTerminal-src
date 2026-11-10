#!/usr/bin/env python3
"""Stage 08 - plan the Phase 4.9.1 backfill: six full symbols + active gaps.

Two lists, both data-driven from the B7 symbol ledger
(``ledgers/HISTORY-COVERAGE-LEDGER.csv``):

``symbols-six.csv``
    The six symbols the owner mandated for full history, by name:
    شنفت, فافق, فخاس, فولاژ, لخزر, مارون. Membership is decided by the symbol,
    never by ``final_status``; a status change must not drop one of the six.

``symbols-freshness.csv``
    Symbols whose ``last_date`` sits in the freshness window
    ``[global_last - freshness_days, global_last)`` and that are not one of the
    six. The list is not capped: a gap is a gap.

Dates are parsed as canonical ``YYYY-MM-DD`` and compared as dates. A
malformed, empty or non-zero-padded value (``2026-1-1``, ``20260101``) is a
hard error naming the row and symbol - never a silent skip, because a skipped
row would quietly shrink the plan. A ledger without all six mandated symbols
is also an error: the plan could not be executed as written.

Outputs go under an ignored directory (``phase49-full-verification/backfill-plan``);
the ledger is only read. Reads no network, writes no data rows.
"""
import argparse
import csv
import os
import sys
from datetime import date, timedelta

SIX = ("شنفت", "فافق", "فخاس", "فولاژ", "لخزر", "مارون")
COLUMNS = ("symbol", "last_date")


def canonical_day(value, what):
    """A canonical zero-padded ISO day; anything else raises ValueError."""
    if not isinstance(value, str) or not value:
        raise ValueError("%s is empty; expected a canonical ISO date YYYY-MM-DD"
                         % (what,))
    try:
        day = date.fromisoformat(value)
    except ValueError:
        raise ValueError(
            "%s %r is not a canonical ISO date YYYY-MM-DD" % (what, value))
    if day.isoformat() != value:
        raise ValueError(
            "%s %r is not canonical (did you mean %s?)"
            % (what, value, day.isoformat()))
    return day


def read_rows(path):
    """Read the symbol ledger; require the two columns this plan depends on."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        names = reader.fieldnames or []
        for column in COLUMNS:
            if column not in names:
                raise ValueError("%s: symbol ledger has no %r column (columns: %s)"
                                 % (path, column, ", ".join(names) or "none"))
        return list(reader)


def missing_six(rows):
    """The mandated symbols absent from the ledger, in canonical order."""
    present = {r.get("symbol") for r in rows}
    return [s for s in SIX if s not in present]


def plan(rows, global_last, freshness_days, out_dir):
    """Write the two plans and return ``(six, freshness)`` symbol lists."""
    global_day = canonical_day(global_last, "--global-last")
    if freshness_days < 1:
        raise ValueError("--freshness-days must be >= 1, got %r"
                         % (freshness_days,))
    cutoff = global_day - timedelta(days=freshness_days)

    six, fresh = [], []
    for number, row in enumerate(rows, start=2):
        symbol = row.get("symbol") or ""
        if not symbol:
            raise ValueError("symbol-ledger row %d: empty symbol" % number)
        try:
            last = canonical_day(row.get("last_date"),
                                 "symbol-ledger row %d (%s): last_date"
                                 % (number, symbol))
        except ValueError as exc:
            raise ValueError("%s; freshness cannot be evaluated" % (exc,))
        if symbol in SIX:
            six.append(symbol)
        elif cutoff <= last < global_day:
            fresh.append(symbol)

    os.makedirs(out_dir, exist_ok=True)
    for name, symbols in (("symbols-six.csv", six),
                          ("symbols-freshness.csv", fresh)):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8",
                  newline="") as fh:
            writer = csv.writer(fh, lineterminator="\n")
            writer.writerow(["symbol"])
            writer.writerows([s] for s in symbols)
    return six, fresh


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Plan the six-symbol and freshness backfill from the "
                    "B7 history-coverage ledger.")
    ap.add_argument("--symbol-ledger", required=True)
    ap.add_argument("--global-last", required=True)
    ap.add_argument("--freshness-days", type=int, default=30)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    try:
        canonical_day(a.global_last, "--global-last")
        rows = read_rows(a.symbol_ledger)
        absent = missing_six(rows)
        if absent:
            raise ValueError(
                "symbol ledger lacks mandated symbols: %s" % ", ".join(absent))
        six, fresh = plan(rows, a.global_last, a.freshness_days, a.out_dir)
    except (OSError, ValueError) as exc:
        sys.stderr.write("stage08_backfill: %s\n" % (exc,))
        return 2
    print("six=%d freshness=%d" % (len(six), len(fresh)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
