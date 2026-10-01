# -*- coding: utf-8 -*-
"""قدمِ ۱ قراردادِ parity — دو سنجشِ باز، مستقیم از دادهٔ خودِ رهاورد.

سؤالِ الف: openِ کندلِ رهاورد از ستونِ `FIRST` (اولین) تپ‌سیت‌مک است یا `OPEN`
(قیمتِ پایه)؟ هر دو درِ همان فایلِ CSV هست‌اند و کدِ ما درِ
`test_tsetmc.py:1181` دومی را برمی‌دارد در حالی که دادهٔ ذخیره‌شده با اولی
می‌خواند.

سؤالِ ب: کندلِ ماهانۀ آن‌ها بر چه تقویمی bucket می‌شود — جلالی یا میلادی؟
بی‌نیاز از هیچ تبدیلِ تقویمی: اگر bucket میلادی باشد، زمانِ هر کندلِ ماهانه
حتماً «روزِ اولِ ماهِ میلادی» است؛ اگر جلالی باشد، روزِ شروعِ ماهِ جلالی درِ
میلادی می‌چرخد (۲۰/۲۱/۲۲). پس فقط شمارشِ روزِ شروع کافی است.

سریِ رهاورد تعدیلِ برگشتی است، لذا ضریب k از خودِ هر ردیف حل می‌شود
(k = ra_close / TSETMC_LAST، که LAST مبنایِ close آن‌ها در سنجشِ §۱-پ قراردادهاست)
و openِ انتظار = ra_open / k. مقایسه رویِ هر دو ستون انجام می‌شود و عددِ
برنده با حاشیه گزارش می‌شود — نه با یک آستانهٔ دل‌خواه.
"""
import csv
import datetime as dt
import io
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_tsetmc as T  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://tradersarena.ir/"}
SYMS = [("فولاد", "46348559193224090"), ("پارس", "6110133418282108"),
        ("خگستر", "48990026850202503"), ("شبندر", "35366681030756042"),
        ("خودرو", "65883838195688438")]
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ra_probe_cache")


def get_json(url, timeout=90):
    os.makedirs(CACHE, exist_ok=True)
    key = os.path.join(CACHE, "".join(c for c in url if c.isalnum()) + ".json")
    if os.path.isfile(key):
        return json.load(open(key, encoding="utf-8"))
    req = urllib.request.Request(url, headers=UA)
    data = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    j = json.loads(data)
    json.dump(j, open(key, "w", encoding="utf-8"))
    return j


def ra_candles(ins, timeframe):
    u = f"https://tradersarena.ir/data/{ins}/prices?timeframe={timeframe}"
    j = get_json(u)
    out = {}
    for row in j.get("candles") or []:
        if len(row) < 6:
            continue
        # [time, open, high, low, close, volume, jalali, ...]
        t = int(row[0])
        day = dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d")
        out[day] = dict(open=float(row[1]), high=float(row[2]), low=float(row[3]),
                        close=float(row[4]), vol=float(row[5]),
                        jalali=row[6] if len(row) > 6 else None)
    return out


def tsetmc_days(ins):
    u = f"{T.BASE}/ClosingPrice/GetClosingPriceDailyListCSV/{ins}/20240101"
    rows = list(csv.reader(io.StringIO(urllib.request.urlopen(
        urllib.request.Request(u, headers=T.HEADERS), timeout=150).read().decode("utf-8", "replace"))))
    head = [h.strip("<>") for h in rows[0]]
    idx = {n: i for i, n in enumerate(head)}
    out = {}
    for f in rows[1:]:
        if len(f) < len(head):
            continue
        d = f[idx["DTYYYYMMDD"]].strip()
        if len(d) != 8 or not d.isdigit():
            continue
        try:
            out[f"{d[:4]}-{d[4:6]}-{d[6:]}"] = {
                k: float(f[idx[k]]) for k in ("FIRST", "OPEN", "HIGH", "LOW", "CLOSE", "LAST")}
        except (ValueError, KeyError, IndexError):
            continue
    return out


def main():
    print("=== الف) openِ رهاورد: FIRST در برابرِ OPEN ===")
    tot_first = tot_open = tot_none = n = 0
    for sym, ins in SYMS:
        try:
            ra, ts = ra_candles(ins, 0), tsetmc_days(ins)
        except Exception as e:
            print("  %-8s ERR %s %s" % (sym, type(e).__name__, str(e)[:80]))
            continue
        hit_f = hit_o = neither = used = 0
        for day, r in sorted(ra.items()):
            t = ts.get(day)
            if not t or not t.get("LAST"):
                continue
            k = r["close"] / t["LAST"]
            if k <= 0:
                continue
            exp_open = r["open"] / k
            df, do = abs(exp_open / t["FIRST"] - 1), abs(exp_open / t["OPEN"] - 1)
            used += 1
            if df <= 0.0015 and df < do:
                hit_f += 1
            elif do <= 0.0015 and do < df:
                hit_o += 1
            else:
                neither += 1
        n += used
        tot_first += hit_f
        tot_open += hit_o
        tot_none += neither
        print("  %-8s ردیف=%-5d FIRST=%-5d OPEN=%-5d هیچ‌کدام=%-5d" %
              (sym, used, hit_f, hit_o, neither))
    if n:
        print("  جمع: FIRST %d (%.1f%%) | OPEN %d (%.1f%%) | هیچ‌کدام %d (%.1f%%)" %
              (tot_first, 100 * tot_first / n, tot_open, 100 * tot_open / n,
               tot_none, 100 * tot_none / n))
    else:
        print("  هیچ ردیفِ مشترکی نبود — سنجش انجام نشد")

    print("\n=== ب) bucketِ ماهانۀ رهاورد ===")
    for sym, ins in SYMS[:2]:
        for tf in (1, 2, 3, 4, 5):
            try:
                j = get_json(f"https://tradersarena.ir/data/{ins}/prices?timeframe={tf}")
                rows = j.get("candles") or []
            except Exception as e:
                print("  %-8s tf=%d ERR %s" % (sym, tf, type(e).__name__))
                continue
            if len(rows) < 4:
                print("  %-8s tf=%d -> %d candle" % (sym, tf, len(rows)))
                continue
            starts = []
            for row in rows[-14:]:
                t = int(row[0])
                g = dt.datetime.fromtimestamp(t, dt.timezone.utc)
                starts.append((g.strftime("%Y-%m-%d"), g.day, row[6] if len(row) > 6 else ""))
            day1 = sum(1 for _, d, _ in starts if d == 1)
            print("  %-8s tf=%d -> %d candle | نمونهٔ شروع: %s | روز=۱ِ میلادی: %d/%d"
                  % (sym, tf, len(rows), ", ".join(s[0] for s in starts[:4]),
                     day1, len(starts)))
            if starts and day1 < len(starts):
                print("     ⇒ شروع‌ها رویِ روزِ اولِ ماهِ میلادی نمی‌افتند؛ bucket جلالی است")
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
