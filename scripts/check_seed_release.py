#!/usr/bin/env python3
"""Refuse Seed packaging while reference-derived rows lack owner approval.

The Phase 4.9.1 pipeline records how many rows in the packaged market.db came
from the licensed reference (price_history.src='rahavard365') in
``seed_manifest.reference_derived_rows``. This gate turns that record into a
release decision:

* 0 rows                              -> SEED_RELEASE_OK
* >0 rows with a valid recorded owner -> SEED_RELEASE_OK
  approval record
* >0 rows without recorded approval    -> SEED_RELEASE_BLOCKED (exit 1)
* manifest missing/unreadable          -> SEED_RELEASE_BLOCKED (exit 1)

The recorded approval (Phase 4.9.2) is a committed JSON document that names the
approver, the approved scope, the exact row count and the reference capture
hashes the approval covers. It authorises known reference rows, not an unknown
manifest: a missing seed_manifest table, a missing key, a non-integer value or
a negative count still block even when an approval record exists. The same
holds when ``--owner-approved-reference-redistribution`` is passed on the
command line (the explicit manual override kept from Phase 4.9.1).

The approval does not verify the rows or any adjustment step; it only permits
their inclusion in a Seed whose technical checks still have to pass.

The DB is opened read-only (``mode=ro``) so running the gate can never alter
the artefact it inspects.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_APPROVAL_RECORD = os.path.join(
    ROOT, "docs", "opportunity-center", "phase49-2",
    "OWNER-APPROVAL-REFERENCE-DERIVED.json")
APPROVAL_SCHEMA = "phase49-2-owner-approval-reference-derived-v1"


class SeedManifestError(Exception):
    """The manifest exists but its reference_derived_rows value is untrusted."""


class SeedApprovalError(Exception):
    """The approval record exists but does not cover this Seed."""


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


def _read_seed_manifest(db_path: str) -> dict[str, str]:
    """Return the seed_manifest key/value map, or raise SeedManifestError."""
    uri = "file:%s?mode=ro" % db_path.replace("\\", "/")
    con = sqlite3.connect(uri, uri=True)
    try:
        rows = con.execute("SELECT key, value FROM seed_manifest").fetchall()
    finally:
        con.close()
    manifest = {str(k): str(v) for k, v in rows}
    if not manifest:
        raise SeedManifestError(
            "seed_manifest is missing or empty; the seed was not built by the "
            "Phase 4.9.1 pipeline")
    return manifest


def _read_reference_derived_rows(manifest: dict[str, str]) -> int:
    """Return reference_derived_rows from the manifest, or raise SeedManifestError."""
    value = manifest.get("reference_derived_rows")
    if value is None:
        raise SeedManifestError(
            "seed_manifest has no reference_derived_rows key; the seed was not "
            "built by the Phase 4.9.1 pipeline")
    try:
        rows = int(value)
    except (TypeError, ValueError):
        raise SeedManifestError(
            "reference_derived_rows is not an integer (%r); refusing to guess"
            % (value,)) from None
    if rows < 0:
        raise SeedManifestError(
            "reference_derived_rows is negative (%d); the manifest is corrupt" % rows)
    return rows


def _load_approval(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
    except FileNotFoundError:
        raise SeedApprovalError(
            "no owner approval record at %s; reference-derived rows still "
            "require an explicit owner decision" % path) from None
    except (OSError, ValueError) as exc:
        raise SeedApprovalError(
            "owner approval record %s is unreadable or not valid JSON (%s)"
            % (path, exc)) from None
    if not isinstance(record, dict):
        raise SeedApprovalError(
            "owner approval record %s is not a JSON object" % path)
    return record


def _validate_approval(record: dict, rows: int, manifest: dict[str, str]) -> str:
    """Return the approval date, or raise SeedApprovalError."""
    if record.get("schema") != APPROVAL_SCHEMA:
        raise SeedApprovalError(
            "approval record schema is %r, expected %r"
            % (record.get("schema"), APPROVAL_SCHEMA))
    if record.get("approved") is not True:
        raise SeedApprovalError("approval record does not say approved=true")
    if record.get("scope") != "reference_derived_rows":
        raise SeedApprovalError(
            "approval scope is %r, expected 'reference_derived_rows'"
            % (record.get("scope"),))
    for field in ("approver", "approved_at"):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise SeedApprovalError(
                "approval record has no usable %s" % field)
    expected = record.get("expected_reference_derived_rows")
    if not isinstance(expected, int) or isinstance(expected, bool):
        raise SeedApprovalError(
            "approval record has no integer expected_reference_derived_rows")
    if expected != rows:
        raise SeedApprovalError(
            "approval covers %d reference-derived rows but the seed reports %d"
            % (expected, rows))
    for key in ("reference_capture_sha256", "reference_index_sha256"):
        approved_hash = record.get(key)
        manifest_hash = manifest.get(key)
        if approved_hash and manifest_hash and approved_hash != manifest_hash:
            raise SeedApprovalError(
                "approval %s %s does not match the seed manifest %s"
                % (key, approved_hash, manifest_hash))
    conditions = record.get("conditions")
    if (not isinstance(conditions, list) or not conditions
            or not all(isinstance(c, str) and c.strip() for c in conditions)):
        raise SeedApprovalError(
            "approval record must carry the non-empty conditions list")
    return record["approved_at"]


def main() -> int:
    _harden_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--owner-approved-reference-redistribution", action="store_true")
    ap.add_argument("--approval-record", default=DEFAULT_APPROVAL_RECORD,
                    help="committed owner approval JSON (default: %(default)s)")
    args = ap.parse_args()
    try:
        manifest = _read_seed_manifest(args.db)
        rows = _read_reference_derived_rows(manifest)
    except SeedManifestError as exc:
        print("SEED_RELEASE_BLOCKED: %s" % exc)
        return 1
    except (sqlite3.Error, OSError, ValueError) as exc:
        # Missing DB file, a path that is not a SQLite file, a missing table or
        # an unreadable DB all land here: report blocked, never a traceback.
        print("SEED_RELEASE_BLOCKED: cannot read seed_manifest from %s (%s); "
              "refusing to package an unverifiable seed" % (args.db, exc))
        return 1
    if rows == 0:
        print("SEED_RELEASE_OK: reference_derived_rows=0")
        return 0
    if args.owner_approved_reference_redistribution:
        print("SEED_RELEASE_OK: reference_derived_rows=%d; explicit "
              "owner-approved-reference-redistribution override" % rows)
        return 0
    try:
        record = _load_approval(args.approval_record)
        approved_at = _validate_approval(record, rows, manifest)
    except SeedApprovalError as exc:
        print("SEED_RELEASE_BLOCKED: %d reference-derived rows; %s"
              % (rows, exc))
        return 1
    print("SEED_RELEASE_OK: reference_derived_rows=%d; owner approval recorded "
          "in %s (approved_at=%s)" % (rows, args.approval_record, approved_at))
    return 0


if __name__ == "__main__":
    sys.exit(main())
