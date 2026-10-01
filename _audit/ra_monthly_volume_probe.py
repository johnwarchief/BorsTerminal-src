# -*- coding: utf-8 -*-
"""قدمِ ۱(b) — ضمیمهٔ دوم: volume/ارزشِ کندلِ ماهانۀ رهاورد چه جمعِ روزانه است یا نه.

سنجشِ قبلی (`ra_monthly_aggregate_probe.py`) نشان داد سطل ماه جلالی است و
high/low/closeِ ماهانه دقیقاً از روزهایِ همان ماهِ جلالی می‌آید (نسبت close = ۱٫۰۰۰۰۰۰،
cv=۰). ولی «vol ماهانه == جمع vol روزانه» در هیچ‌کدام از دو فرض نخواند (۰/۱۸۲).
اینجا فرض‌ها را یکی‌می‌سنجیم: جمع، میانگین، آخرین، بیشینه — و نسبتِ واقعی را گزارش
می‌کنیم. همۀ اعداد از خودِ دو سریِ رهاورد (tf=0 و tf=2) می‌آید؛ هیچ منبعِ دیگری نه.
"""
import datetime as dt
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ra_monthly_aggregate_probe import candles, SYMS  # noqa: E402


def main():
    per = {}
    for name, ins in SYMS:
        d, m = candles(ins, 0), candles(ins, 2)
        buck = {}
        for x in d:
            buck.setdefault((x["jy"], x["jm"]), []).append(x)
        rows = []
        for c in m:
            days = sorted(buck.get((c["jy"], c["jm"]), []), key=lambda x: x["ep"])
            if not days:
                continue
            s = sum(x["v"] for x in days)
            rows.append({"g": c["g"], "mvol": c["v"], "sum": s, "mean": s / len(days),
                         "last": days[-1]["v"], "max": max(x["v"] for x in days),
                         "ndays": len(days),
                         "ratio_sum": c["v"] / s if s else None,
                         "open_ratio": c["o"] / days[0]["o"] if days[0]["o"] else None,
                         "close_ratio": c["c"] / days[-1]["c"] if days[-1]["c"] else None})
        hit = {k: sum(1 for r in rows if r["mvol"] == r[k]) for k in ("sum", "mean", "last", "max")}
        rr = [r["ratio_sum"] for r in rows if r["ratio_sum"]]
        oc = [r["open_ratio"] for r in rows if r["open_ratio"]]
        cc = [r["close_ratio"] for r in rows if r["close_ratio"]]
        per[name] = {"months_matched": len(rows), "exact_matches": hit,
                     "vol_over_sum_median": round(st.median(rr), 6),
                     "vol_over_sum_min": round(min(rr), 6), "vol_over_sum_max": round(max(rr), 6),
                     "open_over_firstday_open_median": round(st.median(oc), 6),
                     "open_over_firstday_open_cv": round(st.pstdev(oc) / st.mean(oc), 6),
                     "close_over_lastday_median": round(st.median(cc), 6),
                     "close_over_lastday_cv": round(st.pstdev(cc) / st.mean(cc), 6),
                     "sample_3": rows[-3:]}
        print(name, json.dumps({k: v for k, v in per[name].items() if k != "sample_3"}, ensure_ascii=False))
        print("   نمونهٔ آخر:", json.dumps(rows[-3:], ensure_ascii=False)[:400])
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ra_monthly_volume.json")
    json.dump(per, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("نوشته شد:", p)


if __name__ == "__main__":
    main()
