#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble the reference pack and write its manifest.

The pack is the single object a consumer reads:

    reference-pack/
      manifest.json              what is inside, its hashes and its counts
      coverage.json              per-series row counts and status
      bars.ndjson.gz             one record per (symbol, timeframe, adjust, basis, date)
      factor_segments.ndjson.gz  one record per inferred factor interval
      mismatch_map.ndjson.gz     one record per unmatched paired date
      *-summary.json             the per-tool summaries

`pack_id` is a hash of the file list (path, sha256, rows), so it changes when
and only when the content changes; the wall-clock `generated_at` is recorded
next to it and never folded into the id.

A file the round could not produce is listed as unavailable with the reason,
never silently omitted and never replaced by a placeholder.

Usage
  python pack.py --dir <packdir> [--require bars,coverage] [--generated-at ISO8601Z]
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import r32_io as IO  # noqa: E402
import r32_schema as S  # noqa: E402

EXPECTED = {
    "bars.ndjson.gz": S.SCHEMA_BAR,
    "factor_segments.ndjson.gz": S.SCHEMA_SEGMENT,
    "mismatch_map.ndjson.gz": S.SCHEMA_MISMATCH,
    "coverage.json": S.SCHEMA_COVERAGE,
}


KNOWN_EXTRA = {
    "factor_segments_frozen.ndjson.gz": S.SCHEMA_SEGMENT,
    "bars_capture.ndjson.gz": S.SCHEMA_BAR,
}


def build_manifest(pack_dir, generated_at=None, require=()):
    files, unavailable = [], []
    for name, schema in EXPECTED.items():
        path = os.path.join(pack_dir, name)
        if os.path.exists(path):
            files.append(IO.file_entry(path, schema, rel=name))
        else:
            unavailable.append({"path": name, "schema": schema, "reason": "not produced by this run"})
    for name, schema in KNOWN_EXTRA.items():
        path = os.path.join(pack_dir, name)
        if os.path.exists(path):
            files.append(IO.file_entry(path, schema, rel=name))
    for path in sorted(glob.glob(os.path.join(pack_dir, "*-summary.json"))):
        files.append(IO.file_entry(path, "ra365-summary/1", rel=os.path.basename(path)))
    for path in sorted(glob.glob(os.path.join(pack_dir, "*-disposition.json"))):
        files.append(IO.file_entry(path, "ra365-summary/1", rel=os.path.basename(path)))

    missing = [p for p in require if p in {u["path"] for u in unavailable}]
    if missing:
        raise S.SchemaError("required pack members missing: %s" % ",".join(missing))

    pack_id = S.row_hash([{"path": f["path"], "sha256": f["sha256"], "rows": f["rows"]}
                          for f in files])
    totals = {}
    for f in files:
        if f["path"].endswith(".ndjson.gz"):
            totals[f["schema"]] = f["rows"]

    return {
        "schema": S.SCHEMA_MANIFEST,
        "pack_id": pack_id,
        "generated_at": generated_at or S.now_utc(),
        "tool": {"name": "tools/ra365/r32-reference", "version": "1"},
        "contract": {
            "key": "symbol_id|timeframe|date|price_basis",
            "factor_convention": "reference_adjusted / product_raw",
            "schemas": [S.SCHEMA_BAR, S.SCHEMA_SEGMENT, S.SCHEMA_MISMATCH,
                        S.SCHEMA_COVERAGE],
        },
        "files": files,
        "unavailable": unavailable,
        "totals": totals,
        "license": "reference data is the owner's Rahavard365 subscription; local-only, "
                   "never published to the public repository",
        "consumer_notes": [
            "Every row names its source and its price basis.",
            "Fields the source did not supply are listed in the row's `unavailable` array; "
            "they are never estimated.",
            "A row is one of: paired and passing, paired and failing (mismatch_map), or "
            "present on one side only (coverage).",
        ],
    }


def main():
    ap = argparse.ArgumentParser(description="Assemble the R32 reference pack manifest.")
    ap.add_argument("--dir", required=True, help="the pack directory")
    ap.add_argument("--require", default="", help="comma-separated files that must exist")
    ap.add_argument("--generated-at", default=None)
    a = ap.parse_args()
    require = [s.strip() for s in a.require.split(",") if s.strip()]
    manifest = build_manifest(a.dir, a.generated_at, require)
    path = IO.write_json(os.path.join(a.dir, "manifest.json"), manifest)
    print("wrote %s" % path)
    print("pack_id=%s  files=%d  unavailable=%d"
          % (manifest["pack_id"], len(manifest["files"]), len(manifest["unavailable"])))
    for f in manifest["files"]:
        print("  %-32s %10d bytes  %8s rows  %s"
              % (f["path"], f["bytes"], f["rows"], f["sha256"][:16]))
    for u in manifest["unavailable"]:
        print("  UNAVAILABLE %-24s %s" % (u["path"], u["reason"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())