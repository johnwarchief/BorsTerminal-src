# _audit/verify2-20261010/probe3_watch_widths.py
# بند ۳ — «دیده‌بان بازار» در عرضِ باریک: بریدگیِ ارقامِ عمقِ پنج‌سطحی + سوییچِ سه پنل
import json
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"C:\Users\PCMOD\Desktop\BorsTerminal\_audit\verify2-20261010")
EXE = r"C:\Users\PCMOD\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe"
BASE = "http://127.0.0.1:8002"

MEASURE_JS = """
() => {
  const panel = document.querySelector('[data-testid="watch-orderbook"]');
  const rows = document.querySelector('[data-testid="watch-orderbook-rows"]');
  const cellClips = [];
  let rowClips = [];
  if (rows) {
    for (const li of rows.querySelectorAll('li')) {
      const rec = { sw: li.scrollWidth, cw: li.clientWidth,
                    w: Math.round(li.getBoundingClientRect().width),
                    text: (li.textContent || '').replace(/\\s+/g,' ').trim().slice(0,60) };
      if (rec.sw > rec.cw + 0.5) rowClips.push(rec);
      for (const sp of li.querySelectorAll('span.num')) {
        const r = sp.getBoundingClientRect();
        const rn = li.getBoundingClientRect();
        const over = sp.scrollWidth > sp.clientWidth + 0.5;
        // بیرون‌زدگی از لبۀ سطر (قیمت+حجم به هم می‌چسبند / از ستون رد می‌شوند)
        const bleedRight = r.right - rn.right;
        const bleedLeft = rn.left - r.left;
        const overlapPrev = (() => {
          const prev = sp.previousElementSibling;
          if (!prev) return null;
          const p = prev.getBoundingClientRect();
          return +(p.right - r.left).toFixed(2);   // >0 یعنی هم‌پوشانی
        })();
        if (over || Math.abs(bleedRight) > 0.5 || Math.abs(bleedLeft) > 0.5 || (overlapPrev && overlapPrev > 0.5)) {
          cellClips.push({ text: (sp.textContent || '').trim(), over, bleedRight: +bleedRight.toFixed(2),
                           bleedLeft: +bleedLeft.toFixed(2), overlapPrev, sw: sp.scrollWidth, cw: sp.clientWidth });
        }
      }
    }
  }
  const all = document.querySelectorAll('*');
  let docOverflow = 0;
  if (document.scrollingElement) docOverflow = document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth;
  const grid = rows ? getComputedStyle(rows.parentElement).gridTemplateColumns : null;
  return {
    viewport: { w: innerWidth, h: innerHeight },
    panel: panel ? { sw: panel.scrollWidth, cw: panel.clientWidth,
                     rect: Math.round(panel.getBoundingClientRect().width),
                     symbol: panel.getAttribute('data-symbol'),
                     text: (panel.textContent || '').replace(/\\s+/g,' ').trim().slice(0,220) } : null,
    rows: rows ? { sw: rows.scrollWidth, cw: rows.clientWidth, n_li: rows.querySelectorAll('li').length } : null,
    gridCols: grid,
    rowClips, cellClips,
    docOverflowX: docOverflow,
    totalEls: all.length,
  };
}
"""

PANEL_STATE_JS = """
() => {
  const g = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    return { symbol: el.getAttribute('data-symbol'),
             text: (el.textContent || '').replace(/\\s+/g,' ').trim().slice(0,160),
             canvas: !!el.querySelector('canvas') };
  };
  return {
    chart: g('[data-testid="watch-chart"]'),
    ob: g('[data-testid="watch-orderbook"]'),
    sum: g('[data-testid="watch-summary"]'),
    feedAge: (document.querySelector('[data-testid="watch-feed-age"]')?.textContent || '').replace(/\\s+/g,' ').trim(),
    clickedRow: (() => { const a = document.querySelector('[data-testid^="watch-row-"][aria-current], [data-testid^="watch-row-"].bg-accent-blue, [data-testid^="watch-row-"][data-selected]'); return a ? a.getAttribute('data-testid') : null; })(),
  };
}
"""


def main():
    log = {"item": 3, "started_at_local": datetime.now().isoformat(timespec="seconds"),
           "console_errors": [], "bad_responses": [], "widths": {}, "clicks": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=EXE)
        ctx = browser.new_context(viewport={"width": 1600, "height": 900})
        ctx.add_init_script("sessionStorage.setItem('bors_auth_session','true');")
        page = ctx.new_page()
        page.on("console", lambda m: log["console_errors"].append(m.text[:300]) if m.type == "error" else None)
        page.on("pageerror", lambda e: log["console_errors"].append("PAGEERROR " + str(e)[:300]))

        def on_resp(resp):
            if resp.status >= 400:
                log["bad_responses"].append({"url": resp.url[:160], "status": resp.status})
        page.on("response", on_resp)

        page.goto(BASE + "/#/portfolio", wait_until="domcontentloaded")
        page.wait_for_selector('[data-testid="portfolio-section-watch"]', timeout=40000)
        page.click('[data-testid="portfolio-section-watch"]')
        page.wait_for_timeout(2500)
        log["href"] = page.evaluate("location.href")
        ids = page.evaluate("() => Array.from(document.querySelectorAll('[data-testid^=\"watch-row-\"]')).map(e => e.getAttribute('data-testid'))")
        log["watch_rows_present"] = ids
        if len(ids) < 3:
            for sym in ["شپنا", "فولاد", "خساپ"]:
                if not any(sym in i for i in ids):
                    try:
                        page.fill('[data-testid="watch-add-input"]', sym, timeout=5000)
                        page.wait_for_timeout(500)
                        page.click('[data-testid="watch-add-btn"]', timeout=5000)
                        page.wait_for_timeout(900)
                    except Exception as e:
                        log.setdefault("add_errors", []).append(f"{sym}: {str(e)[:120]}")
            ids = page.evaluate("() => Array.from(document.querySelectorAll('[data-testid^=\"watch-row-\"]')).map(e => e.getAttribute('data-testid'))")
            log["watch_rows_after_add"] = ids
        log["subtab_text"] = page.evaluate(
            "() => { const b=document.querySelector('[data-testid=\"portfolio-section-watch\"]');"
            " return b ? (b.textContent||'').replace(/\\s+/g,' ').trim() : null; }")

        for w, h in [(1600, 900), (1366, 768), (1280, 720)]:
            page.set_viewport_size({"width": w, "height": h})
            page.wait_for_timeout(1500)
            m = page.evaluate(MEASURE_JS)
            m["state"] = page.evaluate(PANEL_STATE_JS)
            log["widths"][f"{w}x{h}"] = m
            page.screenshot(path=str(OUT / f"04_watch_{w}x{h}.png"))

        # سه نماد: کلیک و سوییچِ هر سه پنل (در 1366×768)
        page.set_viewport_size({"width": 1366, "height": 768})
        page.wait_for_timeout(1000)
        rows3 = page.evaluate("() => Array.from(document.querySelectorAll('[data-testid^=\"watch-row-\"]')).map(e => ({t:e.getAttribute('data-testid'), text:(e.textContent||'').replace(/\\s+/g,' ').trim().slice(0,60)}))")
        for r in rows3[:3]:
            page.click(f'[data-testid="{r["t"]}"]')
            page.wait_for_timeout(13000)
            st = page.evaluate(PANEL_STATE_JS)
            meas = page.evaluate(MEASURE_JS)
            log["clicks"].append({"row": r, "state": st,
                                  "panel_cw": meas["panel"]["cw"] if meas.get("panel") else None,
                                  "panel_sw": meas["panel"]["sw"] if meas.get("panel") else None,
                                  "cellClips": meas["cellClips"], "rowClips": meas["rowClips"],
                                  "ob_text": meas["panel"]["text"] if meas.get("panel") else None,
                                  "rows": meas.get("rows")})
            safe = r["t"].replace("watch-row-", "").replace("/", "_")
            page.screenshot(path=str(OUT / f"05_watch_click1366_{safe}.png"))
        log["ended_at_local"] = datetime.now().isoformat(timespec="seconds")
        browser.close()
    (OUT / "probe3_result.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: {kk: log["widths"][k].get(kk) for kk in ("viewport", "panel", "rows", "gridCols", "docOverflowX", "rowClips", "cellClips")}
                      for k in log["widths"]}, ensure_ascii=False, indent=1))
    print(json.dumps({"subtab": log.get("subtab_text"), "rows": log.get("watch_rows_present"),
                      "after": log.get("watch_rows_after_add"), "add_errors": log.get("add_errors"),
                      "clicks": [{"row": c["row"]["t"], "chart": c["state"]["chart"], "ob_sym": c["state"]["ob"],
                                  "sum": c["state"]["sum"], "clips": len(c["cellClips"])} for c in log["clicks"]],
                      "errors": log["console_errors"][:8], "bad": log["bad_responses"][:10]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
