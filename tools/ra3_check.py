"""RA-3 — بررسیِ زندهٔ سه قابلیتِ جاافتاده از ره‌آورد، روی چارتِ واقعی.

سه چیز که ویتست نمی‌تواند ثابتشان کند:
  ۱) همسنجیِ دو نماد واقعاً پنلِ جدید می‌سازد و عددِ اختلافِ بازدهی را نشان می‌دهد
  ۲) هشدارِ قیمتی با تیکرِ زنده شلیک می‌شود و در localStorage می‌ماند
  ۳) قالبِ چارت همان مطالعه‌ها را ذخیره و دوباره می‌سازد

اجرا با پایتونِ محیطِ توسعه (playwright نصب‌شده)، نه محیطِ ریلیز:
    python tools/ra3_check.py http://127.0.0.1:8003
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8003"
SYM = sys.argv[2] if len(sys.argv) > 2 else "فولاد"
OTHER = sys.argv[3] if len(sys.argv) > 3 else "شپنا"
SHOTS = Path("E:/bors-ui-qa/shots/ra3")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ساختارِ پنل‌ها را از DOMِ میزبانِ چارت می‌خوانیم: هر پنل یک div فرزند با ارتفاع
LAYOUT = """() => {
  const host = document.querySelector('.nahayat-negar-container');
  if (!host) return {host: false};
  const panes = [];
  host.querySelectorAll(':scope > div > div, :scope > div').forEach(d => {
    const r = d.getBoundingClientRect();
    if (r.width > 200 && r.height > 20) panes.push(Math.round(r.height));
  });
  return {
    host: true,
    canvases: document.querySelectorAll('canvas').length,
    paneHeights: panes.slice(0, 12),
    testids: [...document.querySelectorAll('[data-testid]')]
      .map(e => e.getAttribute('data-testid'))
      .filter(t => /compare|alert|template/.test(t)),
  };
}"""

STORES = """() => ({
  alerts: localStorage.getItem('fts.price-alerts.v1'),
  templates: localStorage.getItem(['fts','chart','templates','v1'].join('.')),
})"""


def login(pg):
    pg.goto(BASE + "/#/fundamental")
    if pg.evaluate("() => !!document.querySelector('input[type=password]')"):
        pg.locator("input").first.fill("admin")
        pg.locator("input[type=password]").first.fill("bors123")
        pg.get_by_role("button", name=re.compile("ورود")).first.click()
    pg.wait_for_timeout(2000)


def show(label, value):
    print(f"  {label}: {json.dumps(value, ensure_ascii=False)[:400]}", flush=True)


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    errs: list[str] = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1600, "height": 900})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        login(pg)
        # نشست‌هایِ پیشین ممکن است هشدار/قالبِ آزمون جا گذاشته باشند
        pg.evaluate(
            """() => {
              localStorage.removeItem('fts.price-alerts.v1');
              localStorage.removeItem(['fts','chart','templates','v1'].join('.'));
            }"""
        )

        # ── ۱) همسنجی ────────────────────────────────────────────────────────
        print("\n=== ۱) همسنجیِ دو نماد ===", flush=True)
        pg.goto(f"{BASE}/#/technical/{SYM}")
        pg.wait_for_selector("canvas", timeout=45000)
        pg.wait_for_timeout(7000)
        errs.clear()
        before = pg.evaluate(LAYOUT)
        show("پیش از همسنجی", before)

        pg.get_by_test_id("compare-open").click()
        pg.wait_for_timeout(600)
        box = pg.locator("input[placeholder*='جستجو']").last
        box.fill(OTHER)
        pg.wait_for_timeout(1200)
        card = pg.locator(
            "xpath=(//input[contains(@placeholder,'جستجوی نماد')]/ancestor::div[2])[last()]"
        )
        card.get_by_text(OTHER, exact=True).first.click()
        pg.wait_for_timeout(6000)

        after = pg.evaluate(LAYOUT)
        show("پس از همسنجی", after)
        chip = pg.locator('[data-testid="compare-chip"]').inner_text() if pg.get_by_test_id(
            "compare-chip").count() else None
        gap = pg.get_by_test_id("compare-gap")
        print(f"  چیپ: {chip!r}  gap={'(نیست)' if gap.count() == 0 else gap.first.inner_text()}", flush=True)
        pg.screenshot(path=str(SHOTS / f"compare-{SYM}-{OTHER}.png"), full_page=False)
        print(f"  پنل اضافه شد؟ {len(after.get('paneHeights', [])) > len(before.get('paneHeights', []))} "
              f"| خطاها: {len(errs)}", flush=True)
        for e in errs[:3]:
            print(f"    خطای صفحه: {e[:200]}", flush=True)

        # حالتِ تعدیلِ عملکردی با همسنجِ روشن — نباید چارت را بشکند
        errs.clear()
        pg.get_by_title("نوع تعدیل قیمت").click()
        pg.wait_for_timeout(500)
        pg.get_by_text("تعدیل عملکردی").first.click()
        pg.wait_for_timeout(4000)
        show("پس از تعدیلِ عملکردی", pg.evaluate(LAYOUT))
        print(f"  خطاهای تعدیل: {len(errs)}", flush=True)
        for e in errs[:3]:
            print(f"    {e[:200]}", flush=True)
        if pg.get_by_test_id("compare-clear").count():
            pg.get_by_test_id("compare-clear").click()
            pg.wait_for_timeout(1500)
            show("پس از برداشتنِ همسنج", pg.evaluate(LAYOUT))

        # ── ۲) هشدارِ قیمتی ──────────────────────────────────────────────────
        print("\n=== ۲) هشدارِ قیمتی ===", flush=True)
        errs.clear()
        pg.get_by_test_id("price-alert-bell").click()
        pg.wait_for_timeout(500)
        show("پنل باز شد", {"panel": pg.get_by_test_id("price-alerts-panel").count()})
        show("جایِ پنل و ورودیِ آستانه", pg.evaluate("""() => {
          const p = document.querySelector('[data-testid="price-alerts-panel"]');
          const i = document.querySelector('[data-testid="alert-price"]');
          const r = (e) => { if (!e) return null; const b = e.getBoundingClientRect();
            return {x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height),
                    hidden: b.width === 0 || b.height === 0}; };
          const top = i ? document.elementFromPoint(i.getBoundingClientRect().x + 5,
                                                   i.getBoundingClientRect().y + 5)?.tagName : null;
          return {panel: r(p), price: r(i), pointOverPrice: top,
                  vw: innerWidth, vh: innerHeight};
        }"""))

        # شرطی که همین حالا برقرار است: قیمتِ اکنون زیرِ هر آستانۀ بالا است
        pg.get_by_test_id("alert-side-below").click()
        pg.get_by_test_id("alert-price").fill("۹۹۹۹۹۹۹۹")
        pg.wait_for_timeout(400)
        show("راهنمایِ شلیکِ فوری", pg.get_by_test_id("alert-immediate").count())
        pg.get_by_test_id("alert-add").click()
        pg.wait_for_timeout(2500)
        show("بنر", {
            "banner": pg.get_by_test_id("price-alert-banner").count(),
            "shotted": pg.locator('[data-testid^="alert-fired-"]').count(),
            "rows": pg.locator('[data-testid^="alert-row-"]').count(),
        })
        if pg.get_by_test_id("price-alert-banner").count():
            show("متنِ بنر", pg.get_by_test_id("price-alert-banner").inner_text()[:120])
            pg.get_by_test_id("price-alert-dismiss").click()
        pg.screenshot(path=str(SHOTS / "alerts.png"))

        # آستانهٔ دست‌نیافتنی ⇒ باید فعال بماند
        pg.get_by_test_id("alert-side-above").click()
        pg.get_by_test_id("alert-price").fill("۹۹۹۹۹۹۹۹")
        pg.get_by_test_id("alert-add").click()
        pg.wait_for_timeout(1500)
        store = pg.evaluate(STORES)
        alerts = json.loads(store["alerts"] or '{"alerts":[]}').get("alerts", [])
        print("  هشدارها در حافظه:", flush=True)
        for a in alerts:
            print(f"    {a['symbol']} {a['side']} {a['price']} active={a['active']} "
                  f"firedAt={a['firedAt']} seen={a['seen']}", flush=True)
        print(f"  خطاهای هشدار: {len(errs)}", flush=True)
        for e in errs[:3]:
            print(f"    {e[:200]}", flush=True)

        # ── ۳) قالبِ چارت ────────────────────────────────────────────────────
        print("\n=== ۳) قالبِ چارت ===", flush=True)
        errs.clear()
        pg.get_by_test_id("price-alert-bell").click()  # بستنِ پنلِ هشدار
        pg.wait_for_timeout(300)
        pg.get_by_title("پنل اندیکاتورها").click()
        pg.wait_for_timeout(500)
        ma = pg.get_by_text("میانگین متحرک نمایی (EMA 50)")
        ma.click()
        pg.wait_for_timeout(1500)
        show("پس از روشن کردن EMA", pg.evaluate(LAYOUT)["testids"])

        pg.get_by_test_id("template-name").fill("آزمونِ RA-3")
        pg.get_by_test_id("template-save").click()
        pg.wait_for_timeout(800)
        store = pg.evaluate(STORES)
        raw = json.loads(store["templates"] or "[]")
        tps = raw.get("templates", []) if isinstance(raw, dict) else raw
        print("  قالب‌ها:", json.dumps(tps, ensure_ascii=False)[:400], flush=True)
        ema_box = pg.locator('label:has-text("میانگین متحرک نمایی") input')
        if tps:
            show("تیکِ EMA پیش از برداشتن", ema_box.is_checked())
            # خاموش کردن، بعد اعمالِ دوباره
            ma.click()
            pg.wait_for_timeout(1200)
            show("تیکِ EMA پس از برداشتن", ema_box.is_checked())
            pg.get_by_test_id(f"template-apply-{tps[0]['id']}").click()
            pg.wait_for_timeout(2500)
            show("پس از اعمالِ قالب", pg.evaluate(LAYOUT))
            show("تیکِ EMA پس از اعمالِ قالب", ema_box.is_checked())
        pg.screenshot(path=str(SHOTS / "templates.png"))
        for t in tps:
            pg.get_by_test_id(f"template-remove-{t['id']}").click()
            pg.wait_for_timeout(300)
        print(f"  خطاهای قالب: {len(errs)}", flush=True)
        for e in errs[:3]:
            print(f"    {e[:200]}", flush=True)

        # ── پاکسازیِ stateِ آزمون ─────────────────────────────────────────────
        pg.goto(f"{BASE}/#/technical/{SYM}")
        pg.wait_for_selector("canvas", timeout=45000)
        pg.wait_for_timeout(4000)
        pg.get_by_test_id("price-alert-bell").click()
        pg.wait_for_timeout(400)
        if pg.get_by_test_id("alert-clear-all").count():
            pg.get_by_test_id("alert-clear-all").click()
        pg.wait_for_timeout(500)
        left = pg.evaluate(STORES)
        print("  پس از پاکسازی — هشدار: "
              f"{json.dumps(left['alerts'], ensure_ascii=False)} | قالب: {json.dumps(left['templates'], ensure_ascii=False)}",
              flush=True)
        b.close()
        print("\nپایان. شواهد: " + str(SHOTS), flush=True)


if __name__ == "__main__":
    main()
