#!/usr/bin/env python3
"""Stage 02 - import the reference capture and build the factor-change index.

The capture is parsed by the frozen importer, never by a second parser:
``tools/phase45/rahavard/import_capture.py --in <capture> --out <normalized>``
writes ``bars.ndjson.gz`` / ``coverage.json`` / ``summary.json``. This stage
reads the bars back and builds one index record per *normalised* symbol key.

Identity
--------
Symbols join on ``dev.symbol_identity.key``: the capture may spell one security
with Arabic kaf, Persian kaf, a ZWNJ or a leading space, and those spellings
must be one record, not two. Each record carries both the normalised ``key`` and
the raw ``symbol``/``raw_symbols`` (plus ``asset_ids``), so a later stage can
still see an ambiguous duplicate instead of inheriting a silent merge.

Factor change (frozen rule)
---------------------------
For every daily date present in both ``type0`` (raw) and ``type7`` (adjusted),
``factor = adjusted_close / raw_close``. A transition is a step when
``abs(factor / previous_factor - 1) > FACTOR_EXACT`` (``1e-3``, the existing
0.1% rule from ``stageC_reference_parity.py``). The threshold is not configurable
here on purpose.

Provenance
----------
Every record carries ``source`` (repo-relative path of the capture that fed the
import) and ``capture_sha256`` (SHA-256 of the decompressed ``bars.ndjson.gz``
payload actually consumed). The digest covers the bars, not the ``.gz``
container: the gzip header embeds a wall-clock mtime, so container hashes would
differ between runs over identical rows. Provenance lives on each record rather
than in a ``__meta__`` entry so consumers that iterate every key keep seeing
only symbols.

Every comparable transition is counted: ``factor_exact`` (ratio exactly 1.0),
``factor_within_0.1pct`` (0 < |ratio-1| <= 1e-3), ``factor_undefined_ratio``
(the previous level was zero, so the ratio does not exist) and
``factor_changes`` (above the threshold). A change entry keeps the raw ratio as
``ratio_change`` next to the new ``factor``, so a later audit can re-derive the
previous level. The four buckets add up to ``max(factor_days - 1, 0)``.

CLI:
    python _audit/phase49-full-verification/stage02_import_reference.py \\
        --capture <capture.json> --normalized <dir> \\
        --out <reference-index.json> [--manifest evidence/<stage>.manifest.json]

The index is an output and belongs in the gitignored ``captures/`` or
``ledgers/`` area; the tracked evidence is the small stage manifest (input and
output SHA-256s plus counts), never bars or raw rows. Stdlib only.
"""
import argparse
import gzip
import hashlib
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DEV = os.path.join(ROOT, "dev")
if DEV not in sys.path:
    sys.path.insert(0, DEV)

import phase49_manifest as PM  # noqa: E402
from symbol_identity import key as symbol_key  # noqa: E402

IMPORT = os.path.join(ROOT, "tools", "phase45", "rahavard", "import_capture.py")
FACTOR_EXACT = 1e-3
DEFAULT_MANIFEST = os.path.join(HERE, "evidence",
                                "stage02_import_reference.manifest.json")


def _abs(path):
    """Resolve a repo-relative path against ROOT; leave absolute paths alone."""
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def _rel(path):
    """Repo-relative POSIX path (portable in evidence; no machine paths)."""
    try:
        rel = os.path.relpath(_abs(path), ROOT)
    except ValueError:  # different drive on Windows
        rel = _abs(path)
    return rel.replace("\\", "/")


def _write_json(path, payload):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    return path


def series_type(row):
    """``type0`` (raw) or ``type7`` (adjusted) from one normalised bar."""
    typ = str(row.get("type") or "")
    adjust = row.get("adjust")
    if typ == "type0" or adjust == "raw":
        return "type0"
    if typ == "type7" or adjust == "adjusted":
        return "type7"
    return None


def read_bars(bars_path):
    """Return ``(rows, sha256)`` for the importer's ``bars.ndjson.gz``.

    The digest is the one stored as ``capture_sha256``: SHA-256 of the
    decompressed NDJSON payload the index is actually built from. It is stable
    across runs over the same rows, unlike a hash of the gzip container.
    """
    with gzip.open(bars_path, "rb") as fh:
        payload = fh.read()
    rows = [json.loads(line) for line in payload.decode("utf-8").splitlines()
            if line.strip()]
    return rows, hashlib.sha256(payload).hexdigest()


def build_index(rows, source=None, capture_sha256=None):
    """Build ``{normalised_key: record}`` from imported daily bars.

    ``source`` and ``capture_sha256`` are copied onto every record, so an index
    read later can prove which capture and which bars bytes produced it. Both
    default to ``None`` (keys are always present) for callers that build an
    index from in-memory rows, such as the unit tests.

    Bars that are undated, non-daily, unclassifiable or have a non-finite close
    are skipped. For a repeated (key, type, date) the first row wins and the
    conflict is counted, so the index never pretends two values were one.
    """
    raw, adj = {}, {}          # key -> {date: close}
    raw_symbols, asset_ids = {}, {}
    conflicts, zero_raw = {}, {}

    for row in rows:
        if str(row.get("resolution")) != "D":
            continue
        key = symbol_key(row.get("symbol"))
        if not key:
            continue
        typ = series_type(row)
        if typ is None:
            continue
        day = str(row.get("date") or "")
        if not day:
            continue
        try:
            close = float(row["close"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(close):
            continue

        raw_symbols.setdefault(key, set()).add(str(row.get("symbol")))
        aid = row.get("asset_id")
        if aid not in (None, ""):
            asset_ids.setdefault(key, set()).add(str(aid))
        target = raw if typ == "type0" else adj
        days = target.setdefault(key, {})
        if day in days:
            if days[day] != close:
                conflicts[key] = conflicts.get(key, 0) + 1
            continue
        days[day] = close

    out = {}
    for key in sorted(set(raw) | set(adj)):
        rr = raw.get(key, {})
        aa = adj.get(key, {})
        common = sorted(set(rr) & set(aa))

        previous = None
        exact = within = changes = zero = undefined = 0
        factor_days = 0
        events = []
        for day in common:
            if rr[day] == 0:
                zero += 1
                continue
            factor = aa[day] / rr[day]
            if not math.isfinite(factor):
                continue
            factor_days += 1
            if previous is not None:
                if previous == 0:
                    # A zero adjusted level makes the step ratio undefined;
                    # count it for the audit instead of dividing by zero.
                    undefined += 1
                else:
                    ratio = factor / previous
                    if not math.isfinite(ratio):
                        undefined += 1
                    elif ratio == 1.0:
                        exact += 1
                    elif abs(ratio - 1.0) > FACTOR_EXACT:
                        events.append({"date": day, "factor": factor,
                                       "ratio_change": ratio})
                        changes += 1
                    else:
                        within += 1
            previous = factor
        zero_raw[key] = zero

        spellings = sorted(raw_symbols.get(key, ()))
        out[key] = {
            "key": key,
            "source": source,
            "capture_sha256": capture_sha256,
            "symbol": min(spellings, key=lambda s: (len(s), s))
            if spellings else None,
            "raw_symbols": spellings,
            "asset_ids": sorted(asset_ids.get(key, ())),
            "type0": {"first": min(rr) if rr else None,
                      "last": max(rr) if rr else None, "n": len(rr)},
            "type7": {"first": min(aa) if aa else None,
                      "last": max(aa) if aa else None, "n": len(aa)},
            "factor_days": factor_days,
            "factor_exact": exact,
            "factor_within_0.1pct": within,
            "factor_undefined_ratio": undefined,
            "factor_changes": events,
            "date_conflicts": conflicts.get(key, 0),
            "zero_raw_days": zero,
        }
    return out


def _counts(index, rows):
    return {
        "symbols": len(index),
        "rows": len(rows),
        "daily_rows": sum(1 for r in rows
                          if str(r.get("resolution")) == "D"),
        "type0_series": sum(1 for r in index.values() if r["type0"]["n"]),
        "type7_series": sum(1 for r in index.values() if r["type7"]["n"]),
        "factor_days": sum(r["factor_days"] for r in index.values()),
        "factor_exact": sum(r["factor_exact"] for r in index.values()),
        "factor_within_0.1pct": sum(r["factor_within_0.1pct"]
                                    for r in index.values()),
        "factor_undefined_ratio": sum(r["factor_undefined_ratio"]
                                      for r in index.values()),
        "factor_changes": sum(len(r["factor_changes"])
                              for r in index.values()),
        "multi_spelling_symbols": sum(1 for r in index.values()
                                      if len(r["raw_symbols"]) > 1),
        "date_conflicts": sum(r["date_conflicts"] for r in index.values()),
        "zero_raw_days": sum(r["zero_raw_days"] for r in index.values()),
        "factor_threshold": FACTOR_EXACT,
    }


def build(capture, normalized, out, manifest=""):
    """Import one capture, write the index, and optionally the stage manifest."""
    capture = _abs(capture)
    normalized = _abs(normalized)
    out = _abs(out)
    if not os.path.isfile(capture):
        raise FileNotFoundError("capture not found: %s" % capture)
    if not os.path.isfile(IMPORT):
        raise FileNotFoundError("importer not found: %s" % IMPORT)

    os.makedirs(normalized, exist_ok=True)
    subprocess.check_call([sys.executable, IMPORT, "--in", capture,
                           "--out", normalized])

    bars_path = os.path.join(normalized, "bars.ndjson.gz")
    rows, bars_sha256 = read_bars(bars_path)

    index = build_index(rows, source=_rel(capture), capture_sha256=bars_sha256)
    _write_json(out, index)
    counts = _counts(index, rows)
    if manifest:
        PM.write_manifest(
            "stage02_import_reference",
            [_rel(capture), _rel(IMPORT), _rel(bars_path)],
            [_rel(out)], counts, _abs(manifest))
    return index, counts


def _safe_stdout():
    """Never let a non-UTF-8 console turn a printed count into a crash."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--capture", required=True, help="capture JSON (gitignored)")
    ap.add_argument("--normalized", required=True,
                    help="importer output directory (gitignored)")
    ap.add_argument("--out", required=True,
                    help="reference index JSON (gitignored area)")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST,
                    help="stage manifest path ('' disables)")
    a = ap.parse_args(argv)

    _safe_stdout()
    os.chdir(ROOT)
    try:
        index, counts = build(a.capture, a.normalized, a.out, a.manifest)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print("IMPORT REFERENCE FAIL: %s" % exc, file=sys.stderr)
        return 2

    print("reference index: %d symbols -> %s" % (len(index), _rel(a.out)))
    print(json.dumps(counts, ensure_ascii=False, indent=1, sort_keys=True))
    if a.manifest:
        print("REFERENCE INDEX MANIFEST: %s" % _rel(a.manifest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
