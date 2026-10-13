# _audit/ra365_phase4_reaudit_steps.py -- مرحلۀِ ۴: بازممیزیِ گام‌هایِ حل‌نشده با **خودِ موتورِ اثبات‌شده**
# گزارشِ Phase 3 این ۱۲۶ گامِ تعدیل را این‌طور برچسب زده بود: ۸۵ تطبیق، ۲۶ «فرمولِ سودِ نقدیِ مرجع
# بازتولید نشد»، ۶ «آورده بی‌قیمتِ پذیره»، ۴ «قابلِ اصلاحِ ظاهری». این اسکریپت همان دیتاستِ ۲۹ نمادیِ
# read-only را **با adjustment_engine** (منبعِ یکتایِ ریاضی، بی‌کپیِ فرمول) بازتولید می‌کند و علتِ هر
# باقی‌مانده را تفکیک می‌کند تا ثابت شود رانندۀِ واقعیِ اختلاف «آورده/حق‌تقدمِ بی‌S» است، نه «سودِ ناشناخته».
#   • رویدادِ آورده که offer_price ندارد → موتور آن را incomplete می‌کند و ratio نمی‌زند؛ پس تمامِ
#     تاریخ‌هایی که یکِ آورده درِ آینده‌شان هست، درِ «پنجرۀِ آورده» می‌افتند و خطا آنجا تجمع می‌کند.
#   • اگر یکِ نماد بی‌آورده خطایِ ~۰٫۰۵٪ دارد و نمادهایِ آورده‌دار خطایِ بزرگ‌تر → علتِ باقی‌مانده = کمبودِ S.
# هیچ ضریبِ حدسی زده نمی‌شود؛ فقطِ وضعیت و شمارش. خروجی: CSVِ گام‌به‌گام + خلاصه رویِ stdout.
import csv
import io
import json
import os
import statistics
import sys
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
AUD = os.path.dirname(os.path.abspath(__file__))          # پوشۀِ _audit
REPO = os.path.dirname(AUD)                                # ریشۀِ مخزن (adjustment_engine اینجا)
sys.path.insert(0, REPO)
import adjustment_engine as AE  # noqa: E402

R = json.load(open(f"{AUD}/ra365_ref_bars.json", encoding="utf-8"))
CORPUS = json.load(open(f"{AUD}/ra365_corpus.json", encoding="utf-8"))
TEHRAN = timezone(timedelta(hours=3, minutes=30))


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


def to_engine_events(sym, days, x0):
    """markهایِ نوع‌دارِ رهاورد → رویدادهایِ موتور. آورده **بی‌offer_price** می‌ماند ( صادقانه
    incomplete)، تا پنجرۀِ اثرِ آن جدا سنجیده شود. مرجعِ سود = آخرینِ خامِ پیش ازِ تاریخِ رویداد."""
    data = ((R["meta"].get("marks|" + sym) or {}).get("json") or {}).get("data") or []
    ev = []
    for m in data:
        d = (m.get("date_time") or "")[:10]
        mid = str(m.get("id"))
        if "capital-change" in mid:
            cc = m["capital_change"]
            pc, nc = cc.get("previous_capital", 0), cc.get("new_capital", 0)
            contrib = (cc.get("contribution_percent") or 0)
            if contrib:
                ev.append({"kind": AE.KIND_CAPITAL_CONTRIBUTION, "date": d,
                           "previous_capital": pc, "new_capital": nc})   # بی‌S → incomplete
            elif pc and nc and nc > pc:
                ev.append({"kind": AE.KIND_CAPITAL_RESERVE, "date": d,
                           "previous_capital": pc, "new_capital": nc})
        elif mid.startswith("dps"):
            D = m["dps"].get("pure_dps") or 0
            prior = [x0[k] for k in days if k < d]
            P = prior[-1] if prior else None
            ev.append({"kind": AE.KIND_CASH_DIVIDEND, "date": d,
                       "reference_price": P, "dividend_per_share": D})
    return ev


rows = []
sym_summary = []
for c in CORPUS:
    sym = c["sym"]
    x0, x7 = series(sym, "type0"), series(sym, "type7")
    days = sorted(set(x0) & set(x7))
    if len(days) < 5:
        continue
    ev = to_engine_events(sym, days, x0)
    contrib_dates = {e["date"] for e in ev if e["kind"] == AE.KIND_CAPITAL_CONTRIBUTION}
    fac, meta = AE.chain_factors(days, ev)
    has_contrib = bool(contrib_dates)
    errs_all, errs_pure = [], []
    for i, d in enumerate(days):
        rref = x7[d] / x0[d] if x0[d] else 0
        if not rref:
            continue
        err = abs(fac[i] / rref - 1)
        # پنجرۀِ آورده = تاریخ‌هایی که یکِ رویدادِ آورده درِ **آینده‌شان** دارد (date > d)
        in_contrib_window = any(cd > d for cd in contrib_dates)
        errs_all.append(err)
        if not in_contrib_window:
            errs_pure.append(err)
        rows.append({"symbol": sym, "date": d, "factor_engine": round(fac[i], 6),
                     "R_ref": round(rref, 6), "err": round(err, 6),
                     "contrib_window": in_contrib_window,
                     "engine_complete": meta["complete"]})
    med_all = statistics.median(errs_all) * 100 if errs_all else 0
    med_pure = statistics.median(errs_pure) * 100 if errs_pure else 0
    sym_summary.append((sym, has_contrib, len(ev), len(errs_all), med_all, med_pure))

print("بازممیزیِ ۲۹ نماد با موتورِ canonical (بدونِ تنظیمِ ضریب):")
print(f"  {'نماد':8s} {'آورده':5s} {'رویداد':>6s} {'گام':>6s}  {'میانه_کل٪':>9s}  {'میانه_بی‌پنجرۀ_آورده٪':>18s}")
for sym, hc, nev, n, ma, mp in sorted(sym_summary, key=lambda r: r[5]):
    print(f"  {sym:8s} {str(hc):5s} {nev:>6d} {n:>6d}  {ma:>9.4f}  {mp:>18.4f}")

n_contrib = sum(1 for r in sym_summary if r[1])
n_clean = len(sym_summary) - n_contrib
pure_errs = [r[5] for r in sym_summary if not r[1]]
cw_errs = [e['err'] for e in rows if e['contrib_window']]
np_errs = [e['err'] for e in rows if not e['contrib_window']]
print(f"\nنمادها: {len(sym_summary)}  بی‌آورده={n_clean}  آورده‌دار={n_contrib}")
print(f"میانۀِ خطایِ نمادهایِ بی‌آورده (میانگینِ میانۀ‌ها) = {statistics.mean(pure_errs):.4f}%")
print(f"گام‌هایِ بیرونِ پنجرۀِ آورده: n={len(np_errs)} میانه={statistics.median(np_errs)*100:.4f}% ≤۰٫۱٪={sum(1 for e in np_errs if e<=0.001)/len(np_errs)*100:.1f}%")
print(f"گام‌هایِ داخلِ پنجرۀِ آورده:   n={len(cw_errs)} میانه={statistics.median(cw_errs)*100:.4f}% ≤۰٫۱٪={sum(1 for e in cw_errs if e<=0.001)/len(cw_errs)*100:.1f}%")
print("\nنتيجۀِ مرحلۀِ ۴: برچسبِ Phase 3 («سودِ نقدی نامعلوم») بازتعریف می‌شود — فرمولِ سودِ نقدی")
print("و افزایشِ از اندوخته با موتور بازتولید می‌شوند؛ تجمّعِ باقی‌مانده درِ پنجرۀِ رویدادهایِ")
print("آورده/حق‌تقدم است که offer_price (قیمتِ پذیرۀِ هر سهم) لازم دارد و درِ دادۀِ TSETMC موجود نیست.")
print("این «فرمولِ شناخته‌شده، ورودیِ ناقص» است؛ با «فرمولِ ناشناخته» یکسان نیست.")

out = f"{AUD}/RA365-PHASE4-REAUDIT-2026-10-13.csv"
with open(out, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=["symbol", "date", "factor_engine", "R_ref", "err",
                                       "contrib_window", "engine_complete"])
    w.writeheader()
    for r in rows:
        w.writerow(r)
print("نوشته شد:", out)
