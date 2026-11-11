#!/usr/bin/env python3
"""Stage 08 - plan the Phase 4.9.1 backfill: six full symbols + active gaps.

Two lists, both data-driven from the B7 symbol ledger
(``ledgers/HISTORY-COVERAGE-LEDGER.csv``):

``symbols-six.csv``
    The six symbols the owner mandated for full history, by name:
    شنفت, فافق, فخاس, فولاژ, لخزر, مارون. Membership is decided by the symbol,
    never by ``final_status`` and never by the freshness filters; a status
    change, a halted row or an unmapped asset must not drop one of the six.

``symbols-freshness.csv``
    The active captured symbols with recent missing sessions (spec section
    10.2). A row enters only when all of these hold:

    - ``asset_id`` is non-empty and, when a capture ``symbols.json`` is given,
      the symbol is present there with the same asset id;
    - ``stale_status`` is not ``halted``;
    - ``instrument_status`` does not start with ``ممنوع`` (forbidden);
    - ``sessions_behind`` parses to an integer greater than zero;
    - ``last_date`` is canonical ``YYYY-MM-DD``, at or after the freshness
      cutoff and before ``global_last``.

``symbols-freshness-excluded.csv``
    Every other non-six ledger row, exactly once, with the first failed rule
    as its reason: BAD_DATE, OUT_OF_WINDOW, NO_ASSET_ID, HALTED,
    FORBIDDEN_INSTRUMENT or NO_MISSING_SESSION (precedence in that order). A
    row is never dropped silently, and the freshness list is not capped: a
    gap is a gap.

Dates for inclusion are parsed as canonical ``YYYY-MM-DD`` and compared as
dates; a malformed, empty or non-zero-padded value (``2026-1-1``,
``20260101``) is excluded as BAD_DATE, never skipped. ``--global-last``
itself remains a hard error when malformed: without it no window exists. A
ledger without all six mandated symbols is also an error: the plan could not
be executed as written.

Outputs go under an ignored directory (``phase49-full-verification/backfill-plan``);
the ledger and the capture plan are only read. Reads no network, writes no
data rows.
"""
import argparse
import csv
import json
import os
import sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DEV = os.path.join(ROOT, "dev")
if DEV not in sys.path:
    sys.path.insert(0, DEV)

from symbol_identity import key  # noqa: E402

SIX = ("شنفت", "فافق", "فخاس", "فولاژ", "لخزر", "مارون")
COLUMNS = ("symbol", "last_date", "asset_id", "stale_status",
           "instrument_status", "sessions_behind")
REASONS = ("BAD_DATE", "OUT_OF_WINDOW", "NO_ASSET_ID", "HALTED",
           "FORBIDDEN_INSTRUMENT", "NO_MISSING_SESSION")
FORBIDDEN_PREFIX = "ممنوع"


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
    """Read the symbol ledger; require the columns this plan depends on."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        names = reader.fieldnames or []
        for column in COLUMNS:
            if column not in names:
                raise ValueError("%s: symbol ledger has no %r column (columns: %s)"
                                 % (path, column, ", ".join(names) or "none"))
        return list(reader)


def sessions_behind(value):
    """The integer in ``sessions_behind``, or None when it is not an integer."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def read_capture_symbols(path):
    """The capture plan's ``symbols.json`` as ``{normalised symbol: asset_id}``."""
    with open(path, encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except ValueError as exc:
            raise ValueError("%s: not valid JSON: %s" % (path, exc))
    if not isinstance(data, list):
        raise ValueError("%s: expected a JSON list of capture entries" % (path,))
    planned = {}
    for number, entry in enumerate(data, start=1):
        if not isinstance(entry, dict):
            raise ValueError("%s: entry %d is not an object" % (path, number))
        symbol = entry.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("%s: entry %d has no symbol" % (path, number))
        asset_id = str(entry.get("asset_id") or "").strip()
        if not asset_id:
            raise ValueError("%s: entry %d (%s) has no asset_id"
                             % (path, number, symbol))
        planned[key(symbol)] = asset_id
    return planned


def missing_six(rows):
    """The mandated symbols absent from the ledger, in canonical order."""
    present = {r.get("symbol") for r in rows}
    return [s for s in SIX if s not in present]


def exclusion_reason(row, cutoff, global_day, capture_plan):
    """The first failed freshness rule for a non-six row, or None if included."""
    symbol = row.get("symbol") or ""
    try:
        last = canonical_day(row.get("last_date"),
                             "symbol-ledger row (%s): last_date" % (symbol,))
    except ValueError:
        return "BAD_DATE"
    if not cutoff <= last < global_day:
        return "OUT_OF_WINDOW"
    asset_id = str(row.get("asset_id") or "").strip()
    if not asset_id:
        return "NO_ASSET_ID"
    if capture_plan is not None:
        planned_id = capture_plan.get(key(symbol))
        if planned_id is None or planned_id != asset_id:
            return "NO_ASSET_ID"
    if str(row.get("stale_status") or "").strip() == "halted":
        return "HALTED"
    if str(row.get("instrument_status") or "").strip().startswith(
            FORBIDDEN_PREFIX):
        return "FORBIDDEN_INSTRUMENT"
    sessions = sessions_behind(row.get("sessions_behind"))
    if sessions is None or sessions <= 0:
        return "NO_MISSING_SESSION"
    return None


def select(rows, global_last, freshness_days, capture_plan=None):
    """Return ``(six, freshness, excluded)``; excluded holds (symbol, reason)."""
    global_day = canonical_day(global_last, "--global-last")
    if freshness_days < 1:
        raise ValueError("--freshness-days must be >= 1, got %r"
                         % (freshness_days,))
    cutoff = global_day - timedelta(days=freshness_days)

    six, fresh, excluded = [], [], []
    for number, row in enumerate(rows, start=2):
        symbol = row.get("symbol") or ""
        if not symbol:
            raise ValueError("symbol-ledger row %d: empty symbol" % number)
        if symbol in SIX:
            six.append(symbol)
            continue
        reason = exclusion_reason(row, cutoff, global_day, capture_plan)
        if reason is None:
            fresh.append(symbol)
        else:
            excluded.append((symbol, reason))
    return six, fresh, excluded


def write_outputs(six, fresh, excluded, out_dir):
    """Write the three plan CSVs (LF only)."""
    os.makedirs(out_dir, exist_ok=True)
    files = (
        ("symbols-six.csv", ("symbol",), [(s,) for s in six]),
        ("symbols-freshness.csv", ("symbol",), [(s,) for s in fresh]),
        ("symbols-freshness-excluded.csv", ("symbol", "reason"), excluded),
    )
    for name, header, body in files:
        with open(os.path.join(out_dir, name), "w", encoding="utf-8",
                  newline="") as fh:
            writer = csv.writer(fh, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(body)


def plan(rows, global_last, freshness_days, out_dir, capture_plan=None):
    """Write the plans and return ``(six, freshness)`` symbol lists."""
    six, fresh, excluded = select(rows, global_last, freshness_days,
                                 capture_plan)
    write_outputs(six, fresh, excluded, out_dir)
    return six, fresh


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Plan the six-symbol and freshness backfill from the "
                    "B7 history-coverage ledger.")
    ap.add_argument("--symbol-ledger", required=True)
    ap.add_argument("--global-last", required=True)
    ap.add_argument("--freshness-days", type=int, default=30)
    ap.add_argument("--capture-symbols",
                    help="the capture plan's symbols.json; when given, a "
                         "freshness row must be captured with the same "
                         "asset id")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    try:
        canonical_day(a.global_last, "--global-last")
        rows = read_rows(a.symbol_ledger)
        absent = missing_six(rows)
        if absent:
            raise ValueError(
                "symbol ledger lacks mandated symbols: %s" % ", ".join(absent))
        capture_plan = None
        if a.capture_symbols:
            capture_plan = read_capture_symbols(a.capture_symbols)
        six, fresh, excluded = select(rows, a.global_last, a.freshness_days,
                                      capture_plan)
        write_outputs(six, fresh, excluded, a.out_dir)
    except (OSError, ValueError) as exc:
        sys.stderr.write("stage08_backfill: %s\n" % (exc,))
        return 2
    counts = {reason: 0 for reason in REASONS}
    for _symbol, reason in excluded:
        counts[reason] += 1
    print("six=%d freshness=%d excluded=%d"
          % (len(six), len(fresh), len(excluded)))
    print("excluded " + " ".join("%s=%d" % (reason, counts[reason])
                                 for reason in REASONS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
