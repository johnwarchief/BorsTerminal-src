# _audit/ra365_ledger_rule.py -- آیا گامِ تعدیلِ مرجع از دفترِ شرکتی (capital-change/dps) بازسازی می‌شود؟
# سه حدسِ آزمون‌پذیر (هیچ‌کدام ساخته نمی‌شوند؛ همه از داده خوانده می‌شوند):
#   H1  افزایشِ صرفِ ذخیره (contribution_percent == 0)  ->  گام = new_capital / previous_capital
#   H2  افزایشِ با آورده (contribution_percent  >  0)   ->  گام = (N_old + N_new*(S/P)) / (N_old+N_new) درِ فرمولِ ترکیبی
#   H3  سودِ نقدی (dps)                                  ->  گام = P / (P - dps)
# مرجع: گام از ratio(type7/type0). ما: گام از ratio رویدادهایِ adjust_events.
import json
import io
import sys
import csv
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = "C:/Users/Johnkallnaya/Desktop/Borsterminal/BorsTerminal-src"
R = json.load(open(f"{ROOT}/_audit/ra365_ref_bars.json", encoding="utf-8"))
P = json.load(open(f"{ROOT}/_audit/ra365_product_bars.json", encoding="utf-8"))
CORPUS = json.load(open(f"{ROOT}/_audit/ra365_corpus.json", encoding="utf-8"))


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


def steps_of(days, ratio):
    """گام‌هایِ فاکتورِ مرجع (آستانۀ 0.25٪) به‌صورتِ [(date, step, prev_raw_close)]"""
    out = []
    for i in range(1, len(days)):
        d, dp = days[i], days[i - 1]
        st = ratio[d] / ratio[dp]
        if abs(st - 1) > 0.0025:
            out.append((d, st, dp))
    return out


rows = []
h1_hits = h1_tot = h2_tot = h3_hits = h3_tot = 0
for c in CORPUS:
    sym = c["sym"]
    x0, x7 = ref_series(sym, "type0"), ref_series(sym, "type7")
    common = sorted(set(x0) & set(x7))
    if not common:
        continue
    raw = {d: x7[d] / x0[d] for d in common}
    anchor = raw[common[-1]]
    ratio = {d: v / anchor for d, v in raw.items()}
    marks = ((R["meta"].get("marks|" + sym) or {}).get("json") or {}).get("data") or []
    led = []
    for m in marks:
        d = (m.get("date_time") or "")[:10]
        if "capital-change" in str(m.get("id")):
            cc = m["capital_change"]
            led.append((d, "capital", cc))
        elif str(m.get("id", "")).startswith("dps"):
            led.append((d, "dps", m["dps"]))
    ours = {e["date"]: e["ratio"] for e in (P[sym]["live"].get("adjustEvents") or [])}
    for d, st, dp in steps_of(common, ratio):
        # رویدادِ دفترِ نزدیک (پنجرۀ ۴۵ روزِ قبلِ گام — تاریخِ ثبت می‌تواند زودتر باشد)
        cand = [(ld, k, v) for ld, k, v in led if 0 <= (as_date(d) - as_date(ld)).days <= 45]
        cand.sort(key=lambda z: (as_date(d) - as_date(z[0])).days)
        near = cand[0] if cand else None
        prev_close_raw = x0[dp]
        rec = {"symbol": sym, "step_date": d, "ref_step": round(st, 6),
               "prev_trade_date": dp, "prev_raw_close": prev_close_raw,
               "our_event_date": None, "our_step": None, "ledger_date": None,
               "ledger_kind": None, "predicted": None, "rel_err": None, "note": ""}
        for od, orr in ours.items():
            if 0 <= (as_date(d) - as_date(od)).days <= 45 or abs((as_date(od) - as_date(d)).days) <= 12:
                rec["our_event_date"] = od
                rec["our_step"] = round(1.0 / orr, 6)
                break
        if near:
            ld, kind, v = near
            rec["ledger_date"], rec["ledger_kind"] = ld, kind
            if kind == "capital":
                prev_c, new_c = v["previous_capital"], v["new_capital"]
                share_ratio = new_c / prev_c
                if not v.get("contribution_percent"):
                    rec["predicted"] = round(share_ratio, 6)
                    h1_tot += 1
                    if abs(st / share_ratio - 1) < 0.0025:
                        h1_hits += 1
                        rec["note"] = "H1 دقیق"
                    else:
                        rec["note"] = "H1 نزدیک‌تر از H2/H3"
                else:
                    # آورده: گامِ مشاهده‌شده -> نسبتِ قیمتِ پیشنهادِ هر سهمِ جدید به قیمتِ قبلی (S/P)
                    n_old, n_new = prev_c, new_c - prev_c
                    ex_over_p = 1.0 / st
                    frac_new = n_new / new_c
                    s_over_p = (ex_over_p - (1 - frac_new)) / frac_new if frac_new else None
                    rec["predicted"] = f"blend S/P={s_over_p:.5f}" if s_over_p else "blend"
                    rec["note"] = (f"contribution={v.get('contribution_percent')}% "
                                   f"reserve={v.get('reserve_percent')}% "
                                   f"naive_step={share_ratio:.5f} observed={st:.5f}")
                    h2_tot += 1
            else:
                dps = v.get("pure_dps") or 0
                if dps and prev_close_raw:
                    rec["predicted"] = round(prev_close_raw / (prev_close_raw - dps), 6)
                    h3_tot += 1
                    if abs(st / (prev_close_raw / (prev_close_raw - dps)) - 1) < 0.005:
                        h3_hits += 1
                        rec["note"] = "H3 دقیق"
                    else:
                        rec["note"] = "H3 با خطا"
        if rec["predicted"] and isinstance(rec["predicted"], (int, float)) and rec["predicted"]:
            rec["rel_err"] = round(st / rec["predicted"] - 1, 6)
        rows.append(rec)

hdr = ["symbol", "step_date", "ref_step", "ledger_date", "ledger_kind", "predicted",
       "rel_err", "our_event_date", "our_step", "prev_trade_date", "note"]
with open(f"{ROOT}/_audit/RA365-LEDGER-RULE-2026-10-12.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=hdr)
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k) for k in hdr})

print(f"گام‌هایِ سنجیده‌شده در مرجع: {len(rows)}")
print(f"H1 افزایشِ ذخیره‌ای (گام=new/prev): {h1_hits}/{h1_tot} با خطایِ کمتر از ۰٫۲۵٪")
print(f"H2 افزایشِ آورده‌ای: {h2_tot} گام (فرمولِ ترکیبی لازم است)")
print(f"H3 سودِ نقدی (گام=P/(P-dps)): {h3_hits}/{h3_tot} با خطایِ کمتر از ۰٫۵٪")
print()
print("جدولِ کامل (نمونۀِ اول):")
for r in rows[:40]:
    print("  " + " | ".join(str(r.get(k)) for k in hdr))
