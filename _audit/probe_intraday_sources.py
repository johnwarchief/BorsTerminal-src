# -*- coding: utf-8 -*-
"""_audit/probe_intraday_sources.py — شکارِ منبعِ دقیقه‌ای، بی‌احیایِ مسیرهایِ مرده

مرجعِ دورِ پیش (`docs/fts-notes/LIVE_HOT_STATE.md` §۸) ده مسیرِ tsev2/MarketData را
آزمود و همه مردد شدند (۴۰۴ یا HTMLِ ۸۲۴ بایتیِ ضدربات). آن‌ها اینجا **دوباره
نمی‌آیند**. این اسکریپت فقط اعضایِ همان خانوادۀ `cdn.tsetmc.com/api` را که هنوز
آزموده نشده‌اند می‌زند — همان میزبانی که `GetClosingPriceDailyListCSV` از آن
می‌آید و درِ تولید کار می‌کند (api/chart.py:405).

خروجی برایِ هر نامزد: کدِ وضعیت، نوعِ محتوا، اندازه، و نخستینِ ۱۲۰ بایت. «داده»
فقط وقتی اعلام می‌شود که بدنه JSON/CSV باشد و رشته‌ایِ زمان‌دارِ دقیقه‌ای
(`1405/… 09:…` یا `time`/`date` با ساعت) در آن دیده شود — نه هر پاسخِ ۲۰۰.
"""
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402

DB = os.environ.get("PROBE_DB", "market.db")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Referer": "https://www.tsetmc.com/", "Accept": "application/json"}


def ins_code():
    try:
        import sqlite3
        c = sqlite3.connect(f"file:{DB.replace(os.sep, '/')}?mode=ro", uri=True)
        r = c.execute("SELECT ins_code FROM market_watch ORDER BY q_tot_cap DESC LIMIT 1").fetchone()
        c.close()
        if r:
            return r[0]
    except Exception as e:
        print("ins_code از بانک نیامد:", str(e)[:80])
    import sqlite3
    c = sqlite3.connect(DB)
    r = c.execute("SELECT ins_code FROM market_watch ORDER BY q_tot_cap DESC LIMIT 1").fetchone()
    c.close()
    return r[0]


def main():
    code = ins_code()
    today = dt.datetime.now().strftime("%Y%m%d")
    yester = (dt.datetime.now() - dt.timedelta(days=1)).strftime("%Y%m%d")
    cand = [
        ("Trades/GetInstrumentTradesWithDate", f"https://cdn.tsetmc.com/api/Trades/GetInstrumentTradesWithDate?insCode={code}&date={today}"),
        ("Trades/GetInstrumentTradesWithDate(دیروز)", f"https://cdn.tsetmc.com/api/Trades/GetInstrumentTradesWithDate?insCode={code}&date={yester}"),
        ("Trades/GetInstrumentTradesLastNUpdate", f"https://cdn.tsetmc.com/api/Trades/GetInstrumentTradesLastNUpdate?insCode={code}"),
        ("Trades/GetInstrumentTradesWithDate(مسیرِ path)", f"https://cdn.tsetmc.com/api/Trades/GetInstrumentTradesWithDate/{code}/{today}"),
        ("Chart/GetChartV2", f"https://cdn.tsetmc.com/api/Chart/GetChartV2?insCode={code}&tf=1&dateFrom={yester}&dateTo={today}"),
        ("Chart/GetChartData", f"https://cdn.tsetmc.com/api/Chart/GetChartData?iCode={code}&days=60"),
        ("MarketData/GetMarketDataTwo?method=PostMarketData", "https://cdn.tsetmc.com/api/MarketData/GetMarketDataTwo?method=PostMarketData"),
        ("ClosingPrice/GetClosingPriceDailyListCSV(مراجعه به api/History)", f"https://cdn.tsetmc.com/api/History/GetInstrumentHistory?insCode={code}"),
        ("StaticData/GetInstrumentStatic", f"https://cdn.tsetmc.com/api/StaticData/GetInstrumentStatic?insCode={code}"),
    ]
    print(f"ins_code={code}  today={today}\n")
    alive = []
    for name, url in cand:
        try:
            r = requests.get(url, headers=HDRS, timeout=45)
            body = r.content or b""
            ct = r.headers.get("content-type", "?")
            txt = body[:400].decode("utf-8", "replace")
            minutes = bool(re.search(r"\d{2}:\d{2}", txt)) or '"time"' in txt or "date" in txt.lower()
            looks_data = r.status_code == 200 and len(body) > 900 and (
                "json" in ct or "csv" in ct or txt.lstrip()[:1] in "[{")
            verdict = "داده" if (looks_data and minutes) else ("۲۰۰ بی‌دقت" if looks_data else "مرده")
            print(f"[{r.status_code}] {len(body):>8}B {ct[:28]:28s} {verdict:11s} {name}")
            print(f"        {txt[:120]!r}")
            if verdict == "داده":
                alive.append((name, url))
        except Exception as e:
            print(f"[ERR] {name}: {str(e)[:90]}")
    print("\nزنده‌هایِ دقیقه‌ای:", alive or "هیچ")
    print("تفسیر: اگر فهرست خالی است، هیچ سورسِ دقیقه‌ایِ قابلِ اتکایی از TSETMC "
          "دسترس نیست و کندلِ ۱m..۱h باید صریحاً «غیرقابل‌اعمال» بماند.")


if __name__ == "__main__":
    main()
