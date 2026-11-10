#!/usr/bin/env python3
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage06_anomaly_ledger as S  # noqa: E402


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

    # The first bar of a symbol is never compared with itself: no seed means
    # no OPEN_EQ_PREV_CLOSE, which is the false event the sketch manufactured.
    first_only = [{"symbol": "B", "date": "2020-01-01", "open": 7,
                   "high": 7, "low": 7, "close": 7, "volume": 5}]
    assert S.detect(first_only) == [], S.detect(first_only)

    # A no-trade row whose flat price is carried forward is a calendar gap;
    # a traded opening at the prior close is a price-basis difference.
    carried = [
        {"symbol": "C", "date": "2020-01-01", "open": 5, "high": 6,
         "low": 4, "close": 5, "volume": 9},
        {"symbol": "C", "date": "2020-01-02", "open": 5, "high": 5,
         "low": 5, "close": 5, "volume": 0},
    ]
    by_kind = {a["kind"]: a for a in S.detect(
        carried, date_stats={"2020-01-01": (3, 3), "2020-01-02": (3, 2)})}
    assert by_kind["ZERO_VOLUME"]["root_cause"] == "no_trade_carried_close"
    assert by_kind["ZERO_VOLUME"]["category"] == "CALENDAR_GAP"
    assert by_kind["OPEN_EQ_PREV_CLOSE"]["category"] == "CALENDAR_GAP"

    traded = [
        {"symbol": "D", "date": "2020-01-01", "open": 5, "high": 6,
         "low": 4, "close": 5, "volume": 9},
        {"symbol": "D", "date": "2020-01-02", "open": 5, "high": 7,
         "low": 4, "close": 6, "volume": 9},
    ]
    by_kind = {a["kind"]: a for a in S.detect(traded)}
    assert by_kind["OPEN_EQ_PREV_CLOSE"]["category"] == "PRICE_BASIS_DIFFERENCE"
    assert by_kind["OPEN_EQ_PREV_CLOSE"]["root_cause"] == "open_at_prior_close"

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
    print("ANOMALY EDGE TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
