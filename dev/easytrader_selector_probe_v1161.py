#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""easytrader_selector_probe_v1161 — read-only DOM diagnostic.

اگر browser hostِ مالک در دسترس باشد، فقط selector count/visible/enabled را
می‌خواند؛ هیچ کلیک، fill، submit یا navigation انجام نمی‌شود. اگر host نباشد
صریح NO_ACCESS می‌دهد و candidateهایِ مرجع را VERIFIED علامت نمی‌زند.
"""
from __future__ import annotations

import json
import os
import sys
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CANDIDATES = {
    "buy_open": "[data-cy='order-buy-btn']",
    "sell_open": "[data-cy='order-sell-btn']",
    "buy_submit": "[data-cy='oms-order-form-submit-button-buy']",
    "sell_submit": "[data-cy='oms-order-form-submit-button-sell']",
    "header": "order-form-header",
    "symbol_name": "[data-cy='order-form-header-symbol-name']",
    "price": "[data-cy='order-form-input-price']",
    "quantity": "[data-cy='order-form-input-quantity']",
    "side": "[data-cy='order-form-header-side']",
}


def main() -> int:
    import execution_browser as EB
    cdp = EB.active_cdp_url()
    if not cdp:
        print(json.dumps({
            "access": "NO_ACCESS",
            "reason": "no owner browser-host CDP URL",
            "verified": [],
            "candidates": CANDIDATES,
            "source": "candidates from third-party reference/source; UNVERIFIED",
        }, ensure_ascii=False, indent=2))
        print("SELECTOR PROBE SKIP (NO_ACCESS)")
        return 0
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:                       # noqa: BLE001
        print(json.dumps({"access": "NO_PLAYWRIGHT", "error": type(e).__name__}))
        return 0
    out: dict = {"access": "HOST", "pages": [], "verified": [],
                 "candidates": CANDIDATES}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(cdp)
            for ctx in browser.contexts:
                for page in ctx.pages:
                    url = page.url or ""
                    if "easytrader" not in url:
                        continue
                    js = """(sels) => {
                      const vis = el => { try { const r=el.getBoundingClientRect();
                        const s=getComputedStyle(el); return !!(r.width||r.height)
                          && s.display!=='none' && s.visibility!=='hidden'; }
                        catch(e){ return false; } };
                      const out = {};
                      for (const [k,s] of Object.entries(sels)) {
                        let nodes=[]; try { nodes=Array.from(document.querySelectorAll(s)); } catch(e){}
                        out[k] = {count:nodes.length,
                          visible:nodes.filter(vis).length,
                          enabled:nodes.filter(n => !n.disabled).length};
                      }
                      return out;
                    }"""
                    counts = page.evaluate(js, CANDIDATES)
                    out["pages"].append({
                        "path": urlparse(url).path,
                        "title": (page.title() or "")[:80],
                        "selectors": counts,
                    })
            browser.close()
    except Exception as e:                       # noqa: BLE001
        out["error"] = "%s: %s" % (type(e).__name__, str(e)[:160])
    out["verified"] = [k for k, v in (out.get("pages") or [{}])[0].get(
        "selectors", {}).items() if v.get("count") == 1 and v.get("visible") == 1]
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("SELECTOR PROBE " + ("HOST" if out.get("pages") else "NO_PAGE"))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
