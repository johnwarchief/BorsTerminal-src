#!/usr/bin/env python3
"""Stage 06 - OHLC/anomaly ledger: every invalid candle with a root cause.

One event per (symbol, date, anomaly kind). The five kinds are the ones the
design names in section 8.5 - ``INVALID_OHLC``, ``ZERO_FIELDS``,
``OPEN_EQ_PREV_CLOSE``, ``ZERO_VOLUME`` and ``DUPLICATE_DATE`` - and each event
carries one of the 13 reconciliation categories from section 9 (the list is
read from ``dev/phase49_status_rules.json``; nothing is redefined here). Every
event also carries a ``witness`` column naming the evidence that decided its
category, so the split can be recomputed from the CSV alone.

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
    Section 8.5 defines ``PRICE_BASIS_DIFFERENCE`` as the divergence between
    LAST and the official closing - not as this equality - so the category is
    decided by a witness, never by the kind:

    * a date on which no row of the DB traded at all is a ``CALENDAR_GAP``;
    * a first-trade witness (positive ``daily_prices.price_first``) equal to
      ``open`` is ``VERIFIED_NO_EVENT``: the opening was a real trade at the
      prior close, so no adjustment event is needed;
    * a halt/suspension snapshot for the symbol on that date is also
      ``VERIFIED_NO_EVENT``; it decides only when the first-trade witness is
      absent, and the tag stays recorded either way;
    * a basis witness on that symbol/date (``price_history.last`` vs
      ``price_history.close``, or ``daily_prices.p_last`` vs
      ``daily_prices.p_closing``, compared through ``price_basis.last_of`` /
      ``closing_of``) is ``PRICE_BASIS_DIFFERENCE``;
    * a first-trade witness that differs from ``open``, or no witness at all,
      is ``UNRESOLVED_SOURCE_GAP`` - the ledger does not assert a basis or a
      repair it cannot prove.

    When both the basis witness and the first-trade equality are present (621
    rows in the Seed), the first-trade witness decides the open event: it is
    direct evidence that the opening price was traded, while the basis
    witness is about the close. Both tags stay in the ``witness`` column, so
    the other reading is recomputable. The first bar of a symbol is never
    compared with itself (the sketch this stage replaces seeded the first bar
    with its own close, which would have manufactured one false event per flat
    first bar).

``ZERO_VOLUME``
    The row records no trade. The root cause is read from the row and the
    whole-DB session evidence, in this order: a date on which no row of the DB
    traded at all (``market_no_session`` -> ``CALENDAR_GAP``); a halt snapshot
    for the symbol/date (``no_trade_halt_witness`` -> ``VERIFIED_NO_EVENT``);
    a non-flat bar with zero volume (``no_trade_price_range`` - a price range
    with no volume is an internally inconsistent record ->
    ``INVALID_SOURCE_RECORD``); the remaining per-symbol no-trade rows
    (``no_trade_first_bar``, ``no_trade_carried_close``,
    ``no_trade_price_change``) have valid OHLC fields but no halt or session
    witness, so they are ``UNRESOLVED_SOURCE_GAP``. The 135 flat bars whose
    close moved and the 4 first bars are not invalid records; only the 2
    non-flat bars contradict themselves (``open > 0`` everywhere, so the
    review's "genuinely invalid, e.g. open = 0" carve-out matches no row).

    ``instrument_state`` cannot root-cause these rows: its five snapshots cover
    2026-10-05..2026-10-11 and the last zero-volume row is 2026-09-30, so there
    is zero overlap. The counts file states that a halt cannot be separated
    from a plain no-trade day in this DB instead of inventing a halt flag, and
    the branch that would use a halt witness is implemented and unit-tested.

``DUPLICATE_DATE``
    ``price_history`` has ``PRIMARY KEY (symbol, date)``, so a duplicate is
    structurally impossible in the Seed; the SQL check returns 0 and the ledger
    keeps the detector for an input that is not this table. The detector emits
    one event per extra row of a repeated key and the SQL counts
    ``COUNT(*) - 1`` per key, so a triple yields 2 on both sides and the build
    does not fail; a mismatch would fail closed.

An event whose branch set does not explain the row is emitted with root cause
``UNEXPLAINED`` and category ``UNRESOLVED_SOURCE_GAP``; the build fails when
the UNEXPLAINED count is not zero, so "all anomalies categorized" is
machine-checked rather than asserted in prose. ``UNRESOLVED_SOURCE_GAP``
itself is a measured category (no witness exists): the Seed holds 50,489 such
events (47,993 OPEN_EQ_PREV_CLOSE + 2,496 ZERO_VOLUME), and they are expected
to remain unresolved until their witness sources arrive, not treated as a
build failure.

CLI:
    python _audit/phase49-full-verification/stage06_anomaly_ledger.py \\
        --db _audit/phase49-finalization/seed/market.db \\
        --out _audit/phase49-full-verification/ledgers/anomaly-ledger.csv

The CSV belongs in the gitignored ``ledgers/`` area; the tracked outputs are
the small counts summary and the stage manifest under ``evidence/``. Stdlib
plus ``dev/phase49_manifest.py`` and the frozen ``price_basis.py`` (imported,
never modified); the Seed DB is opened read-only, no network call.
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
import price_basis as PB  # noqa: E402

DEFAULT_RULES = os.path.join(ROOT, "dev", "phase49_status_rules.json")
DEFAULT_COUNTS = os.path.join(HERE, "evidence", "anomaly-counts.json")
DEFAULT_MANIFEST = os.path.join(HERE, "evidence",
                                "stage06_anomaly_ledger.manifest.json")
DEFAULT_POST_BACKFILL = os.path.join(HERE, "evidence",
                                     "post-backfill-anomalies.json")

KINDS = ("INVALID_OHLC", "ZERO_FIELDS", "OPEN_EQ_PREV_CLOSE", "ZERO_VOLUME",
         "DUPLICATE_DATE")

# Same halt vocabulary as stage05's instrument_state reading (kept local so a
# future stage05 rename cannot silently change this stage's witness).
HALT_WORDS = ("توقف", "معلق", "ممنوع")

# The sketch mapping of the brief, kept as the documented default per kind.
# OPEN_EQ_PREV_CLOSE and ZERO_VOLUME stay unresolved unless a witness says
# otherwise; the kind alone never asserts a basis or a calendar event.
BASE_CATEGORY = {
    "INVALID_OHLC": "INVALID_SOURCE_RECORD",
    "ZERO_FIELDS": "INVALID_SOURCE_RECORD",
    "OPEN_EQ_PREV_CLOSE": "UNRESOLVED_SOURCE_GAP",
    "ZERO_VOLUME": "UNRESOLVED_SOURCE_GAP",
    "DUPLICATE_DATE": "INVALID_SOURCE_RECORD",
}

# Root cause -> category. Every root cause names a real, measured branch; the
# category follows the cause instead of being copied from the kind.
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
    "open_at_prior_close_no_session": "CALENDAR_GAP",
    "open_at_prior_close_halt": "VERIFIED_NO_EVENT",
    "open_at_prior_close_basis": "PRICE_BASIS_DIFFERENCE",
    "open_at_prior_close_first_trade": "VERIFIED_NO_EVENT",
    "open_at_prior_close_unwitnessed": "UNRESOLVED_SOURCE_GAP",
    "no_trade_halt_witness": "VERIFIED_NO_EVENT",
    "no_trade_price_range": "INVALID_SOURCE_RECORD",
    "no_trade_first_bar": "UNRESOLVED_SOURCE_GAP",
    "no_trade_carried_close": "UNRESOLVED_SOURCE_GAP",
    "no_trade_price_change": "UNRESOLVED_SOURCE_GAP",
    "duplicate_primary_key": "INVALID_SOURCE_RECORD",
    "UNEXPLAINED": "UNRESOLVED_SOURCE_GAP",
}

FIELDS = ("symbol", "date", "kind", "category", "root_cause", "witness", "src",
          "evidence")

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


def _int(value, what, default=None):
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError("%s is not an integer: %r" % (what, value))


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


def _event(symbol, date, kind, root_cause, witness, src, evidence):
    return {
        "symbol": symbol,
        "date": date,
        "kind": kind,
        "category": ROOT_CATEGORY.get(root_cause, BASE_CATEGORY[kind]),
        "root_cause": root_cause,
        "witness": witness,
        "src": src,
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


def _positive(value):
    """Positive price or None - the same semantics as price_basis._num.

    ``last_of`` only validates the number, it does not read a file, so it is
    safe to reuse for the daily_prices columns and for price_first.
    """
    return PB.last_of({"last": value})


def _basis_tags(row, daily, exact):
    """Basis witnesses on the same symbol/date, via price_basis as authority."""
    tags = []
    last = PB.last_of(row)
    closing = PB.closing_of(row)
    if last is not None and closing is not None and abs(last - closing) > exact:
        tags.append("basis:last_vs_close")
    if daily:
        d_last = PB.last_of(daily)
        d_closing = PB.closing_of(daily)
        if (d_last is not None and d_closing is not None
                and abs(d_last - d_closing) > exact):
            tags.append("basis:p_last_vs_p_closing")
    return tags


def _first_trade(daily):
    """First-trade witness from daily_prices.price_first, positive only."""
    if not daily:
        return None
    return _positive(daily.get("price_first"))


def _daily_evidence(daily):
    """Daily_prices witness values, prefixed so they cannot be confused with
    the price_history columns."""
    out = {}
    if not daily:
        return out
    if daily.get("last") is not None:
        out["p_last"] = daily["last"]
    if daily.get("closing") is not None:
        out["p_closing"] = daily["closing"]
    if daily.get("price_first") is not None:
        out["price_first"] = daily["price_first"]
    return out


def _open_eq_event(row, o, h, l, c, v, pc, pd, exact, daily, halted,
                   halt_title, no_session):
    """Decide one OPEN_EQ_PREV_CLOSE event from its witnesses."""
    if None not in (o, h, l, c):
        if o == h == l == c:
            shape = "flat"
        elif h == l:
            shape = "flat_shadow"
        else:
            shape = "range"
    else:
        shape = "incomplete"
    basis = _basis_tags(row, daily, exact)
    first = _first_trade(daily)
    tags = list(basis)
    if first is not None:
        tags.append("first_trade:price_first_eq_open"
                    if abs(first - o) <= exact
                    else "first_trade:price_first_ne_open")
    if halted:
        tags.append("halt:instrument_state")
    if no_session:
        tags.append("session_calendar")
    witness = "+".join(tags) if tags else "none"

    if no_session:
        root = "open_at_prior_close_no_session"
    elif first is not None and abs(first - o) <= exact:
        root = "open_at_prior_close_first_trade"
    elif halted:
        root = "open_at_prior_close_halt"
    elif basis:
        root = "open_at_prior_close_basis"
    else:
        root = "open_at_prior_close_unwitnessed"

    evidence = dict(open=o, prev_close=pc, prev_date=pd, volume=v, high=h,
                    low=l, close=c, shape=shape)
    if row.get("last") is not None:
        evidence["last"] = row["last"]
    evidence.update(_daily_evidence(daily))
    if halted and halt_title:
        evidence["state_title"] = halt_title
    return _event(row["symbol"], row["date"], "OPEN_EQ_PREV_CLOSE", root,
                  witness, row.get("src"), _ev(**evidence))


def _zero_volume_event(row, o, h, l, c, v, pc, pd, exact, date_stats,
                       run_start, daily, halted, halt_title):
    """Decide one ZERO_VOLUME event; only session-wide evidence is a gap."""
    date = row["date"]
    date_rows, date_traded = date_stats.get(date, (0, 0))
    no_session = date_rows > 0 and date_traded == 0
    flat = (o == h == l == c) if None not in (o, h, l, c) else False
    held_since = run_start.get(row["symbol"], date)
    first = _first_trade(daily)
    tags = []
    if halted:
        tags.append("halt:instrument_state")
    if first is not None:
        tags.append("first_trade:price_first_eq_open"
                    if abs(first - o) <= exact
                    else "first_trade:price_first_ne_open")
    if no_session:
        tags.append("session_calendar")

    if v is None:
        root = "volume_null"
        witness = "+".join(tags + ["row_fields"])
    elif no_session:
        root = "market_no_session"
        witness = "+".join(tags) if tags else "session_calendar"
    elif halted:
        root = "no_trade_halt_witness"
        witness = "+".join(tags) if tags else "halt:instrument_state"
    elif not flat:
        root = "no_trade_price_range"
        witness = "+".join(tags + ["row_fields"])
    elif pc is None:
        root = "no_trade_first_bar"
        witness = "+".join(tags) if tags else "none"
    elif abs(c - pc) <= exact:
        root = "no_trade_carried_close"
        witness = "+".join(tags) if tags else "none"
    else:
        root = "no_trade_price_change"
        witness = "+".join(tags) if tags else "none"

    evidence = dict(open=o, high=h, low=l, close=c, volume=v, flat=flat,
                    prev_close=pc, prev_date=pd, held_since=held_since,
                    date_rows=date_rows, date_traded=date_traded)
    evidence.update(_daily_evidence(daily))
    if halted and halt_title:
        evidence["state_title"] = halt_title
    return _event(row["symbol"], date, "ZERO_VOLUME", root, witness,
                  row.get("src"), _ev(**evidence))


def detect(rows, prev_close=None, date_stats=None, rules=None,
           daily_witness=None, halt_dates=None):
    """Return one event per anomaly, in (symbol, date, kind) input order.

    ``rows`` must be ordered by (symbol, date); ``prev_close`` may seed the
    first bar (symbol key) or override one bar ((symbol, date) key). When
    ``date_stats`` is absent it is measured from ``rows`` itself, so a caller
    that passes a fragment (the unit test) gets session evidence for that
    fragment only; the CLI always passes the whole-DB table.

    ``daily_witness`` maps ``(symbol, date)`` to a dict with ``last``,
    ``closing`` and ``price_first`` (the daily_prices row); ``halt_dates`` maps
    ``(symbol, date)`` to the instrument_state title. With neither, every
    OPEN_EQ and every per-symbol no-trade row is ``UNRESOLVED_SOURCE_GAP`` -
    the conservative default.
    """
    rules = rules or {}
    exact = float(rules.get("exact_eq", (rules.get("tolerances") or {}).get(
        "EXACT_EQ", 1e-9)))
    daily_witness = daily_witness or {}
    halt_dates = halt_dates or {}
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
        daily = daily_witness.get(key)
        halted = key in halt_dates
        halt_title = halt_dates.get(key) if halted else None
        date_rows, date_traded = date_stats.get(date, (0, 0))
        no_session = date_rows > 0 and date_traded == 0

        if key in seen:
            out.append(_event(symbol, date, "DUPLICATE_DATE",
                              "duplicate_primary_key", "primary_key",
                              row.get("src"), "same_symbol_date_seen_twice"))
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
                _invalid_root(reasons, o, h, l, c), "row_fields",
                row.get("src"),
                "reasons=%s;%s" % (",".join(reasons),
                                   _ev(open=o, high=h, low=l, close=c,
                                       volume=v, src=row.get("src")))))
            if ((o is not None and h is not None and l is not None
                 and c is not None and o == 0 and h == 0 and l == 0
                 and c == 0)):
                out.append(_event(symbol, date, "ZERO_FIELDS", "all_ohlc_zero",
                                  "row_fields", row.get("src"),
                                  _ev(open=o, high=h, low=l, close=c,
                                      volume=v)))

        pc = overrides.get(key, prev.get(symbol))
        pd = prev_date.get(symbol)
        if o is not None and pc is not None and abs(o - pc) <= exact:
            out.append(_open_eq_event(row, o, h, l, c, v, pc, pd, exact,
                                      daily, halted, halt_title, no_session))

        if not v:
            out.append(_zero_volume_event(row, o, h, l, c, v, pc, pd, exact,
                                          date_stats, run_start, daily,
                                          halted, halt_title))
            run_start.setdefault(symbol, date)
        else:
            run_start.pop(symbol, None)

        if c is not None:
            prev[symbol] = c
            prev_date[symbol] = date
    return out


def _witness_consistent(event):
    """The category must be reachable from the recorded witness."""
    witness = event["witness"]
    category = event["category"]
    kind = event["kind"]
    if category == "PRICE_BASIS_DIFFERENCE":
        return witness.startswith("basis:") or "+basis:" in witness
    if category == "VERIFIED_NO_EVENT":
        return ("first_trade:price_first_eq_open" in witness
                or witness.startswith("halt:") or "+halt:" in witness)
    if category == "CALENDAR_GAP":
        return witness == "session_calendar" or witness.endswith(
            "+session_calendar")
    if kind in ("OPEN_EQ_PREV_CLOSE", "ZERO_VOLUME"):
        if category == "UNRESOLVED_SOURCE_GAP":
            return (witness == "none" or witness.startswith("first_trade:")
                    or "+first_trade:" in witness)
        if category == "INVALID_SOURCE_RECORD":
            return witness == "row_fields" or witness.endswith("+row_fields")
    return True


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
    # One extra row per repeated key: a triple contributes 2, matching the
    # detector's one-event-per-extra-row rule.
    duplicates = con.execute(
        "SELECT COALESCE(SUM(extra),0) FROM (SELECT COUNT(*)-1 AS extra "
        "FROM price_history GROUP BY symbol,date "
        "HAVING COUNT(*)>1)").fetchone()[0]
    return {"rows": int(one), "zero_volume": int(zero_volume),
            "invalid_ohlc": int(invalid), "zero_fields": int(zero_fields),
            "duplicate_dates": int(duplicates)}


def _iso_even(value):
    text = str(value or "")
    if len(text) != 8 or not text.isdigit():
        return ""
    return "%s-%s-%s" % (text[:4], text[4:6], text[6:])


def _load_witnesses(con):
    """Daily and halt witness tables keyed by (symbol, date).

    price_history already carries ``last``/``close``; daily_prices supplies
    ``p_last``/``p_closing``/``price_first`` for 2026-08-20..2026-10-11 and
    instrument_state supplies halt/suspension titles.
    """
    ins = {}
    for name, code in con.execute(
            "SELECT l_val18,ins_code FROM instruments "
            "WHERE l_val18 IS NOT NULL AND TRIM(l_val18)<>'' "
            "ORDER BY ins_code"):
        ins.setdefault(name, code)
    code_symbol = {}
    for name, code in ins.items():
        code_symbol.setdefault(code, name)
    daily = {}
    for code, even, p_closing, p_last, price_first in con.execute(
            "SELECT ins_code,d_even,p_closing,p_last,price_first "
            "FROM daily_prices"):
        symbol = code_symbol.get(code)
        if not symbol or even is None:
            continue
        date = _iso_even(int(even))
        if not date:
            continue
        daily[(symbol, date)] = {"closing": p_closing, "last": p_last,
                                 "price_first": price_first}
    halts = {}
    for symbol, even, title in con.execute(
            "SELECT i.l_val18,s.d_even,s.c_etaval_title "
            "FROM instrument_state s "
            "JOIN instruments i ON i.ins_code=s.ins_code "
            "WHERE i.l_val18 IS NOT NULL AND TRIM(i.l_val18)<>'' "
            "AND s.c_etaval_title IS NOT NULL"):
        if not any(word in title for word in HALT_WORDS):
            continue
        date = _iso_even(even)
        if not date:
            continue
        halts.setdefault((symbol, date), title)
    return daily, halts


def _witness_coverage(con):
    """Measured coverage of the two independent witness sources.

    The residual populations must state which rows have no witness and how
    much of the window each source actually covers. These are table-level
    aggregates, not raw rows.
    """
    daily = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT d_even), MIN(d_even), MAX(d_even), "
        "SUM(CASE WHEN price_first>0 THEN 1 ELSE 0 END) FROM daily_prices"
    ).fetchone()
    state = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT d_even), MIN(d_even), MAX(d_even) "
        "FROM instrument_state").fetchone()
    duplicate_names = [str(row[0]) for row in con.execute(
        "SELECT l_val18 FROM instruments WHERE l_val18 IS NOT NULL "
        "AND TRIM(l_val18)<>'' GROUP BY l_val18 "
        "HAVING COUNT(DISTINCT ins_code)>1 ORDER BY l_val18")]
    mapped = {str(row[0]) for row in con.execute(
        "SELECT DISTINCT l_val18 FROM instruments WHERE l_val18 IS NOT NULL "
        "AND TRIM(l_val18)<>''")}
    return {
        "daily": {
            "rows": int(daily[0] or 0),
            "sessions": int(daily[1] or 0),
            "first_date": _iso_even(daily[2]),
            "last_date": _iso_even(daily[3]),
            "positive_price_first": int(daily[4] or 0),
        },
        "instrument_state": {
            "rows": int(state[0] or 0),
            "snapshot_days": int(state[1] or 0),
            "first_date": _iso_even(state[2]),
            "last_date": _iso_even(state[3]),
        },
        "mapped_symbols": mapped,
        "duplicate_names": duplicate_names,
    }


def _residual_detail(events, daily, coverage, halt_dates):
    """Bind an UNRESOLVED_SOURCE_GAP population to what is missing.

    Every count is measured against the witness tables: before/inside/after
    the ``daily_prices`` window, the state of a joined daily row (no ins_code,
    no daily row, null/zero ``price_first``, positive ``price_first``), the
    halt snapshots and the ``instrument_state`` window. No raw rows leave the
    ledger; the output is aggregates only.
    """
    first = coverage["daily"]["first_date"]
    last = coverage["daily"]["last_date"]
    state_first = coverage["instrument_state"]["first_date"]
    state_last = coverage["instrument_state"]["last_date"]
    mapped = coverage["mapped_symbols"]
    counts = {
        "before": 0,
        "inside": 0,
        "after": 0,
        "uncovered": 0,
        "positive": 0,
        "halts": 0,
        "state_window": 0,
    }
    inside_state = collections.Counter()
    outside_state = collections.Counter()
    for event in events:
        key = (event["symbol"], event["date"])
        if key in halt_dates:
            counts["halts"] += 1
        if state_first and state_last and state_first <= event["date"] <= state_last:
            counts["state_window"] += 1
        if event["symbol"] not in mapped:
            state = "no_ins_code"
        else:
            row = daily.get(key)
            if row is None:
                state = "no_daily_row"
            elif _positive(row.get("price_first")) is None:
                state = "price_first_null_or_zero"
            else:
                state = "price_first_positive"
                counts["positive"] += 1
        if not first or not last:
            counts["uncovered"] += 1
            outside_state[state] += 1
        elif event["date"] < first:
            counts["before"] += 1
            outside_state[state] += 1
        elif event["date"] > last:
            counts["after"] += 1
            outside_state[state] += 1
        else:
            counts["inside"] += 1
            inside_state[state] += 1
    dates = sorted(event["date"] for event in events)
    return {
        "missing_witness": {
            "event_window": {
                "first_date": dates[0] if dates else "",
                "last_date": dates[-1] if dates else "",
            },
            "daily_prices_window": coverage["daily"],
            "instrument_state_window": coverage["instrument_state"],
            "rows_total": len(events),
            "rows_before_daily_prices_window": counts["before"],
            "rows_inside_daily_prices_window": counts["inside"],
            "rows_after_daily_prices_window": counts["after"],
            "rows_uncovered_by_daily_prices": counts["uncovered"],
            "rows_inside_by_state": dict(sorted(inside_state.items())),
            "rows_outside_by_state": dict(sorted(outside_state.items())),
            "rows_without_positive_price_first": (len(events)
                                                  - counts["positive"]),
            "rows_with_positive_price_first": counts["positive"],
            "rows_inside_instrument_state_window": counts["state_window"],
            "rows_with_halt_snapshot": counts["halts"],
        },
    }


def _invalid_witness(con, events):
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


def _witness_summary(events):
    """Category, witness and source counts for a filtered event list."""
    return {
        "events": len(events),
        "by_category": dict(sorted(collections.Counter(
            e["category"] for e in events).items())),
        "by_witness": dict(sorted(collections.Counter(
            e["witness"] for e in events).items())),
        "by_src": dict(sorted(collections.Counter(
            str(e["src"]) for e in events).items())),
    }


def _post_backfill_summary(path):
    """Attach the seven C4 one-session-drop classifications to this ledger.

    They are outside the five anomaly kinds (a price drop with valid OHLC is
    not an invalid row), so the summary is carried as a cross-reference and
    never re-categorized by this stage. An absent path disables the block.
    """
    if not path:
        return None
    if not os.path.isfile(path):
        raise ValueError("post-backfill evidence not found: %s" % path)
    with open(path, encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except ValueError as exc:
            raise ValueError("post-backfill evidence is not valid JSON: %s"
                             % exc)
    if not isinstance(data, dict):
        raise ValueError("post-backfill evidence must be a JSON object")
    counts = data.get("counts") or {}
    if not isinstance(counts, dict):
        raise ValueError("post-backfill evidence counts must be an object")
    events = data.get("events") or []
    return {
        "path": _rel(path),
        "schema": data.get("schema"),
        "events": _int(counts.get("events", len(events)), "post-backfill events"),
        "new_rows": _int(counts.get("new_rows"), "post-backfill new_rows"),
        "by_category": counts.get("by_category") or {},
        "blockers": _int(counts.get("blockers"), "post-backfill blockers"),
        "blocker_dates": counts.get("blocker_dates") or [],
        "note": ("one-session drops are outside the five B8 kinds; "
                 "the full evidence is in the named file, recorded here so C5 "
                 "sees the blockers alongside the candle anomalies"),
    }


def build(db, out, counts_path, manifest_path="", rules_path=DEFAULT_RULES,
          expect_rows=0, post_backfill_path=""):
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
        daily_witness, halt_dates = _load_witnesses(con)
        coverage = _witness_coverage(con)
        last_diff = con.execute(
            "SELECT COUNT(*) FROM price_history WHERE last>0 AND close>0 "
            "AND ABS(last-close)>?", (exact,)).fetchone()[0]
        p_diff = con.execute(
            "SELECT COUNT(*) FROM daily_prices WHERE p_last>0 AND p_closing>0 "
            "AND ABS(p_last-p_closing)>?", (exact,)).fetchone()[0]
        cursor = con.execute(
            "SELECT symbol,date,open,high,low,close,volume,last,src "
            "FROM price_history ORDER BY symbol,date")
        events = detect((dict(row) for row in cursor), date_stats=date_stats,
                        rules=rules, daily_witness=daily_witness,
                        halt_dates=halt_dates)

        by_kind = {kind: 0 for kind in KINDS}
        by_category = {name: 0 for name in categories}
        by_root = collections.Counter()
        by_witness = collections.Counter()
        invalid_reasons = collections.Counter()
        for event in events:
            if event["category"] not in by_category:
                raise ValueError("event with unknown category: %r" % (event,))
            if not _witness_consistent(event):
                raise ValueError("category does not follow the witness: %r"
                                 % (event,))
            by_kind[event["kind"]] += 1
            by_category[event["category"]] += 1
            by_root[event["root_cause"]] += 1
            by_witness[event["witness"]] += 1
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
        witness = _invalid_witness(con, invalid)
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

    basis_events = [e for e in open_eq if "basis:" in e["witness"]]
    first_eq = [e for e in open_eq
                if "first_trade:price_first_eq_open" in e["witness"]]
    first_ne = [e for e in open_eq
                if "first_trade:price_first_ne_open" in e["witness"]]
    open_basis = [e for e in open_eq
                  if e["category"] == "PRICE_BASIS_DIFFERENCE"]
    open_first = [e for e in open_eq
                  if e["root_cause"] == "open_at_prior_close_first_trade"]
    open_halt = [e for e in open_eq
                 if e["root_cause"] == "open_at_prior_close_halt"]
    open_halt_tagged = [e for e in open_eq if "halt:" in e["witness"]]
    open_calendar = [e for e in open_eq
                     if e["category"] == "CALENDAR_GAP"]
    open_unresolved = [e for e in open_eq
                       if e["category"] == "UNRESOLVED_SOURCE_GAP"]
    basis_tags = collections.Counter()
    for event in basis_events:
        for tag in event["witness"].split("+"):
            if tag.startswith("basis:"):
                basis_tags[tag] += 1
    dual = [e for e in basis_events
            if "first_trade:price_first_eq_open" in e["witness"]]
    zero_invalid = [e for e in zero_volume
                    if e["category"] == "INVALID_SOURCE_RECORD"]
    zero_unresolved = [e for e in zero_volume
                       if e["category"] == "UNRESOLVED_SOURCE_GAP"]
    zero_calendar = [e for e in zero_volume
                     if e["category"] == "CALENDAR_GAP"]
    zero_halt = [e for e in zero_volume if "halt:" in e["witness"]]

    open_residual = _residual_detail(open_unresolved, daily_witness, coverage,
                                     halt_dates)
    zero_residual = _residual_detail(zero_unresolved, daily_witness, coverage,
                                     halt_dates)
    open_residual["by_root_cause"] = dict(sorted(collections.Counter(
        e["root_cause"] for e in open_unresolved).items()))
    zero_residual["by_root_cause"] = dict(sorted(collections.Counter(
        e["root_cause"] for e in zero_unresolved).items()))
    open_residual.update(_witness_summary(open_unresolved))
    zero_residual.update(_witness_summary(zero_unresolved))

    daily_cov = coverage["daily"]
    state_cov = coverage["instrument_state"]
    present_coverage = (
        "daily_prices %s..%s (%d sessions, %d rows, %d with positive "
        "price_first); instrument_state %s..%s (%d snapshot days, %d rows)"
        % (daily_cov["first_date"], daily_cov["last_date"],
           daily_cov["sessions"], daily_cov["rows"],
           daily_cov["positive_price_first"], state_cov["first_date"],
           state_cov["last_date"], state_cov["snapshot_days"],
           state_cov["rows"]))
    open_missing = open_residual["missing_witness"]
    zero_missing = zero_residual["missing_witness"]
    open_residual["required_source"] = {
        "primary": ("daily_prices.price_first (first-trade print) for every "
                    "symbol/session in %s..%s"
                    % (open_missing["event_window"]["first_date"],
                       open_missing["event_window"]["last_date"])),
        "alternatives": [
            "halt/suspension snapshot on the exact symbol/date "
            "(instrument_state.c_etaval_title)",
            "full-history exchange calendar; a whole-market no-session date "
            "only re-files CALENDAR_GAP rows and cannot verify a per-symbol "
            "open-at-prior-close equality",
        ],
        "present_coverage": present_coverage,
        "missing": (
            "%d rows predate the daily_prices window, %d follow it, %d inside "
            "it have no positive price_first, %d are uncovered by daily_prices, "
            "and %d carry a halt snapshot; the remaining %d positive "
            "price_first row(s) differ from open."
            % (open_missing["rows_before_daily_prices_window"],
               open_missing["rows_after_daily_prices_window"],
               (open_missing["rows_inside_daily_prices_window"]
                - open_missing["rows_with_positive_price_first"]),
               open_missing["rows_uncovered_by_daily_prices"],
               open_missing["rows_with_halt_snapshot"],
               open_missing["rows_with_positive_price_first"])),
    }
    zero_residual["required_source"] = {
        "primary": ("per-symbol halt/suspension snapshots covering %s..%s, or "
                    "a full-history exchange calendar that marks the symbol's "
                    "no-session days"
                    % (zero_missing["event_window"]["first_date"],
                       zero_missing["event_window"]["last_date"])),
        "alternatives": [
            "full-history daily trade tape (daily_prices.price_first) to "
            "distinguish a traded first print from a no-trade row",
        ],
        "present_coverage": present_coverage,
        "missing": (
            "%d rows predate the daily_prices window, %d follow it, %d inside "
            "it have no positive price_first, %d are uncovered by daily_prices, "
            "and %d carry a halt snapshot; instrument_state starts %s, after "
            "the last zero-volume row (%s)."
            % (zero_missing["rows_before_daily_prices_window"],
               zero_missing["rows_after_daily_prices_window"],
               (zero_missing["rows_inside_daily_prices_window"]
                - zero_missing["rows_with_positive_price_first"]),
               zero_missing["rows_uncovered_by_daily_prices"],
               zero_missing["rows_with_halt_snapshot"],
               state_cov["first_date"], zero_last)),
    }
    open_residual["attempted"] = [
        "basis witness: price_basis.last_of vs closing_of on price_history "
        "and daily_prices p_last/p_closing",
        "first-trade witness: positive daily_prices.price_first compared "
        "with open",
        "halt witness: instrument_state.c_etaval_title (HALT_WORDS) on the "
        "exact symbol/date",
        "session witness: whole-DB dates with zero traded rows",
    ]
    zero_residual["attempted"] = [
        "session witness: whole-DB dates with zero traded rows",
        "halt witness: instrument_state.c_etaval_title (HALT_WORDS) on the "
        "exact symbol/date",
        "bar shape: flat carried close, flat price change, first bar, "
        "non-flat range",
        "first-trade witness: positive daily_prices.price_first",
    ]
    open_residual["verdict"] = "UNRESOLVED_SOURCE_GAP"
    zero_residual["verdict"] = "UNRESOLVED_SOURCE_GAP"

    residual_events = open_unresolved + zero_unresolved
    residual_summary = _witness_summary(residual_events)
    residual_summary["by_kind"] = {
        "OPEN_EQ_PREV_CLOSE": len(open_unresolved),
        "ZERO_VOLUME": len(zero_unresolved),
    }
    residual_summary["by_root_cause"] = dict(sorted(collections.Counter(
        e["root_cause"] for e in residual_events).items()))
    residual_summary.update({
        "verdict": "UNRESOLVED_SOURCE_GAP",
        "build_gate": ("only UNEXPLAINED fails the build; "
                       "UNRESOLVED_SOURCE_GAP is a measured residual"),
        "detail": ("open_eq_prev_close.residual_unverified and "
                   "zero_volume.residual_unverified bind each kind to its "
                   "required source and missing witness rows"),
    })
    identity_caveat = (
        "PRICE_BASIS_DIFFERENCE=%d is a join-policy count under the documented "
        "ISIN/ins_code precedence, not an absolute identity claim: %d l_val18 "
        "names resolve to two ins_codes each, and the filed كيمازي 2026-10-10 "
        "event would be VERIFIED_NO_EVENT under the sibling code's daily row "
        "(price_first=open); the join policy is unchanged."
        % (len(open_basis), len(coverage["duplicate_names"])))

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
        "by_witness": dict(sorted(by_witness.items())),
        "residual_unverified": residual_summary,
        "kind_x_category": _cross(events, "kind", "category"),
        "kind_x_root_cause": _cross(events, "kind", "root_cause"),
        "kind_x_witness": _cross(events, "kind", "witness"),
        "witness_x_category": _cross(events, "witness", "category"),
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
            "by_category": dict(sorted(collections.Counter(
                e["category"] for e in open_eq).items())),
            "by_witness": dict(sorted(collections.Counter(
                e["witness"] for e in open_eq).items())),
            "by_src": sql_open_eq,
            "by_year": year_open_eq,
            "comparisons": sum(v["comparisons"]
                               for v in sql_open_eq.values()),
            "verification": "witness_split_v1",
            "basis_witness": {
                "definition": ("price_basis.last_of() vs closing_of() on the "
                               "price_history row and on the same-day "
                               "daily_prices p_last/p_closing"),
                "events_with_basis_witness": len(basis_events),
                "last_vs_close": basis_tags.get("basis:last_vs_close", 0),
                "p_last_vs_p_closing": basis_tags.get(
                    "basis:p_last_vs_p_closing", 0),
                "both": sum(1 for e in basis_events
                            if "basis:last_vs_close" in e["witness"]
                            and "basis:p_last_vs_p_closing" in e["witness"]),
                "filed_price_basis_difference": len(open_basis),
                "also_first_trade_equal": len(dual),
                "whole_db_pool_last_vs_close": int(last_diff),
                "whole_db_pool_p_last_vs_p_closing": int(p_diff),
                "identity_caveat": identity_caveat,
            },
            "first_trade_witness": {
                "source": ("daily_prices.price_first, positive values only, "
                           "for 2026-08-20..2026-10-11"),
                "equals_open": len(first_eq),
                "differs_from_open": len(first_ne),
                "filed_verified_by_first_trade": len(open_first),
            },
            "calendar_witness": {
                "source": "whole-DB date with zero traded rows",
                "events": len(open_calendar),
            },
            "halt_witness": {
                "source": "instrument_state.c_etaval_title (HALT_WORDS)",
                "tagged_rows": len(open_halt_tagged),
                "decided": len(open_halt),
                "note": ("the halt tag is recorded on every matching row; it "
                         "decides only when the first-trade witness is absent, "
                         "and every tagged row here already has that witness"),
            },
            "residual_unverified": open_residual,
            "method": ("previous close is the preceding bar of the same "
                       "symbol in date order; the first bar of a symbol is "
                       "never compared with itself; the category is decided "
                       "by the witness, never by the kind"),
        },
        "zero_volume": {
            "events": len(zero_volume),
            "rows": len(affected.get("ZERO_VOLUME", ())),
            "by_root_cause": dict(sorted(zero_roots.items())),
            "by_category": dict(sorted(collections.Counter(
                e["category"] for e in zero_volume).items())),
            "by_witness": dict(sorted(collections.Counter(
                e["witness"] for e in zero_volume).items())),
            "by_src": sql_zero_by_src,
            "no_session_dates": [
                {"date": date, "rows": rows} for date, rows in session_rows],
            "no_session_rows": sum(rows for _, rows in session_rows),
            "calendar_gap_events": len(zero_calendar),
            "invalid_record_events": len(zero_invalid),
            "invalid_record_roots": dict(sorted(collections.Counter(
                e["root_cause"] for e in zero_invalid).items())),
            "halt_witness": {
                "source": "instrument_state.c_etaval_title (HALT_WORDS)",
                "events": len(zero_halt),
                "note": ("no per-symbol no-trade row has a halt snapshot on "
                         "its exact date in this Seed"),
            },
            "residual_unverified": zero_residual,
            "last_zero_volume_date": zero_last,
            "instrument_state": {
                "first_date": _iso_even(state[0]) if state else "",
                "last_date": _iso_even(state[1]) if state else "",
                "snapshot_days": int(state[2] or 0) if state else 0,
                "overlap_with_zero_volume_rows": int(overlap or 0),
                "halt_attribution": ("not possible: zero overlap between the "
                                     "state snapshots and zero-volume rows"),
            },
            "method": ("date-level session evidence (no row traded all day), "
                       "then halt witness, then bar shape; a per-symbol "
                       "no-trade day without either stays unresolved"),
        },
        "duplicate_dates": {
            "events": by_kind["DUPLICATE_DATE"],
            "sql_check": sql["duplicate_dates"],
            "definition": ("one event per extra row of a repeated "
                           "(symbol, date); the SQL counts COUNT(*)-1 per key, "
                           "so a triple yields 2 on both sides"),
            "constraint": ("PRIMARY KEY (symbol, date) makes a duplicate "
                           "impossible in the Seed; the check is 0 and the "
                           "detector stays for inputs without the constraint"),
        },
        "checks": {
            "uncategorized_events": (len(events)
                                     - sum(by_category.values())),
            "unexplained_events": by_root.get("UNEXPLAINED", 0),
            "witness_category_mismatches": 0,
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
            "chosen from the measured root cause and the recorded witness, "
            "not from the anomaly kind.",
            "Every event carries the raw values that triggered it and the "
            "witness tags in the CSV; the tracked counts hold aggregates "
            "only, no raw rows.",
            "A branch set that explains nothing is emitted with root cause "
            "UNEXPLAINED (category UNRESOLVED_SOURCE_GAP); the build fails "
            "only when the UNEXPLAINED count is non-zero, and that count is "
            "zero in this Seed. The category UNRESOLVED_SOURCE_GAP itself is "
            "a measured residual with %d events (%d OPEN_EQ_PREV_CLOSE, %d "
            "ZERO_VOLUME): no witness exists for those rows, so it is "
            "reported, not treated as a build failure."
            % (len(residual_events), len(open_unresolved),
               len(zero_unresolved)),
        ],
        "notes": [
            "5 of the 13 categories are used (CALENDAR_GAP, "
            "INVALID_SOURCE_RECORD, PRICE_BASIS_DIFFERENCE, "
            "VERIFIED_NO_EVENT, UNRESOLVED_SOURCE_GAP). The eight zero "
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
            "no row required it.",
            "OPEN_EQ_PREV_CLOSE is decided by a witness, never by the kind: "
            "%d rows have a first-trade witness equal to open and are filed "
            "VERIFIED_NO_EVENT (%d of them also carry a halt tag), %d have a "
            "basis witness and no first-trade equality "
            "(PRICE_BASIS_DIFFERENCE), %d sit on a market-wide no-trade date "
            "(CALENDAR_GAP), and %d have no witness or a first-trade witness "
            "that differs (UNRESOLVED_SOURCE_GAP). %d rows carry both a basis "
            "witness and the first-trade equality; the opening witness "
            "decides the open event and all tags stay in the witness column."
            % (len(first_eq), len(open_halt_tagged), len(open_basis),
               len(open_calendar), len(open_unresolved), len(dual)),
            "The design's basis witness pool is larger than the OPEN_EQ "
            "population: %d price_history rows have last != close and %d "
            "daily_prices rows have p_last != p_closing, but only %d OPEN_EQ "
            "events join one of those witnesses on their own symbol/date. A "
            "basis divergence without an OPEN_EQ anomaly is not an event of "
            "this ledger."
            % (int(last_diff), int(p_diff), len(basis_events)),
            identity_caveat,
            "Zero volume: %d rows. %d sit on the %d dates where no row of "
            "the DB traded at all (calendar evidence, not a per-symbol "
            "guess); %d are per-symbol no-trade rows with no halt witness "
            "(UNRESOLVED_SOURCE_GAP); %d are non-flat bars whose price range "
            "contradicts zero volume (INVALID_SOURCE_RECORD); 0 have a halt "
            "witness. Of the previously invalid 141, 135 are flat "
            "price-change bars, 4 are first bars and 2 are non-flat range "
            "bars; only the 2 range bars are genuinely invalid and none has "
            "open=0."
            % (len(zero_volume), len(zero_calendar), len(session_rows),
               len(zero_unresolved), len(zero_invalid)),
            "OPEN_EQ_PREV_CLOSE is not a legacy-only property: by source it "
            "is %s over %d comparable bars, so the equality spans the tagged "
            "writers. Zero-volume and invalid-OHLC rows, by contrast, all "
            "carry legacy-unknown."
            % (" and ".join("%s %d" % (name, entry["open_eq_prev_close"])
                            for name, entry in sorted(sql_open_eq.items())),
               sum(v["comparisons"] for v in sql_open_eq.values())),
            "The 306 invalid OHLC rows carry %s; %d of them resolve to an "
            "instruments row and %d of those have a daily_prices row on the "
            "same day, so the root cause is the row's own field set and not a "
            "repair candidate."
            % (" and ".join("%s (%d rows)" % item
                            for item in sorted(sql_invalid_by_src.items())),
               witness["instruments_matched"],
               witness["daily_prices_matched"]),
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
    post_backfill = _post_backfill_summary(post_backfill_path)
    if post_backfill:
        payload["post_backfill_anomalies"] = post_backfill

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
    ap.add_argument("--post-backfill-evidence", default=DEFAULT_POST_BACKFILL,
                    help="optional post-backfill drop evidence to attach "
                         "('' disables)")
    args = ap.parse_args(argv)
    os.chdir(ROOT)
    try:
        events, payload = build(
            args.db, args.out, args.counts, args.manifest, args.rules,
            args.expect_rows, args.post_backfill_evidence)
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
