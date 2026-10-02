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
    # حجم درِ پاسخِ CDN داخلِ کندل نیست: `candles` بی‌volume است و حجم درِ آرایۀ جداِ
    # `volumes` (کلیدِ `value`) می‌آید؛ درِ مسیرِ دیتابیس (`get_chart_db`) برعکس، کندل
    # خودش volume دارد. این تفاوتِ شکلِ payload خودش یکِ یافته است (§۱-ح) ولی اینجا
    # باید هر دو را یکی بخوانیم، وگرنه حجمِ ما صفر می‌شود و سنجشِ حجم بی‌محتوا.
    vol = {v["time"]: (v.get("value") or 0) for v in (j.get("volumes") or [])}
    out, raw_out = {}, {}
    for c in j.get("candles") or []:
        k = fac.get(c["time"], 1.0)
        v = c.get("volume")
        if v is None:
            v = vol.get(c["time"], 0)
        out[c["time"]] = {"open": (c.get("open") or 0) * k, "high": (c.get("high") or 0) * k,
                          "low": (c.get("low") or 0) * k, "close": (c.get("close") or 0) * k,
                          "volume": (v or 0) / k if k else None}
        raw_out[c["time"]] = {"open": c.get("open") or 0, "high": c.get("high") or 0,
                              "low": c.get("low") or 0, "close": c.get("close") or 0,
                              "volume": v or 0,
                              "closing": c.get("closing"), "last": c.get("last")}
    return out, {"basis_applied": j.get("priceBasis"), "reason": j.get("priceBasisReason"),
                 "adjustSource": j.get("adjustSource"), "events": (j.get("adjustEvents") or []),
                 # رویدادها فهرست‌اند (تعدادش برایِ چاپ گرفته می‌شود): factor_schedule
                 # باید تاریخِ هر رویداد را ببیند، نه شمارِ آن.
                 "n_events": len(j.get("adjustEvents") or []),
                 # سریِ **خامِ همان منبع** (بی‌ضریب) — با کلیدِ «_» از گزارشِ JSON بیرون
                 # می‌ماند و فقط خوراکِ استنتاجِ k_ref است.
                 "_raw_series": raw_out}


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
        vals = [c.get("volume") for _, c in items if c.get("volume") is not None]
        out[first_d] = {"open": first["open"], "high": max(c["high"] for _, c in items),
                        "low": min(c["low"] for _, c in items), "close": last["close"],
                        "volume": first["volume"],
                        "volume_sum": sum(vals) if vals else None,
                        "ndays": len(items), "end": last_d}
    return out


def day_alignment(ref, our, tf):
    """تفکیکِ «سطل‌بندیِ متفاوت» از «حلقۀ دادۀ مرجع».

    اگر کلیدِ سطلِ ما با سطلِ خودِ مرجع یکی نباشد، مقابله پر از reference_missing و
    missing_candle می‌شود و آن‌ها با «کندلِ جاافتاده» یکی نیستند. این تابع پیش از
    هر طبقه‌بندیِ عددی، فقط مجموعۀ روزها را می‌شمارد.
    """
    shared = sorted(set(ref) & set(our))
    only_ref = sorted(set(ref) - set(our))
    only_our = sorted(set(our) - set(ref))
    return {"tf": tf, "shared": len(shared), "only_reference": len(only_ref),
            "only_bors": len(only_our),
            "first_shared": shared[0] if shared else None,
            "last_shared": shared[-1] if shared else None,
            "only_reference_days": only_ref[:40], "only_bors_days": only_our[:8],
            "sample_only_reference": only_ref[:4], "sample_only_bors": only_our[:4]}


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


def compare(symbol, tf, basis, ref, our, rows, space="raw", ref_raw=None, our_raw=None):
    """مقابلهٔ یکِ (نماد × تایم‌فریم × مبنای). دو پاس: میانۀ نسبتِ تعدیل، بعد طبقه‌بندی."""
    ref_raw = ref if ref_raw is None else ref_raw
    our_raw = our if our_raw is None else our_raw
    days = sorted(set(ref) | set(our))
    shared = [d for d in days if ref.get(d) and our.get(d)]
    rs = sorted(v for v in (implied_ratio(ref[d]["close"], our[d]["close"]) for d in shared) if v)
    median_ratio = rs[len(rs) // 2] if rs else None
    # ضریبِ میانه درِ فضایِ خام: تنها چیزی که تستِ دقتِ انتشار به آن نیاز دارد.
    rraw = sorted(v for v in (implied_ratio(ref_raw.get(d, {}).get("close"),
                                            our_raw.get(d, {}).get("close"))
                              for d in shared if d in ref_raw and d in our_raw) if v)
    median_raw = rraw[len(rraw) // 2] if rraw else None
    for d in days:
        r, o = ref.get(d), our.get(d)
        rr, orr = ref_raw.get(d) or {}, our_raw.get(d) or {}
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
                         "median_raw": None if median_raw is None else round(median_raw, 6),
                         "precision_ok": precision_explained(rr.get(field), orr.get(field),
                                                             median_raw),
                         "mismatch_type": mt, "suspected_source": why})
    return median_ratio



PRICE_FIELDS = ("open", "high", "low", "close")


def regroup_by_day(rows):
    """طبقه‌بندیِ نهایی با شاهدِ روز، نه با آستانهٔ تنها-فیلد.

    شاهدِ روز = closeِ همان روز. سه و فقط سه حالت:

      • close می‌جنگد (>.۱٪) ⇒ تمامِ بدنه و سایه درِ همان مقیاس می‌جنگند ⇒ `adjustment`
        (جدولِ ضرایبِ تعدیل درِ آن دورۀ زمانی با مرجع فرق دارد).
      • close می‌خواند و high/low می‌جنگد ⇒ `aggregation` — بدنه توافق دارد و سایه نه؛
        این همان تفکیکی است که بندِ ۲ خواست (قعدۀ widen یا پنجرۀ سطل).
      • close می‌خواند و open می‌جنگد ⇒ `field_mapping` — مقیاس یکی است و ستون نه.

    نسخهٔ اولِ این تابع شعبهٔ اول را «close_matches و فیلد در PRICE» می‌گرفت و پس هر
    سایۀ روزِ هم‌مقیاس را `adjustment` می‌خواند (۸٬۵۵۶ سطرِ aggregation به ۲۰۵ کاهش یافت).
    نسخهٔ دوم بازِ بدونِ سقفِ خطا هر چیزی بالای ۰٫۱٪ را `adjustment` خواند و طبقاتِ
    data_source/field_mapping را صفر کرد. هر دو با دادهٔ خودِ گزارش دیده شد و اصلاح شد.
    """
    by_day = {}
    for r in rows:
        by_day.setdefault((r["symbol"], r["timeframe"], r["price_basis"], r["date"]), []).append(r)
    for key, grp in by_day.items():
        close = next((g for g in grp if g["field"] == "close"), None)
        crel = close["relative_err"] if close else None
        close_matches = crel is not None and crel <= 0.001
        for g in grp:
            if g["relative_err"] is None:
                continue
            if g["mismatch_type"] in ("missing_candle", "extra_candle", "reference_missing"):
                continue
            if g["relative_err"] <= 0.001 or g["field"] not in PRICE_FIELDS:
                continue
            if close_matches:
                if g["field"] in ("high", "low"):
                    g["mismatch_type"] = "aggregation"
                    g["suspected_source"] = ("closeِ همان روز می‌خواند (≤۰٫۱٪) ولی " + g["field"] +
                                             " نمی‌خواند ⇒ قاعدۀ سایه یا پنجرۀ سطل، "
                                             "نه جدولِ ضرایبِ تعدیل")
                elif g["field"] == "open":
                    g["mismatch_type"] = "field_mapping"
                    g["suspected_source"] = ("closeِ همان روز می‌خواند و فقط body فرق دارد ⇒ "
                                             "نگاشتِ ستونِ open (FIRST در برابرِ پایه/پیش‌close)")
            else:
                g["mismatch_type"] = "adjustment"
                g["suspected_source"] = ("خودِ close این روز هم می‌جنگد ⇒ مقیاسِ سری درِ "
                                         "این دورۀ زمانی با مرجع فرق دارد (رویدادِ ضریب)، "
                                         "نه کندلِ متفاوت")
    return rows


def _ladder(pairs, eps=0.0005):
    """گام‌هایِ یکِ پلکان: روز‌هایی که نسبتِ (مرجع/سریِ ما) بیش از eps عوض می‌شود."""
    steps = []
    for (d0, k0), (d1, k1) in zip(pairs, pairs[1:]):
        if k0 and abs(k1 / k0 - 1.0) > eps:
            steps.append({"from_day": d0, "to_day": d1, "before": round(k0, 6),
                          "after": round(k1, 6), "ratio": round(k1 / k0, 6)})
    return steps


def factor_schedule(raw_our, disp_our, ref, events):
    """دو پلکانِ ضریب از یکِ داده، کنارِ رویدادهایِ خودِ ما.

    مرجع فاکتور منتشر نمی‌کند، ولی از خودِ دادۀ دو سری درمی‌آید (§۰ قرارداد همین را
    کرد: پراکندگی k از O/H/L ≈ ۰٫۰۰۰۰٪):

      k_ref(t) = ra_close(t) / close_خام(t)   → ضریبِ تعدیلِ **خودِ مرجع**
      gap(t)   = ra_close(t) / close_نمایشی(t) → فاصلۀ جدولِ ضرایبِ او با جدولِ ما
                 (نمایشی = خام × ضریبِ خودِ ما)

    گامِ k_ref = رویدادِ تعدیلِ آن‌ها. گامِ gap = روزی که عددهایِ چارتِ ما نسبت به
    عددهایِ روزهایِ قبل جابه‌جا می‌شود. تفکیکِ سه حالت:
      • گامِ k_ref در رویدادهایِ ما نیست → آن‌ها تعدیلی را می‌بینند که ما نمی‌بینیم
      • رویدادِ ما گامِ k_ref نسازد → ما تعدیلی می‌بینیم که آن‌ها تعدیل نمی‌کنند
      • گامِ gap در هیچ‌کدام نیست → ضریب نیست؛ خودِ قیمتِ خامِ دو منبع فرق دارد

    توجه: close_خام درِ اینجا همان **مبنایِ منتخبِ همان اجرا** است (`last` یا
    `closing`)، نه همیشه پایانی. پس پلکانِ k_ref خودش هم یکِ اندازه‌گیری است: اگر
    مرجع close را از «آخرین» می‌ساخت، درِ مبنایِ closing این پلکان پر‌گام می‌شود
    (نویزِ روزانۀ last/پایانی) و درِ مبنایِ last صاف. شمارِ گام‌ها درِ گزارش هست و
    این ادعا را می‌شود از همان JSON خواند — بی‌حدس.
    """
    days = sorted(set(raw_our) & set(ref))
    ks, gs = [], []
    for d in days:
        raw = raw_our[d].get("close")
        disp = (disp_our.get(d) or {}).get("close")
        rv = ref[d].get("close")
        if raw and rv:
            ks.append((d, rv / raw))
        if disp and rv:
            gs.append((d, rv / disp))
    steps = _ladder(ks)
    gap_steps = _ladder(gs, 0.0001)
    ev = sorted(str(e.get("date") or e.get("time") or "") for e in (events or []))
    ref_days = {s["to_day"] for s in steps}
    our_days = set(ev)
    gap_days = {s["to_day"] for s in gap_steps}
    unexplained = sorted(gap_days - ref_days - our_days)
    return {"k_first": round(ks[0][1], 6) if ks else None,
            "k_last": round(ks[-1][1], 6) if ks else None,
            "n_reference_steps": len(steps), "n_our_events": len(ev),
            "n_gap_steps": len(gap_steps),
            "reference_steps": steps[:200], "reference_step_days": sorted(ref_days),
            "our_events_all": ev[:200], "gap_steps": gap_steps[:200],
            "n_days_only_they_move": len(ref_days - our_days),
            "n_days_only_we_move": len(our_days - ref_days),
            "n_days_both": len(ref_days & our_days),
            "days_only_they_move": sorted(ref_days - our_days)[:40],
            "days_only_we_move": sorted(our_days - ref_days)[:40],
            "both": sorted(ref_days & our_days)[:40],
            "gap_days_explained_by_neither": unexplained[:40]}


def volume_rule(agg, ref_native, tf):
    """فقط اندازه‌گیری: دو فرضیۀ حجمِ سطل (روزِ اول، جمعِ روزها) با سطلِ **منتشرشدۀ خودِ مرجع**.

    بی‌تصمیم: رأیِ pilot «جمع بماند» بود و تصمیمِ نهایی با مالک است (§۱-ج پ). این تابع
    چیزی را عوض نمی‌کند، فقط می‌گوید کدامِ فرضیه با عددِ آن‌ها می‌خواند و چقدر.
    """
    if tf == 0 or not agg:
        return None
    days = sorted(set(agg) & set(ref_native))
    out = {"tf": tf, "buckets_shared": len(days)}
    for rule in ("volume", "volume_sum"):
        hits = tot = 0
        rels = []
        for d in days:
            a = agg[d].get(rule)
            r = ref_native[d].get("volume")
            if not a or not r:
                continue
            tot += 1
            if abs(a - r) / r <= 0.005:
                hits += 1
            rels.append(a / r)
        med = sorted(rels)[len(rels) // 2] if rels else None
        out[rule] = {"compared": tot, "match_within_0.5pct": hits,
                     "median_our_over_reference": None if med is None else round(med, 4)}
    ratios = []
    for d in days:
        a = agg[d].get("volume") or 0
        s = agg[d].get("volume_sum") or 0
        if a:
            ratios.append(s / a)
    out["median_our_sum_over_our_first"] = (round(sorted(ratios)[len(ratios) // 2], 3)
                                            if ratios else None)
    return out


def decimals_of(v):
    """تعدادِ ارقامِ اعشاریِ عددی که مرجع **منتشر کرده** است (نه انتخابِ ما).

    منبعِ تلورانسِ «rounding» همین است: اگر رهاورد 60.35 داده، دقتِ منتشرشدۀ او ۰٫۰۱
    است و هر اختلافی زیرِ نیمِ همان واحد با چاپِ خودش قابلِ بیان است. هیچ آستانۀ
    ابداعی درِ کار نیست.
    """
    s = repr(float(v))
    if "e" in s or "E" in s:
        return None
    if "." not in s:
        return 0
    return len(s.split(".")[1].rstrip("0"))


def precision_explained(ref, our, median):
    """آیا «مرجع ≈ گردکردۀ (ما × ضریبِ میانۀ همان نماد)» است؟ — بله/نه، با عددِ شاهد.

    True یعنی اختلافِ این سطر با همان دقتی که خودِ مرجع منتشر کرده می‌خواند و
    تعدیل/تجمیع نیست. برنگرداندنِ True درِ روزِ دارایِ گامِ ضریب درست است: آن‌جا
    ضریبِ میانه نمایندۀ آن روز نیست.
    """
    if ref is None or our is None or not median:
        return False
    d = decimals_of(ref)
    if d is None:
        return False
    mapped = our * median
    return abs(mapped - ref) <= 0.5 * (10 ** -d) + 1e-9


def reclassify_precision(rows):
    """سطرهایِ «تعدیل/تجمیع» که با دقتِ انتشارِ خودِ مرجع می‌خورند → rounding.

    پیش از آن‌که یکِ عدد را «رویدادِ ضریب» بنامیم، باید ثابت شود با چاپِ مرجع
    توضیح داده نمی‌شود. این پاس همان تستِ قطعی را می‌زند و نوع را عوض می‌کند؛
    سطرهایِ از پیش match و سطرهایِ «بود/نبود» دست نمی‌خورند.
    """
    moved = 0
    for r in rows:
        if not r.get("precision_ok") or r["relative_err"] is None:
            continue
        if r["mismatch_type"] in ("match", "rounding", "reference_missing",
                                  "missing_candle", "extra_candle"):
            continue
        if r["relative_err"] <= 0.005:
            r["mismatch_type"] = "rounding"
            r["suspected_source"] = ("اختلاف با دقتِ منتشرشدۀ خودِ مرجع "
                                     "(±½ واحدِ آخرین رقم) و ضریبِ میانۀ همان نماد می‌خواند ⇒ "
                                     "گردکردن، نه رویدادِ ضریب")
            moved += 1
    return rows, moved


def era_profile(batch, min_run=5):
    """پروفیلِ خطایِ close روز‌به‌روز → دورۀ ثابت‌ها.

    چرا لازم است: «adjustment» با آستانه به‌تنهایی دو چیزِ خیلی متفاوت را می‌شمارد —
    یکِ روزِ نامعلوم با خطایِ بزرگ، و یکِ offsetِ ثابت که کلِ چندسالِ تاریخ را جابه‌جا
    می‌کند (نشانه‌اش: چندصدِ روزِ پیاپی با یکِ عددِ خطا). این تابع همان ساختار را
    بی‌نمونه‌برداری می‌شمارد: هر گامِ خطا یکِ دورۀ تازه است.
    """
    cl = sorted((r["date"], r["relative_err"]) for r in batch
                if r["field"] == "close" and r["relative_err"] is not None)
    runs = []
    for d, e in cl:
        if runs:
            r = runs[-1]
            if abs(e - r["sum"] / r["n"]) <= 0.0002:
                r["to"], r["n"], r["sum"] = d, r["n"] + 1, r["sum"] + e
                continue
        runs.append({"from": d, "to": d, "n": 1, "sum": e})
    for r in runs:
        r["mean_rel_err"] = round(r["sum"] / r["n"], 6)
        del r["sum"]
    long_runs = [r for r in runs if r["n"] >= min_run]
    return {"close_days": len(cl), "n_error_runs": len(runs),
            "n_long_runs": len(long_runs),
            "long_runs": long_runs[:24],
            "days_in_long_runs": sum(r["n"] for r in long_runs),
            "single_day_errors": len(runs) - len(long_runs)}


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
    ap.add_argument("--cap", type=int, default=200,
                    help="سقفِ سطرهایِ جدولِ نمونه در هر (نماد×تایم‌فریم×مبنای×نوع)؛ "
                         "شمارِ by_mismatch_type کامل است و به این وابسته نیست")
    a = ap.parse_args()
    tf_list = [int(x) for x in a.timeframes.split(",") if x.strip() != ""]
    basis_list = [b.strip() for b in a.basis.split(",") if b.strip()]
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
    # ── دو safeguard که بی‌آن‌ها این اجرا «رویِ کپی» نیست:
    # ۱) `--source display` از api.chart می‌گذرد و آن DB_PATH را درِ import می‌بندد؛
    #    مسیرِ fallbackِ چارت (`_schedule_history_repair`) می‌تواند fetch_price_history
    #    را درِ thread بنشاند و بانکِ کاری را **بنویسد**. پس پیش از import به کپی
    #    اشاره می‌کنیم و بعد از import هر ماژولِ بسته‌شده را هم تصحیح می‌کنیم.
    # ۲) تنظیمِ مبنایِ قیمت هم فایلِ خودِ برنامه است، پس به فایلِ موقتِ هارنس می‌رود.
    import bors_config
    import price_basis
    basis_before = price_basis.current()
    bors_config.DB_PATH = DB_COPY
    # تنظیمِ مبنای قیمت هم به فایلِ موقتِ خودِ هارنس می‌رود: `price_basis.json` درِ
    # WORK_DIR تنظیمِ واقعیِ برنامه است و این اجرا آن را بارها عوض می‌کند. با
    # _path() که هر بار از bors_config می‌خواند، این جایگزینی کافی است.
    bors_config.PRICE_BASIS_PATH = os.path.join(os.path.dirname(DB_COPY), "price_basis.json")
    for _m in ("api._core", "api.chart", "api.market", "api.screener", "api.fundamental"):
        _mod = sys.modules.get(_m)
        if _mod is not None:
            _mod.DB_PATH = DB_COPY
    print(f"[copy] بانکِ کاری دست‌نخورده · سنجش رویِ {DB_COPY} · "
          f"settingِ برنامه={basis_before} (هارنس رویِ فایلِ موقت می‌نویسد)")

    tried, bad, examples = validate_jalali()
    print(f"[jalali] تبدیل با ستونِ jalali خودِ مرجع سنجیده شد: {tried:,} ردیف، "
          f"ناهم‌خوانی {bad}  {examples}")
    if tried and bad:
        print("  ⛔ تبدیلِ جلالیِ خودی با مرجع نمی‌خواند — سطل‌بندیِ ماهانه را نمی‌توان "
              "با آن بست. گزارشِ parity بی‌اعتماد است.")
    rows, vol_rows, align_rows, report_symbols = [], [], [], []
    counts, by_tf, by_field, per = Counter(), Counter(), Counter(), Counter()
    dropped = precision_moved = 0

    def _dump(partial=False):
        """گزارش را بنویس — هر ۶ دسته، تا یکِ خطایِ میانیِ ۳۶نمادی کلِ کار را نَبَرَد."""
        kept = [r for r in rows if r["mismatch_type"] != "match"]
        body = {"generated": dt.datetime.now().isoformat(timespec="seconds"),
                "partial": partial, "source": a.source, "space": a.space,
                "price_basis_requested": a.basis, "timeframes": a.timeframes,
                "symbols_requested": len([s for s in a.symbols.split(",") if s.strip()]),
                "symbols_done": len({(r["symbol"], r["basis"]) for r in report_symbols}),
                "rows_compared": sum(counts.values()), "rows_kept": len(kept),
                "table_sample_cap": a.cap, "table_sample_dropped": dropped,
                "precision_explained_rows": precision_moved,
                "by_mismatch_type": dict(counts), "by_mismatch_type_and_tf": dict(by_tf),
                "by_mismatch_field_and_tf": dict(by_field),
                "by_field": dict(Counter(r["field"] for r in kept)),
                "jalali_validation": {"rows": tried, "mismatches": bad},
                "note": "reference = Rahavard (tradersarena) · bors = سریِ نمایشیِ این برنامه "
                        "(کندل × ضریبِ تعدیلِ خودِ برنامه) · تجمیع با قواعدِ سنجیده‌شده‌ی §۱-ج "
                        "(شنبه/جلالی)؛ حجم درِ فضایِ عملکرد مقابله نمی‌شود و درِ volume_rules "
                        "جدا اندازه گرفته می‌شود",
                "volume_rules": vol_rows, "day_alignment": align_rows,
                "per_symbol": report_symbols, "table": kept}
        json.dump(body, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return body

    for sym in [s.strip() for s in a.symbols.split(",") if s.strip()]:
        ins = str(ins_map.get(sym) or "")
        if not ins:
            print(f"  {sym}: ins_code درِ بانک نیست — رد می‌شود (بی‌حدس)")
            continue
        for basis in basis_list:
            try:
                if a.source == "local":
                    daily, meta = bors_series_local(sym, ins, basis)
                    meta["_raw_series"] = daily
                elif a.source == "api":
                    daily, meta = bors_series_api(a.base_url, sym, basis)
                    meta["_raw_series"] = daily
                else:
                    daily, meta = bors_series_display(sym, basis)
            except Exception as e:      # noqa: BLE001 — یکِ نماد گزارش را نباید بخورَد
                print(f"  {sym} [{basis}] ⚠ خطا درِ سریِ ما: {type(e).__name__}: {e}")
                report_symbols.append({"symbol": sym, "basis": basis,
                                       "error": f"{type(e).__name__}: {e}"})
                _dump(partial=True)
                continue
            if not daily:
                print(f"  {sym} [{basis}]: سریِ ما نداشت {meta.get('error') or meta} — رد")
                report_symbols.append({"symbol": sym, "basis": basis,
                                       "error": meta.get("error") or "empty"})
                _dump(partial=True)
                continue
            raw_series = meta.get("_raw_series") or {}
            ref0 = ra_rows(ins, 0)
            sched, era, holes = {}, {}, []
            for tf in tf_list:
                ref_native = ref0 if tf == 0 else ra_rows(ins, tf)
                ours = aggregate(daily, tf, basis)
                ours_raw = (raw_series if tf == 0 else aggregate(raw_series, tf, basis))
                note = volume_rule(ours, ref_native, tf)
                if note:
                    note.update({"symbol": sym, "basis": basis})
                    vol_rows.append(note)
                al = day_alignment(ref_native, ours, tf)
                align_rows.append({"symbol": sym, "basis": basis, **al})
                batch = []
                if a.space == "performance":
                    compare(sym, tf, basis, to_performance(ref_native), to_performance(ours),
                            batch, a.space, ref_native, ours_raw)
                else:
                    compare(sym, tf, basis, ref_native, ours, batch, a.space,
                            ref_native, ours_raw)
                # تفکیکِ شاهد‌محور درِ همان دسته (batch یکی (نماد×تایم‌فریم×مبنای) است،
                # و کلیدِ regroup هم همین چهارگانه) — پس نتیجه با پاسِ جهانی یکی است،
                # ولی فقط یک دسته درِ حافظه می‌ماند و ۳۶ نماد × دو مبنای سبز می‌شود.
                batch = regroup_by_day(batch)
                batch, mv = reclassify_precision(batch)
                precision_moved += mv
                for r in batch:
                    counts[r["mismatch_type"]] += 1
                    by_tf[f"{r['mismatch_type']}|tf{tf}|{basis}"] += 1
                    by_field[f"{r['mismatch_type']}|tf{tf}|{basis}|{r['field']}"] += 1
                    key = (sym, tf, basis, r["mismatch_type"])
                    per[key] += 1
                    if r["mismatch_type"] != "match" and per[key] <= a.cap:
                        rows.append(r)
                    elif r["mismatch_type"] != "match":
                        dropped += 1
                if tf == 0:
                    holes = al["only_reference_days"]
                    era = era_profile(batch)
            if 0 in tf_list:
                sched = factor_schedule(raw_series, daily, ref0, meta.get("events") or [])
            block = {"symbol": sym, "basis": basis, "candles": len(daily),
                     "meta": {k: v for k, v in meta.items()
                              if k not in ("events", "_raw_series")},
                     "adjust_events": meta.get("events"), "factor_schedule": sched,
                     # رویدادی که روزِ برچسبش کندل نیست (سطرِ توقفِ معامله درِ CSV ولی
                     # بی‌H/L و بی‌حجم) فقط برچسب است: نه آن روز و نه هیچ روزِ بعدی
                     # جابه‌جا می‌شود. تفکیکِ این از «رویدادی که اثرش یکِ نشست دیر/زود
                     # می‌شود» بدونِ این ستون ممکن نیست.
                     "events_not_in_candles": sorted(str(e.get("date")) for e in
                                                     (meta.get("events") or [])
                                                     if e.get("date") not in daily),
                     "era_profile": era,
                     # روزهایی که مرجع دارد و ما نه — «سوراخ» درِ سریِ خودِ ما. اگر
                     # رویدادِ تعدیلِ ما دقیقاً روزِ بعد از یکی از این‌ها بیفتد، آن
                     # رویداد از نبودِ سطر ساخته شده، نه از تغییرِ قیمتِ پایه.
                     "days_reference_has_and_we_dont": holes}
            report_symbols.append(block)
            print(f"  {sym} [{basis}] {len(daily)} کندل | رویدادِ ما={meta.get('n_events')} "
                  f"| گامِ k مرجع={sched.get('n_reference_steps')} "
                  f"| فقطِ مرجع={len(sched.get('days_only_they_move') or [])} "
                  f"| فقطِ ما={len(sched.get('days_only_we_move') or [])} "
                  f"| گامِ gap={sched.get('n_gap_steps')} "
                  f"| بی‌توضیح={len(sched.get('gap_days_explained_by_neither') or [])} "
                  f"| دورۀِ ثابت={era.get('n_long_runs')} روزِ ثابت={era.get('days_in_long_runs')} "
                  f"تک‌روزی={era.get('single_day_errors')} سوراخ‌هایِ ما={len(holes)} "
                  f"| counted={sum(counts.values())} kept={len(rows)}")
            if len(report_symbols) % 6 == 0:
                _dump(partial=True)
    body = _dump()
    kinds = Counter(counts)
    print(json.dumps({k: v for k, v in body.items()
                      if k not in ("table", "per_symbol", "volume_rules", "day_alignment")},
                     ensure_ascii=False, indent=1))
    print(f"[precision] {precision_moved} سطر با دقتِ انتشارِ خودِ مرجع توضیح داده شد → rounding")
    print(f"[cap] {dropped} سطر از جدولِ نمونه بیرون ماند (دربستِ {a.cap} در هر "
          f"نماد×تایم‌فریم×مبنای×نوع) — شمارِ by_mismatch_type کامل است")
    for k, n in kinds.most_common(8):
        ex = next((r for r in rows if r["mismatch_type"] == k), None)
        if ex is None:      # «match» درِ جدولِ نمونه نمی‌ماند، فقط شمرده می‌شود
            print(f"  {k:<20} {n:>6}")
            continue
        print(f"  {k:<20} {n:>6}  نمونه: {ex['symbol']} tf={ex['timeframe']} {ex['date']} "
              f"{ex['field']} ref={ex['reference']} bors={ex['bors']} | {ex['suspected_source'][:60]}")
    print("نوشته شد:", a.out)
    # تنظیمِ برنامه جابه‌جا نشده (هارنس PRICE_BASIS_PATH را به فایلِ موقت برد)، ولی
    # برایِ اطمینان مقدارِ اولیه را می‌نویسیم و بعد پوشهٔ موقت را می‌بَندیم.
    price_basis.set_basis(basis_before)
    print(f"[setting] مبنایِ برنامه پیش از اجرا و پس از آن: {basis_before} "
          f"(هارنس فقط رویِ {bors_config.PRICE_BASIS_PATH} نوشت)")
    import shutil
    shutil.rmtree(os.path.dirname(DB_COPY), ignore_errors=True)


DB_COPY = None
if __name__ == "__main__":
    main()
