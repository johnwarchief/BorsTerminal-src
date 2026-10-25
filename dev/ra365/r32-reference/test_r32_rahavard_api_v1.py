#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32A: the Rahavard vocabulary and both export parsers."""
import _harness as H

import r32_schema as S
import r32_rahavard_api as API

# --- ticker vocabulary ---------------------------------------------------
H.ck(API.ticker_for("453", "raw") == "exchange.asset:453:real_close:type0",
     "ticker_for: a raw series uses type0")
H.ck(API.ticker_for("453", "adjusted") == "exchange.asset:453:real_close:type7",
     "ticker_for: an adjusted series uses type7")
H.ck(API.parse_ticker("exchange.asset:453:real_close:type7") == ("453", "adjusted", "real_close"),
     "parse_ticker: splits id, adjust and basis")
H.ck(API.parse_ticker("not-a-ticker") is None, "parse_ticker: a foreign string returns None")

url = API.bars_url("exchange.asset:453:real_close:type0", "d", 300, "2024-01-01", "2024-02-01")
H.ck(url.startswith("/api/v2/chart/bars?"), "bars_url: uses the measured endpoint", url)
H.ck("countback=300" in url and "resolution=D" in url, "bars_url: carries countback and resolution")
H.ck("symbol=exchange.asset%3A453%3Areal_close%3Atype0" in url,
     "bars_url: the ticker is percent-encoded", url)

# --- a capture export ----------------------------------------------------
doc = {
    "source": {"kind": "rahavard365-web-api", "captured_at": "2026-10-25T10:00:00Z",
               "endpoint": "https://rahavard365.com"},
    "series": [{
        "asset_id": 453, "symbol": "\u0641\u0648\u0644\u0627\u062f",
        "ticker": "exchange.asset:453:real_close:type7",
        "resolution": "D", "basis": "real_close", "adjust": "adjusted",
        "bars": [{"utc": "2024-01-05", "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5},
                 {"utc": "2024-01-06", "open": 1.6, "high": 2.6, "low": 1.1, "close": 2.0,
                  "volume": 12}],
    }],
}
src, bars = API.parse_rahavard_json(doc)
H.ck(len(bars) == 2, "json export: two bars parsed")
H.ck(src["kind"] == "rahavard365-web-api", "json export: the source kind is carried")
H.ck(all(b["schema"] == S.SCHEMA_BAR for b in bars), "json export: every bar carries the contract")
H.ck(bars[0]["adjust"] == "adjusted" and bars[0]["symbol_id"] == "453",
     "json export: adjust and symbol_id are derived from the ticker")
H.ck(bars[0]["date"] == "2024-01-05" and bars[0]["basis"] == "real_close",
     "json export: date normalised and basis kept")
H.ck("volume" in bars[0]["unavailable"] and bars[0]["volume"] is None,
     "json export: a bar without volume marks volume unavailable instead of zero", bars[0])
H.ck(S.validate(bars[0], S.SCHEMA_BAR) == [], "json export: the first bar satisfies the contract")
H.ck(bars[0]["row_hash"] != bars[1]["row_hash"], "json export: distinct bars hash differently")

# --- a manual CSV export -------------------------------------------------
text = ("date,symbol,open,high,low,close,volume,adjust,basis,timeframe\n"
        "2024/01/05,\u0641\u0648\u0644\u0627\u062f,10,12,9,11,100,raw,last,D\n"
        "2024-01-06,\u0641\u0648\u0644\u0627\u062f,11,13,10,12.5,,raw,last,D\n")
src2, bars2 = API.parse_rahavard_csv(text)
H.ck(len(bars2) == 2, "csv export: two bars parsed")
H.ck(bars2[0]["date"] == "2024-01-05" and bars2[0]["close"] == 11.0,
     "csv export: a YYYY/MM/DD date normalises and numbers convert")
H.ck(bars2[1]["volume"] is None and "volume" in bars2[1]["unavailable"],
     "csv export: a blank volume is unavailable, not zero")
H.ck(src2["kind"] == "rahavard365-export", "csv export: the source kind is carried")
H.ck(S.validate(bars2[1], S.SCHEMA_BAR) == [], "csv export: a row with a blank volume validates")

H.ck(len(API.parse_csv_rows([{"date": "2024-01-05", "symbol": "x", "o": 1, "h": 2, "l": 0.5,
                              "c": 1.5}], "s", None, default_adjust="raw",
                            default_timeframe="D")) == 1,
     "csv export: short column aliases (o/h/l/c) are understood")

H.report()