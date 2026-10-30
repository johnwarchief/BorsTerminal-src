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

# همان ۱۱ ستونی که `_row_keys(False)` حذف می‌کند — تنها تعریفِ فهرست.
DEPTH_COLS = ("buy_q_vol", "buy_q_val", "buy_q_cnt", "sell_q_vol", "sell_q_val",
              "sell_q_cnt", "buy_q1_vol", "buy_q1_px", "sell_q1_vol",
              "sell_q1_px", "buy_q1_cnt")


def enrich_rows(erows):
    """ردیف‌هایِ دامپِ enrich — همان فیلدهایی که تستِ Go ردیف‌به‌ردیف می‌سنجد.

    `p_first`/`p_min`/`p_max`/`price_change`/`total_shares`/`h_even` در `m`
    نمی‌آیند؛ بی‌آن‌ها، جابه‌جاییِ موقعیتیِ همین ستون‌ها در SQLِ Go بی‌صدا سبز
    می‌شد. ترتیبِ ردیف‌ها هم همان ترتیبِ خروجیِ کوئری است و تست آن را می‌سنجد.
    """
    return [{"ins_code": r["ins_code"], "symbol": r["symbol"], "cls": r["cls"],
             "kind": r["kind"], "pct": r["pct"], "clock_pct": r["clock_pct"],
             "p_first": r.get("p_first"), "p_min": r.get("p_min"),
             "p_max": r.get("p_max"), "price_change": r.get("price_change"),
             "total_shares": r.get("total_shares"), "h_even": r.get("h_even"),
             "top50": r["_top50"], "m": dict(r["_m"])} for r in erows]


def drop_depth(con):
    """`market_watch` را بدونِ ستون‌هایِ عمق بازمی‌سازد (بانکِ همگام‌نشده).

    CTAS به‌جایِ `ALTER TABLE DROP COLUMN` تا SQLiteهایِ کهن هم همان جدول را
    بدهند؛ ترتیبِ ردیف‌ها (rowid) حفظ می‌شود و همان چیزی است که تستِ Go هم
    می‌سازد.
    """
    cols = [r[1] for r in con.execute("PRAGMA table_info(market_watch)")
            if r[1] not in DEPTH_COLS]
    con.execute("CREATE TABLE market_watch_nodepth AS SELECT %s FROM market_watch"
                % ", ".join(cols))
    con.execute("DROP TABLE market_watch")
    con.execute("ALTER TABLE market_watch_nodepth RENAME TO market_watch")
    con.commit()


class _DateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return PIN


class _DT:
    date, datetime, time, timedelta = datetime.date, _DateTime, datetime.time, datetime.timedelta


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
    """درزِ داده باید به پوشۀ موقت بسته باشد — نه به بانکِ عملیاتیِ ریشه.

    هر سه مسیرِ نوشتنیِ `bors_config` یک بار و در import حل می‌شوند؛ هر importی
    که پیش از تنظیمِ BORS_DATA_DIR رخ بدهد، اوراکل را (بی‌صدا) رویِ دادۀ واقعی
    می‌نشاند. `DB_PATH` به بازار، `USER_DB_PATH` به دفترچۀ کاربر و `WORK_DIR` به
    پوشۀ داده/وضعیت اشاره می‌کند؛ سنجشِ فقط `DB_PATH` دو مسیرِ دیگر را باز
    می‌گذاشت. این بررسی همان اشتباه را پرصدا می‌کند.
    """
    import bors_config
    tmp = os.path.abspath(tmp)
    want = {"DB_PATH": os.path.join(tmp, "market.db"),
            "USER_DB_PATH": os.path.join(tmp, "user.db"),
            "WORK_DIR": tmp}
    for attr, expected in sorted(want.items()):
        got = os.path.abspath(getattr(bors_config, attr))
        if os.path.normcase(got) != os.path.normcase(expected):
            raise RuntimeError("fixture seam broken: %s=%r, want %r"
                               % (attr, got, expected))


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
    # mainwatch از بانکِ صحنۀ قبل می‌آیند. استثنا را نمی‌بلعیم: اگر نامِ تابع
    # عوض شود، باید پرصدا بشکند، نه اینکه کشِ صحنهٔ قبل بی‌صدا بماند.
    import api.market as MK
    MK._market_clear()
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

    # دامپِ موتور برایِ تستِ Go: `load_snapshot` + `money` ردیف‌به‌ردیف.
    # این بدنهٔ یک مسیرِ HTTP نیست (status ندارد)؛ فقط صحنهٔ پایه آن را دارد،
    # چون فیکسچرِ ورودیِ همان تست، فیکسچرِ دست‌نخوردهٔ s1 است.
    if only is None:
        import mstat_engine as ME
        con2 = sqlite3.connect(os.path.join(tmp, "market.db"))
        try:
            erows, emeta = ME.enrich(con2)
        finally:
            con2.close()
        save("enrich.json", {"asof": emeta, "rows": enrich_rows(erows)})
        # صحنهٔ بی‌عمق: بانکِ همگام‌نشده هنوز ستون‌هایِ صف را ندارد و پایتون آن
        # را «بی‌داده» می‌خواند، نه صفر. کپیِ موقتِ همین صحنه — هرگز بانکِ
        # عملیاتیِ ریشه یا پوشهٔ فیکسچرِ ردیابی‌شده.
        nodepth = os.path.join(tmp, "market_nodepth.db")
        shutil.copy2(os.path.join(tmp, "market.db"), nodepth)
        con3 = sqlite3.connect(nodepth)
        try:
            drop_depth(con3)
            nrows, nmeta = ME.enrich(con3)
        finally:
            con3.close()
        os.remove(nodepth)
        save("enrich_nodepth.json", {"asof": nmeta,
                                     "rows": enrich_rows(nrows)})


def main() -> int:
    import importlib
    # پیش از هر importِ اپ: پوشۀ داده باید بسته باشد (بندِ assert_seam).
    data_dir()
    assert_seam(data_dir())
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
    # صحنهٔ ۴: تعطیلی — فعالیت رویِ جمعه اعلام شده. فقط ردیفِ تازه‌ترین نشست
    # جابه‌جا می‌شود؛ بی‌`WHERE`، ردیفِ قبلی هم به همان کلید می‌رسید و
    # PRIMARY KEY می‌شکست.
    scenario("s4", [("UPDATE market_index SET d_even=20261016,"
                     " activity_h_even=123000 WHERE d_even=20261014", ())],
             only={"phase"})
    if _DATA_DIR:
        shutil.rmtree(_DATA_DIR, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
