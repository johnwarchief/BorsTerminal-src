#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Phase 4.9 Stage 0: restore the three Phase 4.8 DB archives to isolated
paths, verify SHA-256 against manifest, and report integrity/schema/stats.
Read-only with respect to every pre-existing file.
"""
import hashlib
import json
import lzma
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT = os.path.join(ROOT, "_audit", "phase49", "continuation", "db")

ARCHIVES = [
    ("source", "data/phase48/db/phase48-source-market.db.lzma",
     "42cd1567da50bd4c507b0f8503d015ba44b9005b1bd8ecd077a28b03cb1eb93f",
     "bb57564b2671162238f5760641e05dd5fd0fe0e44501383fb8c2f96a26efb8ca"),
    ("work", "data/phase48/db/phase48-backfill-work-market.db.lzma",
     "db214908de84f25778a7d7cabfe44bf17c37c302a79a0627526f57ef378bafca",
     "2b701ea3d32dcb30c5c0bc248cd160b1aa5bc5f38598a71e6b056c355e1ed3b5"),
    ("verify", "data/phase48/db/phase48-backfill-verify-market.db.lzma",
     "db214908de84f25778a7d7cabfe44bf17c37c302a79a0627526f57ef378bafca",
     "2b701ea3d32dcb30c5c0bc248cd160b1aa5bc5f38598a71e6b056c355e1ed3b5"),
]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def restore(name, archive_rel, archive_sha, raw_sha):
    archive = os.path.join(ROOT, archive_rel)
    dest = os.path.join(OUT, "restored-%s.db" % name)
    report = {"name": name, "archive": archive_rel,
              "archive_sha256": sha256_file(archive),
              "archive_sha_expected": archive_sha,
              "dest": dest}
    report["archive_sha_ok"] = report["archive_sha256"] == archive_sha
    if os.path.exists(dest):
        report["restored"] = False
        report["note"] = "destination already exists; not overwritten"
    else:
        os.makedirs(OUT, exist_ok=True)
        d = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
        with open(archive, "rb") as src, open(dest, "wb") as dst:
            while True:
                chunk = src.read(1 << 22)
                if not chunk:
                    break
                dst.write(d.decompress(chunk))
        report["restored"] = True
    report["raw_size"] = os.path.getsize(dest)
    report["raw_sha256"] = sha256_file(dest)
    report["raw_sha_expected"] = raw_sha
    report["raw_sha_ok"] = report["raw_sha256"] == raw_sha
    return report, dest


def db_stats(path):
    uri = "file:%s?mode=ro" % path.replace("\\", "/")
    con = sqlite3.connect(uri, uri=True)
    cur = con.cursor()
    out = {}
    out["integrity_check"] = [r[0] for r in cur.execute("PRAGMA integrity_check")]
    out["journal_mode"] = [r[0] for r in cur.execute("PRAGMA journal_mode")]
    tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    out["table_count"] = len(tables)
    counts = {}
    for t in tables:
        try:
            counts[t] = cur.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
        except sqlite3.Error as exc:
            counts[t] = "ERR:%s" % exc
    out["tables"] = counts
    if "price_history" in counts and "symbol" in counts:
        rows = cur.execute(
            "SELECT symbol, MIN(date), MAX(date), COUNT(*) FROM price_history "
            "GROUP BY symbol ORDER BY symbol").fetchall()
        out["price_history_symbols"] = len(rows)
        out["price_history_total"] = sum(r[3] for r in rows)
        out["price_history_min"] = min(r[1] for r in rows)
        out["price_history_max"] = max(r[2] for r in rows)
        out["price_history_per_symbol"] = rows
    if "price_history" in counts:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(price_history)")]
        out["price_history_columns"] = cols
        try:
            out["src_counts"] = dict(cur.execute(
                "SELECT src, COUNT(*) FROM price_history GROUP BY src"))
        except sqlite3.Error:
            pass
    con.close()
    return out


def main():
    reports = []
    for name, archive_rel, asha, rsha in ARCHIVES:
        rep, dest = restore(name, archive_rel, asha, rsha)
        rep["db"] = db_stats(dest)
        reports.append(rep)
        print(json.dumps(rep, ensure_ascii=False, indent=1)[:2000])
        print("---")
    with open(os.path.join(ROOT, "_audit", "phase49", "continuation",
                           "stage0-restore-report.json"), "w",
              encoding="utf-8") as fh:
        json.dump(reports, fh, ensure_ascii=False, indent=1)
    ok = all(r["archive_sha_ok"] and r["raw_sha_ok"]
             and r["db"]["integrity_check"] == ["ok"] for r in reports)
    print("STAGE0_RESTORE:", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
