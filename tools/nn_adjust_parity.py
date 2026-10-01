#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#107 — حالتِ تعدیلِ ما دقیقاً کدام حالتِ نهایات نگر است؟

واحدِ قیمتِ آن‌ها با ما یکی نیست (pricescale=100 و مقیاسِ خودش)، پس مقایسهٔ
عددِ قیمت بی‌معناست؛ چیزی که مقایسه می‌شود **شکلِ فاکتور** است:
    آن‌ها:  f_m(t) = close_m(t) / close_0(t)
    ما:     f(t)   = پایانی × factor / پایانی = factor(t)
هر دو در آخرین روز ۱‌اند، پس نسبتِشان در کلِ تاریخ باید تخت بماند اگر همان
حالت باشد. خروجی: درصدِ انحرافِ میانه، بدترین انحراف، و تاریخِ بیشترین پرش.

اجرا: python tools/nn_adjust_parity.py [--ours http://127.0.0.1:8011]
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import statistics
import sys
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NN = "https://www.nahayatnegar.com/tv/chart/history"
HDRS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.nahayatnegar.com/tv/"}
MODE = {0: "بدون تعدیل", 1: "افزایش سرمایه", 2: "سود نقدی",
        3: "افزایش+سود با آورده", 4: "تعدیل عملکردی"}
SYMS = (("فولاد", "IRO1FOLD0001"), ("خودرو", "IRO1IKCO0001"))


def get(url: str, timeout: int = 120) -> dict:
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _norm(sym: str) -> str:
    """نرمالِ نامِ نماد: بی‌فاصله، بی‌نیم‌فاصله، و بی‌پسوندِ «سری»."""
    s = (sym or "").replace("\u200c", "").replace(" ", "").strip()
    while s and s[-1].isdigit():
        s = s[:-1]
    return s


def nn_resolve(query: str) -> str:
    """نامِ فارسیِ نماد → isinCodeای که آن‌ها درِ `symbol=` می‌خواهند.

    بی‌این هر سنجشی جزِ دو نمادِ hard-code شده ممکن نبود (آن‌ها isin را درِ
    آدرس می‌خواهند، نه ins_code عددیِ tsetmc؛ با عددِ خودی «no_data» می‌دهند).
    پارامترِ درستِ این endpoint `query=` است — با `search=` یا `text=` فهرست
    خالی برمی‌گردد.

    دو دام که اولِ کار نمادِ غلط را داد:
      ۱) نام‌هایِ آن‌ها پسوندِ سری دارد («فولاد1») و نتایج fuzzy مرتب‌شده‌اند،
         پس «اولینِ فهرست» برایِ فولاد «فولاد تربت1» بود و سنجش بی‌صدا رویِ
         نمادِ دیگری انجام می‌شد؛
      ۲) دیکته‌ها فرق می‌کند: «وغدير»ِ ما با ي عربی است و آن‌ها «وغدیر» با ی
         فارسی دارند، پس جست‌وجو صفرِ نتیجه می‌داد.
    حالا فقط تطبیقِ دقیقِ نامِ نرمال‌شده پذیرفته می‌شود و وگرنه "" برمی‌گردد —
    نبودنش بهترِ سنجشِ رویِ نمادِ اشتباه است.
    """
    tries = [query]
    alt = query.replace("ي", "ی").replace("ك", "ک")
    if alt != query:
        tries.append(alt)
    want = _norm(query)
    for term in tries:
        try:
            items = get("https://www.nahayatnegar.com/tv/chart/search?query="
                        + urllib.parse.quote(term), timeout=60).get("tvSymbols") or []
        except Exception:
            items = []
        for it in items:
            if _norm(it.get("symbol") or it.get("ticker") or "") == want:
                return it.get("id") or it.get("ticker") or ""
    return ""


def nn_series(sym_id: str, adj: int, frm: int, to: int) -> dict:
    j = get(f"{NN}?symbol={sym_id}{adj}&resolution=1D&from={frm}&to={to}"
            f"&type=stock&adjustmentType={adj}&countback=4000")
    return {dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"): float(c)
            for t, c in zip(j.get("t") or [], j.get("c") or [])}


def our_factors(base: str, sym: str) -> dict:
    j = get(f"{base}/api/chart/{urllib.parse.quote(sym)}", timeout=240)
    return ({f["time"]: float(f["factor"]) for f in (j.get("factors") or [])},
            len(j.get("adjustEvents") or []), j.get("adjustSource"), j.get("count"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ours", default="http://127.0.0.1:8011")
    ap.add_argument("--since", default="2015-01-01")
    ap.add_argument("--symbols", default="",
                    help="comma list of Persian tickers; each isin is resolved live")
    ap.add_argument("--modes", default="3,4",
                    help="adjustmentType numbers to compare against (default 3,4)")
    a = ap.parse_args()
    want_modes = [int(m) for m in a.modes.split(",") if m.strip()]
    if a.symbols:
        pairs = [(s.strip(), "") for s in a.symbols.split(",") if s.strip()]
    else:
        pairs = list(SYMS)
    frm = int(dt.datetime(2012, 1, 1, tzinfo=dt.timezone.utc).timestamp())
    to = int(dt.datetime.now(dt.timezone.utc).timestamp())
    for sym, sym_id in pairs:
        sym_id = sym_id or nn_resolve(sym)
        if not sym_id:
            print("\n=== %s: isinِ آن‌ها پیدا نشد — سنجش انجام شدنی نیست" % sym)
            continue
        fac, n_ev, src, cnt = our_factors(a.ours, sym)
        raw0 = nn_series(sym_id, 0, frm, to)
        dates = sorted(d for d in fac if d >= a.since and d in raw0)
        print(f"\n=== {sym} ({sym_id})  ردیفِ ما={cnt}  رویدادِ تعدیل={n_ev}  ({src})"
              f"  ردیفِ قابلِ مقایسه={len(dates)}  ردیفِ آن‌ها={len(raw0)}")
        if not dates:
            print("  هیچ ردیفِ مشترکی نبود")
            continue
        # فاکتورِ خودِ ما نرمال می‌شود به آخرین روزِ مشترک (همان قراردادِ آن‌ها)
        last = dates[-1]
        ours = {d: fac[d] / fac[last] for d in dates}
        best = None
        for m in want_modes:
            s = nn_series(sym_id, m, frm, to)
            dd = [d for d in dates if d in s and raw0[d]]
            if len(dd) < 50:
                print(f"  mode {m} ({MODE[m]}): ردیفِ کافی نیست ({len(dd)})")
                continue
            theirs = {d: s[d] / raw0[d] for d in dd}
            tl = theirs[dd[-1]]
            ratios = [ours[d] / (theirs[d] / tl) for d in dd]
            med = statistics.median(ratios)
            dev = [abs(r / med - 1) for r in ratios]
            within = sum(1 for x in dev if x <= 0.01)
            worst_i = max(range(len(ratios)), key=lambda i: dev[i])
            print(f"  mode {m} ({MODE[m]:<22}): میانهٔ نسبت={med:.5f}  "
                  f"درصدِ ردیفِ هم‌خوان(±۱٪)={100 * within / len(dev):5.1f}٪  "
                  f"بدترین={dev[worst_i] * 100:5.1f}٪ در {dd[worst_i]}")
            if best is None or within / len(dev) > best[1]:
                best = (m, within / len(dev), med)
        if best:
            print(f"  → فاکتورِ ما شبیه‌ترین حالت به mode {best[0]} «{MODE[best[0]]}» "
                  f"({100 * best[1]:.1f}٪ ردیف‌ها، نسبتِ میانهٔ {best[2]:.4f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
