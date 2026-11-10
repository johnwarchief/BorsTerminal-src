#!/usr/bin/env python3
"""Tests for stage01_capture_plan.

Three cases:

* the brief's synthetic case (pack-unverified + long-history only, no raw-only
  symbols from the live pack);
* a dedupe case where the pack, the DB and the live map spell one symbol three
  ways (Arabic kaf / Persian kaf / different source sets) - it must become one
  row, because identity is the normalised key, never the raw string;
* a real-fixture case over the frozen Seed DB and the two packs; it SKIPs
  cleanly when the gitignored fixtures are absent (fresh clone / CI).
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage01_capture_plan as S  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
DB = "_audit/phase49-finalization/seed/market.db"
PACK = "data/ra365_corrections/ra365-phase49-rebuild-full-v2"
LIVE = "data/ra365_corrections/ra365-live40-v1"

PH = ("CREATE TABLE price_history(symbol TEXT, date TEXT, open REAL, high REAL,"
      " low REAL, close REAL, volume REAL, last REAL, value REAL, src TEXT)")
INS = ("CREATE TABLE instruments(ins_code TEXT,l_val18 TEXT,l_val30 TEXT,"
       "paper_type INTEGER,isin TEXT,updated_at TEXT)")


def make_db(path):
    con = sqlite3.connect(path)
    con.execute(PH)
    con.execute(INS)
    con.execute("INSERT INTO instruments VALUES('11','\u0627\u0644\u0641','\u0627\u0644\u0641',1,NULL,'2026-01-01')")
    con.execute("INSERT INTO price_history VALUES('\u0627\u0644\u0641','2020-01-01',1,1,1,1,1,1,NULL,'x')")
    con.execute("INSERT INTO price_history VALUES('\u0627\u0644\u0641','2021-01-01',1,1,1,1,1,1,NULL,'x')")
    con.execute("INSERT INTO price_history VALUES('\u0628','2026-01-01',1,1,1,1,1,1,NULL,'x')")
    con.commit(); con.close()


def make_pack(path, rows):
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "factors.jsonl"), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def brief_case():
    tmp = tempfile.mkdtemp()
    try:
        db = os.path.join(tmp, "market.db"); make_db(db)
        pack = os.path.join(tmp, "pack"); make_pack(pack, [
            {"symbol": "\u0627\u0644\u0641", "asset_id": "1", "validity": "unverified"},
            {"symbol": "\u0628", "asset_id": "2", "validity": "verified"}])
        live = os.path.join(tmp, "live"); make_pack(live, [
            {"symbol": "\u0627\u0644\u0641", "asset_id": "1"},
            {"symbol": "\u0628", "asset_id": "2"},
            {"symbol": "\u062c", "asset_id": "3"}])
        out = os.path.join(tmp, "out"); os.makedirs(out)
        plan = S.build(db, pack, live, out, min_span_days=365)
        syms = {s["symbol"]: s for s in json.load(open(os.path.join(out, "symbols.json"), encoding="utf-8"))}
        assert "\u0627\u0644\u0641" in syms and "\u0628" not in syms and "\u062c" not in syms, syms
        assert syms["\u0627\u0644\u0641"]["asset_id"] == 1
        plan = json.load(open(os.path.join(out, "capture-plan.json"), encoding="utf-8"))
        assert plan["counts"]["pack_unverified"] == 1
        assert plan["counts"]["long_history"] == 1
        # the six short-history symbols are absent from this DB and the map:
        # they must be reported, not dropped.
        unmapped = json.load(open(os.path.join(out, "capture-unmapped.json"), encoding="utf-8"))
        assert len(unmapped) == len(S.SIX) == plan["counts"]["unmapped"], unmapped
        assert {u["symbol"] for u in unmapped} == set(S.SIX)
        assert {u["reason"] for u in unmapped} == {"NO_ASSET_ID"}
        print("  brief case OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def dedupe_case():
    """One security, three spellings, two sources -> exactly one row."""
    ara = "\u0643\u062a\u0648"   # Arabic kaf
    per = "\u06a9\u062a\u0648"   # Persian kaf
    tmp = tempfile.mkdtemp()
    try:
        db = os.path.join(tmp, "market.db")
        con = sqlite3.connect(db)
        con.execute(PH)
        con.execute(INS)
        con.execute("INSERT INTO instruments VALUES('22',?,'x',1,NULL,'2026-01-01')", (per,))
        con.execute("INSERT INTO price_history VALUES(?,'2020-01-01',1,1,1,1,1,1,NULL,'x')", (ara,))
        con.execute("INSERT INTO price_history VALUES(?,'2021-01-01',1,1,1,1,1,1,NULL,'x')", (ara,))
        con.commit(); con.close()
        pack = os.path.join(tmp, "pack")
        make_pack(pack, [{"symbol": per, "asset_id": "7", "validity": "unverified"}])
        live = os.path.join(tmp, "live")
        make_pack(live, [{"symbol": ara, "asset_id": "7"}])
        out = os.path.join(tmp, "out")
        plan = S.build(db, pack, live, out)
        syms = json.load(open(os.path.join(out, "symbols.json"), encoding="utf-8"))
        assert len(syms) == 1, syms
        assert syms[0]["asset_id"] == 7, syms
        assert syms[0]["ins_code"] == "22", syms
        assert syms[0]["basis"] == "real_close"
        assert set(syms[0]["source"].split(",")) == {"pack-unverified", "long-history"}, syms
        assert plan["counts"]["union"] == 1 + len(S.SIX), plan["counts"]
        assert plan["counts"]["mapped"] == 1, plan["counts"]
        assert plan["counts"]["pack_unverified"] == 1
        assert plan["counts"]["union_by_symbol"] == 2 + len(S.SIX), plan["counts"]
        # --extra-symbols is an owner addition, not a new identity: the same
        # key gains the owner-extra source instead of a second row.
        out2 = os.path.join(tmp, "out-extra")
        plan2 = S.build(db, pack, live, out2, extra=[{"symbol": per}])
        syms2 = json.load(open(os.path.join(out2, "symbols.json"), encoding="utf-8"))
        assert len(syms2) == 1, syms2
        assert "owner-extra" in syms2[0]["source"].split(","), syms2
        assert plan2["counts"]["owner_extra"] == 1, plan2["counts"]
        print("  dedupe case OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def ambiguous_case():
    """Two ids for one key: neither wins silently; the key is flagged."""
    per = "\u06a9\u062a\u0648"   # Persian kaf
    ara = "\u0643\u062a\u0648"   # Arabic kaf, same normalised key
    tmp = tempfile.mkdtemp()
    try:
        db = os.path.join(tmp, "market.db"); make_db(db)
        pack = os.path.join(tmp, "pack")
        make_pack(pack, [{"symbol": per, "asset_id": "7",
                          "validity": "unverified"}])
        live = os.path.join(tmp, "live")
        make_pack(live, [{"symbol": per, "asset_id": "7"},
                         {"symbol": ara, "asset_id": "9"}])
        out = os.path.join(tmp, "out")
        plan = S.build(db, pack, live, out)
        k = S.key(per)
        assert plan["counts"]["asset_map_ambiguous"] == [k], plan["counts"]
        assert plan["counts"]["mapped"] == 0, plan["counts"]
        unmapped = json.load(open(os.path.join(out, "capture-unmapped.json"),
                                  encoding="utf-8"))
        row = [u for u in unmapped if u["key"] == k]
        assert row and row[0]["reason"] == "AMBIGUOUS_ASSET_ID", unmapped
        assert row[0]["asset_ids"] == ["7", "9"], row
        syms = json.load(open(os.path.join(out, "symbols.json"),
                              encoding="utf-8"))
        assert not any(str(s["asset_id"]) in ("7", "9") for s in syms), syms
        print("  ambiguous case OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def real_case():
    absent = [rel for rel, check in ((DB, os.path.isfile), (PACK, os.path.isdir),
                                     (LIVE, os.path.isdir))
              if not check(os.path.join(ROOT, rel))]
    if absent:
        for rel in absent:
            print("SKIP real fixture: %s missing (gitignored)" % rel)
        return
    tmp = tempfile.mkdtemp()
    try:
        out = os.path.join(tmp, "plan")
        plan = S.build(os.path.join(ROOT, DB), os.path.join(ROOT, PACK),
                       os.path.join(ROOT, LIVE), out)
        c = plan["counts"]
        assert c["asset_map_symbols"] == 828, c
        assert c["pack_steps_unverified"] == 1358, c
        assert c["pack_symbols_unverified"] == 782, c
        assert c["pack_unverified"] == 754, c
        assert c["long_history"] == 854, c
        assert c["union"] == 1097, c
        assert c["union_by_symbol"] == 1130, c
        assert c["mapped"] == 758, c
        assert c["unmapped"] == 339, c
        assert c["mapped"] + c["unmapped"] == c["union"], c
        assert plan["min_span_sessions"] == 240, plan["min_span_sessions"]
        syms = json.load(open(os.path.join(out, "symbols.json"), encoding="utf-8"))
        assert len(syms) == c["mapped"]
        ids = [s["asset_id"] for s in syms]
        assert len(set(map(str, ids))) == len(ids), "one asset id per symbol"
        six = {S.key(n) for n in S.SIX}
        assert six <= {S.key(s["symbol"]) for s in syms}, "all six are mapped and captured"
        unmapped = json.load(open(os.path.join(out, "capture-unmapped.json"), encoding="utf-8"))
        assert len(unmapped) == c["unmapped"]
        assert {u["reason"] for u in unmapped} == {"NO_ASSET_ID"}
        print("  real fixture OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    brief_case()
    dedupe_case()
    ambiguous_case()
    real_case()
    print("CAPTURE PLAN TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
