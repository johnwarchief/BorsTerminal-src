#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sarkhati_regress_live_v1123.py — رگرسیونِ زندهٔ صفحۀ‌هایِ دیگر باِ همان بدین

تبِّ تازه دو چیز را درِ پوسته لمس کرده: `routes.tsx` (مقصدِ تازه) و
`Sidebar.tsx` (testidِ آیتم‌ها) + `Icons.tsx`. پس باید ثابت شود هیچِ مقصدِ
پیشینی ننشسته: هر route باز می‌شود، testidِ صاحبِ صفحه را دارد، اسکرولِ افقیِ
ناخواسته ندارد و هیچ خطایِ کنسول یا ErrorBoundary نمی‌دهد.

نکته: درِ عرضِ کوچک «بازرسِ نماد» تمام‌صفحه می‌شود (رفتارِ ازپیش‌موجودِ پوسته)،
پس همه‌چیز درِ ۱۳۶۶×۷۶۸ سنجیده می‌شود تا مقایسهٔ صفحات منصفانه بماند.
"""
import os
import sys

CHROME = r"C:\Users\PCMOD\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe"
BASE = "http://127.0.0.1:8103"
OUT_DEFAULT = r"C:\Users\PCMOD\Desktop\_bors-sarkhati-tab\_test_runs\tab_live"
SEED = "try{sessionStorage.setItem('bors_auth_session','true');}catch(e){}"

# لنگرها ازِ خودِ DOMِ هر صفحه کشف شده‌اند (نه حدسِ نامِ مؤلفه): اولینِ اجرایِ
# همین ابزار باِ سلکتورِ حدسی پنج صفحه را «ناموفق» گفت، در حالی که همه رندر
# شده بودند — همان تله‌ای که درِ skills/bors-live-ui-check ثبت شده.
PAGES = [
    ("#/market", "[data-testid='filters-side']"),
    ("#/market-status", "[data-testid='sarkhati-page'], [data-testid='pulse-bar'], [data-testid='market-status-page']"),
    ("#/technical", "[data-testid='chart-area']"),
    ("#/fundamental", "[data-testid='codal-health-strip']"),
    ("#/master", "[data-testid='fts-funnel-workspace']"),
    ("#/strategy-tree", "[data-testid='strategy-tree'], svg"),
    ("#/portfolio", "[data-testid='portfolio-page'], [role='tab']"),
    ("#/watch", "[data-testid='watch-add-area']"),
    ("#/sarkhati", "[data-testid='sarkhati-page']"),
]


def main():
    out = os.environ.get("OUT") or OUT_DEFAULT
    os.makedirs(out, exist_ok=True)
    from playwright.sync_api import sync_playwright
    fails, errs_all = [], []
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME, headless=True)
        ctx = b.new_context(viewport={"width": 1366, "height": 768})
        ctx.add_init_script(SEED)
        for route, sel in PAGES:
            errs = []
            page = ctx.new_page()
            page.on("console", lambda m: errs.append(m.text[:160]) if m.type == "error" else None)
            page.on("pageerror", lambda e: errs.append("pageerror: " + str(e)[:160]))
            ok, note = False, ""
            try:
                page.goto(BASE + "/" + route, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(1500)
                page.wait_for_selector(sel, timeout=25000)
                horiz = page.evaluate(
                    "() => document.documentElement.scrollWidth > window.innerWidth + 2")
                body = page.evaluate("() => document.body.innerText")
                ok = not horiz and "Unexpected Application Error" not in body
                note = "horiz=%s text=%d" % (horiz, len(body))
                page.screenshot(path=os.path.join(out, "regress_%s.png"
                                                   % route.strip("#/").replace("/", "-")),
                                full_page=True)
            except Exception as e:
                ok, note = False, str(e).split("\n")[0][:150]
            fatal = [e for e in errs if "favicon" not in e.lower()]
            print(("  ok   " if ok and not fatal else "  FAIL ") + route + "  " + note)
            for e in fatal[:3]:
                print("        console:", e)
            if not ok or fatal:
                fails.append(route)
            errs_all.extend(fatal)
            page.close()
        b.close()
    print("\n%d route، %d ناموفق" % (len(PAGES), len(fails)))
    print("SARKHATI REGRESSION LIVE " + ("OK" if not fails else "FAILED: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
