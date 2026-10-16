#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline contract test for configurable Hourglass RSI and MA52 gating.

No market.db, network, or running API server is required.
"""
import datetime
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.chart as CH  # noqa: E402
import api.market as M  # noqa: E402
from bors_config import FTS_DEFAULTS  # noqa: E402

PASS = FAIL = 0


def ck(label, cond):
    global PASS, FAIL
    print(("  PASS " if cond else "  FAIL ") + label)
    if cond:
        PASS += 1
    else:
        FAIL += 1


def bars(n=720):
    start = datetime.date(2024, 1, 1)
    result = []
    for i in range(n):
        # Slight upward drift plus repeated pullbacks produces non-flat weekly RSI.
        close = 100.0 + i * 0.015 + 4.0 * math.sin(i / 13.0) + 1.1 * math.sin(i / 3.7)
        day = start + datetime.timedelta(days=i)
        result.append({
            "time": day.isoformat(), "open": close - 0.2, "high": close + 0.7,
            "low": close - 0.8, "close": close, "volume": 1000.0 + i,
        })
    return result


def main():
    ck("backend default is RSI(7)", FTS_DEFAULTS.get("hourglass_rsi_period") == 7)
    ck("oversold threshold defaults to 30", FTS_DEFAULTS.get("hourglass_rsi_oversold") == 30.0)
    ck("MA52 mode defaults to below", FTS_DEFAULTS.get("hourglass_ma52_position") == "below")

    original_market_path = M.FTS_CONFIG_PATH
    original_chart_path = CH.FTS_CONFIG_PATH
    original_cache = dict(CH._FTS_HG_SETTINGS_CACHE)
    try:
        with tempfile.TemporaryDirectory(prefix="fts-hourglass-") as tmp:
            config_path = os.path.join(tmp, "fts_thresholds.json")
            M.FTS_CONFIG_PATH = config_path
            CH.FTS_CONFIG_PATH = config_path
            CH._FTS_HG_SETTINGS_CACHE.update({"signature": None, "values": None})

            saved = M.set_fts_config({
                "hourglass_rsi_period": 7,
                "hourglass_rsi_oversold": 30,
                "hourglass_ma52_position": "below",
            })
            ck("valid settings persist through POST handler", saved.get("status") == "success")
            loaded = CH._fts_hourglass_settings()
            ck("engine reads RSI period 7 from saved settings", loaded["hourglass_rsi_period"] == 7)

            series = bars()
            below = CH._fts_analyze_candles("HG-TEST", series)["hourglass"]
            ck("analysis returns active RSI period and threshold", below.get("rsi_period") == 7 and below.get("rsi_oversold") == 30.0)
            ck("legacy weekly_rsi5 alias equals RSI value for compatibility",
               below.get("weekly_rsi") is not None and below.get("weekly_rsi") == below.get("weekly_rsi5"))
            ck("MA52 is only computed with at least 52 weekly bars",
               below.get("weekly_bars", 0) >= 52 and below.get("ma52") is not None)

            saved9 = M.set_fts_config({
                "hourglass_rsi_period": 9,
                "hourglass_rsi_oversold": 50,
                "hourglass_ma52_position": "above",
            })
            above = CH._fts_analyze_candles("HG-TEST", series)["hourglass"]
            ck("changed RSI period and threshold apply to engine output",
               saved9.get("status") == "success" and above.get("rsi_period") == 9 and above.get("rsi_oversold") == 50.0
               and above.get("weekly_rsi") is not None and above.get("weekly_rsi") != below.get("weekly_rsi"))
            ck("above mode matches actual price-vs-MA52 geometry",
               above.get("ma52_position_mode") == "above"
               and above.get("ma52_position_match") == (above.get("weekly_close") > above.get("ma52")))
            ck("below mode matches actual price-vs-MA52 geometry",
               below.get("ma52_position_mode") == "below"
               and below.get("ma52_position_match") == (below.get("weekly_close") < below.get("ma52")))

            saved_either = M.set_fts_config({
                "hourglass_rsi_period": 7,
                "hourglass_rsi_oversold": 30,
                "hourglass_ma52_position": "either",
            })
            either = CH._fts_analyze_candles("HG-TEST", series)["hourglass"]
            ck("either mode disables direction comparison but retains MA52 context",
               saved_either.get("status") == "success" and either.get("ma52") is not None
               and either.get("ma52_position_mode") == "either" and either.get("ma52_position_match") is True)

            bad_period = M.set_fts_config({"hourglass_rsi_period": 7.5})
            bad_threshold = M.set_fts_config({"hourglass_rsi_oversold": 51})
            bad_mode = M.set_fts_config({"hourglass_ma52_position": "sideways"})
            ck("non-integer RSI periods are rejected", bad_period.get("status") == "error" and "hourglass_rsi_period" in bad_period.get("errors", {}))
            ck("out-of-range oversold thresholds are rejected", bad_threshold.get("status") == "error" and "hourglass_rsi_oversold" in bad_threshold.get("errors", {}))
            ck("unknown MA52 modes are rejected", bad_mode.get("status") == "error" and "hourglass_ma52_position" in bad_mode.get("errors", {}))

            too_short = CH._fts_analyze_candles("HG-SHORT", series[:200])["hourglass"]
            ck("insufficient MA52 history returns UNKNOWN, not false", too_short.get("active") is None and too_short.get("action") == "UNKNOWN")
    finally:
        M.FTS_CONFIG_PATH = original_market_path
        CH.FTS_CONFIG_PATH = original_chart_path
        CH._FTS_HG_SETTINGS_CACHE.update(original_cache)

    # Separate sandbox for the server-side single-symbol analysis cache regression.
    original_market_path_2 = M.FTS_CONFIG_PATH
    original_chart_path_2 = CH.FTS_CONFIG_PATH
    original_hg_cache_2 = dict(CH._FTS_HG_SETTINGS_CACHE)
    original_series = CH._fts_analysis_series
    original_events = CH._stored_adjust_events
    original_source = CH._stored_adjust_source
    original_capability = CH._adjust_capability
    original_analysis_cache = dict(CH.FTS_ANALYSIS_CACHE)
    try:
        with tempfile.TemporaryDirectory(prefix="fts-hourglass-cache-") as tmp:
            config_path = os.path.join(tmp, "fts_thresholds.json")
            M.FTS_CONFIG_PATH = config_path
            CH.FTS_CONFIG_PATH = config_path
            CH._FTS_HG_SETTINGS_CACHE.update({"signature": None, "values": None})
            cache_series = bars()
            CH._fts_analysis_series = lambda _symbol: (cache_series, "test-basis")
            CH._stored_adjust_events = lambda _symbol: []
            CH._stored_adjust_source = lambda _symbol: "test-source"
            CH._adjust_capability = lambda _events, _source: {}
            CH.FTS_ANALYSIS_CACHE.clear()

            first_save = M.set_fts_config({
                "hourglass_rsi_period": 7,
                "hourglass_rsi_oversold": 30,
                "hourglass_ma52_position": "below",
            })
            first_cached = CH._fts_analyze_symbol("HG-CACHE")
            second_save = M.set_fts_config({
                "hourglass_rsi_period": 9,
                "hourglass_rsi_oversold": 50,
                "hourglass_ma52_position": "above",
            })
            second_cached = CH._fts_analyze_symbol("HG-CACHE")
            first_hg = (first_cached.get("fts") or {}).get("hourglass") or {}
            second_hg = (second_cached.get("fts") or {}).get("hourglass") or {}
            ck("server 900s cache is keyed by active hourglass settings",
               first_save.get("status") == "success" and second_save.get("status") == "success"
               and first_hg.get("rsi_period") == 7
               and second_hg.get("rsi_period") == 9
               and second_hg.get("rsi_oversold") == 50.0
               and second_hg.get("ma52_position_mode") == "above")
    finally:
        CH._fts_analysis_series = original_series
        CH._stored_adjust_events = original_events
        CH._stored_adjust_source = original_source
        CH._adjust_capability = original_capability
        CH.FTS_ANALYSIS_CACHE.clear()
        CH.FTS_ANALYSIS_CACHE.update(original_analysis_cache)
        M.FTS_CONFIG_PATH = original_market_path_2
        CH.FTS_CONFIG_PATH = original_chart_path_2
        CH._FTS_HG_SETTINGS_CACHE.update(original_hg_cache_2)

    print(f"\n{PASS + FAIL} checks, {FAIL} failures")
    print("HOURGLASS USER SETTINGS " + ("OK" if not FAIL else "FAILED"))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
