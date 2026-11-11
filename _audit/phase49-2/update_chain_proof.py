#!/usr/bin/env python3
"""Prove the adjustment chain updates reproducibly when a new event arrives.

Real-data scenario: تپسي's 2026-11-10 split is present in the fresh capture but
absent from the old pack. On a throwaway copy of the independent DB we build
the "before" state (no factor/bar at or after 2026-11-10), then restore the
full captured rows and rebuild. The test asserts:
  * the revision changes,
  * the pre-event factor changes from 1.0 to the measured split ratio,
  * the post-event factor stays 1.0,
  * a repeated rebuild is byte-stable at the table level (idempotent).
"""
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "_audit", "phase49-2", "db", "market.db")
TEST = os.path.join(ROOT, "_audit", "phase49-2", "db", "update-test.db")
BIN = os.path.join(ROOT, "_audit", "phase49-2", "bin", "candlebuild.exe")
OUT = os.path.join(ROOT, "_audit", "phase49-2", "evidence", "update-chain-proof.json")
SYMBOL = "تپسي"
CUTOFF = "2026-11-10"


def build(db_path):
    r = subprocess.run([BIN, "--db", db_path], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("candlebuild failed: %s" % (r.stdout + r.stderr))
    return json.loads(r.stdout)


def table_hash(db_path, table, where=""):
    con = sqlite3.connect(db_path)
    try:
        q = "SELECT * FROM %s" % table
        if where:
            q += " WHERE " + where
        q += " ORDER BY symbol,date"
        h = hashlib.sha256()
        for row in con.execute(q):
            h.update(("\x1f".join("" if v is None else str(v) for v in row)
                      + "\n").encode("utf-8"))
        return h.hexdigest()
    finally:
        con.close()


def factor_at(db_path, date):
    con = sqlite3.connect(db_path)
    try:
        row = con.execute(
            "SELECT factor FROM adjusted_candles WHERE symbol=? AND date=?",
            (SYMBOL, date)).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def revision(db_path):
    con = sqlite3.connect(db_path)
    try:
        return con.execute(
            "SELECT revision FROM candle_build_revisions WHERE symbol=?",
            (SYMBOL,)).fetchone()[0]
    finally:
        con.close()


def last_pre_event_date(db_path):
    con = sqlite3.connect(db_path)
    try:
        return con.execute(
            "SELECT MAX(date) FROM adjusted_candles WHERE symbol=? AND date<?",
            (SYMBOL, CUTOFF)).fetchone()[0]
    finally:
        con.close()


def main():
    if os.path.exists(TEST):
        os.remove(TEST)
    shutil.copy2(DB, TEST)
    con = sqlite3.connect(TEST)
    original_rev = con.execute(
        "SELECT revision FROM adjustment_factors WHERE symbol=? LIMIT 1",
        (SYMBOL,)).fetchone()[0]
    saved = {}
    for table, cols in (
            ("adjustment_factors", "*"),
            ("reference_raw", "*"),
            ("reference_adjusted", "*")):
        saved[table] = con.execute(
            "SELECT %s FROM %s WHERE symbol=? AND date>=?" % (cols, table),
            (SYMBOL, CUTOFF)).fetchall()
    for table in saved:
        con.execute("DELETE FROM %s WHERE symbol=? AND date>=?" % table,
                    (SYMBOL, CUTOFF))
    # A real incremental capture recomputes the factor-set revision. Do the
    # same for the truncated set so the before/after revisions are meaningful.
    rows = con.execute(
        "SELECT date,ratio,capture_sha256 FROM adjustment_factors "
        "WHERE symbol=? ORDER BY date", (SYMBOL,)).fetchall()
    capture = rows[0][2]
    before_rev = hashlib.sha256(
        (capture + "\n" + "\n".join("%s|%.17g" % (d, r) for d, r, _ in rows)
         ).encode()).hexdigest()
    con.execute("UPDATE adjustment_factors SET revision=? WHERE symbol=?",
                (before_rev, SYMBOL))
    con.commit()
    con.close()

    before = build(TEST)
    prev_date = last_pre_event_date(TEST)
    before_prev_factor = factor_at(TEST, prev_date)
    before_factors = table_hash(TEST, "adjustment_factors",
                                "symbol='%s'" % SYMBOL)

    con = sqlite3.connect(TEST)
    for table, rows in saved.items():
        if not rows:
            continue
        placeholders = ",".join("?" * len(rows[0]))
        con.executemany(
            "INSERT INTO %s VALUES(%s)" % (table, placeholders), rows)
    con.execute("UPDATE adjustment_factors SET revision=? WHERE symbol=?",
                (original_rev, SYMBOL))
    con.commit()
    con.close()

    after = build(TEST)
    after_rev = revision(TEST)
    after_prev_factor = factor_at(TEST, prev_date)
    after_event_factor = factor_at(TEST, CUTOFF)
    after_factors = table_hash(TEST, "adjustment_factors",
                               "symbol='%s'" % SYMBOL)
    adjusted_hash = table_hash(TEST, "adjusted_candles")
    repeat = build(TEST)
    adjusted_hash2 = table_hash(TEST, "adjusted_candles")
    repeat_rev = revision(TEST)

    expected_pre = 0.14950616
    checks = {
        "revision_changed": before_rev != after_rev,
        "factor_table_changed": before_factors != after_factors,
        "before_factor_is_one": before_prev_factor == 1.0,
        "after_factor_is_measured_split":
            after_prev_factor is not None
            and abs(after_prev_factor / expected_pre - 1) < 1e-5,
        "after_event_factor_is_one": after_event_factor == 1.0,
        "repeat_build_idempotent": adjusted_hash == adjusted_hash2,
        "repeat_revision_stable": after_rev == repeat_rev,
        "rows_before": before["adjusted_rows"],
        "rows_after": after["adjusted_rows"],
    }
    out = {
        "schema": "phase49-2-update-chain-proof-v1",
        "db": os.path.relpath(TEST, ROOT).replace("\\", "/"),
        "symbol": SYMBOL,
        "cutoff": CUTOFF,
        "last_pre_event_date": prev_date,
        "before": {
            "revision": before_rev,
            "factor_last_pre_event": before_prev_factor,
            "adjusted_rows": before["adjusted_rows"],
        },
        "after": {
            "revision": after_rev,
            "factor_last_pre_event": after_prev_factor,
            "factor_at_cutoff": after_event_factor,
            "adjusted_rows": after["adjusted_rows"],
            "adjusted_sha256": adjusted_hash,
            "repeat_sha256": adjusted_hash2,
        },
        "checks": checks,
        "ok": all(v is True for k, v in checks.items()
                  if isinstance(v, bool)),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
