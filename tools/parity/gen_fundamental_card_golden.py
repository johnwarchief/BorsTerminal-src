#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""اوراکلِ طلاییِ «کارتِ پنج‌محور» — مسیرِ `GET /api/fundamental/{symbol}`.

داورِ پورتِ Go برایِ کارتِ بنیادی همین است: بدنۀ واقعیِ پایتون رویِ همان
فیکسچرِ یخ‌زۀ `internal/fundamental/testdata/fixture/market.db`، نه دست‌نویس و نه
جدولِ عملیاتی.

چهار چیز قطعی می‌ماند (همان قواعدِ `gen_fundamental_golden.py`):

* `BORS_DATA_DIR` به پوشۀ موقت (کپیِ فیکسچر) ⇒ بانکِ عملیاتی باز نمی‌شود.
* `BORS_CHART_CDN=off` و `BORS_CODAL_OFFLINE=1` ⇒ هیچ درخواستِ شبکه‌ای نیست.
* «امروز» درِ ماژول‌هایی که `date.today()` می‌خوانند مخ‌کوبی می‌شود (سنجشِ
  تازگیِ داده به آن وابسته است) ⇒ اجرایِ دوباره همان بایت را می‌دهد.
* بدنه با همان قراردادِ طلایی‌هایِ موجود نوشته می‌شود: `ensure_ascii=False`،
  `indent=1`، بدونِ `sort_keys` (ترتیبِ درجِ پاسخِ پایتون معنادار است)، خطِ
  تازهٔ پایانی، و LF (`.gitattributes` هم `eol=lf` است ⇒ بایتِ کامیت‌شده درِ
  هر سیستمی یکی است).

خروجی:
  backend-go/internal/fundamental/testdata/golden/card_<CASE>/body.json
  backend-go/internal/fundamental/testdata/golden/card_<CASE>/meta.json
  backend-go/internal/fundamental/testdata/golden/card_index.json

اجرا: python tools/parity/gen_fundamental_card_golden.py [--out <پوشه>]
"""
import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FIX = os.path.join(ROOT, "backend-go", "internal", "fundamental", "testdata", "fixture")
OUT = os.path.join(ROOT, "backend-go", "internal", "fundamental", "testdata", "golden")
TODAY = _dt.date(2026, 10, 28)
SETTINGS_FILE = "fts_thresholds.json"

UP, DOWN, FUND, THIN, MIXED = "عادی01", "پایین02", "اهرم‌ب", "کم‌سابقه11", "متنوع01"
# رقمِ فارسی با کدپوینت: نوشتنِ مستقیمِ رقم درِ متن، رقم را می‌دزدد.
UNKNOWN = "نیست" + chr(0x06F0) + chr(0x06F1)
GUARD = "نگهبان03"        # رویِ تابلو، ارزشِ بازارِ NULL
GHOST = "غایب"           # در instruments، بدونِ ردیفِ تابلو
HOLDING = "سخت05"        # صنعتِ سرمایه‌گذاری ⇒ محورِ ۴ معاف
NO_SALES = "کدبه‌کد09"   # فروشِ سالانۀ راستی‌آمایی‌شده ندارد

# (نامِ کیس، نماد، months، شاخه‌ای که این بدنه پوشش می‌دهد، پروندهٔ آستانه‌ها)
# پروندهٔ آستانه‌ها همان `fts_thresholds.json`ِ پوشۀ داده است — همان مکانیزمی
# که صحنۀ `s2`ِ `gen_fundamental_golden.py` از آن استفاده می‌کند. بانک هرگز
# دست نخورده می‌ماند؛ فقط آستانهٔ مؤثر عوض می‌شود.
CASES = (
    ("card_up", UP, 0,
     "چهار محور از پنج محور قبول (score=4، حکمِ WATCH)؛ شش صورتِ مالیِ سالانه و "
     "ارزشِ بازار از اسنپ‌شاتِ رسمی", None),
    ("card_up_score5", UP, 0,
     "هر پنج محور قبول (score=5، حکمِ STRONG) — با مبنای تورمِ 40 درصد رشدِ "
     "واقعی مثبت می‌شود؛ با پیش‌فرضِ 60 درصد همین نماد چهار از پنج محور را "
     "قبول است (نگاه به card_up)", {"v10_inflation_basis": 40.0}),
    ("card_down", DOWN, 0,
     "دو محورِ ردِ واقعی: EPSِ نزولی و حاشیۀ ناخالصِ 11 درصد ⇒ حکمِ REJECT با "
     "score=2", None),
    ("card_fund", FUND, 0,
     "صندوق: applicable=false، حکمِ «FTS ندارد» و score=null", None),
    ("card_thin", THIN, 0,
     "گپِ داده درِ محورهای 1، 2 و 3: سه‌حالۀ null در برابر False، نه صفرِ ساختگی",
     None),
    ("card_mixed", MIXED, 0,
     "نمادِ فقط-کدال: ارزشِ بازار «موجود نیست» (symbol_not_on_board) و محورِ 3 "
     "با na=true؛ تله‌های ترتیب و نوشتارِ تاریخ هم درِ همان بدنه‌اند", None),
    ("card_mcap_missing", GUARD, 0,
     "ستونِ ارزشِ بازار هست ولی مقدارِ آن ندارد (market_cap_missing_value) و "
     "نماد به‌خاطرِ قیمت‌گذاریِ دستوری از غربالگری حذف شده است", None),
    ("card_no_board_row", GHOST, 0,
     "نماد درِ instruments هست ولی ردیفِ تابلو ندارد ⇒ ارزشِ بازارِ بدونِ asof و "
     "متنِ «موجود نیست»", None),
    ("card_holding", HOLDING, 0,
     "نمادِ تابلوییِ بی‌دادۀ کدال درِ صنعتِ سرمایه‌گذاری ⇒ محورِ 4 معاف (N/A)", None),
    ("card_no_sales", NO_SALES, 0,
     "فروشِ سالانۀ راستی‌آمایی‌شده ندارد ⇒ محورِ 4 «سنجیده نشد» (نه رد)", None),
    ("card_not_found", UNKNOWN, 0,
     "نمادِ ناشناخته ⇒ 404 با شکلِ خودِ مسیر", None),
    ("card_up_months6", UP, 6,
     "پارامترِ months درِ داوری اثری ندارد ⇒ بدنه عینِ card_up است", None),
)

# شاخه‌هایی که این فیکسچر نمی‌تواند بسازد — صریح ثبت می‌شود تا داور فکرکند
# «پوشش ناقص است» نه «پوشش هست».
NOT_COVERED = (
    {"branch": "قراردادِ اختیار (l_val18 با «ض»)",
     "why": "هیچ نمادِ «ض…» درِ جدولِ instrumentsِ فیکسچر نیست، پس شاخهٔ "
            "option_contract (ارجاع به نمادِ اصلی و حکمِ «FTS ندارد») هیچ بدنه‌ای "
            "ندارد."},
    {"branch": "خطِ کلاسِ شماردار (پایه درِ کدال ← خطِ تابلو)",
     "why": "قاعدۀ class_siblings تک‌رقمِ انتهایِ نام را می‌طلبد و همهٔ نام‌هایِ "
            "تابلویِ فیکسچر پسوندِ دو‌رقمی دارند («عادی01»، «ساده12» …)؛ پس هیچ "
            "جفتِ «پایه درِ کدال / خطِ شماردار درِ تابلو» درِ این بانک ساخته نمی‌شود."},
    {"branch": "ستونِ ارزشِ بازار غایب (market_cap_column_missing)",
     "why": "جدولِ market_watchِ فیکسچر ستونِ market_cap را دارد؛ ضمناً خودِ کد "
            "درِ این حالت مهاجرت را صدا می‌زند (ensure_market_cap_schema)، پس "
            "شاخه درِ اجرا ترمیم می‌شود و بدنۀ پایدار ندارد."},
    {"branch": "ارزشِ بازارِ نامعتبر (market_cap_invalid_value)",
     "why": "هیچ مقدارِ NaN/inf درِ ستونِ market_cap نیست."},
    {"branch": "بانِ مردۀ تابلو (market_cap_no_live_band)",
     "why": "تنها بانِ خالیِ فیکسچر 0/0 است و قاعدۀ mcap_dead_band_sql بانِ "
            "خالی را عمداً رد نمی‌کند (نبودِ شاهد ≠ شاهدِ بی‌اعتباری)."},
)


class _Date(_dt.date):
    @classmethod
    def today(cls):
        return TODAY


class _DT:
    date, datetime, time, timedelta = _Date, _dt.datetime, _dt.time, _dt.timedelta


def prepare(tmp):
    """کپیِ موقتِ فیکسچر + دروازه‌های بدونِ شبکه."""
    for name in ("market.db", "user.db"):
        shutil.copyfile(os.path.join(FIX, name), os.path.join(tmp, name))
    os.environ["BORS_DATA_DIR"] = tmp
    os.environ["BORS_CHART_CDN"] = "off"
    os.environ.setdefault("BORS_CODAL_OFFLINE", "1")
    os.environ.setdefault("BORS_NO_FETCH_LOOPS", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def pin_clock(*mods):
    """«امروز» را میخ‌کوبی می‌کند تا دوباره‌کاری بایت‌به‌بایت بماند."""
    for mod in mods:
        for attr in ("datetime", "date"):
            obj = getattr(mod, attr, None)
            if obj is _dt.datetime or obj is _dt.date:
                setattr(mod, attr, _DT if attr == "datetime" else _Date)


def write_setting(tmp, name, payload):
    """پروندهٔ آستانه‌ها درِ پوشۀ داده (مثلِ صحنۀ `s2`ِ اوراکلِ بنیادی)."""
    p = os.path.join(tmp, name)
    if payload is None:
        if os.path.exists(p):
            os.remove(p)
        return
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def unwrap(body):
    """`/api/tape-history` پاسخِ orjson برمی‌گرداند؛ اینجا dict است."""
    raw = getattr(body, "body", None)
    return json.loads(raw) if raw is not None else body


def call(fn, *args):
    """خطایِ HTTPِ خودِ مسیر هم صحنه است (نمادِ ناشناخته ⇒ 404)."""
    from fastapi import HTTPException
    try:
        return unwrap(fn(*args))
    except HTTPException as e:
        return {"__http_status__": e.status_code, "detail": e.detail}


def json_bytes(payload):
    """بایتِ همان قراردادِ طلایی‌هایِ موجود — با LFِ ثابت درِ هر سیستم."""
    return (json.dumps(payload, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def write_bytes(path, raw):
    with open(path, "wb") as f:
        f.write(raw)


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit():
    """sha1ِ کمیتِ پایتون درِ لحظۀ تولید (اطّلاعی است، نه شرطِ بازتولید)."""
    try:
        out = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"],
                             capture_output=True, text=True)
        sha = (out.stdout or "").strip()
        return sha if len(sha) == 40 else None
    except Exception:                                        # noqa: BLE001
        return None


def fixture_digests():
    return {name: sha256_file(os.path.join(FIX, name))
            for name in ("market.db", "user.db")}


def route_of(symbol, months):
    path = "/api/fundamental/" + symbol
    return ("GET " + path + ("?months=%d" % months if months else ""))


def main(argv=None):
    argv = list(argv) if argv is not None else []
    ap = argparse.ArgumentParser(
        prog="gen_fundamental_card_golden.py",
        description="اوراکلِ طلاییِ کارتِ پنج‌محورِ `GET /api/fundamental/{symbol}`")
    ap.add_argument("--out", default=None,
                    help="پوشهٔ خروجی (پیش‌فرض: testdata/golden)")
    args = ap.parse_args(argv)
    out_dir = os.path.abspath(args.out or OUT)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                                        # noqa: BLE001
        pass

    tmp = tempfile.mkdtemp(prefix="bors-card-golden-")
    try:
        prepare(tmp)
        import api.chart as ch
        import api.fundamental as fd
        import api.market as mk
        import fts_engine as fe
        import codal_periods as cp
        pin_clock(ch, fd, mk, fe, cp)

        commit = git_commit()
        digests = fixture_digests()
        os.makedirs(out_dir, exist_ok=True)
        rows = []
        for name, symbol, months, branch, settings in CASES:
            # پروندهٔ آستانه‌ها پیش از هر کیس پاک می‌شود تا کیسِ بدونِ override
            # پروندهٔ کیسِ قبلی را نداشته باشد.
            write_setting(tmp, SETTINGS_FILE, settings)
            body = call(fd.get_fundamental, symbol, months)
            raw = json_bytes(body)
            case_dir = os.path.join(out_dir, name)
            os.makedirs(case_dir, exist_ok=True)
            write_bytes(os.path.join(case_dir, "body.json"), raw)
            meta = {
                "case": name,
                "symbol": symbol,
                "route": route_of(symbol, months),
                "branch": branch,
                "settings": settings,
                "python": {
                    "module": "api/fundamental.py",
                    "function": "get_fundamental",
                    "args": [symbol, months],
                    "call": "api.fundamental.get_fundamental(symbol, months)",
                },
                "python_commit": commit,
                "fixture": {
                    "dir": "backend-go/internal/fundamental/testdata/fixture",
                    "market_db_sha256": digests["market.db"],
                    "user_db_sha256": digests["user.db"],
                },
                "pinned_today": TODAY.isoformat(),
                "body_file": "body.json",
                "body_sha256": sha256_bytes(raw),
                "body_bytes": len(raw),
                "generated_by": "tools/parity/gen_fundamental_card_golden.py",
            }
            write_bytes(os.path.join(case_dir, "meta.json"), json_bytes(meta))
            rows.append({
                "name": name,
                "symbol": symbol,
                "route": route_of(symbol, months),
                "branch": branch,
                "settings": settings,
                "body": "%s/body.json" % name,
                "meta": "%s/meta.json" % name,
                "sha256": meta["body_sha256"],
                "bytes": meta["body_bytes"],
                "verdict": body.get("verdict"),
                "score": body.get("score"),
                "applicable": body.get("applicable"),
            })
        write_setting(tmp, SETTINGS_FILE, None)

        index = {
            "version": 1,
            "route": "GET /api/fundamental/{symbol}",
            "generated_by": "tools/parity/gen_fundamental_card_golden.py",
            "python_commit": commit,
            "pinned_today": TODAY.isoformat(),
            "fixture": {
                "dir": "backend-go/internal/fundamental/testdata/fixture",
                "market_db_sha256": digests["market.db"],
                "user_db_sha256": digests["user.db"],
            },
            "cases": rows,
            "not_covered": list(NOT_COVERED),
        }
        write_bytes(os.path.join(out_dir, "card_index.json"), json_bytes(index))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("card goldens -> %s" % out_dir)
    for row in rows:
        print("  %-18s %-12s %7d bytes  %s"
              % (row["name"], row["symbol"], row["bytes"], row["sha256"][:16]))
    print("  %d cases, index -> card_index.json" % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
