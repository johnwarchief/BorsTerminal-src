#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/ra365_chain_parity.py — زنجیرۀِ تعدیلِ خودی در برابرِ مرجع، تا اولِ تاریخچه

پیش از این فقط ۶۰۱ روزِ آخر شاهد داشتیم. حالا هر دو سریِ مرجع (type0 خام و
type7 تعدیل‌شده) برایِ ۴٬۲۴۹ کندل از ۲۰۰۷-۰۳-۱۱ تا امروز گرفته شده‌اند
(`_scratch/live/ra365_type{0,7}_daily.json`، ازِ همانِ نشستِ مجازِ مالک).

خروجی: جدولِ پلۀِ ضریب‌ها + اختلافِ عددیِ سریِ رسم‌شدنه، و CSVِ گواهی.
اجرا: python _audit/ra365_chain_parity.py
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = lambda *p: os.path.join(ROOT, *p)
OUT_CSV = A("_audit", "RA365-CHAIN-PARITY-FULL-HISTORY-2026-10-18.csv")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


ref7 = load(A("_scratch", "live", "ra365_type7_daily.json"))["bars"]
ref0 = load(A("_scratch", "live", "ra365_type0_daily.json"))["bars"]
ours = load(A("_scratch", "live", "api_chart_folad_last.json"))

t7 = {b["utc"][:10]: b for b in ref7}
t0 = {b["utc"][:10]: b for b in ref0}
oc = {c["time"]: c for c in ours["candles"]}
of = {f["time"]: f["factor"] for f in ours["factors"]}

dates = sorted(set(t7) & set(t0) & set(oc))
rows = []
for d in dates:
    r0, r7 = t0[d]["c"], t7[d]["c"]
    if not r0:
        continue
    ref_factor = r7 / r0
    our_factor = of.get(d, 1.0)
    our_drawn = round(oc[d]["close"] * our_factor, 4)
    rows.append({
        "date": d, "ref_raw": r0, "ref_adj": r7, "our_raw": oc[d]["close"],
        "ref_factor": ref_factor, "our_factor": our_factor,
        "factor_gap": our_factor - ref_factor,
        "factor_gap_pct": (our_factor / ref_factor - 1) * 100 if ref_factor else None,
        "our_drawn": our_drawn, "price_gap": our_drawn - r7,
        "price_gap_pct": (our_drawn / r7 - 1) * 100 if r7 else None,
    })

gaps = [abs(r["factor_gap"]) for r in rows]
pct = [abs(r["factor_gap_pct"]) for r in rows if r["factor_gap_pct"] is not None]
pgap = [abs(r["price_gap"]) for r in rows]
ppct = [abs(r["price_gap_pct"]) for r in rows if r["price_gap_pct"] is not None]

print(f"تاریخ‌هایِ مشترک (خودی × مرجع خام × مرجع تعدیل‌شده): {len(rows)}")
print(f"  بازه: {rows[0]['date']} تا {rows[-1]['date']}")
print(f"  اختلافِ ضریب  |max| = {max(gaps):.9f}  |mean| = {sum(gaps)/len(gaps):.9f}")
print(f"  اختلافِ ضریب  درصدی |max| = {max(pct):.4f}%  |mean| = {sum(pct)/len(pct):.4f}%")
print(f"  اختلافِ قیمتِ رسم‌شدنه  |max| = {max(pgap):.4f}  |mean| = {sum(pgap)/len(pgap):.4f}")
print(f"  اختلافِ قیمتِ رسم‌شدنه  درصدی |max| = {max(ppct):.4f}%  |mean| = {sum(ppct)/len(ppct):.4f}%")
exact = sum(1 for r in rows if abs(r["price_gap"]) < 1e-9)
print(f"  تطبیقِ کاملِ قیمت: {exact} از {len(rows)}")

# پلۀِ ضریبِ خودی در برابرِ پلۀِ ضریبِ مرجع (نخستینِ تاریخِ هرِ پله)
def levels(key):
    out, prev = [], None
    for r in rows:
        v = round(r[key], 9)
        if v != prev:
            out.append({"factor": v, "first": r["date"], "count": 0})
            prev = v
        out[-1]["count"] += 1
    return out

lv_our, lv_ref = levels("our_factor"), levels("ref_factor")
print(f"\nپلۀِ ضریبِ خودی: {len(lv_our)}   پلۀِ ضریبِ مرجع: {len(lv_ref)}")
print(f"{'نخستینِ پلۀِ خودی':<16}{'ضریبِ خودی':<16}{'نخستینِ پلۀِ مرجع':<20}{'ضریبِ مرجع':<16}{'Δ%':>10}")
for i in range(max(len(lv_our), len(lv_ref))):
    a = lv_our[i] if i < len(lv_our) else None
    b = lv_ref[i] if i < len(lv_ref) else None
    if a and b:
        d = (a["factor"] / b["factor"] - 1) * 100
        print(f"{a['first']:<16}{a['factor']:<16.9f}{b['first']:<20}{b['factor']:<16.9f}{d:>10.4f}")
    elif a:
        print(f"{a['first']:<16}{a['factor']:<16.9f}{'—':<20}{'—':<16}{'—':>10}")
    else:
        print(f"{'—':<16}{'—':<16}{b['first']:<20}{b['factor']:<16.9f}{'—':>10}")

worst = sorted(rows, key=lambda r: -abs(r["price_gap_pct"] or 0))[:12]
print("\nبدترینِ تاریخ‌ها از نظرِ قیمتِ رسم‌شدنه:")
for r in worst:
    print(f"  {r['date']}  خودی {r['our_drawn']:.4f}  مرجع {r['ref_adj']:.4f}  "
          f"Δ {r['price_gap']:+.4f} ({r['price_gap_pct']:+.4f}%)  "
          f"ضریب خودی {r['our_factor']:.9f} / مرجع {r['ref_factor']:.9f}")

with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    for r in rows:
        w.writerow({k: (f"{v:.9f}" if isinstance(v, float) else v) for k, v in r.items()})
print("\nCSV:", OUT_CSV, "rows:", len(rows))
