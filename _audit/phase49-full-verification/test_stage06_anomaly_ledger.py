#!/usr/bin/env python3
import json
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage06_anomaly_ledger as S  # noqa: E402


def _by_kind(events):
    return {e["kind"]: e for e in events}


def _make_db(path):
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE price_history (symbol TEXT, date TEXT, open REAL, "
        "high REAL, low REAL, close REAL, volume REAL, last REAL, "
        "value REAL, src TEXT);"
        "CREATE TABLE instruments (ins_code TEXT PRIMARY KEY, l_val18 TEXT, "
        "l_val30 TEXT, sector_code TEXT, sector_name TEXT, total_shares REAL, "
        "eps REAL, pe REAL, base_vol REAL, updated_at TEXT, "
        "paper_type INTEGER, isin TEXT, c_gr_val_cot TEXT);"
        "CREATE TABLE daily_prices (ins_code TEXT, d_even INTEGER, "
        "p_closing REAL, price_min REAL, price_max REAL, price_yesterday REAL, "
        "price_first REAL, q_tot_tran REAL, q_tot_cap REAL, price_change REAL, "
        "fetched_at TEXT, market_cap REAL, market_cap_src TEXT, "
        "z_tot_tran REAL, p_last REAL, repair_src TEXT);"
        "CREATE TABLE instrument_state (ins_code TEXT, d_even INTEGER, "
        "c_etaval TEXT, c_etaval_title TEXT, under_supervision INTEGER, "
        "last_h_even INTEGER NOT NULL DEFAULT 0, real_heven INTEGER, "
        "source TEXT, fetched_at TEXT, "
        "PRIMARY KEY (ins_code, d_even, last_h_even));")
    # No primary key on price_history, so a triple can exist in this temp DB.
    triple = ("T", "2020-01-01", 3, 4, 3, 4, 2, None, None, "legacy-unknown")
    con.executemany(
        "INSERT INTO price_history VALUES (?,?,?,?,?,?,?,?,?,?)",
        [triple, triple, triple])
    # A second symbol with an open-at-prior-close and no witness: the residual
    # payload must count it and name the missing source.
    unresolved = [
        ("U", "2020-01-01", 5, 5, 5, 5, 1, None, None, "legacy-unknown"),
        ("U", "2020-01-02", 5, 5, 5, 5, 1, None, None, "legacy-unknown"),
    ]
    con.executemany(
        "INSERT INTO price_history VALUES (?,?,?,?,?,?,?,?,?,?)", unresolved)
    con.commit()
    con.close()


def main():
    rows = [
        {"symbol": "A", "date": "2020-01-01", "open": 10, "high": 10, "low": 10, "close": 10, "volume": 1},
        {"symbol": "A", "date": "2020-01-02", "open": 10, "high": 9, "low": 11, "close": 10, "volume": 1},
        {"symbol": "A", "date": "2020-01-03", "open": 10, "high": 10, "low": 10, "close": 10, "volume": 0},
    ]
    out = S.detect(rows, prev_close={"A": 10})
    kinds = {a["kind"] for a in out}
    assert "INVALID_OHLC" in kinds and "ZERO_VOLUME" in kinds, out
    assert all(a["category"] for a in out)
    print("ANOMALY TESTS OK")

    # --- additions for the controller rulings (the brief's test stays above) ---
    categories = set(S.load_rules()["categories"])
    assert len(categories) == 13
    assert all(a["category"] in categories for a in out)
    assert not any(a["root_cause"] == "UNEXPLAINED" for a in out)
    assert all(a["witness"] for a in out), out

    # The first bar of a symbol is never compared with itself: no seed means
    # no OPEN_EQ_PREV_CLOSE, which is the false event the sketch manufactured.
    first_only = [{"symbol": "B", "date": "2020-01-01", "open": 7,
                   "high": 7, "low": 7, "close": 7, "volume": 5}]
    assert S.detect(first_only) == [], S.detect(first_only)

    # A per-symbol no-trade day has no halt witness: both the carried close
    # and the equal open stay unresolved instead of claiming a calendar gap.
    carried = [
        {"symbol": "C", "date": "2020-01-01", "open": 5, "high": 6,
         "low": 4, "close": 5, "volume": 9},
        {"symbol": "C", "date": "2020-01-02", "open": 5, "high": 5,
         "low": 5, "close": 5, "volume": 0},
    ]
    by_kind = _by_kind(S.detect(
        carried, date_stats={"2020-01-01": (3, 3), "2020-01-02": (3, 2)}))
    assert by_kind["ZERO_VOLUME"]["root_cause"] == "no_trade_carried_close"
    assert by_kind["ZERO_VOLUME"]["category"] == "UNRESOLVED_SOURCE_GAP"
    assert by_kind["ZERO_VOLUME"]["witness"] == "none"
    assert by_kind["OPEN_EQ_PREV_CLOSE"]["category"] == "UNRESOLVED_SOURCE_GAP"
    assert (by_kind["OPEN_EQ_PREV_CLOSE"]["root_cause"]
            == "open_at_prior_close_unwitnessed")

    # A market-wide no-trade date is the only zero-volume calendar gap.
    by_kind = _by_kind(S.detect(
        carried, date_stats={"2020-01-01": (3, 3), "2020-01-02": (3, 0)}))
    assert by_kind["ZERO_VOLUME"]["category"] == "CALENDAR_GAP"
    assert by_kind["ZERO_VOLUME"]["witness"] == "session_calendar"
    assert by_kind["OPEN_EQ_PREV_CLOSE"]["category"] == "CALENDAR_GAP"
    assert (by_kind["OPEN_EQ_PREV_CLOSE"]["root_cause"]
            == "open_at_prior_close_no_session")

    # A halt snapshot on the exact symbol/date is a verified no-event.
    by_kind = _by_kind(S.detect(
        carried, date_stats={"2020-01-01": (3, 3), "2020-01-02": (3, 2)},
        halt_dates={("C", "2020-01-02"): "halted"}))
    assert by_kind["ZERO_VOLUME"]["category"] == "VERIFIED_NO_EVENT"
    assert by_kind["ZERO_VOLUME"]["witness"] == "halt:instrument_state"
    assert by_kind["OPEN_EQ_PREV_CLOSE"]["category"] == "VERIFIED_NO_EVENT"

    # A traded opening without a witness stays unresolved; it is not a basis.
    traded = [
        {"symbol": "D", "date": "2020-01-01", "open": 5, "high": 6,
         "low": 4, "close": 5, "volume": 9},
        {"symbol": "D", "date": "2020-01-02", "open": 5, "high": 7,
         "low": 4, "close": 6, "volume": 9},
    ]
    by_kind = _by_kind(S.detect(traded))
    assert by_kind["OPEN_EQ_PREV_CLOSE"]["category"] == "UNRESOLVED_SOURCE_GAP"
    assert by_kind["OPEN_EQ_PREV_CLOSE"]["witness"] == "none"

    # Basis witness on the price_history row: last != close.
    basis_rows = [
        {"symbol": "G", "date": "2020-01-01", "open": 5, "high": 6,
         "low": 4, "close": 5, "volume": 9, "last": 5},
        {"symbol": "G", "date": "2020-01-02", "open": 5, "high": 7,
         "low": 4, "close": 6, "volume": 9, "last": 7},
    ]
    ev = _by_kind(S.detect(basis_rows))["OPEN_EQ_PREV_CLOSE"]
    assert ev["category"] == "PRICE_BASIS_DIFFERENCE", ev
    assert ev["witness"] == "basis:last_vs_close", ev

    # Basis witness on the daily_prices row: p_last != p_closing.
    daily_basis = [
        {"symbol": "H", "date": "2020-01-01", "open": 5, "high": 6,
         "low": 4, "close": 5, "volume": 9},
        {"symbol": "H", "date": "2020-01-02", "open": 5, "high": 7,
         "low": 4, "close": 6, "volume": 9},
    ]
    ev = _by_kind(S.detect(
        daily_basis,
        daily_witness={("H", "2020-01-02"): {"last": 7, "closing": 6,
                                             "price_first": 0}})
    )["OPEN_EQ_PREV_CLOSE"]
    assert ev["category"] == "PRICE_BASIS_DIFFERENCE", ev
    assert ev["witness"] == "basis:p_last_vs_p_closing", ev

    # First-trade witness equal to open: a genuine opening, no event needed.
    daily_first = [
        {"symbol": "I", "date": "2020-01-01", "open": 5, "high": 6,
         "low": 4, "close": 5, "volume": 9},
        {"symbol": "I", "date": "2020-01-02", "open": 5, "high": 7,
         "low": 4, "close": 6, "volume": 9},
    ]
    by_kind = _by_kind(S.detect(
        daily_first,
        daily_witness={("I", "2020-01-02"): {"last": None, "closing": None,
                                             "price_first": 5}}))
    assert by_kind["OPEN_EQ_PREV_CLOSE"]["category"] == "VERIFIED_NO_EVENT"
    assert (by_kind["OPEN_EQ_PREV_CLOSE"]["witness"]
            == "first_trade:price_first_eq_open")

    # A first-trade witness that differs from open does not verify the event.
    by_kind = _by_kind(S.detect(
        daily_first,
        daily_witness={("I", "2020-01-02"): {"last": None, "closing": None,
                                             "price_first": 6}}))
    assert by_kind["OPEN_EQ_PREV_CLOSE"]["category"] == "UNRESOLVED_SOURCE_GAP"
    assert (by_kind["OPEN_EQ_PREV_CLOSE"]["witness"]
            == "first_trade:price_first_ne_open")

    # Both witnesses: the first-trade equality decides the open event, but
    # both tags stay recorded so the basis reading is recomputable.
    by_kind = _by_kind(S.detect(
        daily_first,
        daily_witness={("I", "2020-01-02"): {"last": 7, "closing": 6,
                                             "price_first": 5}}))
    assert by_kind["OPEN_EQ_PREV_CLOSE"]["category"] == "VERIFIED_NO_EVENT"
    assert "basis:p_last_vs_p_closing" in by_kind["OPEN_EQ_PREV_CLOSE"]["witness"]
    assert "first_trade:price_first_eq_open" in by_kind["OPEN_EQ_PREV_CLOSE"]["witness"]

    # A price range with zero volume is the only genuinely invalid zero-volume
    # shape; a flat price change with zero volume is not invalid.
    range_rows = [
        {"symbol": "J", "date": "2020-01-01", "open": 5, "high": 6,
         "low": 4, "close": 5, "volume": 9},
        {"symbol": "J", "date": "2020-01-02", "open": 5, "high": 7,
         "low": 4, "close": 7, "volume": 0},
        {"symbol": "K", "date": "2020-01-01", "open": 5, "high": 5,
         "low": 5, "close": 5, "volume": 9},
        {"symbol": "K", "date": "2020-01-02", "open": 6, "high": 6,
         "low": 6, "close": 6, "volume": 0},
    ]
    by_sym = {}
    for event in S.detect(range_rows,
                          date_stats={"2020-01-01": (3, 3),
                                      "2020-01-02": (3, 2)}):
        if event["kind"] == "ZERO_VOLUME":
            by_sym[event["symbol"]] = event
    assert by_sym["J"]["category"] == "INVALID_SOURCE_RECORD"
    assert by_sym["J"]["witness"] == "row_fields"
    assert by_sym["K"]["root_cause"] == "no_trade_price_change"
    assert by_sym["K"]["category"] == "UNRESOLVED_SOURCE_GAP"

    # Both measured invalid shapes are root-caused from the row itself.
    shapes = [
        {"symbol": "E", "date": "2020-01-01", "open": 0, "high": 9,
         "low": 8, "close": 8, "volume": 1},
        {"symbol": "E", "date": "2020-01-02", "open": 0, "high": 0,
         "low": 0, "close": 8, "volume": 1},
    ]
    inv = {a["date"]: a for a in S.detect(shapes) if a["kind"] == "INVALID_OHLC"}
    assert inv["2020-01-01"]["root_cause"] == "source_open_zero", inv
    assert inv["2020-01-02"]["root_cause"] == "source_shadow_and_open_zero", inv

    # A repeated key is classified, not silently merged.
    twin = [{"symbol": "F", "date": "2020-01-01", "open": 3, "high": 4,
             "low": 3, "close": 4, "volume": 2},
            {"symbol": "F", "date": "2020-01-01", "open": 3, "high": 4,
             "low": 3, "close": 4, "volume": 2}]
    dup = [a for a in S.detect(twin) if a["kind"] == "DUPLICATE_DATE"]
    assert len(dup) == 1 and dup[0]["category"] == "INVALID_SOURCE_RECORD", dup

    # A triple in a table without the primary key emits one event per extra
    # row and the SQL cross-check counts the same two rows, so the build
    # succeeds instead of failing closed on a count mismatch.
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "triple.db")
        _make_db(db)
        out_csv = os.path.join(tmp, "anomaly-ledger.csv")
        counts = os.path.join(tmp, "counts.json")
        events, payload = S.build(db, out_csv, counts, "")
        dup = [e for e in events if e["kind"] == "DUPLICATE_DATE"]
        assert len(dup) == 2, dup
        assert payload["by_kind"]["DUPLICATE_DATE"] == 2, payload["by_kind"]
        assert payload["duplicate_dates"]["sql_check"] == 2, payload
        assert payload["checks"]["uncategorized_events"] == 0, payload
        # The residual population is bound to its root cause and missing
        # source, not just counted.
        residual = payload["residual_unverified"]
        assert residual["events"] == 1, residual
        assert residual["by_kind"] == {"OPEN_EQ_PREV_CLOSE": 1,
                                       "ZERO_VOLUME": 0}, residual
        assert residual["by_root_cause"] == {
            "open_at_prior_close_unwitnessed": 1}, residual
        open_residual = payload["open_eq_prev_close"]["residual_unverified"]
        assert open_residual["by_root_cause"] == {
            "open_at_prior_close_unwitnessed": 1}, open_residual
        assert open_residual["missing_witness"]["rows_total"] == 1
        assert open_residual["required_source"]["primary"], open_residual
        assert open_residual["attempted"], open_residual
        assert open_residual["verdict"] == "UNRESOLVED_SOURCE_GAP"
        zero_residual = payload["zero_volume"]["residual_unverified"]
        assert zero_residual["events"] == 0, zero_residual
        assert zero_residual["by_root_cause"] == {}, zero_residual
        assert payload["open_eq_prev_close"]["basis_witness"][
            "identity_caveat"], payload["open_eq_prev_close"]
        with open(out_csv, encoding="utf-8") as fh:
            assert len(fh.read().splitlines()) == 1 + len(events)
        # The seven post-backfill drop classifications are attached for C5,
        # not re-categorized as candle anomalies.
        assert "post_backfill_anomalies" not in payload
        post_path = os.path.join(tmp, "post-backfill.json")
        with open(post_path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({
                "schema": "test-post-backfill",
                "events": [{}, {}],
                "counts": {
                    "events": 2, "new_rows": 2,
                    "by_category": {"UNRESOLVED_SOURCE_GAP": 2},
                    "blockers": 2,
                    "blocker_dates": [{"symbol": "S", "date": "2020-01-01"}]},
            }, fh)
        _, attached = S.build(
            db, os.path.join(tmp, "ledger-post.csv"),
            os.path.join(tmp, "counts-post.json"), "",
            post_backfill_path=post_path)
        post = attached["post_backfill_anomalies"]
        assert post["events"] == 2 and post["blockers"] == 2, post
        assert post["by_category"] == {"UNRESOLVED_SOURCE_GAP": 2}, post
        assert post["blocker_dates"] == [{"symbol": "S", "date": "2020-01-01"}], post
        assert post["schema"] == "test-post-backfill", post
    print("ANOMALY EDGE TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
