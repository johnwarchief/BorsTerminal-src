#!/usr/bin/env python3
"""Refuse Seed packaging while reference-derived rows lack owner approval.

The Phase 4.9.1 pipeline records how many rows in the packaged market.db came
from the licensed reference (price_history.src='rahavard365') in
``seed_manifest.reference_derived_rows``. This gate turns that record into a
release decision:

* 0 rows                         -> SEED_RELEASE_OK
* >0 rows without owner approval -> SEED_RELEASE_BLOCKED (exit 1)
* manifest missing/unreadable    -> SEED_RELEASE_BLOCKED (exit 1)

A Seed we cannot verify is not a Seed we may publish: a missing seed_manifest
table, a missing key, a non-integer value or a negative count all block the
release even when ``--owner-approved-reference-redistribution`` is passed,
because approval authorises known reference rows, not an unknown manifest.
The DB is opened read-only (``mode=ro``) so running the gate can never alter
the artefact it inspects.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys


class SeedManifestError(Exception):
    """The manifest exists but its reference_derived_rows value is untrusted."""


def _harden_stdout() -> None:
    """A blocked verdict must never degrade into a traceback on the console.

    The blocked message names the DB path, and local checkouts live under
    non-ASCII (e.g. Persian) folder names; on a cp1252/ascii console that
    print would raise UnicodeEncodeError. Escaping the unencodable characters
    keeps the exit path a clean exit 1.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass


def _read_reference_derived_rows(db_path: str) -> int:
    """Return seed_manifest.reference_derived_rows, or raise SeedManifestError."""
    uri = "file:%s?mode=ro" % db_path.replace("\\", "/")
    con = sqlite3.connect(uri, uri=True)
    try:
        row = con.execute(
            "SELECT value FROM seed_manifest WHERE key='reference_derived_rows'").fetchone()
    finally:
        con.close()
    if row is None:
        raise SeedManifestError(
            "seed_manifest has no reference_derived_rows key; the seed was not built "
            "by the Phase 4.9.1 pipeline")
    try:
        rows = int(row[0])
    except (TypeError, ValueError):
        raise SeedManifestError(
            "reference_derived_rows is not an integer (%r); refusing to guess"
            % (row[0],)) from None
    if rows < 0:
        raise SeedManifestError(
            "reference_derived_rows is negative (%d); the manifest is corrupt" % rows)
    return rows


def main() -> int:
    _harden_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--owner-approved-reference-redistribution", action="store_true")
    args = ap.parse_args()
    try:
        rows = _read_reference_derived_rows(args.db)
    except SeedManifestError as exc:
        print("SEED_RELEASE_BLOCKED: %s" % exc)
        return 1
    except (sqlite3.Error, OSError, ValueError) as exc:
        # Missing DB file, a path that is not a SQLite file, a missing table or
        # an unreadable DB all land here: report blocked, never a traceback.
        print("SEED_RELEASE_BLOCKED: cannot read seed_manifest from %s (%s); "
              "refusing to package an unverifiable seed" % (args.db, exc))
        return 1
    if rows > 0 and not args.owner_approved_reference_redistribution:
        print("SEED_RELEASE_BLOCKED: %d reference-derived rows; "
              "owner approval for redistribution is required" % rows)
        return 1
    print("SEED_RELEASE_OK: reference_derived_rows=%d" % rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
