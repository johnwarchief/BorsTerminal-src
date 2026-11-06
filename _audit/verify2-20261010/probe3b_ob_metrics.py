# _audit/verify2-20261010/probe3b_ob_metrics.py
# بند ۳ (اندازۀ دقیق): در RTL همسایه‌ها از راست به چپ می‌چیند؛ پس:
#  - فاصلۀ دو اسپنِ مجاور = prev.left - cur.right  (منفی ⇒ هم‌پوشانی)
#  - بیرون‌زدگی از جعبۀ سطر = cur.left < li.left+pad یا cur.right > li.right-pad
#  - li در CSS `overflow-hidden` دارد ⇒ بیرون‌زدگی = بریدگیِ دیدنی
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
  if (!panel || !rows) return { present: false };
  const out = { present: true, symbol: panel.getAttribute('data-symbol'),
                panel: { sw: panel.scrollWidth, cw: panel.clientWidth, w: +panel.getBoundingClientRect().width.toFixed(2) },
                grid: { sw: rows.scrollWidth, cw: rows.clientWidth, w: +rows.getBoundingClientRect().width.toFixed(2),
                        cols: getComputedStyle(rows).gridTemplateColumns,
                        colW: rows.children.length ? Array.from(rows.children).map(c => +c.getBoundingClientRect().width.toFixed(2)) : null },
                row_list: [] };
  for (const ul of rows.children) {
    const side = ul === rows.firstElementChild ? 'demand(تقاضا)' : 'supply(عرضه)';
    Array.from(ul.querySelectorAll('li')).forEach((li, i) => {
      const lr = li.getBoundingClientRect();
      const spans = Array.from(li.querySelectorAll('span.num'));
      const cs = getComputedStyle(li);
      const padS = parseFloat(cs.paddingLeft) || 0, padE = parseFloat(cs.paddingRight) || 0;
      const cells = spans.map(s => {
        const r = s.getBoundingClientRect();
        return { text: (s.textContent || '').trim(), w: +r.width.toFixed(2),
                 left: +r.left.toFixed(2), right: +r.right.toFixed(2),
                 sw: s.scrollWidth, cw: s.clientWidth };
      });
      const gaps = [];
      for (let k = 1; k < cells.length; k++) {
        // cells[k-1] در RTL سمت راستِ cells[k] است
        gaps.push(+(cells[k - 1].left - cells[k].right).toFixed(2));
      }
      const leftOut = +Math.max(0, (lr.left + padE) - Math.min(...cells.map(c => c.left))).toFixed(2);
      const rightOut = +Math.max(0, Math.max(...cells.map(c => c.right)) - (lr.right - padS)).toFixed(2);
      out.row_list.push({ side, i, li_w: +lr.width.toFixed(2), li_sw: li.scrollWidth, li_cw: li.clientWidth,
                          cells, gaps, clipped_left_px: leftOut, clipped_right_px: rightOut,
                          text: (li.textContent || '').replace(/\\s+/g,' ').trim().slice(0, 60) });
    });
  }
  out.rowClips = out.row_list.filter(r => r.li_sw > r.li_cw + 0.5);
  out.overlaps = out.row_list.filter(r => r.gaps.some(g => g < 0));
  out.bleeds = out.row_list.filter(r => r.clipped_left_px > 0.5 || r.clipped_right_px > 0.5);
  out.cell_self_clip = out.row_list.flatMap(r => r.cells.filter(c => c.sw > c.cw + 0.5)
      .map(c => ({ side: r.side, i: r.i, text: c.text, sw: c.sw, cw: c.cw })));
  const se = document.scrollingElement;
  out.docOverflowX = se ? se.scrollWidth - se.clientWidth : null;
  return out;
}
"""


def main():
    log = {"item": "3b", "started_at_local": datetime.now().isoformat(timespec="seconds"),
          "console_errors": [], "bad_responses": [], "measure": {}}
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

        def read_rows():
            return page.evaluate("() => Array.from(document.querySelectorAll('[data-testid^=\"watch-row-\"]')).map(e=>e.getAttribute('data-testid'))")

        rows = []
        deadline = time.time() + 60
        while time.time() < deadline:
            rows = read_rows()
            if len(rows) >= 1:
                break
            time.sleep(2)
        log["rows_after_wait"] = rows
        if len(rows) < 3:
            for sym in ["شپنا", "فولاد", "خساپ"]:
                if any(sym in r for r in rows):
                    continue
                try:
                    page.fill('[data-testid="watch-add-input"]', sym, timeout=8000)
                    page.wait_for_timeout(700)
                    page.click('[data-testid="watch-add-btn"]', timeout=8000)
                    page.wait_for_timeout(1200)
                except Exception as e:
                    log.setdefault("add_errors", []).append(f"{sym}: {str(e)[:160]}")
            rows = read_rows()
        log["watch_rows"] = rows
        if not rows:
            log["body_text"] = page.evaluate("() => document.body.innerText.replace(/\\s+/g,' ').slice(0,600)")
        page.wait_for_timeout(2000)
        rows = page.evaluate("() => Array.from(document.querySelectorAll('[data-testid^=\"watch-row-\"]')).map(e=>e.getAttribute('data-testid'))")
        log["watch_rows"] = rows
        for w, h in [(1366, 768), (1280, 720), (1920, 1080)]:
            page.set_viewport_size({"width": w, "height": h})
            page.wait_for_timeout(1200)
            per = {}
            for tid in rows[:3]:
                page.click(f'[data-testid="{tid}"]')
                page.wait_for_timeout(9000)
                sym = tid.replace("watch-row-", "")
                m = page.evaluate(MEASURE_JS)
                per[sym] = m
                if w == 1366:
                    page.screenshot(path=str(OUT / f"06_ob_1366_{sym}.png"))
                elif w == 1280:
                    page.screenshot(path=str(OUT / f"07_ob_1280_{sym}.png"))
                else:
                    page.screenshot(path=str(OUT / f"08_ob_1920_{sym}.png"))
            log["measure"][f"{w}x{h}"] = per
        log["ended_at_local"] = datetime.now().isoformat(timespec="seconds")
        browser.close()
    (OUT / "probe3b_result.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, per in log["measure"].items():
        print("==", k)
        for sym, m in per.items():
            if not m.get("present"):
                print("  ", sym, "بدون ردیفِ عمق (پنل خالی)")
                continue
            print("   ", sym, "panel sw/cw", m["panel"]["sw"], m["panel"]["cw"],
                  "| grid sw/cw", m["grid"]["sw"], m["grid"]["cw"], "| cols", m["grid"]["colW"],
                  "| rows", len(m["row_list"]),
                  "| overlaps", len(m["overlaps"]), "| bleeds", len(m["bleeds"]),
                  "| rowClips", len(m["rowClips"]), "| selfClip", len(m["cell_self_clip"]),
                  "| docOverflowX", m["docOverflowX"])
            worst = sorted(m["row_list"], key=lambda r: min(r["gaps"]) if r["gaps"] else 99)[:3]
            for r in worst:
                print("      min gap", min(r["gaps"]) if r["gaps"] else None, "| bleedL", r["clipped_left_px"],
                      "| bleedR", r["clipped_right_px"], "|", r["text"])
    print("errors", log["console_errors"][:6], "bad", log["bad_responses"][:6])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
