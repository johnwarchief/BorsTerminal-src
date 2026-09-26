#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#101/#102 — دستِ Playwright روی کارت زنده: درصد رشد EPS و میله‌های سود ناخالص.

vitest کامپوننت را با دادهٔ ساختگی می‌سنجد؛ این اسکریپت همان کارت را روی
buildِ واقعیِ سرویس‌شده با دادهٔ کدالِ bank بررسی می‌کند:
  · «رشد سال‌به‌سال» در کارت شاخص ۲ با ارقامِ فارسی و علامت + می‌آید
  · روند فصلی، میلهٔ سود ناخالص دارد (نه فقط درآمد)
  · هیچ pageerror ای ثبت نمی‌شود

اجرا: python tools/fundamental_card_live.py [--base http://127.0.0.1:8011]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright  # noqa: E402

SYMBOL = "شپنا"
fails: list[str] = []


def ck(name: str, cond: bool, got=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else f"  ← {got!r}"))
    if not cond:
        fails.append(name)


def api_json(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=90) as r:
        return json.loads(r.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8011")
    ap.add_argument("--symbol", default=SYMBOL)
    a = ap.parse_args()
    sym = a.symbol

    with sync_playwright() as p:
        b = p.chromium.launch(args=["--disable-gpu"])
        ctx = b.new_context(viewport={"width": 1600, "height": 1000})
        ctx.add_init_script("try{sessionStorage.setItem('bors_auth_session','true')}catch(e){}")
        pg = ctx.new_page()
        errs: list[str] = []
        pg.on("pageerror", lambda e: errs.append(str(e)))

        # مسیرِ نماد در روتر است: /fundamental/<symbol> — با جستجو زدنِ input
        # صفحه، نمادِ مورد نظر ممکن است اصلاً در فیلتر فعلی نباشد.
        pg.goto(a.base + "/#/fundamental/" + urllib.parse.quote(sym), wait_until="networkidle")
        pg.wait_for_timeout(3000)

        card_txt = pg.locator("body").inner_text()
        ck(f"کارتِ «{sym}» باز شد", sym in card_txt, card_txt[:120])

        # انتظارات از خودِ سرور گرفته می‌شوند، نه از شکلِ یک نمادِ خاص: صندوق
        # هیچ EPS و هیچ سودِ ناخالصی ندارد، و آن‌جا «درصدِ ساختگی» و «میلهٔ صفر»
        # هر دو خطایند — باید متنِ صریحِ «ندارد» بنشیند.
        card = api_json(a.base, f"/api/fundamental/{urllib.parse.quote(sym)}")
        i2 = (card.get("indicators") or {}).get("2") or {}
        yoy_expect = [p for p in (i2.get("eps_yoy_pct") or []) if isinstance(p, (int, float))]
        quarters = api_json(a.base, f"/api/fundamental/{urllib.parse.quote(sym)}/quarters?limit=8"
                                    ).get("quarters") or []
        gross_expect = [q for q in quarters if isinstance(q.get("gross_profit"), (int, float))]

        growth = pg.get_by_test_id("fts-card-eps-growth")
        ck("ردیفِ «رشد سال‌به‌سال» در کارت هست", growth.count() >= 1)
        g = growth.first.inner_text() if growth.count() else ""
        percents = re.findall(r"[+\u2212−][۰-۹]+(?:\.[۰-۹]+)?٪", g)
        nodata = pg.get_by_test_id("fts-card-eps-growth-nodata")
        if yoy_expect:
            ck("هر درصدِ رشدِ سرور روی کارت می‌آید", len(percents) == len(yoy_expect),
               f"{len(percents)} روی کارت / {len(yoy_expect)} در سرور ← {g}")
            ck("ارقامِ فارسی و ٪ رعایت شده", bool(re.search(r"[۰-۹]", g)) and "٪" in g, g)
            ck("«بدون داده» با وجودِ درصد نمایش داده نمی‌شود", nodata.count() == 0, g)
        else:
            ck("بدونِ سریِ EPS، درصدی جعل نمی‌شود و علتِ صریح می‌آید",
               nodata.count() >= 1 and not percents, g)

        chart = pg.get_by_test_id("quarterly-trend-chart")
        ck("نمودار روند فصلی رسم شده", chart.count() >= 1)
        bars = pg.locator("[data-testid='quarterly-trend-chart'] rect")
        n = bars.count()
        fills = {bars.nth(i).get_attribute("fill") or "" for i in range(min(n, 60))}
        gross_bars = sum(1 for i in range(min(n, 60))
                         if any(c in (bars.nth(i).get_attribute("fill") or "")
                                for c in ("accent-green", "accent-red")))
        # تعدادِ فصل‌های خامِ سرور با میله‌ها برابری نمی‌کند: سریِ YTD به فصلِ
        # گسسته تبدیل می‌شود و نخستین سال بی‌مبنایِ تفریق می‌ماند. پس انتظارِ
        # درون-صفحه‌ای: هر فصلی که tooltip اش «سود ناخالص» has، میله هم دارد.
        tlocs = pg.locator("[data-testid='quarterly-trend-chart'] title")
        titles = [tlocs.nth(i).text_content() or "" for i in range(tlocs.count())]
        titled_gross = [t for t in titles if "گزارش نشده" not in t]
        na = pg.get_by_test_id("qtrend-gross-na")
        if gross_expect:
            ck("هر فصلِ دارایِ سود، میلهٔ سودِ ناخالص دارد (و بی‌سود ندارد)",
               gross_bars == len(titled_gross) and gross_bars >= 1,
               f"{gross_bars} میله / {len(titled_gross)} فصلِ سوددار از {len(titles)} فصل")
            ck("با سودِ موجود، بنرِ N/A نمی‌آید", na.count() == 0)
        else:
            ck("بدونِ سودِ ناخالص، میله‌ای رسم نمی‌شود", gross_bars == 0, str(sorted(fills)[:4]))
            ck("بنرِ صریحِ N/A به جایِ میلهٔ صفر", na.count() >= 1)

        ck("بدون خطای رانر", not errs, str(errs[:2]))
        b.close()

    print("\n" + (f"{len(fails)} شکست: " + " | ".join(fails) if fails else "همه سبز"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
