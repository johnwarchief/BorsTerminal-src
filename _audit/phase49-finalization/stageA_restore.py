#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Phase 4.9 finalization Stage A: restore the three Phase 4.8 DB archives
into NEW isolated paths under _audit/phase49-finalization/db/, verify SHA-256
against the Phase 4.8 manifest, and record integrity/schema/row/date/
adjustment-event/provenance stats. Never overwrites or deletes any DB.
"""
import hashlib
import json
import lzma
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "_audit", "phase49-finalization", "db")
REPORT = os.path.join(ROOT, "_audit", "phase49-finalization",
                      "stageA-restore-report.json")

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
    rep = {"name": name, "archive": archive_rel,
           "archive_sha256": sha256_file(archive),
           "archive_sha_expected": archive_sha, "dest": dest}
    rep["archive_sha_ok"] = rep["archive_sha256"] == archive_sha
    if os.path.exists(dest):
        rep["restored"] = False
        rep["note"] = "destination already exists; NOT overwritten"
    else:
        os.makedirs(OUT, exist_ok=True)
        tmp = dest + ".partial"
        d = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
        with open(archive, "rb") as src, open(tmp, "wb") as dst:
            while True:
                chunk = src.read(1 << 22)
                if not chunk:
                    break
                dst.write(d.decompress(chunk))
        os.replace(tmp, dest)
        rep["restored"] = True
    rep["raw_size"] = os.path.getsize(dest)
    rep["raw_sha256"] = sha256_file(dest)
    rep["raw_sha_expected"] = raw_sha
    rep["raw_sha_ok"] = rep["raw_sha256"] == raw_sha
    return rep, dest


def q(cur, sql, default=None):
    try:
        return cur.execute(sql).fetchall()
    except sqlite3.Error as exc:
        return [("ERR", str(exc))] if default is None else default


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
    out["nonempty_tables"] = {k: v for k, v in counts.items()
                              if isinstance(v, int) and v > 0}
    out["all_tables"] = counts

    if "price_history" in counts:
        out["price_history"] = {
            "total": counts["price_history"],
            "symbols": q(cur, "SELECT COUNT(DISTINCT symbol) FROM price_history"),
            "date_min": q(cur, "SELECT MIN(date) FROM price_history"),
            "date_max": q(cur, "SELECT MAX(date) FROM price_history"),
            "src_counts": dict(q(cur,
                "SELECT src, COUNT(*) FROM price_history GROUP BY src")),
            "columns": [r[1] for r in cur.execute(
                "PRAGMA table_info(price_history)")],
        }
        cols = out["price_history"]["columns"]
        if "ins_code" in cols:
            out["price_history"]["distinct_ins_codes"] = q(
                cur, "SELECT COUNT(DISTINCT ins_code) FROM price_history")
    for t in ("adjust_events", "adjust_verdict", "price_adjust_events",
              "share_change_events", "backfill_runs", "backfill_rows",
              "instruments", "codal_notices", "monthly_sales",
              "financial_statements"):
        if t in counts:
            out.setdefault("tables_of_interest", {})[t] = counts[t]
    if "adjust_events" in counts:
        out["adjust_events_detail"] = {
            "symbols": q(cur, "SELECT COUNT(DISTINCT symbol) FROM adjust_events"),
            "date_min": q(cur, "SELECT MIN(date) FROM adjust_events"),
            "date_max": q(cur, "SELECT MAX(date) FROM adjust_events"),
            "kind_counts": dict(q(cur,
                "SELECT kind, COUNT(*) FROM adjust_events GROUP BY kind")),
        }
    if "backfill_runs" in counts:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(backfill_runs)")]
        out["backfill_runs"] = {
            "columns": cols,
            "rows": [dict(zip(cols, r)) for r in cur.execute(
                "SELECT * FROM backfill_runs ORDER BY rowid")],
        }
    if "backfill_rows" in counts:
        out["backfill_rows_detail"] = {
            "symbols": q(cur, "SELECT COUNT(DISTINCT symbol) FROM backfill_rows"),
            "src_counts": dict(q(cur,
                "SELECT src, COUNT(*) FROM backfill_rows GROUP BY src")),
        }
    con.close()
    return out


def main():
    reports = []
    for name, archive_rel, asha, rsha in ARCHIVES:
        rep, dest = restore(name, archive_rel, asha, rsha)
        rep["db"] = db_stats(dest)
        reports.append(rep)
        print("%-7s archive_ok=%s raw_ok=%s restored=%s integrity=%s tables=%d ph=%s" % (
            name, rep["archive_sha_ok"], rep["raw_sha_ok"],
            rep.get("restored"), rep["db"]["integrity_check"],
            rep["db"]["table_count"],
            rep["db"].get("price_history", {}).get("total")))
    with open(REPORT, "w", encoding="utf-8") as fh:
        json.dump(reports, fh, ensure_ascii=False, indent=1)
    ok = all(r["archive_sha_ok"] and r["raw_sha_ok"]
             and r["db"]["integrity_check"] == ["ok"] for r in reports)
    print("STAGE_A_RESTORE:", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
