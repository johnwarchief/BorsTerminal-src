#!/usr/bin/env python3
"""Inventory the local evidence sources available to Phase 4.9.2.

Read-only. Opens every DB with mode=ro; never writes an operational DB.
"""
import hashlib
import json
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "_audit", "phase49-2", "evidence", "source-inventory.json")

DBS = {
    "root": "market.db",
    "seed": "_audit/phase49-full-verification/seed/market.db",
    "work": "_audit/phase49-full-verification/db/backfill-v2/market.db",
}
TABLES = (
    "price_history", "daily_prices", "instrument_state", "tape_history",
    "tape_flag_day", "adjust_events", "history_validity", "instruments",
    "market_watch", "monthly_sales", "financial_statements", "codal_notices",
    "seed_manifest", "price_adjust_events", "share_change_events",
)


def sha256(path, limit=16 * 1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def table_info(con, name):
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(%s)" % name)]
        rows = con.execute("SELECT COUNT(*) FROM %s" % name).fetchone()[0]
        return {"rows": rows, "columns": cols}
    except sqlite3.Error as exc:
        return {"error": str(exc)}


def main():
    out = {"sources": {}, "db": {}, "files": {}}
    for name, rel in DBS.items():
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            out["db"][name] = {"path": rel, "missing": True}
            continue
        con = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True)
        try:
            info = {"path": rel, "size": os.path.getsize(path),
                    "sha256": sha256(path), "tables": {}}
            for t in TABLES:
                info["tables"][t] = table_info(con, t)
        finally:
            con.close()
        out["db"][name] = info

    files = [
        "codal.db", "market.db.lzma", "codal.db.lzma",
        "_audit/phase49-full-verification/captures/bars-all.ndjson.gz",
        "_audit/phase49-full-verification/captures/reference-index-all.json",
        "_audit/phase49-full-verification/capture-plan/symbols.json",
        "_audit/phase49-full-verification/capture-plan/capture-unmapped.json",
        "_audit/phase49-full-verification/ledgers/ADJUSTMENT-EVIDENCE-LEDGER.csv",
        "_audit/phase49-full-verification/ledgers/HISTORY-COVERAGE-LEDGER.csv",
        "data/ra365_corrections/ra365-phase49-rebuild-full-v2",
    ]
    for rel in files:
        path = os.path.join(ROOT, rel)
        if os.path.isdir(path):
            out["files"][rel] = {"dir": True,
                                 "entries": len(os.listdir(path))}
        elif os.path.exists(path):
            out["files"][rel] = {"size": os.path.getsize(path),
                                 "sha256": sha256(path)}
        else:
            out["files"][rel] = {"missing": True}

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
