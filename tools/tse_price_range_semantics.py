#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/tse_price_range_semantics.py — «بیشترین/کمترین» درِ تابلو کدامِ منبع است؟

سنجشِ مرحلۀ ۵ نشان داد درِ مقایسهٔ هم‌زمان، ستونِ «بیشترین قیمت» ما با `pMaxِ`
خودِ تابلو برایِ اکثرِ ردیف‌ها نمی‌خواند (mid_rel≈۱ ⇒ عددِ ما صفر، منبع غيرصفر).
دو فرضِ رقیب:
  (الف) نگاشتِ ما غلط است (pMax را باید می‌گذاشت سرِ price_max).
  (ب) `pMax/pMin` سقف/کفِ **مجاز** قیمت است و `pmx/pmn` بیشترین/کمترینِ **معامله‌شده**.

کدِ دریافت (`test_tsetmc._mw_row`) ردیفِ `market_watch` را این‌طور می‌چیند:
    price_min ← pmn · price_max ← pmx · allowed_min ← pMin · allowed_max ← pMax
پس اگر (ب) درست باشد، ستونِ دیدنیِ ما ازِ همان `pmx/pmn` می‌آید و مقایسهٔ پیشین
**نگاشتِ خودش** را اشتباه انتخاب کرده بود. این ابزار هر دو را رویِ کلِ universe
می‌شمارد و چهار ضلعِ چهارگانه را می‌دهد؛ هیچ عددی حدس نمی‌شود:

  • چند ردیف ours == منبع(pMax)      • چند ردیف ours == منبع(pmx)
  • چند ردیف ours == 0 درحالی‌که pMax>0 · چند ردیف pmx == 0 درحالی‌که pMax>0
  • و پایانی‌ترینِ سنسور: آیا pMax ازِ pLast/پایانی بزرگ‌تر است و pmx هم؟

فقط‌خواندنی (یکِ GET + بانکِ mode=ro).

اجرا: PYTHONIOENCODING=utf-8 python tools/tse_price_range_semantics.py [--db market.db]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.request
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import test_tsetmc as TT                       # noqa: E402


def get(url, timeout=90):
    req = urllib.request.Request(url, headers=TT.HEADERS)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))


def n(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "market.db"))
    ap.add_argument("--print", type=int, default=12)
    a = ap.parse_args()

    mw = get(TT.MW_URL)
    rows = mw.get("marketwatch") if isinstance(mw, dict) else mw
    src = {str(r.get("insCode")): r for r in rows if r.get("insCode")}

    p = os.path.abspath(a.db).replace(chr(92), "/")
    c = sqlite3.connect("file:" + p + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    day = c.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0]
    ours = {r["ins_code"]: r for r in c.execute(
        "SELECT ins_code, h_even, p_closing, p_last, price_min, price_max,"
        "       allowed_min, allowed_max, price_first, q_tot_tran, total_shares,"
        "       market_cap FROM market_watch WHERE d_even=?", (day,))}
    print("نشست %s | ردیفِ ما %d | ردیفِ منبع %d" % (day, len(ours), len(src)))

    common = sorted(set(ours) & set(src))
    cnt = Counter()
    pairs = []
    for code in common:
        o, r = ours[code], src[code]
        pmax_s, pmin_s = n(r.get("pMax")), n(r.get("pMin"))
        pmx, pmn = n(r.get("pmx")), n(r.get("pmn"))
        o_max, o_min = n(o["price_max"]), n(o["price_min"])
        oa_max, oa_min = n(o["allowed_max"]), n(o["allowed_min"])
        cnt["rows"] += 1
        if o_max is not None and pmax_s is not None:
            if o_max == pmax_s:
                cnt["price_max == pMax"] += 1
            if o_max == pmx:
                cnt["price_max == pmx"] += 1
            if o_max == oa_max:
                cnt["price_max == allowed_max(=pMax ذخیرۀ ما)"] += 1
        if o_min is not None and pmin_s is not None:
            if o_min == pmin_s:
                cnt["price_min == pMin"] += 1
            if o_min == pmn:
                cnt["price_min == pmn"] += 1
        if not o_max and pmax_s:
            cnt["price_max ما صفر، pMax منبع>0"] += 1
        if not pmx and pmax_s:
            cnt["pmx منبع صفر، pMax>0"] += 1
        if not pmax_s and pmx:
            cnt["pMax منبع صفر، pmx>0"] += 1
        # کدام‌یک «بالایِ هیچ‌وقتِ قیمت» است؟ سقفِ مجاز باید ≥ آخرین و ≥ پایانی باشد
        last, clo = n(r.get("pdv")), n(r.get("pcl"))
        if last:
            if pmax_s and pmax_s >= last:
                cnt["pMax ≥ آخرین (سازگار با سقفِ مجاز)"] += 1
            if pmx and pmx >= last:
                cnt["pmx ≥ آخرین"] += 1
            if pmax_s and pmax_s > 3 * last:
                cnt["pMax > 3× آخرین (قطعاً معاملۀ روز نیست)"] += 1
            if pmx and pmx > 3 * last:
                cnt["pmx > 3× آخرین"] += 1
        if len(pairs) < 200 and o_max and pmx and pmax_s and o_max not in (pmx, pmax_s):
            pairs.append((code, (r.get("lva") or "").strip(), o_max, pmx, pmax_s,
                          n(o["price_min"]), pmn, pmin_s, last, n(o["h_even"]), n(r.get("hEven"))))

    print("\n" + "=" * 84)
    for k in sorted(cnt, key=lambda x: (-cnt[x], x)):
        print(f"{k:46} {cnt[k]:>7} / {cnt['rows']}")
    print("\nنمونۀ ردیف‌هایی که عددِ ما با هیچ‌دوِ pMax و pmx منبع نمی‌خواند:")
    print(f"{'نماد':12} {'ما_max':>10} {'pmx':>10} {'pMax':>10} {'ما_min':>10} "
          f"{'pmn':>10} {'pMin':>10} {'آخرین':>10} {'ساعت‌ما':>9} {'ساعت‌منبع':>9}")
    for _c, sym, o_max, pmx, pmax_s, o_min, pmn, pmin_s, last, oh, sh in pairs[:a.print]:
        print(f"{sym:12} {o_max:>10.0f} {pmx:>10.0f} {pmax_s:>10.0f} "
              f"{(o_min or 0):>10.0f} {(pmn or 0):>10.0f} {(pmin_s or 0):>10.0f} "
              f"{(last or 0):>10.0f} {str(oh):>9} {str(sh):>9}")
    c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
