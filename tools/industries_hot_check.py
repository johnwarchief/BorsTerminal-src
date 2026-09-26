#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#104 — دستِ Playwright روی پنل «صنایع داغ»: رتبه‌بندی با سرور + چیدمانِ RTL.

vitest (src/__tests__/market-industries.spec.tsx) سورت را با دادهٔ ماک می‌سنجد؛
این اسکریپت همان پنل را روی buildِ واقعی و بانکِ زنده می‌سنجد:
  · سه ردیفِ نمایشی عیناً همان سه صنعتِ برترِ سرورند (flow و درصد)
  · سنجهٔ غایب «بدون داده» است، نه صفرِ سبز
  · جهتِ بصری: فلش راستِ عدد و واحد «ب.ت» چپِ عدد است (جریانِ RTL)

اجرا: python tools/industries_hot_check.py [--base http://127.0.0.1:8011]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright  # noqa: E402

FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
fails: list[str] = []


def ck(name: str, cond: bool, got=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else f"  ← {got!r}"))
    if not cond:
        fails.append(name)


def api_json(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=60) as r:
        return json.loads(r.read().decode())


def fa_int(x: float) -> str:
    """fmtIntِ app: گردِ صحیح + جداکنندهٔ هزارگان٬ + رقمِ فارسی."""
    return f"{int(round(x)):,}".replace(",", "٬").translate(FA)


def rendered_rows(pg):
    """[industry, flow_text, pct_text, arrow_box, num_box, unit_box] برای هر ردیفِ پنل."""
    out = []
    for li in pg.locator("[data-testid='sector-inflow'] li").all():
        industry = li.locator("span").first.inner_text().replace("★ پیشرو", "").strip()
        flow_el = li.locator(f"[data-testid='industry-flow-{industry}']")
        pct_el = li.locator(f"[data-testid='industry-pct-{industry}']")
        out.append({
            "industry": industry,
            "flow": flow_el.first.inner_text().strip() if flow_el.count() else "",
            "pct": pct_el.first.inner_text().strip() if pct_el.count() else "",
            "boxes": {
                i: li.locator("span").nth(i).bounding_box()
                for i in range(0, 8)
                if li.locator("span").nth(i).bounding_box()
            },
            "spans": [li.locator("span").nth(i).inner_text().strip()
                      for i in range(li.locator("span").count())],
        })
    return out


def order_check(rows_data) -> list[str]:
    """فلش باید راستِ عدد باشد و واحد «ب.ت» چپِ عدد (در RTL همین است)."""
    bad = []
    for r in rows_data:
        if not r["flow"].startswith(("▲", "▼")):
            continue  # «بدون داده» فلش ندارد
        arrow = num = unit = None
        for i, txt in enumerate(r["spans"]):
            box = r["boxes"].get(i)
            if box is None:
                continue
            t = txt.strip()
            if t in ("▲", "▼") and arrow is None:
                arrow = box
            elif t == "ب.ت" and unit is None:
                unit = box
            elif re.fullmatch(r"[۰-۹٬]+", t) and num is None:
                num = box
        if not (arrow and num and unit):
            bad.append(f"{r['industry']}: اجزایِ ردیف پیدا نشد ({r['spans']})")
            continue
        if not (arrow["x"] > num["x"] > unit["x"]):
            bad.append(f"{r['industry']}: ترتیبِ بصریِ اشتباه "
                       f"(arrow={arrow['x']:.0f} num={num['x']:.0f} unit={unit['x']:.0f})")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8011")
    a = ap.parse_args()

    feed = api_json(a.base, "/api/mstat/industries")
    rows = feed.get("rows") or []
    by_flow = [r for r in rows if isinstance(r.get("flow_b_toman"), (int, float))]
    by_flow.sort(key=lambda r: -r["flow_b_toman"])
    by_pct = [r for r in rows if isinstance(r.get("avg_pct"), (int, float))]
    by_pct.sort(key=lambda r: -r["avg_pct"])
    null_flow = [r["industry"] for r in rows if r.get("flow_b_toman") is None]

    with sync_playwright() as p:
        b = p.chromium.launch(args=["--disable-gpu"])
        ctx = b.new_context(viewport={"width": 1600, "height": 1000})
        ctx.add_init_script("try{sessionStorage.setItem('bors_auth_session','true')}catch(e){}")
        pg = ctx.new_page()
        errs: list[str] = []
        pg.on("pageerror", lambda e: errs.append(str(e)))

        pg.goto(a.base + "/#/market", wait_until="networkidle")
        pg.wait_for_timeout(2000)
        pg.get_by_test_id("watch-tab-industries").click()
        pg.wait_for_selector("[data-testid='sector-inflow'] ul", timeout=15000)
        pg.wait_for_timeout(800)

        got = rendered_rows(pg)
        ck("سه ردیفِ صنعت نمایش داده شده", len(got) == 3, [r["industry"] for r in got])
        ck("رتبهٔ «ورود پول حقیقی» عیناً همان سه صنعتِ سرور است",
           [r["industry"] for r in got] == [r["industry"] for r in by_flow[:3]],
           f"{[r['industry'] for r in got]} ≠ {[r['industry'] for r in by_flow[:3]]}")
        for g, s in zip(got, by_flow[:3]):
            want = fa_int(abs(s["flow_b_toman"]))
            ck(f"عددِ جریانِ «{g['industry']}» با سرور می‌خواند",
               want in g["flow"], f"{g['flow']!r} (منتظره {want})")
            sign_ok = (g["flow"].startswith("▲") and s["flow_b_toman"] >= 0) or \
                      (g["flow"].startswith("▼") and s["flow_b_toman"] < 0)
            ck(f"علامت/رنگِ «{g['industry']}» با نشانهٔ جریان یکی است", sign_ok, g["flow"])

        bad = order_check(got)
        ck("چیدمانِ RTL: فلش راستِ عدد، واحدِ «ب.ت» چپِ عدد", not bad, bad[:2])

        # نمای دوم: «بیشترین درصد»
        pg.get_by_role("button", name="بیشترین درصد").click()
        pg.wait_for_timeout(900)
        got2 = rendered_rows(pg)
        ck("رتبهٔ «بیشترین درصد» عیناً همان سه صنعتِ سرور است",
           [r["industry"] for r in got2] == [r["industry"] for r in by_pct[:3]],
           f"{[r['industry'] for r in got2]} ≠ {[r['industry'] for r in by_pct[:3]]}")
        for g, s in zip(got2, by_pct[:3]):
            digits = re.findall(r"[۰-۹]+(?:\.[۰-۹]+)?", g["pct"])
            want = (f"{abs(s['avg_pct']):.1f}").translate(FA)
            ck(f"درصدِ «{g['industry']}» با میانگینِ سرور می‌خواند",
               bool(digits) and digits[0] == want, f"{g['pct']!r} (منتظره {want})")

        # «بی‌داده» هرگز صفر نمی‌شود: اگر صنعتی جریانِ null دارد، در رتبه نیست
        shown = {r["industry"] for r in got} | {r["industry"] for r in got2}
        ck("صنعتِ بی‌جریان در فهرستِ رتبه‌شده نمی‌نشیند",
           not (set(null_flow) & shown), f"null-flow={null_flow[:5]}")
        if not null_flow:
            print("  ..   بانکِ فعلی هیچ صنعتِ بی‌جریانی ندارد؛ چکِ بالا بی‌مصرف ماند")

        ck("بدون خطای رانر", not errs, str(errs[:2]))
        b.close()

    print("\n" + (f"{len(fails)} شکست: " + " | ".join(fails) if fails else "همه سبز"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
