#!/usr/bin/env python3
"""Prove --since inserts only recent missing dates and stays idempotent."""
import contextlib
import gzip
import io
import json
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "phase48"))
import backfill_reference as B  # noqa: E402

SCHEMA = """CREATE TABLE price_history(
    symbol TEXT,date TEXT,open REAL,high REAL,low REAL,close REAL,
    volume REAL,last REAL,value REAL,src TEXT)"""


def make_db(path):
    con = sqlite3.connect(path)
    con.execute(SCHEMA)
    con.execute("INSERT INTO price_history VALUES('الف','2026-01-01',10,10,10,10,1,10,NULL,'legacy-unknown')")
    con.commit(); con.close()


def write_ref(path, rows):
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def ref_row(symbol, date, price):
    return {"symbol": symbol, "asset_id": 1, "type": "type0", "adjust": "raw",
            "resolution": "D", "date": date, "open": price, "high": price,
            "low": price, "close": price, "volume": 1}


def make_ref(path):
    write_ref(path, [ref_row("الف", "2025-12-30", 9),
                     ref_row("الف", "2026-01-02", 10)])


def dates_in(db_path, symbol):
    con = sqlite3.connect(db_path)
    try:
        return [r[0] for r in con.execute(
            "SELECT date FROM price_history WHERE symbol=? ORDER BY date", (symbol,))]
    finally:
        con.close()


def count_rahavard(db_path):
    con = sqlite3.connect(db_path)
    try:
        return con.execute(
            "SELECT COUNT(*) FROM price_history WHERE src='rahavard365'").fetchone()[0]
    finally:
        con.close()


def main():
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "src.db"); make_db(src)
    ref = os.path.join(tmp, "bars.ndjson.gz"); make_ref(ref)
    work = os.path.join(tmp, "work")
    rep = B.apply_backfill(src, work, ref, ["الف"], "test-since", since="2026-01-01")
    assert rep["totals"]["inserted"] == 1, rep["totals"]
    dates = dates_in(os.path.join(work, "market.db"), "الف")
    assert dates == ["2026-01-01", "2026-01-02"], dates
    rep2 = B.apply_backfill(src, work, ref, ["الف"], "test-since-2",
                            reuse_work=True, since="2026-01-01")
    assert rep2["totals"]["inserted"] == 0, rep2["totals"]

    # مرز: ردیفِ مرجع دقیقاً رویِ `since` کاندید است (≥، نه >)؛ پایین‌تر از آن نه.
    con = sqlite3.connect(src)
    con.execute("INSERT INTO price_history VALUES('ب','2026-01-05',20,20,20,20,1,20,NULL,'legacy-unknown')")
    con.commit(); con.close()
    bref = os.path.join(tmp, "bars-boundary.ndjson.gz")
    write_ref(bref, [ref_row("ب", "2025-12-31", 19),
                     ref_row("ب", "2026-01-01", 20),
                     ref_row("ب", "2026-01-03", 21)])
    brep = B.apply_backfill(src, os.path.join(tmp, "work-boundary"), bref,
                            ["ب"], "test-boundary", since="2026-01-01")
    assert brep["totals"]["inserted"] == 2, brep["totals"]
    assert brep["ref_rows"] == 2, brep["ref_rows"]  # ردیفِ بیرونِ پنجره کاندید نیست
    bdates = dates_in(os.path.join(tmp, "work-boundary", "market.db"), "ب")
    assert bdates == ["2026-01-01", "2026-01-03", "2026-01-05"], bdates

    # بدونِ `since`: رفتارِ پیشین دست‌نخورده — هر تاریخِ مفقود، از جمله گپِ قدیمی.
    nrep = B.apply_backfill(src, os.path.join(tmp, "work-nosince"), ref,
                            ["الف"], "test-no-since")
    assert nrep["totals"]["inserted"] == 2, nrep["totals"]
    ndates = dates_in(os.path.join(tmp, "work-nosince", "market.db"), "الف")
    assert ndates == ["2025-12-30", "2026-01-01", "2026-01-02"], ndates

    # CLI: `apply --since` به همان پنجره سیم‌کشی شده است (dry-run، بی‌نوشتن).
    syms = os.path.join(tmp, "symbols.csv")
    with open(syms, "w", encoding="utf-8") as fh:
        fh.write("symbol\nالف\n")
    out = os.path.join(tmp, "cli-report.json")
    rc = B.main(["apply", "--src", src, "--work", os.path.join(tmp, "work-cli"),
                 "--ref", ref, "--symbols", syms, "--run-id", "test-cli",
                 "--since", "2026-01-01", "--dry-run", "--out", out])
    assert rc == 0, rc
    with open(out, encoding="utf-8") as fh:
        cli = json.load(fh)
    assert cli["would_insert"] == 1 and cli["inserted"] == 0, cli["totals"]
    assert cli["ref_rows"] == 1, cli["ref_rows"]

    # CLI: a non-canonical `--since` is a parser error before any work: no DB,
    # no report, no inserted row. `2026-1-1` and `20260101` used to fall through
    # to a lexical filter and silently insert 0.
    for bad in ("2026-1-1", "20260101", "garbage", "2026-13-45"):
        bad_work = os.path.join(tmp, "work-bad-" + bad.replace("-", "_"))
        bad_out = os.path.join(tmp, "bad-" + bad.replace("-", "_") + ".json")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            try:
                brc = B.main(["apply", "--src", src, "--work", bad_work,
                              "--ref", ref, "--symbols", syms,
                              "--run-id", "test-bad-since",
                              "--since", bad, "--out", bad_out])
            except SystemExit as exc:
                brc = exc.code
        assert brc not in (0, None), (bad, brc)
        msg = err.getvalue()
        assert "--since" in msg and "canonical" in msg, (bad, msg)
        assert not os.path.exists(bad_out), (bad, "report written")
        bad_db = os.path.join(bad_work, "market.db")
        assert not os.path.exists(bad_db) or count_rahavard(bad_db) == 0, \
            (bad, "rows written")

    print("BACKFILL SINCE TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
