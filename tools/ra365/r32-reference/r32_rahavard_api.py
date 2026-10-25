#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rahavard365 chart-API vocabulary, and the parsers for the two export shapes.

The endpoint/ticker vocabulary below is the one measured in Rounds 21/30/31 by
driving the logged-in Rahavard365 page; it is recorded here so the capture
driver and the importer cannot drift apart.  Nothing in this module reads or
stores a credential: capture runs inside the owner's own browser session and
the importer only ever sees an exported file.

Two export shapes are accepted
------------------------------
rahavard-json (what capture_rahavard.mjs writes):

    {
      "source": {"kind": "rahavard365-web-api", "endpoint": "...",
                 "captured_at": "...", "session": "owner-browser-cdp"},
      "series": [
        {"asset_id": 453, "symbol": "\u0641\u0648\u0644\u0627\u062f",
         "ticker": "exchange.asset:453:real_close:type0",
         "adjust": "raw", "resolution": "D", "basis": "real_close",
         "bars": [{"utc": "2024-12-31", "open": 1.0, "high": 2.0,
                   "low": 0.5, "close": 1.5, "volume": 100}, ...]}
      ]
    }

rahavard-csv (a manual export from any tool that can write these columns):

    date,symbol,open,high,low,close,volume,adjust,basis,timeframe[,symbol_id]

Anything absent is left absent: `volume` that the source did not send lands in
the bar's `unavailable` list rather than becoming a zero.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re

import r32_schema as S

BASE_URL = "https://rahavard365.com"
ENTITY_TYPE = "exchange.asset"

#: chart type suffix -> adjust mode.  type7 is Rahavard's performance-adjusted
#: ("\u0639\u0645\u0644\u06a9\u0631\u062f\u06cc") series; type0 is literal raw.
TYPE_TO_ADJUST = {
    "type0": "raw",
    "type1": "adjusted",
    "type2": "adjusted",
    "type3": "adjusted",
    "type4": "adjusted",
    "type5": "adjusted",
    "type6": "adjusted",
    "type7": "adjusted",
}
ADJUST_TO_TYPE = {"raw": "type0", "adjusted": "type7"}

TICKER_RE = re.compile(r"^exchange\.asset:(?P<id>[^:]+):(?P<basis>[^:]+):(?P<type>type\d+)$")


def ticker_for(asset_id, adjust="raw", basis="real_close"):
    """Build the Rahavard ticker string for one series."""
    suffix = ADJUST_TO_TYPE[S.normalize_adjust(adjust)]
    return "%s:%s:%s:%s" % (ENTITY_TYPE, asset_id, basis, suffix)


def parse_ticker(ticker):
    """('453', 'raw', 'real_close') or None when the string is not a ticker."""
    m = TICKER_RE.match(str(ticker or "").strip())
    if not m:
        return None
    return m.group("id"), TYPE_TO_ADJUST.get(m.group("type"), "raw"), m.group("basis")


def bars_url(ticker, resolution, countback, date_from=None, date_to=None):
    """The bars endpoint exactly as the product's own chart page calls it."""
    parts = ["countback=%d" % int(countback),
             "symbol=" + _q(ticker),
             "resolution=" + S.normalize_timeframe(resolution)]
    if date_from:
        parts.append("from=" + _q(date_from))
    if date_to:
        parts.append("to=" + _q(date_to))
    return "/api/v2/chart/bars?" + "&".join(parts)


def marks_url(ticker, resolution="D"):
    return ("/api/v2/chart/timescale_marks?ticker=" + _q(ticker)
            + "&resolution=" + S.normalize_timeframe(resolution))


def _q(value):
    from urllib.parse import quote
    return quote(str(value), safe="")


# --------------------------------------------------------------------------
# parsers
# --------------------------------------------------------------------------

def _bar_record(asset_id, symbol, adjust, resolution, basis, source_id,
                raw_bar, retrieved_at, unavailable_extra=()):
    date = S.normalize_date(raw_bar.get("utc") if isinstance(raw_bar, dict) else None)
    fields = {}
    unavailable = list(unavailable_extra)
    for key in ("open", "high", "low", "close", "volume"):
        value = S.normalize_number(raw_bar.get(key)) if isinstance(raw_bar, dict) else None
        fields[key] = value
        if value is None:
            unavailable.append(key)
    rec = {
        "schema": S.SCHEMA_BAR,
        "symbol_id": str(asset_id),
        "symbol": S.normalize_symbol(symbol),
        "ins_code": None,
        "timeframe": S.normalize_timeframe(resolution),
        "date": date,
        "adjust": S.normalize_adjust(adjust),
        "basis": S.normalize_basis(basis),
        "source_id": source_id,
        "retrieved_at": retrieved_at,
        "precision": None,
        "revision": None,
        "unavailable": sorted(set(unavailable)),
        **fields,
    }
    rec["row_hash"] = S.row_hash(rec)
    return rec


def parse_rahavard_json(path_or_obj):
    """Yield (source_record, bar_records) for a capture export."""
    doc = _load_json(path_or_obj)
    src = doc.get("source") or {}
    source_id = src.get("source_id") or ("rahavard365@" + str(src.get("captured_at") or "unknown"))
    source = {
        "source_id": source_id,
        "kind": src.get("kind", "rahavard365-web-api"),
        "endpoint": src.get("endpoint", BASE_URL),
        "session": src.get("session"),
        "captured_at": src.get("captured_at"),
        "input_sha256": src.get("input_sha256"),
        "adjust_scope": "per-series",
        "price_basis": "per-series",
        "license": src.get("license", "owner subscription; not redistributable"),
    }
    bars = []
    for series in doc.get("series") or []:
        ticker = series.get("ticker")
        asset_id = series.get("asset_id")
        adjust = series.get("adjust")
        basis = series.get("basis") or "real_close"
        if ticker:
            parsed = parse_ticker(ticker)
            if parsed:
                asset_id = asset_id if asset_id is not None else parsed[0]
                adjust = adjust if adjust is not None else parsed[1]
                basis = series.get("basis") if series.get("basis") else parsed[2]
        if asset_id is None or adjust is None:
            raise S.SchemaError("series without asset_id/adjust: %r" % (series.get("symbol"),))
        unavailable = list(series.get("unavailable") or [])
        for raw_bar in series.get("bars") or []:
            bars.append(_bar_record(asset_id, series.get("symbol"), adjust,
                                    series.get("resolution") or series.get("timeframe"),
                                    basis, source_id, raw_bar,
                                    src.get("captured_at"), unavailable))
    return source, bars


_CSV_ALIASES = {
    "date": ("date", "utc", "time", "day"),
    "symbol": ("symbol", "ticker", "name"),
    "symbol_id": ("symbol_id", "asset_id", "id", "ra_asset_id"),
    "open": ("open", "o", "our_o", "prod_o"),
    "high": ("high", "h", "our_h", "prod_h"),
    "low": ("low", "l", "our_l", "prod_l"),
    "close": ("close", "c", "our_c", "prod_c"),
    "volume": ("volume", "v", "vol"),
    "adjust": ("adjust", "adjustment", "mode"),
    "basis": ("basis", "price_basis", "price_type"),
    "timeframe": ("timeframe", "resolution", "res", "tf"),
}


def _pick(row, field, default=None):
    for alias in _CSV_ALIASES[field]:
        if alias in row and row[alias] not in (None, ""):
            return row[alias]
    return default


def parse_csv_rows(rows, source_id, retrieved_at, default_adjust=None,
                   default_basis=None, default_timeframe=None):
    bars = []
    for row in rows:
        adjust = _pick(row, "adjust", default_adjust)
        if adjust is None:
            raise S.SchemaError("csv row without adjust mode and no default given")
        symbol = _pick(row, "symbol", "")
        symbol_id = _pick(row, "symbol_id", symbol)
        # The bar builder reads `utc`; a CSV export names the column `date`.
        values = dict(row)
        values["utc"] = _pick(row, "date")
        bars.append(_bar_record(symbol_id, symbol, adjust,
                                _pick(row, "timeframe", default_timeframe),
                                _pick(row, "basis", default_basis) or "unknown",
                                source_id, values, retrieved_at))
    return bars


def parse_rahavard_csv(path_or_text):
    if os.path.exists(str(path_or_text)):
        with open(path_or_text, encoding="utf-8-sig", newline="") as fh:
            text = fh.read()
    else:
        text = str(path_or_text)
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise S.SchemaError("csv export has no data rows")
    source_id = "csv-export@" + (os.path.basename(str(path_or_text)) or "inline")
    source = {
        "source_id": source_id,
        "kind": "rahavard365-export",
        "endpoint": None,
        "captured_at": None,
        "input_sha256": S.row_hash({"n": len(rows), "head": rows[0]}),
        "adjust_scope": "per-row",
        "price_basis": "per-row",
        "license": "owner subscription; not redistributable",
    }
    return source, parse_csv_rows(rows, source_id, None)


def _load_json(path_or_obj):
    if isinstance(path_or_obj, (dict, list)):
        return path_or_obj
    with open(path_or_obj, encoding="utf-8-sig") as fh:
        return json.load(fh)


def detect_and_parse(path):
    """Parse whichever export shape the file is, by sniffing its first bytes."""
    with open(path, "rb") as fh:
        head = fh.read(4096).decode("utf-8-sig", "replace").lstrip()
    if head.startswith("{"):
        return parse_rahavard_json(path)
    return parse_rahavard_csv(path)