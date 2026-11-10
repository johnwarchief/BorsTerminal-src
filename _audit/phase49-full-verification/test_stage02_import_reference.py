#!/usr/bin/env python3
"""Tests for stage02_import_reference.

Four synthetic cases plus one real-fixture case:

* the brief's case: one 0.9 factor step on two daily bars;
* the frozen 0.1% boundary: 0.0999% is not a step, 0.1001% is a step in both
  directions;
* symbol identity: Arabic-kaf and Persian-kaf spellings of one symbol join on
  ``dev.symbol_identity.key``, and the record carries the key plus the raw
  spellings;
* an end-to-end CLI run over a synthetic capture in a temp dir - the real
  owner-session capture is B10's checkpoint and must not be required here;
* capture-7 from the local phase49 run when it exists, skipped cleanly when it
  does not (fresh clone / CI).
"""
import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage02_import_reference as S  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
CAPTURE_7 = os.path.join(ROOT, "_audit", "phase49-finalization", "rahavard",
                         "capture-7.json")

ALEF = "\u0627\u0644\u0641"
BE = "\u0628"
JIM = "\u062c"
DAL = "\u062f"
KAF_AR = "\u0643\u062a\u0648"   # Arabic kaf
KAF_FA = "\u06a9\u062a\u0648"   # Persian kaf


def row(symbol, typ, adjust, date, close, resolution="D", asset_id=1):
    return {"symbol": symbol, "asset_id": asset_id, "type": typ,
            "adjust": adjust, "resolution": resolution, "date": date,
            "close": close}


def brief_case():
    rows = [
        row(ALEF, "type0", "raw", "2020-01-01", 100),
        row(ALEF, "type0", "raw", "2020-01-02", 100),
        row(ALEF, "type7", "adjusted", "2020-01-01", 100),
        row(ALEF, "type7", "adjusted", "2020-01-02", 90),
    ]
    idx = S.build_index(rows)
    ch = idx[ALEF]["factor_changes"]
    assert len(ch) == 1, ch
    assert ch[0]["date"] == "2020-01-02"
    assert abs(ch[0]["factor"] - 0.9) < 1e-12
    assert abs(ch[0]["ratio_change"] - 0.9) < 1e-12
    assert idx[ALEF]["type0"] == {"first": "2020-01-01",
                                  "last": "2020-01-02", "n": 2}
    assert idx[ALEF]["type7"] == {"first": "2020-01-01",
                                  "last": "2020-01-02", "n": 2}
    # audit counters: one transition, no exact/within transition
    assert idx[ALEF]["factor_days"] == 2, idx[ALEF]
    assert idx[ALEF]["factor_exact"] == 0, idx[ALEF]
    assert idx[ALEF]["factor_within_0.1pct"] == 0, idx[ALEF]
    print("  brief case OK")


def threshold_case():
    """0.0999% is not a step; 0.1001% is; both directions; exact repeats."""
    raw = 1000000
    cases = {
        ALEF: [raw, 1000999],          # +0.0999% -> within, not a step
        BE: [raw, 1001001],            # +0.1001% -> step up
        JIM: [raw, 998999],            # -0.1001% -> step down
        DAL: [raw, raw, 2 * raw, 2 * raw],  # exact, step, exact
    }
    rows = []
    for sym, values in cases.items():
        for i, value in enumerate(values):
            date = "2020-01-%02d" % (i + 1)
            rows.append(row(sym, "type0", "raw", date, raw))
            rows.append(row(sym, "type7", "adjusted", date, value))
    idx = S.build_index(rows)

    above = idx[ALEF]
    assert above["factor_changes"] == [], above
    assert above["factor_within_0.1pct"] == 1, above
    assert abs(above["factor_days"] - 2) == 0, above

    up = idx[BE]["factor_changes"]
    assert len(up) == 1, up
    assert up[0]["date"] == "2020-01-02", up
    assert abs(up[0]["ratio_change"] - 1.001001) < 1e-12, up
    assert abs(up[0]["ratio_change"] - 1.0) > S.FACTOR_EXACT, up

    down = idx[JIM]["factor_changes"]
    assert len(down) == 1, down
    assert abs(down[0]["ratio_change"] - 0.998999) < 1e-12, down
    assert abs(down[0]["ratio_change"] - 1.0) > S.FACTOR_EXACT, down

    mixed = idx[DAL]
    assert mixed["factor_exact"] == 2, mixed
    assert mixed["factor_within_0.1pct"] == 0, mixed
    assert len(mixed["factor_changes"]) == 1, mixed
    assert abs(mixed["factor_changes"][0]["factor"] - 2.0) < 1e-12, mixed
    assert (mixed["factor_exact"] + mixed["factor_within_0.1pct"]
            + len(mixed["factor_changes"]) == mixed["factor_days"] - 1), mixed
    print("  threshold case OK")


def key_join_case():
    """One security, two kaf spellings, one record carrying both identities."""
    rows = [
        row(KAF_AR, "type0", "raw", "2020-01-01", 100),
        row(KAF_AR, "type0", "raw", "2020-01-02", 100),
        row(KAF_FA, "type7", "adjusted", "2020-01-01", 100),
        row(KAF_FA, "type7", "adjusted", "2020-01-02", 90),
        # a weekly bar with a different close must not enter the daily index
        row(KAF_FA, "type7", "adjusted", "2020-01-03", 1, resolution="W"),
    ]
    assert S.symbol_key(KAF_AR) == S.symbol_key(KAF_FA)
    idx = S.build_index(rows)
    assert list(idx) == [S.symbol_key(KAF_FA)], idx
    rec = idx[S.symbol_key(KAF_FA)]
    assert rec["key"] == S.symbol_key(KAF_FA), rec
    assert rec["symbol"] in (KAF_AR, KAF_FA), rec
    assert set(rec["raw_symbols"]) == {KAF_AR, KAF_FA}, rec
    assert rec["type0"]["n"] == 2 and rec["type7"]["n"] == 2, rec
    assert len(rec["factor_changes"]) == 1, rec
    print("  key join case OK")


def make_capture(path):
    doc = {
        "source": {"kind": "synthetic-b3", "endpoint": "none",
                   "captured_at": "2026-11-10T00:00:00Z",
                   "browser": "synthetic", "types": ["type0", "type7"],
                   "resolutions": ["D"], "countback": 2,
                   "from": "2020-01-01T00:00:00Z",
                   "to": "2020-01-02T00:00:00Z"},
        "series": [
            {"symbol": ALEF, "asset_id": 1, "adjust": "raw",
             "resolution": "D", "basis": "real_close",
             "ticker": "exchange.asset:1:real_close:type0",
             "bars": [{"utc": "2020-01-01T00:00:00Z", "open": 100,
                       "high": 100, "low": 100, "close": 100, "volume": 1},
                      {"utc": "2020-01-02T00:00:00Z", "open": 100,
                       "high": 100, "low": 100, "close": 100, "volume": 1}]},
            {"symbol": ALEF, "asset_id": 1, "adjust": "adjusted",
             "resolution": "D", "basis": "real_close",
             "ticker": "exchange.asset:1:real_close:type7",
             "bars": [{"utc": "2020-01-01T00:00:00Z", "open": 100,
                       "high": 100, "low": 100, "close": 100, "volume": 1},
                      {"utc": "2020-01-02T00:00:00Z", "open": 90,
                       "high": 90, "low": 90, "close": 90, "volume": 1}]},
        ],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    return path


def run_cli(capture, tmp):
    normalized = os.path.join(tmp, "normalized")
    out = os.path.join(tmp, "reference-index.json")
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "stage02_import_reference.py"),
         "--capture", capture, "--normalized", normalized, "--out", out,
         "--manifest", ""],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    return normalized, out, proc


def cli_case():
    """A small synthetic capture in a temp dir exercises the whole CLI."""
    tmp = tempfile.mkdtemp()
    try:
        capture = make_capture(os.path.join(tmp, "capture.json"))
        normalized, out, proc = run_cli(capture, tmp)
        for name in ("bars.ndjson.gz", "coverage.json", "summary.json"):
            assert os.path.isfile(os.path.join(normalized, name)), name
        with gzip.open(os.path.join(normalized, "bars.ndjson.gz"), "rt",
                       encoding="utf-8") as fh:
            written = [json.loads(line) for line in fh if line.strip()]
        assert len(written) == 4, written
        assert "reference index: 1 symbols" in proc.stdout, proc.stdout
        idx = json.load(open(out, encoding="utf-8"))
        assert len(idx) == 1 and ALEF in idx, idx
        assert idx[ALEF]["type0"]["n"] == 2, idx[ALEF]
        assert abs(idx[ALEF]["factor_changes"][0]["ratio_change"] - 0.9) < 1e-12
        print("  cli case OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def real_case():
    if not os.path.isfile(CAPTURE_7):
        print("SKIP real fixture: capture-7.json missing (gitignored)")
        return
    tmp = tempfile.mkdtemp()
    try:
        normalized, out, proc = run_cli(CAPTURE_7, tmp)
        idx = json.load(open(out, encoding="utf-8"))
        assert len(idx) == 7, idx
        for key, rec in idx.items():
            assert rec["key"] == key == S.symbol_key(rec["symbol"]), rec
            assert rec["raw_symbols"], rec
            assert rec["type0"]["n"] > 0 and rec["type7"]["n"] > 0, rec
            assert (rec["factor_exact"] + rec["factor_within_0.1pct"]
                    + len(rec["factor_changes"]) == rec["factor_days"] - 1), rec
        assert sum(len(r["factor_changes"]) for r in idx.values()) > 0, idx
        print("  real fixture OK (7 symbols, %d changes)"
              % sum(len(r["factor_changes"]) for r in idx.values()))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    brief_case()
    threshold_case()
    key_join_case()
    cli_case()
    real_case()
    print("REFERENCE INDEX TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
