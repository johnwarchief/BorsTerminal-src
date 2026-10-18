# _audit/ra365_parity_matrix.py -- ماتریسِ تطبیقِ کندل: مرجع (ره‌آورد ۳۶۵) در برابرِ محصول (BorsTerminal)
# مرجع: _audit/ra365_ref_bars.json  (API خودِ ره‌آورد: type0 = بدونِ تعدیل، type7 = عملکردی)
# محصول: _audit/ra365_product_bars.json  (دو مسارۀِ خودِ محصول: live = /api/chart، db = /api/chart-db)
# بازوها (همه درِ یک پنجرۀِ یکسان سنجیده می‌شوند):
#   R0 خامِ زنده با مبنایِ آخرین    <-> type0   (سیب با سیبِ بی‌تعدیل)
#   R1 زنده × فاکتور، مبنایِ آخرین  <-> type7   (تعدیلِ عملکردیِ محصول در برابرِ مرجع)
#   R2 خامِ زنده با مبنایِ پایانی   <-> type0   (اثرِ کلیدِ مبنایِ قیمت)
#   R3 دیتابیسِ محلی (پایانی) خام   <-> type0   (همان چیزی که موتورِ FTS می‌بیند)
#   R4 دیتابیسِ محلی × فاکتور       <-> type7
# فقط اندازۀِ اختلاف؛ رفع درِ مرحلۀِ ۸.
import json
import sys
import io
import csv
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TEHRAN = timezone(timedelta(hours=3, minutes=30))
REF = "_audit/ra365_ref_bars.json"
PROD = "_audit/ra365_product_bars.json"
CORPUS = "_audit/ra365_corpus.json"
OUT_D = "_audit/RA365-PARITY-DAILY-2026-10-12.csv"
OUT_W = "_audit/RA365-PARITY-WEEKLY-2026-10-12.csv"
OUT_X = "_audit/RA365-PARITY-DIVERGE-2026-10-12.csv"
TOL = 0.0005
KEEP_FROM_D = "2024-01-01"
KEEP_FROM_W = "2023-01-01"


def tehran_date(utc_str):
    dt = datetime.fromisoformat(utc_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TEHRAN).date().isoformat()


def ref_series(ref, sym, suf, res):
    obj = ref["bars"].get(f"{sym}|{suf}|{res}")
    if not obj or not obj.get("bars"):
        return {}
    if res == "D":
        return {tehran_date(b["utc"]): b for b in obj["bars"]}
    return {b["utc"][:10]: b for b in obj["bars"]}


def prod_series(prod, sym, path_name, basis, adjust):
    """basis: 'last' | 'closing' -- هر دو کلید درِ پاسخِ محصول هست؛ last درِ مسارۀِ دیتابیس اغلب None است."""
    rec = prod[sym][path_name]
    fac = {f["time"]: f["factor"] for f in (rec.get("factors") or [])}
    vols = rec.get("volumes") or {}
    out = {}
    for c in rec.get("candles") or []:
        d = c["time"]
        f = fac.get(d, 1.0) if adjust else 1.0
        base = c.get("last") if basis == "last" else c.get("closing", c["close"])
        if base is None:
            base = c["close"]
        v = vols.get(d) if vols else c.get("volume")
        out[d] = {
            "o": c["open"] * f, "h": c["high"] * f, "l": c["low"] * f, "c": base * f,
            "h_raw": c.get("high_raw") or c["high"], "l_raw": c.get("low_raw") or c["low"],
            "v": v or 0, "last_raw": c.get("last"), "closing_raw": c.get("closing"),
        }
    return out


def week_key(date_str):
    y, m, d = map(int, date_str.split("-"))
    dt = datetime(y, m, d, tzinfo=TEHRAN)
    return (dt - timedelta(days=(dt.weekday() - 5) % 7)).date().isoformat()


def aggregate_weekly(daily):
    groups = {}
    for d, b in daily.items():
        groups.setdefault(week_key(d), []).append((d, b))
    out = {}
    for wk, items in groups.items():
        items.sort()
        out[wk] = {"o": items[0][1]["o"], "h": max(b["h"] for _, b in items),
                   "l": min(b["l"] for _, b in items), "c": items[-1][1]["c"],
                   "v": sum(b["v"] for _, b in items), "n": len(items),
                   "h_raw": max(b.get("h_raw", b["h"]) for _, b in items),
                   "l_raw": min(b.get("l_raw", b["l"]) for _, b in items),
                   "last_raw": items[-1][1].get("last_raw"), "closing_raw": items[-1][1].get("closing_raw")}
    return out


def pct_from_sorted(srt, q):
    if not srt:
        return 0.0
    return srt[min(len(srt) - 1, max(0, int(round(q * (len(srt) - 1)))))]


def compare(refmap, prodmap, sym, arm, diverge_rows, keep_from):
    refmap = {k: v for k, v in refmap.items() if k >= keep_from}
    prodmap = {k: v for k, v in prodmap.items() if k >= keep_from}
    common = sorted(set(refmap) & set(prodmap))
    if not common:
        return None
    res = {"symbol": sym, "arm": arm, "ref_bars": len(refmap), "prod_bars": len(prodmap), "common": len(common),
           "only_in_ref": len(set(refmap) - set(prodmap)), "only_in_prod": len(set(prodmap) - set(refmap)),
           "missing_dates_in_product": "|".join(sorted(set(refmap) - set(prodmap))[-12:])}
    hit = {"o": 0, "h": 0, "l": 0, "c": 0, "c_last": 0, "c_close": 0, "v": 0, "h_raw": 0}
    errs = []
    for d in common:
        r, p = refmap[d], prodmap[d]
        rc, pc = r["c"], p["c"]
        tol = max(abs(rc) * TOL, 0.6)
        if abs(r["o"] - p["o"]) <= tol:
            hit["o"] += 1
        if abs(r["h"] - p["h"]) <= tol:
            hit["h"] += 1
        if abs(r["l"] - p["l"]) <= tol:
            hit["l"] += 1
        if abs(rc - pc) <= tol:
            hit["c"] += 1
        if p.get("last_raw") is not None and abs(rc - p["last_raw"]) <= tol:
            hit["c_last"] += 1
        if p.get("closing_raw") is not None and abs(rc - p["closing_raw"]) <= tol:
            hit["c_close"] += 1
        if r.get("v") and p.get("v") and abs(r["v"] - p["v"]) <= abs(r["v"]) * 0.01:
            hit["v"] += 1
        if r["h"] and p.get("h_raw") is not None and abs(r["h"] - p["h_raw"]) <= max(abs(r["h"]) * TOL, 0.6):
            hit["h_raw"] += 1
        rel = abs(rc - pc) / rc if rc else 0.0
        errs.append((rel, d))
        if rel > 0.005:
            diverge_rows.append({"symbol": sym, "arm": arm, "date": d,
                                 "ref_o": r["o"], "ref_h": r["h"], "ref_l": r["l"], "ref_c": rc,
                                 "prod_o": p["o"], "prod_h": p["h"], "prod_l": p["l"], "prod_c": pc,
                                 "prod_last_raw": p.get("last_raw"), "prod_closing_raw": p.get("closing_raw"),
                                 "rel_err": round(rel, 5)})
    srt = sorted(e for e, _ in errs)
    res.update(open_match=hit["o"], high_match=hit["h"], low_match=hit["l"], close_match=hit["c"],
               ref_c_equals_prod_last_raw=hit["c_last"], ref_c_equals_prod_closing_raw=hit["c_close"],
               high_matches_prod_raw=hit["h_raw"], volume_match=hit["v"],
               median_rel_err=round(pct_from_sorted(srt, 0.5), 6),
               p95_rel_err=round(pct_from_sorted(srt, 0.95), 5),
               max_rel_err=round(srt[-1], 5),
               worst="; ".join(f"{d}:{e:.4f}" for e, d in sorted(errs, reverse=True)[:3]))
    return res


ARMS = [
    ("R0-زنده-آخرین-خام", "live", "last", False, "type0"),
    ("R1-زنده-آخرین-عملکردی", "live", "last", True, "type7"),
    ("R2-زنده-پایانی-خام", "live", "closing", False, "type0"),
    ("R3-دیتابیس-پایانی-خام", "db", "closing", False, "type0"),
    ("R4-دیتابیس-پایانی-عملکردی", "db", "closing", True, "type7"),
]


def main():
    ref = json.load(open(REF, encoding="utf-8"))
    prod = json.load(open(PROD, encoding="utf-8"))
    corpus = json.load(open(CORPUS, encoding="utf-8"))

    daily_rows, weekly_rows, diverge = [], [], []
    for c in corpus:
        sym = c["sym"]
        if sym not in prod:
            continue
        for label, path_name, basis, adjust, suf in ARMS:
            pm = prod_series(prod, sym, path_name, basis, adjust)
            row = compare(ref_series(ref, sym, suf, "D"), pm, sym, label, diverge, KEEP_FROM_D)
            if row:
                daily_rows.append(row)
            ww = aggregate_weekly({k: v for k, v in pm.items() if k >= "2022-01-01"})
            wrow = compare(ref_series(ref, sym, suf, "W"), ww, sym, label, diverge, KEEP_FROM_W)
            if wrow:
                wrow["basis"] = "هفتگیِ محصول از تجمیعِ روزانۀِ خودش"
                weekly_rows.append(wrow)

    for name, rows in ((OUT_D, daily_rows), (OUT_W, weekly_rows), (OUT_X, diverge)):
        if not rows:
            continue
        fields = sorted({k for r in rows for k in r})
        with open(name, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print("CSV ->", name, len(rows), "سطر")

    def table(rows_, title):
        print(f"\n=== {title} ===")
        print(f"{'بازو':28s} {'مشترک':>7s} {'O':>7s} {'H':>7s} {'L':>7s} {'C':>7s} {'حجم':>7s} {'میانه٪':>8s} {'p95٪':>8s} {'فقط‌در‌مرجع':>10s}")
        for label, *_ in ARMS:
            rs = [r for r in rows_ if r["arm"] == label]
            if not rs:
                continue
            n = sum(r["common"] for r in rs)
            g = lambda k: sum(r[k] for r in rs) / n
            print(f"{label:28s} {n:7d} {g('open_match'):7.1%} {g('high_match'):7.1%} {g('low_match'):7.1%} "
                  f"{g('close_match'):7.1%} {g('volume_match'):7.1%} "
                  f"{sum(r['median_rel_err'] for r in rs) / len(rs) * 100:8.3f} "
                  f"{sum(r['p95_rel_err'] for r in rs) / len(rs) * 100:8.3f} "
                  f"{sum(r['only_in_ref'] for r in rs):10d}")
        print("    تطبیقِ ستونِ close با دادۀِ خام:")
        for label, *_ in ARMS:
            rs = [r for r in rows_ if r["arm"] == label]
            if not rs:
                continue
            n = sum(r["common"] for r in rs)
            print(f"    {label:28s} ref_c==last_raw {sum(r['ref_c_equals_prod_last_raw'] for r in rs) / n:7.1%} "
                  f"ref_c==closing_raw {sum(r['ref_c_equals_prod_closing_raw'] for r in rs) / n:7.1%} "
                  f"ref_h==high_raw {sum(r['high_matches_prod_raw'] for r in rs) / n:7.1%}")

    table(daily_rows, "کندلِ روزانە (۲۰۲۴-۰۱-۰۱ به بعد، ۲۹ نماد)")
    table(weekly_rows, "کندلِ هفتگی (۲۰۲۳-۰۱-۰۱ به بعد، تجمیعِ شنبه‌آغاز)")


if __name__ == "__main__":
    main()
