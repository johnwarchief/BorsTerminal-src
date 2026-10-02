# -*- coding: utf-8 -*-
"""_audit/adjust_zero_volume_probe.py — آیا «بازنویسیِ پایانی درِ سطرِ بی‌معامله» همان
رویدادِ گم‌شده است؟ (سنجشِ همگرایی، نه حدس)

چیزی که درِ داده دیدیم (وبملت، گردِ ۲۰۱۲-۰۲-۰۶):

    ۲۰۱۲-۰۲-۰۴  VOL=0  CLOSE=2242  BASE=2242
    ۲۰۱۲-۰۲-۰۵  VOL=0  CLOSE=1793  BASE=2242     ← پایانیِ همین سطر بازنویسی شده
    ۲۰۱۲-۰۲-۰۶  VOL=15٬۱۸۷٬۵۸۰  CLOSE=1736  BASE=1793

درِ این الگو «قیمت پایه» هیچ‌وقت از پایانیِ دیروز جلو نمی‌زند، پس گاردِ فعلیِ ما
(`base != closeِ سطرِ قبل`) هیچ رویدادی نمی‌بیند؛ ولی نسبتِ ۱۷۹۳/۲۲۴۲ = ۰٫۷۹۹۷۳
دقیقاً معکوسِ گامِ پلکانِ رهاورد درِ همان روز است (۱٫۲۵۰۴۱۸).

درِ نمادِ دیگر (فولاد ۲۰۲۱-۰۵-۲۴) بازنویسی درِ خودِ «قیمت پایه» دیده می‌شود و گاردِ
فعلی کار می‌کند. پس دو نشانۀ جدا وجود دارد و باید هر دو خوانده شوند:

  (ی) base(D) != close(prev)              → رویداد (رفتارِ امروزِ ما)
  (ب) vol(D) == 0 و close(D) != base(D)   → رویداد با نسبتِ close/base  (گم‌شده)

این اسکریپت هر دو را رویِ CSVِ خام می‌شمارد و با گام‌هایِ استنتاج‌شدۀ مرجع (که درِ
_audit/ra_parity_report.json است) مقابله می‌دهد: چند گامِ مرجع با (ی) پوشسته است،
چند تا با (ی)+(ب)، و آیا (ب) رویدادِ جعلیِ جدیدی می‌سازد؟
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
CACHE = os.path.join(ROOT, "_audit", "parity_event_csv")

import api.chart as CH          # noqa: E402  (از _parse_tsetmc_csvِ خودِ برنامه)


def fetch_csv(ins):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, f"raw_{ins}.txt")
    if os.path.isfile(p) and os.path.getsize(p) > 1000:
        return open(p, encoding="utf-8").read()
    url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyListCSV/{ins}/19900101"
    txt = urllib.request.urlopen(urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.tsetmc.com/"}),
        timeout=150).read().decode("utf-8", "replace")
    open(p, "w", encoding="utf-8").write(txt)
    time.sleep(1.5)     # ادبِ درخواست، همان کاری که test_tsetmc می‌کند
    return txt


def events_both_rules(txt):
    """هر دو نشانۀ (ی) و (ب) رویِ ردیف‌هایِ خامِ CSV — با همان آستانۀ دوتاییِ برنامه."""
    rows = []
    for ln in txt.splitlines()[1:]:
        p = [x.strip() for x in ln.split(",")]
        if len(p) < 11:
            continue
        d = p[1]
        if len(d) != 8 or not d.isdigit():
            continue
        try:
            rows.append({"time": f"{d[:4]}-{d[4:6]}-{d[6:8]}",
                         "close": float(p[5] or 0), "vol": float(p[7] or 0),
                         "base": float(p[10] or 0)})
        except ValueError:
            continue
    rows.sort(key=lambda r: r["time"])
    ev_i, ev_ii = [], []
    prev = None
    for r in rows:
        if r["base"] <= 0 or r["close"] <= 0:
            prev = r
            continue
        if prev and prev["close"] > 0 and prev["base"] > 0:
            ratio = r["base"] / prev["close"]
            if abs(r["base"] - prev["close"]) >= 1.0 and abs(ratio - 1.0) > CH.ADJ_TOL:
                ev_i.append({"date": r["time"], "ratio": round(ratio, 6)})
        if r["vol"] == 0.0 and r["base"] != r["close"]:
            ratio = r["close"] / r["base"]
            if abs(ratio - 1.0) > CH.ADJ_TOL:
                ev_ii.append({"date": r["time"], "ratio": round(ratio, 6)})
        prev = r
    return ev_i, ev_ii, len(rows)


def ref_steps(report_paths, symbol):
    for path in report_paths:
        if not os.path.isfile(path):
            continue
        d = json.load(open(path, encoding="utf-8"))
        for b in d.get("per_symbol", []):
            if b.get("symbol") == symbol and b.get("basis") == "last" and b.get("factor_schedule"):
                return [s for s in (b["factor_schedule"].get("reference_steps") or [])]
    return []


def main():
    import sqlite3
    con = sqlite3.connect(os.path.join(ROOT, "market.db"), timeout=30)
    names = sys.argv[1:] or ["فولاد", "وبملت", "شپنا", "فخوز", "كگل", "اخابر",
                             "غپينو", "مبين", "فاراك", "ثامان", "بترانس", "پارس"]
    ins_map = {n: str(i) for n, i in con.execute(
        "SELECT l_val18, ins_code FROM instruments WHERE l_val18 IN (%s)"
        % ",".join("?" * len(names)), names)}
    con.close()
    reports = [os.path.join(ROOT, "_audit", n) for n in
               ("ra_parity_report.json", "ra_parity_foolad_pars.json", "ra_parity_eracheck.json")]
    tot = {"steps": 0, "covered_i": 0, "covered_i_ii": 0, "new_false": 0, "ev_i": 0, "ev_ii": 0}
    for sym in names:
        ins = ins_map.get(sym)
        if not ins:
            print(f"{sym}: ins_code نیست")
            continue
        txt = fetch_csv(ins)
        ei, eii, nrows = events_both_rules(txt)
        steps = ref_steps(reports, sym)
        cov_i = cov_ii = 0
        # معیارِ پوشش: نسبتِ گامِ مرجع با معکوسِ نسبتِ رویدادِ ما بخورد و روز نزدیک باشد
        for s in steps:
            want = s["ratio"]
            if any(abs(1.0 / e["ratio"] / want - 1.0) < 0.004 and _daydiff(s["to_day"], e["date"]) <= 8
                   for e in ei):
                cov_i += 1
            if any(abs(1.0 / e["ratio"] / want - 1.0) < 0.004 and _daydiff(s["to_day"], e["date"]) <= 8
                   for e in ei + eii):
                cov_ii += 1
        only_new = [e for e in eii if not any(_daydiff(e["date"], o["date"]) <= 8 for o in ei)]
        print(f"  {sym:<9} ردیف={nrows:>5} رویدادِ (ی)={len(ei):>3} سیگنالِ (ب)={len(eii):>3} "
              f"| گامِ مرجع={len(steps):>3} پوششِ (ی)={cov_i:>3} پوششِ (ی)+(ب)={cov_ii:>3} "
              f"| (ب) تنها={len(only_new)}")
        for e in only_new[:6]:
            print(f"        (ب) تنها: {e['date']} ratio={e['ratio']}"
                  f" ← گامِ مرجعِ نزدیک: "
                  f"{[(s['to_day'], s['ratio']) for s in steps if _daydiff(s['to_day'], e['date']) <= 8]}")
        tot["steps"] += len(steps); tot["covered_i"] += cov_i; tot["covered_i_ii"] += cov_ii
        tot["ev_i"] += len(ei); tot["ev_ii"] += len(eii); tot["new_false"] += len(only_new)
    print("\nجمع:", json.dumps(tot, ensure_ascii=False))
    if tot["steps"]:
        print(f"پوششِ پلکانِ مرجع: (ی) به‌تنهایی {tot['covered_i']}/{tot['steps']} = "
              f"{tot['covered_i']/tot['steps']:.1%} → با (ی)+(ب) {tot['covered_i_ii']}/{tot['steps']} = "
              f"{tot['covered_i_ii']/tot['steps']:.1%}")


def _dt(s):
    import datetime as dt
    return dt.date.fromisoformat(s)


def _daydiff(a, b):
    return abs((_dt(a) - _dt(b)).days)


if __name__ == "__main__":
    main()
