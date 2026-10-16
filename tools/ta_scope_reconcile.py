#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/ta_scope_reconcile.py — تطبیقِ دامنهٔ «نبض بازار» با منبع، در یکِ لحظه.

چرا: در مقایسهٔ هم‌زمان ۱۰:۵۷، تنها سطرِ «صندوق‌های سهامی و مختلط» فراتر از تلورانس
بود (ما ۲٬۹۹۸ در برابر مرجع ۷٬۲۵۰ م.ت) درحالی‌که سهام/حق‌تقدم، درآمدثابت و اهرمی
زیر ۰٫۲٪ بودند. `tools/live_board_vs_source.py` ثابت کرد ردیفی از تابلو جا نیفتاده
(منبعِ زنده ۳٬۰۱۶ ردیف، ما ۳٬۰۲۴ — هیچِ جاافتاده) ⇒ اختلاف از **تعریفِ دامنه** است،
نه از دریافت. این ابزار همان دو طرف را در یکِ ثانیه می‌خواند و باقی‌مانده را
تفکیکِ کلاس می‌کند تا معلوم شود کدام طبقه درِ دیدگاهِ مرجع داخلِ `sf` نشسته است.

فقط‌خواندنی: دو GET (مرجع + تابلو) و یکِ کوئری `mode=ro`.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import mstat_engine as ME                                        # noqa: E402
import test_tsetmc as TT                                          # noqa: E402

BT = 1e10          # ریال → میلیارد تومان
TA_URL = "https://tradersarena.ir/data/market0"
TA_HDR = {"User-Agent": "Mozilla/5.0", "Referer": "https://tradersarena.ir/market"}


def get(url, headers=None, timeout=45):
    req = urllib.request.Request(url, headers=headers or {})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))


def main() -> int:
    t0 = time.time()
    ta = get(TA_URL, TA_HDR)
    if isinstance(ta, list):
        ta = ta[0] if ta else {}
    mw = get(TT.MW_URL, TT.HEADERS)
    rows = mw if isinstance(mw, list) else next(
        (mw[k] for k in ("marketwatch", "index", "data") if isinstance(mw.get(k), list)), [])
    print("دو خواندن در %.2f ثانیه | مرجع %s %s | ردیفِ تابلو %d"
          % (time.time() - t0, ta.get("j"), ta.get("d"), len(rows)))

    def val(x):
        return float(x.get("qtc") or 0.0) / BT

    def flow(x):
        # جریانِ مرجع = خریدِ حقیقی + خریدِ حقوقی − فروش‌ها؛ اینجا فقط ارزشِ
        # معامله را می‌سنجیم (جریان درِ ابزارِ دیگری سنجیده می‌شود).
        return None

    db = os.path.join(ROOT, "market.db")
    c = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
    c.row_factory = sqlite3.Row
    inst = {r["ins_code"]: r for r in c.execute(
        "SELECT ins_code, l_val18, l_val30, paper_type, sector_name FROM instruments")}
    c.close()

    agg = {}
    for x in rows:
        code = str(x.get("insCode") or "")
        i = inst.get(code)
        name = (i["l_val30"] if i else "") or (x.get("lvc") or "")
        sym = (i["l_val18"] if i else "") or (x.get("lva") or "")
        pt = i["paper_type"] if i else x.get("cpaperType")
        sec = (i["sector_name"] if i else "") or ""
        cls, kind = ME.classify(pt, name, sym, sec)
        a = agg.setdefault(kind, [0, 0.0, cls])
        a[0] += 1
        a[1] += val(x)

    def ta_v(k, idx=1):
        arr = ta.get(k) or []
        return float(arr[idx] or 0.0) / BT if len(arr) > idx else None

    groups = {
        "stock+right": ["stock", "right"],
        "equity-family": ["equity", "mixed", "etf", "fof"],
        "commodity-family": ["commod", "gold", "silver"],
        "fixed": ["fixed"],
        "lev": ["lev"],
        "other(bonds/options)": ["other"],
    }
    print("\nمنبعِ TSETMC با classifyِ خودِ برنامه:")
    for g, kinds in groups.items():
        n = sum(agg[k][0] for k in kinds if k in agg)
        v = sum(agg[k][1] for k in kinds if k in agg)
        print("   %-22s n=%4d %10.1f م.ت" % (g, n, v))
    tot = sum(a[1] for a in agg.values())
    print("   %-22s      %10.1f م.ت" % ("جمعِ تابلو", tot))

    print("\nمرجع (تریدرزآرنا، میلیارد تومان):")
    for k in ("m", "st", "sf", "nsf", "lf", "cf", "scf", "afl", "um"):
        v = ta_v(k)
        if v is not None:
            print("   %-4s %12.1f" % (k, v))

    st, sf, nsf, lf = ta_v("st"), ta_v("sf"), ta_v("nsf"), ta_v("lf")
    eq = sum(agg[k][1] for k in groups["equity-family"] if k in agg)
    com = sum(agg[k][1] for k in groups["commodity-family"] if k in agg)
    fix = sum(agg[k][1] for k in groups["fixed"] if k in agg)
    lev = sum(agg[k][1] for k in groups["lev"] if k in agg)
    stk = sum(agg[k][1] for k in groups["stock+right"] if k in agg)
    oth = sum(agg[k][1] for k in groups["other(bonds/options)"] if k in agg)
    print("\nباقی‌مانده (مرجع − منبع، همان کلاس):")
    print("   st−(stock+right) = %8.1f   | nsf−fixed = %8.1f   | lf−lev = %8.1f"
          % ((st or 0) - stk, (nsf or 0) - fix, (lf or 0) - lev))
    print("   sf−equity-family = %8.1f  ← شکافِ اصلی" % ((sf or 0) - eq))
    print("   sf−(equity+commodity) = %6.1f | sf−(equity+commodity+other) = %6.1f"
          % ((sf or 0) - eq - com, (sf or 0) - eq - com - oth))
    print("   m−(st+sf+nsf) [identityِ مرجع] = %.1f"
          % ((ta_v("m") or 0) - (st or 0) - (sf or 0) - (nsf or 0)))
    print("   مجموعِ همهٔ سطرهایِ مرجع (m+lf+cf+scf) = %.1f  در برابرِ تابلو %.1f"
          % ((ta_v("m") or 0) + (lf or 0) + (ta_v("cf") or 0) + (ta_v("scf") or 0), tot))
    return 0


if __name__ == "__main__":
    sys.exit(main())
