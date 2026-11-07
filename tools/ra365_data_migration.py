#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 17: versioned, idempotent, transactional data promotion.

Promotes the isolated full-history tables (price_adjust_events,
share_change_events, fund_profit_events, share_type_evidence) into a
**copy** of the operational DB.  The real operational DB is refused unless
--allow-operational is given explicitly; the recommended path is a copy.

Usage:
  python tools/ra365_data_migration.py --source-db FULL.db --target-db COPY.db --plan
  python tools/ra365_data_migration.py --source-db FULL.db --target-db COPY.db --apply
  python tools/ra365_data_migration.py --target-db COPY.db --rollback
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sqlite3
import sys

VERSION = "ra365-r17-v1"
TABLES = {
    "price_adjust_events": 9,
    "share_change_events": 8,
    "fund_profit_events": 10,
}
DDL_EVIDENCE = """CREATE TABLE IF NOT EXISTS share_type_evidence (
 ins_code TEXT NOT NULL,
 d_even INTEGER NOT NULL,
 no_cash INTEGER NOT NULL,
 source TEXT,
 source_id TEXT,
 fetched_at TEXT NOT NULL,
 PRIMARY KEY (ins_code, d_even))"""
OPERATIONAL = "rahavard-full-universe"


def unique_key(con, table):
    """Columns of a unique/PK index, or None."""
    for idx in con.execute("PRAGMA index_list(%s)" % table):
        if not idx[2]:
            continue
        cols = [r[2] for r in con.execute("PRAGMA index_info(%s)" % idx[1])]
        if cols:
            return cols
    return None


def duplicate_keys(con, table, cols):
    q = ("SELECT COUNT(*) FROM (SELECT %s, COUNT(*) c FROM %s "
         "GROUP BY %s HAVING c > 1)" % (",".join(cols), table, ",".join(cols)))
    return con.execute(q).fetchone()[0]


def table_rows(con, table):
    cols = [r[1] for r in con.execute("PRAGMA table_info(%s)" % table)]
    if not cols:
        return cols, []
    rows = con.execute("SELECT * FROM %s ORDER BY 1,2" % table).fetchall()
    return cols, rows


def checksum(cols, rows):
    h = hashlib.sha256()
    h.update(("|".join(cols) + "\n").encode("utf-8"))
    for row in rows:
        h.update(repr(tuple(row)).encode("utf-8") + b"\n")
    return h.hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def source_tables(src):
    con = sqlite3.connect("file:%s?mode=ro" % src.replace("\\", "/"), uri=True)
    out = {}
    try:
        for t in list(TABLES) + ["share_type_evidence"]:
            cols, rows = table_rows(con, t)
            out[t] = {"cols": cols, "rows": rows}
    finally:
        con.close()
    return out


def evidence_extra(path):
    rows = []
    if not path or not os.path.exists(path):
        return rows
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        j = json.loads(line)
        et = j.get("event_type")
        paid = (j.get("composition") or {}).get("paid_cash") or 0
        if et not in ("RESERVE_ONLY", "COMBINED_CLAIMS") or float(paid) > 0:
            continue
        sd = str(j.get("share_date") or "")[:10].replace("-", "")
        ins = str(j.get("ins_code") or "")
        if not sd or not ins:
            continue
        rows.append((ins, int(sd), 1, "codal-letter",
                     str((j.get("letter") or {}).get("tracing_no") or ""),
                     dt.date.today().isoformat()))
    return rows


def backup_db(src, dst):
    s = sqlite3.connect("file:%s?mode=ro" % src.replace("\\", "/"), uri=True)
    try:
        d = sqlite3.connect(dst)
        try:
            s.backup(d)
        finally:
            d.close()
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-db")
    ap.add_argument("--target-db", required=True)
    ap.add_argument("--evidence-jsonl", default="")
    ap.add_argument("--manifest", default="")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--allow-operational", action="store_true")
    a = ap.parse_args()
    target = os.path.abspath(a.target_db)
    if OPERATIONAL in target.replace("\\", "/") and not a.allow_operational:
        print("REFUSED_OPERATIONAL_DB: pass a copy, or --allow-operational explicitly")
        return 2
    if not os.path.isfile(target):
        print("TARGET_NOT_FOUND:", target)
        return 2
    baseline = target + ".%s.baseline" % VERSION
    if a.rollback:
        if not os.path.isfile(baseline):
            print("NO_BASELINE:", baseline)
            return 2
        shutil.copy2(baseline, target)
        print("ROLLED_BACK:", target, "from", baseline)
        return 0
    if not a.source_db:
        print("--source-db is required for plan/apply")
        return 2
    src = os.path.abspath(a.source_db)
    if not os.path.isfile(src):
        print("SOURCE_NOT_FOUND:", src)
        return 2
    data = source_tables(src)
    src_con = sqlite3.connect("file:%s?mode=ro" % src.replace("\\", "/"), uri=True)
    try:
        source_keys = {t: unique_key(src_con, t) for t in TABLES}
        for t, key in source_keys.items():
            if not key:
                print("SOURCE_KEY_MISSING:", t)
                return 2
            dup = duplicate_keys(src_con, t, key)
            if dup:
                print("SOURCE_DUPLICATE_KEYS:", t, dup, key)
                return 2
    finally:
        src_con.close()
    extra = evidence_extra(a.evidence_jsonl)
    for t, n in TABLES.items():
        if not data[t]["cols"]:
            print("SOURCE_TABLE_MISSING:", t)
            return 2
        if len(data[t]["cols"]) != n:
            print("SOURCE_SCHEMA_DRIFT:", t, data[t]["cols"])
            return 2
    con = sqlite3.connect("file:%s?mode=ro" % target.replace("\\", "/"), uri=True)
    try:
        target_cols = {t: [r[1] for r in con.execute("PRAGMA table_info(%s)" % t)]
                       for t in TABLES}
        target_keys = {t: unique_key(con, t) for t in TABLES}
        for t, key in source_keys.items():
            if target_keys[t] and target_keys[t] != key:
                print("TARGET_KEY_DRIFT:", t, target_keys[t], "expected", key)
                return 2
            dup = duplicate_keys(con, t, key)
            if dup:
                print("TARGET_DUPLICATE_KEYS:", t, dup, key)
                return 2
    finally:
        con.close()
    for t, n in TABLES.items():
        if len(target_cols[t]) != n:
            print("TARGET_SCHEMA_DRIFT:", t, target_cols[t])
            return 2
    plan = {}
    for t in TABLES:
        plan[t] = {"source_rows": len(data[t]["rows"]),
                   "source_sha256": checksum(data[t]["cols"], data[t]["rows"])}
    print(json.dumps({"version": VERSION, "plan": plan,
                      "evidence_extra": len(extra)}, ensure_ascii=False, indent=1))
    if a.plan or not a.apply:
        print("PLAN_ONLY")
        return 0

    # Keep one immutable baseline for rollback, plus a per-run pre-apply copy.
    if not os.path.exists(baseline):
        backup_db(target, baseline)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = target + ".%s.pre-%s" % (VERSION, stamp)
    backup_db(target, backup)
    before = {"target_sha256": file_sha(target), "baseline": baseline,
              "pre_apply_backup": backup,
              "at": dt.datetime.now().isoformat(timespec="seconds")}
    applied = {}
    try:
        con = sqlite3.connect(target, timeout=60)
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute("BEGIN IMMEDIATE")
        for t in TABLES:
            key = source_keys[t]
            if not target_keys[t]:
                con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_r17_%s ON %s(%s)"
                            % (t, t, ",".join(key)))
            cols, rows = data[t]["cols"], data[t]["rows"]
            ph = ",".join("?" * len(cols))
            con.executemany("INSERT OR REPLACE INTO %s VALUES (%s)" % (t, ph), rows)
            applied[t] = len(rows)
        con.execute(DDL_EVIDENCE)
        ev_cols, ev_rows = data["share_type_evidence"]["cols"], data["share_type_evidence"]["rows"]
        if ev_cols:
            ph = ",".join("?" * len(ev_cols))
            con.executemany("INSERT OR REPLACE INTO share_type_evidence VALUES (%s)" % ph,
                            ev_rows)
        if extra:
            con.executemany(
                "INSERT OR REPLACE INTO share_type_evidence"
                " (ins_code,d_even,no_cash,source,source_id,fetched_at)"
                " VALUES (?,?,?,?,?,?)", extra)
        con.commit()
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        after = {}
        for t in list(TABLES) + ["share_type_evidence"]:
            cols, rows = table_rows(con, t)
            after[t] = {"rows": len(rows), "sha256": checksum(cols, rows)}
        con.close()
    except Exception as e:
        try:
            con.rollback()
            con.close()
        except Exception:
            pass
        shutil.copy2(backup, target)
        print("MIGRATION_FAILED_ROLLED_BACK:", type(e).__name__, str(e)[:300])
        return 3
    manifest = {
        "version": VERSION,
        "source_db": src, "source_sha256": file_sha(src),
        "target_db": target, "before": before,
        "applied_rows": applied, "evidence_extra": len(extra),
        "after": after, "integrity_check": integrity,
        "keys": source_keys,
        "idempotent": "INSERT OR REPLACE by the source unique key",
        "finished_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    if a.manifest:
        os.makedirs(os.path.dirname(a.manifest) or ".", exist_ok=True)
        json.dump(manifest, open(a.manifest, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print(json.dumps(manifest, ensure_ascii=False, indent=1))
    return 0 if integrity == "ok" else 4


if __name__ == "__main__":
    sys.exit(main())
