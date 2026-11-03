#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 17: staged data migration is idempotent, transactional, reversible.

Uses a tiny synthetic source/target pair; the operational DB is never opened.
"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "ra365_data_migration.py")
P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


def make_db(path, *, pa_rows, sh_rows, fund_rows, evidence_rows=None):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE price_adjust_events (ins_code TEXT, d_even INTEGER,"
                " symbol TEXT, p_closing REAL, p_closing_not_adjusted REAL,"
                " corporate_type_code TEXT, ratio REAL, source TEXT, fetched_at TEXT,"
                " PRIMARY KEY(ins_code,d_even))")
    con.execute("CREATE TABLE share_change_events (ins_code TEXT, d_even INTEGER,"
                " symbol TEXT, shares_old REAL, shares_new REAL, ratio REAL,"
                " source TEXT, fetched_at TEXT, PRIMARY KEY(ins_code,d_even))")
    con.execute("CREATE TABLE fund_profit_events (ins_code TEXT, d_even INTEGER,"
                " symbol TEXT, profit_date TEXT, unit_profit REAL, reference_price REAL,"
                " ratio REAL, source TEXT, source_id TEXT, fetched_at TEXT,"
                " PRIMARY KEY(ins_code,d_even))")
    if evidence_rows is not None:
        con.execute("CREATE TABLE share_type_evidence (ins_code TEXT, d_even INTEGER,"
                    " no_cash INTEGER, source TEXT, source_id TEXT, fetched_at TEXT,"
                    " PRIMARY KEY(ins_code,d_even))")
        con.executemany("INSERT INTO share_type_evidence VALUES (?,?,?,?,?,?)",
                        evidence_rows)
    con.executemany("INSERT INTO price_adjust_events VALUES (?,?,?,?,?,?,?,?,?)", pa_rows)
    con.executemany("INSERT INTO share_change_events VALUES (?,?,?,?,?,?,?,?)", sh_rows)
    con.executemany("INSERT INTO fund_profit_events VALUES (?,?,?,?,?,?,?,?,?,?)", fund_rows)
    con.commit()
    con.close()


def counts(path):
    con = sqlite3.connect(path)
    try:
        out = {}
        for t in ("price_adjust_events", "share_change_events", "fund_profit_events"):
            out[t] = con.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
        try:
            out["share_type_evidence"] = con.execute(
                "SELECT COUNT(*) FROM share_type_evidence").fetchone()[0]
        except sqlite3.OperationalError:
            out["share_type_evidence"] = None
        out["integrity"] = con.execute("PRAGMA integrity_check").fetchone()[0]
        return out
    finally:
        con.close()


tmp = tempfile.mkdtemp(prefix="r17_mig_")
src = os.path.join(tmp, "source.db")
tgt = os.path.join(tmp, "target.db")
man = os.path.join(tmp, "manifest.json")
extra = os.path.join(tmp, "extra.jsonl")
make_db(src, pa_rows=[("i1", 20200101, "A", 100.0, 110.0, None, 0.90909091,
                       "tsetmc_price_adjust_by_flow", "t")],
        sh_rows=[("i1", 20200101, "A", 100.0, 120.0, 0.83333333,
                  "tsetmc_share_change_by_flow", "t")],
        fund_rows=[("i1", 20200101, "A", "1398/10/11", 10.0, 100.0, 0.9,
                    "fund-portal:test", "1", "t")],
        evidence_rows=[("i1", 20200101, 1, "codal-letter", "1", "2026-10-22")])
make_db(tgt, pa_rows=[("i0", 20190101, "OLD", 50.0, 55.0, None, 0.90909091,
                       "tsetmc_price_adjust_by_flow", "t")],
        sh_rows=[], fund_rows=[])
with open(extra, "w", encoding="utf-8") as fh:
    fh.write(json.dumps({"ins_code": "i2", "share_date": "2020-02-02",
                         "event_type": "RESERVE_ONLY",
                         "composition": {"paid_cash": 0.0},
                         "letter": {"tracing_no": "2"}}) + "\n")

base = counts(tgt)
ck(base["price_adjust_events"] == 1 and base["fund_profit_events"] == 0,
   "target starts with one old PA row and no fund rows", base)


def run(*args):
    return subprocess.run([sys.executable, TOOL, *args], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120)


p = run("--source-db", src, "--target-db", tgt, "--evidence-jsonl", extra,
        "--apply", "--manifest", man)
ck(p.returncode == 0, "migration exits 0", p.stdout[-400:] + p.stderr[-300:])
a = counts(tgt)
ck(a["price_adjust_events"] == 2 and a["share_change_events"] == 1
   and a["fund_profit_events"] == 1 and a["share_type_evidence"] == 2,
   "source rows + extra evidence are merged", a)
ck(a["integrity"] == "ok", "migration leaves integrity_check=ok", a)
m1 = json.load(open(man, encoding="utf-8"))
ck(m1["version"] == "ra365-r17-v1" and m1["after"]["price_adjust_events"]["rows"] == 2,
   "manifest records version and counts", m1.get("version"))

p = run("--source-db", src, "--target-db", tgt, "--evidence-jsonl", extra,
        "--apply", "--manifest", man)
a2 = counts(tgt)
m2 = json.load(open(man, encoding="utf-8"))
ck(p.returncode == 0 and a2 == a,
   "second run is idempotent (same counts/integrity)", (a, a2))
ck(m2["after"] == m1["after"], "second run keeps the same logical checksums")

p = run("--target-db", tgt, "--rollback")
r = counts(tgt)
ck(p.returncode == 0 and r["price_adjust_events"] == 1
   and r["fund_profit_events"] == 0 and r["share_type_evidence"] is None,
   "rollback restores the pre-migration target", r)

fake = os.path.join(tmp, "rahavard-full-universe", "market.db")
os.makedirs(os.path.dirname(fake), exist_ok=True)
make_db(fake, pa_rows=[], sh_rows=[], fund_rows=[])
p = run("--source-db", src, "--target-db", fake, "--apply")
ck(p.returncode == 2 and "REFUSED_OPERATIONAL_DB" in p.stdout,
   "operational-looking target is refused without an explicit override",
   p.stdout[-300:])

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
