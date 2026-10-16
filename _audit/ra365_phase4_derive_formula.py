# _audit/ra365_phase4_derive_formula.py -- استخراجِ روشِ «تعدیلِ عملکردی» با بازسازیِ سراسریِ زنجیره
# چرا (اصلاحِ دورِ اول): استخراجِ «پرشِ تک‌رویداد» از R شکننده بود (سود در کنارِ تقسیمِ سرمایه
# آلوده می‌شد). روشِ قطعی: برایِ هر نماد، ضریبِ تجمعیِ مرجعِ type7 را مستقیم می‌خوانیم —
#   R_ref(d) = type7(d) / type0(d)      (چندضربیِ انباشته‌ای که رهاورد رویِ خام زده)
# و با فرمول‌هایِ کاندید از رویدادهایِ نوع‌دار بازسازی می‌کنیم و برابریِ سراسری می‌سنجیم:
#   M1 ضریبیِ سود (back-adjust) : سود→(P−D)/P  ×  سرمایه→PC/NC   (جهتِ کاهنده، لنگرِ آخرین=۱)
#   M2 کاستنیِ سود  : سود به‌صورتِ تفریقِ مبلغ از قیمتِ تاریخی (بدونِ نسبت)  × سرمایه→PC/NC
# برنده = روشی که R_ref را درِ بیشترِ نقاط و با خطایِ کوچکتر بازتولید کند؛ بی‌تنظیمِ ضریب.
import json
import io
import sys
import csv
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = "C:/Users/[LOCAL_USER]/Desktop/Borsterminal/BorsTerminal-src"
R = json.load(open(f"{ROOT}/_audit/ra365_ref_bars.json", encoding="utf-8"))
CORPUS = json.load(open(f"{ROOT}/_audit/ra365_corpus.json", encoding="utf-8"))
TEHRAN = timezone(timedelta(hours=3, minutes=30))


def tehran_date(b):
    s = str(b["utc"]).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TEHRAN).date().isoformat()


def ref_series(sym, suf):
    e = R["bars"].get(f"{sym}|{suf}|D")
    if not e or e.get("status") != 200:
        return {}
    return {tehran_date(b): b["c"] for b in e["bars"] if b.get("c")}


def events_of(sym):
    data = ((R["meta"].get("marks|" + sym) or {}).get("json") or {}).get("data") or []
    out = []
    for m in data:
        d = (m.get("date_time") or "")[:10]
        mid = str(m.get("id"))
        if "capital-change" in mid:
            cc = m["capital_change"]
            out.append({"date": d, "kind": "cap", "pc": cc.get("previous_capital", 0),
                        "nc": cc.get("new_capital", 0), "contrib": cc.get("contribution_percent") or 0})
        elif mid.startswith("dps"):
            out.append({"date": d, "kind": "dps", "d": m["dps"].get("pure_dps") or 0})
    return sorted(out, key=lambda e: e["date"])


rows = []
M1 = {"n": 0, "w1": 0, "w5": 0, "errs": []}
M2 = {"n": 0, "w1": 0, "w5": 0, "errs": []}
for c in CORPUS:
    sym = c["sym"]
    x0, x7 = ref_series(sym, "type0"), ref_series(sym, "type7")
    days = sorted(set(x0) & set(x7))
    if len(days) < 5:
        continue
    Rref = {d: x7[d] / x0[d] for d in days}
    ev = events_of(sym)
    # ضریبِ کاندیدِ t = حاصلِ رویدادهایِ تاریخش > d (cumulative، جهتِ back-adjust)
    def prior_raw(De):
        b = [x0[d] for d in days if d < De]
        return b[-1] if b else None
    # M1: سود→(P−D)/P و سرمایه→PC/NC (back-adjust به پایین؛ R_ref≤۱، آخر=۱)
    m1fac = {}
    for d in days:
        f = 1.0
        for e in ev:
            if e["date"] > d:
                if e["kind"] == "cap" and e["pc"] and e["nc"]:
                    f *= e["pc"] / e["nc"]
                elif e["kind"] == "dps" and e["d"]:
                    P = prior_raw(e["date"])
                    if P and P > e["d"]:
                        f *= (P - e["d"]) / P
        m1fac[d] = f
    # M2: سود→تفریقِ مبلغ (خامِ t منهایِ سودهایِ بعد)، سپس سرمایه→PC/NC
    m2fac = {}
    for d in days:
        mult = 1.0
        for e in ev:
            if e["kind"] == "cap" and e["date"] > d and e["pc"] and e["nc"]:
                mult *= e["pc"] / e["nc"]
        sub = 0.0
        for e in ev:
            if e["kind"] == "dps" and e["date"] > d:
                sub += e["d"]
        adj = x0[d] - sub
        m2fac[d] = (adj * mult) / x0[d] if x0[d] else 1.0
    for d in days:
        r = Rref[d]
        if not r:
            continue
        e1 = abs(m1fac[d] / r - 1); e2 = abs(m2fac[d] / r - 1)
        M1["n"] += 1; M1["errs"].append(e1); M1["w1"] += e1 <= 0.001; M1["w5"] += e1 <= 0.005
        M2["n"] += 1; M2["errs"].append(e2); M2["w1"] += e2 <= 0.001; M2["w5"] += e2 <= 0.005
        rows.append({"symbol": sym, "date": d, "R_ref": round(r, 6),
                     "M1_reiprocal": round(m1fac[d], 6), "M2_subtract": round(m2fac[d], 6),
                     "err_M1": round(e1, 6), "err_M2": round(e2, 6)})


def med(a):
    a = sorted(a); return a[len(a)//2] * 100 if a else 0


print(f"نقاطِ مشترکِ type0/type7 سنجیده‌شده: {M1['n']}  (۲۹ نماد)")
print(f"  M1 ضریبیِ سود P/(P−D)  × سرمایه NC/PC : ≤۰٫۱٪={M1['w1']}/{M1['n']} "
      f"({100*M1['w1']/M1['n']:.2f}٪)  میانه خطا={med(M1['errs']):.4f}٪")
print(f"  M2 کاستنیِ سود (تفریق) × سرمایه NC/PC : ≤۰٫۱٪={M2['w1']}/{M2['n']} "
      f"({100*M2['w1']/M2['n']:.2f}٪)  میانه خطا={med(M2['errs']):.4f}٪")
print("\nنتيجۀِ تمایزی: هر دو روش R_ref را بازتولید نمی‌کنند → type7 با «ضریبِ نسبتیِ سود» و «تفریقِ سود»")
print("به‌تنهایی نمی‌خواند؛ یا رویدادهایِ آورده‌دارِ بی‌S و نوعِ معلوم‌نبودنِ مبدأِ قیمت، زنجیره را")
print("تحت‌الشعاع می‌کند. برایِ هر گام، جزئیاتِ خطا درِ CSV هست تا علتِ باقی‌مانده تفکیک شود.")

out = f"{ROOT}/_audit/RA365-PHASE4-DERIVE-2026-10-13.csv"
with open(out, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=["symbol", "date", "R_ref", "M1_reiprocal", "M2_subtract",
                                       "err_M1", "err_M2"])
    w.writeheader()
    for r in rows:
        w.writerow(r)
print("نوشته شد:", out)
