# _audit/verify2-20261010/probe4_presets.py
# بند ۴ — سوییچِ پریست با کلیک (بی‌رفرشِ دستی): نوسان‌گیر ← روندگیر ← Custom
# برایِ هر پریست: خطِ شمارشِ مرحلۀ تابلو، سه ردیفِ اول، چیپِ «محاسبه: HH:MM»
# و تقابلِ شمارها با POST /api/funnelِ همان درخواستِ UI (بدنه‌یِ واقعیِ فرستاده‌شده).
import json
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"C:\Users\PCMOD\Desktop\BorsTerminal\_audit\verify2-20261010")
EXE = r"C:\Users\PCMOD\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe"
BASE = "http://127.0.0.1:8002"

SNAP_JS = """
() => {
  const t = (sel) => { const el = document.querySelector(sel); return el ? (el.textContent||'').replace(/\\s+/g,' ').trim() : null; };
  const rows = Array.from(document.querySelectorAll('[data-testid="tape-row"]')).slice(0,3).map(r => {
    const cell = r.children[0];
    const tn = Array.from(cell ? cell.childNodes : []).filter(n => n.nodeType === 3).map(n => n.textContent.trim()).filter(Boolean);
    return { symbol: tn[0] || null, text: (r.textContent||'').replace(/\\s+/g,' ').trim().slice(0,190) };
  });
  const tabs = Array.from(document.querySelectorAll('[role="tab"], [data-testid^="funnel-stage-"]')).map(e => ({
    testid: e.getAttribute('data-testid'), text: (e.textContent||'').replace(/\\s+/g,' ').trim().slice(0,60) }));
  return {
    url: location.href,
    stage_count_tape: t('[data-testid="fts-stage-count-tape"]'),
    stage_count_header: t('[data-testid="fts-stage-count"]'),
    as_of: t('[data-testid="funnel-as-of"]'),
    as_of_present: !!document.querySelector('[data-testid="funnel-as-of"]'),
    tape_freshness: t('[data-testid="funnel-tape-freshness"]'),
    calc_state: t('[data-testid="funnel-calc-state"]'),
    active_mode: (() => { const b = document.querySelector('[data-testid^="funnel-mode-"][aria-pressed="true"]'); return b ? { testid: b.getAttribute('data-testid'), text: b.textContent.trim() } : null; })(),
    rows, tabs,
    workspace_text: (document.querySelector('[data-testid="fts-funnel-workspace"]')?.textContent || '').replace(/\\s+/g,' ').trim().slice(0, 700),
  };
}
"""


def main():
    log = {"item": 4, "started_at_local": datetime.now().isoformat(timespec="seconds"),
           "console_errors": [], "bad_responses": [], "funnel_calls": [], "presets": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=EXE)
        ctx = browser.new_context(viewport={"width": 1600, "height": 950})
        ctx.add_init_script("sessionStorage.setItem('bors_auth_session','true');")
        page = ctx.new_page()
        page.on("console", lambda m: log["console_errors"].append(m.text[:300]) if m.type == "error" else None)
        page.on("pageerror", lambda e: log["console_errors"].append("PAGEERROR " + str(e)[:300]))
        pending = {}

        def on_req(req):
            if "/api/funnel" in req.url and req.method == "POST":
                pending[req] = datetime.now().strftime("%H:%M:%S")

        def on_resp(resp):
            if "/api/funnel" in resp.url:
                body = None
                try:
                    if resp.request.method == "POST":
                        body = resp.request.post_data
                except Exception:
                    pass
                rec = {"at_local": pending.pop(resp.request, datetime.now().strftime("%H:%M:%S")),
                       "method": resp.request.method, "url": resp.url[:120], "status": resp.status,
                       "req_body": None}
                if body:
                    try:
                        rec["req_body"] = json.loads(body)
                    except Exception:
                        rec["req_body_raw"] = body[:300]
                log["funnel_calls"].append(rec)
        page.on("request", on_req)
        page.on("response", on_resp)

        def on_fail(f):
            if f.status and f.status >= 400:
                log["bad_responses"].append({"url": f.url[:160], "status": f.status})
        page.on("requestfailed", on_fail)

        page.goto(BASE + "/#/master?stage=tape&preset=swing", wait_until="domcontentloaded")
        page.wait_for_selector('[data-testid="fts-funnel-workspace"]', timeout=60000)
        page.wait_for_selector('[data-testid="tape-row"]', timeout=120000)
        page.wait_for_timeout(2500)

        seq = [("swing", "funnel-mode-swing"), ("trend", "funnel-mode-trend"), ("custom", "funnel-mode-custom")]
        for i, (key, tid) in enumerate(seq):
            if i > 0:
                page.click(f'[data-testid="{tid}"]')
                # صبر تا شمارشِ مرحله ثبات/findشود (پاسخِ تازه برسد)
                try:
                    page.wait_for_function(
                        """() => { const el=document.querySelector('[data-testid="funnel-as-of"]');
                                   return !!el && /محاسبه/.test(el.textContent||''); }""", timeout=60000)
                except Exception:
                    pass
                page.wait_for_timeout(3500)
            snap = page.evaluate(SNAP_JS)
            snap["preset_clicked"] = key
            snap["click_local"] = datetime.now().strftime("%H:%M:%S")
            log["presets"].append(snap)
            page.screenshot(path=str(OUT / f"09_preset_{key}.png"))
        log["ended_at_local"] = datetime.now().isoformat(timespec="seconds")
        log["api"] = {}
        browser.close()

    # تقابل با POST /api/funnelِ همان بدنه‌هایِ UI
    import urllib.request
    seen = {}
    for c in log["funnel_calls"]:
        if c["method"] == "POST" and c.get("req_body"):
            seen[json.dumps(c["req_body"], sort_keys=True, ensure_ascii=False)] = c["req_body"]
    for k, b in seen.items():
        try:
            req = urllib.request.Request(BASE + "/api/funnel", data=json.dumps(b).encode("utf-8"),
                                         headers={"Content-Type": "application/json"}, method="POST")
            d = json.loads(urllib.request.urlopen(req, timeout=240).read())
            summ = {}
            for st, v in (d.get("stages") or {}).items():
                summ[st] = {"input": v.get("input"), "matched": v.get("matched"), "removed": v.get("removed")}
            log["api"][k] = {"as_of": d.get("as_of"), "preset": d.get("preset"), "universe": d.get("universe"),
                             "stages": summ, "handover": d.get("handover") if isinstance(d.get("handover"), dict) else None,
                             "counts": d.get("counts")}
        except Exception as e:
            log["api"][k] = {"error": str(e)[:200]}
    (OUT / "probe4_result.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"presets": [{k: p.get(k) for k in ("preset_clicked", "click_local", "url", "active_mode",
                                                          "stage_count_tape", "as_of", "tape_freshness", "rows")}
                                 for p in log["presets"]],
                      "calls": [{"at": c["at_local"], "status": c["status"], "body": c.get("req_body")} for c in log["funnel_calls"]],
                      "api_keys": list(log["api"]), "errors": log["console_errors"][:8],
                      "bad": log["bad_responses"][:8]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
