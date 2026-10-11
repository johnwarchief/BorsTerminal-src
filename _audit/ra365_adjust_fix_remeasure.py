# _audit/ra365_adjust_fix_remeasure.py -- سنجشِ «پیش» و «پس»ِ زنجیرۀِ تعدیل
# چرا: رفعِ RC3 (تیزکردنِ ضریبِ گسستِ CSV با دفترِ رویدادِ مبدأِ TSETMC درِ
# `api/chart.py:_sharpen_events_with_ledger`) باید با عددِ خودش ثابت شود، نه با
# روایت. هر دو فایلِ محصول (`ra365_product_bars.json` = پیش از رفع،
# `ra365_product_bars_after.json` = پس از رفع) رویِ همان سریِ مرجعِ ذخیرۀِ ۱۴۰۵-۰۷-۲۰
# سنجیده می‌شوند؛ مرجع از قبل یخ‌زده است، پس مقایسه تکرارپذیر است.
# وزنِ آمار روی «تکتکِ کندل‌هایِ مشترک» است (میانگیِ میانه‌ها گمراه‌کننده است:
# نمادهایِ بی‌رویداد خطایِ صفر می‌دهند).
import json
import io
import sys
import csv
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = "C:/Users/Johnkallnaya/Desktop/Borsterminal/BorsTerminal-src"
R = json.load(open(f"{ROOT}/_audit/ra365_ref_bars.json", encoding="utf-8"))
CORPUS = json.load(open(f"{ROOT}/_audit/ra365_corpus.json", encoding="utf-8"))
BEFORE = json.load(open(f"{ROOT}/_audit/ra365_product_bars.json", encoding="utf-8"))
# «پس» با argv[1] قابلِ تعویض است تا همین سنجش برایِ ضبطِ هر قاعدۀِ تازه خوانده شود
AFTER = json.load(open(sys.argv[1] if len(sys.argv) > 1 else f"{ROOT}/_audit/ra365_product_bars_after.json",
                       encoding="utf-8"))
TOL = 0.0005
LEDGER_CSV = f"{ROOT}/_audit/RA365-LEDGER-RULE-2026-10-12.csv"


def tehran_date(b):
    s = str(b["utc"]).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=3, minutes=30))).date().isoformat()


def ref_series(sym, suf):
    e = R["bars"].get(f"{sym}|{suf}|D")
    if not e or e.get("status") != 200:
        return {}
    return {tehran_date(b): b["c"] for b in e["bars"] if b.get("c")}


def quant(a, q):
    if not a:
        return float("nan")
    return a[min(len(a) - 1, max(0, int(round(q * (len(a) - 1)))))]


def prod_series(live, adj, basis="last"):
    """{date: close} از پاسخِ خودِ محصول؛ adj=True یعنی ضریبِ زنجیره اعمال شود.

    مبنایِ نمایش با همان تعریفِ دورِ پیشینِ سنجش است (R1/R0 = «آخرین»، R4 = «پایانی»،
    چون درِ بانکِ محلی ستونِ «آخرین» برایِ تاریخِเก่า پر نیست) تا عددها با
    `RA365-STAGE3-SUMMARY-2026-10-12.csv` قابلِ مقایسه بمانند.
    """
    fac = {f["time"]: f["factor"] for f in (live.get("factors") or [])}
    out = {}
    for c in live["candles"]:
        base = c.get("last") if basis == "last" else c.get("closing", c.get("close"))
        out[c["time"]] = (base * fac.get(c["time"], 1.0)) if adj else base
    return out


def measure(prod, arm_adj, path, ref_suf, basis="last"):
    errs, per_sym, tol_hit = [], {}, 0
    n = 0
    for c in CORPUS:
        sym = c["sym"]
        rf = ref_series(sym, ref_suf)
        pd_ = prod_series(prod[sym][path], arm_adj, basis)
        common = sorted(set(rf) & set(pd_))
        se = []
        for d in common:
            rel = abs(rf[d] - pd_[d]) / rf[d] if rf[d] else 0.0
            se.append(rel)
            errs.append(rel)
            if abs(rf[d] - pd_[d]) <= max(abs(rf[d]) * TOL, 0.6):
                tol_hit += 1
        n += len(common)
        se.sort()
        per_sym[sym] = (len(common), quant(se, 0.5), quant(se, 0.9), se[-1] if se else 0.0)
    errs.sort()
    return {"bars": n, "within_tol_pct": 100.0 * tol_hit / n if n else 0.0,
            "median_pct": 100 * quant(errs, 0.5), "p90_pct": 100 * quant(errs, 0.9),
            "p99_pct": 100 * quant(errs, 0.99), "max_pct": 100 * errs[-1] if errs else 0.0,
            "per_sym": per_sym}


print("=" * 108)
print("۱) زنجیرۀِ عملکردیِ زنده (بازو R1: محصولِ تعدیل‌شده <-> مرجعِ type7)")
b1, a1 = measure(BEFORE, True, "live", "type7"), measure(AFTER, True, "live", "type7")
b0, a0 = measure(BEFORE, False, "live", "type0"), measure(AFTER, False, "live", "type0")
b4, a4 = measure(BEFORE, True, "db", "type7", "closing"), \
    measure(AFTER, True, "db", "type7", "closing")

for label, b, a in (("R1 عملکردیِ زنده", b1, a1), ("R0 خامِ زنده (باید دست‌نخورده)", b0, a0),
                    ("R4 عملکردیِ دیتابیس", b4, a4)):
    print(f"\n{label}")
    print(f"  پیش: درتلورانس {b['within_tol_pct']:.2f}٪  میانه {b['median_pct']:.4f}٪  "
          f"p90 {b['p90_pct']:.4f}٪  p99 {b['p99_pct']:.4f}٪  بیشینه {b['max_pct']:.4f}٪")
    print(f"  پس : درتلورانس {a['within_tol_pct']:.2f}٪  میانه {a['median_pct']:.4f}٪  "
          f"p90 {a['p90_pct']:.4f}٪  p99 {a['p99_pct']:.4f}٪  بیشینه {a['max_pct']:.4f}٪")
    print(f"  دلتا: میانه {a['median_pct'] - b['median_pct']:+.4f}٪  "
          f"p90 {a['p90_pct'] - b['p90_pct']:+.4f}٪  p99 {a['p99_pct'] - b['p99_pct']:+.4f}٪  "
          f"بیشینه {a['max_pct'] - b['max_pct']:+.4f}٪")

print("\n" + "=" * 108)
print("۲) بهتر/بدترشدنِ هر نماد (میانۀِ خطایِ R1، درصدِ کندل)")
rows = []
for c in CORPUS:
    sym = c["sym"]
    nb = 100 * b1["per_sym"][sym][1]
    na = 100 * a1["per_sym"][sym][1]
    ev_b = BEFORE[sym]["live"].get("adjustEvents") or []
    ev_a = AFTER[sym]["live"].get("adjustEvents") or []
    cap = AFTER[sym]["live"].get("adjustCapability") or {}
    sharp_n = cap.get("ledger_sharpened")
    if sharp_n is None:   # فایلِ پیشینِ capability را ضبط نکرده بود: از خودِ رویدادها می‌خوانیم
        sharp_n = sum(1 for e in ev_a if str(e.get("source")) in ("priceAdjust", "shareChange"))
    collapse_n = cap.get("ledger_ambiguous")
    if collapse_n is None:
        collapse_n = max(0, len(ev_b) - len(ev_a))
    rows.append({"symbol": sym, "bars": a1["per_sym"][sym][0],
                 "median_before_pct": round(nb, 4), "median_after_pct": round(na, 4),
                 "delta_pct": round(na - nb, 4),
                 "p90_before_pct": round(100 * b1["per_sym"][sym][2], 4),
                 "p90_after_pct": round(100 * a1["per_sym"][sym][2], 4),
                 "events_before": len(ev_b), "events_after": len(ev_a),
                 "ledger_sharpened": cap.get("ledger_sharpened"),
                 "ledger_ambiguous": cap.get("ledger_ambiguous"),
                 "adjust_source_after": AFTER[sym]["live"].get("adjustSource")})
rows.sort(key=lambda r: r["delta_pct"])
better = [r for r in rows if r["delta_pct"] < -0.0005]
worse = [r for r in rows if r["delta_pct"] > 0.0005]
print(f"  بهتر: {len(better)}  بدتر: {len(worse)}  بی‌تغییر: {len(rows) - len(better) - len(worse)}")
for r in rows[:8]:
    print(f"  {r['symbol']:8s} میانه {r['median_before_pct']:.4f} → {r['median_after_pct']:.4f} "
          f"({r['delta_pct']:+.4f}٪)  p90 {r['p90_before_pct']:.4f} → {r['p90_after_pct']:.4f}  "
          f"رویداد {r['events_before']}→{r['events_after']}  تیز={r['ledger_sharpened']} "
          f"مبهم={r["ledger_ambiguous"]}  {r['adjust_source_after']}")
print("  --- بدترین‌ها ---")
for r in rows[-6:]:
    print(f"  {r['symbol']:8s} میانه {r['median_before_pct']:.4f} → {r['median_after_pct']:.4f} "
          f"({r['delta_pct']:+.4f}٪)  p90 {r['p90_before_pct']:.4f} → {r['p90_after_pct']:.4f}  "
          f"رویداد {r['events_before']}→{r['events_after']}  تیز={r['ledger_sharpened']} "
          f"مبهم={r["ledger_ambiguous"]}  {r['adjust_source_after']}")

print("\n" + "=" * 108)
print("۳) گام‌هایِ مرجعِ جدولِ تعدیل (RA365-LEDGER-RULE): ضریبِ ما در برابرِ گامِ مرجع")
steps = list(csv.DictReader(open(LEDGER_CSV, encoding="utf-8-sig")))
ev_after = {s: {str(e["date"]): float(e["ratio"]) for e in (AFTER[s]["live"].get("adjustEvents") or [])}
            for s in AFTER}
ev_before = {s: {str(e["date"]): float(e["ratio"]) for e in (BEFORE[s]["live"].get("adjustEvents") or [])}
             for s in BEFORE}


def nearest_step(events, sym, d):
    """ضریبِ رویدادِ نزدیک‌ترین تاریخ درِ پنجرۀِ ±۱۲ روز (همان درِ سنجشِ پیشین)."""
    if sym not in events or not events[sym]:
        return None
    try:
        target = datetime.strptime(d, "%Y-%m-%d").date()
    except Exception:
        return None
    best = None
    for ed, rv in events[sym].items():
        try:
            dd = abs((datetime.strptime(ed, "%Y-%m-%d").date() - target).days)
        except Exception:
            continue
        if dd <= 12 and (best is None or dd < best[0]):
            best = (dd, rv)
    return (1.0 / best[1]) if best and best[1] else None


n_cmp = 0
be, ae = [], []
for s in steps:
    sym, rs = s["symbol"], float(s["ref_step"])
    ob = nearest_step(ev_before, sym, s["step_date"])
    oa = nearest_step(ev_after, sym, s["step_date"])
    if ob and oa:
        be.append(abs(ob / rs - 1.0))
        ae.append(abs(oa / rs - 1.0))
        n_cmp += 1
be.sort()
ae.sort()
print(f"  گام‌هایِ قابلِ مقایسه: {n_cmp} از {len(steps)}")
if n_cmp:
    print(f"  پیش: میانه {100*quant(be,0.5):.4f}٪  p90 {100*quant(be,0.9):.4f}٪  بیشینه {100*be[-1]:.4f}٪")
    print(f"  پس : میانه {100*quant(ae,0.5):.4f}٪  p90 {100*quant(ae,0.9):.4f}٪  بیشینه {100*ae[-1]:.4f}٪")
    print(f"  گام‌هایِ زیرِ ۰٫۱٪: پیش {sum(1 for x in be if x<0.001)}  پس {sum(1 for x in ae if x<0.001)}")

_OUT_CSV = sys.argv[2] if len(sys.argv) > 2 else f"{ROOT}/_audit/RA365-ADJUST-FIX-2026-10-12.csv"
with open(_OUT_CSV, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    for r in rows:
        w.writerow(r)
print(f"\nنوشته شد: {_OUT_CSV}")
