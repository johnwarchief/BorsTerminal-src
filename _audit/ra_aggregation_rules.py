# -*- coding: utf-8 -*-
"""قدمِ ۱(b) — قانونِ کاملِ تجمیعِ رهاورد (روزانه → هفتگی/ماهانه)، رویِ همهٔ سطل‌ها.

چرا این سنجش لازم است: §۶ موجودی می‌گوید تجمیعِ ما «جمعِ حجم» است و close را از آخرینِ روز
می‌گیرد؛ باید عددِ مرجع (رهاورد) اندازه گرفته شود، نه فرض.

فرضیه‌هایِ حجم که جدا جدا شمرده می‌شوند (تطبیقِ دقیق، بی‌تلورانس):
  first (روزِ اولِ سطل) · last · sum · mean · max · median
و برایِ OHLC: open=first.open، close=last.close، high=max، low=min (نسبت + پراکندگی).
کلیدِ سطل = (سال، ماه/هفتۀ) جلالیِ ستونِ jalali خودِ API؛ هیچ تبدیلِ تقویمیِ ما دخیل نیست.
"""
import datetime as dt
import json
import os
import statistics as st
import sys

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ra_probe_cache")
SYMS = [("فولاد", "46348559193224090"), ("پارس", "6110133418282108"),
        ("خگستر", "48990026850202503"), ("شبندر", "35366681030756042"),
        ("خودرو", "65883838195688438")]


def raw(tf, ins):
    p = os.path.join(CACHE, f"httpstradersarenairdata{ins}pricestimeframe{tf}.json")
    return json.load(open(p, encoding="utf-8"))["candles"]


def day(r):
    return dt.datetime.fromtimestamp(int(r[0]), dt.timezone.utc).date()


def jkey(r):
    s = str(int(r[6])).zfill(8)
    return int(s[:4]), int(s[4:6])


def wkkey(r):
    """سطلِ هفتگی را با همان کلیدِ ماه نمی‌شود گرفت؛ از stamp و ستون jalali فقط روز می‌آید،
    پس هفته را با فاصلۀ stamp از اولِ سریِ ماهانۀ خودشان نمی‌سازیم — هفتگی در این فایل
    فقط برایِ «حجم = روزِ اول» بودنِ همان قاعده سنجیده می‌شود (کلید: خودِ stamp)."""
    return day(r).isocalendar()[0], day(r).isocalendar()[1]


def buckets(daily, keyfn):
    b = {}
    for r in daily:
        b.setdefault(keyfn(r), []).append(r)
    for v in b.values():
        v.sort(key=lambda r: int(r[0]))
    return b


def measure(name, agg_rows, daily, keyfn, label):
    """دو روشِ سطل‌بندی، هر دو بدونِ فرضِ تقویمی:
       (الف) کلیدِ جلالیِ خودِ API (jalali column)
       (ب) بازۀِ stamp: از stampِ این کندلِ تجمیلی تا stampِ کندلِ بعدی (از خودِ رهاورد)
    نتیجهٔ هر دو جدا شمرده می‌شود؛ اگر یکی باشند، قانون مستقلِ تقویم است."""
    out = {"tf": label, "symbol": name, "modes": {}}
    eps = sorted(int(r[0]) for r in daily)
    epi = {int(r[0]): r for r in daily}
    for mode in ("jalali_key", "stamp_range"):
        b = {}
        if mode == "jalali_key":
            b = {k: v for k, v in buckets(daily, keyfn).items()}
            get = lambda a: b.get(keyfn(a), [])
        else:
            ast = sorted(int(r[0]) for r in agg_rows)
            def get(a, ast=ast):
                t = int(a[0])
                nxt = [x for x in ast if x > t]
                hi = nxt[0] if nxt else 10**12
                return [epi[e] for e in eps if t <= e < hi]
        hit = {k: 0 for k in ("first", "last", "sum", "mean", "max", "median")}
        ohlc = {k: [0, 0] for k in ("open_first", "close_last", "high_max", "low_min")}
        tot = 0
        for a in agg_rows:
            days = get(a)
            if not days:
                continue
            tot += 1
            v = [float(x[5]) for x in days]
            mv = float(a[5])
            for k, val in (("first", v[0]), ("last", v[-1]), ("sum", sum(v)),
                           ("mean", sum(v) / len(v)), ("max", max(v)), ("median", st.median(v))):
                if mv == val:
                    hit[k] += 1
            for k, got, exp in (("open_first", float(a[1]), float(days[0][1])),
                                ("close_last", float(a[4]), float(days[-1][4])),
                                ("high_max", float(a[2]), max(float(x[2]) for x in days)),
                                ("low_min", float(a[3]), min(float(x[3]) for x in days))):
                ohlc[k][1] += 1
                if exp and abs(got / exp - 1.0) < 1e-9:
                    ohlc[k][0] += 1
        out["buckets_matched"] = tot
        out["modes"][mode] = {"volume_rule_hits": {k: f"{c}/{tot}" for k, c in hit.items()},
                              "ohlc_rule_hits": {k: f"{c[0]}/{c[1]}" for k, c in ohlc.items()}}
    return out


def main():
    report = {}
    for name, ins in SYMS:
        daily = raw(0, ins)
        for tf, label, keyfn in ((2, "ماهانه(tf=2)", jkey),
                                 (1, "هفتگی(tf=1)", wkkey)):
            agg = raw(tf, ins) if os.path.isfile(
                os.path.join(CACHE, f"httpstradersarenairdata{ins}pricestimeframe{tf}.json")) else None
            if agg is None:
                print(f"{name} {label}: سریِ مرجع در cache نیست (عمداً حدس نمی‌زنم)")
                continue
            r = measure(name, agg, daily, keyfn, label)
            report.setdefault(label, []).append(r)
            print(json.dumps(r, ensure_ascii=False))
        # هفتگی با کلیدِ شنبه (قراردادِ خودِ ما) هم سنجیده شود تا معلوم شود کلیدِ آن‌ها چیست
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ra_aggregation_rules.json")
    json.dump(report, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("نوشته شد:", p)


if __name__ == "__main__":
    main()
