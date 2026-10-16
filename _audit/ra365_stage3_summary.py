# _audit/ra365_stage3_summary.py -- عددهایِ وزن‌دارِ مرحلۀِ ۳ (خطایِ تکتکِ کندل‌ها، نه میانگیِ میانه‌ها)
# چرا: درِ RA365-PARITY-DAILY «میانگیِ میانه‌ها» نمادهایی را هم می‌شمارد که درِ پنجره هیچ
# رویدادِ تعدیل ندارند و فاکتورشان ۱ است (پس خطایِ صفر). چنین میانگیِ گمراه‌کننده است.
# اینجا خطا روی همهٔ کندل‌هایِ مشترک وزن می‌خورد و نمادها به دو دستهٔ «رویداددار» و
# «بی‌رویداد» جدا می‌شوند.
import json
import io
import sys
import csv
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = "C:/Users/[LOCAL_USER]/Desktop/Borsterminal/BorsTerminal-src"
R = json.load(open(f"{ROOT}/_audit/ra365_ref_bars.json", encoding="utf-8"))
P = json.load(open(f"{ROOT}/_audit/ra365_product_bars.json", encoding="utf-8"))
CORPUS = json.load(open(f"{ROOT}/_audit/ra365_corpus.json", encoding="utf-8"))
TOL = 0.0005


def tehran_date(b):
    s = str(b["utc"]).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=3, minutes=30))).date().isoformat()


def ref_close(sym, suf):
    e = R["bars"].get(f"{sym}|{suf}|D")
    if not e or e.get("status") != 200:
        return {}
    return {tehran_date(b): b["c"] for b in e["bars"] if b.get("c")}


def quant(a, q):
    if not a:
        return float("nan")
    return a[min(len(a) - 1, max(0, int(round(q * (len(a) - 1)))))]


def prod_series(sym, path, basis):
    live = P[sym][path]
    fac = {f["time"]: f["factor"] for f in (live.get("factors") or [])}
    out = {}
    for c in live["candles"]:
        base = c.get("last") if basis == "last" else c.get("closing", c.get("close"))
        out[c["time"]] = (base, c.get("close"), fac.get(c["time"], 1.0))
    return out


arms = [
    ("R0 خامِ زنده (مبنای آخرین) <-> type0", "live", "last", False),
    ("R1 عملکردیِ زنده <-> type7", "live", "last", True),
    ("R1b عملکردیِ زنده با مبنای پایانی <-> type7", "live", "closing", True),
    ("R3 خامِ دیتابیس (مبنای پایانی) <-> type0", "db", "closing", False),
    ("R4 عملکردیِ دیتابیس <-> type7", "db", "closing", True),
]

ev_count = {c["sym"]: len(P[c["sym"]]["live"].get("adjustEvents") or []) for c in CORPUS}
print("تعدادِ رویدادهایِ تعدیلِ محصول درِ هر نماد (پنجرۀِ کاملِ CSV):")
print("  " + ", ".join(f"{k}={v}" for k, v in ev_count.items()))
no_ev = [k for k, v in ev_count.items() if v == 0]
print(f"  نمادهایِ بی‌رویداد: {len(no_ev)} -> {no_ev}")

rows = []
for label, path, basis, adj in arms:
    ref_suf = "type7" if adj else "type0"
    errs, errs_ev, errs_no = [], [], []
    tol_hit = tol_hit_ev = n_ev = n_no = 0
    per_sym = []
    for c in CORPUS:
        sym = c["sym"]
        rf = ref_close(sym, ref_suf)
        pd_ = prod_series(sym, path, basis)
        common = sorted(set(rf) & set(pd_))
        se, hit = [], 0
        for d in common:
            base, raw_close, f = pd_[d]
            ours = (base * f) if adj else base
            rel = abs(ours - rf[d]) / rf[d] if rf[d] else 0.0
            se.append(rel)
            if abs(ours - rf[d]) <= max(abs(rf[d]) * TOL, 0.6):
                hit += 1
            (errs_ev if ev_count[sym] else errs_no).append(rel)
            if ev_count[sym]:
                n_ev += 1
            else:
                n_no += 1
        se.sort()
        errs.extend(se)
        tol_hit += hit
        tol_hit_ev += hit if ev_count[sym] else 0
        per_sym.append((sym, len(common), hit, quant(se, 0.5), quant(se, 0.95), se[-1] if se else 0))
    eev = sorted(errs_ev)
    print("\n" + "=" * 100)
    print(label)
    print(f"  همهٔ کندل‌هایِ مشترک: {len(errs)}  درِ تلورانسِ ۰٫۰۵٪: {100*tol_hit/len(errs):.1f}%  "
          f"میانه={100*quant(sorted(errs),0.5):.4f}٪  p90={100*quant(sorted(errs),0.9):.4f}٪  "
          f"p99={100*quant(sorted(errs),0.99):.4f}٪")
    if eev:
        print(f"  فقط نمادهایِ رویداددار: {len(eev)} کندل  میانه={100*quant(eev,0.5):.4f}٪  "
              f"p90={100*quant(eev,0.9):.4f}٪  p99={100*quant(eev,0.99):.4f}٪  بیشینه={100*eev[-1]:.4f}٪")
    if errs_no:
        en = sorted(errs_no)
        print(f"  فقط نمادهایِ بی‌رویداد: {len(en)} کندل  میانه={100*quant(en,0.5):.4f}٪  "
              f"بیشینه={100*en[-1]:.4f}٪")
    rows.append({"arm": label, "bars": len(errs), "within_tol_pct": round(100 * tol_hit / len(errs), 2),
                 "median_err_pct": round(100 * quant(sorted(errs), 0.5), 4),
                 "p90_err_pct": round(100 * quant(sorted(errs), 0.9), 4),
                 "p99_err_pct": round(100 * quant(sorted(errs), 0.99), 4),
                 "median_with_events_pct": round(100 * quant(eev, 0.5), 4) if eev else "",
                 "p99_with_events_pct": round(100 * quant(eev, 0.99), 4) if eev else "",
                 "max_with_events_pct": round(100 * (eev[-1] if eev else 0), 4)})

with open(f"{ROOT}/_audit/RA365-STAGE3-SUMMARY-2026-10-12.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    for r in rows:
        w.writerow(r)
print("\nنوشته شد: RA365-STAGE3-SUMMARY-2026-10-12.csv")
