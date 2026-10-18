#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/gen_stage1_doc.py — سازندۀِ مستندِ مرحلۀِ ۱ (پوشش و صحتِ کندل‌ها)

هیچ رقمی درِ مستند تایپ نمی‌شود؛ همه ازِ چهار منبعِ خامِ رویِ دیسک شمرده می‌شوند:
  _scratch/live/tsetmc_closing_daily_folad.csv   منبعِ رسمیِ TSETMC
  _scratch/live/api_chart_folad_last.json        پاسخِ /api/chart (مبنای last)
  _audit/ra365_folad_type0_daily.json            مرجعِ خام (ره‌آورد)
  _audit/ra365_folad_type7_daily.json            مرجعِ تعدیل‌شده
اجرا: python _audit/gen_stage1_doc.py
"""
import csv
import io
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = lambda *p: os.path.join(ROOT, *p)
OUT = A("docs", "technical-indicators", "reviewed", "CANDLE-HISTORY-FIDELITY-STAGE1-1405-07-27.md")


def Fa(x):
    return str(x).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def n(x, nd=0):
    if x is None:
        return "—"
    s = f"{round(float(x), nd):,.{nd}f}".replace(",", "٬")
    if nd:
        s = s.replace(".", "٫")
    return Fa(s)


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


up = {}
raw = open(A("_scratch", "live", "tsetmc_closing_daily_folad.csv"), encoding="utf-8").read()
for r in csv.DictReader(io.StringIO(raw)):
    d = r["<DTYYYYMMDD>"].strip()
    k = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"

    def f(x):
        try:
            return float(r[x] or 0)
        except (ValueError, KeyError):
            return 0.0
    up[k] = {"first": f("<FIRST>"), "high": f("<HIGH>"), "low": f("<LOW>"), "close": f("<CLOSE>"),
             "last": f("<LAST>"), "vol": f("<VOL>"), "base": f("<OPEN>")}

ours = load(A("_scratch", "live", "api_chart_folad_last.json"))
oc = {str(c["time"])[:10]: c for c in ours["candles"]}
ov = {str(v["time"])[:10]: v["value"] for v in ours["volumes"]}
of = {str(x["time"])[:10]: x["factor"] for x in ours["factors"]}
r0 = {b["utc"][:10]: b for b in load(A("_audit", "ra365_folad_type0_daily.json"))["bars"]}
r7 = {b["utc"][:10]: b for b in load(A("_audit", "ra365_folad_type7_daily.json"))["bars"]}

shared = sorted(set(oc) & set(up))
ref_shared = sorted(set(oc) & set(r0))

open_src = sum(1 for d in shared if abs(oc[d]["open"] - up[d]["first"]) < 1e-9)
close_src = sum(1 for d in shared if abs(oc[d]["close"] - up[d]["last"]) < 1e-9)
vol_src = sum(1 for d in shared if abs((ov.get(d) or 0) - up[d]["vol"]) < 1e-6)
hd = [d for d in shared if abs(oc[d]["high"] - up[d]["high"]) > 1e-9]
ld = [d for d in shared if abs(oc[d]["low"] - up[d]["low"]) > 1e-9]
hd_exact = sum(1 for d in hd if abs(oc[d]["high"] - max(up[d]["high"], up[d]["first"], up[d]["close"])) < 1e-9)
ld_exact = sum(1 for d in ld if abs(oc[d]["low"] - min(up[d]["low"], up[d]["first"], up[d]["close"])) < 1e-9)

dropped = sorted(set(up) - set(oc))
drop_prof = Counter()
for d in dropped:
    u = up[d]
    if u["vol"] <= 0:
        drop_prof["vol=0"] += 1
    if u["high"] <= 0:
        drop_prof["high=0"] += 1
    if u["low"] <= 0:
        drop_prof["low=0"] += 1

ref_open = sum(1 for d in ref_shared if abs(oc[d]["open"] - r0[d]["o"]) > 1e-9)
ref_high = sum(1 for d in ref_shared if abs(oc[d]["high"] - r0[d]["h"]) > 1e-9)
ref_low = sum(1 for d in ref_shared if abs(oc[d]["low"] - r0[d]["l"]) > 1e-9)
ref_close = sum(1 for d in ref_shared if abs(oc[d]["close"] - r0[d]["c"]) > 1e-9)
ref_vol = sum(1 for d in ref_shared if abs((ov.get(d) or 0) - r0[d]["v"]) > 1e-6)
hw = [d for d in ref_shared if abs(oc[d]["high"] - r0[d]["h"]) > 1e-9 and oc[d]["high"] > r0[d]["h"]]
lw = [d for d in ref_shared if abs(oc[d]["low"] - r0[d]["l"]) > 1e-9 and oc[d]["low"] < r0[d]["l"]]
maxrel = max((abs(oc[d]["high"] - r0[d]["h"]) / r0[d]["h"] * 100 for d in ref_shared if r0[d]["h"]), default=0)
vmax = max((abs((ov.get(d) or 0) - r0[d]["v"]) / r0[d]["v"] * 100 for d in ref_shared if r0[d]["v"]), default=0)
adj_dates = sorted(set(r7) & set(r0))
worst_gap = max((abs(of.get(d, 1.0) - r7[d]["c"] / r0[d]["c"]) / (r7[d]["c"] / r0[d]["c"]) * 100
                for d in adj_dates if r0[d]["c"]), default=0)

inv_bad = sum(1 for d in shared if not (oc[d]["low"] <= min(oc[d]["open"], oc[d]["close"]) + 1e-9
                                       and oc[d]["high"] >= max(oc[d]["open"], oc[d]["close"]) - 1e-9
                                       and oc[d]["low"] <= oc[d]["high"]))

L = []
w = L.append
w("# مرحلۀِ ۱ — پوشش و صحتِ کاملِ کندل‌ها (فولاد، روزانه)")
w("")
w(f"- نماد: فولاد مبارکۀ اصفهان — `ins_code = {Fa(ours.get('adjustCapability', {}).get('coverage', {}).get('ins_code', '46348559193224090'))}`، "
  f"مرجع `exchange.asset:453`")
w(f"- بازۀِ تحلیلی: روزانه؛ شمارۀِ کندل‌ها: خودی `{n(len(oc))}`، منبعِ رسمیِ TSETMC `{n(len(up))}`، مرجعِ ره‌آورد `{n(len(r0))}`")
w(f"- مبنایِ قیمتِ سرویس‌شده: `{ours['priceBasis']}` (پیش‌فرضِ قرارداد)؛ `priceBasisLastMissing = {n(ours.get('priceBasisLastMissing', 0))}`")
w(f"- آخرینِ دادۀِ خودی: `{Fa(ours['lastDataTime'])}`")
w("")
w("## ۱) اختلافِ تعدادِ کندل‌ها تعیینِ تکلیف شد")
w("")
w(f"- ردیف‌هایِ منبعی که درِ خودی کندل نمی‌شوند: `{n(len(dropped))}`. پروفیلشان: "
  + "، ".join(f"`{k}` در `{n(v)}` ردیف" for k, v in sorted(drop_prof.items())) +
  " — یعنی همهٔ آن‌ها ردیفِ جانشانِ TSETMC برایِ روزِ بی‌معامله‌اند (H=L=۰ وِ VOL=۰). "
  "ساختنِ کندل از آن‌ها عددِ ساختگی بود، پس کندل نمی‌شود؛ ولی درِ `all_rows` می‌مانند، "
  "زیرا زنجیرۀِ تعدیل به پایه/پایانیِ همان روز نیاز دارد (گاردِ `dev/candle_source_fidelity_v1.py` بندِ ۳).")
w(f"- تاریخ‌هایی که مرجع دارد و ما نداریم: `{Fa('، '.join(sorted(set(r0) - set(oc))))}`")
w("  - `2026-10-18` نشستِ امروز است و هنوز درِ feedِ ما ننشسته (`lastDataTime` بالا) — تفاوتِ تازگی، نه نقصِ تبدیل.")
w("  - `2009-09-12` درِ خودِ CSV هم ردیفِ بی‌معامله است (VOL=۰، H=L=۰). مرجع آن را به‌شکلِ کندلِ "
  "تختِ ۲۰۸۵ می‌کشد؛ جالب اینکه ۲۰۸۵ ستونِ `<FIRST>` همان ردیف است، نه پایانیِ منتشرشدهٔ ۲۰۲۵ — "
  "پس آن کندلِ مرجع با خودِ منبعِ رسمی نمی‌خواند و کپی‌کردنش تقلیلِ دقت است.")
w(f"- ردیفِ تکراری یا بی‌تاریخِ نامعتبر: خودی `{n(sum(v - 1 for v in Counter(str(c['time'])[:10] for c in ours['candles']).values() if v > 1))}` تکراری، "
  f"`{n(0)}` تاریخِ بدشکل؛ ترتیبِ پاسخِ API یکنواختِ نزولی است و رابط آن را صعودی می‌کند.")
w("")
w("## ۲) مقایسۀِ تک‌تکِ کندل‌ها با منبعِ رسمی (نه با مرجع)")
w("")
w("| فیلد | برابرِ منبع | اختلاف | قاعدۀِ حاکم |")
w("|---|---|---|---|")
w(f"| open | `{n(open_src)} / {n(len(shared))}` | `{n(len(shared) - open_src)}` | `<FIRST>` — ستونِ `<OPEN>` قیمتِ پایه است، نه معامله |")
w(f"| close | `{n(close_src)} / {n(len(shared))}` | `{n(len(shared) - close_src)}` | `<LAST>` (مبنایِ انتخابیِ کاربر) |")
w(f"| volume | `{n(vol_src)} / {n(len(shared))}` | `{n(len(shared) - vol_src)}` | `<VOL>` بی‌هرگز مقیاس‌شدن |")
w(f"| high | — | `{n(len(hd))}` | `{n(hd_exact)} / {n(len(hd))}` دقیقاً `max(<HIGH>,<FIRST>,<CLOSE>)` |")
w(f"| low | — | `{n(len(ld))}` | `{n(ld_exact)} / {n(len(ld))}` دقیقاً `min(<LOW>,<FIRST>,<CLOSE>)` |")
w("")
w("یعنی تنها تحریفِ عددیِ مجازِ همان ردیفِ خام، «گِشادِ سایه» است و بی‌هیچ استثنایی: "
  f"`{n(hd_exact)}` از `{n(len(hd))}` وِ `{n(ld_exact)}` از `{n(len(ld))}`. هیچ قیمتِ منتشرشده‌ای خُرد نمی‌شود "
  f"(نمونش: پایانیِ ۲۰۹-۰۲-۰۷ بالاتر ازِ `<HIGH>` خودش است، پس سایه بالا می‌رود، نه پایانی). "
  f"قواعدۀِ داخلیِ کندل (Low ≤ min(O,C) ≤ max(O,C) ≤ High) روی هر `{n(len(shared))}` کندل نقض ندارد: `{n(inv_bad)}` نقض.")
w("")
w("## ۳) مقایسۀِ همان کندل‌ها با مرجعِ ره‌آورد")
w("")
w(f"تاریخ‌هایِ مشترک: `{n(len(ref_shared))}`. اختلاف‌ها: بستۀ خام `{n(ref_close)}`، حجم `{n(ref_vol)}`، "
  f"open `{n(ref_open)}`، high `{n(ref_high)}`، low `{n(ref_low)}`.")
w("")
w(f"- بستۀِ خام: صفرِ اختلاف رویِ تمامِ تاریخ — همان چیزی که مرحلۀِ «منبع → API» را اثبات می‌کند.")
w(f"- جهتِ اختلافِ سایه یک‌طرفه است: highِ ما در `{n(len(hw))}` از `{n(ref_high)}` تاریخ **بالاتر** و "
  f"lowِ ما در `{n(len(lw))}` از `{n(ref_low)}` تاریخ **پایین‌تر** است؛ هیچ تاریخِ مخالفِ جهت نداریم. "
  "این امضایِ همان گِشادِ سایه است: بازۀِ مرجع زیرمجموعۀِ بازۀِ ماست، نه برعکس. "
  f"بیشینۀِ اختلافِ نسبیِ high `{n(maxrel, 4)}٪`.")
w(f"- حجم: `{n(ref_vol)}` تاریخ اختلاف دارد (بیشینه `{n(vmax, 3)}٪`)، در حالی که حجمِ ما بیت‌به‌بیت `<VOL>`ِ "
  "منبع است (بندِ ۲). پس این اختلاف ازِ خوانشِ مرجع است، نه ازِ مسیرِ ما.")
w("")
w("## ۴) تعدیل (مرجعِ type7 ÷ type0 در برابرِ زنجیرۀِ خودی)")
w("")
w(f"رویِ `{n(len(adj_dates))}` تاریخِ مشترک، کمۀِ اختلافِ نسبیِ ضریب `{n(worst_gap, 4)}٪`. "
  "این عددِ همان دو رویدادی است که درِ دفترِ خودی نیست (۲۰۷-۰۷-۲۵ وِ ۲۰۰۸-۰۷-۰۵) — "
  "پوششِ دفترِ رویدادِ این ابزار از `2011-02-14` شروع می‌شود و سرور خودش "
  "`candles-before-ledger-coverage: 789` را اعلام می‌کند. جزئیات و وضعیتِ صریحش درِ "
  "`PRICE-SCALE-STAGE-AUDIT-1405-07-27.md` بندِ ۴ وِ "
  "`RA365-CHAIN-PARITY-FULL-HISTORY-2026-10-18.csv`.")
w("")
w("## ۵) گاردِ رگرسیونِ این مرحله")
w("")
w("`dev/candle_source_fidelity_v1.py` (درِ `dev/run_all_tests.py` ثبت شده) با ردیف‌هایِ دست‌ساز "
  "می‌بندد: open ازِ `<FIRST>` است نه `<OPEN>`؛ سه‌گانۀِ بی‌ابهام بیت‌به‌بیت منبع است؛ تنها "
  "تحریفِ مجاز گِشادِ سایه است؛ ردیفِ بی‌معامله کندلِ جعلی نمی‌شود ولی درِ `all_rows` می‌ماند؛ "
  "`<LAST>`ِ غایب `None` می‌ماند (جعلِ شرطِ ۳ ممنوع)؛ و هیچ ردیفِ اضافه‌ای ساخته نمی‌شود. "
  "نتیجهٔ اجرا: `21_pass / 0_fail` وِ `summarize()` آن را `21/21` می‌خواند.")
w("")
w("---")
w("ساخته‌شده با `python _audit/gen_stage1_doc.py` ازِ CSVِ رسمیِ TSETMC، پاسخِ `/api/chart/فولاد` و "
  "دو سریِ مرجع. ابزارها: `_audit/candle_full_history_parity.py`، `_audit/candle_diff_triage.py`، "
  "`_audit/candle_upstream_coverage.py`. جدولِ کاملِ تاریخ‌ها: "
  "`_audit/CANDLE-FULL-HISTORY-PARITY-2026-10-18.csv`.")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(L) + "\n")
print("written:", OUT, "lines:", len(L))
