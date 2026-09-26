"""محورِ چارت پس از روشن/خاموش کردنِ همسنج جابه‌جا می‌شود؟ (شاهدِ اسکرینشاتِ RA-3)

دو مسیرِ جدا در دو نشستِ تازه:
  الف) فولاد → تعدیلِ عملکردی                       (بی‌همسنج)
  ب) فولاد → همسنجِ شپنا → تعدیلِ عملکردی → برداشتن
اسکرینشاتِ دو انتها مقایسه می‌شود؛ اگر محورِ ب با الف فرق کند، همسنج چیزی را
پشتِ خودش خراب گذاشته است.
"""
from __future__ import annotations

import re
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8003"
SYM = sys.argv[2] if len(sys.argv) > 2 else "فولاد"
OTHER = sys.argv[3] if len(sys.argv) > 3 else "شپنا"
SHOTS = "E:/bors-ui-qa/shots/ra3"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def login(pg):
    pg.goto(BASE + "/#/fundamental")
    if pg.evaluate("() => !!document.querySelector('input[type=password]')"):
        pg.locator("input").first.fill("admin")
        pg.locator("input[type=password]").first.fill("bors123")
        pg.get_by_role("button", name=re.compile("ورود")).first.click()
    pg.wait_for_timeout(2000)


def open_chart(pg):
    pg.goto(f"{BASE}/#/technical/{SYM}")
    pg.wait_for_selector("canvas", timeout=45000)
    pg.wait_for_timeout(7000)


def set_perf(pg):
    pg.get_by_title("نوع تعدیل قیمت").click()
    pg.wait_for_timeout(400)
    pg.get_by_text("تعدیل عملکردی").first.click()
    pg.wait_for_timeout(4000)


def add_compare(pg):
    pg.get_by_test_id("compare-open").click()
    pg.wait_for_timeout(600)
    pg.locator("input[placeholder*='جستجو']").last.fill(OTHER)
    pg.wait_for_timeout(1200)
    card = pg.locator(
        "xpath=(//input[contains(@placeholder,'جستجوی نماد')]/ancestor::div[2])[last()]"
    )
    card.get_by_text(OTHER, exact=True).first.click()
    pg.wait_for_timeout(6000)


def main():
    errs: list[str] = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()

        pg = b.new_page(viewport={"width": 1600, "height": 900})
        pg.on("pageerror", lambda e: errs.append("الف: " + str(e)))
        login(pg)
        open_chart(pg)
        set_perf(pg)
        pg.screenshot(path=f"{SHOTS}/axis-a-plain.png")
        print("الف) فولاد + عملکردی، بی‌همسنج — ذخیره شد", flush=True)
        pg.close()

        pg = b.new_page(viewport={"width": 1600, "height": 900})
        pg.on("pageerror", lambda e: errs.append("ب: " + str(e)))
        login(pg)
        open_chart(pg)
        add_compare(pg)
        pg.screenshot(path=f"{SHOTS}/axis-b-with-compare.png")
        set_perf(pg)
        pg.get_by_test_id("compare-clear").click()
        pg.wait_for_timeout(4000)
        pg.screenshot(path=f"{SHOTS}/axis-b-after-clear.png")
        print("ب) فولاد + همسنج + عملکردی، پس از برداشتن — ذخیره شد", flush=True)

        print("خطاها:", len(errs), flush=True)
        for e in errs[:6]:
            print("   ", e[:160], flush=True)
        b.close()


if __name__ == "__main__":
    main()
