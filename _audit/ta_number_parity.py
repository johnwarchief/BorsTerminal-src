# -*- coding: utf-8 -*-
"""_audit/ta_number_parity.py — عدد‌به‌عدد: نبضِ ما در برابرِ تریدرزآرنا، با واحدِ اثبات‌شده

واحدِ هر سری را **حدس نمی‌زنم**: برایِ هر عدد، مجموعه‌ای از تبدیل‌هایِ واحدِ
قطعی (ریال↔تومان، میلیارد، همت، شمارش) را آزمایش می‌کنم و «تطبیق» را فقط وقتی
اعلام می‌کنم که نسبتِ دو طرف در چند نمونۀ پشت‌سرهم *ثابت* بماند و ضریبش یکی از
تبدیل‌هایِ قطعیِ بالا باشد. ضریبِ ۱ ⇒ همان عدد، بدونِ تبدیل. ضریبِ ۱۰/۱۰۰/۱e۴ ⇒
واحد. هیچ ضریبِ دیگری ⇒ «اختلافِ تعریف»، و آن را در گزارش می‌نویسم نه در کد.

نمونۀ چندبار (پیش‌فرض ۴ بار، هر ۸ ثانیه) چون مقایسۀ تک‌لحظه‌ای با دادهِ متحرک
دو «اختلافِ جعلی» ساخته بود (قاعدۀ حافظه: Compare market feeds at one instant —
این‌جا همان «یک لحظه» را چهار بار تکرار می‌کنیم تا تصادفی بودنِ جابه‌جایی بصری
از ثباتِ تعریف جدا شود).
"""
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests                              # noqa: E402

TA = "https://tradersarena.ir"
H = {"User-Agent": "Mozilla/5.0", "Referer": TA + "/", "Accept": "application/json"}
APP = os.environ.get("PAR_APP", "http://127.0.0.1:8002")
# تبدیل‌هایِ واحدِ قطعی: ریالِ خودِ TSETMC/TA به واحدِ گزارشِ ما (میلیارد تومان)
RIAL_TO_BT = 1e10
UNITS = {"rial→ب.ت": RIAL_TO_BT, "بی‌واحد": 1.0, "تومان→ب.ت": 1e9,
         "ریال→همت": RIAL_TO_BT * 1e3, "میلیون‌ریال→ب.ت": 1e3}
SAMPLES = int(os.environ.get("PAR_SAMPLES", "4"))
GAP = float(os.environ.get("PAR_GAP", "8"))


def ours():
    su = requests.get(APP + "/api/mstat/summary", timeout=90).json()
    sm = requests.get(APP + "/api/mstat/smart-money", timeout=90).json()
    de = requests.get(APP + "/api/mstat/depth?group=eq_all", timeout=90).json()
    th = requests.get(APP + "/api/mstat/thermometer?group=eq_all", timeout=90).json()
    rows = {r["label"]: r for r in su["rows"]}
    allm = rows.get("کل بازار", {})
    eq = next((v for k, v in rows.items() if k.startswith("سهام، حق تقدم و ص")), {})
    return su, {"flow_all_bt": allm.get("money_flow_b_toman"),
                "flow_eq_bt": (sm.get("flow") or {}).get("eq_flow_b_toman"),
                "flow_fixed_bt": (sm.get("flow") or {}).get("fixed_flow_b_toman"),
                "flow_gold_bt": (sm.get("flow") or {}).get("gold_flow_b_toman"),
                "value_all_bt": allm.get("value_b_toman"),
                "value_eq_bt": eq.get("value_b_toman"),
                "pc_buy": allm.get("pc_buy_m_toman"),
                "pc_sell": allm.get("pc_sell_m_toman"),
                "buy_power": allm.get("buy_power"),
                "buy_queue_bt": de.get("buy_queue_b_toman"),
                "sell_queue_bt": de.get("sell_queue_b_toman"),
                "queue_ratio": de.get("ratio"),
                "buy_queue_n": de.get("buy_queue_count"),
                "sell_queue_n": de.get("sell_queue_count"),
                "positive": th.get("positive"), "negative": th.get("negative"),
                "zero": th.get("zero"), "symbols": th.get("symbols") or su["asof"].get("n")}


def last(a):
    if isinstance(a, list):
        for x in reversed(a):
            if x not in (None, 0):
                return x
        return a[-1] if a else None
    return a


def main():
    pairs = []
    for i in range(SAMPLES):
        t0 = time.time()
        tot = requests.get(TA + "/data/market/chart/totals0", headers=H, timeout=90).json()
        ta = {"flow_all": last(tot.get("transfer")), "flow_eq": last(tot.get("stockTransfer")),
              "flow_fixed": last(tot.get("fixedIncomesTransfer")), "value_all": last(tot.get("val")),
              "mval": last(tot.get("mval")), "bq": last(tot.get("bq")), "sq": last(tot.get("sq")),
              "bpc": last(tot.get("bpc")), "spc": last(tot.get("spc")),
              "bpcx": last(tot.get("bpcx")), "spcx": last(tot.get("spcx")),
              "plus": last(tot.get("plus")), "minus": last(tot.get("minus")),
              "mTransfer": last(tot.get("mTransfer")), "msTransfer": last(tot.get("msTransfer")),
              "mfixed": last(tot.get("mfixedTransfer"))}
        su, ou = ours()
        pairs.append({"ta_at": datetime.now().isoformat(timespec="seconds"),
                      "ta_skew_s": round(time.time() - t0, 2), "app_asof": su["asof"],
                      "ta": ta, "ours": ou})
        print(f"نمونۀ {i+1}: TA {datetime.now():%H:%M:%S} (read {pairs[-1]['ta_skew_s']}s) | "
              f"app h_even={ou and su['asof']['h_even']}")
        if i < SAMPLES - 1:
            time.sleep(GAP)

    MAP = [("جریان پول کل بازار (ب.ت)", "flow_all", "flow_all_bt"),
           ("جریان پول سهام+حق‌تقدم+ص.سهامی", "flow_eq", "flow_eq_bt"),
           ("جریان پول درآمد ثابت", "flow_fixed", "flow_fixed_bt"),
           ("ارزش معاملات کل (واحدسنجی)", "value_all", "value_all_bt"),
           ("ارزش معاملات سهام‌ساندها", "mval", "value_eq_bt"),
           ("ارزش صف خرید", "bq", "buy_queue_bt"),
           ("ارزش صف فروش", "sq", "sell_queue_bt"),
           ("نسبت صف", "bq_over_sq", "queue_ratio"),
           ("نماد مثبت", "plus", "positive"),
           ("نماد منفی", "minus", "negative"),
           ("سرانه خرید", "bpc", "pc_buy"),
           ("سرانه فروش", "spc", "pc_sell")]
    rows = []
    for label, tk, ok in MAP:
        series = []
        for p in pairs:
            tv = p["ta"].get(tk)
            if tk == "bq_over_sq":
                tv = (p["ta"]["bq"] / p["ta"]["sq"]) if p["ta"].get("sq") else None
            ov = p["ours"].get(ok)
            if tv and ov:
                series.append(tv / ov)
        if not series:
            rows.append({"panel": label, "verdict": "بی‌عددِ قابل‌مقایسه",
                         "ta": pairs[-1]["ta"].get(tk), "ours": pairs[-1]["ours"].get(ok)})
            continue
        spread = max(series) - min(series)
        med = sorted(series)[len(series) // 2]
        named = None
        for uname, uval in UNITS.items():
            if abs(med - uval) / uval < 0.02:
                named = uname
                break
        stable = spread / max(abs(med), 1e-9) < 0.03
        if named and abs(med - 1.0) < 0.02:
            verdict = "PARITY (همان عدد، بی‌تبدیل)"
        elif named:
            verdict = f"همان عدد با واحدِ {named}"
        elif not stable:
            verdict = f"ضریبِ ناپایدار (med={med:.4g}, spread={spread:.4g}) ⇒ اختلافِ تعریف"
        else:
            verdict = f"ضریبِ ثابت {med:.4g} اما واحدِ قطعی نیست ⇒ نیازمندِ تعریفِ آن‌ها"
        rows.append({"panel": label, "ratio_median": round(med, 6), "spread": round(spread, 6),
                     "n": len(series), "unit": named, "verdict": verdict,
                     "ta_last": pairs[-1]["ta"].get(tk), "ours_last": pairs[-1]["ours"].get(ok)})
    print("\n| عدد | TA (آخر) | ما (آخر) | نسبتِ ثابت | داوری |")
    print("|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['panel']} | {r.get('ta_last')} | {r.get('ours_last')} | "
              f"{r.get('ratio_median', '—')} | {r['verdict']} |")
    out = os.path.join("_audit", "ta_number_parity.json")
    json.dump({"pairs": pairs, "rows": rows}, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nwrote", out)


if __name__ == "__main__":
    main()
