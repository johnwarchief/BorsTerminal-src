# _audit/verify2-20261010/probe1_market_status.py
# بند ۱ — سنِ داده درِ پنلِ «وضعیت بازار»: ۹۰ ثانیه بی‌هیچ کلیک/تعاملی.
# فقط خواندنِ DOM (page.evaluate) — هیچ کلیک، کیبورد یا اسکرولی انجام نمی‌شود.
import json
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"C:\Users\PCMOD\Desktop\BorsTerminal\_audit\verify2-20261010")
EXE = r"C:\Users\PCMOD\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe"
BASE = "http://127.0.0.1:8002"

READ_JS = """
() => {
  const panel = document.querySelector('[data-testid="market-status-panel"]');
  if (!panel) return null;
  const chips = Array.from(panel.querySelectorAll('span.inline-flex'))
    .map(el => {
      const lab = el.querySelector('span');
      const val = el.querySelectorAll('span')[1];
      return {
        label: lab ? lab.textContent.trim() : null,
        value: val ? val.textContent.trim() : null,
        title: (el.getAttribute('title') || '').trim(),
        testid: el.getAttribute('data-testid'),
      };
    });
  return {
    text: (panel.textContent || '').replace(/\\s+/g, ' ').trim(),
    chips,
    revision: (() => { const c = chips.find(x => x.label === 'ویرایش'); return c ? c.value : null; })(),
    dataAge: (() => { const c = chips.find(x => x.label === 'عوض‌شدنِ عدد'); return c ? c.value : null; })(),
    lastMarketData: (() => { const c = chips.find(x => x.label === 'آخرین دادهٔ بازار'); return c ? c.value : null; })(),
    marketState: (() => { const c = chips.find(x => x.label === 'بازار'); return c ? c.value : null; })(),
    connection: (() => { const c = chips.find(x => x.label === 'اتصال'); return c ? c.value : null; })(),
    hasCooldownChip: !!panel.querySelector('[data-testid="msp-cooldown"]'),
    hasRetryBtn: !!panel.querySelector('[data-testid="msp-retry"]'),
    claimsLiveness: /لحظاتی پیش|زنده|به‌روزرسانی:/.test(panel.textContent || ''),
    livenessTexts: (panel.textContent || '').match(/[^ ]*(لحظاتی پیش|زنده)[^ ]*/g) || [],
  };
}
"""


def main():
    log = {"item": 1, "started_at_local": datetime.now().isoformat(timespec="seconds"),
           "samples": [], "console_errors": [], "bad_responses": [], "notes": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=EXE)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_init_script("sessionStorage.setItem('bors_auth_session','true');")
        page = ctx.new_page()
        page.on("console", lambda m: log["console_errors"].append(m.text[:300]) if m.type == "error" else None)
        page.on("pageerror", lambda e: log["console_errors"].append("PAGEERROR " + str(e)[:300]))

        def on_resp(resp):
            try:
                if resp.status >= 400:
                    log["bad_responses"].append({"url": resp.url, "status": resp.status})
            except Exception:
                pass
        page.on("response", on_resp)

        page.goto(BASE + "/#/market", wait_until="domcontentloaded")
        page.wait_for_selector('[data-testid="market-status-panel"]', timeout=40000)
        page.wait_for_selector('[data-testid="tape-row"]', timeout=60000)
        href = page.evaluate("location.href")
        body_head = page.evaluate("() => document.body.innerText.replace(/\\s+/g,' ').slice(0,200)")
        log["href"] = href
        log["body_head"] = body_head
        log["error_boundary"] = "Unexpected Application Error" in body_head

        import time
        t0 = time.time()
        for i in range(19):  # 0s .. 90s هر ۵ ثانیه
            snap = page.evaluate(READ_JS)
            stamp = datetime.now().strftime("%H:%M:%S")
            if snap is None:
                log["samples"].append({"t_s": round(time.time() - t0), "clock": stamp, "panel": None})
            else:
                log["samples"].append({
                    "t_s": round(time.time() - t0), "clock": stamp,
                    "data_age": snap["dataAge"], "last_market_data": snap["lastMarketData"],
                    "market": snap["marketState"], "connection": snap["connection"],
                    "revision": snap["revision"],
                    "chips": [{"label": c["label"], "value": c["value"]} for c in snap["chips"]],
                    "panel_text": snap["text"],
                    "cooldown_chip": snap["hasCooldownChip"], "retry_btn": snap["hasRetryBtn"],
                    "claims_liveness": snap["claimsLiveness"],
                    "data_age_title": next((c["title"] for c in snap["chips"] if c["label"] == "عوض‌شدنِ عدد"), None),
                    "last_data_title": next((c["title"] for c in snap["chips"] if c["label"] == "آخرین دادهٔ بازار"), None),
                })
            if i == 0:
                page.screenshot(path=str(OUT / "01_market_t0.png"))
            if i == 15:
                page.screenshot(path=str(OUT / "01_market_t75.png"))
            if i == 18:
                page.screenshot(path=str(OUT / "01_market_t90.png"))
            if i < 18:
                time.sleep(max(0.0, 5.0 - (time.time() - t0 - i * 5)))

        # جمع‌شدنِ پنلِ باز هم فقط با خواندن است (کلیکِ مپس فقط برایِ دیدنِ جزئیات)
        page.screenshot(path=str(OUT / "01_market_final.png"), full_page=False)
        # جزئیاتِ بازِ پنل (یک کلیک، بعد از پایان دورۀ بی‌دست‌کاری)
        page.click('[data-testid="msp-toggle"]')
        page.wait_for_timeout(800)
        log["expanded_text"] = page.evaluate(
            "() => { const el=document.querySelector('[data-testid=\"market-status-panel\"]');"
            " return el ? (el.textContent||'').replace(/\\s+/g,' ').trim() : null; }")
        page.screenshot(path=str(OUT / "02_market_expanded.png"))
        # زندهٔ بک‌اند درِ همان لحظه
        try:
            log["live_stats"] = page.evaluate(
                "async () => (await (await fetch('/api/live-stats')).json())")
        except Exception as e:
            log["live_stats_error"] = str(e)[:200]
        log["ended_at_local"] = datetime.now().isoformat(timespec="seconds")
        browser.close()
    (OUT / "probe1_result.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    ages = [(s["t_s"], s.get("data_age"), s.get("last_market_data")) for s in log["samples"]]
    print(json.dumps({"href": log["href"], "err_boundary": log["error_boundary"],
                      "samples": ages, "console_errors": log["console_errors"][:5],
                      "bad": log["bad_responses"][:10]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
