# -*- coding: utf-8 -*-
"""tools/ra_parity.py — Reference Parity Test Suite (Step 5، کارِ #73).

هدفِ پروژه (docs/CANDLE-CONTRACT.md §۱-ت): چارتِ BorsTerminal تا حدِّ ممکن ۱:۱ با
رهاورد رفتار کند؛ تغییری که از همسان‌سازی با رهاورد بیاید regression نیست.

خروجی یکِ جدولِ مسطح است با ستون‌هایِ خواستۀ قرارداد:

    symbol · timeframe · price_basis · date · field
    reference · bors · absolute_err · relative_err · mismatch_type · suspected_source

و `mismatch_type` از واژۀ ثابتِ قرارداد است — هیچ واگرایی با «احتمالاً» بسته نمی‌شود:
    data_source · field_mapping · aggregation · adjustment · session_boundary
    timezone_date · rounding · missing_candle · extra_candle · reference_missing
    indicator_formula · parameter · rendering_transformation · match

مبنایِ سنجش‌ها از داده‌هایِ اندازه‌گیری‌شده می‌آید، نه فرض (قرارداد §۱-ج):
  • کدِ timeframe رهاورد: 0=روزانه ۱=هفتگی ۲=ماهانه (markupِ خودِ صفحهٔ چارتشان).
  • close آن‌ها = «آخرین قیمت»، open آن‌ها = FIRST.
  • سطلِ ماهِ آن‌ها **جلالی** است و سطلِ هفته **شنبه‌محور**.
  • حجمِ تجمیعیِ آن‌ها جمعِ روزها نیست، حجمِ روزِ اولِ سطل است (تصمیمِ مالک باز).
  • خودِ رهاورد از ۱۴۰۴-۱۲-۰۶ تا بهار ۱۴۰۵ حلقۀ دادۀ واقعی دارد ⇒ reference_missing.

نحوۀ اجرای بors-side:
  --source local  (پیش‌فرض) از تابع‌هایِ خودِ برنامه رویِ **کپیِ** بانک (market.db دست‌نخورده)
  --source api    از HTTPِ یکِ بک‌اندِ در حال اجرا (--base-url) — برایِ اثباتِ زنده

اجرا:  python tools/ra_parity.py --symbols فولاد,پارس --timeframes 0,1,2 --basis last,closing
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CACHE = os.path.join(ROOT, "_audit", "ra_probe_cache")
MISMATCH_KINDS = ("match", "rounding", "field_mapping", "aggregation", "adjustment",
                  "session_boundary", "timezone_date", "missing_candle", "extra_candle",
                  "reference_missing", "data_source", "indicator_formula", "parameter",
                  "rendering_transformation")
# تلورانسِ گردکردن: رهاورد عدد را با یکِ رقمِ اعشار می‌دهد و ما ریالِ صحیح؛ پس
# اختلافِ زیرِ نیم‌ریال «rounding» است نه field_mapping — این عدد از خودِ داده آمد،
# نه از سلیقه: §۱-ج پ نسبتِ closeِ ماهانه/روزانه = ۱٫۰۰۰۰۰۰ با cv=۰.
ROUND_EPS = 0.5


# ────────────────────────────── تقویمِ جلالی ──────────────────────────────
# الگوریتمِ jalaali-js (همان که `frontend/src/shared/lib/jalaliDate.ts` پیاده دارد) —
# بی‌آزمون باور نمی‌شود: `validate_jalali()` آن را با ستونِ jalali خودِ API رهاورد
# مقابله می‌کند و شمارِ ناهم‌خوانی را چاپ می‌کند (§۱-ج ت می‌گوید تطبیقِ تقویمی خودش
# منبعِ خطاست و باید از یکِ تبدیلِ واحدِ پروژه بیاید).
_GDM = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)


def g2j(gy, gm, gd):
    """میلادی → جلالی (jy, jm, jd). تقسیمِ صحیحِ کف‌محور با // (مثل ~~ در JS)."""
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100
            + (gy2 + 399) // 400 + gd + _GDM[gm - 1])
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return int(jy), int(jm), int(jd)


def jalali_of(date):
    return g2j(date.year, date.month, date.day)


def validate_jalali():
    """سنجشِ تبدیل با oracleِ خودِ مرجع: ستونِ jalaliِ ردیف‌هایِ رهاورد.

    بازگشت: (ردیف‌هایِ آزموده، ناهم‌خوانی‌ها). صفرِ ناهم‌خوانی یعنی همین تبدیل برایِ
    سطل‌بندیِ جلالیِ ماهانه قابلِ استفاده است؛ وگرنه Step 5 با تبدیلِ خودی پیش نمی‌رود.
    """
    tried = bad = 0
    examples = []
    for ins in ("46348559193224090", "48990026850202503", "6110133418282108",
                "35366681030756042", "65883838195688438"):
        try:
            raw = ra_rows(ins, 0)
        except Exception:
            continue
        for d, c in raw.items():
            j = c.get("jalali")
            if not j or len(j) != 8:
                continue
            day = dt.date.fromisoformat(d)
            jy, jm, jd = jalali_of(day)
            got = f"{jy:04d}{jm:02d}{jd:02d}"
            tried += 1
            if got != j:
                bad += 1
                if len(examples) < 3:
                    examples.append((d, j, got))
    return tried, bad, examples


# ───────────────────────────────── مرجع (رهاورد) ─────────────────────────────────
def ra_rows(ins_code, tf):
    os.makedirs(CACHE, exist_ok=True)
    key = os.path.join(CACHE, "httpstradersarenairdata%spricestimeframe%d.json" % (ins_code, tf))
    if os.path.isfile(key):
        raw = json.load(open(key, encoding="utf-8"))["candles"]
    else:
        req = urllib.request.Request(
            f"https://tradersarena.ir/data/{ins_code}/prices?timeframe={tf}",
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://tradersarena.ir/"})
        raw = json.loads(urllib.request.urlopen(req, timeout=90).read().decode("utf-8", "replace"))["candles"]
        json.dump({"candles": raw}, open(key, "w", encoding="utf-8"))
    out = {}
    for r in raw:
        if len(r) < 7:
            continue
        d = dt.datetime.fromtimestamp(int(r[0]), dt.timezone.utc).date()
        out[d.isoformat()] = {"open": float(r[1]), "high": float(r[2]), "low": float(r[3]),
                              "close": float(r[4]), "volume": float(r[5]),
                              "jalali": str(int(r[6]))}
    return out


# ───────────────────────────────── بors-side ─────────────────────────────────
def bors_series_local(symbol, ins_code, basis):
    """سریِ روزانۀ ما، از همان مسیرِ تولیدِ کندل (bank copy) و با همان price_basis."""
    import candle_contract as K
    import price_basis
    price_basis.set_basis(basis)
    con = sqlite3.connect(DB_COPY)
    rows = con.execute("SELECT symbol, date, open, high, low, close, volume, last, value, src"
                       " FROM price_history WHERE symbol=? ORDER BY date", (symbol,)).fetchall()
    con.close()
    candles = [K.from_db_row(r) for r in rows]
    candles = [c for c in candles if c]
    meta = K_meta = price_basis.apply_basis(candles, copy=False)
    return ({c["time"]: {"open": c["open"], "high": c["high"], "low": c["low"],
                         "close": c["close"], "volume": c["volume"]} for c in candles}, meta)


def bors_series_display(symbol, basis):
    """سریِ **نمایشیِ** ما: همان چیزی که چارت رسم می‌کند — کندل + ضربِ ضریبِ تعدیلِ خودِ ما.

    چرا این پیش‌فرض است: پاسخِ رهاورد تعدیلِ برگشتی است (§۰: k≈۱۵٫۴۶ فولاد). مقابلهٔ
    سریِ خامِ ما با سریِ تعدیل‌شده‌ی آن‌ها حتی در فضایِ عملکرد هم شکل را فرق می‌دهد —
    اولینِ اجرای هارنس دقیقاً همین را «data_source» زد (۲۰۲۴-۰۸-۲۴: ما ۱۲۱٫۹۶،
    آن‌ها ۶۰٫۳۵). پس parity یعنی: سریِ نمایشیِ ما ⇄ سریِ نمایشیِ آن‌ها.

    مسیرِ CDN خودِ برنامه (`get_chart_tsetmc`) هر دو مبنای خام را درِ کندل نگه می‌دارد
    (`close` منتخب، `closing` لنگر) و `factors` را از گسستِ «قیمت پایه» می‌سازد — همان
    ضرایبی که فرانت می‌زند. اینجا همان ضرب درِ سرور انجام می‌شود تا عددِ سنجیده‌شده
    عددِ رویِ چارت باشد.
    """
    import api.chart as CH
    import price_basis
    price_basis.set_basis(basis)
    j = CH.get_chart_tsetmc(symbol)
    if j.get("status") != "success":
        return {}, {"error": j.get("message")}
    fac = {f["time"]: float(f["factor"]) for f in j.get("factors") or []}
    out = {}
    for c in j.get("candles") or []:
        k = fac.get(c["time"], 1.0)
        out[c["time"]] = {"open": (c.get("open") or 0) * k, "high": (c.get("high") or 0) * k,
                          "low": (c.get("low") or 0) * k, "close": (c.get("close") or 0) * k,
                          "volume": (c.get("volume") or 0) / k if k else None}
    return out, {"basis_applied": j.get("priceBasis"), "reason": j.get("priceBasisReason"),
                 "adjustSource": j.get("adjustSource"), "events": len(j.get("adjustEvents") or [])}


def bors_series_api(base_url, symbol, basis):
    import urllib.parse
    u = f"{base_url}/api/chart-db/{urllib.parse.quote(symbol)}"
    j = json.loads(urllib.request.urlopen(u, timeout=120).read().decode("utf-8", "replace"))
    out = {c["time"]: {k: c.get(k) for k in ("open", "high", "low", "close", "volume")}
           for c in j.get("candles") or []}
    return out, {"basis_applied": j.get("priceBasis"), "reason": j.get("priceBasisReason")}


def aggregate(daily, tf, basis):
    """تجمیعِ ما با همان قواعدی که درِ رهاورد **اندازه گرفته شد** (§۱-ج ب/پ):
       tf=1 سطلِ شنبه، tf=2 سطلِ ماهِ جلالی؛ open=روزِ اول، close=آخرینِ روز،
       high=max، low=min، و volume = حجمِ روزِ اولِ سطل (قاعدۀ مرجع — رأیِ حجمِ مالک باز است)."""
    if tf == 0:
        return daily
    buckets = {}
    for d, c in sorted(daily.items()):
        day = dt.date.fromisoformat(d)
        if tf == 1:
            key = (day - dt.timedelta(days=(day.weekday() + 2) % 7)).isoformat()   # شنبه
        else:
            jy, jm, _ = jalali_of(day)
            key = (jy, jm)
        buckets.setdefault(key, []).append((d, c))
    out = {}
    for key, items in buckets.items():
        items.sort(key=lambda x: x[0])
        first_d, first = items[0]
        last_d, last = items[-1]
        out[first_d] = {"open": first["open"], "high": max(c["high"] for _, c in items),
                        "low": min(c["low"] for _, c in items), "close": last["close"],
                        "volume": first["volume"], "ndays": len(items), "end": last_d}
    return out


# ───────────────────────────────── مقابله ─────────────────────────────────
def to_performance(series):
    """هر سری را با closeِ **آخرینِ کندل خودش** نرمال می‌کند (آخرین = ۱۰۰).

    چرا: سریِ رهاورد تعدیلِ برگشتی است و سریِ خامِ ما نه (§۰ قرارداد: k≈۱۵٫۴۶ فولاد).
    مقابلهٔ عدد-به-عددِ این دو فضای متفاوت، نه parity است نه واگرایی — اولینِ اجرای
    این هارنس ۱٬۶۵۴ ردیف را بی‌دلیل «data_source» زد. درِ فضایِ عملکرد، مقیاسِ هر دو
    سری حذف می‌شود و فقط *شکلِ* تاریخچه مقابله می‌شود؛ حجم درِ این فضا مقابله نمی‌شود.
    """
    if not series:
        return {}
    last_day = max(series)
    base = series[last_day].get("close")
    if not base:
        return {}
    out = {}
    for d, c in series.items():
        out[d] = {k: (v / base * 100.0) if (k in ("open", "high", "low", "close") and v is not None)
                  else (v if k == "volume" else None)
                  for k, v in c.items()}
        out[d]["volume"] = None      # حجم درِ فضایِ عملکرد بی‌معناست (تعدیلِ حجم جداست)
    return out


def implied_ratio(ref, our):
    """نسبتِ عددِ مرجع به عددِ ما رویِ همان روز (شاهد، نه حدس).

    سریِ کندلِ رهاورد **تعدیلِ برگشتی** است (§۰ قرارداد: k≈۱۵٫۴۶ برایِ فولاد) و سریِ
    محلیِ ما خام + ضرایبِ جداست. مقابلهٔ بی‌واسطهٔ این دو، هر اختلافی را «واگرایی»
    نشان می‌دهد؛ پس نسبتِ محفوظِ هر جفت حساب می‌شود و با میانۀ همان نماد/تایم‌فریم
    سنجیده می‌شود: ردیفی که نسبتش با میانه می‌خواند، درِ همان «فضایِ تعدیل» است و
    واگراییِ قیمت نیست.
    """
    if not ref or not our:
        return None
    return ref / our


def classify(field, ref, our, ratio, median_ratio, space="raw"):
    """مismatch-type با شاهد: اول فضایِ تعدیل، بعد تلورانس، بعد نوع."""
    if ref is None and our is None:
        return None, ""
    if ref is None:
        return "reference_missing", "مرجع این نشست را ندارد (حلقۀ ۱۴۰۴-۱۲ که درِ §۱-ج ت سنجیده شد)"
    if our is None:
        return "missing_candle", "بانکِ ما این نشست را ندارد (عمق/backfill — §۱-ه)"
    ae = abs(ref - our)
    rel = ae / abs(ref) if ref else None
    if space == "performance":
        # آستانه‌ها ابداعی نیستند: توزیعِ اندازه‌گیری‌شده‌ی خطایِ نسبی (p50=۰٫۰۰۳۱۷،
        # p90=۰٫۰۰۳۵۱، و صفرِ مطلق از ۲۰۲۳-۰۳-۲۸ به بعد) دو دسته می‌سازد — یا
        # «همان عدد» (≤۰٫۱٪) یا یکِ گامِ ~۰٫۳٪ که همان اختلافِ جدولِ ضرایبِ تعدیل است.
        if rel is not None and rel <= 0.001:
            return ("match", "شکلِ یکسان درِ فضایِ عملکرد (≤۰٫۱٪)")
        if rel is not None and 0.001 < rel <= 0.005:
            return ("adjustment", "گامِ ~۰٫۳٪: جدولِ ضرایبِ تعدیلِ ما با مرجع درِ یکِ رویداد "
                                  "می‌جنگد (تاریخِ گام درِ ستونِ date همین سطر)")
        if rel is not None and rel <= 0.01:
            return ("adjustment", "اختلافِ ≤۱٪ درِ فضایِ عملکرد — ضرایبِ تعدیل")
    elif ae <= ROUND_EPS:
        return ("match", "همان عدد، در یک فضا") if ae == 0 else ("rounding", "زیرِ نیم‌ریال")
    r = ratio
    if median_ratio and r and abs(r / median_ratio - 1.0) < 0.002:
        return ("adjustment", "نسبتِ مرجع/ما == میانۀ تعدیلِ همان نماد ⇒ اختلافِ فضایِ "
                              "تعدیل است، نه واگراییِ قیمت (مقایسه با --space performance)")
    if rel is not None and rel < 0.01:
        return ("field_mapping", "اختلافِ زیرِ ۱٪ با نسبتِ تعدیل نمی‌خواند — نگاشتِ فیلد/روزِ متنازع")
    if field == "open":
        return ("field_mapping", "open: FIRST در برابرِ پایه/پیش‌close (سنجشِ §۱-ج الف)")
    if field in ("high", "low"):
        return ("aggregation", "سایه/حدودِ سطل — قاعدۀ widen یا پنجرۀ سطل")
    if field == "close":
        return ("data_source", "close با اختلافِ بیش از تلورانس و بی‌نسبتِ تعدیل — ریشه‌یابیِ دستی")
    if field == "volume":
        return ("aggregation", "قاعدۀ حجمِ سطل (جمع در برابرِ روزِ اول) — رأیِ مالک باز (§۱-ج پ)")
    return ("data_source", "بی‌طبقه — پیش از هر اصلاح باید ریشه‌یابی شود")


def compare(symbol, tf, basis, ref, our, rows, space="raw"):
    """مقابلهٔ یکِ (نماد × تایم‌فریم × مبنای). دو پاس: میانۀ نسبتِ تعدیل، بعد طبقه‌بندی."""
    days = sorted(set(ref) | set(our))
    shared = [d for d in days if ref.get(d) and our.get(d)]
    rs = sorted(v for v in (implied_ratio(ref[d]["close"], our[d]["close"]) for d in shared) if v)
    median_ratio = rs[len(rs) // 2] if rs else None
    for d in days:
        r, o = ref.get(d), our.get(d)
        for field in ("open", "high", "low", "close", "volume"):
            rv = r.get(field) if r else None
            ov = o.get(field) if o else None
            if rv is None and ov is None:
                continue
            if space == "performance" and field == "volume":
                continue
            ratio = implied_ratio(rv, ov)
            mt, why = classify(field, rv, ov, ratio, median_ratio, space)
            if mt is None:
                continue
            ae = abs(rv - ov) if (rv is not None and ov is not None) else None
            re_ = (ae / abs(rv)) if (ae is not None and rv) else None
            rows.append({"symbol": symbol, "timeframe": tf, "price_basis": basis, "date": d,
                         "field": field, "reference": rv, "bors": ov,
                         "absolute_err": None if ae is None else round(ae, 4),
                         "relative_err": None if re_ is None else round(re_, 6),
                         "implied_ratio": None if ratio is None else round(ratio, 6),
                         "median_ratio": None if median_ratio is None else round(median_ratio, 6),
                         "mismatch_type": mt, "suspected_source": why})
    return median_ratio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="فولاد,پارس")
    ap.add_argument("--timeframes", default="0", help="0 روزانه، 1 هفتگی، 2 ماهانه (کدِ خودِ رهاورد)")
    ap.add_argument("--basis", default="last", help="last | closing (پیش‌فرض last)")
    ap.add_argument("--source", choices=("display", "local", "api"), default="display",
                    help="display = سریِ نمایشیِ ما (کندل × ضریبِ تعدیلِ خودِ برنامه، پیش‌فرض)؛ "
                         "local = خامِ بانک؛ api = HTTPِ یکِ بک‌اندِ در حال اجرا")
    ap.add_argument("--base-url", default="http://127.0.0.1:8002")
    ap.add_argument("--space", choices=("raw", "performance"), default="performance",
                    help="raw = عددِ ریالی (فقط آن‌جا که دو سری هم‌مقیاس‌اند)؛ "
                         "performance = هر سری با آخریِ خودش (پیش‌فرض — فضایِ رهاورد تعدیلِ برگشتی است)")
    ap.add_argument("--out", default=os.path.join(ROOT, "_audit", "ra_parity_report.json"))
    a = ap.parse_args()
    global DB_COPY
    import tempfile
    DB_COPY = os.path.join(tempfile.mkdtemp(prefix="parity_"), "copy.db")
    src = os.path.join(ROOT, "market.db")
    x = sqlite3.connect(src, timeout=60); y = sqlite3.connect(DB_COPY)
    with y:
        x.backup(y)
    x.close(); y.close()
    import mstat_engine
    cc = sqlite3.connect(DB_COPY)
    mstat_engine.ensure_schema(cc)
    ins_map = {n: i for n, i in cc.execute("SELECT l_val18, ins_code FROM instruments")}
    cc.close()

    tried, bad, examples = validate_jalali()
    print(f"[jalali] تبدیل با ستونِ jalali خودِ مرجع سنجیده شد: {tried:,} ردیف، "
          f"ناهم‌خوانی {bad}  {examples}")
    if tried and bad:
        print("  ⛔ تبدیلِ جلالیِ خودی با مرجع نمی‌خواند — سطل‌بندیِ ماهانه را نمی‌توان "
              "با آن بست. گزارشِ parity بی‌اعتماد است.")
    rows = []
    for sym in [s.strip() for s in a.symbols.split(",") if s.strip()]:
        ins = str(ins_map.get(sym) or "")
        if not ins:
            print(f"  {sym}: ins_code درِ بانک نیست — رد می‌شود (بی‌حدس)")
            continue
        for basis in [b.strip() for b in a.basis.split(",") if b.strip()]:
            if a.source == "local":
                daily, meta = bors_series_local(sym, ins, basis)
            elif a.source == "api":
                daily, meta = bors_series_api(a.base_url, sym, basis)
            else:
                daily, meta = bors_series_display(sym, basis)
            if not daily:
                print(f"  {sym} [{basis}]: سریِ ما نداشت {meta.get('error') or meta} — رد")
                continue
            print(f"  {sym} [{basis}] bors: {len(daily)} کندل | مبنایِ اعمال‌شده="
                  f"{meta.get('basis_applied')} {meta.get('reason') or ''} | "
                  f"رویدادِ تعدیل={meta.get('events', '—')} ({meta.get('adjustSource','')})")
            for tf in [int(x) for x in a.timeframes.split(",")]:
                ref = ra_rows(ins, tf)
                ours = aggregate(daily, tf, basis)
                if a.space == "performance":
                    ref, ours = to_performance(ref), to_performance(ours)
                mr = compare(sym, tf, basis, ref, ours, rows, a.space)
                print(f"  [{sym} tf={tf} basis={basis}] میانۀ نسبتِ تعدیلِ مرجع/ما = "
                      f"{mr if mr is None else round(mr, 4)}")
    kinds = Counter(r["mismatch_type"] for r in rows)
    out = {"generated": dt.datetime.now().isoformat(timespec="seconds"),
           "source": a.source, "rows": len(rows), "by_mismatch_type": dict(kinds),
           "space": a.space, "price_basis_requested": a.basis,
           "note": "reference = Rahavard (tradersarena) · bors = این برنامه · "
                   "تجمیع با قواعدِ سنجیده‌شده‌ی §۱-ج (شنبه/جلالی) و حجمِ روزِ اولِ سطل",
           "table": rows}
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "table"}, ensure_ascii=False, indent=1))
    for k, n in kinds.most_common(6):
        ex = next(r for r in rows if r["mismatch_type"] == k)
        print(f"  {k:<20} {n:>6}  نمونه: {ex['symbol']} tf={ex['timeframe']} {ex['date']} "
              f"{ex['field']} ref={ex['reference']} bors={ex['bors']} | {ex['suspected_source'][:60]}")
    print("نوشته شد:", a.out)
    import shutil
    shutil.rmtree(os.path.dirname(DB_COPY), ignore_errors=True)


DB_COPY = None
if __name__ == "__main__":
    main()
