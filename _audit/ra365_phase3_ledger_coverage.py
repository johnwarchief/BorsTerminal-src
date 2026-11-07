# _audit/ra365_phase3_ledger_coverage.py -- تکلیفِ هر گامِ واگرا: «منبعِ اصلاح درِ بانک هست؟» یا «داده نیست»
# چرا: مرحلۀِ ۲ ثابت کرد گروه‌بندیِ بلوکِ VOL= هویتِ رویداد را درست می‌کند، ولی وزنِ خطایِ
# R1 (تعدیلِ عملکردی) جابه‌جا نشد. علتِ باقی‌مانده این است که مرجعِ رهاوردِ type7 زنجیرۀ
# تعدیلش را از «دفترِ شرکتیِ نوع‌دار» می‌سازد (افزایشِ سرمایه با تفکیکِ ذخیره/آورده،
# سودِ نقدیِ خالصِ هر سهم) و ضریبِ خودی از گسستِ «قیمت پایه» درِ CSVِ TSETMC می‌آید
# (ردِپِردِ گرد). این سنجشِ فقط‌خواندنی، هر گامِ واگرا را به یکی از این سطل‌ها منتسب
# می‌کند تا داوری «رفع‌کردنی» از «بدونِ منبع/مهارِ دسترسی» جدا شود.
#
# خروجی هیچ عددی را تغییر نمی‌دهد و هیچ رویدادی را جابه‌جا نمی‌کند؛ فقط دسته‌بندی و شمارش.
# داده‌ها: snapshotِ یخ‌زده (ref/product/corpus) + market.db با mode=ro&immutable=1 (فقط خواندن).
import json
import io
import sys
import csv
import sqlite3
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = "C:/Users/Johnkallnaya/Desktop/Borsterminal/BorsTerminal-src"
R = json.load(open(f"{ROOT}/_audit/ra365_ref_bars.json", encoding="utf-8"))
P = json.load(open(f"{ROOT}/_audit/ra365_product_bars.json", encoding="utf-8"))
CORPUS = json.load(open(f"{ROOT}/_audit/ra365_corpus.json", encoding="utf-8"))
DB = f"{ROOT}/market.db"

STEP_TOL = 0.0025     # آستانۀِ تشخیصِ گام (نه آستانۀِ پذیرش)
AGREE = 0.0025        # «گامِ مرجع از فرمولِ دفتر بازسازی شد»
SOURCE_WINDOW = 12    # روز: ردیفِ مبدأ درِ بانکِ خودی درِ هم‌این پنجره؟
TEHRAN = timezone(timedelta(hours=3, minutes=30))

# پوششِ مبدأِ خودی: نماد -> تاریخ‌هایِ ردیفِ share_change (افزایشِ سرمایه) و price_adjust (سودِ تعدیل‌شده)
con = sqlite3.connect(f"file:{DB}?mode=ro&immutable=1", uri=True)
share_dates, padj_dates = {}, {}
for sym in [c["sym"] for c in CORPUS]:
    row = con.execute("SELECT ins_code FROM instruments WHERE l_val18=? OR l_val30=?",
                      (sym, sym)).fetchone()
    if not row:
        continue
    ins = str(row[0])
    for t, store in (("share_change_events", share_dates), ("price_adjust_events", padj_dates)):
        for (d,) in con.execute(f"SELECT d_even FROM {t} WHERE ins_code=?", (ins,)):
            s = str(d or "").strip()
            if len(s) == 8 and s.isdigit():
                store.setdefault(sym, set()).add(f"{s[:4]}-{s[4:6]}-{s[6:]}")
con.close()


def tehran_date(b):
    s = str(b["utc"]).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TEHRAN).date().isoformat()


def as_date(x):
    return datetime.strptime(x[:10], "%Y-%m-%d").date()


def ref_series(sym, suf):
    e = R["bars"].get(f"{sym}|{suf}|D")
    if not e or e.get("status") != 200:
        return {}
    return {tehran_date(b): b["c"] for b in e["bars"] if b.get("c")}


def ledger_of(sym):
    data = ((R["meta"].get("marks|" + sym) or {}).get("json") or {}).get("data") or []
    out = []
    for m in data:
        d = (m.get("date_time") or "")[:10]
        mid = str(m.get("id"))
        if "capital-change" in mid:
            out.append((d, "capital", m["capital_change"]))
        elif mid.startswith("dps"):
            out.append((d, "dps", m["dps"]))
    return sorted(out)


def has_source(store, sym, d):
    ds = store.get(sym, set())
    return any(abs((as_date(d) - as_date(x)).days) <= SOURCE_WINDOW for x in ds)


rows = []
bucket = {}
for c in CORPUS:
    sym = c["sym"]
    x0, x7 = ref_series(sym, "type0"), ref_series(sym, "type7")
    common = sorted(set(x0) & set(x7))
    if len(common) < 5:
        continue
    raw = {d: x7[d] / x0[d] for d in common}
    anchor = raw[common[-1]]
    ratio = {d: v / anchor for d, v in raw.items()}
    ours = sorted(((e["date"][:10], e["ratio"]) for e in (P[sym]["live"].get("adjustEvents") or [])))
    led = ledger_of(sym)
    prev = common[0]
    for i in range(1, len(common)):
        d, dp = common[i], common[i - 1]
        st = ratio[d] / ratio[dp]
        if abs(st - 1) <= STEP_TOL:
            continue
        cand = [(ld, k, v) for ld, k, v in led if 0 <= (as_date(d) - as_date(ld)).days <= 150]
        cand.sort(key=lambda z: (as_date(d) - as_date(z[0])).days)
        near = cand[0] if cand else None
        # گامِ خودیِ درِ پنجره: حاصل‌ضربِ نسبت‌هایِ رویدادهایِ خودیِ میانِ دو گامِ مرجع
        mult, n_ours = 1.0, 0
        for od, orr in ours:
            if dp < od <= d:
                mult *= (1.0 / orr)
                n_ours += 1
        pred, kind, blend, note = None, "", False, ""
        if near:
            ld, k, v = near
            kind = k
            if k == "capital":
                pc, nc = v["previous_capital"], v["new_capital"]
                if v.get("contribution_percent"):
                    blend = True
                    note = f"contribution={v['contribution_percent']}% premium={v.get('premium_percent')}%"
                    pred = nc / pc   # حدسِ خام؛ آوردۀِ نقدیِ سهامدار فرمولِ ترکیبی می‌خواهد
                else:
                    pred = nc / pc
            else:
                dps = v.get("pure_dps") or 0
                price_prev = x0[dp]
                if dps and price_prev > dps:
                    pred = price_prev / (price_prev - dps)
        reconstructed = pred is not None and abs(st / pred - 1) <= AGREE
        has_src = has_source(share_dates, sym, d) if kind == "capital" else \
                  has_source(padj_dates, sym, d) if kind == "dps" else False
        our_gap = abs(mult / st - 1) if n_ours else None
        divergent = our_gap is None or our_gap > AGREE
        if not near:
            cat = "no_corporate_mark_in_window"
        elif blend:
            cat = "contribution_blend_needs_offer_price"
        elif kind == "dps" and not reconstructed:
            cat = "dps_formula_imprecise"
        elif kind == "capital" and not reconstructed:
            cat = "capital_formula_imprecise"
        elif divergent and has_src:
            cat = "REPROducible_from_source_but_not_applied"
        elif divergent and not has_src:
            cat = "BLOCKED_no_source_for_symbol_window"
        else:
            cat = "matched_within_tol"
        bucket[cat] = bucket.get(cat, 0) + 1
        rows.append({"symbol": sym, "step_date": d, "ref_step": round(st, 6),
                     "kind": kind or "", "predicted": round(pred, 6) if pred else None,
                     "formula_reconstructs": int(reconstructed), "blend": int(blend),
                     "source_window_days": SOURCE_WINDOW, "product_has_source_row": int(has_src),
                     "our_step_count": n_ours, "our_step": round(mult, 6) if n_ours else None,
                     "our_gap_pct": round((our_gap or 0) * 100, 4), "category": cat, "note": note})

out = f"{ROOT}/_audit/RA365-PHASE3-LEDGER-COVERAGE-2026-10-13.csv"
hdr = ["symbol", "step_date", "ref_step", "kind", "predicted", "formula_reconstructs", "blend",
       "product_has_source_row", "our_step_count", "our_step", "our_gap_pct", "category", "note"]
with open(out, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=hdr)
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k) for k in hdr})

total = len(rows)
print(f"گام‌هایِ تعدیلِ مرجع (آستانۀِ {STEP_TOL*100:.2f}٪) در {len(CORPUS)} نماد: {total}")
print(f"ردیفِ CSV -> {out}\n")
for cat, n in sorted(bucket.items(), key=lambda z: -z[1]):
    print(f"  {n:4d}  {100*n/total:5.1f}٪  {cat}")

# خلاصۀِ عملیاتیِ سطل‌هایِ «رفع‌کردنی» در برابرِ «مهارِ منبع»
fixable = bucket.get("REPROducible_from_source_but_not_applied", 0)
blocked = bucket.get("BLOCKED_no_source_for_symbol_window", 0)
print(f"\nجمع‌بندی: رفع‌پذیر از منبعِ موجودِ خودی = {fixable}   "
      f"مهارِ منبع (دست‌کم درِ پنجرۀِ {SOURCE_WINDOW} روز) = {blocked}")
print("نکتہ: «sودِ نقدیِ پیش از ۲۰۲۴-۰۷-۲۱» درِ price_adjust_events هیچ ردیفی ندارد "
      "(سنجیدۀِ بالا: کلِ جدول [20240721..20261010])، پس بازسازیِ بی‌جعلِ ضریبِ آن تاریخ "
      "از خودی ممکن نیست و به مرجعِ بیرونیِ نوع‌دار نیاز دارد.")
