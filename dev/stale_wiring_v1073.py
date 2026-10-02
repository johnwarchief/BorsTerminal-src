# -*- coding: utf-8 -*-
"""dev/stale_wiring_v1073.py — هر data-sync، کشِ وابسته‌به‌آن داده را هم می‌بَرَد.

چرا این گارد متولد شد (هدفِ ۲، دورۀ audit پیش از FTS). چهار مسیرِ «داده تازه شد ولی
برنامه کهنه جواب داد» با کدِ خودِ فایل و با آزمونِ رفتار بسته شد:

  ۱) کشِ payload اسکرینر TTL ۱۲ ساعته دارد و رویِ دیسک هم می‌نشیند (پس با restart
     هم نمی‌رود)، ولی سینکِ بازار `market_watch.market_cap` را بازنویسی می‌کند و
     ادغامِ snapshot کدال هر سه جدولِ بنیادی را. هیچ‌کدام کشِ اسکرینر را پاک نمی‌کردند
     ⇒ همان شکلِ «عددِ اسکرینر با عددِ کارت می‌جنگد» که برایِ #66 ثبت شد.
  ۲) سه endpoint زیرپروسۀ کدال را با `[sys.executable, "codal_fetcher.py", …]`
     Popen می‌کردند. درِ بیلدِ فریزشده `sys.executable` خودِ EXE است ⇒ دومینِ پنجرۀ
     برنامه بالا می‌آمد (و طبقِ `bors_config:452` یکِ مسیرِ فرعی با connectِ خالی
     market.db را ناقص گذاشته بود). پرچمِ `--codal-worker` هم هیچ‌جا dispatch نشده.
  ۳) سه کشِ `MA_CACHE`/`KEY_LEVELS_CACHE`/`PATTERNS_CACHE` رویِ سریِ **پس ازِ
     price_basis** حساب می‌شوند ولی کلیدشان مبنایِ قیمت نداشت؛ `set_basis` هم هیچ کشی
     را پاک نمی‌کند ⇒ تا ۱۵ دقیقه پس ازِ عوض‌کردنِ setting، MA/سطوح/الگو رویِ مبنایِ
     قبلی می‌ماندند (نقضِ شرطِ ۱ِ §۱-ث).
  ۴) `INDEX_CACHE` سریِ **برش‌خورده با limit** را درِ کش می‌گذاشت؛ اولینِ درخواستِ
     `limit=0` بعد از آن تا TTL سریِ ناقص می‌گرفت. شاخۀ دومِ همان نقص: پاسخِ کش‌شده
     از `price_basis.resolve_payload` رد نمی‌شد، پس درِ همان TTL پاسخِ `priceBasis*`
     ندارد و کندلش حل‌نشده است (شرطِ ۵ِ §۱-ث: هر سری‌دهنده درِ پایانِ کار از همین
     یکِ نقطه می‌گذرد).

بی‌شبکه و بی‌market.dbِ واقعی. اجرا:  python dev/stale_wiring_v1073.py
"""
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = FAIL = 0


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  ✓ {what}")
    else:
        FAIL += 1
        print(f"  ✗ {what}" + (f"   ← {detail}" if detail else ""))


def temp_chart_db(days=120):
    """یکِ بانکِ کوچکِ فقط‌خواندنی‌شده با `price_history` — برایِ مسیرهایِ کشِ چارت.

    `days` باید ≥۶۰ باشد: `get_key_levels` زیرِ ۶۰ روز «تاریخچه کافی نیست» برمی‌گرداند
    و هیچ چیزی درِ `KEY_LEVELS_CACHE` نمی‌نشیند، پس آزمونِ کلیدِ دوبخشیِ آن پوچ می‌شد.
    """
    import datetime
    path = os.path.join(tempfile.mkdtemp(prefix="wiring_"), "t.db")
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE price_history (symbol TEXT, date TEXT, open REAL, high REAL,"
                " low REAL, close REAL, volume REAL, last REAL, value REAL, src TEXT,"
                " PRIMARY KEY (symbol, date))")
    day0 = datetime.date(2026, 1, 1)
    for i in range(days):
        d = (day0 + datetime.timedelta(days=i)).isoformat()
        con.execute("INSERT OR REPLACE INTO price_history VALUES (?,?,?,?,?,?,?,?,?,?)",
                    ("فولاد", d, 100.0 + i, 105.0 + i, 95.0 + i, 102.0 + i, 1e6,
                     103.0 + i if i % 3 else None, 1.06e8, "published"))
    con.commit()
    con.close()
    return path


def main():
    print("— ۱) سینکِ بازار کشِ اسکرینر را باطل و دوباره گرم می‌کند")
    import api._sync_market as SM
    import api.screener as SC
    calls = []
    orig = {"tsetmc": SM._tsetmc_mod.main, "warm_m": SM.warm_market_cache,
            "inv": SC.invalidate_screener_cache, "warm_s": SC.warm_screener_cache}
    SM._tsetmc_mod.main = lambda *a, **k: calls.append("sync")
    SM.warm_market_cache = lambda *a, **k: calls.append("board")
    SC.invalidate_screener_cache = lambda **k: calls.append(("inv", k.get("drop_materialized")))
    SC.warm_screener_cache = lambda *a, **k: calls.append("warm")
    try:
        SM._run_market_sync()
    finally:
        SM._tsetmc_mod.main = orig["tsetmc"]
        SM.warm_market_cache = orig["warm_m"]
        SC.invalidate_screener_cache = orig["inv"]
        SC.warm_screener_cache = orig["warm_s"]
    ck(("inv", False) in calls, "پس ازِ سینک، کشِ اسکرینر باطل می‌شود (بدونِ پاک‌کردن fts_results)", str(calls))
    ck("warm" in calls, "و درِ همان نخ دوباره گرم می‌شود تا کاربر ~۲۷ ثانیه نپردازد", str(calls))

    print("\n— ۲) ادغامِ snapshot کدال هم همین کش را می‌بَرَد")
    import inspect
    import api._sync_codal as SD
    src = inspect.getsource(SD._codal_db_worker) + inspect.getsource(SD)
    ck("invalidate_screener_cache" in src,
       "مسیرِ merge کدال به invalidate_screener_cache می‌رسد", "")
    ck(src.count("drop_materialized=False") >= 1,
       "با drop_materialized=False (درِ EXE هیچ نویسدۀ دیگری برای fts_results نیست)", "")

    print("\n— ۳) درِ بیلدِ فریزشده هیچ زیرپروسۀ خزنده‌ای متولد نمی‌شود")
    import api._core as CORE
    import codal_engine as CE
    real = CORE.codal_crawler_available
    CORE.codal_crawler_available = lambda: False
    SD.codal_crawler_available = lambda: False
    try:
        r1 = SD.sync_codal(mode="update")
        r2 = CE.run_sync_job("full")
        r3 = CE.run_sync_job("watchlist")
    finally:
        CORE.codal_crawler_available = real
        SD.codal_crawler_available = real
    ck(r1.get("status") == "unavailable" and "دیتابیس کدال" in (r1.get("message") or ""),
       "/api/sync/codal در EXE صادقانه رد می‌کند (نه پنجرۀ دوم)", str(r1)[:90])
    ck(r2.get("status") == "unavailable", "run_sync_job(full) در EXE رد می‌کند", str(r2)[:80])
    ck(r3.get("status") == "unavailable", "run_sync_job(watchlist) هم رد می‌کند", str(r3)[:80])

    print("\n— ۴) کلیدِ سه کشِ چارت مبنایِ قیمت را حمل می‌کند")
    import api.chart as CH
    import bors_config
    import price_basis
    db = temp_chart_db()
    orig_db, orig_pb = CH.DB_PATH, bors_config.PRICE_BASIS_PATH
    CH.DB_PATH = db
    bors_config.PRICE_BASIS_PATH = os.path.join(os.path.dirname(db), "pb.json")
    orig_adj = CH._adjust_events_for
    CH._adjust_events_for = lambda symbol, rows: []      # گارد بی‌شبکه بماند
    try:
        CH.MA_CACHE.clear()
        CH.KEY_LEVELS_CACHE.clear()
        CH.PATTERNS_CACHE.clear()
        price_basis.set_basis("last")
        CH.get_ma_events("فولاد", 30)
        CH.get_key_levels("فولاد")
        CH.get_patterns("فولاد")
        price_basis.set_basis("closing")
        CH.get_ma_events("فولاد", 30)
        CH.get_key_levels("فولاد")
        CH.get_patterns("فولاد")
        keys_ma = sorted(CH.MA_CACHE)
        keys_kl = sorted(CH.KEY_LEVELS_CACHE)
        keys_pt = sorted(CH.PATTERNS_CACHE)
        ck(len(keys_ma) == 2 and any("|last" in k for k in keys_ma)
           and any("|closing" in k for k in keys_ma),
           "MA_CACHE برایِ هر مبنای یکِ کلید دارد", str(keys_ma))
        ck(len(keys_kl) == 2 and any("|last" in k for k in keys_kl)
           and any("|closing" in k for k in keys_kl),
           "KEY_LEVELS_CACHE هم مبن را درِ کلید دارد", str(keys_kl))
        ck(len(keys_pt) == 2 and any("|last" in k for k in keys_pt)
           and any("|closing" in k for k in keys_pt),
           "PATTERNS_CACHE هم مبن را درِ کلید دارد", str(keys_pt))
        price_basis.set_basis("last")
        n0 = len(CH.MA_CACHE)
        CH.get_ma_events("فولاد", 30)                      # همین کلید قبلاً ساخته شده
        ck(len(CH.MA_CACHE) == n0, "اجرایِ دومِ همان مبنایِ دوباره محاسبه نمی‌کند", "")
    finally:
        CH._adjust_events_for = orig_adj
        CH.DB_PATH = orig_db
        bors_config.PRICE_BASIS_PATH = orig_pb

    print("\n— ۵) کشِ شاخص با limit مسموم نمی‌شود و مسیرِ hit هم مبن دارد")
    import datetime
    import api.market_index as MI
    day0 = datetime.date(2026, 1, 1)
    raw = [{"dEven": int((day0 + datetime.timedelta(days=i)).strftime("%Y%m%d")),
            "xNivInuClMresIbs": 1600 + i, "xNivInuPhMresIbs": 1610 + i,
            "xNivInuPbMresIbs": 1590 + i}
           for i in range(60)]

    def fake_fetch(ins_code=None, **kw):
        return list(raw)

    MI.fetch_tedpix_series = fake_fetch
    MI.INDEX_CACHE.clear()
    a = MI.build_tedpix_payload("dji", limit=5)
    b = MI.build_tedpix_payload("dji", limit=0)
    ck(len(a["candles"]) == 5 and len(b["candles"]) == 60,
       "اولینِ درخواستِ برش‌خورده سریِ کاملِ دومینِ درخواست را نمی‌بَرَد",
       f"{len(a['candles'])}/{len(b['candles'])}")
    c = MI.build_tedpix_payload("dji", limit=7)
    ck(len(c["candles"]) == 7 and c.get("cached") is True,
       "مسیرِ hit هم با limit درست کار می‌کند", str(c.get("cached")))
    ck(b.get("priceBasis") == c.get("priceBasis") == "closing"
       and c.get("priceBasisLastMissing") == len(c["candles"])
       and b.get("priceBasisLastMissing") == len(b["candles"]),
       "پاسخِ کش‌شده هم از ریزالویِ مبن می‌گذرد (شاخص last ندارد → closing، با اعلام)",
       f"{b.get('priceBasis')}/{c.get('priceBasis')}/{c.get('priceBasisReason')}")
    ck(all(set(x) >= {"closing", "close"} for x in c["candles"]),
       "کندلِ مسیرِ hit هم کندلِ حل‌شده است، نه خامِ دیسک", "")
    ck(MI.INDEX_CACHE["dji"][1]["count"] == 60,
       "درِ خودِ کش سریِ کامل (۶۰) مانده است", str(MI.INDEX_CACHE["dji"][1]["count"]))

    print(f"\nنتیجه: {PASS} سبز، {FAIL} قرمز")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
