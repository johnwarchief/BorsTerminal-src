# _audit/verify2-20261010/probe2_indicators.py
# بند ۲ — ردپایِ I1..I5 در «در یک نگاه»: سه نماد از جدولِ تابلو، عینِ رندرِ رابط.
import json
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"C:\Users\PCMOD\Desktop\BorsTerminal\_audit\verify2-20261010")
EXE = r"C:\Users\PCMOD\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe"
BASE = "http://127.0.0.1:8002"

ROWS_JS = """
() => Array.from(document.querySelectorAll('[data-testid="tape-row"]')).slice(0, 80).map((r, i) => {
  const cell = r.children[0];
  // نماد = نخستین گره متنیِ مستقیمِ ستونِ اول (بعد از جعبه و ستاره)
  const tn = Array.from(cell ? cell.childNodes : [])
    .filter(n => n.nodeType === 3).map(n => n.textContent.trim()).filter(Boolean);
  const nameSpan = cell ? cell.querySelector('span.truncate') : null;
  return { idx: i, symbol: tn.length ? tn[0] : null,
           name: nameSpan ? nameSpan.textContent.trim() : null,
           raw: (cell ? cell.textContent : '').replace(/\\s+/g,' ').trim().slice(0,60) };
})
"""

IND_JS = """
() => {
  const wrap = document.querySelector('[data-testid="inspector-i1-i5"]');
  const aside = document.querySelector('[data-shell="inspector"]');
  const chips = wrap ? Array.from(wrap.querySelectorAll('[data-testid^="inspector-ind-"]')).map(el => ({
    testid: el.getAttribute('data-testid'),
    label: (el.children[0]?.textContent || '').trim(),
    value: (el.children[1]?.textContent || '').trim(),
    title: (el.getAttribute('title') || '').trim(),
    cls: el.className,
  })) : null;
  const header = aside ? (aside.querySelector('div.truncate.text-xs')?.textContent || '').trim() : null;
  return {
    header_symbol: header,
    glance_tab_active: document.querySelector('[data-testid="inspector-tab-glance"]')?.getAttribute('aria-current') || null,
    trend: (document.querySelector('[data-testid="inspector-trend"]')?.textContent || '').replace(/\\s+/g,' ').trim(),
    chips,
    wrap_text: wrap ? (wrap.textContent || '').replace(/\\s+/g, ' ').trim() : null,
    no_data_any: wrap ? /بدون داده|داده نیست|لازم نبود|هنوز|بی‌داده/.test(wrap.textContent || '') : null,
    aside_text_head: aside ? (aside.textContent || '').replace(/\\s+/g,' ').trim().slice(0, 900) : null,
  };
}
"""


def norm_sym(t):
    """ستونِ نمادِ ردیف: '[جعبه][ستاره]نماد نام' → first token after the checkbox/star."""
    t = t.strip()
    return t.split(" ")[0] if t else None


def main():
    log = {"item": 2, "started_at_local": datetime.now().isoformat(timespec="seconds"),
           "console_errors": [], "bad_responses": [], "symbols": [], "reads": []}
    screener = json.loads((OUT / "api_screener.json").read_text(encoding="utf-8"))
    scr_by_sym = {r["symbol"]: r for r in screener["data"]}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=EXE)
        ctx = browser.new_context(viewport={"width": 1600, "height": 950})
        ctx.add_init_script("sessionStorage.setItem('bors_auth_session','true');")
        page = ctx.new_page()
        page.on("console", lambda m: log["console_errors"].append(m.text[:300]) if m.type == "error" else None)
        page.on("pageerror", lambda e: log["console_errors"].append("PAGEERROR " + str(e)[:300]))

        def on_resp(resp):
            if resp.status >= 400:
                log["bad_responses"].append({"url": resp.url[:160], "status": resp.status})
        page.on("response", on_resp)

        page.goto(BASE + "/#/market", wait_until="domcontentloaded")
        page.wait_for_selector('[data-testid="tape-row"]', timeout=90000)
        page.wait_for_timeout(4000)
        log["href"] = page.evaluate("location.href")
        rows = page.evaluate(ROWS_JS)
        log["board_rows"] = rows
        cands = []
        seen = set()
        for r in rows:
            s = r.get("symbol")
            if s and s not in seen and s in scr_by_sym:
                seen.add(s)
                cands.append(s)
            if len(cands) >= 6:
                break
        # سه نمادِ اولِ جدول که درِ جامعۀ غربالگری هم هستند (تا مقایسه معنا داشته باشد)
        picked = cands[:3]
        log["picked"] = picked
        log["picked_reason"] = "سه نمادِ اولِ صفِ جدولِ تابلو که در /api/screener هم ردیف دارند"
        for sym in picked:
            # ردیفِ همان نماد را پیدا و کلیک کن
            row = page.locator('[data-testid="tape-row"]', has_text=sym).first
            row.click(timeout=15000)
            page.wait_for_timeout(1200)
            try:
                page.click('[data-testid="inspector-tab-glance"]', timeout=4000)
            except Exception:
                pass
            page.wait_for_timeout(2500)
            read = page.evaluate(IND_JS)
            read["symbol_clicked"] = sym
            read["api"] = {k: scr_by_sym[sym].get(k) for k in
                           ["rev_growth", "eps_last", "gross_margin", "sales_to_mcap", "pricing_mode",
                            "annualize_months", "assembly_date", "i1_na", "i2_na", "i3_na", "i4_na",
                            "i1_pass", "i2_pass", "i3_pass", "i4_pass", "i5_pass", "verdict", "name"]}
            read["api_top_level_as_of"] = screener["as_of"]
            # ردیفِ اولِ جدول برایِ ثباتِ ترتیب
            read["first_board_row"] = (page.locator('[data-testid="tape-row"]').first.inner_text() or "").replace("\n", " ")[:120]
            log["reads"].append(read)
            safe = sym.replace("/", "_")
            page.screenshot(path=str(OUT / f"03_glance_{safe}.png"))
        browser.close()
    log["ended_at_local"] = datetime.now().isoformat(timespec="seconds")
    (OUT / "probe2_result.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"picked": log["picked"],
                      "reads": [{"sym": r["symbol_clicked"], "header": r["header_symbol"],
                                 "chips": [(c["label"], c["value"]) for c in (r["chips"] or [])],
                                 "api": {k: r["api"][k] for k in ["rev_growth", "eps_last", "gross_margin", "sales_to_mcap", "pricing_mode"]}}
                                for r in log["reads"]],
                      "console_errors": log["console_errors"][:8], "bad": log["bad_responses"][:10]},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
