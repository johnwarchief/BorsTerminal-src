"""نمای زندهٔ چارتِ کندل‌استیک برای چند نماد — شواهد بصریِ CANDLE-1.

دیتا را با `tools/candle_source_audit.py` سنجیدیم؛ این اسکریپت سؤالِ باقی‌مانده را
پاسخ می‌دهد: «آیا کاربر روی چارت درست می‌بیند؟» (سؤالی که با عدد حل نمی‌شود).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8011"
SHOTS = Path(sys.argv[2] if len(sys.argv) > 2 else "E:/bors-ui-qa/shots/candles")
SYMS = sys.argv[3:] or ["آسود", "فولاد", "خودرو", "اعتماد4"]


def login(pg):
    pg.goto(BASE + "/#/fundamental")
    if pg.evaluate("() => !!document.querySelector('input[type=password]')"):
        pg.locator("input").first.fill("admin")
        pg.locator("input[type=password]").first.fill("bors123")
        pg.get_by_role("button", name=re.compile("ورود")).first.click()
    pg.wait_for_timeout(2000)


def chart_stats(pg):
    """از خودِ کتابخانهٔ چارت می‌پرسیم چه میله‌هایی در دید است، نه از حدسِ پیکسلی."""
    return pg.evaluate("""() => {
      const k = window.__kline || null;
      const cv = document.querySelectorAll('canvas');
      const boxes = [...cv].slice(0,3).map(c => {
        const r = c.getBoundingClientRect();
        return {w: Math.round(r.width), h: Math.round(r.height)};
      });
      const texts = [...document.querySelectorAll('span,div')]
        .map(e => (e.textContent||'').trim())
        .filter(t => /^[\\d٠-٩.,%±]{1,14}$/.test(t));
      return {canvases: boxes, numeric_nodes: texts.length,
              symbol_head: (document.querySelector('h1,h2')?.textContent||'').trim().slice(0,40)};
    }""")


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1600, "height": 900})
        errs: list[str] = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        login(pg)
        for sym in SYMS:
            errs.clear()
            pg.goto(f"{BASE}/#/technical/{sym}")
            try:
                pg.wait_for_selector("canvas", timeout=45000)
            except Exception:  # noqa: BLE001
                pass
            pg.wait_for_timeout(6000)
            out = SHOTS / f"{sym}.png"
            pg.screenshot(path=str(out))
            st = chart_stats(pg)
            print(f"{sym:<10} → {out.name}  canvases={st['canvases']} "
                  f"numeric={st['numeric_nodes']} head={st['symbol_head']!r} "
                  f"errors={len(errs)}", flush=True)
            for e in errs[:3]:
                print(f"    خطای صفحه: {e[:160]}", flush=True)
        b.close()


if __name__ == "__main__":
    main()
