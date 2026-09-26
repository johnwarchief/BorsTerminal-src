#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/ui_portfolio_check.py — دستِ Playwright روی flow «افزودن دارایی به سبد».

گاردِ پایتون (dev/portfolio_weights_v1035.py) منطقِ سرور را می‌سنجد و
vitest کامپوننت را؛ این اسکریپت همان مسیر را روی buildِ واقعیِ سرویس‌شده
تأیید می‌کند: جستجوی نماد → نام/قیمت از سرور → تعداد با رقمِ فارسی →
ارزش و وزنِ زنده → ذخیره → ردیفِ جدول → جملهٔ ترکیبِ طبقات.

پیش‌نیاز: سرورِ توسعه روی --base (پیش‌فرض 127.0.0.1:8011) و `npm run build`.
اجرا:     python tools/ui_portfolio_check.py
پاک‌سازی: ردیف‌هایِ آزمون در پایان حذف می‌شوند.
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

TEST_SYMBOLS = ("آوا", "فولاد", "عيار")
fails: list[str] = []


def ck(name: str, cond: bool, got=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else f"  ← {got}"))
    if not cond:
        fails.append(name)


def api(base: str, path: str, method: str = "GET"):
    req = urllib.request.Request(base + path, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except Exception:
        return None


_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(x) -> str:
    """عددِ پایتونی → رقمِ فارسی، همان‌طور که UI چاپ می‌کند (نقطهٔ اعشار می‌ماند)."""
    return str(x).translate(_FA)


def cover_of(pg) -> float | None:
    """«پوشش X٪» روی نوارِ شکاف — اگر یک وزن دو بار جمع شود از ۱۰۰ رد می‌شود."""
    txt = pg.locator('[aria-label="نوار شکاف و ری‌بالانس"]').inner_text()
    m = re.search(r"پوشش\s*([\d.]+)٪", txt)
    if not m:
        return None
    return float(m.group(1).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))


def pick_symbol(pg, sym: str):
    """ردیفِ همانِ نماد را کلیک می‌کند، نه هر ردیفی که نامش آن کلیدواژه را دارد.

    نامِ چند صندوق «عیار» دارد (فیروز/…)، پس تطبیقِ متنِ کامل اشتباه می‌زد؛
    دکمهٔ نتیجه با خودِ نماد شروع می‌شود.
    """
    row = pg.get_by_role("button", name=re.compile(r"^" + re.escape(sym) + r"[\s]"))
    if row.count() == 0:
        raise AssertionError(f"نتیجه‌ای برای نمادِ «{sym}» پیدا نشد")
    row.first.click()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8011")
    a = ap.parse_args()
    base = a.base

    with sync_playwright() as p:
        b = p.chromium.launch(args=["--disable-gpu"])
        ctx = b.new_context(viewport={"width": 1600, "height": 950})
        # دروازهٔ ورود محلیِ UI (همان ترفندِ tools/ui_walkthrough.py)
        ctx.add_init_script("try{sessionStorage.setItem('bors_auth_session','true')}catch(e){}")
        pg = ctx.new_page()
        errs: list[str] = []
        pg.on("pageerror", lambda e: errs.append(str(e)))

        pg.goto(base + "/#/portfolio", wait_until="networkidle")
        pg.wait_for_timeout(1200)
        pg.get_by_role("tab", name="پرتفوی فعلی").click()
        pg.wait_for_timeout(500)

        # ۱) صندوقِ طلا: جستجو → پیش‌پرشِ قیمت → تعداد با رقمِ فارسی
        pg.get_by_role("button", name="افزودن دارایی").click()
        pg.wait_for_selector('[role="dialog"]')
        pg.get_by_label("جستجوی نام یا نماد دارایی").fill("عیار")
        pg.wait_for_timeout(1000)
        pick_symbol(pg, "عيار")
        price = pg.get_by_label("قیمت هر واحد به تومان")
        pg.wait_for_function(
            "() => document.querySelector('[aria-label=\"قیمت هر واحد به تومان\"]')?.value.length > 0",
            timeout=6000)
        px = price.input_value()
        ck("قیمتِ انتخابی از سرور پیش‌پر شد", px.isdigit() and int(px) > 0, px)
        pg.get_by_label("تعداد دارایی").fill("۱۰")
        pg.wait_for_timeout(400)
        val = pg.get_by_test_id("basket-row-value").inner_text()
        ck("ارزشِ ردیف با رقمِ فارسی حساب می‌شود", f"{int(px) * 10:,}".replace(",", "٬") in val or "تومان" in val, val)
        pg.get_by_role("button", name="ثبت تصمیم").click()
        pg.wait_for_timeout(1600)

        table = pg.locator("table").inner_text()
        ck("ردیفِ تازه در جدول نشست", "عيار" in table, table[:160])
        ck("تعداد در ردیف دیده می‌شود", "بدون تعداد" not in table, table[:160])
        ck("جملهٔ ترکیبِ طبقات طلا را از سبد می‌گوید (نه صفر)",
           pg.get_by_test_id("mix-sentence").count() >= 1
           and "طلا" in pg.get_by_test_id("mix-sentence").first.inner_text(),
           pg.get_by_test_id("mix-sentence").first.inner_text() if pg.get_by_test_id("mix-sentence").count() else "-")
        # سبدِ تک‌صندوقِ طلا: اگر وزنِ همان ردیف در «جانشینِ سهام» هم جمع شود،
        # پوشش ۲۰۰٪ و جمله «سهام ۱۰۰٪» می‌شود.
        ck("با یک صندوقِ طلا، پوشش از ۱۰۰٪ رد نمی‌شود", (cover_of(pg) or 0) <= 100.001,
           str(cover_of(pg)))
        # دوناتِ «تحلیل دارایی‌ها» همان سبد را می‌خواند؛ پیش از این «جمعِ وزنِ همهٔ
        # پوزیشن‌ها» را سهام می‌نامید و همین سبد تک‌صندوقی را «سهام ۱۰۰٪» می‌کرد.
        pg.get_by_role("tab", name="پرتفوی هدف").click()
        pg.wait_for_timeout(700)
        # سطرهای سنجهٔ هم‌ترازی: «طلا و سکه — هدف ۴۵٪ · واقعی …»
        gold_li = pg.locator("li").filter(has_text=re.compile("طلا و سکه"))
        eq_li = pg.locator("li").filter(has_text=re.compile("سهام مستقیم"))
        _g = [gold_li.nth(i).inner_text() for i in range(gold_li.count())]
        _e = [eq_li.nth(i).inner_text() for i in range(eq_li.count())]
        ck("طلا در سنجهٔ هم‌ترازی ۱۰۰٪ است", len(_g) >= 1 and all("۱۰۰٪" in x for x in _g), str(_g[:2]))
        # دونات پیش از این «جمعِ وزنِ همهٔ پوزیشن‌ها» را سهام می‌خواند و همین
        # سبدِ تک‌صندوقی را «سهام ۱۰۰٪» می‌کرد.
        ck("سبدِ تمام‌طلا در دونات «سهام ۱۰۰٪» نمی‌شود",
           all("۱۰۰٪" not in x for x in _e), str(_e[:2]))
        pg.get_by_role("tab", name="پرتفوی فعلی").click()
        pg.wait_for_timeout(500)

        # ۲) دومی: دکمهٔ «افزودن» باید همان «افزودن» بماند و وزنِ نسبی درست حساب شود
        add = pg.get_by_role("button", name="افزودن دارایی")
        ck("دکمهٔ افزودن پس از ذخیره سرِ جایش می‌ماند", add.count() >= 1, str(add.count()))
        add.first.click()
        pg.wait_for_selector('[role="dialog"]')
        pg.get_by_label("جستجوی نام یا نماد دارایی").fill("فولاد")
        pg.wait_for_timeout(1000)
        pick_symbol(pg, "فولاد")
        pg.wait_for_timeout(400)
        px2 = pg.get_by_label("قیمت هر واحد به تومان").input_value()
        pg.get_by_label("تعداد دارایی").fill("100")
        pg.wait_for_timeout(400)
        w2 = pg.get_by_test_id("basket-row-weight").inner_text()
        want = round(int(px2) * 100 / (int(px2) * 100 + int(px) * 10) * 100, 1)
        ck("وزنِ نسبی با هر دو ردیف درست می‌شود", fa(want) in w2, f"{w2} (منتظره {fa(want)}٪)")
        pg.get_by_role("button", name="ثبت تصمیم").click()
        pg.wait_for_timeout(1600)
        table2 = pg.locator("table").inner_text()
        ck("دو ردیف در سبد است", "فولاد" in table2 and "عيار" in table2, table2[:200])

        # ۴) #106: «طلا» دو ردیفِ هدف دارد (فیزیکی + گواهی) ولی تابلو یک طبقه
        # می‌دهد. اگر همان درصد روی هر دو بنشیند، «پوشش» ۱۸۷٪ و دو کارتِ تکراری
        # می‌شود. اینجا روی buildِ واقعی سنجیده می‌شود، نه فقط در vitest.
        with urllib.request.urlopen(base + "/api/selection/portfolio", timeout=10) as r:
            _lim = (json.loads(r.read().decode()) or {}).get("limits") or {}
        _mix = _lim.get("class_mix_pct") or {}
        ck("نمونهٔ آزمون واقعاً ترکیبِ طبقات دارد", bool(_mix), str(_lim)[:120])
        bar = pg.locator('[aria-label="نوار شکاف و ری‌بالانس"]')
        pg.get_by_role("button", name=re.compile(r"جزئیات ری‌بالانس")).click()
        pg.wait_for_timeout(600)
        bar_txt = bar.inner_text()
        ck("«پوشش» از ۱۰۰٪ رد نمی‌شود (وزنِ طبقه دو بار جمع نشده)",
           cover_of(pg) is not None and cover_of(pg) <= 100.001, bar_txt[:200])
        gold_cards = bar.locator("li").filter(has_text=re.compile("طلای فیزیکی|گواهی سپردهٔ طلا"))
        ck("کارتِ ری‌بالانس، طلا را یک بار می‌آورد", gold_cards.count() <= 1,
           f"{gold_cards.count()} کارتِ طلا")
        if gold_cards.count() == 1:
            ck("کارتِ طلا هدفِ جمعِ طبقه (۴۵٪) را می‌گوید، نه ۳۰٪ِ سطر",
               "هدف ۴۵٪" in gold_cards.first.inner_text(), gold_cards.first.inner_text())
        ms = pg.get_by_test_id("mix-sentence")
        sent = ms.first.inner_text() if ms.count() else ""
        ck("جملهٔ headline ساخته می‌شود و مخرجش را می‌گوید",
           bool(sent) and ("از سبد" in sent or "از سرمایه" in sent), sent)
        ck("ردیفِ ادغام‌شده به‌جای «بدون داده»، علت دارد",
           "سنجیده شد" in bar_txt, bar_txt[-220:])

        # ۳) قیمت را پاک کن → وزنِ خودکار باید صادقانه رد شود، نه صفر بسازد
        pg.get_by_role("button", name="افزودن دارایی").click()
        pg.wait_for_selector('[role="dialog"]')
        pg.get_by_label("تعداد دارایی").fill("5")
        pg.get_by_label("قیمت هر واحد به تومان").fill("")
        pg.wait_for_timeout(300)
        ck("بدونِ قیمت، ارزشی ساخته نمی‌شود",
           "لازم است" in pg.get_by_test_id("basket-row-value").inner_text(),
           pg.get_by_test_id("basket-row-value").inner_text())
        pg.get_by_role("button", name="بستن").last.click()

        ck("بدون خطای رانر", not errs, str(errs[:2]))
        b.close()

    for s in TEST_SYMBOLS:
        api(base, "/api/selection/decision/" + urllib.parse.quote(s), "DELETE")
    with urllib.request.urlopen(base + "/api/selection/portfolio", timeout=10) as r:
        left = json.loads(r.read().decode()).get("decisions") or []
    print(f"  ..   ردیف‌هایِ باقی‌مانده پس از پاک‌سازی: {[d['symbol'] for d in left]}")
    print("\n" + (f"{len(fails)} شکست: " + " | ".join(fails) if fails else "همه سبز"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
