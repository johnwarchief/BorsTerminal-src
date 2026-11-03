# _audit/ra365_adjustment_events.py -- ریشۀِ اختلافِ تعدیلِ عملکردی: زنجیرۀِ فاکتورِ ما در برابرِ دفترِ رویدادهایِ مرجع
# مرجع دو دستۀِ دادۀِ هم‌خانواده دارد: type0 (بدونِ تعدیل) و type7 (عملکردی).
#   نسبتِ type7/type0 در هر روز == فاکتورِ تجمعیِ خودِ مرجع (بدونِ مدل‌سازی).
# تغییرِ این نسبت درِ یک روز = رویدادِ تعدیلِ آن روز. همان را با زنجیرۀِ فاکتورِ خودِ محصول می‌سنجیم.
# محصول: factorsِ /api/chart (مقیاسِ روزِ آخر) + adjust_events (تاریخ، نسبت).
import json
import sys
import io
import csv
from datetime import datetime, timezone, timedelta
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
TEHRAN = timezone(timedelta(hours=3, minutes=30))
TOL = 0.004  # آستانۀِ «رویداد» در نسبتِ تعدیل (۰.۴٪)
OUT = "_audit/RA365-ADJUSTMENT-EVENTS-2026-10-12.csv"


def tdate(u):
    dt = datetime.fromisoformat(u)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TEHRAN).date().isoformat()


ref = json.load(open("_audit/ra365_ref_bars.json", encoding="utf-8"))
prod = json.load(open("_audit/ra365_product_bars.json", encoding="utf-8"))
corpus = json.load(open("_audit/ra365_corpus.json", encoding="utf-8"))

rows = []
totals = Counter()
for c in corpus:
    sym = c["sym"]
    a0 = ref["bars"].get(f"{sym}|type0|D")
    a7 = ref["bars"].get(f"{sym}|type7|D")
    if not a0 or not a7:
        continue
    R0 = {tdate(b["utc"]): b for b in a0["bars"]}
    R7 = {tdate(b["utc"]): b for b in a7["bars"]}
    dates = sorted(set(R0) & set(R7))
    if len(dates) < 20:
        continue
    ratio = {d: (R7[d]["c"] / R0[d]["c"]) for d in dates if R0[d]["c"]}
    # لنگر: نسبتِ آخرینِ روز (باید ۱ باشد اگر مرجع هم مقیاسِ روزِ آخر دارد)
    anchor = ratio[dates[-1]]
    ref_factor = {d: v / anchor for d, v in ratio.items()}
    ref_events = []
    prev = None
    for d in dates:
        f = ref_factor[d]
        if prev is not None and abs(f / prev - 1.0) > TOL:
            ref_events.append({"date": d, "multiplier": round(prev / f, 6) if f else None})
        prev = f

    rec = prod[sym]["live"]
    fac = {f["time"]: f["factor"] for f in (rec["factors"] or [])}
    first_ref_day = dates[0]
    ours = sorted((kv for kv in fac.items() if kv[0] >= first_ref_day))
    our_events = []
    prev = None
    for d, v in ours:
        if prev is not None and abs(v / prev - 1.0) > TOL:
            our_events.append({"date": d, "multiplier": round(prev / v, 6)})
        prev = v
    # رویدادهایِ ثبت‌شده درِ جدولِ خودِ محصول (منبعِ همان فاکتورها)
    stored = {e["date"]: e["ratio"] for e in (rec.get("adjustEvents") or [])}

    # تطبیقِ رویدادها با تلورانسِ ۷ روز
    used = set()
    pairs = []
    for e in ref_events:
        best = None
        for o in our_events:
            if o["date"] in used:
                continue
            dd = abs((datetime.fromisoformat(o["date"]) - datetime.fromisoformat(e["date"])).days)
            if dd <= 7 and (best is None or dd < best[0]):
                best = (dd, o)
        if best:
            used.add(best[1]["date"])
            pairs.append({"kind": "matched", "ref_date": e["date"], "ref_mult": e["multiplier"],
                          "our_date": best[1]["date"], "our_mult": best[1]["multiplier"],
                          "days_apart": best[0],
                          "mult_rel_err": round(abs(e["multiplier"] - best[1]["multiplier"]) / e["multiplier"], 5) if e["multiplier"] else None})
        else:
            pairs.append({"kind": "only-in-reference", "ref_date": e["date"], "ref_mult": e["multiplier"]})
    for o in our_events:
        if o["date"] not in used:
            pairs.append({"kind": "only-in-product", "our_date": o["date"], "our_mult": o["multiplier"]})

    n_ref = len(ref_events)
    n_our = len(our_events)
    n_match = sum(1 for p in pairs if p["kind"] == "matched")
    totals["ref_events"] += n_ref
    totals["our_events"] += n_our
    totals["matched"] += n_match
    totals["anchor_offset_pct"] += abs(anchor - 1.0) * 100
    rows.append({
        "symbol": sym, "asset_id": c["id"], "days_compared": len(dates),
        "ref_anchor_ratio_at_last_day": round(anchor, 6),
        "ref_events": n_ref, "product_events": n_our, "matched_within_7d": n_match,
        "only_in_reference": sum(1 for p in pairs if p["kind"] == "only-in-reference"),
        "only_in_product": sum(1 for p in pairs if p["kind"] == "only-in-product"),
        "median_multiplier_rel_err": (round(sorted(p["mult_rel_err"] for p in pairs if p.get("mult_rel_err") is not None)[
            max(0, len([p for p in pairs if p.get("mult_rel_err") is not None]) // 2)], 5)
            if any(p.get("mult_rel_err") is not None for p in pairs) else None),
        "our_adjustSource": rec.get("adjustSource"),
        "detail": json.dumps(pairs, ensure_ascii=False)[:1800],
    })

fields = sorted({k for r in rows for k in r})
with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

print("CSV ->", OUT, len(rows), "سطر")
print(f"{'نماد':9s} {'روز':>5s} {'لنگر':>9s} {'رویدادِ‌مرجع':>12s} {'رویدادِ‌ما':>10s} {'زوج‌شده':>7s} {'فقط‌مرجع':>9s} {'فقط‌ما':>7s} {'میانۀِ خطایِ نسبت':>16s}")
for r in rows:
    print(f"{r['symbol']:9s} {r['days_compared']:5d} {r['ref_anchor_ratio_at_last_day']:9.5f} {r['ref_events']:12d} "
          f"{r['product_events']:10d} {r['matched_within_7d']:7d} {r['only_in_reference']:9d} {r['only_in_product']:7d} "
          f"{(r['median_multiplier_rel_err'] if r['median_multiplier_rel_err'] is not None else 0):14.5f}")
n = max(1, len(rows))
print(f"\nمجموع: رویدادِ مرجع={totals['ref_events']}  رویدادِ ما={totals['our_events']}  زوج‌شده={totals['matched']}  "
      f"لنگرِ مرجع درِ آخرینِ روز (میانۀِ خطایِ نسبت)={totals['anchor_offset_pct'] / n:.3f}")
