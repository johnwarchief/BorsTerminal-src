# -*- coding: utf-8 -*-
"""قدمِ ۱(b) — ضمیمه: کندلِ ماهانۀ رهاورد از کدامِ روزها جمع می‌شود؟

فرضِ محوریِ §۶ قرارداد: سطلِ ماهِ آن‌ها جلالی است (اندازه‌گیری‌شده در
`_audit/ra_monthly_bucket.py`) و closeِ تجمیعی := آخرینِ روزِ سطل.
اینجا همان را با خودِ دادهٔ رهاورد می‌سنجیم، بی‌هیچ تعلقِ به ضریبِ تعدیل و بی‌TSETMC:
هر دو سری (tf=0 و tf=2) از یکِ منبع‌اند و فقط در ثابتِ نرمال‌سازی فرق دارند، پس
نسبتِ عددِ ماهانه به عددِ تجمیعیِ روزانه باید تحتِ «فرضِ درست» یکِ مقدارِ ثابت باشد و
تحتِ فرضِ رقیب (سطلِ میلادی) نه.

سه سنجه که هیچ‌کدام حدس نیست:
  ۱) volume: جمعِ حجمِ روزهایِ سطل == حجمِ کندلِ ماهانه؟ (حجم خامِ جمع‌شدنی است)
  ۲) close : نسبتِ closeِ ماهانه به closeِ «آخرینِ روزِ سطل» — پراکندگی (std/mean)
  ۳) high/low: آیا highِ ماهانه == max(highِ روزها) و low == min(lowِ روزها) است؟
فرض‌ها: سطلِ جلالی (از ستونِ jalali خودِ API) در برابرِ سطلِ میلادی (از stamp).
"""
import datetime as dt
import json
import os
import statistics as st
import sys
import urllib.request

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://tradersarena.ir/"}
SYMS = [("فولاد", "46348559193224090"), ("پارس", "6110133418282108"),
        ("خگستر", "48990026850202503"), ("شبندر", "35366681030756042"),
        ("خودرو", "65883838195688438")]
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


def candles(ins, tf):
    out = []
    for x in get_json(f"https://tradersarena.ir/data/{ins}/prices?timeframe={tf}").get("candles") or []:
        if len(x) < 7:
            continue
        out.append({"ep": int(x[0]), "o": float(x[1]), "h": float(x[2]), "l": float(x[3]),
                    "c": float(x[4]), "v": float(x[5]),
                    "jy": int(str(int(x[6])).zfill(8)[:4]), "jm": int(str(int(x[6])).zfill(8)[4:6]),
                    "jd": int(str(int(x[6])).zfill(8)[6:]),
                    "g": dt.datetime.fromtimestamp(int(x[0]), dt.timezone.utc).strftime("%Y-%m-%d"),
                    "gy": dt.datetime.fromtimestamp(int(x[0]), dt.timezone.utc).year,
                    "gm": dt.datetime.fromtimestamp(int(x[0]), dt.timezone.utc).month})
    return out


def compare(name, daily, monthly, dkey, mkey):
    """dkey/mkey: تابعِ کلیدِ سطل برایِ روزانه و ماهانه (جلالی یا میلادی)."""
    buckets = {}
    for d in daily:
        buckets.setdefault(dkey(d), []).append(d)
    vol_ok = vol_tot = close_hit = close_tot = hi_ok = lo_ok = 0
    ratios = []
    for m in monthly:
        days = buckets.get(mkey(m))
        if not days:
            continue
        vol_tot += 1
        s = sum(x["v"] for x in days)
        if s > 0 and abs(m["v"] / s - 1.0) < 0.02:
            vol_ok += 1
        days.sort(key=lambda x: x["ep"])
        last = days[-1]
        close_tot += 1
        if last["c"] > 0:
            ratios.append(m["c"] / last["c"])
        if abs(m["h"] - max(x["h"] for x in days)) <= max(1e-6, 0.01 * m["h"]):
            hi_ok += 1
        if abs(m["l"] - min(x["l"] for x in days)) <= max(1e-6, 0.01 * m["l"]):
            lo_ok += 1
    disp = (st.pstdev(ratios) / st.mean(ratios)) if len(ratios) > 2 else float("nan")
    return {"symbol": name, "monthly_candles_matched": vol_tot,
            "vol_sum_match": f"{vol_ok}/{vol_tot}",
            "high_max_match": f"{hi_ok}/{vol_tot}", "low_min_match": f"{lo_ok}/{vol_tot}",
            "close_ratio_median": round(st.median(ratios), 6) if ratios else None,
            "close_ratio_cv": round(disp, 8) if disp == disp else None}


def main():
    jal, gre = {}, {}
    for name, ins in SYMS:
        d, m = candles(ins, 0), candles(ins, 2)
        jal[name] = compare(name, d, m, lambda x: (x["jy"], x["jm"]), lambda x: (x["jy"], x["jm"]))
        gre[name] = compare(name, d, m, lambda x: (x["gy"], x["gm"]), lambda x: (x["gy"], x["gm"]))
    print("== سطلِ جلالی ==")
    for v in jal.values():
        print("  ", json.dumps(v, ensure_ascii=False))
    print("\n== سطلِ میلادی ==")
    for v in gre.values():
        print("  ", json.dumps(v, ensure_ascii=False))
    out = {"jalali_bucket": jal, "gregorian_bucket": gre,
           "note": "نسبتِ close تحتِ فرضِ درست باید پراکندگیِ ~صفر داشته باشد (ثابتِ نرمال‌سازی)"}
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ra_monthly_aggregate.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nنوشته شد:", p)


if __name__ == "__main__":
    main()
