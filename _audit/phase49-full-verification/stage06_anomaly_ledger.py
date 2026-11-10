#!/usr/bin/env python3
"""Stage 06 - OHLC/anomaly ledger: every invalid candle with a root cause.

One event per (symbol, date, anomaly kind). The five kinds are the ones the
design names in section 8.5 - ``INVALID_OHLC``, ``ZERO_FIELDS``,
``OPEN_EQ_PREV_CLOSE``, ``ZERO_VOLUME`` and ``DUPLICATE_DATE`` - and each event
carries one of the 13 reconciliation categories from section 9 (the list is
read from ``dev/phase49_status_rules.json``; nothing is redefined here).

Root cause method (evidence first, no guess promoted to fact)
--------------------------------------------------------------
``INVALID_OHLC``
    The predicate is data-complete: a null field, a nonpositive value, a
    ``high < low`` inversion, an open outside ``[low, high]`` or a close
    outside ``[low, high]``. The 306 rows in the Seed split into two shapes
    that are root-caused from the row itself: ``open = 0`` with a valid shadow
    (12) and ``open = high = low = 0`` with a positive close (294). Both are
    ``INVALID_SOURCE_RECORD``; the contract's ``candle_contract.widen`` docstring
    already states that zero in ``high|low`` means "the source has not filled
    it", which is exactly these rows. All 306 carry ``src = legacy-unknown``
    and none resolves to a ``daily_prices`` row, so no independent witness
    exists in this DB; the ledger reports what the row contains, not a repair.

``ZERO_FIELDS``
    ``open = high = low = close = 0``. Measured: 0 rows. Kept as a check so a
    future Seed that introduces them cannot pass silently.

``OPEN_EQ_PREV_CLOSE``
    ``open`` equals the previous bar's close exactly (``EXACT_EQ`` = 1e-9).
    The previous close is the preceding row of the same symbol in date order;
    the first bar of a symbol is never compared with itself (the sketch this
    stage replaces seeded the first bar with its own close, which would have
    manufactured one false event per flat first bar). The equality is a
    price-basis signal: the open carries no information of its own. It occurs
    in every writer (legacy 11.9%, board 10.8%, rahavard365 6.4%), so it is a
    general data property, not one writer's bug. Without an intraday source
    the equality cannot be proven to be a copied base price rather than a real
    opening at the prior close; the category is ``PRICE_BASIS_DIFFERENCE`` and
    the counts file records that verification status explicitly.

``ZERO_VOLUME``
    The row records no trade. The root cause is read from the row and the
    whole-DB session evidence, in this order: a date on which no row of the DB
    traded at all (``market_no_session``); a non-flat bar with zero volume
    (``no_trade_price_range`` - prices moved without volume, an inconsistent
    record); the symbol's first bar (``no_trade_first_bar``); a flat bar whose
    close equals the previous close (``no_trade_carried_close`` - the price was
    carried, no trade); a flat bar whose close differs (``no_trade_price_change``
    - a price change with no volume, again an inconsistent record). The first
    two of the last four are ``CALENDAR_GAP`` (the session produced no trade);
    the inconsistent records are ``INVALID_SOURCE_RECORD``.

    ``instrument_state`` cannot root-cause these rows: its five snapshots cover
    2026-10-05..2026-10-11 and the last zero-volume row is 2026-09-30, so there
    is zero overlap. The counts file states that a halt cannot be separated
    from a plain no-trade day in this DB instead of inventing a halt flag.

``DUPLICATE_DATE``
    ``price_history`` has ``PRIMARY KEY (symbol, date)``, so a duplicate is
    structurally impossible in the Seed; the SQL check returns 0 and the ledger
    keeps the detector for an input that is not this table.

An event whose branch set does not explain the row is emitted with root cause
``UNEXPLAINED`` and category ``UNRESOLVED_SOURCE_GAP``; the build fails when
that count is not zero, so "all anomalies categorized" is machine-checked
rather than asserted in prose.

CLI:
    python _audit/phase49-full-verification/stage06_anomaly_ledger.py \\
        --db _audit/phase49-finalization/seed/market.db \\
        --out _audit/phase49-full-verification/ledgers/anomaly-ledger.csv

The CSV belongs in the gitignored ``ledgers/`` area; the tracked outputs are
the small counts summary and the stage manifest under ``evidence/``. Stdlib
only, the Seed DB is opened read-only, no network call.
"""
import argparse
import collections
import csv
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.append(ROOT)
_DEV = os.path.join(ROOT, "dev")
while _DEV in sys.path:
    sys.path.remove(_DEV)
sys.path.insert(0, _DEV)

import phase49_manifest as PM  # noqa: E402

DEFAULT_RULES = os.path.join(ROOT, "dev", "phase49_status_rules.json")
DEFAULT_COUNTS = os.path.join(HERE, "evidence", "anomaly-counts.json")
DEFAULT_MANIFEST = os.path.join(HERE, "evidence",
                                "stage06_anomaly_ledger.manifest.json")

KINDS = ("INVALID_OHLC", "ZERO_FIELDS", "OPEN_EQ_PREV_CLOSE", "ZERO_VOLUME",
         "DUPLICATE_DATE")

# The sketch mapping of the brief, kept as the documented default per kind.
BASE_CATEGORY = {
    "INVALID_OHLC": "INVALID_SOURCE_RECORD",
    "ZERO_FIELDS": "INVALID_SOURCE_RECORD",
    "OPEN_EQ_PREV_CLOSE": "PRICE_BASIS_DIFFERENCE",
    "ZERO_VOLUME": "CALENDAR_GAP",
    "DUPLICATE_DATE": "INVALID_SOURCE_RECORD",
}

# Root cause -> category. Every root cause names a real, measured branch; the
# category follows the cause instead of being copied from the kind, so a
# zero-volume row that cannot be a no-trade session (prices moved) is not
# filed as a calendar gap.
ROOT_CATEGORY = {
    "missing_value": "INVALID_SOURCE_RECORD",
    "shadow_inverted": "INVALID_SOURCE_RECORD",
    "source_shadow_and_open_zero": "INVALID_SOURCE_RECORD",
    "source_open_zero": "INVALID_SOURCE_RECORD",
    "close_outside_shadow": "INVALID_SOURCE_RECORD",
    "open_outside_shadow": "INVALID_SOURCE_RECORD",
    "nonpositive_price": "INVALID_SOURCE_RECORD",
    "all_ohlc_zero": "INVALID_SOURCE_RECORD",
    "volume_null": "INVALID_SOURCE_RECORD",
    "market_no_session": "CALENDAR_GAP",
    "no_trade_carried_close": "CALENDAR_GAP",
    "no_trade_price_range": "INVALID_SOURCE_RECORD",
    "no_trade_first_bar": "INVALID_SOURCE_RECORD",
    "no_trade_price_change": "INVALID_SOURCE_RECORD",
    "open_at_prior_close_no_trade": "CALENDAR_GAP",
    "flat_bar_at_prior_close": "PRICE_BASIS_DIFFERENCE",
    "prior_close_with_flat_shadow": "PRICE_BASIS_DIFFERENCE",
    "open_at_prior_close": "PRICE_BASIS_DIFFERENCE",
    "duplicate_primary_key": "INVALID_SOURCE_RECORD",
    "UNEXPLAINED": "UNRESOLVED_SOURCE_GAP",
}

FIELDS = ("symbol", "date", "kind", "category", "root_cause", "evidence")

_RULES_CACHE = {}


def load_rules(path=DEFAULT_RULES):
    path = os.path.abspath(path)
    if path in _RULES_CACHE:
        return _RULES_CACHE[path]
    with open(path, encoding="utf-8-sig") as fh:
        payload = json.load(fh)
    categories = list(payload.get("reconciliation_categories") or [])
    if len(categories) != 13:
        raise ValueError("reconciliation_categories must hold 13 entries, "
                         "found %d" % len(categories))
    used = set(BASE_CATEGORY.values()) | set(ROOT_CATEGORY.values())
    unknown = sorted(used - set(categories))
    if unknown:
        raise ValueError("categories outside the frozen list: %r" % unknown)
    tol = payload.get("tolerances") or {}
    rules = {
        "categories": categories,
        "exact_eq": float(tol.get("EXACT_EQ", 1e-9)),
    }
    _RULES_CACHE[path] = rules
    return rules


def _fmt(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return "%.10g" % value
    return str(value)


def _ev(**kwargs):
    return ";".join("%s=%s" % (name, _fmt(value))
                    for name, value in kwargs.items())


def _event(symbol, date, kind, root_cause, evidence):
    return {
        "symbol": symbol,
        "date": date,
        "kind": kind,
        "category": ROOT_CATEGORY.get(root_cause, BASE_CATEGORY[kind]),
        "root_cause": root_cause,
        "evidence": evidence,
    }


def _invalid_root(reasons, o, h, l, c):
    if "null_field" in reasons:
        return "missing_value"
    if "high_lt_low" in reasons:
        return "shadow_inverted"
    if (o is not None and h is not None and l is not None and c is not None
            and o <= 0 and h <= 0 and l <= 0 and c > 0):
        return "source_shadow_and_open_zero"
    if o is not None and h is not None and l is not None and o <= 0 \
            and h > 0 and l > 0:
        return "source_open_zero"
    if "close_outside_shadow" in reasons:
        return "close_outside_shadow"
    if "open_outside_shadow" in reasons:
        return "open_outside_shadow"
    if any(reason.endswith("_nonpositive") for reason in reasons):
        return "nonpositive_price"
    return "UNEXPLAINED"


def _date_stats(rows):
    stats = {}
    for row in rows:
        entry = stats.setdefault(row["date"], [0, 0])
        entry[0] += 1
        if row.get("volume"):
            entry[1] += 1
    return {date: (value[0], value[1]) for date, value in stats.items()}


def detect(rows, prev_close=None, date_stats=None, rules=None):
    """Return one event per anomaly, in (symbol, date, kind) input order.

    ``rows`` must be ordered by (symbol, date); ``prev_close`` may seed the
    first bar (symbol key) or override one bar ((symbol, date) key). When
    ``date_stats`` is absent it is measured from ``rows`` itself, so a caller
    that passes a fragment (the unit test) gets session evidence for that
    fragment only; the CLI always passes the whole-DB table.
    """
    rules = rules or {}
    exact = float(rules.get("exact_eq", (rules.get("tolerances") or {}).get(
        "EXACT_EQ", 1e-9)))
    seeds, overrides = {}, {}
    for key, value in (prev_close or {}).items():
        if isinstance(key, tuple):
            overrides[key] = value
        else:
            seeds[key] = value
    if date_stats is None:
        rows = list(rows)
        date_stats = _date_stats(rows)
    prev = dict(seeds)
    prev_date = {}
    run_start = {}
    seen = set()
    out = []
    for row in rows:
        symbol = row["symbol"]
        date = row["date"]
        o = row.get("open")
        h = row.get("high")
        l = row.get("low")
        c = row.get("close")
        v = row.get("volume")
        key = (symbol, date)

        if key in seen:
            out.append(_event(symbol, date, "DUPLICATE_DATE",
                              "duplicate_primary_key",
                              "same_symbol_date_seen_twice"))
        seen.add(key)

        reasons = []
        if None in (o, h, l, c):
            reasons.append("null_field")
        else:
            if o <= 0:
                reasons.append("open_nonpositive")
            if h <= 0:
                reasons.append("high_nonpositive")
            if l <= 0:
                reasons.append("low_nonpositive")
            if c <= 0:
                reasons.append("close_nonpositive")
            if h < l:
                reasons.append("high_lt_low")
            if o < l or o > h:
                reasons.append("open_outside_shadow")
            if c < l or c > h:
                reasons.append("close_outside_shadow")
        if reasons:
            out.append(_event(
                symbol, date, "INVALID_OHLC",
                _invalid_root(reasons, o, h, l, c),
                "reasons=%s;%s" % (",".join(reasons),
                                   _ev(open=o, high=h, low=l, close=c,
                                       volume=v, src=row.get("src")))))
            if ((o is not None and h is not None and l is not None
                 and c is not None and o == 0 and h == 0 and l == 0
                 and c == 0)):
                out.append(_event(symbol, date, "ZERO_FIELDS", "all_ohlc_zero",
                                  _ev(open=o, high=h, low=l, close=c,
                                      volume=v)))

        pc = overrides.get(key, prev.get(symbol))
        pd = prev_date.get(symbol)
        if o is not None and pc is not None and abs(o - pc) <= exact:
            if v is not None and v <= 0:
                out.append(_event(
                    symbol, date, "OPEN_EQ_PREV_CLOSE",
                    "open_at_prior_close_no_trade",
                    _ev(open=o, prev_close=pc, prev_date=pd, volume=v, close=c)))
            elif o == h == l == c:
                out.append(_event(
                    symbol, date, "OPEN_EQ_PREV_CLOSE",
                    "flat_bar_at_prior_close",
                    _ev(open=o, prev_close=pc, prev_date=pd, volume=v,
                        high=h, low=l, close=c)))
            elif h == l:
                out.append(_event(
                    symbol, date, "OPEN_EQ_PREV_CLOSE",
                    "prior_close_with_flat_shadow",
                    _ev(open=o, prev_close=pc, prev_date=pd, volume=v,
                        high=h, low=l, close=c)))
            else:
                out.append(_event(
                    symbol, date, "OPEN_EQ_PREV_CLOSE", "open_at_prior_close",
                    _ev(open=o, prev_close=pc, prev_date=pd, volume=v,
                        high=h, low=l, close=c)))

        if not v:
            date_rows, date_traded = date_stats.get(date, (0, 0))
            flat = (o == h == l == c) if None not in (o, h, l, c) else False
            held_since = run_start.get(symbol, date)
            if v is None:
                root = "volume_null"
            elif date_rows > 0 and date_traded == 0:
                root = "market_no_session"
            elif not flat:
                root = "no_trade_price_range"
            elif pc is None:
                root = "no_trade_first_bar"
            elif abs(c - pc) <= exact:
                root = "no_trade_carried_close"
            else:
                root = "no_trade_price_change"
            run_start.setdefault(symbol, date)
            out.append(_event(
                symbol, date, "ZERO_VOLUME", root,
                _ev(open=o, high=h, low=l, close=c, volume=v, flat=flat,
                    prev_close=pc, prev_date=pd, held_since=held_since,
                    date_rows=date_rows, date_traded=date_traded,
                    src=row.get("src"))))
        else:
            run_start.pop(symbol, None)

        if c is not None:
            prev[symbol] = c
            prev_date[symbol] = date
    return out


# --------------------------------------------------------------------------
# Build / CLI
# --------------------------------------------------------------------------

def _connect(db):
    con = sqlite3.connect(
        "file:%s?mode=ro" % os.path.abspath(db).replace("\\", "/"), uri=True)
    con.row_factory = sqlite3.Row
    return con


def _rel(path):
    try:
        rel = os.path.relpath(os.path.abspath(path), ROOT)
    except ValueError:
        rel = os.path.abspath(path)
    return rel.replace("\\", "/")


BAD_SQL = ("(open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL "
           "OR open<=0 OR high<=0 OR low<=0 OR close<=0 OR high<low "
           "OR open<low OR open>high OR close<low OR close>high)")


def _grouped(con, column_sql, exact):
    """Comparable rows and exact open-at-prior-close matches per group.

    Only bars with a preceding bar in the same symbol are comparable, so the
    rate never divides by a first bar that has no previous close.
    """
    query = (
        "WITH x AS (SELECT %s AS grp, open, "
        "LAG(close) OVER (PARTITION BY symbol ORDER BY date) AS pc "
        "FROM price_history) "
        "SELECT COALESCE(grp,'null'), COUNT(*), "
        "SUM(CASE WHEN ABS(open-pc)<=? THEN 1 ELSE 0 END) "
        "FROM x WHERE pc IS NOT NULL GROUP BY grp ORDER BY grp"
        % column_sql)
    out = {}
    for grp, total, equal in con.execute(query, (exact,)):
        out[str(grp)] = {
            "comparisons": int(total),
            "open_eq_prev_close": int(equal or 0),
            "rate": round(float(equal or 0) / total, 4) if total else 0.0,
        }
    return out


def _sql_counts(con):
    one = con.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
    zero_volume = con.execute(
        "SELECT COUNT(*) FROM price_history WHERE COALESCE(volume,0)=0"
    ).fetchone()[0]
    invalid = con.execute(
        "SELECT COUNT(*) FROM price_history WHERE " + BAD_SQL).fetchone()[0]
    zero_fields = con.execute(
        "SELECT COUNT(*) FROM price_history WHERE open=0 AND high=0 "
        "AND low=0 AND close=0").fetchone()[0]
    duplicates = con.execute(
        "SELECT COUNT(*) FROM (SELECT 1 FROM price_history "
        "GROUP BY symbol,date HAVING COUNT(*)>1)").fetchone()[0]
    return {"rows": int(one), "zero_volume": int(zero_volume),
            "invalid_ohlc": int(invalid), "zero_fields": int(zero_fields),
            "duplicate_dates": int(duplicates)}


def _iso_even(value):
    text = str(value or "")
    if len(text) != 8 or not text.isdigit():
        return ""
    return "%s-%s-%s" % (text[:4], text[4:6], text[6:])


def _witness(con, events):
    """How many invalid rows have an instruments and a daily_prices witness."""
    if not events:
        return {"rows": 0, "instruments_matched": 0,
                "daily_prices_matched": 0}
    ins = {}
    for name, code in con.execute(
            "SELECT l_val18,ins_code FROM instruments "
            "WHERE l_val18 IS NOT NULL AND TRIM(l_val18)<>''"):
        ins.setdefault(name, code)
    matched = hits = 0
    for event in events:
        code = ins.get(event["symbol"])
        if not code:
            continue
        matched += 1
        day = int(event["date"].replace("-", ""))
        if con.execute(
                "SELECT 1 FROM daily_prices WHERE ins_code=? AND d_even=? "
                "LIMIT 1", (code, day)).fetchone():
            hits += 1
    return {"rows": len(events), "instruments_matched": matched,
            "daily_prices_matched": hits}


def _cross(events, left, right):
    out = collections.defaultdict(lambda: collections.Counter())
    for event in events:
        out[str(event[left])][str(event[right])] += 1
    return {key: dict(sorted(value.items()))
            for key, value in sorted(out.items())}


def build(db, out, counts_path, manifest_path="", rules_path=DEFAULT_RULES,
          expect_rows=0):
    rules = load_rules(rules_path)
    categories = rules["categories"]
    exact = rules["exact_eq"]
    con = _connect(db)
    try:
        sql = _sql_counts(con)
        head = con.execute(
            "SELECT COUNT(DISTINCT symbol), COUNT(DISTINCT date), "
            "MIN(date), MAX(date) FROM price_history").fetchone()
        symbols, dates, first_date, last_date = (
            int(head[0]), int(head[1]), str(head[2]), str(head[3]))
        date_stats = {}
        session_rows = []
        for date, total, traded in con.execute(
                "SELECT date, COUNT(*), SUM(CASE WHEN COALESCE(volume,0)>0 "
                "THEN 1 ELSE 0 END) FROM price_history GROUP BY date"):
            date_stats[date] = (int(total), int(traded or 0))
            if not traded:
                session_rows.append((date, int(total)))
        cursor = con.execute(
            "SELECT symbol,date,open,high,low,close,volume,src "
            "FROM price_history ORDER BY symbol,date")
        events = detect((dict(row) for row in cursor), date_stats=date_stats,
                        rules=rules)

        by_kind = {kind: 0 for kind in KINDS}
        by_category = {name: 0 for name in categories}
        by_root = collections.Counter()
        invalid_reasons = collections.Counter()
        for event in events:
            if event["category"] not in by_category:
                raise ValueError("event with unknown category: %r" % (event,))
            by_kind[event["kind"]] += 1
            by_category[event["category"]] += 1
            by_root[event["root_cause"]] += 1
            if event["kind"] == "INVALID_OHLC":
                detail = event["evidence"].split(";", 1)[0]
                for reason in detail[len("reasons="):].split(","):
                    if reason:
                        invalid_reasons[reason] += 1
        if sum(by_kind.values()) != len(events):
            raise ValueError("kind counts do not sum to the row count")
        if sum(by_category.values()) != len(events):
            raise ValueError("category counts do not sum to the row count")
        if by_root.get("UNEXPLAINED"):
            raise ValueError("%d rows have no root cause"
                             % by_root["UNEXPLAINED"])
        if by_kind["ZERO_VOLUME"] != sql["zero_volume"]:
            raise ValueError("ZERO_VOLUME %d != SQL zero-volume %d"
                             % (by_kind["ZERO_VOLUME"], sql["zero_volume"]))
        if by_kind["INVALID_OHLC"] != sql["invalid_ohlc"]:
            raise ValueError("INVALID_OHLC %d != SQL invalid %d"
                             % (by_kind["INVALID_OHLC"], sql["invalid_ohlc"]))
        if by_kind["ZERO_FIELDS"] != sql["zero_fields"]:
            raise ValueError("ZERO_FIELDS %d != SQL zero-fields %d"
                             % (by_kind["ZERO_FIELDS"], sql["zero_fields"]))
        if by_kind["DUPLICATE_DATE"] != sql["duplicate_dates"]:
            raise ValueError("DUPLICATE_DATE %d != SQL duplicates %d"
                             % (by_kind["DUPLICATE_DATE"],
                                sql["duplicate_dates"]))
        if expect_rows and sql["rows"] != expect_rows:
            raise ValueError("expected %d rows, found %d"
                             % (expect_rows, sql["rows"]))

        row_keys = {(event["symbol"], event["date"]) for event in events}
        affected = collections.defaultdict(set)
        for event in events:
            affected[event["kind"]].add((event["symbol"], event["date"]))

        zero_volume = [e for e in events if e["kind"] == "ZERO_VOLUME"]
        open_eq = [e for e in events if e["kind"] == "OPEN_EQ_PREV_CLOSE"]
        invalid = [e for e in events if e["kind"] == "INVALID_OHLC"]
        invalid_roots = collections.Counter(e["root_cause"] for e in invalid)
        zero_roots = collections.Counter(e["root_cause"] for e in zero_volume)
        open_roots = collections.Counter(e["root_cause"] for e in open_eq)

        sql_open_eq = _grouped(con, "src", exact)
        year_open_eq = _grouped(con, "substr(date,1,4)", exact)
        sql_invalid_by_src = {
            str(src): int(count) for src, count in con.execute(
                "SELECT COALESCE(src,'null'),COUNT(*) FROM price_history "
                "WHERE " + BAD_SQL + " GROUP BY 1 ORDER BY 1")}
        sql_zero_by_src = {
            str(src): int(count) for src, count in con.execute(
                "SELECT COALESCE(src,'null'),COUNT(*) FROM price_history "
                "WHERE COALESCE(volume,0)=0 GROUP BY 1 ORDER BY 1")}
        witness = _witness(con, invalid)
        state = con.execute(
            "SELECT MIN(d_even),MAX(d_even),COUNT(DISTINCT d_even) "
            "FROM instrument_state").fetchone()
        zero_last = con.execute(
            "SELECT MAX(date) FROM price_history WHERE COALESCE(volume,0)=0"
        ).fetchone()[0]
        overlap = con.execute(
            "SELECT COUNT(*) FROM price_history WHERE COALESCE(volume,0)=0 "
            "AND date IN (SELECT DISTINCT substr(CAST(d_even AS TEXT),1,4) "
            "|| '-' || substr(CAST(d_even AS TEXT),5,2) || '-' "
            "|| substr(CAST(d_even AS TEXT),7,2) FROM instrument_state)"
        ).fetchone()[0]
    finally:
        con.close()

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(FIELDS),
                                lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(events)

    payload = {
        "schema": 1,
        "stage": "stage06_anomaly_ledger",
        "rows_scanned": sql["rows"],
        "symbols": symbols,
        "dates": dates,
        "first_date": first_date,
        "last_date": last_date,
        "anomaly_events": len(events),
        "rows_with_anomaly": len(row_keys),
        "rows_with_anomaly_by_kind": {
            kind: len(keys) for kind, keys in sorted(affected.items())},
        "symbols_by_kind": {
            kind: len({symbol for symbol, _ in keys})
            for kind, keys in sorted(affected.items())},
        "by_kind": by_kind,
        "by_category": by_category,
        "by_root_cause": dict(sorted(by_root.items())),
        "kind_x_category": _cross(events, "kind", "category"),
        "kind_x_root_cause": _cross(events, "kind", "root_cause"),
        "invalid_ohlc": {
            "events": len(invalid),
            "rows": len(affected.get("INVALID_OHLC", ())),
            "by_root_cause": dict(sorted(invalid_roots.items())),
            "by_reason": dict(sorted(invalid_reasons.items())),
            "by_src": sql_invalid_by_src,
            "witness": witness,
            "unresolved_witness": (
                "%d of %d invalid rows have an instruments row and %d of those "
                "have a daily_prices row on the same day; the rest have no "
                "independent witness in this Seed"
                % (witness["instruments_matched"], witness["rows"],
                   witness["daily_prices_matched"])),
        },
        "zero_fields": {
            "events": by_kind["ZERO_FIELDS"],
            "check": "open=high=low=close=0",
        },
        "open_eq_prev_close": {
            "events": len(open_eq),
            "rows": len(affected.get("OPEN_EQ_PREV_CLOSE", ())),
            "by_root_cause": dict(sorted(open_roots.items())),
            "comparisons": sum(v["comparisons"]
                               for v in sql_open_eq.values()),
            "by_src": sql_open_eq,
            "by_year": year_open_eq,
            "verification": "unverified_no_intraday_witness",
            "method": ("previous close is the preceding bar of the same "
                       "symbol in date order; the first bar of a symbol is "
                       "never compared with itself"),
        },
        "zero_volume": {
            "events": len(zero_volume),
            "rows": len(affected.get("ZERO_VOLUME", ())),
            "by_root_cause": dict(sorted(zero_roots.items())),
            "by_src": sql_zero_by_src,
            "no_session_dates": [
                {"date": date, "rows": rows} for date, rows in session_rows],
            "no_session_rows": sum(rows for _, rows in session_rows),
            "last_zero_volume_date": zero_last,
            "instrument_state": {
                "first_date": _iso_even(state[0]) if state else "",
                "last_date": _iso_even(state[1]) if state else "",
                "snapshot_days": int(state[2] or 0) if state else 0,
                "overlap_with_zero_volume_rows": int(overlap or 0),
                "halt_attribution": ("not possible: zero overlap between the "
                                     "state snapshots and zero-volume rows"),
            },
            "method": ("date-level session evidence (no row traded all day) "
                       "then bar shape: flat/carried, flat/changed, non-flat"),
        },
        "duplicate_dates": {
            "events": by_kind["DUPLICATE_DATE"],
            "sql_check": sql["duplicate_dates"],
            "constraint": "PRIMARY KEY (symbol, date)",
        },
        "checks": {
            "uncategorized_events": (len(events)
                                     - sum(by_category.values())),
            "unexplained_events": by_root.get("UNEXPLAINED", 0),
            "categories_declared": len(categories),
            "categories_used": sum(1 for n in by_category.values() if n),
            "sql_crosscheck": {
                "zero_volume": sql["zero_volume"],
                "invalid_ohlc": sql["invalid_ohlc"],
                "zero_fields": sql["zero_fields"],
                "duplicate_dates": sql["duplicate_dates"],
                "all_match": True,
            },
        },
        "method": [
            "Anomaly detection is row-level and rule-based; the category is "
            "chosen from the measured root cause, not from the anomaly kind.",
            "Every event carries the raw values that triggered it in the "
            "evidence column of the CSV; the tracked counts hold aggregates "
            "only, no raw rows.",
            "A branch set that explains nothing is UNEXPLAINED / "
            "UNRESOLVED_SOURCE_GAP and fails the build; the measured count "
            "is zero in this Seed.",
        ],
        "notes": [
            "%d of the 13 categories are used (CALENDAR_GAP, "
            "INVALID_SOURCE_RECORD, PRICE_BASIS_DIFFERENCE). The ten zero "
            "categories are zero for a stated reason, not by omission: "
            "SOURCE_MISMATCH and SOURCE_REVISION need two sources for one "
            "row, and price_history keeps exactly one row per (symbol, date) "
            "with a writer tag, not a source pair; CORPORATE_ACTION_MISSING, "
            "EVENT_DATE_MISMATCH and EVENT_RATIO_MISMATCH are event-chain "
            "findings owned by B5/B6 and cannot be read from a bare candle; "
            "SYMBOL_IDENTITY_MISMATCH is B7's identity join; MISSING_HISTORY "
            "is the absence of rows, which is B7's gap count, not a row "
            "event; PRECISION_OR_ROUNDING needs a rounding divergence, and "
            "every compared price here is bit-equal or clearly different, so "
            "no row required it; VERIFIED_NO_EVENT is a verification claim, "
            "which this stage does not make; UNRESOLVED_SOURCE_GAP is zero "
            "because every event got a cause from the row or the session "
            "evidence."
            % sum(1 for n in by_category.values() if n),
            "All %d invalid OHLC rows carry %s; %d of them resolve to an "
            "instruments row and %d of those have a daily_prices row on the "
            "same day, so the root cause is the row's own field set and not a "
            "repair candidate."
            % (len(invalid),
               " and ".join("%s (%d rows)" % item
                            for item in sorted(sql_invalid_by_src.items())),
               witness["instruments_matched"],
               witness["daily_prices_matched"]),
            "Zero volume: %d rows, all %s. %d of them sit on the %d dates "
            "where no row of the DB traded at all (a date-level session "
            "evidence, not a per-symbol guess); the rest are flat bars whose "
            "close was carried (%d) or changed with no volume (%d), plus %d "
            "first bars and %d non-flat bars."
            % (len(zero_volume),
               " and ".join("%s (%d)" % item
                            for item in sorted(sql_zero_by_src.items())),
               sum(rows for _, rows in session_rows), len(session_rows),
               zero_roots.get("no_trade_carried_close", 0),
               zero_roots.get("no_trade_price_change", 0),
               zero_roots.get("no_trade_first_bar", 0),
               zero_roots.get("no_trade_price_range", 0)),
            "The brief's sketch seeded the first bar of a symbol with its own "
            "close and passed a single prev_close per symbol to every row; "
            "both would manufacture false OPEN_EQ_PREV_CLOSE rows. This stage "
            "uses the preceding bar of the same symbol and measures %d "
            "equalities over %d comparable rows."
            % (len(open_eq), sum(v["comparisons"]
                                 for v in sql_open_eq.values())),
            "The 6,328 'reported no evidence' symbols are B9's inventory "
            "reconciliation and are not touched here.",
        ],
        "inputs": {
            "db": _rel(db),
            "rules": _rel(rules_path),
            "rows": sql["rows"],
            "symbols": symbols,
            "dates": dates,
            "first_date": first_date,
            "last_date": last_date,
        },
    }
    os.makedirs(os.path.dirname(os.path.abspath(counts_path)), exist_ok=True)
    with open(counts_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    if manifest_path:
        PM.write_manifest(
            "stage06_anomaly_ledger",
            [_rel(db), _rel(rules_path)],
            [_rel(out), _rel(counts_path)],
            {"rows": len(events), **by_kind}, manifest_path)
    return events, payload


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--counts", default=DEFAULT_COUNTS)
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST,
                    help="stage manifest path ('' disables)")
    ap.add_argument("--rules", default=DEFAULT_RULES)
    ap.add_argument("--expect-rows", type=int, default=0,
                    help="fail when the price_history row count differs")
    args = ap.parse_args(argv)
    os.chdir(ROOT)
    try:
        events, payload = build(
            args.db, args.out, args.counts, args.manifest, args.rules,
            args.expect_rows)
    except (OSError, ValueError, sqlite3.Error) as exc:
        print("ANOMALY LEDGER FAIL: %s" % exc, file=sys.stderr)
        return 2
    print("anomalies: %d -> %s" % (len(events), args.out))
    print(json.dumps({"by_kind": payload["by_kind"],
                      "by_category": payload["by_category"]},
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
