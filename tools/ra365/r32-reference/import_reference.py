#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ingest Rahavard reference data into the R32 pack contract.

This is the repeatable entry point: it accepts a capture export from
capture_rahavard.mjs, a manual CSV export, or one of the frozen R26-R31
ledgers, and writes the normalised artifacts a consumer reads.

  bars.ndjson.gz     one record per (symbol, timeframe, adjust, basis, date)
  coverage.json      per-series row counts, first/last date and status
  import-manifest.json   the file hashes plus the source records

Nothing is written to a database and no network call is made; the importer only
ever sees a file that already exists.

Usage
  python import_reference.py --in <export> --out <dir> [--kind auto]
      [--also-pairs <pairs.ndjson.gz>] [--generated-at ISO8601Z]

  python import_reference.py --in _audit/RA365-CANDLE-DIVERGE-2026-10-12.csv \\
      --kind candle-diverge --out D:/BorsTerminal-tmp/ra365_round32/reference-pack
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import r32_evidence as EV  # noqa: E402
import r32_io as IO  # noqa: E402
import r32_rahavard_api as API  # noqa: E402
import r32_schema as S  # noqa: E402

KINDS = ("auto", "rahavard-json", "rahavard-csv", "candle-diverge",
         "parity-diverge", "steps")


def load(path, kind, url=None):
    """Return (sources, bars, pairs, segments) for one input file."""
    if kind == "auto":
        with open(path, "rb") as fh:
            head = fh.read(4096).decode("utf-8-sig", "replace").lstrip()
        if head.startswith("{") and os.path.basename(path).endswith(".json"):
            kind = "rahavard-json"
        else:
            with open(path, encoding="utf-8-sig", newline="") as fh:
                header = fh.readline()
            cols = {c.strip().lower() for c in header.split(",")}
            if {"arm", "prod_o", "ref_o"} <= cols:
                kind = "parity-diverge"
            elif {"our_o", "ref_o", "symbol"} <= cols:
                kind = "candle-diverge"
            elif {"asset_id", "prod_ratio", "ref_ratio"} <= cols:
                kind = "steps"
            elif {"date", "symbol", "open"} <= cols:
                kind = "rahavard-csv"
            else:
                raise S.SchemaError("cannot tell which export %r is; pass --kind"
                                    % os.path.basename(path))

    if kind == "rahavard-json":
        sources, bars = API.parse_rahavard_json(path)
        return [sources], bars, [], []
    if kind == "rahavard-csv":
        sources, bars = API.parse_rahavard_csv(path)
        return [sources], bars, [], []
    if kind == "candle-diverge":
        sources, bars = EV.bars_from_candle_diverge(path, url=url)
        return sources, bars, EV.pairs_from_candle_diverge(path), []
    if kind == "parity-diverge":
        return [], [], EV.pairs_from_parity_diverge(path, url=url), []
    if kind == "steps":
        return [], [], [], EV.segments_from_steps(path)
    raise S.SchemaError("unknown kind: %r" % (kind,))


def build_coverage(bars):
    """Per-series counts. A series with zero bars is EMPTY, never dropped."""
    groups = defaultdict(list)
    for b in bars:
        groups[(b["symbol_id"], b["symbol"], b["timeframe"], b["adjust"],
                b["basis"], b["source_id"])].append(b)
    series = []
    for key, rows in sorted(groups.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        dates = sorted(b["date"] for b in rows)
        unavailable = defaultdict(int)
        for b in rows:
            for f in b.get("unavailable") or []:
                unavailable[f] += 1
        series.append({
            "symbol_id": key[0], "symbol": key[1], "timeframe": key[2],
            "adjust": key[3], "basis": key[4], "source_id": key[5],
            "rows": len(rows), "first": dates[0], "last": dates[-1],
            "status": "OK" if rows else "EMPTY",
            "unavailable_counts": dict(sorted(unavailable.items())),
        })
    return series


def _display_path(path):
    """A readable, drive-safe path: relpath raises across Windows drives."""
    try:
        return os.path.relpath(path).replace("\\", "/")
    except ValueError:
        return os.path.abspath(path).replace("\\", "/")


def _declared(path):
    doc = IO.read_json(path)
    rows = doc.get("coverage") if isinstance(doc, dict) else doc
    return {"source": doc.get("reference") if isinstance(doc, dict) else None,
            "series": rows or []}


def _shortfall(declared, bars):
    """Declared reference universe minus what this import actually holds.

    The unit is the (asset, type, resolution) series plus the asset count,
    because a declared bar count cannot be compared with a partially captured
    subset row by row without inventing the missing rows.
    """
    decl_series = [s for s in (declared.get("series") or []) if isinstance(s, dict)]
    decl_assets = {s.get("assets") for s in decl_series if s.get("assets")}
    decl_series_count = sum(1 for s in decl_series if s.get("series"))
    present_by_tf = {}
    for b in bars:
        key = (b["timeframe"], b["adjust"], b["basis"])
        present_by_tf.setdefault(key, set()).add(b["symbol_id"])
    present_assets = {b["symbol_id"] for b in bars}
    return {
        "declared_series": decl_series_count,
        "declared_assets": max(decl_assets) if decl_assets else None,
        "present_series": len({(b["symbol_id"], b["timeframe"], b["adjust"], b["basis"])
                               for b in bars}),
        "present_assets": len(present_assets),
        "assets_missing": (max(decl_assets) - len(present_assets)) if decl_assets else None,
        "present_by_timeframe": {("%s|%s|%s" % k): len(v) for k, v in sorted(present_by_tf.items())},
        "unit_note": "series = asset x adjust x resolution; a declared bar count is not "
                     "compared row by row against a partial capture",
    }


def main():
    ap = argparse.ArgumentParser(description="Ingest reference data into the R32 pack.")
    ap.add_argument("--in", dest="inputs", nargs="+", required=True)
    ap.add_argument("--kind", default="auto", choices=KINDS)
    ap.add_argument("--out", required=True, help="pack directory")
    ap.add_argument("--source-url", default=None, help="provenance URL for a frozen ledger")
    ap.add_argument("--also-pairs", default=None, help="dump paired rows for the inference step")
    ap.add_argument("--declared-coverage", default=None,
                    help="the frozen R26 universe this import should be measured against")
    ap.add_argument("--generated-at", default=None)
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    generated_at = a.generated_at or S.now_utc()

    sources, bars, pairs, segments = [], [], [], []
    inputs_meta = []
    for path in a.inputs:
        s, b, p, seg = load(path, a.kind, url=a.source_url)
        sources.extend(s)
        bars.extend(b)
        pairs.extend(p)
        segments.extend(seg)
        inputs_meta.append({"path": _display_path(path),
                            "sha256": S.sha256_file(path),
                            "bytes": os.path.getsize(path),
                            "kind": a.kind})

    seen = set()
    unique_bars = []
    dupes = 0
    for b in sorted(bars, key=lambda r: (str(r["symbol_id"]), r["timeframe"], r["adjust"],
                                         r["basis"], r["date"], r["source_id"])):
        k = (b["symbol_id"], b["timeframe"], b["adjust"], b["basis"], b["date"], b["source_id"])
        if k in seen:
            dupes += 1
            continue
        seen.add(k)
        unique_bars.append(b)

    violations = []
    for b in unique_bars:
        errs = S.validate(b, S.SCHEMA_BAR)
        if errs:
            violations.append({"row": b.get("date"), "errors": errs})
            if len(violations) > 20:
                break

    bars_path = os.path.join(a.out, "bars.ndjson.gz")
    n_bars = IO.write_ndjson_gz(bars_path, unique_bars)

    coverage = {
        "schema": S.SCHEMA_COVERAGE,
        "generated_at": generated_at,
        "series": build_coverage(unique_bars),
        "totals": {
            "bars": n_bars,
            "series": len({(s["symbol_id"], s["timeframe"], s["adjust"], s["basis"])
                           for s in build_coverage(unique_bars)}),
            "symbols": len({b["symbol"] for b in unique_bars}),
            "duplicate_rows_dropped": dupes,
            "schema_violations": len(violations),
        },
        "not_captured": [],
        "notes": [
            "A series that the source answered with zero bars is recorded as EMPTY, not removed.",
            "Rows are unique on (symbol_id, timeframe, adjust, basis, date, source_id).",
        ],
    }
    if a.declared_coverage and os.path.exists(a.declared_coverage):
        coverage["declared_universe"] = _declared(a.declared_coverage)
        coverage["shortfall"] = _shortfall(coverage["declared_universe"], unique_bars)
    coverage_path = IO.write_json(os.path.join(a.out, "coverage.json"), coverage)

    if segments:
        IO.write_ndjson_gz(os.path.join(a.out, "factor_segments.ndjson.gz"), segments)
    if pairs and a.also_pairs:
        IO.write_ndjson_gz(a.also_pairs, pairs)

    manifest = {
        "schema": S.SCHEMA_MANIFEST,
        "generated_at": generated_at,
        "tool": {"name": "tools/ra365/r32-reference/import_reference.py", "version": "1"},
        "sources": sources,
        "inputs": inputs_meta,
        "files": [IO.file_entry(bars_path, S.SCHEMA_BAR, rows=n_bars,
                                rel="bars.ndjson.gz"),
                  IO.file_entry(coverage_path, S.SCHEMA_COVERAGE, rows=None,
                                rel="coverage.json")],
        "counts": coverage["totals"],
        "violations": violations[:20],
        "notes": [
            "Reference data is the owner's subscription; this pack is local-only and is "
            "never committed to the public repository.",
            "No credential, cookie or token is read or stored by this importer.",
        ],
    }
    manifest_path = IO.write_json(os.path.join(a.out, "import-manifest.json"), manifest)

    print("wrote %s (%d bars)" % (bars_path, n_bars))
    print("wrote %s (%d series)" % (coverage_path, len(coverage["series"])))
    print("wrote %s" % manifest_path)
    if a.also_pairs and pairs:
        print("wrote %s (%d paired rows)" % (a.also_pairs, len(pairs)))
    if segments:
        print("segments: %d" % len(segments))
    if violations:
        print("SCHEMA VIOLATIONS: %d (first: %r)" % (len(violations), violations[0]))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())