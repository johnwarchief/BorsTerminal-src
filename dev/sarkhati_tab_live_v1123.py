#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sarkhati_tab_live_v1123.py — شاهدِ مرورگرِ زندهٔ تبِّ «سرخطی»

چه چیزی سنجیده می‌شود (همه رویِ بدینِ ساخته‌شدۀ همین branch و بک‌اندِ همین
worktree درِ پورت ۸۱۰۳؛ نصبیِ ۸۰۰۱ دست‌نخورده):

  ۱) مقصد باز می‌شود، ازِ سایدبار و ازِ لینکِ مستقیم و بعدِ reload.
  ۲) هیچ کلیکِ معمولی (تب‌ها، بازشوها) هیچ POST/DELETE‌ای نمی‌سازد —
     «بازکردنِ پنل ≠ ارسالِ سفارش».
  ۳) فرم باِ جابه‌جایی می‌ماند و باِ عوض‌شدنِ نماد پاک می‌شود.
  ۴) پیش‌فرود رأیِ خودِ سرویس را درِ خطِ پاسخ می‌آورد (نه متنِ ثابت).
  ۵) درِ هر چهار viewport: RTL، اسکرولِ افقیِ نبود، دیده‌شدنِ testidهایِ کلیدی،
     و نبودِ خطایِ کنسول.
  ۶) «لغو» وقتی capabilityاش نیست ساخته نمی‌شود، و علتش نوشته می‌شود.

نکتهٔ ابزار: درِ حالتِ بدونِ نشستِ کارگزاری (mock/dry_run) هیچ ترافیکی به بیرون
نمی‌رود؛ این سنجه خودش هم هیچ درِ نوشتنیِ سفارشی نمی‌زند مگر پیش‌فرود/توقف که
درِ بک‌اند بی‌ارسالند.
"""
import argparse
import json
import os
import sys
import time

CHROME = r"C:\Users\PCMOD\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe"
BASE_DEFAULT = "http://127.0.0.1:8103"   # بک‌اندِ همین worktree درِ حالتِ توسعه
OUT_DEFAULT = r"C:\Users\PCMOD\Desktop\_bors-sarkhati-tab\_test_runs\tab_live"
# ارزشِ 'true' ازِ تصادف نیست: `authStore.ts:45` دقیقاً `=== 'true'` را بررسی
# می‌کند، پس بی‌این دانه هر testid رویِ صفحۀِ ورود «نیست» می‌شود و منفیِ
# ساختگی می‌سازد (همان تله‌ای که درِ skills/bors-live-ui-check ثبت شده).
SEED = ("try{sessionStorage.setItem('bors_auth_session','true');"
        "sessionStorage.setItem('bors_auth_user','admin');}catch(e){}")

SIZES = [(1366, 768), (1280, 720), (1024, 768), (900, 700)]
CHECKS = []


def ck(cond, label, detail=""):
    CHECKS.append((bool(cond), label, str(detail)[:220]))
    print(("  ok   " if cond else "  FAIL ") + label + ("" if cond else "  -> " + str(detail)[:200]))
    return bool(cond)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--base", default=BASE_DEFAULT,
                    help="نشانیِ بک‌اند؛ برایِ بیلدِ منجمد پورتِ خودش را بدهید")
    a = ap.parse_args()
    base = a.base.rstrip("/")
    os.makedirs(a.out, exist_ok=True)
    from playwright.sync_api import sync_playwright

    net, errors = [], []
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME, headless=True)
        ctx = b.new_context(viewport={"width": SIZES[0][0], "height": SIZES[0][1]})
        ctx.add_init_script(SEED)
        page = ctx.new_page()
        page.on("request", lambda r: net.append((r.method, r.url.split("?")[0])))
        page.on("console", lambda m: errors.append(m.text[:160]) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append("pageerror: " + str(e)[:160]))

        print("── ۱) نشانیِ مستقیم و سایدبار ──")
        # `networkidle` درِ بیلدِ منجمد هرگز رخ نمی‌دهد (فیدِ تابلو مداوم پولینگ
        # می‌کند)، پس نشانی باِ domcontentloaded باز و سپس lنگرِ صفحه انتظار
        # می‌رود — همان چیزی که واقعاً لازم است.
        page.goto(base + "/#/sarkhati", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector("[data-testid='sarkhati-page']", timeout=25000)
        ck(page.evaluate("() => location.hash") == "#/sarkhati", "hash router", page.evaluate("() => location.hash"))
        ck(page.get_by_test_id("sarkhati-status-strip").count() == 1, "خطِ وضعیت هست")
        # صبر تا کوئریِ وضعیت بنشیند: درِ بیلدِ منجمد ilk ثانیه‌ها سرویس درگیر
        # همگام‌سازیِ start-up است و اولین پاسخ ممکن است نیامده باشد (باگِ رابط
        # نیست؛ باگِ سنجه است اگر بی‌صبر قضاوت کند).
        strip = ""
        _t0 = time.time()
        while time.time() - _t0 < 30:
            strip = page.get_by_test_id("sarkhati-status-strip").inner_text()
            if "سرویسِ اجرا: " in strip:
                break
            page.wait_for_timeout(700)
        ck("سرویسِ اجرا: mock" in strip, "آداپتور از پاسخِ سرویس", strip[:120])
        ck("هیچ درخواستی از این ماشین بیرون نمی‌رود" in strip,
           "دروازۀِ ترافیک صادق اعلام شده", strip[:160])
        ck(page.get_by_test_id("nav-sarkhati").count() == 1, "سایدبار «سرخطی» را دارد")
        page.get_by_test_id("nav-sarkhati").click()
        page.wait_for_timeout(300)
        ck(page.evaluate("() => location.hash") == "#/sarkhati",
           "کلیکِ سایدبار همان مقصدِ پایدار را باز می‌کند", page.evaluate("() => location.hash"))

        print("\n── ۲) چرخیدنِ بینِ بخش‌ها هیچ نوشتنی نمی‌سازد ──")
        net_len = len(net)
        for t in ("connect", "schedule", "tracking", "risk", "monitor", "order"):
            page.get_by_test_id("sarkhati-tab-" + t).click()
            page.wait_for_timeout(220)
        writes = [(m, u) for m, u in net[net_len:] if m not in ("GET", "HEAD", "OPTIONS")]
        ck(not writes, "چرخشِ تب بدونِ هیچ POST/DELETE/PATCH", writes[:4])
        ck(page.get_by_test_id("sarkhati-sections").get_attribute("role") == "tablist",
           "بخش‌ها باِ role=tablist (برایِ screener و آزمونِ دسترسی)")

        print("\n── ۳) فرم: نماد، مقدار، ماندن و پاک\u200cشدن ──")
        page.get_by_test_id("sarkhati-tab-order").click()
        page.wait_for_selector("[data-testid='sarkhati-symbol-search']", timeout=10000)
        # بی\u200cنماد فرم ساخته نمی\u200cشود؛ «—» نماد نیست و پیش\u200cفرود با آن معنی ندارد
        ck(page.get_by_test_id("sarkhati-order-empty").count() == 1,
           "بی\u200cنماد، فرمِ سفارش ساخته نشده و علتش نوشته می\u200cشود",
           page.get_by_test_id("sarkhati-order-empty").inner_text()[:120])
        # نماد ازِ خودِ فیدِ تابلو برداشته می\u200cشود (نامِ دقیق درِ این بانک ثابت نیست)
        page.get_by_test_id("sarkhati-symbol-search").fill("نمادِقطعاًنیست999")
        page.wait_for_timeout(500)
        ck(page.get_by_test_id("sarkhati-symbol-none").count() == 1,
           "جستجویِ بی\u200cنتیجه صریح «چیزی نیست» می\u200cگوید")
        page.get_by_test_id("sarkhati-symbol-search").fill("فولاد")
        page.wait_for_selector("[data-testid^='sarkhati-symbol-pick-']", timeout=8000)
        picks = page.evaluate("""() => Array.from(
            document.querySelectorAll("[data-testid^='sarkhati-symbol-pick-']"))
            .map(e => e.getAttribute("data-testid"))""")
        ck(len(picks) > 0, "جستجو ازِ فیدِ تابلو نتیجه داد", picks[:3])
        page.query_selector("[data-testid='%s']" % picks[0]).click()
        page.wait_for_timeout(400)
        chosen = page.get_by_test_id("sarkhati-chosen-symbol").inner_text().strip()
        ck(bool(chosen) and chosen != "—" and picks[0].endswith(chosen),
           "انتخابِ نماد ازِ فیدِ تابلو نشسته است", (chosen, picks[0]))
        page.wait_for_selector("[data-testid='watch-order-price']", timeout=10000)
        page.get_by_test_id("watch-order-price").fill("12610")
        page.get_by_test_id("watch-order-qty").fill("1000")
        summary = page.get_by_test_id("sarkhati-draft-summary").inner_text()
        ck("۱۲٬۶۱۰٬۰۰۰ ریال" in summary, "ارزشِ تخمینی درِ خلاصه\u200cیِ نهایی", summary[:150])
        ck("نماد: " in summary and "هدفِ ارسال: فوری" in summary,
           "خلاصه نماد و هدف را پیش ازِ تأیید می\u200cگوید", summary[:150])
        page.get_by_test_id("sarkhati-tab-risk").click()
        page.wait_for_timeout(250)
        page.get_by_test_id("sarkhati-tab-order").click()
        ck(page.get_by_test_id("watch-order-price").input_value() == "12610",
           "فرم باِ جابه\u200cجاییِ بینِ بخش\u200cها نمی\u200cسوزد",
           page.get_by_test_id("watch-order-price").input_value())
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("[data-testid='watch-order-price']", timeout=15000)
        ck(page.get_by_test_id("watch-order-price").input_value() == "12610",
           "فرم بعدِ reload هم می\u200cماند (لینکِ مستقیم و refresh)",
           page.get_by_test_id("watch-order-price").input_value())
        # نمادِ دیگر نباید قیمتِ نمادِ اول را زیرِ خودش بگذارد
        page.get_by_test_id("sarkhati-symbol-search").fill("حديد")
        page.wait_for_selector("[data-testid^='sarkhati-symbol-pick-']", timeout=8000)
        # `evaluate` فقط JSِ ساده می‌گیرد؛ متغیرِ پایتون را نمی‌شناسد، پس
        # فیلتر درِ پایتون انجام می‌شود (نه داخلِ expression).
        allp2 = page.evaluate("""() => Array.from(
            document.querySelectorAll("[data-testid^='sarkhati-symbol-pick-']"))
            .map(e => e.getAttribute("data-testid"))""")
        picks2 = [t for t in allp2 if not t.endswith(chosen)]
        if picks2:
            page.query_selector("[data-testid='%s']" % picks2[0]).click()
            page.wait_for_timeout(400)
            ck(page.get_by_test_id("watch-order-price").input_value() == "",
               "باِ نمادِ تازه، قیمتِ نمادِ قبلی پاک می\u200cشود",
               (picks2[0], page.get_by_test_id("watch-order-price").input_value()))

        print("\n── ۴) پیش‌فرود رأیِ سرویس را می‌آورد ──")
        net_len2 = len(net)
        # «:not(:empty)» سنسورِ درستی نیست: خطِ پاسخ همیشه پر است (متنِ پیش‌فرضِ
        # دروازۀِ اجرا)، پس این انتظار بی‌درنگ رد می‌شود و متنِ *پیش ازِ کلیک*
        # خوانده می‌شود. آنچه ثابت می‌شود «تازه‌شدنِ خط به سببِ اقدام» است.
        before = page.get_by_test_id("watch-order-reason").inner_text()
        page.get_by_test_id("exec-preflight").click()
        reason, waited = before, 0.0
        while waited < 10.0:
            page.wait_for_timeout(400)
            waited += 0.4
            reason = page.get_by_test_id("watch-order-reason").inner_text()
            if reason != before:
                break
        ck(reason != before, "خطِ پاسخ باِ اقدام تازه شد (نه متنِ پیش‌فرضِ دروازه)",
           (before[:80], reason[:80]))
        ck("پیش‌فرود" in reason, "خطِ پاسخ ازِ خودِ اقدام است", reason[:150])
        ck(any(u.endswith("/api/execution/preflight") and m == "POST" for m, u in net[net_len2:]),
           "پیش‌فرود واقعاً درخواست زده", net[net_len2:][:4])
        ck(not any(u.endswith("/api/execution/dispatch") for m, u in net),
           "هیچ dispatch درِ کلِ این سنجه نرفته")

        print("\n── ۵) لغو باِ capability ──")
        page.get_by_test_id("sarkhati-tab-tracking").click()
        page.wait_for_timeout(400)
        cap = page.evaluate("async () => (await (await fetch('/api/execution/status')).json())")
        print("   capabilities:", json.dumps(cap.get("capabilities"), ensure_ascii=False))
        track = page.get_by_test_id("sarkhati-tracking-card").inner_text()
        if cap.get("capabilities", {}).get("cancel") is True:
            ck("لغوِ سفارش" in track or "لغو" in track, "باِ capabilityِ لغو، کنش هست")
        else:
            ck("پشتیبانی نمی‌شود" in track, "بی‌capabilityِ لغو، علت نوشته می‌شود", track[-160:])

        print("\n── ۶) چهار viewport ──")
        # درِ عرضِ <۱۰۲۴ پیکسل «بازرسِ نماد»ِ خودِ AppShell (`SymbolInspector.tsx:373`)
        # تمام‌صفحه می‌شود و backgroundش کلِ صفحه را می‌پوشاند — هر وقت نمادی
        # انتخاب شده باشد. این رفتارِ ازپیش‌موجودِ پوسته است (رویِ #/master و
        # #/watch هم همین‌طور سنجیده شد)، پس دو چیز جدا آزموده می‌شود:
        #   (الف) باِ نمادِ انتخابی: رندر، RTL و نبودِ اسکرولِ افقی (کلیک مسدود است)
        #   (ب) بی‌نماد درِ عرضِ کوچک: لایه‌ای مزاحم نیست ⇒ تب‌ها کلیک‌پذیرند
        for w, h in SIZES:
            page.set_viewport_size({"width": w, "height": h})
            page.wait_for_timeout(300)
            shot = os.path.join(a.out, "sarkhati_%dx%d.png" % (w, h))
            page.screenshot(path=shot, full_page=True)
            ck(page.get_by_test_id("sarkhati-page").count() == 1
               and page.get_by_test_id("sarkhati-status-strip").count() == 1,
               "%dx%d: صفحه کامل رندر شد" % (w, h), os.path.basename(shot))
            ck(not page.evaluate(
                "() => document.documentElement.scrollWidth > window.innerWidth + 2"),
               "%dx%d: اسکرولِ افقیِ ناخواسته نیست" % (w, h),
               page.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]"))
            ck("سرخطی" in page.evaluate("() => document.body.innerText"),
               "%dx%d: عنوانِ تب دیده می‌شود" % (w, h))
            if w >= 1024:
                page.get_by_test_id("sarkhati-tab-order").click(timeout=6000)
                page.wait_for_timeout(250)
                ck(page.get_by_test_id("watch-order-price").count() == 1,
                   "%dx%d: تب‌ها کلیک‌پذیر و فرم دیده می‌شود" % (w, h))
            else:
                blocked = page.evaluate(
                    "() => { const d = document.querySelector('.fixed.inset-0.z-40');"
                    "return d ? getComputedStyle(d).opacity : 'none'; }")
                print("   %dx%d: بازرسِ نماد تمام‌صفحه (opacity=%s) — کلیکِ تب درِ این"
                      " عرض مسدود است؛ رفتارِ خودِ پوسته، نه این تب" % (w, h, blocked))
        # «بی‌نماد» یعنی هیچ منبعی نماد نمی‌دهد: هم استورِ سراسری و هم
        # stateِ تب‌هایِ فضایِ کاری (bors-workspace-tabs) که درِ فاز ۵ منبعِ
        # دومِ نمادِ هرِ تب شد وِ پسِ reload آن را برمی‌گرداند.
        page.evaluate("() => { try { localStorage.removeItem('bors-symbol');"
                      " localStorage.removeItem('bors-workspace-tabs'); } catch (e) {} }")
        page.set_viewport_size({"width": 900, "height": 700})
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("[data-testid='sarkhati-page']", timeout=15000)
        for t in ("schedule", "tracking", "risk", "monitor", "order"):
            page.get_by_test_id("sarkhati-tab-" + t).click(timeout=5000)
            page.wait_for_timeout(200)
        page.screenshot(path=os.path.join(a.out, "sarkhati_no-symbol_900x700.png"),
                        full_page=True)
        ck(page.get_by_test_id("sarkhati-order-empty").count() == 1,
           "900x700 بی‌نماد: تب‌ها کلیک‌پذیرند و فرم باِ علتِ صریح بسته است")
        page.set_viewport_size({"width": SIZES[0][0], "height": SIZES[0][1]})

        b.close()

    print("\n── خطاهایِ کنسول: %d ──" % len(errors))
    for e in errors[:6]:
        print("   ", e)
    ck(not [e for e in errors if "Unexpected Application Error" in e], "بدونِ ErrorBoundary")
    bad = [c for c in CHECKS if not c[0]]
    print("\n%d سنجه، %d خطا" % (len(CHECKS), len(bad)))
    with open(os.path.join(a.out, "checks.json"), "w", encoding="utf-8") as fh:
        json.dump([{"ok": o, "label": l, "detail": d} for o, l, d in CHECKS], fh,
                  ensure_ascii=False, indent=1)
    print("SARKHATI TAB LIVE " + ("OK" if not bad else "FAILED"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
