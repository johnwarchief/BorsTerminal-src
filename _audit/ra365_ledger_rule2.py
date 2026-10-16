# _audit/ra365_ledger_rule2.py -- دورِ دومِ قاعدۀِ دفتر: پنجرۀِ باز + ضربِ رویدادهایِ چندتایی
# چرا لازم بود: درِ دورِ اول (ra365_ledger_rule.py) سه گام به «بدونِ رویداد» و چند گام با
# خطایِ ۴ تا ۲۹٪ خورد، چون تاریخِ مجمعِ ثبت‌شده درِ دفتر می‌تواند بیش از ۴۵ روز قبل از
# روزِ اثرِ تعدیل باشد و یک گامِ مرجع می‌تواند حاصلِ ضربِ دو رویداد (سود + افزایشِ سرمایه) باشد.
# داوریِ نهایی فقط با اعدادِ خوانده‌شده می‌شود، نه با فرض.
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
LOOKBACK_DAYS = 150


def tehran_date(b):
    s = str(b["utc"]).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=3, minutes=30))).date().isoformat()


def as_date(s):
    return datetime.fromisoformat(s[:10]).date()


def ref_series(sym, suf):
    e = R["bars"].get(f"{sym}|{suf}|D")
    if not e or e.get("status") != 200:
        return {}
    out = {}
    for b in e["bars"]:
        d = tehran_date(b)
        if b.get("c"):
            out[d] = b["c"]
    return out


def ledger_of(sym):
    marks = ((R["meta"].get("marks|" + sym) or {}).get("json") or {}).get("data") or []
    out = []
    for m in marks:
        d = (m.get("date_time") or "")[:10]
        mid = str(m.get("id"))
        if "capital-change" in mid:
            out.append((d, "capital", m["capital_change"]))
        elif mid.startswith("dps"):
            out.append((d, "dps", m["dps"]))
    return sorted(out)


rows = []
for c in CORPUS:
    sym = c["sym"]
    x0, x7 = ref_series(sym, "type0"), ref_series(sym, "type7")
    common = sorted(set(x0) & set(x7))
    if len(common) < 5:
        continue
    raw = {d: x7[d] / x0[d] for d in common}
    anchor = raw[common[-1]]
    ratio = {d: v / anchor for d, v in raw.items()}
    led = ledger_of(sym)
    ours = sorted(((e["date"], e["ratio"]) for e in (P[sym]["live"].get("adjustEvents") or [])))

    steps = []
    for i in range(1, len(common)):
        d, dp = common[i], common[i - 1]
        st = ratio[d] / ratio[dp]
        if abs(st - 1) > 0.0025:
            steps.append((d, st, dp))

    lo_bound = (as_date(steps[0][0]) - timedelta(days=LOOKBACK_DAYS)).isoformat() if steps else common[0]
    prev_step = lo_bound
    for d, st, dp in steps:
        lo = prev_step if prev_step > lo_bound else lo_bound
        picked = [(ld, k, v) for ld, k, v in led if lo < ld <= d]
        # اگر پنجرۀِ بسته خالی بود، پنجرۀِ بازِ LOOKBACK را امتحان کن
        if not picked:
            picked = [(ld, k, v) for ld, k, v in led
                      if 0 <= (as_date(d) - as_date(ld)).days <= LOOKBACK_DAYS]
        price_prev = x0[dp]
        pred = 1.0
        blend_needed = None
        kinds = []
        for ld, k, v in picked:
            if k == "capital":
                pc, nc = v["previous_capital"], v["new_capital"]
                kinds.append("capital" + ("+آورده" if v.get("contribution_percent") else "+ذخیره"))
                if v.get("contribution_percent"):
                    blend_needed = (pc, nc, v)
                    pred *= nc / pc          # حدسِ خام؛ ترکیبِ آورده جداگانه حل می‌شود
                else:
                    pred *= nc / pc
            else:
                dps = v.get("pure_dps") or 0
                kinds.append("dps")
                if dps and price_prev > dps:
                    pred *= price_prev / (price_prev - dps)
        our_step = None
        our_nearest = None
        best = 10**9
        for od, orr in ours:
            gap = abs((as_date(od) - as_date(d)).days)
            if gap < best:
                best = gap
                our_nearest, our_step = od, round(1.0 / orr, 6)
        if best > 12:
            our_nearest, our_step = None, None
        # ضربِ رویدادهایِ خودیِ درِ همین پنجره (بینِ دو گامِ مرجع)
        mult = 1.0
        n_ours = 0
        for od, orr in ours:
            if lo < od <= d:
                mult *= 1.0 / orr
                n_ours += 1
        rec = {"symbol": sym, "step_date": d, "ref_step": round(st, 6),
               "n_ledger": len(picked), "kinds": "+".join(sorted(set(kinds))),
               "ledger_dates": ",".join(p[0] for p in picked),
               "predicted": round(pred, 6) if picked else None,
               "ref_over_pred": round(st / pred, 6) if picked and pred else None,
               "blend": "YES" if blend_needed else "",
               "our_event": our_nearest, "our_step": our_step,
               "n_ours_in_window": n_ours, "our_product": round(mult, 6) if n_ours else None,
               "ref_over_ours": round(st / mult, 6) if n_ours and mult else None,
               "prev_trade": dp, "prev_raw_close": price_prev}
        rows.append(rec)
        prev_step = d

hdr = list(rows[0].keys())
with open(f"{ROOT}/_audit/RA365-LEDGER-RULE-2026-10-12.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=hdr)
    w.writeheader()
    for r in rows:
        w.writerow(r)

have = [r for r in rows if r["predicted"]]
err = sorted(abs(r["ref_over_pred"] - 1) for r in have if r["ref_over_pred"])
n_plain = [r for r in have if not r["blend"]]
err_plain = sorted(abs(r["ref_over_pred"] - 1) for r in n_plain if r["ref_over_pred"])


def pct(a, q):
    if not a:
        return float("nan")
    i = min(len(a) - 1, int(round(q * (len(a) - 1))))
    return a[i]


print(f"گام‌هایِ مرجع: {len(rows)}   با رویدادِ دفتر: {len(have)}   بی‌رویداد: {len(rows)-len(have)}")
print(f"خطایِ نسبیِ (مرجع/پیش‌بینی) روی همه: میانه={pct(err,0.5)*100:.4f}٪  "
      f"p90={pct(err,0.9)*100:.4f}٪  بیشینه={err[-1]*100 if err else 0:.4f}٪")
print(f"فقط رویدادهایِ بدونِ آورده (ذخیره/سود): n={len(n_plain)}  میانه={pct(err_plain,0.5)*100:.4f}٪  "
      f"p90={pct(err_plain,0.9)*100:.4f}٪  بیشینه={err_plain[-1]*100 if err_plain else 0:.4f}٪")
print(f"گام‌هایِ نیازمندِ فرمولِ ترکیبیِ آورده: {sum(1 for r in rows if r['blend'])}")
print("گام‌هایی که هیچ رویدادِ دفترِ نزدیک ندارند:")
for r in rows:
    if not r["predicted"]:
        print(f"    {r['symbol']}  {r['step_date']}  ref_step={r['ref_step']}  our={r['our_step']}")
bad = [r for r in have if r["ref_over_pred"] and abs(r["ref_over_pred"] - 1) > 0.005]
print(f"گام‌هایِ با خطایِ بیش از ۰٫۵٪ ({len(bad)}):")
for r in bad:
    print(f"    {r['symbol']} {r['step_date']} ref={r['ref_step']} pred={r['predicted']} "
          f"({r['kinds']} n={r['n_ledger']}) ours={r['our_step']} x{r['n_ours_in_window']}={r['our_product']} blend={r['blend']}")

# خطایِ رویدادِ ما در برابرِ گامِ مرجع (تک‌رویدادی‌ها، بی‌آورده)
solo = [r for r in rows if r["our_step"] and r["n_ours_in_window"] == 1 and not r["blend"]]
se = sorted(abs(r["ref_step"] / r["our_step"] - 1) for r in solo)
print(f"  تک‌رویدادی‌هایِ قابلِ مقایسه (ما/مرجع): n={len(se)}  میانه={pct(se,0.5)*100:.4f}٪  "
      f"p90={pct(se,0.9)*100:.4f}٪  بیشینه={se[-1]*100 if se else 0:.4f}٪")
nosolo = [r for r in rows if r["our_step"] is None]
print(f"گام‌هایِ مرجعی که رویدادِ هم‌روزِ ما ندارند: {len(nosolo)}")
ours_only = [r for r in rows if r["n_ours_in_window"] >= 2]
print(f"گام‌هایی که ما درِ همان پنجره دو یا چند رویداد داریم: {len(ours_only)}")
