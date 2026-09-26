"""شواهدِ زندهٔ #147 — نشانهٔ «باز شدن» روی نوارهای دراپ‌داونی.

jev_ui_check برای برچسب‌های یک‌مرحله‌ای است؛ اینجا سه نوار نیاز به کلیکِ دوم
دارند (داک پایین چارت، دراورِ ری‌بالانس، و <details> ثبتِ ارزش)، پس با
Playwright مستقیم اندازهٔ ارتفاع را قبل/بعد از کلیک می‌گیریم: انیمیشنِ
ارتفاع بدونِ تغییرِ ارتفاع یعنی هیچ.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8003"
SHOTS = Path("E:/bors-ui-qa/shots/drop-aff")
SYMBOL = "شپنا"


def login(pg) -> None:
    pg.goto(BASE + "/#/fundamental")
    if pg.evaluate("() => !!document.querySelector('input[type=password]')"):
        pg.locator("input").first.fill("admin")
        pg.locator("input[type=password]").first.fill("bors123")
        pg.get_by_role("button", name="ورود").first.click()
    pg.wait_for_timeout(1500)


def box(pg, selector: str) -> dict | None:
    return pg.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {w: Math.round(r.width), h: Math.round(r.height),
                    expanded: el.getAttribute('aria-expanded'),
                    text: (el.textContent || '').trim().slice(0, 60)};
        }""",
        selector,
    )


def main() -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    report: dict = {}
    errs: list[str] = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1366, "height": 900})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        login(pg)

        # ── ۱) داک پایین چارت ────────────────────────────────────────────────
        pg.goto(f"{BASE}/#/technical/{SYMBOL}")
        pg.wait_for_timeout(9000)
        dock = "[data-testid=fts-dock]"
        closed = box(pg, dock)
        chip = box(pg, "[data-testid=fts-dock-toggle]")
        pg.screenshot(path=str(SHOTS / "dock-closed.png"))
        opened = None
        if chip:
            pg.click("[data-testid=fts-dock-toggle]")
            pg.wait_for_timeout(700)  # بعد از انیمیشنِ ۳۰ms
            opened = box(pg, dock)
        report["dock"] = {"closed": closed, "chip": chip, "opened": opened,
                          "body": box(pg, "[data-testid=fts-dock-body]")}
        pg.screenshot(path=str(SHOTS / "dock-open.png"))

        # ── ۲) نوارِ ری‌بالانس + <details> در تب پرتفوی ──────────────────────
        pg.goto(f"{BASE}/#/portfolio")
        pg.wait_for_timeout(7000)
        pills = pg.evaluate("""() => [...document.querySelectorAll('button[aria-expanded]')]
            .map(e => ({text: (e.textContent||'').trim().slice(0,44), expanded: e.getAttribute('aria-expanded'),
                        rounded: e.className.includes('rounded-full'),
                        hasChevron: !!e.querySelector('svg, .disclosure-chevron'),
                        h: Math.round(e.getBoundingClientRect().height)}))""")
        report["portfolio_pills"] = pills
        det = box(pg, "details > summary")
        report["details_summary"] = det
        if det:
            pg.click("details > summary")
            pg.wait_for_timeout(400)
            report["details_open"] = pg.evaluate("() => !!document.querySelector('details[open]')")
        pg.screenshot(path=str(SHOTS / "portfolio.png"))

        # نوارِ شکاف در تبِ «پرتفوی فعلی» است؛ دراورش هم باید باز شود
        pg.get_by_role("tab", name=re.compile("پرتفوی فعلی")).first.click()
        pg.wait_for_timeout(3000)
        by_text = """(txt) => { const el = [...document.querySelectorAll('button[aria-expanded]')]
              .find(e => (e.textContent || '').includes(txt));
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {w: Math.round(r.width), h: Math.round(r.height),
                    expanded: el.getAttribute('aria-expanded'),
                    rounded: el.className.includes('rounded-full'),
                    chevron: !!el.querySelector('svg'),
                    text: (el.textContent || '').trim().slice(0, 44)}; }"""
        panel_h = """(txt) => { const p = [...document.querySelectorAll('.glass-panel')]
                .find(e => e.textContent?.includes(txt));
            return p ? Math.round(p.getBoundingClientRect().height) : null; }"""
        d_closed = pg.evaluate(panel_h, "جزئیات ری‌بالانس")
        d_chip = pg.evaluate(by_text, "جزئیات ری‌بالانس")
        d_open = None
        if d_chip:
            pg.get_by_role("button", name=re.compile("جزئیات ری‌بالانس")).first.click()
            pg.wait_for_timeout(600)
            d_open = pg.evaluate(panel_h, "جزئیات ری‌بالانس")
        report["delta_bar"] = {"h_closed": d_closed, "chip": d_chip, "h_open": d_open}
        pg.screenshot(path=str(SHOTS / "portfolio-delta-open.png"))

        # ── ۳) نوارِ نمودارهای تابلو: ارتفاعِ بسته↔باز ──────────────────────
        pg.goto(f"{BASE}/#/market")
        pg.wait_for_timeout(9000)
        bar = "[data-testid=micro-charts-toggle]"
        h_before = pg.evaluate(
            """(sel) => { const el = document.querySelector(sel);
                const p = el?.closest('.glass-panel'); return p ? Math.round(p.getBoundingClientRect().height) : null; }""",
            bar,
        )
        hint = box(pg, "[data-testid=micro-charts-toggle-hint]")
        pg.click(bar)
        pg.wait_for_timeout(700)
        h_after = pg.evaluate(
            """(sel) => { const el = document.querySelector(sel);
                const p = el?.closest('.glass-panel'); return p ? Math.round(p.getBoundingClientRect().height) : null; }""",
            bar,
        )
        report["micro_bar"] = {"h_closed": h_before, "h_open": h_after, "hint": hint,
                               "rotate": pg.evaluate("() => !!document.querySelector('[data-testid=micro-charts-toggle] .rotate-180')")}
        pg.screenshot(path=str(SHOTS / "market-bar-open.png"))
        report["console_errors"] = errs
        b.close()

    out = Path("_audit/drop_aff_check.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=1))


if __name__ == "__main__":
    main()
