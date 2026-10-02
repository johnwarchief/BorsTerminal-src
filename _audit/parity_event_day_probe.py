# -*- coding: utf-8 -*-
"""_audit/parity_event_day_probe.py — اثباتِ علتِ دو واگراییِ تعدیل، روز‌به‌روز.

دو فرضیه از اجرای parity درِ `_audit/ra_parity_report.json` بیرون آمد و این اسکریپت
هر دو را با عددِ خامِ همان روزها می‌آزماید (نه با آستانه):

  الف) «یکِ نشستِ جابه‌جا»: رویدادِ ما درِ روز D ضریب را از D به بعد برمی‌دارد
     (factor(t)=∏ ratio برای date > t)، پلکانِ مرجع درِ همان نسبت درِ D+1 جابه‌جا
     می‌شود ⇒ فقط کندلِ روز D اختلافِ بزرگ دارد. پیش‌بینی: هر دو سری درِ D-1 و D+1
     می‌خوانند و فقط D نمی‌خواند.

  ب) «رویدادِ یک‌طرفه»: ما رویدادی داریم که آن‌ها ندارند ⇒ کلِ تاریخِ قبلِ آن روز
     با یکِ عددِ ثابت جابه‌جا می‌شود و gap هیچ گامی درِ میانه ندارد. پیش‌بینی:
     نسبتِ ref/نمایشیِ ما قبل و بعد از آن روز دو سطحِ ثابتِ متفاوت دارد، نه نویز.

خروجی جدولِ روزبه‌روز برایِ فولاد و پارس (همان نمادهایی که مالک eventهایشان را نام برد).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "_audit"))

CACHE_CSV = os.path.join(ROOT, "_audit", "parity_event_csv")
RA_CACHE = os.path.join(ROOT, "_audit", "ra_probe_cache")
REPORTS = ("ra_parity_report.json", "ra_parity_foolad_pars.json")


def g2j(gy, gm, gd):
    _GDM = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100
            + (gy2 + 399) // 400 + gd + _GDM[gm - 1])
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        return int(jy), int(1 + days // 31), int(1 + days % 31)
    return int(jy), int(7 + (days - 186) // 30), int(1 + (days - 186) % 30)


def j2g(jy, jm, jd):
    """جلالی → میلادی با جستوجویِ دودویی رویِ g2j (همان تبدیلِ parity، بی‌کدِ دوم)."""
    lo = dt.date(1990, 1, 1)
    hi = dt.date(2100, 12, 31)
    while lo <= hi:
        mid = lo + (hi - lo) // 2
        got = g2j(mid.year, mid.month, mid.day)
        if got == (jy, jm, jd):
            return mid.isoformat()
        if got < (jy, jm, jd):
            lo = mid + dt.timedelta(days=1)
        else:
            hi = mid - dt.timedelta(days=1)
    return None


def csv_rows(ins_code):
    """قیمتِ خامِ TSETMC از همان CSVِ خودِ چارت: date → (FIRST, H, L, CLOSE, base, LAST)."""
    os.makedirs(CACHE_CSV, exist_ok=True)
    p = os.path.join(CACHE_CSV, f"{ins_code}.json")
    if os.path.isfile(p):
        return json.load(open(p, encoding="utf-8"))
    url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyListCSV/{ins_code}/19900101"
    raw = urllib.request.urlopen(urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.tsetmc.com/"}),
        timeout=120).read().decode("utf-8", "replace")
    out = {}
    for ln in raw.splitlines()[1:]:
        f = [x.strip() for x in ln.split(",")]
        if len(f) < 11:
            continue
        d = f[1]
        if len(d) != 8 or not d.isdigit():
            continue
        try:
            out[f"{d[:4]}-{d[4:6]}-{d[6:8]}"] = {"first": float(f[2] or 0), "high": float(f[3] or 0),
                                                 "low": float(f[4] or 0), "close": float(f[5] or 0),
                                                 "value": float(f[6] or 0), "vol": float(f[7] or 0),
                                                 "base": float(f[10] or 0), "last": float(f[11] or 0)
                                                 if len(f) > 11 else 0.0}
        except ValueError:
            continue
    json.dump(out, open(p, "w", encoding="utf-8"))
    return out


def ra_close(ins_code):
    raw = json.load(open(os.path.join(
        RA_CACHE, "httpstradersarenairdata%spricestimeframe0.json" % ins_code), encoding="utf-8"))["candles"]
    out = {}
    for r in raw:
        if len(r) < 7:
            continue
        d = dt.datetime.fromtimestamp(int(r[0]), dt.timezone.utc).date().isoformat()
        out[d] = {"open": float(r[1]), "high": float(r[2]), "low": float(r[3]), "close": float(r[4])}
    return out


def our_factors(events, days):
    """همان قاعدۀ تولید: factor(t) = ∏ ratio برایِ رویدادهایی که date > t."""
    ev = sorted((e["date"], e["ratio"]) for e in events)
    out, i = {}, len(ev) - 1
    f = 1.0
    for t in sorted(days, reverse=True):
        while i >= 0 and ev[i][0] > t:
            f *= ev[i][1]
            i -= 1
        out[t] = f
    return out


def probe(symbol, ins, events, window=2):
    raw = csv_rows(ins)
    ref = ra_close(ins)
    days = sorted(set(raw) & set(ref))
    fac = our_factors(events, days)
    print(f"\n─── {symbol} ({ins}) ───  روزهایِ مشترک={len(days)}  رویدادِ ما={len(events)}")
    print("  روز        raw_close   ref_close   k_ref     factor_ما  k_ref/factor "
          "⇒ تفسیر")
    hits = {"الف_یک_نشست": 0, "ب_یک_طرفه": 0, "نمی‌خواند": 0}
    for e in events:
        D = e["date"]
        if D not in days:
            continue
        i = days.index(D)
        lo, hi = max(0, i - window), min(len(days), i + window + 1)
        rows = []
        for t in days[lo:hi]:
            k = ref[t]["close"] / raw[t]["close"] if raw[t]["close"] else None
            fr = fac[t]
            rows.append((t, raw[t]["close"], ref[t]["close"], k, fr,
                         (k / fr) if (k and fr) else None))
        # نشانهٔ (الف): همهٔ روزها یکِ k/factor، به‌جز خودِ D
        norm = [r[5] for r in rows if r[5]]
        base_lvl = max(norm, key=norm.count) if norm else None
        d_row = next((r for r in rows if r[0] == D), None)
        tag = "نمی‌خواند"
        if d_row and base_lvl:
            others = [r[5] for r in rows if r[5] and r[0] != D]
            if others and all(abs(o / base_lvl - 1) < 0.002 for o in others) \
               and abs(d_row[5] / base_lvl - 1) > 0.002:
                tag = "الف_یک_نشست"
                hits["الف_یک_نشست"] += 1
            elif others and all(abs(o / base_lvl - 1) < 0.002 for o in others) \
                 and abs(d_row[5] / base_lvl - 1) <= 0.002:
                tag = "گامِ مشترک (هر دو همان روز)"
            else:
                hits["نمی‌خواند"] += 1
        print(f"  رویدادِ {D} ratio={e['ratio']}  [{tag}]")
        for t, rc, kc, k, fr, q in rows:
            print(f"    {t}  raw={rc:>14.4f} ref={kc:>14.6f} k_ref="
                  f"{'—' if k is None else format(k, '.6f'):>10} f_ما={fr:>10.6f} "
                  f"k/f={'—' if q is None else format(q, '.6f'):>10}"
                  + ("   ← روزِ رویداد" if t == D else ""))
    print("  جمعِ نشانه‌ها:", hits)


def main():
    blocks = {}
    for name in REPORTS:
        p = os.path.join(ROOT, "_audit", name)
        if not os.path.isfile(p):
            continue
        for b in json.load(open(p, encoding="utf-8")).get("per_symbol", []):
            if b["basis"] == "last" and "factor_schedule" in b:
                blocks[b["symbol"]] = b
    import sqlite3
    con = sqlite3.connect(os.path.join(ROOT, "market.db"), timeout=30)
    ins_map = {n: str(i) for n, i in con.execute("SELECT l_val18, ins_code FROM instruments")}
    con.close()
    named = {"فولاد": [("1399", 3, 6), ("1400", 3, 4), ("1400", 5, 17), ("1401", 12, 28)],
             "پارس": [("1397", 4, 20), ("1399", 3, 6), ("1399", 3, 26), ("1401", 2, 27)]}
    for sym, g in named.items():
        print(f"\n== تاریخ‌هایِ نام‌برده‌شدۀ مالک برایِ {sym} ==")
        for jy, jm, jd in g:
            print(f"   جلالی {jy}-{jm:02d}-{jd:02d} = میلادی {j2g(int(jy), int(jm), int(jd))}")
    for sym in ("فولاد", "پارس"):
        b = blocks.get(sym)
        if not b:
            print(f"\n{sym}: درِ هیچِ گزارشی نیست — با این هارنس سنجیده نشده")
            continue
        ins = ins_map.get(sym)
        if not ins:
            print(f"{sym}: ins_code درِ بانک نیست")
            continue
        probe(b["symbol"], ins, b["adjust_events"] or [])


if __name__ == "__main__":
    main()
