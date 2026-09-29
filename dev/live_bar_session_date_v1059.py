#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/live_bar_session_date_v1059.py — کندلِ زنده باید تاریخِ *خودِ جلسه* را داشته باشد.

چرا این گارد متولد شد (LIVE-BAR-1، ۱۴۰۵-۰۷-۰۸؛ گزارشِ مالک رویِ نمادِ فولاد):

مالک دید عددِ کندل بی‌هیچ معاملاتی عوض می‌شود («۴۰۵ بود، شد ۴۰۴»). اندازه‌گیریِ
همانِ لحظه رویِ اپِ نصبی دو علتِ عینی نشان داد:

۱) **کندلِ شبح.** `get_chart_db` کندلِ زنده را با `datetime.date.today()`
   می‌ساخت و تاریخِ `market_watch.d_even` را هرگز نمی‌خواند. بامداد، پیش از
   بازگشایی، ردیفِ تابلو هنوز نشستِ **دیروز** بود (فولاد: d_even=20260928،
   p_closing=3420)، ولی کندلی به نامِ «۲۰۲۶-۰۹-۲۹» با O=H=L=C=3420 و حجمِ صفر
   به سری چسبید — درست کنارِ کندلِ واقعیِ ۰۹-۲۸ با همان پایانی. آن کندل هم
   مقیاسِ عمودی را جابه‌جا می‌کند و هم سطل‌هایِ تجمیعِ هفتگی را یک‌خانه
   می‌کِشَد، پس «کندلِ پنجم» دو عددِ متفاوت می‌شد.

۲) **دو منبع، دو آخرین‌کندل.** تزریقِ کندلِ زنده فقط در `/api/chart-db` بود؛
   `/api/chart` (مسیرِ اصلیِ چارت) نداشتش. پس همان نماد در دو اندپوینت دو
   انتهاىِ متفاوت داشت و هر فال‌بکی که بینِ آن‌ها جابه‌جا می‌شد، نمودار را
   تغییر می‌داد. ترمیم: یک هلپرِ مشترک که هر دو مسیر از آن می‌گذرند.

ترمیم‌ها:
  • تاریخِ کندل از d_even خوانده می‌شود؛ فقط نشستی که از آخرین کندل **تازه‌تر**
    است تزریق می‌شود (برابر = آن روز در تاریخچه هست و دست‌نخورده می‌ماند).
  • `_attach_live_bar` همان کندل را به پاسخِ `/api/chart` هم می‌چسباند — رویِ
    نسخه، تا شیءِ کش‌شده با کندلِ نیم‌کارِ یک ساعت قفل نشود.
  • اگر همان فال‌بک نشان دهد که نشستِ جاری در `price_history` نیست، تاریخچۀ
    *همان یک نماد* در پس‌زمینه تازه می‌شود (سقفِ ۱۵ دقیقه برای هر نماد، از راهِ
    `fetch_price_history` که خودش min_interval و سقفِ ۴۲۹ دارد) — رأیِ پایلوت:
    selfheal با اطمینانِ ۰٫۸۳ و ریسکِ ۰٫۸، پس هر سه قیدِ بالا در گارد می‌آیند.

گارد بی‌شبکه و بی‌market.dbِ واقعی اجرا می‌شود (دیتابیسِ موقتِ کوچک + هر دو
منبعِ داده جعل).  اجرا:  python dev/live_bar_session_date_v1059.py
خروج: ۰ اگر همه درست، ۱ در غیر این صورت.
"""
import io
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.chart as ch  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHART_PY = os.path.join(ROOT, "api", "chart.py")

PASS = FAIL = 0


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  ok   %s" % what)
    else:
        FAIL += 1
        print("  FAIL %s%s" % (what, ("  ← " + detail) if detail else ""))


def mini_db(rows):
    """DBِ موقتِ کوچک: (ins_code, l_val18, d_even, first, max, min, close, last, vol).

    فقط ستون‌هایی که `_watch_live_bar` می‌خواند ساخته می‌شوند — اسکیمایِ کاملِ
    market.db در CI نیست و نباید لازم باشد.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE instruments (ins_code TEXT, l_val18 TEXT, l_val30 TEXT)")
    conn.execute("CREATE TABLE market_watch (ins_code TEXT, d_even INTEGER, price_first REAL,"
                 " price_max REAL, price_min REAL, p_closing REAL, p_last REAL, q_tot_tran REAL)")
    for ins, sym, d_even, first, hi, lo, close, last, vol in rows:
        conn.execute("INSERT INTO instruments VALUES (?,?,?)", (ins, sym, sym))
        conn.execute("INSERT INTO market_watch VALUES (?,?,?,?,?,?,?,?)",
                     (ins, d_even, first, hi, lo, close, last, vol))
    conn.commit()
    conn.close()
    return path


ONE_SESSION = [("A1", "فولاد", 20260928, 3410.0, 3420.0, 3380.0, 3420.0, 3350.0, 1834250671.0)]


def main():
    print("live_bar_session_date_v1059")

    # ── ۱) تبدیلِ d_even ──────────────────────────────────────────────────
    print("\n[۱] تاریخِ جلسه")
    ck(ch._d_even_to_date(20260928) == "2026-09-28", "an int d_even becomes an ISO date")
    ck(ch._d_even_to_date("20260928") == "2026-09-28", "a string d_even works too")
    ck(ch._d_even_to_date(0) is None and ch._d_even_to_date(None) is None,
       "a missing/zero d_even is no date, not 0000-00-00")
    ck(ch._d_even_to_date(202609) is None, "a short d_even is refused")

    original_db = ch.DB_PATH
    try:
        # ── ۲) تزریقِ درست و کنترلِ منفیِ کندلِ شبح ───────────────────────
        print("\n[۲] کندلِ زنده از market_watch")
        ch.DB_PATH = mini_db(ONE_SESSION)
        bar, err = ch._watch_live_bar("فولاد", "2026-09-26")
        ck(err is None, "a healthy watch row raises no error", str(err))
        ck(bar and bar["time"] == "2026-09-28",
           "the bar carries the session's own date, not the system clock", str(bar))
        ck(bar and (bar["open"], bar["high"], bar["low"], bar["close"]) ==
           (3410.0, 3420.0, 3380.0, 3420.0), "OHLC comes from the session fields", str(bar))
        ck(bar and bar["volume"] == 1834250671.0, "volume is the session's traded count", str(bar))
        ck(bar and bar["last"] == 3350.0, "«آخرین معامله» from p_last", str(bar))

        ghost, _ = ch._watch_live_bar("فولاد", "2026-09-28")
        ck(ghost is None,
           "NEGATIVE CONTROL: a session already present in the history is not appended again")

        # ساعتِ سیستم را یک روز جلو می‌بریم؛ اگر کد هنوز date.today() می‌ساخت،
        # همین تست قرمز می‌شود.
        future, _ = ch._watch_live_bar("فولاد", "2024-08-24")
        ck(future and future["time"] == "2026-09-28",
           "an old history still gets the real session day, never «today»", str(future))

        nomatch, err2 = ch._watch_live_bar("ناموجود", "2020-01-01")
        ck(nomatch is None and err2 is None, "an unknown symbol yields no bar and no error")

        ch.DB_PATH = mini_db([("A2", "خساپا", 20260928, 100.0, 110.0, 90.0, None, None, None)])
        noclose, _ = ch._watch_live_bar("خساپا", "2026-09-20")
        ck(noclose is None, "a watch row without a closing price is not a candle")

        ch.DB_PATH = mini_db([("A3", "شپنا", 20260928, 0.0, 0.0, 0.0, 500.0, 0.0, 12000.0)])
        flat, _ = ch._watch_live_bar("شپنا", "2026-09-27")
        ck(flat and flat["open"] == 500.0 and flat["high"] == 500.0 and flat["low"] == 500.0
           and flat["last"] == 500.0,
           "a mid-session row with empty wicks degrades to a flat bar of its close", str(flat))

        # پیش از بازگشایی تابلو «پایانی» را با قیمتِ پایه پر می‌کند؛ حجمِ صفر یعنی
        # هنوز معامله‌ای نبوده، پس کندلی هم نیست (اثباتِ زندهٔ اپِ نصبی ۰۷:۵۰).
        ch.DB_PATH = mini_db([("A4", "فولاد", 20260929, 3420.0, 3420.0, 3420.0, 3420.0,
                               3420.0, 0.0)])
        preopen, _ = ch._watch_live_bar("فولاد", "2026-09-28")
        ck(preopen is None,
           "NEGATIVE CONTROL: an untouched session (zero volume) never becomes a candle")
        ch.DB_PATH = mini_db([("A5", "فولاد", 20260929, 3420.0, 3450.0, 3400.0, 3430.0,
                               3440.0, 500000.0)])
        opened, _ = ch._watch_live_bar("فولاد", "2026-09-28")
        ck(opened and opened["time"] == "2026-09-29" and opened["volume"] == 500000.0,
           "the same session the moment it trades does become a candle", str(opened))

        ch.DB_PATH = os.path.join(tempfile.gettempdir(), "definitely-not-here-v1059.db")
        broken_bar, broken_err = ch._watch_live_bar("فولاد", "2020-01-01")
        ck(broken_bar is None and broken_err,
           "a broken DB is reported in liveError instead of being swallowed", str(broken_err))
    finally:
        ch.DB_PATH = original_db

    # ── ۳) چسباندنِ کندلِ زنده به پاسخِ /api/chart ────────────────────────
    print("\n[۳] مسیرِ CDN هم کندلِ زنده می‌گیرد")
    base = {"status": "success",
            "candles": [{"time": "2026-09-28", "open": 3410.0, "high": 3420.0,
                         "low": 3380.0, "close": 3420.0},
                        {"time": "2026-09-27", "open": 3220.0, "high": 3350.0,
                         "low": 3220.0, "close": 3330.0}],
            "volumes": [{"time": "2026-09-28", "value": 1.0, "color": "#10b981"},
                        {"time": "2026-09-27", "value": 2.0, "color": "#f43f5e"}],
            "factors": [{"time": "2026-09-28", "factor": 1.0},
                        {"time": "2026-09-27", "factor": 0.9}],
            "count": 2}
    frozen = dict(base, candles=[dict(base["candles"][0], time="2026-09-29", open=3420.0,
                                      high=3420.0, low=3420.0, close=3420.0,
                                      volume=0.0, last=3420.0)])

    original_wlb = ch._watch_live_bar
    try:
        ch._watch_live_bar = lambda sym, after: (dict(frozen["candles"][0]), None)
        out = ch._attach_live_bar("فولاد", base)
        ck(out["candles"][0]["time"] == "2026-09-29", "the live bar leads the (descending) series")
        ck(out["count"] == 3 and len(out["candles"]) == 3, "count follows the served candles",
           str(out["count"]))
        ck([v["time"] for v in out["volumes"]] == [c["time"] for c in out["candles"]],
           "one volume bar per candle — klinecharts joins them by time")
        ck([f["time"] for f in out["factors"]] == [c["time"] for c in out["candles"]],
           "factors stay parallel to candles")
        ck(out["factors"][0]["factor"] == 1.0, "the newest candle stays raw (factor 1)")
        ck(out["liveInjected"] is True, "the response says a live bar was added")
        ck(len(base["candles"]) == 2 and "liveInjected" not in base,
           "the cached object was not mutated — a half-day bar cannot freeze for an hour")

        asc = {"status": "success",
               "candles": list(reversed(base["candles"])),      # صعودی = مسیرِ محلی
               "volumes": list(reversed(base["volumes"])),
               "factors": list(reversed(base["factors"])),
               "count": 2}
        a_out = ch._attach_live_bar("فولاد", asc)
        ck(a_out["candles"][-1]["time"] == "2026-09-29",
           "an ascending series grows at its own end, not at index 0")
        ck([v["time"] for v in a_out["volumes"]] == [c["time"] for c in a_out["candles"]],
           "volumes stay aligned in the ascending order too")

        ch._watch_live_bar = lambda sym, after: (None, None)
        same = ch._attach_live_bar("فولاد", base)
        ck(same["candles"] == base["candles"] and "liveInjected" not in same,
           "NEGATIVE CONTROL: no session newer than the history → series untouched")

        ch._watch_live_bar = lambda sym, after: (None, "OperationalError: locked")
        witherr = ch._attach_live_bar("فولاد", base)
        ck(witherr.get("liveError") == "OperationalError: locked",
           "the injection failure is reported, not silent")
        ck(witherr["candles"] == base["candles"], "a failed injection never breaks the series")

        ck(ch._attach_live_bar("خالی", {"status": "error", "message": "x"})["status"] == "error",
           "an empty/error response passes through untouched")
    finally:
        ch._watch_live_bar = original_wlb

    # ── ۴) شکافِ تاریخچه: فقط نمادِ همان شکاف، فقط هر ۱۵ دقیقه ─────────────
    print("\n[۴] خودتازۀ تاریخچه")
    ck(ch.HISTORY_REPAIR_MIN_GAP >= 300.0,
       "the repair has a floor gap — a CDN blip cannot become a request storm",
       str(ch.HISTORY_REPAIR_MIN_GAP))
    saved = dict(ch._HISTORY_REPAIR_AT)
    try:
        ch._HISTORY_REPAIR_AT.clear()
        ck(ch._history_repair_due("2026-09-26", "2026-09-28", "فولاد"),
           "a local series that has not reached the target day is worth a fetch")
        ck(not ch._history_repair_due("2026-09-28", "2026-09-28", "فولاد"),
           "NEGATIVE CONTROL: a history that is current fetches nothing")
        ck(not ch._history_repair_due("2026-09-28", "", "فولاد"),
           "no target day → nothing to compare against → no request")
        ch._HISTORY_REPAIR_AT["فولاد"] = 1000.0
        ck(not ch._history_repair_due("2026-09-26", "2026-09-28", "فولاد", now=1000.0 + 60.0),
           "a second blip inside the window does not re-issue the request")
        ck(ch._history_repair_due("2026-09-26", "2026-09-28", "فولاد",
                                  now=1000.0 + ch.HISTORY_REPAIR_MIN_GAP),
           "after the window the same symbol may be refreshed again")
        ch._HISTORY_REPAIR_AT.clear()
        ch._HISTORY_REPAIR_AT["خساپا"] = 1000.0
        ck(ch._history_repair_due("2026-09-26", "2026-09-28", "فولاد", now=1050.0),
           "a throttle stamp on another symbol never blocks this one")
        ck(not ch._history_repair_due("2026-09-26", "2026-09-28", "خساپا", now=1050.0),
           "…and the stamped symbol stays throttled")
        ck(not ch._schedule_history_repair("فولاد", "2026-09-26", ""),
           "a refused schedule never touches the stamp map",
           str(ch._HISTORY_REPAIR_AT.get("فولاد")))
    finally:
        ch._HISTORY_REPAIR_AT.clear()
        ch._HISTORY_REPAIR_AT.update(saved)

    # ── ۵) سیم‌کشی: هر دو مسیر از یک هلپر، و هیچ today‌ای در کار نیست ──────
    print("\n[۵] سیم‌کشی")
    src = io.open(CHART_PY, encoding="utf-8").read()
    ck('today = datetime.date.today()' not in src and '"time": today' not in src,
       "no candle is ever stamped with the system clock again")
    ck(src.count("_watch_live_bar(") >= 3,
       "both chart routes reach the live bar through the one helper",
       str(src.count("_watch_live_bar(")))
    ck("_attach_live_bar(symbol, _cached[1])" in src and
       "_attach_live_bar(symbol, result)" in src,
       "the CDN path injects on both the cache hit and a fresh fetch")
    ck('"degraded": True' in src, "a local-fallback response is marked as degraded")
    ck('"historyRepairScheduled": ' in src or "res[\"historyRepairScheduled\"]" in src,
       "the fallback says whether it scheduled a refresh")
    ck("test_tsetmc.fetch_price_history(symbol)" in src,
       "the refresh reuses the polite fetcher (min_interval + 429 ceiling), not a new one")
    spec = io.open(os.path.join(ROOT, "bors_setup.spec"), encoding="utf-8").read()
    ck("'test_tsetmc'" in spec,
       "test_tsetmc stays in hiddenimports — the EXE must be able to import it at runtime")

    print("\nlive_bar_session_date_v1059: %d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
