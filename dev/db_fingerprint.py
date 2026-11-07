#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Logical + physical fingerprint for market.db.

The physical SHA-256 changes when SQLite checkpoints or reorders pages. The
logical part is a multiset hash over canonical row encodings: it is independent
of row/page order, so a backup of the same content compares equal while any
insert/update/delete changes the table hash.

Usage:
  python dev/db_fingerprint.py --db market.db --out before.json
  python dev/db_fingerprint.py --db market.db --compare before.json
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys

_SKIP = {"sqlite_sequence", "sqlite_stat1"}
_MASK = (1 << 256) - 1


def _canonical(value):
    if value is None:
        return "n:"
    if isinstance(value, bytes):
        return "b:" + value.hex()
    if isinstance(value, float):
        return "f:" + repr(value)
    if isinstance(value, int):
        return "i:" + str(value)
    return "s:" + str(value)


def _row_digest(row):
    text = "\x1f".join(_canonical(v) for v in row)
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).digest()


def _table_fingerprint(conn, table):
    cols = [r[1] for r in conn.execute('PRAGMA table_info("%s")' % table)]
    quoted = ",".join('"%s"' % c.replace('"', '""') for c in cols)
    rows = 0
    xor_acc = 0
    sum_acc = 0
    cur = conn.execute('SELECT %s FROM "%s"' % (quoted, table))
    for row in cur:
        d = _row_digest(row)
        n = int.from_bytes(d, "big")
        xor_acc ^= n
        sum_acc = (sum_acc + n) & _MASK
        rows += 1
    logical = "%064x%064x" % (xor_acc, sum_acc)
    return {"rows": rows, "logical": logical}


def _physical(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    st = os.stat(path)
    return {"sha256": h.hexdigest(), "size": st.st_size, "mtime_ns": st.st_mtime_ns}


def fingerprint(path):
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise SystemExit("db not found: %s" % path)
    conn = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True)
    conn.execute("PRAGMA query_only=ON")
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        out_tables = {}
        for t in tables:
            if t.startswith("sqlite_") or t in _SKIP:
                continue
            out_tables[t] = _table_fingerprint(conn, t)
    finally:
        conn.close()
    total = hashlib.sha256()
    for t in sorted(out_tables):
        rec = out_tables[t]
        total.update(("%s\x1f%d\x1f%s\n" % (t, rec["rows"], rec["logical"])).encode())
    return {"db": path, "physical": _physical(path), "integrity": integrity,
            "journal_mode": journal, "tables": out_tables,
            "logical_total": total.hexdigest()}


def compare(a, b):
    diffs = []
    if a.get("integrity") != b.get("integrity"):
        diffs.append(("integrity", a.get("integrity"), b.get("integrity")))
    ta, tb = a.get("tables", {}), b.get("tables", {})
    for t in sorted(set(ta) | set(tb)):
        ra, rb = ta.get(t), tb.get(t)
        if ra != rb:
            diffs.append((t, ra, rb))
    if a.get("logical_total") != b.get("logical_total"):
        diffs.append(("logical_total", a.get("logical_total"), b.get("logical_total")))
    return diffs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out")
    ap.add_argument("--compare")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    fp = fingerprint(a.db)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(fp, fh, ensure_ascii=False, indent=1, sort_keys=True)
    if not a.quiet:
        print(json.dumps({"db": fp["db"], "physical": fp["physical"],
                          "integrity": fp["integrity"],
                          "journal_mode": fp["journal_mode"],
                          "logical_total": fp["logical_total"]},
                         ensure_ascii=False, indent=1))
    if a.compare:
        with open(a.compare, encoding="utf-8") as fh:
            old = json.load(fh)
        diffs = compare(old, fp)
        if diffs:
            print("FINGERPRINT_DIFFERENCE: %d" % len(diffs))
            for name, before, after in diffs[:30]:
                print("  %s\n    before=%s\n    after =%s" % (name, before, after))
            return 2
        print("FINGERPRINT_MATCH logical_total=%s" % fp["logical_total"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
