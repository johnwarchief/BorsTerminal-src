#!/usr/bin/env python3
"""Prove stage09: the metadata core, the final manifest, the full build,
idempotency, and the refusal rules. Temp databases only; the real seed and the
captures are never touched.
"""
import contextlib
import gzip
import hashlib
import io
import json
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage09_seed_build as S  # noqa: E402


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _memory_db(ref_rows=1):
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE price_history(symbol TEXT,date TEXT,src TEXT)")
    if ref_rows:
        con.execute("INSERT INTO price_history VALUES('الف','2026-01-01','rahavard365')")
    con.execute("INSERT INTO price_history VALUES('الف','2026-01-02','legacy-unknown')")
    return con


def _symbol(symbol="الف", status="VERIFIED_WITH_EVENTS", **overrides):
    row = {"symbol": symbol, "final_status": status, "rows": 2,
           "first_date": "2026-01-01", "last_date": "2026-01-02",
           "factor_steps": 1, "factor_verified": 1,
           "factor_reconstructed": 0, "factor_unverified": 0,
           "ref_coverage": "full", "remaining_blocker": ""}
    row.update(overrides)
    return row


def _brief_test():
    """The brief's case verbatim, plus the table it relies on."""
    con = _memory_db()
    con.execute("CREATE TABLE backfill_rows(run_id TEXT,symbol TEXT,date TEXT)")
    con.execute("INSERT INTO backfill_rows VALUES('r1','الف','2026-01-01')")
    symbols = [_symbol()]
    steps = [{"symbol": "الف", "final_status": "VERIFIED_OFFICIAL"}]
    ref = {"capture_sha256": "abc", "source": {"captured_at": "2026-11-10"}}
    pack = {"version": "v2", "file_sha256": {"factors": "f"}}
    rep = S.build_metadata(con, pack, steps, symbols, ref)
    assert rep["reference_derived_rows"] == 1, rep
    assert con.execute("SELECT status FROM history_validity WHERE symbol='الف'").fetchone()[0] == "verified"
    rep2 = S.build_metadata(con, pack, steps, symbols, ref)
    assert rep2["reference_derived_rows"] == rep["reference_derived_rows"]
    assert con.execute("SELECT COUNT(*) FROM history_validity").fetchone()[0] == 1
    notes = con.execute("SELECT notes FROM history_validity").fetchone()[0]
    assert notes.startswith("VERIFIED_WITH_EVENTS;"), notes
    assert rep["pack_version"] == "v2"
    assert rep["pack_factors_sha256"] == "f"
    assert rep["reference_capture_sha256"] == "abc"
    assert rep["reference_captured_at"] == "2026-11-10"
    assert rep["validity_status_counts"] == {"verified": 1}


def _status_map_test():
    """All six mission statuses land on exactly the three labels."""
    con = _memory_db()
    statuses = sorted(S.STATUS_MAP)
    symbols = [_symbol("س%d" % i, status)
               for i, status in enumerate(statuses)]
    rep = S.build_metadata(con, {}, [], symbols, {})
    got = dict(con.execute("SELECT status, COUNT(*) FROM history_validity "
                           "GROUP BY status"))
    expected = {"verified": 2, "reconstructed_verified": 1, "unverified": 3}
    assert got == expected, got
    assert rep["validity_status_counts"] == expected, rep
    for i, detailed in enumerate(statuses):
        row = con.execute("SELECT status, notes FROM history_validity "
                          "WHERE symbol=?", ("س%d" % i,)).fetchone()
        assert row[0] == S.STATUS_MAP[detailed], (detailed, row)
        assert row[1].startswith(detailed + ";"), (detailed, row)


def _unknown_status_test():
    con = _memory_db()
    for bad in ("CONFLICT_RATIO", "", "verified"):
        try:
            S.build_metadata(con, {}, [], [_symbol(status=bad)], {})
        except ValueError as exc:
            assert "final_status" in str(exc), (bad, str(exc))
        else:
            raise AssertionError("accepted unknown status %r" % (bad,))


def _duplicate_symbol_test():
    con = _memory_db()
    try:
        S.build_metadata(con, {}, [], [_symbol(), _symbol()], {})
    except ValueError as exc:
        assert "duplicate symbol" in str(exc), str(exc)
    else:
        raise AssertionError("accepted a duplicate symbol")


def _symbol_spaces_test():
    """Two ledger symbols carry a significant edge space; keep the exact key."""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE price_history(symbol TEXT,date TEXT,src TEXT)")
    con.execute("INSERT INTO price_history VALUES(' كارون073','2026-01-01','rahavard365')")
    con.execute("INSERT INTO price_history VALUES('معيار ','2026-01-01','rahavard365')")
    symbols = [_symbol(" كارون073"), _symbol("معيار ")]
    rep = S.build_metadata(con, {}, [], symbols, {})
    assert rep["reference_derived_rows"] == 2, rep
    got = {r[0] for r in con.execute("SELECT symbol FROM history_validity")}
    assert got == {" كارون073", "معيار "}, got


def _manifest_storage_test():
    con = _memory_db()
    rep = S.build_metadata(con, {"version": "v2"},
                           [{"symbol": "الف"}], [_symbol()],
                           {"capture_sha256": "abc",
                            "captured_at": "2026-11-10T00:00:00Z"})
    stored = dict(con.execute("SELECT key, value FROM seed_manifest"))
    for key in ("schema", "pack_version", "pack_factors_sha256",
                "reference_derived_rows", "reference_capture_sha256",
                "reference_captured_at", "validity_status_counts",
                "adjustment_step_ledger_rows", "adjustment_step_ledger_symbols"):
        assert key in stored, (key, sorted(stored))
    assert stored["schema"] == S.SEED_SCHEMA
    assert json.loads(stored["validity_status_counts"]) == {"verified": 1}
    assert stored["adjustment_step_ledger_rows"] == "1"
    assert stored["adjustment_step_ledger_symbols"] == "1"
    assert rep["reference_captured_at"] == "2026-11-10T00:00:00Z"


def _write_csv(path, header, rows):
    import csv
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _make_pack(path, factors=b"{}\n", raw=b"{}\n", bad_hash=False):
    os.makedirs(path, exist_ok=True)
    factors_path = os.path.join(path, "factors.jsonl")
    raw_path = os.path.join(path, "raw_ohlc.jsonl")
    with open(factors_path, "wb") as fh:
        fh.write(factors)
    with open(raw_path, "wb") as fh:
        fh.write(raw)
    manifest = {
        "schema": "ra365-correction-pack-v1",
        "version": "ra365-test-v2",
        "mode": "authoritative",
        "as_of": "2026-10-25",
        "reference_sha256": "ref",
        "files": {"factors": "factors.jsonl", "raw_ohlc": "raw_ohlc.jsonl"},
        "file_sha256": {"factors": _sha(factors_path),
                        "raw_ohlc": _sha(raw_path)},
        "counts": {"symbols": 2, "steps": 3, "verified_steps": 1,
                   "reconstructed_verified_steps": 1, "unverified_steps": 1,
                   "invalid_dropped_steps": 0},
    }
    if bad_hash:
        manifest["file_sha256"]["factors"] = "0" * 64
    with open(os.path.join(path, "manifest.json"), "w", encoding="utf-8",
              newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    return manifest


def _make_db(path, rows, corrections=2, user=True, duplicate=False):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE price_history(symbol TEXT,date TEXT,src TEXT)")
    for row in rows:
        con.execute("INSERT INTO price_history VALUES(?,?,?)", row)
    if duplicate:
        con.execute("INSERT INTO price_history VALUES('الف','2026-01-01','board')")
    con.execute("CREATE TABLE raw_history_corrections(run_id TEXT,symbol TEXT,date TEXT)")
    for i in range(corrections):
        con.execute("INSERT INTO raw_history_corrections VALUES(?,?,?)",
                    ("r1", "الف", "2026-01-0%d" % (i + 1)))
    con.execute("CREATE TABLE instruments(symbol TEXT)")
    con.execute("INSERT INTO instruments VALUES('الف')")
    if user:
        con.execute("CREATE TABLE user_watchlists(symbol_norm TEXT PRIMARY KEY,"
                    " symbol TEXT, name TEXT, note TEXT, added_at TEXT)")
        con.execute("INSERT INTO user_watchlists VALUES('الف','الف','','','')")
    con.commit()
    con.close()


def _fixture(tmp):
    base = os.path.join(tmp, "base.db")
    _make_db(base, [("قديم", "2020-01-01", "legacy-unknown")])
    work = os.path.join(tmp, "work.db")
    _make_db(work, [("الف", "2026-01-01", "rahavard365"),
                    ("الف", "2026-01-02", "rahavard365"),
                    ("ب", "2026-01-01", "rahavard365"),
                    ("ب", "2026-01-02", "legacy-unknown")])
    pack = os.path.join(tmp, "pack")
    _make_pack(pack)
    steps = os.path.join(tmp, "steps.csv")
    _write_csv(steps, ["symbol", "final_status", "action"],
               [("الف", "VERIFIED_OFFICIAL", "step"),
                ("ب", "CONFLICT_RATIO", "step")])
    symbols = os.path.join(tmp, "symbols.csv")
    _write_csv(symbols,
               ["symbol", "rows", "first_date", "last_date", "ref_coverage",
                "factor_steps", "factor_verified", "factor_reconstructed",
                "factor_unverified", "final_status", "remaining_blocker"],
               [("الف", "2", "2026-01-01", "2026-01-02", "full",
                 "2", "1", "1", "0", "VERIFIED_WITH_EVENTS", ""),
                ("ب", "2", "2026-01-01", "2026-01-02", "full",
                 "0", "0", "0", "0", "CONFLICT", "STEP_CONFLICT")])
    ref = os.path.join(tmp, "capture-summary.json")
    with open(ref, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"capture_sha256": "cap", "source": {"captured_at": "2026-11-10"}},
                  fh)
        fh.write("\n")
    return base, work, pack, steps, symbols, ref


def _run(out, base, work, pack, steps, symbols, ref, force=False):
    argv = ["--base", base, "--work", work, "--pack", pack,
            "--steps", steps, "--symbols", symbols,
            "--reference-summary", ref, "--out-dir", out]
    if force:
        argv.append("--force")
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rc = S.main(argv)
    return rc, err.getvalue()


def _full_build_test():
    with tempfile.TemporaryDirectory() as tmp:
        base, work, pack, steps, symbols, ref = _fixture(tmp)
        out = os.path.join(tmp, "seed")
        rc, err = _run(out, base, work, pack, steps, symbols, ref)
        assert rc == 0, (rc, err)

        for name in ("market.db", "market.db.lzma", "market.db.gz",
                     "FINAL-SEED-MANIFEST.json"):
            assert os.path.isfile(os.path.join(out, name)), name
        manifest_path = os.path.join(out, "FINAL-SEED-MANIFEST.json")
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        raw = open(manifest_path, "rb").read()
        assert b"\r" not in raw and raw.endswith(b"\n")

        assert manifest["schema"] == S.MANIFEST_SCHEMA
        assert manifest["integrity"]["ok"] is True, manifest["integrity"]
        assert manifest["integrity"]["duplicate_pairs"] == 0
        assert manifest["seed_lzma"]["roundtrip_ok"] is True
        assert manifest["seed_gzip"]["roundtrip_ok"] is True
        assert manifest["roundtrip_ok"] is True
        assert manifest["reference_derived_rows"] == 3
        assert manifest["price_history_rows"] == 4
        assert manifest["symbols_with_history"] == 2
        assert manifest["seed_db"]["sha256"] == _sha(os.path.join(out, "market.db"))
        assert manifest["seed_lzma"]["sha256"] == _sha(os.path.join(out, "market.db.lzma"))
        assert manifest["seed_gzip"]["sha256"] == _sha(os.path.join(out, "market.db.gz"))
        assert manifest["counts"]["reference_derived_rows"] == 3
        assert manifest["counts"]["price_history_rows"] == 4
        assert manifest["counts"]["symbols_with_history"] == 2
        assert manifest["counts"]["history_validity_rows"] == 2
        assert manifest["counts"]["open_corrections"] == 2
        assert manifest["counts"]["open_corrections_symbols"] == 1
        assert manifest["counts"]["user_watchlists_rows"] == 1
        assert manifest["counts"]["symbols_in_db_missing_from_ledger"] == 0
        assert manifest["validity_status_counts"] == {"unverified": 1,
                                                      "verified": 1}
        assert manifest["user_data"]["preserved"] is True
        assert manifest["inputs"]["pack"]["version"] == "ra365-test-v2"
        assert manifest["inputs"]["pack"]["factors_sha256"]
        assert manifest["inputs"]["reference_summary"]["capture_sha256"] == "cap"
        assert manifest["seed_manifest"]["price_history_rows"] == "4"
        assert manifest["seed_manifest"]["reference_derived_rows"] == "3"

        text = json.dumps(manifest, ensure_ascii=False)
        assert "الف" not in text and "ب" not in text, "raw symbols in manifest"
        assert manifest["seed_db"]["size"] > 0
        assert manifest["seed_lzma"]["size"] > 0
        assert manifest["seed_gzip"]["size"] > 0

        con = sqlite3.connect(os.path.join(out, "market.db"))
        try:
            assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert con.execute("SELECT COUNT(*) FROM history_validity").fetchone()[0] == 2
            assert dict(con.execute("SELECT status, COUNT(*) FROM history_validity "
                                    "GROUP BY status")) == {"unverified": 1,
                                                            "verified": 1}
            assert con.execute("SELECT COUNT(*) FROM user_watchlists").fetchone()[0] == 1
            assert con.execute("SELECT COUNT(*) FROM instruments").fetchone()[0] == 1
            assert con.execute("SELECT version FROM adjust_pack_state").fetchone()[0] == "ra365-test-v2"
            assert con.execute("SELECT steps FROM adjust_pack_state").fetchone()[0] == 3
            notes = dict(con.execute("SELECT symbol, notes FROM history_validity"))
        finally:
            con.close()
        assert notes["ب"].startswith("CONFLICT; blocker=STEP_CONFLICT"), notes

        # A non-empty out dir is refused without --force; its bytes stay put.
        before = open(manifest_path, "rb").read()
        marker = os.path.join(out, "keep.txt")
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write("keep\n")
        rc, err = _run(out, base, work, pack, steps, symbols, ref)
        assert rc == 2, (rc, err)
        assert "--force" in err, err
        assert open(manifest_path, "rb").read() == before
        assert os.path.isfile(marker)

        # --force rebuilds the four artifacts, leaves unrelated files, and the
        # provenance tables are not duplicated.
        rc, err = _run(out, base, work, pack, steps, symbols, ref, force=True)
        assert rc == 0, (rc, err)
        assert os.path.isfile(marker)
        con = sqlite3.connect(os.path.join(out, "market.db"))
        try:
            assert con.execute("SELECT COUNT(*) FROM history_validity").fetchone()[0] == 2
            assert con.execute("SELECT COUNT(*) FROM adjust_pack_state").fetchone()[0] == 1
            assert con.execute("SELECT COUNT(*) FROM seed_manifest").fetchone()[0] == len(
                manifest["seed_manifest"])
        finally:
            con.close()


def _refusal_test():
    with tempfile.TemporaryDirectory() as tmp:
        base, work, pack, steps, symbols, ref = _fixture(tmp)
        out = os.path.join(tmp, "seed")

        rc, err = _run(out, base, os.path.join(tmp, "missing.db"), pack,
                       steps, symbols, ref)
        assert rc == 2 and "work not found" in err, (rc, err)
        assert not os.path.exists(out)

        bad_pack = os.path.join(tmp, "bad-pack")
        _make_pack(bad_pack, bad_hash=True)
        rc, err = _run(out, base, work, bad_pack, steps, symbols, ref)
        assert rc == 2 and "sha256 mismatch" in err, (rc, err)
        assert not os.path.exists(out)

        no_user = os.path.join(tmp, "no-user.db")
        _make_db(no_user, [("الف", "2026-01-01", "rahavard365")], user=False)
        rc, err = _run(out, base, no_user, pack, steps, symbols, ref)
        assert rc == 2 and "user tables" in err, (rc, err)
        assert not os.path.exists(out)

        pending = os.path.join(tmp, "pending.db")
        _make_db(pending, [("الف", "2026-01-01", "rahavard365")])
        with open(pending + "-wal", "wb") as fh:
            fh.write(b"pending")
        rc, err = _run(out, base, pending, pack, steps, symbols, ref)
        assert rc == 2 and "checkpoint" in err, (rc, err)
        assert not os.path.exists(out)

        bad_ref = os.path.join(tmp, "bad-ref.json")
        with open(bad_ref, "w", encoding="utf-8") as fh:
            json.dump({"source": {"captured_at": "2026-11-10"}}, fh)
        rc, err = _run(out, base, work, pack, steps, symbols, bad_ref)
        assert rc == 2 and "capture_sha256" in err, (rc, err)
        assert not os.path.exists(out)

        zero_ref = os.path.join(tmp, "zero-ref.db")
        _make_db(zero_ref, [("الف", "2026-01-01", "legacy-unknown")])
        rc, err = _run(out, base, zero_ref, pack, steps, symbols, ref)
        assert rc == 2 and "reference-derived" in err, (rc, err)
        assert not os.path.isfile(os.path.join(out, "FINAL-SEED-MANIFEST.json"))

        dup = os.path.join(tmp, "dup.db")
        _make_db(dup, [("الف", "2026-01-01", "rahavard365")], duplicate=True)
        out2 = os.path.join(tmp, "seed-dup")
        rc, err = _run(out2, base, dup, pack, steps, symbols, ref)
        assert rc == 2 and "duplicate" in err, (rc, err)
        assert not os.path.isfile(os.path.join(out2, "FINAL-SEED-MANIFEST.json"))


def _gz_test():
    """The gzip really decodes to the seed database."""
    with tempfile.TemporaryDirectory() as tmp:
        base, work, pack, steps, symbols, ref = _fixture(tmp)
        out = os.path.join(tmp, "seed")
        rc, err = _run(out, base, work, pack, steps, symbols, ref)
        assert rc == 0, (rc, err)
        h = hashlib.sha256()
        with gzip.open(os.path.join(out, "market.db.gz"), "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        assert h.hexdigest() == _sha(os.path.join(out, "market.db"))


def main():
    _brief_test()
    _status_map_test()
    _unknown_status_test()
    _duplicate_symbol_test()
    _symbol_spaces_test()
    _manifest_storage_test()
    _full_build_test()
    _refusal_test()
    _gz_test()
    print("SEED BUILD TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
