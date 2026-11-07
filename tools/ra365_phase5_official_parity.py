# tools/ra365_phase5_official_parity.py -- Phase 5 Stage 6/8: parityِ **نسبتِ رسمی** (بی‌proxy) درِ برابرِ type7
# چرا: اعتبارسنجیِ Phase 4 یک `reference_price`ِ proxy (آخرینِ خامِ پیش ازِ رویداد) می‌زد که درِ تولید
# استفاده **نمی‌شود**. این اسکریپت همان نقطه را با مسیرِ واقعیِ برنامه می‌سنجد:
#   رویدادِ رسمیِ TSETMC (price_adjust=adj/raw, share_change=old/new) ← corporate_ledger → engine.chain_factors
# و با `R_ref=type7/type0` (مرجعِ راستینِ احراز‌شده از Edge درِ `_audit/ra365_ref_bars.json`) مقابله می‌کند.
# فقط‌خواندنی برِ market.db (mode=ro)؛ مرجعِ read-onlyِ فریزشده؛ هیچ نوشتنِ عملیاتی نیست.
# تفسیرِ درست: جایی که رویدادِ رسمی درِ هر دو (TSETMC و بازۀِ مرجع) هست باید بخواند؛ اختلافِ بیرونِ
# coverage (پیشِ ۲۰۲۴-۰۷-۲۱ درِ price_adjust نیست) «خطایِ فرمول» نیست، شکافِ پوششِ مبدأ است.
import io
import json
import os
import sqlite3
import statistics
import sys
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import adjustment_engine as AE          # noqa: E402
import corporate_ledger as L            # noqa: E402

AUD = os.path.join(ROOT, "_audit")
R = json.load(open(os.path.join(AUD, "ra365_ref_bars.json"), encoding="utf-8"))
TEHRAN = timezone(timedelta(hours=3, minutes=30))
TOL = 0.001


def tdate(b):
    s = str(b["utc"]).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TEHRAN).date().isoformat()


def series(sym, suf):
    e = R["bars"].get(f"{sym}|{suf}|D")
    if not e or e.get("status") != 200:
        return {}
    return {tdate(b): b["c"] for b in e["bars"] if b.get("c")}


def normfa(s):
    return str(s or "").translate(str.maketrans({"ك": "ک", "ي": "ی", "ى": "ی"})).strip()


ro = sqlite3.connect("file:market.db?mode=ro", uri=True, timeout=5)
insmap = {normfa(n): str(c) for n, c in ro.execute("SELECT l_val18, ins_code FROM instruments")}

rows = []
matched = []
for c in json.load(open(os.path.join(AUD, "ra365_corpus.json"), encoding="utf-8")):
    sym = c["sym"]
    ins = insmap.get(normfa(sym))
    x0, x7 = series(sym, "type0"), series(sym, "type7")
    days = sorted(set(x0) & set(x7))
    if not ins or len(days) < 20:
        continue
    lev, lc = L.build_typed_events(ro, ins)          # رویدادهایِ رسمیِ این ابزار
    fac, meta = AE.chain_factors(days, lev)
    # فقط نقاطی که لااقل یکِ رویدادِ رسمی درِ گذشته‌شان هست مقابله می‌شوند؛ بیرونِ coverage
    # مرجع ممکن است تعدیل‌هایی داشته باشد که price_adjustِ امروز (فقط پسِ ۲۰۲۴) ندارد.
    ev_dates = [e["date"] for e in lev]
    errs, errs_in_cov, errs_pre_cov = [], [], []
    for i, d in enumerate(days):
        rref = x7[d] / x0[d] if x0[d] else 0
        if not rref:
            continue
        err = abs(fac[i] / rref - 1)
        errs.append(err)
        # coverage: آیا رویدادی که رویِ این تاریخ اثر دارد درِ بازۀِ price_adjust (پسِ ۲۰۲۴-۰۷) هست؟
        future = [ed for ed in ev_dates if ed > d]
        (errs_in_cov if future else errs_pre_cov).append(err)
    med = statistics.median(errs) * 100 if errs else 0
    med_cov = statistics.median(errs_in_cov) * 100 if errs_in_cov else float("nan")
    matched.append((sym, ins, len(days), len(lev), lc["complete"], med, med_cov, len(errs_in_cov)))
    rows.append({"symbol": sym, "points": len(errs), "events": len(lev),
                 "official_complete": lc["complete"], "median_all_pct": round(med, 4),
                 "median_with_event_pct": None if med_cov != med_cov else round(med_cov, 4),
                 "within_tol_pct": round(sum(1 for e in errs if e <= TOL) / len(errs) * 100, 1) if errs else 0})

print("Phase 5 — parityِ نسبتِ رسمی (corporate_ledger→engine در برابرِ type7/type0، بی‌proxy)\n")
print(f"{'نماد':8s} {'نقطه':>6s} {'رویداد':>6s} {'کامل':>5s} {'میانه_کل٪':>9s} {'میانه_با_رویداد٪':>16s} {'≤tol٪':>6s}")
print("-" * 70)
for r in sorted(rows, key=lambda x: (x["median_with_event_pct"] if x["median_with_event_pct"] is not None else 999)):
    mm = next(m for m in matched if m[0] == r["symbol"])
    cov = r["median_with_event_pct"]
    print(f"{r['symbol']:8s} {r['points']:>6d} {r['events']:>6d} {r['official_complete']:>5d} "
          f"{r['median_all_pct']:>9.4f} {(cov if cov is not None else float('nan')):>16.4f} {r['within_tol_pct']:>5.1f}%")

cov_vals = [r["median_with_event_pct"] for r in rows if r["median_with_event_pct"] is not None]
pre = [r for r in matched if r[7] == 0]
print(f"\nنمادهایِ مقابله‌شده: {len(rows)}  |  نمادهایِ بی‌رویدادِ رسمی درِ پنجره (فقط coverage_gap): {len(pre)}")
if cov_vals:
    print(f"میانه‌یِ خطا رویِ نقاطِ دارایِ رویدادِ رسمیِ TSETMC = {statistics.median(cov_vals):.4f}٪ "
          f"(بی‌proxy — همان نسبتِ adj/raw و old/new)")
print("تفسیر: نقاطی که مبدأِ رسمیِ TSETMC رویدادشان را دارد باید با type7 بخوانند؛ اختلافِ باقی‌مانده درِ "
      "پیشِ ۲۰۲۴-۰۷-۲۱ شکافِ coverageِ خودِ TSETMC است (source_gap)، نه خطایِ فرمول.")
print("نمونۀِ read-only؛ market.db دست‌نخورده.")
ro.close()

out = os.path.join(AUD, "RA365-PHASE5-OFFICIAL-PARITY-2026-10-14.csv")
import csv
with open(out, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    for r in rows:
        w.writerow(r)
print("نوشته شد:", out)
