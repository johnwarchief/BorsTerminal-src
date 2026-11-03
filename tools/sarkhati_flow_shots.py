# tools/sarkhati_flow_shots.py — اسکرین‌شاتِ زندهٔ قدم‌به‌قدمِ تبِّ «سرخطی»
#
# چرا اسکریپتِ جدا: `tools/jev_ui_check.mts` فقط کلیکِ «باِ متن» و اسکرول می‌دهد؛
# قدمِ ۲ این صفحه باِ تایپ درِ کادرِ جست‌وجویِ نماد باز می‌شود (ردیف‌هایِ نتیجه ازِ
# `SarkhatiSymbolCard`)، پس همین یک دورِ کاملِ تایپ+کلیک+عکس لازم است.
#
# هیچ‌چیز به سرویسِ بیرونی فرستاده نمی‌شود؛ فقط یک Chromiumِ محلی رویِ ۱۲۷٫۰٫۰٫۱
# می‌خواند (GET) و هیچ POST/SEND/PREFLIGHT ساخته نمی‌شود — درِ همین بیلد dry_run=true
# است و دروازۀ ارسال هم بسته است.
import io
import json
import os
import sys

from playwright.sync_api import sync_playwright

# پیش‌فرض‌ها ماشین‌محورند؛ با محیط عوض می‌شوند (پورتِ بک‌اندِ منبع، نه ۸۰۰۱ِ نصبی)
BASE = os.environ.get("BORS_UI_BASE", "http://127.0.0.1:8103/#/sarkhati")
CHROME = os.environ.get(
    "JEV_CHROME",
    r"C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe",
).replace("\\", "/")
OUT = "_audit"
AUTH = "sessionStorage.setItem('bors_auth_session','true');"

VIEWS = [(1366, 768), (1920, 1080)]


def box(page, sel):
    return page.evaluate(
        """(s) => { const e = document.querySelector(s);
        if (!e) return null; const r = e.getBoundingClientRect();
        return { w: Math.round(r.width), h: Math.round(r.height),
                 top: Math.round(r.top), bottom: Math.round(r.bottom) }; }""",
        sel,
    )


def overflow(page):
    return page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )


def shot(page, name):
    path = f"{OUT}/{name}.png"
    page.screenshot(path=path, full_page=False)
    return path


def run(view_w, view_h, tag):
    results = {"viewport": [view_w, view_h], "steps": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=CHROME)
        ctx = browser.new_context(viewport={"width": view_w, "height": view_h})
        ctx.add_init_script(AUTH)
        page = ctx.new_page()
        errors = []
        post_calls = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        def route_probe(request):
            if request.method != "GET":
                post_calls.append(f"{request.method} {request.url}")

        page.on("request", route_probe)
        page.goto(BASE, wait_until="domcontentloaded")
        page.wait_for_selector("[data-testid='sarkhati-page']", timeout=30000)
        page.wait_for_function(
            "() => { const e=document.querySelector('[data-testid=\"sarkhati-status-line\"]');"
            "return e && e.textContent.includes('mock'); }",
            timeout=25000,
        )

        def snap(label):
            return {
                "label": label,
                "step": page.get_attribute("[data-testid='sarkhati-page']", "data-step"),
                "suggested": page.get_attribute(
                    "[data-testid='sarkhati-page']", "data-suggested-step"
                ),
                "headline": (page.inner_text("[data-testid='sarkhati-headline']")
                             .replace("\n", " | ").strip()),
                "page_box": box(page, "[data-testid='sarkhati-page']"),
                "overflow_x": overflow(page),
            }

        r1 = snap("landed")
        r1["screenshot"] = shot(page, f"sarkhati-{tag}-1-landed-{view_w}")
        results["steps"].append(r1)

        # قدمِ ۲: نماد را تایپ و انتخاب می‌کند (همان فولاد، نه هر ردیفِ نخستِ
        # فهرست — «آتيه06» هم درِ جست‌وجوی «فولاد» می‌آید)
        chosen = None
        if page.is_visible("[data-testid='sarkhati-symbol-search']"):
            page.fill("[data-testid='sarkhati-symbol-search']", "فولاد")
            page.wait_for_selector("[data-testid*='sarkhati-symbol-pick']", timeout=12000)
            # «فولاد» دقیقاً همیشه درِ دوازده ردیفِ نخست نیست (فهرست باِ ترتيبِ
            # خودش می‌آید و «آتيه06» هم باِ همین جست‌وجو می‌آید). برایِ اثباتِ
            # جریان، همان ردیفِ اول کافی است؛ نمادِ برگزیده درِ گزارش ثبت می‌شود.
            exact = page.locator("[data-testid='sarkhati-symbol-pick-فولاد']")
            target = exact.first if exact.count() else \
                page.locator("[data-testid*='sarkhati-symbol-pick']").first
            target.click()
            page.wait_for_function(
                "() => document.querySelector('[data-testid=\"sarkhati-page\"]')"
                ".getAttribute('data-symbol').length > 0", timeout=12000)
            chosen = page.get_attribute("[data-testid='sarkhati-page']", "data-symbol")
        r2 = snap("symbol-chosen")
        r2["symbol"] = chosen
        r2["next_action"] = (page.inner_text("[data-testid='sarkhati-next-action']")
                             .strip() if page.is_visible("[data-testid='sarkhati-next-action']")
                             else None)
        r2["screenshot"] = shot(page, f"sarkhati-{tag}-2-guide-{view_w}")
        results["steps"].append(r2)

        # قدمِ ۳: سفارش
        if r2["next_action"]:
            page.click("[data-testid='sarkhati-next-action']")
        page.wait_for_selector("[data-testid='sarkhati-order-section']", timeout=15000)
        page.wait_for_selector("[data-testid='watch-order-price']", timeout=15000)
        r3 = snap("order")
        r3["draft"] = page.inner_text("[data-testid='sarkhati-draft-summary']").replace("\n", " ")
        r3["gate_reason"] = (page.inner_text("[data-testid='watch-order-reason']")
                             .replace("\n", " ")[:180])
        r3["submit_enabled"] = page.is_enabled("[data-testid='exec-submit']")
        r3["screenshot"] = shot(page, f"sarkhati-{tag}-3-order-{view_w}")
        results["steps"].append(r3)

        # جزئیاتِ فنی بازشده
        page.click("[data-testid='sarkhati-tech-details'] summary")
        page.wait_for_selector("[data-testid='sarkhati-status-strip']", state="visible", timeout=8000)
        r4 = snap("details-open")
        r4["strip_session"] = page.get_attribute(
            "[data-testid='sarkhati-status-strip']", "data-session")
        r4["screenshot"] = shot(page, f"sarkhati-{tag}-4-details-{view_w}")
        results["steps"].append(r4)

        results["console_errors"] = errors[:10]
        results["non_get_calls"] = post_calls[:10]
        browser.close()
    return results


out = {}
tag = sys.argv[1] if len(sys.argv) > 1 else "after"
for w, h in VIEWS:
    out[f"{w}x{h}"] = run(w, h, tag)
    print(f"[done] {w}x{h}")
io.open(f"{OUT}/sarkhati-{tag}-flow.json", "w", encoding="utf-8").write(
    json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out, ensure_ascii=False, indent=1)[:200])
