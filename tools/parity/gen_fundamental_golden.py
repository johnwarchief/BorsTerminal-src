#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""اوراکلِ طلاییِ B4: بدنۀ واقعیِ پایتونِ مسیرهایِ بنیادی و نوار رویِ فیکسچر.

چهار چیز قطعی می‌ماند:

* `BORS_DATA_DIR` به پوشۀ موقت (همان فیکسچر)، پس بانکِ عملیاتی باز نمی‌شود.
* `BORS_CHART_CDN=off` و `BORS_CODAL_OFFLINE=1` — هیچ درخواستِ شبکه‌ای درِ این
  مسیرها نیست، ولی درزها بسته می‌مانند تا اجرایِ گیت هم همین شکل باشد.
* «امروز» در ماژول‌هایی که `date.today()` می‌خوانند میخ‌کوبی می‌شود (سنجشِ
  تازگیِ داده و افقِ روزها به آن وابسته است).
* کش‌های درون‌پروسه بینِ صحنه‌ها پاک می‌شوند.

خروجی: backend-go/internal/fundamental/testdata/golden/<scenario>/<case>.json
اجرا: python tools/parity/gen_fundamental_golden.py
"""
import datetime as _dt
import importlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
FIX = os.path.join(ROOT, "backend-go", "internal", "fundamental", "testdata", "fixture")
OUT = os.path.join(ROOT, "backend-go", "internal", "fundamental", "testdata", "golden")
TODAY = _dt.date(2026, 10, 28)

UP, DOWN, FUND, THIN, MIXED = "عادی01", "پایین02", "اهرم‌ب", "کم‌سابقه11", "متنوع01"


class _Date(_dt.date):
    @classmethod
    def today(cls):
        return TODAY


class _DT:
    date, datetime, time, timedelta = _Date, _dt.datetime, _dt.time, _dt.timedelta


def prepare(tmp):
    for name in ("market.db", "user.db"):
        shutil.copyfile(os.path.join(FIX, name), os.path.join(tmp, name))
    os.environ["BORS_DATA_DIR"] = tmp
    os.environ["BORS_CHART_CDN"] = "off"
    os.environ.setdefault("BORS_CODAL_OFFLINE", "1")
    os.environ.setdefault("BORS_NO_FETCH_LOOPS", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def pin_clock(*mods):
    for mod in mods:
        for attr in ("datetime", "date"):
            obj = getattr(mod, attr, None)
            if obj is _dt.datetime or obj is _dt.date:
                setattr(mod, attr, _DT if attr == "datetime" else _Date)


def unwrap(body):
    """`/api/tape-history` پاسخِ orjson برمی‌گرداند، نه dict؛ بدنه را می‌گشاییم."""
    raw = getattr(body, "body", None)
    return json.loads(raw) if raw is not None else body


def call(fn, *args):
    """خطایِ HTTP خودِ مسیر هم صحنه است (نمادِ ناشناخته ⇒ 404)؛ آن را ثبت می‌کنیم
    تا Go همان شکل را برگرداند، نه اینکه کیس از فهرست بیفتد."""
    from fastapi import HTTPException
    try:
        return unwrap(fn(*args))
    except HTTPException as e:
        return {"__http_status__": e.status_code, "detail": e.detail}


def dump(scenario, name, body):
    path = os.path.join(OUT, scenario)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=1)
        f.write("\n")


def write_setting(tmp, name, payload):
    p = os.path.join(tmp, name)
    if payload is None:
        if os.path.exists(p):
            os.remove(p)
        return
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def ins_codes(market_db):
    con = sqlite3.connect("file:%s?mode=ro" % market_db.replace("\\", "/"), uri=True)
    out = {}
    try:
        for sym in (UP, DOWN, FUND, THIN, MIXED):
            row = con.execute("SELECT ins_code FROM instruments WHERE l_val18=?", (sym,)).fetchone()
            out[sym] = str(row[0]) if row else ""
    finally:
        con.close()
    return out


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="bors-fund-golden-")
    prepare(tmp)
    import api.chart as ch
    import api.fundamental as fd
    import api.market as mk
    import fts_engine as fe
    import codal_periods as cp
    pin_clock(ch, fd, mk, fe, cp)
    codes = ins_codes(os.path.join(tmp, "market.db"))

    # ---------- s1: پیش‌فرض ----------
    for name, sym in (("fund_up", UP), ("fund_down", DOWN), ("fund_fund", FUND),
                      ("fund_thin", THIN), ("fund_mixed", MIXED)):
        dump("s1", name, call(fd.get_fundamental, sym, 0))
    dump("s1", "fund_up_months6", call(fd.get_fundamental, UP, 6))
    dump("s1", "fund_unknown", call(fd.get_fundamental, "نیست۰۱", 0))
    for name, sym, limit in (("quarters_up", UP, 16), ("quarters_mixed", MIXED, 16),
                             ("quarters_thin", THIN, 4), ("quarters_clamp_high", UP, 999),
                             ("quarters_clamp_zero", UP, 0), ("quarters_negative", UP, -5),
                             ("quarters_missing", "نیست۰۱", 8)):
        dump("s1", name, call(fd.get_fundamental_quarters, sym, limit))
    dump("s1", "sectors", call(fd.api_fundamental_sectors))
    joined = ",".join([codes[UP], codes[DOWN], codes[THIN], codes[MIXED]])
    for name, args in (("tape_four", (joined, 20)), ("tape_all", ("", 20)),
                       ("tape_one_day", (codes[UP], 1)), ("tape_clamp_days", (codes[UP], 9999)),
                       ("tape_zero_days", (codes[UP], 0)),
                       ("tape_unknown_code", ("ISIN-NOT-HERE", 20)),
                       ("tape_cap_codes", (",".join([codes[UP]] * 500), 20))):
        dump("s1", name, call(mk.get_tape_history, *args))

    # ---------- s2: آستانه‌هایِ v10 در فایلِ تنظیمات ----------
    # سه قاعدۀ پرابِ آستانه‌ها با هم سنجیده می‌شوند:
    #   • `monetary_growth_min` هرگز با `v10_` پراب نمی‌شود (نامِ تاریخیِ کلیدِ
    #     پنل «هدفِ رشد» است) ⇒ کف از `growth_minِ` مشترک می‌آید؛
    #   • همان `v10_monetary_growth_min` به `monetary_growth_target` نگاشت می‌شود؛
    #   • حاشیهٔ ناخالص: `load_fts_config` با `dict(FTS_DEFAULTS)` شروع می‌کند، پس
    #     `v10_margin_min` همیشه در cfg هست و کلیدِ مشترک را می‌پوشاند — نوشتنِ
    #     تنها `margin_min` رأی را تکان نمی‌دهد. هر دو نوشته می‌شوند و همین
    #     پوشیدگی درِ گاردِ B4 پین شده است (اندازه‌گیری، نه حدس).
    write_setting(tmp, "fts_thresholds.json", {
        "margin_min": 40.0, "v10_margin_min": 40.0,
        "v10_monetary_growth_min": 10.0, "growth_min": 70.0})
    dump("s2", "fund_up", call(fd.get_fundamental, UP, 0))
    dump("s2", "fund_down", call(fd.get_fundamental, DOWN, 0))
    dump("s2", "fund_thin", call(fd.get_fundamental, THIN, 0))
    write_setting(tmp, "fts_thresholds.json", None)

    # ---------- s3: بانکی که جدولِ نوار ندارد ----------
    con = sqlite3.connect(os.path.join(tmp, "user.db"))
    con.executescript("DROP TABLE tape_flag_day; DROP TABLE tape_flag_day_meta;")
    con.commit()
    con.close()
    dump("s3", "tape_missing_tables", call(mk.get_tape_history, joined, 20))
    dump("s3", "tape_empty_meta", call(mk.get_tape_history, codes[UP], 20))

    print("fundamental goldens -> %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
