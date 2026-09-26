#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/client_type_date_v1034.py — روزِ `client_type` باید روزِ *نشست* باشد (#119).

باگِ اندازه‌گیری‌شده (۱۴۰۵-۰۷-۰۴، تابلوی زنده): TSETMC پیش از بازگشایی هم ردیف
می‌فرستد — با `dEven`ِ روزِ جدید و حجمِ صفر. نویسنده روزِ `client_type` را
«امروزِ ساعتی» می‌گرفت، پس جریانِ پولِ نشستِ پیش زیرِ تاریخِ امروز نوشته می‌شد
و `client_type` برایِ ۲۳/۲۴/۲۵/۲۶ سپتمبر چهار ردیفِ بایت‌به‌بایت یکسان داشت.
نتیجه درِ نبض بازار: حجمِ امروز صفر + پولِ دیروز = دماسنجِ دوروژه و «نامساعد»
جعلی.

ترمیم: `test_tsetmc.session_day_of(watch, fallback)` — روزی که واقعاً در آن
معامله شده. این گارد همان تابع را بی‌بانک می‌آزماید و سه سیم‌کشی را قفل می‌کند
که با یک ویرایشِ بی‌دقت می‌شکنند:

  ۱) هر دو نویسنده (اسنپ‌شاتِ زنده و بارخوانیِ انبوه) از همان تابع می‌گذرند؛
  ۲) `_DP_INSERT` ستونِ `z_tot_tran` را دارد (qd1 درِ فیلترِ کف‌روبی)؛
  ۳) `ensure_daily_tran_column` پیش از هر `_DP_INSERT` صدا زده می‌شود، وگرنه
     رویِ بانکِ قدیمی اولین نوشتن می‌ترکد.

اجرا:  python dev/client_type_date_v1034.py
خروج: ۰ اگر همه درست، ۱ در غیر این صورت.
"""
import datetime as dt
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mstat_engine as ME  # noqa: E402
from test_tsetmc import session_day_of  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYNC = os.path.join(ROOT, "test_tsetmc.py")

PASS = FAIL = 0


def ck(cond, what, got=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {what}")
    else:
        FAIL += 1
        print(f"  FAIL {what}" + (f"  -> {got}" if got else ""))


def watch_row(ins, d_even, vol):
    """تاپلِ market_watch به همان ترتیبِ _MW_INSERT؛ فقط خانهٔ ۱ و ۱۱ مهم‌اند."""
    t = [None] * 20
    t[0], t[1], t[11] = ins, d_even, vol
    return tuple(t)


def main():
    print("\n[۱] روزِ نشست = روزی که در آن معامله شده")
    traded = [watch_row("الف", 14050630, 12_000.0), watch_row("ب", 14050630, 5_000.0)]
    ck(session_day_of(traded) == 14050630, "همه traded → همان روز")

    # پیش از بازگشایی: ردیفِ تازه با حجمِ صفر نباید تاریخ بسازد.
    pre_open = traded + [watch_row("الف", 14050701, 0.0), watch_row("ب", 14050701, None)]
    ck(session_day_of(pre_open) == 14050630,
       "ردیفِ حجم‌صفرِ امروز تاریخِ نشست نمی‌سازد")

    ck(session_day_of([watch_row("پ", 14050701, 0.0)], fallback=14050630) == 14050630,
       "هیچ ردیفِ معامله‌شده‌ای نبود → fallback")
    ck(session_day_of([], fallback=14050630) == 14050630, "تاپلِ خالی → fallback")
    ck(session_day_of([]) == 0, "تاپلِ خالی بدون fallback صفر است، نه None")
    # روزِ معامله‌شده‌یِ قدیمی‌تر از fallback هم معتبر است؛ fallback فقط «نداشتیم»
    ck(session_day_of([watch_row("ت", 14050625, 7.0)], fallback=14050701) == 14050625,
       "fallback جایِ روزِ معامله‌شده را نمی‌گیرد")

    print("\n[۲] سیم‌کشیِ دو نویسنده")
    src = io.open(SYNC, encoding="utf-8").read()
    # هر جای «INSERT OR REPLACE INTO client_type» باید از session_day_of بیاید
    ck(src.count("session_day_of(watch,") == 2,
       "هر دو نویسنده‌یِ client_type از session_day_of می‌گذرند",
       str(src.count("session_day_of(watch,")))
    ck("d_even or today" in src and not re.search(
        r"client = \[\(x\.get\(\"insCode\"\), (today|d_even)\b", src),
       "مستقیم «today» یا «d_even» درِ سطرِ client_type نمی‌نشیند")

    print("\n[۳] qd1 = تعدادِ معاملاتِ نشستِ پیش")
    m = re.search(r"_DP_INSERT = \(\"INSERT OR REPLACE INTO daily_prices \((.*?)\) VALUES",
                  src, re.S)
    cols = [c.strip() for c in m.group(1).replace("\n", " ").split(",")] if m else []
    ck("z_tot_tran" in cols, "daily_prices ستونِ z_tot_tran را در درج می‌گیرد", str(cols))
    ph = re.search(r"_DP_INSERT.*?\"\?\" \* (\d+)", src, re.S)
    ck(bool(ph) and int(ph.group(1)) == len(cols),
       "تعدادِ نشانه‌ها با ستون‌هایِ _DP_INSERT یکی است",
       f"{ph.group(1) if ph else '?'} vs {len(cols)}")
    ck(src.count("ensure_daily_tran_column(conn)") >= src.count("_DP_INSERT, daily"),
       "ALTERِ idempotent پیش از هر نوشتنِ daily_prices اجرا می‌شود")
    # آخرِ هر تاپلِ daily باید trd باشد ( نه فهرستِ ۱۳تاییِ قدیمی)
    ck(len(re.findall(r"mcap_src, trd\)\)", src)) == 2,
       "هر دو `daily.append` با trd بسته می‌شوند", str(len(re.findall(r"mcap_src, trd\)\)", src))))

    print("\n[۴] abstentionِ نبض بازار (هیچ داوری از نبودِ داده ساخته نمی‌شود)")
    import mstat_engine as ME
    h = ME.macro_health_from({"n_traded": 0, "trade_value": 0.0, "market_value": 0.0})
    ck(h.get("state") == "nodata" and h.get("value_hemat") is None,
       "نشستِ بدونِ معامله → «nodata»، نه «نامساعد»", str(h))
    ck("بدون داده" in str(h.get("label") or ""), "برچسبِ فارسیِ همان حالت هم هست", str(h))

    print("\n[۵] تازگیِ تابلو در ساعتِ بازار (#120)")
    # اندازه‌گیریِ همان نشست: برنامه ۰۷:۲۱ اجرا شده بود و تا ۱۰:۲۱ هیچ سینکی
    # نزد — یعنی جز هوکِ استارت و یک دکمهٔ بی‌صدا، هیچ تازگیِ خودکاری نبود.
    app_src = io.open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    ck("def _board_refresh_loop" in app_src and
       "threading.Thread(target=_board_refresh_loop" in app_src,
       "حلقۀِ تازۀ‌سازیِ تابلو درِ app.py ثبت شده است")
    body = app_src.split("def _market_in_session", 1)[-1][:500] if "def _market_in_session" in app_src else ""
    ck("in_trading_session" in body and "SESSION_OPEN_HM <=" not in body,
       "پنجرۀِ بازار یک بار تعریف شده (mstat_engine)، نه دو بار")
    ck("_run_market_sync" in app_src.split("def _board_refresh_loop", 1)[-1][:600],
       "حلقه همان سینکِ آزمودنی را صدا می‌زند، نه نسخۀِ دومِ آن را")
    wed, thu, fri, sat = (dt.datetime(2026, 9, 23, 10, 21, 30), dt.datetime(2026, 9, 24, 10, 21, 30),
                          dt.datetime(2026, 9, 25, 10, 21, 30), dt.datetime(2026, 9, 26, 10, 21, 30))
    hm = lambda t: t.hour * 10000 + t.minute * 100 + t.second  # noqa: E731
    ck(ME.in_trading_session(hm(wed), wed) is True, "چهارشنبه ۱۰:۲۱ → درِ پنجره")
    ck(ME.in_trading_session(hm(thu), thu) is False, "پنجشنبه تعطیل است، حتی وسطِ ساعت")
    ck(ME.in_trading_session(hm(fri), fri) is False, "جمعه تعطیل است")
    ck(ME.in_trading_session(hm(sat), sat) is True,
       "شنبه روزِ کاری است (شرطِ نادرستِ weekday>۲ همین‌جا لو می‌رود)")
    ck(ME.in_trading_session(hm(dt.datetime(2026, 9, 23, 7, 21, 30)), wed) is False,
       "پیش از بازگشایی سینک نمی‌زنیم (ردیف‌هایِ صفرِ پیش‌ازگشایی data نیست)")
    ck(ME.in_trading_session(hm(dt.datetime(2026, 9, 23, 13, 30, 0)), wed) is False,
       "پس از بسته شدن بازار هم نه")

    print(f"\nclient_type_date_v1034: {PASS} passed / {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
