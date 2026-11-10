#!/usr/bin/env python3
import csv
import json
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage07_inventory_reconcile as S  # noqa: E402


def _edge_tests():
    """Union buckets, pack alias keys, product events and the r32b block."""
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "edge.db")
        con = sqlite3.connect(db)
        con.executescript(
            "CREATE TABLE price_history(symbol TEXT, date TEXT);"
            "CREATE TABLE instruments(ins_code TEXT, l_val18 TEXT);"
            "CREATE TABLE adjust_events(symbol TEXT, date TEXT);")
        con.executemany(
            "INSERT INTO price_history VALUES (?,?)",
            [("الف", "2026-01-01"), ("ج", "2026-01-01"),
             ("د", "2026-01-01")])
        con.executemany(
            "INSERT INTO instruments VALUES (?,?)",
            [("1", "الف"), ("2", "ب"), ("3", "ب")])
        con.executemany(
            "INSERT INTO adjust_events VALUES (?,?)",
            [("الف", "2020-01-01"), ("الف", "2021-01-01")])
        con.commit()

        # "ب " is the same identity as "ب": a separator character must not
        # create a second pack symbol, and it still covers an instruments-only
        # symbol.
        rep = S.reconcile(con, pack_symbols={"د", "ب "}, pack_steps=2,
                          legacy_pack_symbols={"ب"}, legacy_pack_steps=1,
                          report_value=2)
        con.close()
        assert rep["history_symbols"] == 3, rep
        assert rep["instruments"] == 3 and rep["instruments_named"] == 2, rep
        assert rep["duplicate_instrument_names"] == 1, rep
        assert rep["instruments_duplicate_name_rows"] == 1, rep
        assert rep["history_outside_instruments"] == 2, rep
        assert rep["instruments_without_history"] == 1, rep
        assert rep["instruments_with_history"] == 1, rep
        assert rep["instruments_rows_with_history"] == 1, rep
        assert rep["instruments_rows_without_history"] == 2, rep
        assert rep["union_symbols"] == 4, rep
        assert rep["duplicate_instrument_keys"] == [
            {"key": "ب", "rows": 2, "candidates": 2,
             "ins_codes": ["2", "3"], "in_history": False}], rep

        assert rep["pack_symbols"] == 2 and rep["pack_raw_symbols"] == 2, rep
        assert rep["pack_alias_spellings"] == 0, rep
        assert rep["history_symbols_with_pack_steps"] == 1, rep
        assert rep["history_symbols_without_pack_steps"] == 2, rep
        assert rep["pack_symbols_without_history"] == 1, rep

        assert rep["product_events"] == {
            "table": "adjust_events", "rows": 2, "raw_symbols": 1,
            "symbols": 1, "history_symbols_with_events": 1,
            "symbols_outside_history": 0,
            "raw_symbols_outside_history": 0}, rep["product_events"]
        assert rep["no_adjustment_evidence"] == {
            "definition": S.NO_EVIDENCE_DEFINITION, "pack": "current",
            "history_symbols_with_evidence": 2,
            "history_symbols_without_evidence": 1,
            "instruments_without_history": 1,
            "union_symbols_without_evidence": 1,
            "history_plus_instruments_identity": 1}, rep
        # Raw spellings are counted as written, keys after normalisation:
        # "ب " is a fifth raw spelling and a second spelling without history.
        assert rep["raw_universe"]["symbols"] == 5, rep["raw_universe"]
        assert rep["raw_universe"]["no_price_history"] == 2, rep["raw_universe"]

        # The r32b block is the report's definition, not a second count: the
        # instrument-only key covered by the legacy pack never needs evidence,
        # the history key only the current pack covers is still counted, and
        # the pack delta explains the difference.
        legacy = rep["report_no_evidence"]
        assert legacy["report_value"] == 2, legacy
        assert legacy["union_symbols_without_evidence"] == 2, legacy
        assert legacy["history_symbols_without_evidence"] == 2, legacy
        assert legacy["instruments_without_history"] == 1, legacy
        assert legacy["history_plus_instruments_identity"] == 2, legacy
        assert legacy["reproduces_report_value"] is True, legacy
        assert legacy["current_pack"]["union_symbols_without_evidence"] == 1, legacy
        assert legacy["current_pack"]["pack_delta"] == {
            "added_keys": 1, "added_without_product_event": 1,
            "dropped_keys": 0, "dropped_without_product_event": 0,
            "dropped_key_list": [], "net_no_evidence_delta": -1}, legacy
        assert "history_validity" not in rep, rep

        # End to end: pack files in, evidence JSON + CSV + checks out.
        pack_dir = os.path.join(tmp, "pack")
        os.makedirs(pack_dir)
        with open(os.path.join(pack_dir, "factors.jsonl"), "w",
                  encoding="utf-8", newline="\n") as fh:
            for symbol in ("د", "ب "):
                fh.write(json.dumps({"action": "replace_step",
                                     "symbol": symbol},
                                    ensure_ascii=False) + "\n")
        legacy_dir = os.path.join(tmp, "legacy")
        os.makedirs(legacy_dir)
        with open(os.path.join(legacy_dir, "factors.jsonl"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({"action": "replace_step", "symbol": "ب"},
                                ensure_ascii=False) + "\n")
        out = os.path.join(tmp, "evidence", "inventory.json")
        csv_path = os.path.join(tmp, "ledgers", "inventory.csv")
        built = S.build(db, pack_dir, legacy_dir, out, csv_path, "")
        assert built["checks"] and all(built["checks"].values()), built["checks"]
        assert built["overlaps"]["pack_and_product"] == 0, built["overlaps"]
        with open(out, encoding="utf-8") as fh:
            on_disk = json.load(fh)
        assert on_disk["report_no_evidence"][
            "union_symbols_without_evidence"] == 2, on_disk
        with open(csv_path, encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 4, rows
        assert set(rows[0]) == set(S.FIELDS), rows[0]
        by_key = {r["key"]: r for r in rows}
        assert by_key["ب"]["bucket"] == "instruments_only", by_key["ب"]
        assert by_key["ب"]["evidence"] == "pack", by_key["ب"]
        assert by_key["ب"]["ins_codes"] == "2|3", by_key["ب"]
        assert by_key["ج"]["bucket"] == "history_only", by_key["ج"]
        assert by_key["ج"]["evidence"] == "none", by_key["ج"]
        assert by_key["الف"]["evidence"] == "product", by_key["الف"]
        assert int(by_key["الف"]["product_event_rows"]) == 2, by_key["الف"]
        assert by_key["د"]["evidence"] == "pack", by_key["د"]


def main():
    fd, p = tempfile.mkstemp(suffix=".db"); os.close(fd)
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE price_history(symbol TEXT,date TEXT)")
    con.execute("CREATE TABLE instruments(ins_code TEXT,l_val18 TEXT)")
    con.execute("INSERT INTO instruments VALUES('1','الف')")
    con.execute("INSERT INTO instruments VALUES('2','ب')")
    con.execute("INSERT INTO price_history VALUES('الف','2026-01-01')")
    con.execute("INSERT INTO price_history VALUES('ج','2026-01-01')")
    con.commit()
    r = S.reconcile(con)
    assert r["history_symbols"] == 2 and r["instruments"] == 2
    assert r["history_outside_instruments"] == 1
    assert r["instruments_without_history"] == 1
    con.close(); os.unlink(p)
    print("INVENTORY TESTS OK")
    _edge_tests()
    print("INVENTORY EDGE TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
