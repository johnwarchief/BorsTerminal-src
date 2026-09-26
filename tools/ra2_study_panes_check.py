"""#126 — نُه مطالعۀ ره‌آورد روی چارتِ زنده پنلِ واقعی می‌سازند یا فقط تیک می‌خورند؟

تا این‌جا فقط ثبتِ مطالعه و خالصِ calc تست شده بود. این اسکریپت تک‌تکِ مطالعه‌ها را
از مودالِ اندیکاتورها روشن/خاموش می‌کند و از خودِ چارت می‌پرسد چند بوم و چند پنل
ساخته شد؛ خطایِ صفحه (از جمله همان «l.call is not a function» که همسنج داد)
گزارش می‌شود.

اجرا با پایتونِ محیطِ توسعه:
    python tools/ra2_study_panes_check.py http://127.0.0.1:8003
"""
from __future__ import annotations

import re
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8003"
SYM = sys.argv[2] if len(sys.argv) > 2 else "فولاد"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# همان برچسب‌هایِ MABNA_INDICATORS در tvIndicatorCatalog.ts
MABNA = [
    "نوسان‌گر دی‌تی (DT Oscillator)",
    "امتیاز زی (Z Score)",
    "فشارِ مومنتوم (Squeeze Momentum [LazyBear])",
    "نیم‌روند (HalfTrend)",
    "سطوح حمایت و مقاومت با شکست (Support And Resistance Levels With Breaks)",
    "ویو‌ترند (WaveTrend Oscillator [WT])",
    "باندهای بولینگر فیبوناچی (Fibonacci Bollinger Bands)",
    "ویو‌ترند با تقاطع‌ها (WaveTrend with Crosses)",
    "ویکس‌فیک ویلیامز؛ کف‌یاب بازار (CM_Williams_Vix_Fix Finds Market Bottoms)",
]

STATE = """() => {
  const host = document.querySelector('.nahayat-negar-container');
  const panes = new Set();
  if (host) host.querySelectorAll('div').forEach(d => {
    const r = d.getBoundingClientRect();
    if (r.width > 800 && r.height > 30 && r.height < 900) panes.add(Math.round(r.y) + 'x' + Math.round(r.height));
  });
  return { canvases: document.querySelectorAll('canvas').length, paneSlots: panes.size };
}"""


def login(pg):
    pg.goto(BASE + "/#/fundamental")
    if pg.evaluate("() => !!document.querySelector('input[type=password]')"):
        pg.locator("input").first.fill("admin")
        pg.locator("input[type=password]").first.fill("bors123")
        pg.get_by_role("button", name=re.compile("ورود")).first.click()
    pg.wait_for_timeout(2000)


def main():
    errs: list[str] = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1600, "height": 900})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        login(pg)
        pg.goto(f"{BASE}/#/technical/{SYM}")
        pg.wait_for_selector("canvas", timeout=45000)
        pg.wait_for_timeout(8000)
        base = pg.evaluate(STATE)
        print(f"پایه ({SYM}): {base}", flush=True)

        pg.get_by_title("پنل اندیکاتورها").click()
        pg.wait_for_timeout(500)

        bad = []
        for label in MABNA:
            errs.clear()
            box = pg.locator(f'label:has-text("{label}") input[type=checkbox]')
            if box.count() == 0:
                print(f"  {label[:34]:<34} → برچسب در مودال نیست", flush=True)
                bad.append(label)
                continue
            box.first.click()
            pg.wait_for_timeout(2600)
            st = pg.evaluate(STATE)
            checked = box.first.is_checked()
            delta = st["canvases"] - base["canvases"]
            print(f"  {label[:34]:<34} → تیک={checked} بوم‌ها={st['canvases']} (+{delta}) "
                  f"پنل‌ها={st['paneSlots']} خطا={len(errs)}", flush=True)
            for e in errs[:2]:
                print(f"      خطا: {e[:150]}", flush=True)
            if not checked or len(errs) > 0:
                bad.append(label)
            box.first.click()  # خاموش برای سنجشِ بعدی
            pg.wait_for_timeout(1200)

        pg.screenshot(path="E:/bors-ui-qa/shots/ra3/mabna-studies.png")
        print(f"\nناتمام/خطا: {len(bad)}", flush=True)
        for x in bad:
            print("   -", x, flush=True)
        b.close()


if __name__ == "__main__":
    main()
