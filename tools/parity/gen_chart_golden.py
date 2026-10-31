#!/usr/bin/env python
"""اوراکلِ طلاییِ B3: بدنۀ واقعیِ پایتونِ هشت مسیرِ api/chart.py رویِ فیکسچر.

چهار چیز قفل می‌شود تا خروجی قطعی باشد:

* «امروز» = ۲۰۲۶-۱۰-۲۸ (تنها مصرفِ تاریخِ دیواری در این مسیرها `_upcoming_by` است).
* `BORS_CHART_CDN=off` (درزِ پاریتی): هیچ درخواستِ شبکه‌ای، و ترمیمِ پس‌زمینهٔ
  تاریخچه خاموش — همان چیزی که Go در B3 می‌دهد.
* `BORS_CALENDAR_PATH` به تقویمِ فیکسچر، نه تقویمِ واقعیِ ماشین.
* کش‌های درون‌پروسه بینِ صحنه‌ها پاک می‌شوند؛ تنظیمات (مبنا/ساعتِ شنی) با فایلِ
  صحنه نوشته می‌شوند و امضایِ دیسک خودش کش را باطل می‌کند.

خروجی: backend-go/internal/chart/testdata/golden/<scenario>/<case>.json
"""
import datetime as _dt
import json
import os
import shutil
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
FIX = os.path.join(ROOT, "backend-go", "internal", "chart", "testdata", "fixture")
OUT = os.path.join(ROOT, "backend-go", "internal", "chart", "testdata", "golden")
TODAY = _dt.date(2026, 10, 28)

UP, DOWN, FUND, SHORT, NODATA = "عادی01", "پایین02", "اهرم‌ب", "کم‌سابقه11", "بی‌معامله04"
DUAL = "عادی 01"


class _Date(_dt.date):
    @classmethod
    def today(cls):
        return TODAY


class _DT:
    date, datetime, time, timedelta = _Date, _dt.datetime, _dt.time, _dt.timedelta


def prepare(tmp):
    for name in ("market.db", "user.db"):
        shutil.copyfile(os.path.join(FIX, name), os.path.join(tmp, name))
    cal = os.path.join(FIX, "calendar", "cache.json")
    os.environ["BORS_DATA_DIR"] = tmp
    os.environ["BORS_CALENDAR_PATH"] = cal
    os.environ["BORS_CHART_CDN"] = "off"
    os.environ.setdefault("BORS_CODAL_OFFLINE", "1")
    os.environ.setdefault("BORS_NO_FETCH_LOOPS", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def clear_caches(ch):
    for name in ("CHART_CACHE", "KEY_LEVELS_CACHE", "MA_CACHE",
                 "PATTERNS_CACHE", "FTS_ANALYSIS_CACHE"):
        getattr(ch, name).clear()


def write_setting(tmp, name, payload):
    path = os.path.join(tmp, name)
    if payload is None:
        if os.path.exists(path):
            os.remove(path)
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def dump(scenario, name, body):
    path = os.path.join(OUT, scenario)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=1)
        f.write("\n")


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="bors-chart-golden-")
    prepare(tmp)
    import api.chart as ch
    ch.datetime = _DT
    os.makedirs(OUT, exist_ok=True)

    # ---------- s1: پیش‌فرض (مبنای last، تنظیماتِ ساعتِ شنی پیش‌فرض) ----------
    clear_caches(ch)
    write_setting(tmp, "price_basis.json", None)
    write_setting(tmp, "fts_thresholds.json", None)
    for name, sym in (("chartdb_uptrend", UP), ("chartdb_downtrend", DOWN),
                      ("chartdb_fund", FUND), ("chartdb_short", SHORT),
                      ("chartdb_nodata", NODATA), ("chartdb_dualspell", DUAL)):
        dump("s1", name, ch.get_chart_db(sym, 3))
    for name, sym in (("keylevels_uptrend", UP), ("keylevels_short", SHORT),
                      ("keylevels_nodata", NODATA)):
        dump("s1", name, ch.get_key_levels(sym))
    for name, sym in (("ma_uptrend", UP), ("ma_downtrend", DOWN), ("ma_short", SHORT)):
        dump("s1", name, ch.get_ma_events(sym, 730))
    for name, sym in (("patterns_uptrend", UP), ("patterns_short", SHORT)):
        dump("s1", name, ch.get_patterns(sym))
    for name, sym in (("orderbook_five", UP), ("orderbook_null", DOWN),
                      ("orderbook_missing", NODATA)):
        dump("s1", name, ch.get_order_book(sym))
    dump("s1", "calendar_symbol", ch.get_calendar_events(UP))
    dump("s1", "calendar_upcoming", ch.get_calendar_upcoming(14))
    for name, sym, as_of in (("fts_uptrend", UP, None), ("fts_downtrend", DOWN, None),
                             ("fts_short", SHORT, None), ("fts_nodata", NODATA, None),
                             ("fts_asof", UP, "2026-09-01")):
        dump("s1", name, ch.get_fts(sym, as_of))

    # ---------- s2: بانکی که جدولِ order_book ندارد ----------
    clear_caches(ch)
    con = sqlite3.connect(os.path.join(tmp, "market.db"))
    con.execute("DROP TABLE order_book")
    con.commit()
    con.close()
    for name, sym in (("orderbook_five", UP), ("orderbook_null", DOWN)):
        dump("s2", name, ch.get_order_book(sym))

    # ---------- s3: تنظیماتِ سفارشیِ ساعتِ شنی ----------
    clear_caches(ch)
    write_setting(tmp, "fts_thresholds.json", {
        "hourglass_rsi_period": 5,
        "hourglass_rsi_oversold": 40.0,
        "hourglass_ma52_position": "above",
    })
    dump("s3", "fts_uptrend", ch.get_fts(UP, None))
    dump("s3", "chartdb_uptrend", ch.get_chart_db(UP, 3))

    # ---------- s4: مبنای closing ----------
    clear_caches(ch)
    write_setting(tmp, "fts_thresholds.json", None)
    write_setting(tmp, "price_basis.json", {"basis": "closing"})
    dump("s4", "keylevels_uptrend", ch.get_key_levels(UP))
    dump("s4", "ma_uptrend", ch.get_ma_events(UP, 730))
    dump("s4", "patterns_uptrend", ch.get_patterns(UP))
    dump("s4", "chartdb_uptrend", ch.get_chart_db(UP, 3))
    dump("s4", "fts_uptrend", ch.get_fts(UP, None))

    print("chart goldens -> %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
