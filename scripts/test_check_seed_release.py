#!/usr/bin/env python3
"""Tests for scripts/check_seed_release.py (Phase 4.9.1, Task A8).

Every case builds a throwaway DB under the system temp directory; the tracked
root market.db is never opened here (the gate's behaviour on it is recorded in
the task report instead).

Contract under test (controller ruling of 2026-11-10):
  blocked  -> exit 1 and "SEED_RELEASE_BLOCKED" on stdout, never a traceback
  approved -> exit 0 and "SEED_RELEASE_OK" on stdout
A manifest that cannot be read or cannot be trusted (no table, no key,
non-integer, negative) is always blocked, even with the owner flag.
"""
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "scripts", "check_seed_release.py")


def make_db(rows):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE seed_manifest(key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO seed_manifest VALUES ('reference_derived_rows', ?)", (str(rows),))
    con.commit()
    con.close()
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

    # (a) DB without the seed_manifest table must block, not crash and not pass.
    p_a = make_db_without_manifest()
    assert_blocked(run_gate(p_a), "no-table")
    # Owner approval authorises data, not a missing manifest.
    assert_blocked(run_gate(p_a, "--owner-approved-reference-redistribution"), "no-table+approved")

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

    for path in (p, p0, p_a, p_b, p_c, p_d, p_e):
        try:
            os.unlink(path)
        except OSError:
            pass
    shutil.rmtree(p_f_base, ignore_errors=True)
    print("SEED RELEASE GATE TESTS OK")
    print("SEED RELEASE GATE EDGE CASES OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
