#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32E: the FTS weekly/monthly resampler uses the Round 32D calendar.

No network, no DB.  A temporary pack checks:
  * a covered W key takes the reference bar instead of the product aggregate;
  * a covered M key takes the reference bar (Jalali month bucket);
  * no symbol / no pack keeps the product aggregate unchanged;
  * the pack hash is verified, a tampered pack is a no-op;
  * Jalali month keys and Saturday week keys are stable.
"""
import gzip
import hashlib
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import wm_calendar as WMC  # noqa: E402
import api.chart as C  # noqa: E402

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   <- %s" % (detail,)) if detail else ""))


def write_pack(root, rows, bad_hash=False):
    d = os.path.join(root, "pack")
    os.makedirs(d, exist_ok=True)
    fp = os.path.join(d, "wm_calendar_bars.ndjson.gz")
    payload = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                      for r in rows).encode("utf-8")
    with open(fp, "wb") as fh:
        fh.write(gzip.compress(payload, compresslevel=9, mtime=0))
    h = hashlib.sha256(open(fp, "rb").read()).hexdigest()
    if bad_hash:
        h = "0" * 64
    man = {"schema": "ra365-wm-calendar-pack-v1", "version": "test-32e",
           "created_at": "2026-10-25T00:00:00+00:00",
           "files": {"bars": "wm_calendar_bars.ndjson.gz"},
           "file_sha256": {"bars": h},
           "counts": {"W": 1, "M": 1, "total": 2}}
    with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh)
    return d


def use(d):
    os.environ["BORS_WM_CALENDAR_DIR"] = d
    WMC._CACHE.clear()


def row(tf, key, close):
    return {"schema": "ra365-wm-calendar-bar/1", "symbol_id": "1",
            "symbol": "TEST", "timeframe": tf, "key": key,
            "date_from": "2026-10-03", "date_to": "2026-10-07",
            "open": 100.0, "high": 110.0, "low": 90.0, "close": close,
            "volume": 12345.0, "n_sessions": 3, "source": "test",
            "ref_bars_sha256": "test", "generated_at": "2026-10-25T00:00:00+00:00",
            "unavailable": [], "note": "test"}


def main():
    tmp = tempfile.mkdtemp(prefix="r32e_test_")
    try:
        wk = WMC.week_key("2026-10-03")
        mk = WMC.month_key("2026-10-03")
        ck(wk == WMC.week_key("2026-10-07"), "Saturday week key covers the week")
        ck(mk == WMC.month_key("2026-10-20"), "Jalali month key is stable in the month")
        ck(WMC.month_key("2023-12-04") == 16832,
           "the validated Jalali key for 2023-12-04 is 16832", WMC.month_key("2023-12-04"))

        candles = [
            {"time": "2026-10-03", "open": 10.0, "high": 12.0, "low": 9.0,
             "close": 11.0, "volume": 100},
            {"time": "2026-10-04", "open": 11.0, "high": 15.0, "low": 8.0,
             "close": 14.0, "volume": 200},
            {"time": "2026-10-07", "open": 14.0, "high": 16.0, "low": 13.0,
             "close": 15.0, "volume": 300},
            {"time": "2026-11-05", "open": 20.0, "high": 22.0, "low": 19.0,
             "close": 21.0, "volume": 400},
        ]

        # No pack: the product aggregate is unchanged.
        os.environ.pop("BORS_WM_CALENDAR_DIR", None)
        WMC._CACHE.clear()
        w0 = C._fts_resample(candles, "W", symbol="TEST")
        ck(w0[0]["open"] == 10.0 and w0[0]["high"] == 16.0 and w0[0]["close"] == 15.0,
           "without a pack the weekly aggregate is the product's", w0[0])
        m0 = C._fts_resample(candles, "M", symbol="TEST")
        ck(len(m0) == 2 and m0[0]["close"] == 15.0 and m0[1]["close"] == 21.0,
           "without a pack the Jalali month aggregate is the product's", m0)

        # With the pack: the covered W and M bars are replaced.
        d = write_pack(tmp, [row("W", wk, 500.0), row("M", mk, 700.0)])
        use(d)
        ck(WMC.capability("TEST").get("covered") is True,
           "capability reports the covered symbol", WMC.capability("TEST"))
        w1 = C._fts_resample(candles, "W", symbol="TEST")
        ck(w1[0]["close"] == 500.0 and w1[0]["open"] == 100.0
           and w1[0]["high"] == 110.0 and w1[0]["low"] == 90.0,
           "the covered weekly bar is the reference bar", w1[0])
        ck(w1[0]["time"] == "2026-10-07" and w1[0]["volume"] == 12345.0,
           "the reference bar carries its own date and volume", w1[0])
        m1 = C._fts_resample(candles, "M", symbol="TEST")
        ck(m1[0]["close"] == 700.0, "the covered Jalali month bar is replaced", m1[0])
        ck(len(m1) == 2, "only the covered month key changes", len(m1))
        w_no_sym = C._fts_resample(candles, "W")
        ck(w_no_sym[0]["close"] == 15.0,
           "without a symbol the pack is not applied", w_no_sym[0])
        ck(WMC.bar("OTHER", "W", wk) is None,
           "an uncovered symbol is a no-op")
        ck(WMC.bar("TEST", "W", wk + 1) is None,
           "an uncovered key is a no-op")

        # Tampered pack: refused, no-op.
        d = write_pack(os.path.join(tmp, "bad"), [row("W", wk, 500.0)], bad_hash=True)
        use(d)
        ck(WMC.get_pack() is None and WMC.bar("TEST", "W", wk) is None,
           "a tampered pack is refused, not applied")
    finally:
        os.environ.pop("BORS_WM_CALENDAR_DIR", None)
        WMC._CACHE.clear()
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print("result: %d pass, %d fail" % (P, F))
    print("%d/%d" % (P, P + F))
    sys.exit(0 if F == 0 else 1)


if __name__ == "__main__":
    main()
