#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/live_board_vs_source.py — آیا تابلویِ ما همان ردیف‌هایِ منبع را دارد؟

سؤالِ این نشست: سطرِ «صندوق‌های سهامی و مختلط» ما در مقایسه با تریدرزآرنا
−۵۹٪ است (۱۰:۵۷: ما ۲٬۹۹۸ در برابر ۷٬۲۵۰ م.ت) درحالی‌که سهام/حق‌تقدم،
درآمدثابت و اهرمی زیر ۰٫۲٪ می‌خوانند. دو فرض رقیب:
  (الف) منبع امروز آن صندوق‌ها را در `GetMarketWatch` برمی‌گرداند ولی سینکِ ما
      ردیفشان را درِ `market_watch` ندارد ⇒ نقصِ دریافت/نگهداشت (قابلِ رفع).
  (ب) منبع هم ردیفی ندارد (معامله نشده) ⇒ عددِ مرجع از جایِ دیگری می‌آید و
      باید تعریفِ دامنه بازبینی شود، نه دریافت.

این ابزار یکِ GETِ عمومی به همان آدرسی می‌زند که خودِ برنامه می‌زند
(`test_tsetmc.MW_URL`) و مجموعهٔ ردیف‌ها را با `market_watchِ` امروز مقایسه می‌کند.
فقط‌خواندنی: هیچ نوشتنی رویِ بانک، هیچ restartی، هیچ تغییرِ polling.

اجرا: PYTHONIOENCODING=utf-8 python tools/live_board_vs_source.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import mstat_engine as ME                                        # noqa: E402
import test_tsetmc as TT                                          # noqa: E402


def fetch_live():
    req = urllib.request.Request(TT.MW_URL, headers=TT.HEADERS)
    with urllib.request.urlopen(req, timeout=45) as r:
        d = json.loads(r.read().decode("utf-8"))
    if isinstance(d, list):
        return d
    # پاسخِ GetMarketWatch کلیدِ `marketwatch` دارد (نه `index`)؛ بی‌این،
    # منبعِ زنده صفر ردیف می‌شد و «هیچ ردیفی جا نیفتاده» نتیجه‌ای دروغ می‌داد.
    for k in ("marketwatch", "index", "data"):
        if isinstance(d.get(k), list):
            return d[k]
    return []


def main() -> int:
    db = os.path.join(ROOT, "market.db")
    c = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
    c.row_factory = sqlite3.Row
    today = c.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0]
    ours = {r[0]: r[1] for r in c.execute(
        "SELECT ins_code, q_tot_cap FROM market_watch WHERE d_even=?", (today,))}
    inst = {r["ins_code"]: r for r in c.execute(
        "SELECT ins_code, l_val18, l_val30, paper_type, sector_name FROM instruments")}
    print("today=%s  ردیفِ ما درِ market_watch: %d   universe: %d"
          % (today, len(ours), len(inst)))

    live = fetch_live()
    lv = {}
    for x in live:
        code = str(x.get("insCode") or "")
        if code:
            lv[code] = x
    tot_live = sum(float((v.get("qtc") or 0)) for v in lv.values())
    tot_ours = sum(float(v or 0) for v in ours.values())
    print("منبعِ زنده: %d ردیف، ارزش %.1f م.ت | ما: %d ردیف، ارزش %.1f م.ت"
          % (len(lv), tot_live / 1e10, len(ours), tot_ours / 1e10))

    missing = [k for k in lv if k not in ours]
    extra = [k for k in ours if k not in lv]
    print("درِ منبع ولی نه درِ ما: %d | درِ ما ولی نه درِ منبع: %d"
          % (len(missing), len(extra)))
    mv = sum(float(lv[k].get("qtc") or 0) for k in missing)
    print("ارزشِ ردیف‌هایِ جاافتاده: %.1f م.ت" % (mv / 1e10))

    # و تفکیکِ این جاافتاده‌ها به طبقه (همان classifyِ خودِ برنامه)
    agg = {}
    for k in missing:
        i = inst.get(k)
        name = (i["l_val30"] if i else "") or ""
        sym = (i["l_val18"] if i else "") or (lv[k].get("lVal18") or "")
        pt = i["paper_type"] if i else None
        sec = i["sector_name"] if i else ""
        cls, kind = ME.classify(pt, name, sym, sec or "")
        a = agg.setdefault((cls, kind), [0, 0.0])
        a[0] += 1
        a[1] += float(lv[k].get("qtc") or 0)
    for (cls, kind), (n, v) in sorted(agg.items(), key=lambda x: -x[1][1]):
        print("   جاافتاده %-8s/%-8s n=%3d  %10.1f م.ت" % (cls, kind, n, v / 1e10))

    # تفکیکِ خودِ منبع با همان classifyِ برنامه — این «تعریفِ دامنه» را از
    # «نقصِ دریافت» جدا می‌کند: اگر جمعِ صندوقِ سهامی درِ منبع هم ~۳ میلیارد باشد،
    # عددِ مرجع از جایِ دیگری می‌آید؛ اگر ~۷ میلیارد باشد، ردیف‌ها افتاده‌اند.
    src_agg = {}
    for k, x in lv.items():
        i = inst.get(k)
        name = (i["l_val30"] if i else "") or (x.get("lvc") or "")
        sym = (i["l_val18"] if i else "") or (x.get("lva") or "")
        pt = i["paper_type"] if i else x.get("cpaperType")
        cls, kind = ME.classify(pt, name, sym, (i["sector_name"] if i else "") or "")
        a = src_agg.setdefault((cls, kind), [0, 0.0])
        a[0] += 1
        a[1] += float(x.get("qtc") or 0)
    print("	فوری  تفکیکِ ردیف‌هایِ زندهٔ منبع (classifyِ خودِ برنامه):")
    for (cls, kind), (n, v) in sorted(src_agg.items(), key=lambda x: -x[1][1]):
        print("   منبع %-8s/%-8s n=%4d %10.1f م.ت" % (cls, kind, n, v / 1e10))

    # صندوق‌هایِ سهامیِ بی‌ردیفِ امروز درِ ما — خودِ منبع چ می‌گوید؟
    eq_missing = []
    for k, i in inst.items():
        if k in ours:
            continue
        cls, kind = ME.classify(i["paper_type"], i["l_val30"] or "",
                               i["l_val18"] or "", i["sector_name"] or "")
        if kind in ("equity", "mixed", "etf", "fof", "commod"):
            src = lv.get(k)
            if src and float(src.get("qtc") or 0) > 0:
                eq_missing.append((i["l_val18"], kind, float(src["qtc"]) / 1e10))
    eq_missing.sort(key=lambda x: -x[2])
    print("\nصندوقِ سهامی/مختلط که منبع برایش ارزشِ امروز دارد ولی ما ردیف نداریم: %d،"
          " جمع %.1f م.ت" % (len(eq_missing), sum(x[2] for x in eq_missing)))
    for e in eq_missing[:15]:
        print("   %-9s %-7s %9.1f م.ت" % e)
    c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
