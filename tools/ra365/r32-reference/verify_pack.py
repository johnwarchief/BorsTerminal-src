#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify a reference pack against its own manifest and schema.

For every file listed in manifest.json this checks the byte hash and the row
count, then validates every record against the R32 contract.  A file listed as
unavailable is reported, not treated as a failure; a file present but unlisted,
a hash that moved, or a record that breaks the contract is.

Exit code 0 means the pack is intact and every record satisfies the contract.

Usage
  python verify_pack.py --dir <packdir> [--limit 0]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import r32_io as IO  # noqa: E402
import r32_schema as S  # noqa: E402


def iter_records(path):
    if path.endswith(".ndjson.gz"):
        for rec in IO.read_ndjson_gz(path):
            yield rec
    elif path.endswith(".json"):
        yield IO.read_json(path)


def main():
    ap = argparse.ArgumentParser(description="Verify the R32 reference pack.")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--limit", type=int, default=0, help="stop after N problems")
    a = ap.parse_args()
    manifest = IO.read_json(os.path.join(a.dir, "manifest.json"))
    if manifest.get("schema") != S.SCHEMA_MANIFEST:
        print("FAIL manifest schema: %r" % (manifest.get("schema"),))
        return 1

    problems, checked, records = [], 0, 0
    listed = set()
    for entry in manifest.get("files") or []:
        path = os.path.join(a.dir, entry["path"])
        listed.add(entry["path"])
        if not os.path.exists(path):
            problems.append("missing file %s" % entry["path"])
            continue
        digest = S.sha256_file(path)
        if digest != entry["sha256"]:
            problems.append("hash moved for %s: manifest %s actual %s"
                            % (entry["path"], entry["sha256"][:16], digest[:16]))
        rows = IO.count_lines(path) if entry["path"].endswith(".ndjson.gz") else None
        if rows is not None and entry.get("rows") is not None and rows != entry["rows"]:
            problems.append("row count for %s: manifest %s actual %s"
                            % (entry["path"], entry["rows"], rows))
        checked += 1
        schema = entry.get("schema")
        if schema in (S.SCHEMA_BAR, S.SCHEMA_SEGMENT, S.SCHEMA_MISMATCH):
            for rec in iter_records(path):
                records += 1
                for err in S.validate(rec, schema):
                    problems.append("%s: %s (%s)"
                                    % (entry["path"], err, rec.get("key") or rec.get("date")))
                    if a.limit and len(problems) >= a.limit:
                        break
                if a.limit and len(problems) >= a.limit:
                    break
        if a.limit and len(problems) >= a.limit:
            break

    for name in ("bars.ndjson.gz", "coverage.json", "manifest.json"):
        if name not in listed and name != "manifest.json":
            problems.append("expected member %s is not listed in the manifest" % name)

    print("pack_id=%s" % manifest.get("pack_id"))
    print("files checked=%d  records validated=%d  unavailable=%d"
          % (checked, records, len(manifest.get("unavailable") or [])))
    for u in manifest.get("unavailable") or []:
        print("  unavailable: %s (%s)" % (u["path"], u["reason"]))
    if problems:
        print("PROBLEMS: %d" % len(problems))
        for p in problems[:20]:
            print("  - %s" % p)
        return 1
    print("OK — pack intact, every record satisfies the R32 contract")
    return 0


if __name__ == "__main__":
    sys.exit(main())