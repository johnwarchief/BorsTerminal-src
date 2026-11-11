#!/usr/bin/env python3
"""Tests for stage02b_merge_reference.

The cases are synthetic so the test never needs the gitignored owner capture:

* bars: a repeated row is dropped as a duplicate, a same-key row with different
  values is counted as a conflict and the first stream wins, and extra-capture
  rows of a symbol already covered by the full capture are excluded;
* index: the extra record of an already-covered symbol is dropped (full wins),
  a new extra symbol is added, and the kept record keeps its provenance and its
  exact sequence counters (never a sum of two records); a fuller batch record
  replaces a shorter one and the overlap reports the real kinds;
* determinism: two runs over the same inputs produce the same payload hash,
  container hash and row sequence.
"""
import gzip
import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage02_import_reference as S  # noqa: E402
import stage02b_merge_reference as M  # noqa: E402


def row(symbol, typ, adjust, date, close, resolution="D", asset_id=1):
    return {"asset_id": asset_id, "symbol": symbol, "resolution": resolution,
            "type": typ, "basis": "real_close", "adjust": adjust,
            "date": date, "open": close, "high": close, "low": close,
            "close": close, "volume": 1}


def write_bars(path, rows):
    """Write rows the way import_capture writes them: sorted, NDJSON, LF."""
    rows = sorted(rows, key=M.bar_key)
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as fh:
        for item in rows:
            fh.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def write_index(path, rows, source, capture_sha256):
    index = S.build_index(rows, source=source,
                          capture_sha256=capture_sha256)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    return path, index


def build_fixture(tmp):
    a = "AAA"
    b = "BBB"
    extra = "EXTRA"

    batch1 = [
        row(a, "type0", "raw", "2020-01-01", 100),
        row(a, "type7", "adjusted", "2020-01-01", 100),
        row(a, "type0", "raw", "2020-01-02", 100),
        row(a, "type7", "adjusted", "2020-01-02", 90),
    ]
    batch2 = [
        row(a, "type0", "raw", "2020-01-01", 100),   # identical repeat
        row(a, "type7", "adjusted", "2020-01-01", 100),  # identical repeat
        row(a, "type0", "raw", "2020-01-02", 101),   # conflict: batch 1 wins
        row(b, "type0", "raw", "2020-01-01", 50, asset_id=2),
        row(b, "type7", "adjusted", "2020-01-01", 50, asset_id=2),
    ]
    extra_rows = [
        row(a, "type0", "raw", "2020-01-01", 999),   # existing symbol: skip
        row(extra, "type0", "raw", "2020-01-01", 10, asset_id=99),
        row(extra, "type7", "adjusted", "2020-01-01", 10, asset_id=99),
        row(extra, "type0", "raw", "2020-01-01", 11, resolution="M",
            asset_id=99),
        row(extra, "type7", "adjusted", "2020-01-01", 11, resolution="M",
            asset_id=99),
    ]

    bars1 = write_bars(os.path.join(tmp, "bars-1.ndjson.gz"), batch1)
    bars2 = write_bars(os.path.join(tmp, "bars-2.ndjson.gz"), batch2)
    barsx = write_bars(os.path.join(tmp, "bars-extra.ndjson.gz"), extra_rows)
    idx1, _ = write_index(os.path.join(tmp, "index-1.json"), batch1,
                          "capture-1.json", "sha-1")
    idx2, _ = write_index(os.path.join(tmp, "index-2.json"), batch2,
                          "capture-2.json", "sha-2")
    idxx, _ = write_index(os.path.join(tmp, "index-extra.json"), extra_rows,
                          "capture-extra.json", "sha-extra")
    return [bars1, bars2], barsx, [idx1, idx2], idxx


def merge_case():
    tmp = tempfile.mkdtemp()
    try:
        batch_bars, extra_bars, batch_index, extra_index = build_fixture(tmp)
        counts = M.merge(batch_bars, batch_index,
                         os.path.join(tmp, "bars-all.ndjson.gz"),
                         os.path.join(tmp, "index-all.json"),
                         extra_bars, extra_index)
        bars = counts["bars"]
        assert bars["rows"] == 10, bars
        assert bars["duplicates_dropped"] == 2, bars
        assert bars["conflicting_duplicates"] == 1, bars
        assert bars["per_resolution"] == {"D": 8, "M": 2}, bars
        assert counts["symbols_merged"] == 3, counts
        assert counts["symbols_full"] == 2, counts
        assert counts["symbols_extra_added"] == 1, counts
        assert counts["symbols_extra_overlapping"] == 1, counts
        assert len(counts["index_overlaps"]) == 2, counts["index_overlaps"]
        kinds = sorted((o["kept_kind"], o["dropped_kind"])
                       for o in counts["index_overlaps"])
        assert kinds == [("batch", "batch"), ("batch", "extra")], kinds

        with gzip.open(os.path.join(tmp, "bars-all.ndjson.gz"), "rt",
                       encoding="utf-8") as fh:
            written = [json.loads(line) for line in fh if line.strip()]
        assert len(written) == 10, written
        first_day = [r for r in written if r["symbol"] == "AAA"
                     and r["type"] == "type0" and r["date"] == "2020-01-02"]
        assert len(first_day) == 1 and first_day[0]["close"] == 100, first_day
        assert not any(r["symbol"] == "AAA" and r["close"] == 999
                       for r in written), written
        # deterministic order: sorted by the importer key
        assert [M.bar_key(r) for r in written] == \
            sorted(M.bar_key(r) for r in written), written

        index = json.load(open(os.path.join(tmp, "index-all.json"),
                               encoding="utf-8"))
        assert list(index) == ["aaa", "bbb", "extra"], index
        aaa = index["aaa"]
        assert aaa["capture_sha256"] == "sha-1", aaa
        assert aaa["source"] == "capture-1.json", aaa
        assert len(aaa["factor_changes"]) == 1, aaa
        assert abs(aaa["factor_changes"][0]["factor"] - 0.9) < 1e-12, aaa
        assert index["bbb"]["capture_sha256"] == "sha-2", index["BBB"]
        assert index["extra"]["capture_sha256"] == "sha-extra", index["EXTRA"]
        assert index["extra"]["type7"]["n"] == 1, index["EXTRA"]

        counts2 = M.merge(batch_bars, batch_index,
                          os.path.join(tmp, "bars-all-2.ndjson.gz"),
                          os.path.join(tmp, "index-all-2.json"),
                          extra_bars, extra_index)
        assert counts2["bars"]["payload_sha256"] == bars["payload_sha256"]
        assert counts2["bars"]["container_sha256"] == bars["container_sha256"]
        print("  merge case OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def capture_doc(captured_at, rows):
    """A minimal capture in the driver's shape, one series per (symbol, type)."""
    series = []
    for symbol, asset_id in sorted({(r["symbol"], r["asset_id"])
                                    for r in rows}):
        for typ, adjust in (("type0", "raw"), ("type7", "adjusted")):
            bars = [{"utc": r["date"] + "T00:00:00Z", "open": r["close"],
                     "high": r["close"], "low": r["close"],
                     "close": r["close"], "volume": 1}
                    for r in rows
                    if r["symbol"] == symbol and r["type"] == typ]
            series.append({"asset_id": asset_id, "symbol": symbol,
                           "ticker": "exchange.asset:%d:real_close:%s"
                                     % (asset_id, typ),
                           "basis": "real_close", "adjust": adjust,
                           "resolution": "D", "status": 200, "bars": bars})
    return {
        "source": {"kind": "synthetic", "endpoint": "none",
                   "session": "test", "captured_at": captured_at,
                   "browser": "synthetic", "types": ["type0", "type7"],
                   "resolutions": ["D"], "countback": 2,
                   "from": "2020-01-01T00:00:00Z",
                   "to": "2020-01-02T00:00:00Z",
                   "license": "synthetic test"},
        "series": series,
    }


def summary_case():
    tmp = tempfile.mkdtemp()
    try:
        a, b, extra = "AAA", "BBB", "EXTRA"
        batch1 = [row(a, "type0", "raw", "2020-01-01", 100),
                  row(a, "type7", "adjusted", "2020-01-01", 100)]
        batch2 = [row(b, "type0", "raw", "2020-01-01", 50, asset_id=2),
                  row(b, "type7", "adjusted", "2020-01-01", 50, asset_id=2)]
        extra_rows = [row(extra, "type0", "raw", "2020-01-01", 10,
                          asset_id=99),
                      row(extra, "type7", "adjusted", "2020-01-01", 10,
                          asset_id=99)]
        batches = []
        for name, rows, stamp in (("one", batch1, "2026-11-10T23:00:00Z"),
                                  ("two", batch2, "2026-11-11T00:00:00Z")):
            capture = os.path.join(tmp, "capture-%s.json" % name)
            with open(capture, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(capture_doc(stamp, rows), fh, ensure_ascii=False)
            normalized = os.path.join(tmp, "normalized-" + name)
            index = os.path.join(tmp, "index-" + name + ".json")
            S.build(capture, normalized, index, "")
            batches.append((capture, os.path.join(normalized,
                                                  "bars.ndjson.gz"), index))
        extra_capture = os.path.join(tmp, "capture-extra.json")
        with open(extra_capture, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(capture_doc("2026-11-10T11:00:00Z", extra_rows), fh,
                      ensure_ascii=False)
        extra_normalized = os.path.join(tmp, "normalized-extra")
        extra_index = os.path.join(tmp, "index-extra.json")
        S.build(extra_capture, extra_normalized, extra_index, "")

        summary_path = os.path.join(tmp, "capture-summary.json")
        counts = M.merge(
            [b[1] for b in batches], [b[2] for b in batches],
            os.path.join(tmp, "bars-all.ndjson.gz"),
            os.path.join(tmp, "index-all.json"),
            os.path.join(extra_normalized, "bars.ndjson.gz"), extra_index,
            captures=[b[0] for b in batches], extra_capture=extra_capture,
            summary_out=summary_path)
        summary = json.load(open(summary_path, encoding="utf-8"))
        assert summary["failures"] == [], summary
        assert summary["totals"]["batches"] == 2, summary["totals"]
        assert summary["totals"]["series"] == 4, summary["totals"]
        assert summary["totals"]["symbols"] == 2, summary["totals"]
        assert summary["totals"]["raw_bars"] == 4, summary["totals"]
        assert summary["totals"]["merged_symbols"] == 3, summary["totals"]
        assert summary["capture"]["captured_at_min"] == \
            "2026-11-10T23:00:00Z", summary["capture"]
        assert summary["capture"]["captured_at_max"] == \
            "2026-11-11T00:00:00Z", summary["capture"]
        expected = hashlib.sha256(
            (summary["batches"][0]["sha256"]
             + summary["batches"][1]["sha256"]).encode("ascii")).hexdigest()
        assert summary["merged"]["aggregate_capture_sha256"] == expected
        assert summary["extra"]["added_symbols"] == ["extra"], summary["extra"]
        assert summary["extra"]["symbols"] == 1, summary["extra"]
        assert summary["merged"]["bars_payload_sha256"] == \
            counts["bars"]["payload_sha256"], summary["merged"]
        pinned = summary["merged"]["reference_index_all"]
        index_path = os.path.join(tmp, "index-all.json")
        with open(index_path, "rb") as fh:
            index_sha = hashlib.sha256(fh.read()).hexdigest()
        assert pinned["file"].endswith("index-all.json"), pinned
        assert pinned["sha256"] == index_sha, pinned
        assert pinned["symbols"] == 3, pinned
        assert pinned["factor_days"] == 3, pinned
        assert pinned["factor_changes"] == 0, pinned
        print("  summary case OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def overlap_case():
    """A fuller batch record wins; the report names the real kinds."""
    tmp = tempfile.mkdtemp()
    try:
        short = [
            row("AAA", "type0", "raw", "2020-01-01", 100),
            row("AAA", "type0", "raw", "2020-01-02", 100),
            row("AAA", "type7", "adjusted", "2020-01-01", 100),
            row("AAA", "type7", "adjusted", "2020-01-02", 90),
        ]
        full = short + [
            row("AAA", "type0", "raw", "2020-01-03", 100),
            row("AAA", "type7", "adjusted", "2020-01-03", 90),
        ]
        _, short_idx = write_index(os.path.join(tmp, "index-short.json"),
                                   short, "capture-short.json", "sha-short")
        _, full_idx = write_index(os.path.join(tmp, "index-full.json"),
                                  full, "capture-full.json", "sha-full")
        merged, overlaps = M.merge_indexes(
            [("short", short_idx), ("full", full_idx)], [])
        assert len(overlaps) == 1, overlaps
        assert overlaps[0] == {
            "key": "aaa",
            "kept_source": "capture-full.json",
            "dropped_source": "capture-short.json",
            "kept_kind": "batch",
            "dropped_kind": "batch",
        }, overlaps[0]
        aaa = merged["aaa"]
        assert aaa["capture_sha256"] == "sha-full", aaa
        assert aaa["factor_days"] == 3, aaa
        assert len(aaa["factor_changes"]) == 1, aaa
        print("  overlap case OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    merge_case()
    summary_case()
    overlap_case()
    print("MERGE REFERENCE TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
