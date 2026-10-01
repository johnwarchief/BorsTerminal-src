# -*- coding: utf-8 -*-
"""قدمِ ۱(b) — ضمیمهٔ سوم: ستونِ volume درِ کندلِ ماهانۀ رهاورد از چه حسابی می‌آید.

`ra_monthly_volume_probe.py` ثابت کرد OHLC ماهانۀ رهاورد *دقیقاً* تجمیعِ روزهایِ همان
ماه جلالی است (open=روزِ اول، close=روزِ آخر، high=max، low=min؛ نسبت=۱٫۰۰۰۰۰۰، cv=۰)،
ولی «vol ماهانه == جمع vol روزانه» نخواند (۰/۸۰۱) و نسبت پخش است (میانهٔ ۰٫۰۴۵).
اینجا ردیف‌هایِ خام (۹ ستون) دوباره فرضیه‌سنجی می‌شوند؛ هیچ عددی حدس نیست: هر فرضیه
با درصدِ تطبیقِ ±۰٫۵٪ گزارش می‌شود.
"""
import datetime as dt
import json
import os
import statistics as st
import urllib.request

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://tradersarena.ir/"}
SYMS = [("فولاد", "46348559193224090"), ("پارس", "6110133418282108"),
        ("خگستر", "48990026850202503"), ("شبندر", "35366681030756042")]
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ra_probe_cache")


def get_json(url, timeout=90):
    key = os.path.join(CACHE, "".join(c for c in url if c.isalnum()) + ".json")
    if os.path.isfile(key):
        return json.load(open(key, encoding="utf-8"))
    req = urllib.request.Request(url, headers=UA)
    data = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    j = json.loads(data)
    json.dump(j, open(key, "w", encoding="utf-8"))
    return j


def raw(ins, tf):
    return get_json(f"https://tradersarena.ir/data/{ins}/prices?timeframe={tf}")["candles"]


def jkey(row):
    s = str(int(row[6])).zfill(8)
    return int(s[:4]), int(s[4:6])


def main():
    for name, ins in SYMS:
        daily = [r for r in raw(ins, 0) if len(r) >= 7]
        buck = {}
        for r in daily:
            buck.setdefault(jkey(r), []).append(r)
        monthly = [r for r in raw(ins, 2) if len(r) >= 7]
        hyp = {k: [0, 0] for k in ("sum_v5", "mean_v5", "v7_last", "sum_v7", "mean_v7",
                                  "sum_v8", "mean_v8", "v5_of_last", "mean_price_weighted")}
        ratios = []
        for c in monthly:
            days = sorted(buck.get(jkey(c), []), key=lambda r: int(r[0]))
            if not days:
                continue
            mv = float(c[5])
            n = len(days)
            s5 = sum(float(x[5]) for x in days)
            s7 = sum(float(x[7]) for x in days if len(x) > 7 and x[7] is not None)
            s8 = sum(float(x[8]) for x in days if len(x) > 8 and x[8] is not None)
            lastp = float(days[-1][4]) or 1.0
            cand = {"sum_v5": s5, "mean_v5": s5 / n, "v7_last": float(days[-1][7]) if len(days[-1]) > 7 else None,
                    "sum_v7": s7, "mean_v7": s7 / n, "sum_v8": s8, "mean_v8": s8 / n,
                    "v5_of_last": float(days[-1][5]),
                    "mean_price_weighted": sum(float(x[5]) * (float(x[4]) / lastp) for x in days) / n}
            for k, v in cand.items():
                if v:
                    hyp[k][1] += 1
                    if abs(mv / v - 1.0) < 0.005:
                        hyp[k][0] += 1
            ratios.append((c[6], n, mv, s5, mv / s5 if s5 else None,
                           float(c[7]) if len(c) > 7 else None, s7 / n if n else None))
        print(f"--- {name}: {len(ratios)} ماه")
        for k, (hit, tot) in hyp.items():
            print(f"    {k:<22} تطبیق ±۰٫۵٪: {hit}/{tot}")
        rs = [r[4] for r in ratios if r[4]]
        print(f"    نسبت mvol/sum_v5: میانه {st.median(rs):.6f} min {min(rs):.6f} max {max(rs):.6f}")
        # آیا mvol == میانگینِ volume روزهایِ ماه * تحتِ مبنایِ دیگر است؟ نمونهٔ ۵ ماهِ آخر
        print("    ۵ ماهِ آخر (jalali, ndays, mvol, sum_v5, ratio, mcol7, mean_v7):")
        for r in ratios[-5:]:
            print("      ", [x if not isinstance(x, float) else round(x, 3) for x in r])


if __name__ == "__main__":
    main()
