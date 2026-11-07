#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/candle_source_fidelity_v1.py — کندلِ سرویس‌شده باید دقیقاً همانِ منبع باشد

سازشِ امروز (۱۴۰۵-۰۷-۲۷، `_audit/candle_upstream_coverage.py` رویِ فولاد، ۴۲۴ کندل):
  open   == <FIRST>      4247 / 4247
  close  == <LAST>       4247 / 4247   (مبنای last)
  volume == <VOL>        4247 / 4247
  high   == max(<HIGH>,<FIRST>,<CLOSE>)  177 / 177 اختلافِ سایه، بی‌هیچ استثنایی
  low    == min(<LOW> ,<FIRST>,<CLOSE>)  108 / 108 اختلافِ سایه، بی‌هیچ استثنایی
یعنی تنها تحریفِ مجازِ هندسه، همان «گِشادِ سایه» است و هیچ قیمتِ منتشرشده‌ای خُرد
نمی‌شود. این گارد همان قرارداد را با ردیف‌هایِ دست‌ساز می‌بندد تا اگر روزی مسیرِ
تبدیل، نرمال‌سازی یا تعدیل بی‌صدا عددِ خام را عوض کرد، گیت قرمز شود — نه اینکه
چیزی را برای سبز شدن تغییر دهیم.

اجرا:  python dev/candle_source_fidelity_v1.py
خروجی: «N_pass / M_fail» (همان قالبی که dev/guard_counts.py می‌خواند)
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.chart as CH  # noqa: E402

HEADER = "<TICKER>,<DTYYYYMMDD>,<FIRST>,<HIGH>,<LOW>,<CLOSE>,<VALUE>,<VOL>,<OPENINT>,<PER>,<OPEN>,<LAST>"

PASSED = []
FAILED = []


def ck(cond, why, got=None):
    if cond:
        PASSED.append(why)
        print(f"  ok   {why}")
    else:
        FAILED.append(why)
        print(f"  FAIL {why}" + ("" if got is None else f"  → {got}"))


def row(day, first, high, low, close, vol, base, last, value=None):
    return (f"BORS,{day},{first:.2f},{high:.2f},{low:.2f},{close:.2f},"
            f"{(value if value is not None else vol * close):.2f},{vol:.0f},0,D,{base:.2f},"
            f"{('' if last is None else format(last, '.2f'))}")


def build(rows):
    buf = io.StringIO()
    buf.write(HEADER + "\n")
    for r in rows:
        buf.write(r + "\n")
    return buf.getvalue()


def by_date(candles):
    return {c["time"]: c for c in candles}


print("═══ ۱) ردیفِ عادی: سه فیلد بی‌ابهام باید بیت‌به‌بیت منبع باشد")
txt = build([row("20240120", 1000, 1100, 950, 1080, 500, 990, 1050)])
c, v, ar = CH._parse_tsetmc_csv(txt)
d = by_date(c)["2024-01-20"]
ck(d["open"] == 1000, "open == <FIRST> (نه <OPEN> که قیمتِ پایه است)", d["open"])
ck(d["close"] == 1080, "close درِ ناشر == <CLOSE> (مبنایِ بعدی درِ price_basis انتخاب می‌شود)", d["close"])
ck(d["last"] == 1050, "last == <LAST>", d["last"])
ck(v[0]["value"] == 500, "volume == <VOL>", v[0]["value"])
ck(d["high"] == 1100 and d["low"] == 950, "سایه دست‌نخورده وقتی خودش بدنه را دربر دارد", (d["high"], d["low"]))

print("═══ ۲) قاعدۀ تنها تحریفِ مجاز: سایه گِشاد می‌شود، قیمتِ منتشرشده خُرد نمی‌شود")
# <HIGH> زیرِ بدنه، <CLOSE> بالای آن: ناشر خودش با خودش نمی‌خواند
txt = build([row("20240121", 1968, 1990, 1960, 2001, 700, 2004, 1961)])
c, v, ar = CH._parse_tsetmc_csv(txt)
d = by_date(c)["2024-01-21"]
ck(d["high"] == max(1990, 1968, 2001), "high == max(<HIGH>,<FIRST>,<CLOSE>)", d["high"])
ck(d["low"] == min(1960, 1968, 2001), "low == min(<LOW>,<FIRST>,<CLOSE>)", d["low"])
ck(d["close"] == 2001 and d["last"] == 1961, "هیچ قیمتِ منتشرشده‌ای برایِ جاافتادنِ سایه خُرد نشد", (d["close"], d["last"]))
ck(d["low"] <= min(d["open"], d["close"]) and d["high"] >= max(d["open"], d["close"]),
   "هندسهٔ داخلی کندل پس از گِشاد معتبر است")

txt = build([row("20240122", 1957, 1958, 1950, 1916, 800, 1901, 1958)])
c, _, _ = CH._parse_tsetmc_csv(txt)
d = by_date(c)["2024-01-22"]
ck(d["low"] == min(1950, 1957, 1916), "پایانیِ زیرِ <LOW> ⇒ سایه به پایین گِشاد می‌شود", d["low"])
ck(d["high"] == max(1958, 1957, 1916), "وِ بالا دست‌نخورده می‌ماند", d["high"])

print("═══ ۳) روزِ بی‌معامله: کندل نمی‌شود، ولی برایِ تشخیصِ تعدیل گم نمی‌شود")
txt = build([
    row("20240201", 2122, 2130, 2100, 2122, 100, 2100, 2122),
    row("20240204", 0, 0, 0, 2122, 0, 2122, 2122),        # ردیفِ جانشان TSETMC
    row("20240205", 2140, 2160, 2120, 2150, 90, 2122, 2150),
])
c, v, ar = CH._parse_tsetmc_csv(txt)
days = sorted(by_date(c))
ck(days == ["2024-02-01", "2024-02-05"], "ردیفِ H=L=VOL=۰ کندل نمی‌شود (بی‌کندلِ جعلی)", days)
ck(any(r["time"] == "2024-02-04" for r in ar),
   "همان ردیف درِ all_rows می‌ماند — زنجیرۀ تعدیل به پایه/پایانیِ آن نیاز دارد",
   [r["time"] for r in ar])
ck(len(v) == 2, "سریِ حجم هم کندلِ جعلی نمی‌سازد", len(v))

print("═══ ۴) جعل ممنوع (شرطِ ۳ قرارداد): <LAST> خالی ⇒ None، نه کپیِ <CLOSE>")
txt = build([row("20240303", 500, 520, 480, 510, 10, 495, None)])
c, _, _ = CH._parse_tsetmc_csv(txt)
d = by_date(c)["2024-03-03"]
ck(d["last"] is None, "lastِ غایب None می‌ماند؛ قیمتِ پایانی جایگزینِ بی‌صدا نمی‌شود", d["last"])
ck(d["close"] == 510, "close همان <CLOSE> است و برچسبِ «آخرین» نمی‌گیرد", d["close"])

print("═══ ۵) FIRSTِ صفر رویِ روزِ دارایِ معامله: پایه داخلِ بازه clamp می‌شود")
txt = build([row("20240401", 0, 1825, 1825, 1825, 5, 1756, 1825)])
c, _, _ = CH._parse_tsetmc_csv(txt)
d = by_date(c)["2024-04-01"]
ck(d["open"] == 1825, "open بیرونِ [low, high] نمی‌افتد (کندلِ ناممکن ساخته نمی‌شود)", d["open"])
ck(d["low"] <= d["open"] <= d["high"], "هندسهٔ داخلی حفظ است", (d["low"], d["open"], d["high"]))

print("═══ ۶) هیچ ردیفِ جعلی اضافه نمی‌شود و ترتیبِ زمانی دست‌نخورده است")
txt = build([row(f"2024050{i}", 1000 + i, 1100 + i, 900 + i, 1050 + i, 10 + i, 1000 + i, 1050 + i)
             for i in range(1, 8)])
c, v, ar = CH._parse_tsetmc_csv(txt)
ck(len(c) == 7 and len(v) == 7, "تعدادِ کندل و حجم == تعدادِ ردیف‌هایِ معتبرِ CSV", (len(c), len(v)))
ck([x["time"] for x in c] == sorted(x["time"] for x in c), "ترتیبِ زمانی حفظ شد")
ck(all(x["time"].startswith("2024-05") for x in c), "همه از همان بازه‌اند، بی‌تاریخِ ساخته‌شده")

print(f"\n{len(PASSED)}_pass / {len(FAILED)}_fail")
if FAILED:
    for w in FAILED:
        print("  red:", w)
    sys.exit(1)
print("CANDLE SOURCE FIDELITY OK")
