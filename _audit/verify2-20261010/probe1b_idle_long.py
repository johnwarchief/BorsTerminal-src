# _audit/verify2-20261010/probe1b_idle_long.py
# بند ۱ (دورۀ بلند): ۴۲۰ ثانیه بی‌هیچ تعاملی — تا پولینگِ بازارِ بسته
# (CLOSED_POLL_MS = ۵ دقیقه) یک دور بزند و `rev_at`ِ کلاینت واقعاً عدد شود؛
# بعد همان عدد باید با ساعتِ ۱۵ ثانیه‌ایِ پنل جلو برود.
import json
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"C:\Users\PCMOD\Desktop\BorsTerminal\_audit\verify2-20261010")
EXE = r"C:\Users\PCMOD\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe"
BASE = "http://127.0.0.1:8002"
WINDOW_S = 420
STEP_S = 10

READ_JS = """
() => {
  const panel = document.querySelector('[data-testid="market-status-panel"]');
  if (!panel) return null;
  const chips = Array.from(panel.querySelectorAll('span.inline-flex')).map(el => {
    const spans = el.querySelectorAll('span');
    return {
      label: spans[0] ? spans[0].textContent.trim() : null,
      value: spans[1] ? spans[1].textContent.trim() : null,
      title: (el.getAttribute('title') || '').trim(),
    };
  });
  const pick = (l) => chips.find(c => c.label === l) || null;
  return {
    text: (panel.textContent || '').replace(/\\s+/g, ' ').trim(),
    data_age: pick('عوض‌شدنِ عدد'),
    last_market_data: pick('آخرین دادهٔ بازار'),
    market: pick('بازار'),
    connection: pick('اتصال'),
    revision: pick('ویرایش'),
    claims_liveness: /لحظاتی پیش|زنده/.test(panel.textContent || ''),
    topbar: (() => {
      const t = document.querySelector('[data-testid="feed-status"], [data-testid="topbar-feed-status"]');
      return t ? (t.textContent || '').replace(/\\s+/g, ' ').trim() : null;
    })(),
  };
}
"""


def main():
    log = {"item": "1b", "started_at_local": datetime.now().isoformat(timespec="seconds"),
           "samples": [], "market_requests": [], "console_errors": [], "bad_responses": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=EXE)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_init_script("sessionStorage.setItem('bors_auth_session','true');")
        page = ctx.new_page()
        page.on("console", lambda m: log["console_errors"].append(m.text[:300]) if m.type == "error" else None)
        page.on("pageerror", lambda e: log["console_errors"].append("PAGEERROR " + str(e)[:300]))

        def on_resp(resp):
            u = resp.url
            if "/api/market" in u:
                log["market_requests"].append({
                    "at_local": datetime.now().strftime("%H:%M:%S"), "url": u[:120],
                    "status": resp.status, "size": len(resp.body() or b""),
                })
            elif resp.status >= 400:
                log["bad_responses"].append({"url": u[:160], "status": resp.status})
        page.on("response", on_resp)

        page.goto(BASE + "/#/market", wait_until="domcontentloaded")
        page.wait_for_selector('[data-testid="market-status-panel"]', timeout=40000)
        page.wait_for_selector('[data-testid="tape-row"]', timeout=90000)
        log["href"] = page.evaluate("location.href")
        t0 = time.time()
        shot_age_first = False
        while True:
            el = time.time() - t0
            snap = page.evaluate(READ_JS)
            rec = {"t_s": round(el), "clock": datetime.now().strftime("%H:%M:%S")}
            if snap:
                rec.update({
                    "data_age": (snap["data_age"] or {}).get("value"),
                    "data_age_title": (snap["data_age"] or {}).get("title"),
                    "last_market_data": (snap["last_market_data"] or {}).get("value"),
                    "last_market_title": (snap["last_market_data"] or {}).get("title"),
                    "market": (snap["market"] or {}).get("value"),
                    "connection": (snap["connection"] or {}).get("value"),
                    "conn_title": (snap["connection"] or {}).get("title"),
                    "revision": (snap["revision"] or {}).get("value"),
                    "claims_liveness": snap["claims_liveness"],
                    "panel_text": snap["text"],
                })
            log["samples"].append(rec)
            if rec.get("data_age") not in (None, "نامعلوم") and not shot_age_first:
                page.screenshot(path=str(OUT / "01b_age_becomes_numeric.png"))
                shot_age_first = True
            if el >= WINDOW_S:
                break
            time.sleep(max(0.5, STEP_S - (time.time() - t0 - round(el))))
        page.screenshot(path=str(OUT / "01b_market_idle_end.png"))
        log["ended_at_local"] = datetime.now().isoformat(timespec="seconds")
        log["delta_poll_count"] = sum(1 for r in log["market_requests"] if "/api/market/delta" in r["url"])
        log["full_body_count"] = sum(1 for r in log["market_requests"] if r["url"].rstrip().endswith("/api/market"))
        browser.close()
    (OUT / "probe1b_result.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({
        "href": log["href"], "samples": [(s["t_s"], s["clock"], s.get("data_age"), s.get("last_market_data"), s.get("conn_title")) for s in log["samples"]],
        "market_requests": log["market_requests"], "console_errors": log["console_errors"][:8],
        "bad": log["bad_responses"][:10]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    main()
