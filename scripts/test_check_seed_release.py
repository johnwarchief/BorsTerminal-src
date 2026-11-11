#!/usr/bin/env python3
"""Tests for scripts/check_seed_release.py (Phase 4.9.1 Task A8, Phase 4.9.2 approval).

Every case builds a throwaway DB under the system temp directory; the tracked
root market.db is never opened here (the gate's behaviour on it is recorded in
the task report instead).

Contract under test:
  blocked  -> exit 1 and "SEED_RELEASE_BLOCKED" on stdout, never a traceback
  approved -> exit 0 and "SEED_RELEASE_OK" on stdout
A manifest that cannot be read or cannot be trusted (no table, no key,
non-integer, negative) is always blocked, even with the owner flag or a valid
approval record. A >0 row count is approved by a committed approval record that
matches the row count and reference hashes; a missing/mismatched record blocks.
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "scripts", "check_seed_release.py")
DEFAULT_APPROVAL = os.path.join(
    ROOT, "docs", "opportunity-center", "phase49-2",
    "OWNER-APPROVAL-REFERENCE-DERIVED.json")


def make_db(rows, capture_sha="cap-sha", index_sha="idx-sha"):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE seed_manifest(key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO seed_manifest VALUES ('reference_derived_rows', ?)", (str(rows),))
    if capture_sha is not None:
        con.execute("INSERT INTO seed_manifest VALUES ('reference_capture_sha256', ?)",
                    (capture_sha,))
    if index_sha is not None:
        con.execute("INSERT INTO seed_manifest VALUES ('reference_index_sha256', ?)",
                    (index_sha,))
    con.commit()
    con.close()
    return path


def make_approval(rows, capture_sha="cap-sha", index_sha="idx-sha", **overrides):
    record = {
        "schema": "phase49-2-owner-approval-reference-derived-v1",
        "approved": True,
        "scope": "reference_derived_rows",
        "approved_at": "2026-11-11",
        "approver": "BorsTerminal project owner",
        "expected_reference_derived_rows": rows,
        "reference_capture_sha256": capture_sha,
        "reference_index_sha256": index_sha,
        "conditions": ["provenance preserved", "approval does not verify rows"],
    }
    record.update(overrides)
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(record, fh, ensure_ascii=False)
    return path


def make_db_without_manifest():
    """A real DB with ordinary tables but no seed_manifest (the root market.db shape)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE daily_prices(symbol TEXT, date TEXT)")
    con.commit()
    con.close()
    return path


def make_db_without_key():
    """seed_manifest exists but carries no reference_derived_rows key."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE seed_manifest(key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO seed_manifest VALUES ('pack_reference_sha256', 'abc')")
    con.commit()
    con.close()
    return path


def missing_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)  # guaranteed-not-to-exist path with a .db suffix
    return path


def missing_path_under_unicode_dir():
    """A nonexistent DB under a Persian folder name (a real local checkout shape)."""
    base = tempfile.mkdtemp(prefix="seed_gate_")
    folder = os.path.join(base, "\u0645\u062c\u0644\u062f")
    os.makedirs(folder)
    return base, os.path.join(folder, "seed.db")


def run_gate(db, *extra):
    return subprocess.run([sys.executable, TOOL, "--db", db, *extra],
                          capture_output=True, text=True)


def assert_blocked(r, label):
    combined = r.stdout + r.stderr
    assert r.returncode == 1, "%s: expected exit 1, got %d\n%s" % (label, r.returncode, combined)
    assert "SEED_RELEASE_BLOCKED" in r.stdout, \
        "%s: blocked verdict missing from stdout\n%s" % (label, combined)
    assert "Traceback" not in combined, \
        "%s: gate crashed instead of reporting blocked\n%s" % (label, combined)


def main():
    p = make_db(3105)
    r = subprocess.run([sys.executable, TOOL, "--db", p], capture_output=True, text=True)
    assert r.returncode != 0, r.stdout + r.stderr
    assert "SEED_RELEASE_BLOCKED" in r.stdout
    r = subprocess.run([sys.executable, TOOL, "--db", p,
                        "--owner-approved-reference-redistribution"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SEED_RELEASE_OK" in r.stdout
    p0 = make_db(0)
    r = subprocess.run([sys.executable, TOOL, "--db", p0], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr

    # Phase 4.9.2: a committed approval record with matching row count and
    # reference hashes approves the seed; every mismatch still blocks.
    p_ok = make_db(3105, "cap-sha", "idx-sha")
    rec_ok = make_approval(3105, "cap-sha", "idx-sha")
    r = run_gate(p_ok, "--approval-record", rec_ok)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SEED_RELEASE_OK" in r.stdout and "approved_at=2026-11-11" in r.stdout, r.stdout

    rec_missing = os.path.join(tempfile.mkdtemp(prefix="seed_rec_"), "absent.json")
    assert_blocked(run_gate(p_ok, "--approval-record", rec_missing), "record-missing")
    rec_false = make_approval(3105, approved=False)
    assert_blocked(run_gate(p_ok, "--approval-record", rec_false), "record-not-approved")
    rec_count = make_approval(3106)
    assert_blocked(run_gate(p_ok, "--approval-record", rec_count), "record-count-mismatch")
    rec_cap = make_approval(3105, capture_sha="other")
    assert_blocked(run_gate(p_ok, "--approval-record", rec_cap), "record-capture-mismatch")
    rec_idx = make_approval(3105, index_sha="other")
    assert_blocked(run_gate(p_ok, "--approval-record", rec_idx), "record-index-mismatch")
    rec_bad = os.path.join(tempfile.mkdtemp(prefix="seed_rec_"), "bad.json")
    with open(rec_bad, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    assert_blocked(run_gate(p_ok, "--approval-record", rec_bad), "record-invalid-json")

    # The committed default record itself must cover the approved footprint.
    with open(DEFAULT_APPROVAL, encoding="utf-8") as fh:
        default_record = json.load(fh)
    assert default_record["schema"] == "phase49-2-owner-approval-reference-derived-v1"
    assert default_record["approved"] is True
    assert default_record["scope"] == "reference_derived_rows"
    assert default_record["expected_reference_derived_rows"] == 105367
    assert default_record["conditions"], "default approval lost its conditions"

    # (a) DB without the seed_manifest table must block, not crash and not pass.
    p_a = make_db_without_manifest()
    assert_blocked(run_gate(p_a), "no-table")
    # Owner approval authorises data, not a missing manifest.
    assert_blocked(run_gate(p_a, "--owner-approved-reference-redistribution"), "no-table+approved")
    assert_blocked(run_gate(p_a, "--approval-record", rec_ok), "no-table+record")

    # (b) Nonexistent DB path must block (sqlite3.connect raises here, not the SELECT).
    p_b = missing_path()
    assert_blocked(run_gate(p_b), "missing-db")

    # (c) A non-integer reference_derived_rows must block, not raise ValueError.
    p_c = make_db("many")
    assert_blocked(run_gate(p_c), "non-numeric")
    assert_blocked(run_gate(p_c, "--owner-approved-reference-redistribution"), "non-numeric+approved")

    # (d) A negative row count is nonsense and must block.
    p_d = make_db(-5)
    assert_blocked(run_gate(p_d), "negative")

    # (e) seed_manifest present but the counted key absent must block, not pass as 0.
    p_e = make_db_without_key()
    assert_blocked(run_gate(p_e), "missing-key")

    # (f) The blocked message names the DB path; that path must not turn the
    #     verdict into a traceback on an ASCII/cp1252 console (local checkouts
    #     live under Persian folder names).
    p_f_base, p_f = missing_path_under_unicode_dir()
    env = dict(os.environ, PYTHONIOENCODING="ascii")
    r = subprocess.run([sys.executable, TOOL, "--db", p_f], capture_output=True,
                       text=True, env=env, errors="replace")
    assert_blocked(r, "unicode-path-ascii-stdout")

    for path in (p, p0, p_ok, p_a, p_b, p_c, p_d, p_e,
                 rec_ok, rec_false, rec_count, rec_cap, rec_idx, rec_bad):
        try:
            os.unlink(path)
        except OSError:
            pass
    shutil.rmtree(os.path.dirname(rec_missing), ignore_errors=True)
    shutil.rmtree(os.path.dirname(rec_bad), ignore_errors=True)
    shutil.rmtree(p_f_base, ignore_errors=True)
    print("SEED RELEASE GATE TESTS OK")
    print("SEED RELEASE GATE EDGE CASES OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
