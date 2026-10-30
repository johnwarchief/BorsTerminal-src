#!/usr/bin/env python
"""اوراکلِ طلاییِ B2: بدنۀ واقعیِ پایتونِ پنل‌ها رویِ فیکسچر، برایِ تستِ Go.

ساعت تزریق می‌شود: تنها ورودیِ دیواریِ پنل‌ها `market_phase.from_db` است؛
`clock_now` هم در طلایی ثابت می‌ماند تا تستِ Go با همان لحظه بسنجد.
خروجی: backend-go/internal/mstat/testdata/golden/<scenario>/<route>.json

دو نکتهٔ اجرایی که در گارد هم سنجیده می‌شوند:
• `DB_PATH` در `bors_config` یک بار و در import حل می‌شود؛ پس یک پوشۀ داده برایِ
  کلِ اجرا ساخته می‌شود و هر صحنه محتوای همان فایل‌ها را از فیکسچر تازه می‌کند
  (پوشۀ تازه به‌ازایِ هر صحنه، مسیرِ bind‌شده را به پوشۀ حذف‌شده می‌برد).
• توابعِ مسیر با آرگومان‌هایِ صریح صدا زده می‌شوند: پیش‌فرضِ آن‌ها `Query(...)`
  است و فراخوانِ مستقیم (بی‌FastAPI) همان شیء را داخلِ بدنه می‌نشاند.
"""
import datetime
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
FIX = os.path.join(ROOT, "backend-go", "internal", "mstat", "testdata", "fixture")
OUT = os.path.join(ROOT, "backend-go", "internal", "mstat", "testdata", "golden")
PIN = datetime.datetime(2026, 10, 28, 10, 30, 0)   # چهارشنبه، ۱۰:۳۰ تهران

# پیش‌فرض‌هایِ همان مسیرهایِ `/api/mstat/mainwatch` (api/market_status.py).
MAINWATCH_DEFAULTS = {"group": "eq_all", "industry": "", "sort": "clock",
                      "desc": True, "limit": 120}


class _Date(datetime.date):
    @classmethod
    def today(cls):
        return cls(PIN.year, PIN.month, PIN.day)


class _DateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return PIN


class _DT:
    date, datetime, time, timedelta = _Date, _DateTime, datetime.time, datetime.timedelta


_DATA_DIR = None


def data_dir() -> str:
    """پوشۀ دادهٔ مشترکِ کلِ اجرا — یک بار، پیش از نخستین importِ bors_config."""
    global _DATA_DIR
    if _DATA_DIR is None:
        _DATA_DIR = tempfile.mkdtemp(prefix="bors-b2-golden-")
        os.environ["BORS_DATA_DIR"] = _DATA_DIR
        os.environ["BORS_NO_FETCH_LOOPS"] = "1"
        os.environ["BORS_CODAL_OFFLINE"] = "1"
        os.environ["BORS_CODAL_AUTO"] = "0"
    return _DATA_DIR


def assert_seam(tmp):
    """درزِ داده باید به پوشۀ موقت بسته باشد — نه به market.dbِ عملیاتیِ ریشه.

    `bors_config.DB_PATH` یک بار و در import حل می‌شود؛ هر importی که پیش از
    تنظیمِ BORS_DATA_DIR رخ بدهد، اوراکل را (بی‌صدا) رویِ بانکِ واقعی می‌نشاند.
    این بررسی همان اشتباه را پرصدا می‌کند.
    """
    import bors_config
    got = os.path.abspath(bors_config.DB_PATH)
    want = os.path.join(os.path.abspath(tmp), "market.db")
    if os.path.normcase(got) != os.path.normcase(want):
        raise RuntimeError("fixture seam broken: DB_PATH=%r, want %r" % (got, want))


def _restore(src, dst):
    """فیکسچر را رویِ فایلِ مقصد می‌نشاند، با پاک‌کردنِ بازماندۀ WAL."""
    for p in (dst, dst + "-wal", dst + "-shm"):
        try:
            os.remove(p)
        except OSError:
            pass
    shutil.copy2(src, dst)


def scenario(name, sql=(), only=None):
    """کپیِ فیکسچر + تغییراتِ صحنه، سپس بدنه‌هایِ پایتون.

    `only` فهرستِ ساقهٔ فایل‌هایی است که این صحنه لازم دارد؛ None یعنی همهٔ
    هفده پنل. صحنه‌هایِ غیرِ پایه فقط همان پنلی را می‌سازند که رفتارشان را
    می‌سنجد (۱۷ فایلِ یکسان در هر پوشه، طلایی نیست؛ تکرار است).
    """
    tmp = data_dir()
    for f in ("market.db", "user.db"):
        _restore(os.path.join(FIX, f), os.path.join(tmp, f))
    import sqlite3
    con = sqlite3.connect(os.path.join(tmp, "market.db"))
    for stmt, args in sql:
        con.execute(stmt, args)
    con.commit()
    con.close()

    import market_phase as MP
    MP.datetime = _DT
    import api.market_status as MS
    assert_seam(tmp)
    MS._MSTAT_CACHE.clear()
    # کشِ تابلو هم بسته به پوشۀ دادهٔ همان صحنه است؛ کهنه‌اش بماند، پرچم‌هایِ
    # mainwatch از بانکِ صحنۀ قبل می‌آیند.
    try:
        import api.market as MK
        MK._market_clear()
    except Exception:
        pass
    d = os.path.join(OUT, name)
    if os.path.isdir(d):
        shutil.rmtree(d)          # خروجیِ تولیدشده؛ پاک و از نو، بی‌بازماندۀ صحنهٔ قبل
    os.makedirs(d, exist_ok=True)

    def save(fname, obj):
        with open(os.path.join(d, fname), "w", encoding="utf-8", newline="\n") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        print(name, fname, len(json.dumps(obj, ensure_ascii=False)), "chars")

    panels = [("summary", lambda: MS.mstat_summary())]
    for g in ("all", "eq_all"):
        panels.append(("histogram_%s" % g, lambda g=g: MS.mstat_histogram(group=g)))
        panels.append(("thermometer_%s" % g, lambda g=g: MS.mstat_thermometer(group=g)))
        panels.append(("depth_%s" % g, lambda g=g: MS.mstat_depth(group=g)))
    for tab in ("all", "fixed"):
        panels.append(("clientsplit_%s" % tab, lambda tab=tab: MS.mstat_clientsplit(tab=tab)))
    panels.append(("market_snapshot", lambda: MS.mstat_market_snapshot()))
    panels.append(("phase", lambda: MS.mstat_phase()))
    panels.append(("industries", lambda: MS.mstat_industries()))
    for mode in ("cum", "inst"):
        panels.append(("timeline_%s" % mode, lambda mode=mode: MS.mstat_timeline(mode=mode)))
    panels.append(("phases", lambda: MS.mstat_phases()))
    panels.append(("mainwatch_default", lambda: MS.mstat_mainwatch(**MAINWATCH_DEFAULTS)))
    panels.append(("mainwatch_val", lambda: MS.mstat_mainwatch(
        **dict(MAINWATCH_DEFAULTS, sort="val", desc=False, limit=5))))
    for stem, fn in panels:
        if only is not None and stem not in only:
            continue
        save(stem + ".json", fn())


def main() -> int:
    import importlib
    # پیش از هر importِ اپ: پوشۀ داده باید بسته باشد (بندِ assert_seam).
    data_dir()
    # پرچم‌هایِ تابلو نباید به پروبِ زندۀ فرآیندِ همین ماشین وابسته باشند.
    # (همان کاری که اوراکلِ B1 هم می‌کند؛ بی‌آن، طلایی رویِ ماشینی که سینکر
    # بالا دارد با ماشینِ CI یکی نیست.)
    import api.market as MK
    MK._market_running = lambda: False
    # صحنهٔ ۱: پایه.
    scenario("s1")
    # صحنهٔ ۲: تایم‌لاینِ کهنه — نقطه‌هایِ mstat_snap از دیروز. روز در دو جا
    # نشسته است: ستونِ d_even و داخلِ agg؛ `_points` روزِ داخلِ agg را ترجیح
    # می‌دهد، پس فقط ستون را جابه‌جا کردن، «کهنه» نمی‌سازد.
    importlib.reload(__import__("api.market_status", fromlist=["x"]))
    scenario("s2", [("UPDATE mstat_snap SET d_even = d_even - 1,"
                     " agg = json_set(agg, '$.d_even', d_even - 1)", ())],
             only={"timeline_cum", "phases"})
    # صحنهٔ ۳: بی‌وضعیتِ رسمی — phase از تقویم می‌آید و «نامشخص» می‌شود.
    scenario("s3", [("UPDATE market_index SET market_state=NULL,"
                     " market_state_title=NULL", ())], only={"phase"})
    # صحنهٔ ۴: تعطیلی — فعالیت رویِ جمعه اعلام شده.
    scenario("s4", [("UPDATE market_index SET d_even=20261016,"
                     " activity_h_even=123000", ())], only={"phase"})
    if _DATA_DIR:
        shutil.rmtree(_DATA_DIR, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
