#!/usr/bin/env python3
"""Stage 02b - merge the per-batch reference imports into one reference set.

Stage 02 imports each capture batch on its own. This stage joins the stage-02
results without re-importing any bars and without loading 5.2M rows into
memory:

* ``--batch-bars`` / ``--extra-bars`` are the importer's ``bars.ndjson.gz``
  files. Each one is already sorted by ``(asset_id, resolution, type, date)``.
  The merge is a stable k-way merge over those sorted streams, so the output is
  deterministic and duplicates can be dropped with one adjacent-key compare.
  The key is the importer's dedupe key; on a repeated key the first stream wins
  (batch order first, extra last) and a same-key/different-row case is counted
  as a conflict, never silently merged.
* ``--batch-index`` / ``--extra-index`` are the stage-02 factor indexes. Their
  counters describe a *sequence* of daily factors (``factor_days`` minus one
  transitions split into exact / within 0.1% / undefined / changes), so two
  records of one symbol cannot be combined by summing counters: the boundary
  transition would be invented and the events list would lose its order. The
  merge therefore keeps exactly one record per normalised symbol key. A
  full-capture record always beats an extra record (the extra capture exists
  only to add symbols the full capture lacks); between two full records the one
  covering more bars wins, and a tie keeps the first. Every overlap is listed
  in the report instead of being dropped silently.

Provenance is not rewritten: each kept record still carries the ``source`` and
``capture_sha256`` stage 02 stamped on it, so the merged index can be traced to
the batch that fed it.

``--summary-out`` (with one ``--capture`` per batch) also writes the small
tracked capture summary: per-batch file SHA-256/size, captured_at, series,
symbols and raw bar counts, the aggregate capture digest, the merged counts and
an explicitly empty failure list. This path does ``json.load`` each raw capture
once, so the bars pass through memory to be counted, but only counts and the
safe ``source`` block are emitted: the summary carries no raw series, cookies,
tokens or account ids. The bar merge never opens a capture; only this summary
path does, and only to count.

CLI:
    python _audit/phase49-full-verification/stage02b_merge_reference.py \\
        --batch-bars captures/normalized-batch-01/bars.ndjson.gz ... \\
        --batch-index captures/reference-index-batch-01.json ... \\
        --extra-bars captures/normalized-extra/bars.ndjson.gz \\
        --extra-index captures/reference-index-extra.json \\
        --out-bars captures/bars-all.ndjson.gz \\
        --out-index captures/reference-index-all.json \\
        [--capture captures/capture-batch-01.json ... --extra-capture ... \\
         --summary-out evidence/capture-summary.json]

Outputs belong in the gitignored ``captures/`` area. Stdlib only.
"""
import argparse
import gzip
import hashlib
import heapq
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DEV = os.path.join(ROOT, "dev")
if DEV not in sys.path:
    sys.path.insert(0, DEV)

import phase49_manifest as PM  # noqa: E402
from symbol_identity import key as symbol_key  # noqa: E402


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


def bar_key(row):
    """The importer's identity key, as a sortable tuple of strings."""
    return (str(row.get("asset_id")), str(row.get("resolution")),
            str(row.get("type")), str(row.get("date")))


def iter_bars(path, allowed_symbols=None, stats=None):
    """Yield parsed bars from one normalised gzip, asserting sorted order.

    ``allowed_symbols`` filters on ``dev.symbol_identity.key``; rows of other
    symbols are counted in ``stats["rows_filtered"]``. Filtering keeps the
    stream sorted, because it only removes rows of whole symbols.
    """
    stats = stats if stats is not None else {}
    stats.setdefault("rows_in", 0)
    stats.setdefault("rows_filtered", 0)
    previous = None
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            stats["rows_in"] += 1
            if allowed_symbols is not None and \
                    symbol_key(row.get("symbol")) not in allowed_symbols:
                stats["rows_filtered"] += 1
                continue
            key = bar_key(row)
            if previous is not None and key < previous:
                raise ValueError("bars not sorted by (asset_id, resolution, "
                                 "type, date): %s at %r after %r"
                                 % (path, key, previous))
            previous = key
            yield row


def merge_bars(inputs, out_path):
    """Merge sorted bar streams into one deterministic gzip.

    ``inputs`` is an ordered list of ``(path, allowed_symbols_or_None, stats)``.
    The first stream wins a key conflict; identical repeats are counted as
    duplicates. Returns the report counters.
    """
    streams = [iter_bars(path, allowed, stats)
               for path, allowed, stats in inputs]
    merged = heapq.merge(*streams, key=bar_key)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    payload_hash = hashlib.sha256()
    last_key = None
    last_row = None
    report = {"rows": 0, "duplicates_dropped": 0, "conflicting_duplicates": 0,
              "per_resolution": {}, "per_type": {},
              "first_date": None, "last_date": None}
    with open(out_path, "wb") as raw:
        # mtime=0 keeps the gzip header stable across runs, so the container
        # hash is reproducible too; the payload hash below is the real anchor.
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw,
                           compresslevel=9, mtime=0) as gz:
            for row in merged:
                key = bar_key(row)
                if key == last_key:
                    if row == last_row:
                        report["duplicates_dropped"] += 1
                    else:
                        report["conflicting_duplicates"] += 1
                    continue
                data = (json.dumps(row, ensure_ascii=False, sort_keys=True)
                        + "\n").encode("utf-8")
                gz.write(data)
                payload_hash.update(data)
                report["rows"] += 1
                res = str(row.get("resolution"))
                typ = str(row.get("type"))
                report["per_resolution"][res] = \
                    report["per_resolution"].get(res, 0) + 1
                report["per_type"][typ] = report["per_type"].get(typ, 0) + 1
                day = str(row.get("date") or "")
                if day:
                    if report["first_date"] is None or day < report["first_date"]:
                        report["first_date"] = day
                    if report["last_date"] is None or day > report["last_date"]:
                        report["last_date"] = day
                last_key, last_row = key, row
    report["per_resolution"] = dict(sorted(report["per_resolution"].items()))
    report["per_type"] = dict(sorted(report["per_type"].items()))
    report["payload_sha256"] = payload_hash.hexdigest()
    report["container_sha256"] = PM.sha256(out_path)
    return report


def _coverage(record):
    """How much of a symbol's daily sequence a record actually covers."""
    return (record["type0"]["n"] + record["type7"]["n"],
            record["type7"]["n"], record["type0"]["n"])


def _check_record(key, record):
    """Guard the stage-02 counter invariant before a record is trusted."""
    transitions = (record["factor_exact"] + record["factor_within_0.1pct"]
                   + record["factor_undefined_ratio"]
                   + len(record["factor_changes"]))
    expected = max(record["factor_days"] - 1, 0)
    if transitions != expected:
        raise ValueError("record %r breaks the factor counter invariant: "
                         "%d transitions vs factor_days=%d"
                         % (key, transitions, record["factor_days"]))


def merge_indexes(batch_indexes, extra_indexes):
    """Union the stage-02 indexes, keeping one exact record per symbol key.

    A batch record wins over an extra record for the same key by policy; two
    batch records of one key keep the fuller sequence (ties keep the first).
    ``factor_changes`` are never concatenated and counters are never summed.

    The overlap entry names the kind of the record that actually won and the
    kind of the record that was dropped. The kind of the previous holder is
    read *before* ``source_kind[key]`` is overwritten, so a replacement is
    attributed to the winner and not to the incoming stream twice.
    """
    merged, overlaps = {}, []
    source_kind = {}
    for kind, path, index in (
            [("batch", p, idx) for p, idx in batch_indexes]
            + [("extra", p, idx) for p, idx in extra_indexes]):
        for key in sorted(index):
            record = index[key]
            _check_record(key, record)
            if key not in merged:
                merged[key] = record
                source_kind[key] = kind
                continue
            kept = merged[key]
            if kind == "extra" or _coverage(record) <= _coverage(kept):
                winner, winner_kind = kept, source_kind[key]
                dropped, dropped_kind = record, kind
            else:
                winner, winner_kind = record, kind
                dropped, dropped_kind = kept, source_kind[key]
                merged[key] = record
                source_kind[key] = kind
            overlaps.append({
                "key": key,
                "kept_source": winner["source"],
                "dropped_source": dropped["source"],
                "kept_kind": winner_kind,
                "dropped_kind": dropped_kind,
            })
    return dict(sorted(merged.items())), overlaps


SOURCE_KEYS = ("kind", "endpoint", "session", "browser", "types",
               "resolutions", "countback", "from", "to", "license")
IMPORT = os.path.join(ROOT, "tools", "phase45", "rahavard",
                      "import_capture.py")
STAGE02 = os.path.join(HERE, "stage02_import_reference.py")


def _normalized_facts(bars_path):
    """Read the importer's ``summary.json`` next to a ``bars.ndjson.gz``."""
    path = os.path.join(os.path.dirname(_abs(bars_path)), "summary.json")
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    return {"series": doc.get("series"),
            "normalized_bars": doc.get("totals", {}).get("rows"),
            "bars_sha256": doc.get("bars_sha256"),
            "capture_sha256": doc.get("capture_sha256"),
            "capture_file": doc.get("capture_file")}


def _capture_facts(path):
    """File identity, ledger counts and the safe ``source`` block of a capture.

    The raw ``bars`` arrays are parsed but never copied; only the ledger counts
    and the source metadata leave this function.
    """
    path = _abs(path)
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    source = doc.get("source") or {}
    series = doc.get("series") or []
    ledger = doc.get("ledger") or []
    from_series = sum(len(s.get("bars") or []) for s in series)
    if ledger:
        from_ledger = sum(int(e.get("bars") or 0) for e in ledger)
        if from_ledger != from_series:
            raise ValueError("ledger/bar count mismatch in %s: %d vs %d"
                             % (_rel(path), from_ledger, from_series))
    symbol_keys = {symbol_key(s.get("symbol")) for s in series}
    return {
        "file": _rel(path),
        "bytes": os.path.getsize(path),
        "sha256": PM.sha256(path),
        "captured_at": source.get("captured_at"),
        "series": len(series),
        "symbols": len(symbol_keys),
        "symbol_keys": symbol_keys,
        "raw_bars": from_series,
        "failed_series": sum(1 for s in series if s.get("status") != 200),
        "empty_series": sum(1 for s in series if not (s.get("bars") or [])),
        "source": {k: source.get(k) for k in SOURCE_KEYS},
    }


def build_capture_summary(captures, batch_bars, extra_capture, counts,
                          out_bars, extra_bars, manifest=""):
    """Build the small tracked summary from capture metadata and merge counts.

    Every per-batch count is cross-checked against the importer's own
    ``summary.json`` (series, bar rows and capture digest); a mismatch raises
    instead of being papered over.
    """
    if len(captures) != len(batch_bars):
        raise ValueError("need one --capture per --batch-bars for --summary-out")
    batch_facts, normalized_totals = [], 0
    symbols = set()
    for capture, bars in zip(captures, batch_bars):
        facts = _capture_facts(capture)
        norm = _normalized_facts(bars)
        if norm["capture_sha256"] != facts["sha256"]:
            raise ValueError("capture changed after import: %s"
                             % facts["file"])
        if norm["series"] != facts["series"]:
            raise ValueError("series mismatch for %s: %r vs %r"
                             % (facts["file"], norm["series"],
                                facts["series"]))
        facts["normalized_bars"] = norm["normalized_bars"]
        facts["normalized_bars_sha256"] = norm["bars_sha256"]
        batch_facts.append(facts)
        normalized_totals += norm["normalized_bars"] or 0
        symbols |= facts.pop("symbol_keys")

    sources = [f["source"] for f in batch_facts]
    capture_block = dict(sources[0])
    for other in sources[1:]:
        if other != sources[0]:
            raise ValueError("capture batches disagree on source metadata")
    capture_block["captured_at_min"] = min(f["captured_at"]
                                           for f in batch_facts)
    capture_block["captured_at_max"] = max(f["captured_at"]
                                           for f in batch_facts)

    aggregate = hashlib.sha256(
        "".join(f["sha256"] for f in batch_facts).encode("ascii")).hexdigest()
    bars = counts["bars"]
    summary = {
        "stage": "phase49-full-verification/reference-capture",
        "raw_capture_committed": False,
        "tracked_files": "only this summary; captures/, normalized bars and "
                         "the merged factor index stay gitignored",
        "capture": capture_block,
        "batches": batch_facts,
        "totals": {
            "batches": len(batch_facts),
            "series": sum(f["series"] for f in batch_facts),
            "symbols": len(symbols),
            "raw_bars": sum(f["raw_bars"] for f in batch_facts),
            "normalized_bars": normalized_totals,
            "merged_bars": bars["rows"],
            "merged_symbols": counts["symbols_merged"],
            "duplicates_dropped": bars["duplicates_dropped"],
            "conflicting_duplicates": bars["conflicting_duplicates"],
            "failed_series": sum(f["failed_series"] for f in batch_facts),
            "empty_series": sum(f["empty_series"] for f in batch_facts),
        },
        "merged": {
            "bars_file": _rel(_abs(out_bars)),
            "index_file": counts["index_file"],
            "reference_index_all": counts["reference_index_all"],
            "bars_payload_sha256": bars["payload_sha256"],
            "bars_container_sha256": bars["container_sha256"],
            "per_resolution": bars["per_resolution"],
            "per_type": bars["per_type"],
            "first_date": bars["first_date"],
            "last_date": bars["last_date"],
            "aggregate_capture_sha256": aggregate,
            "aggregate_capture_definition":
                "sha256 of the concatenated per-batch capture SHA-256 hex "
                "strings, batch order",
        },
        "normalization": {
            "importer": _rel(IMPORT),
            "importer_sha256": PM.sha256(IMPORT),
            "stage02": _rel(STAGE02),
            "stage02_sha256": PM.sha256(STAGE02),
            "bar_identity": "(asset_id, resolution, type, date)",
            "method": "ISO/epoch timestamps to YYYY-MM-DD; one row per key; "
                      "identical repeats dropped, differing repeats counted "
                      "and resolved first-wins; no estimation, missing "
                      "fields stay null",
            "factor_rule": "factor = type7_close / type0_close on common "
                           "daily dates; step when |factor/prev - 1| > 1e-3",
        },
        "failures": [],
    }
    if extra_capture:
        extra = _capture_facts(extra_capture)
        extra.pop("symbol_keys", None)
        extra_norm = _normalized_facts(extra_bars)
        if extra_norm["capture_sha256"] != extra["sha256"]:
            raise ValueError("extra capture changed after import")
        used = [s for s in counts["inputs"][len(captures):]]
        summary["extra"] = {
            "file": extra["file"],
            "bytes": extra["bytes"],
            "sha256": extra["sha256"],
            "captured_at": extra["captured_at"],
            "series": extra["series"],
            "symbols": extra["symbols"],
            "raw_bars": extra["raw_bars"],
            "normalized_bars": extra_norm["normalized_bars"],
            "added_symbols": counts["extra_added_keys"],
            "overlapping_symbols": counts["symbols_extra_overlapping"],
            "bars_merged": sum(s["rows_in"] - s.get("rows_filtered", 0)
                               for s in used),
        }
    if manifest:
        summary["manifest"] = _rel(_abs(manifest))
    return summary


def merge(batch_bars, batch_indexes, out_bars, out_index,
          extra_bars=None, extra_index=None, manifest="",
          captures=None, extra_capture="", summary_out=""):
    """Run the whole merge and optionally write a stage manifest."""
    batch_bars = [_abs(p) for p in batch_bars]
    batch_indexes = [_abs(p) for p in batch_indexes]
    if not batch_bars or len(batch_bars) != len(batch_indexes):
        raise ValueError("need one --batch-index per --batch-bars")
    if bool(extra_bars) != bool(extra_index):
        raise ValueError("--extra-bars and --extra-index go together")

    def _load(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    loaded_batches = [(_rel(p), _load(p)) for p in batch_indexes]
    loaded_extra = []
    if extra_index:
        loaded_extra = [(_rel(_abs(extra_index)), _load(_abs(extra_index)))]

    merged_index, overlaps = merge_indexes(loaded_batches, loaded_extra)
    full_keys = set().union(*(set(idx) for _, idx in loaded_batches))
    extra_keys = set()
    for _, idx in loaded_extra:
        extra_keys |= set(idx)
    allowed_extra = extra_keys - full_keys

    inputs = [(path, None, {"path": _rel(path)}) for path in batch_bars]
    if extra_bars:
        inputs.append((_abs(extra_bars), allowed_extra,
                       {"path": _rel(_abs(extra_bars))}))
    bars_report = merge_bars(inputs, _abs(out_bars))
    _write_json(_abs(out_index), merged_index)
    index_stats = {
        "file": _rel(_abs(out_index)),
        "sha256": PM.sha256(_abs(out_index)),
        "symbols": len(merged_index),
        "factor_days": sum(int(r["factor_days"])
                           for r in merged_index.values()),
        "factor_changes": sum(len(r["factor_changes"])
                              for r in merged_index.values()),
    }

    counts = {
        "symbols_full": len(full_keys),
        "symbols_extra_added": len(allowed_extra),
        "symbols_extra_overlapping": len(extra_keys & full_keys),
        "symbols_merged": len(merged_index),
        "extra_added_keys": sorted(allowed_extra),
        "index_overlaps": overlaps,
        "index_file": _rel(_abs(out_index)),
        "reference_index_all": index_stats,
        "bars": bars_report,
        "inputs": [stats for _, _, stats in inputs],
    }
    if summary_out:
        summary = build_capture_summary(
            captures or [], batch_bars, extra_capture, counts,
            _abs(out_bars), _abs(extra_bars) if extra_bars else "", manifest)
        _write_json(_abs(summary_out), summary)
        counts["summary"] = _rel(_abs(summary_out))
    if manifest:
        PM.write_manifest(
            "stage02b_merge_reference",
            [_rel(p) for p in batch_bars] + [_rel(p) for p in batch_indexes]
            + ([_rel(_abs(extra_bars))] if extra_bars else [])
            + ([_rel(_abs(extra_index))] if extra_index else [])
            + ([_rel(_abs(c)) for c in captures] if captures else [])
            + ([_rel(_abs(extra_capture))] if extra_capture else []),
            [_rel(_abs(out_bars)), _rel(_abs(out_index))]
            + ([_rel(_abs(summary_out))] if summary_out else []),
            {k: v for k, v in counts.items()
             if k not in ("index_overlaps", "inputs", "bars")},
            _abs(manifest))
        counts["manifest"] = _rel(_abs(manifest))
    return counts


def _safe_stdout():
    """Never let a non-UTF-8 console turn a printed count into a crash."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--batch-bars", action="append", default=[],
                    help="normalised bars.ndjson.gz of a full-capture batch")
    ap.add_argument("--batch-index", action="append", default=[],
                    help="stage-02 reference-index.json of the same batch")
    ap.add_argument("--extra-bars", default="",
                    help="normalised bars of the extra capture (optional)")
    ap.add_argument("--extra-index", default="",
                    help="stage-02 index of the extra capture (optional)")
    ap.add_argument("--out-bars", required=True)
    ap.add_argument("--out-index", required=True)
    ap.add_argument("--capture", action="append", default=[],
                    help="full-capture JSON of each batch (for --summary-out)")
    ap.add_argument("--extra-capture", default="",
                    help="capture JSON of the extra import (optional)")
    ap.add_argument("--summary-out", default="",
                    help="write the small tracked capture summary here")
    ap.add_argument("--manifest", default="")
    a = ap.parse_args(argv)

    _safe_stdout()
    os.chdir(ROOT)
    try:
        counts = merge(a.batch_bars, a.batch_index, a.out_bars, a.out_index,
                       a.extra_bars, a.extra_index, a.manifest,
                       a.capture, a.extra_capture, a.summary_out)
    except (OSError, ValueError) as exc:
        print("MERGE REFERENCE FAIL: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(counts, ensure_ascii=False, indent=1, sort_keys=True))
    if a.summary_out:
        print("CAPTURE SUMMARY: %s" % _rel(_abs(a.summary_out)))
    print("REFERENCE MERGE OK: %d symbols, %d bars -> %s"
          % (counts["symbols_merged"], counts["bars"]["rows"],
             _rel(_abs(a.out_bars))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
