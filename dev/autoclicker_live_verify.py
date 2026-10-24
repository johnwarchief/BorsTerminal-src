#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""autoclicker_live_verify — بررسیِ فقط‌خواندنیِ نشستِ واقعیِ EasyTrader.

چه می‌کند: پنجرۀ host را می‌خواند، تب‌ها را فهرست می‌کند، «ورود» را فقط از شاهدِ
قابلِ مشاهده (بودنِ کلیدِ oidc + نبودِ فیلدِ رمز) می‌سنجد، و اگر تبِ کارگزاری
باز بود، DOMِ فرم را با selectorهایِ ذخیره‌شده می‌خواند و `judge` را گزارش
می‌کند. **هیچ کلیکی، هیچ نوشتنی، هیچ POSTی، و هیچ خواندنِ مقدارِ نشست.**

این تنها بخشی از مأموریت است که به ورودِ دستیِ مالک وابسته است؛ اجرایِ آن پیش
از ورود، صادقانه `NO_HOST` / `LOGIN_REQUIRED` می‌دهد، نه PASSِ ساختگی.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cdp", default="", help="override CDP URL (loopback only)")
    ap.add_argument("--submit-selector", default="")
    ap.add_argument("--price-selector", default="")
    ap.add_argument("--quantity-selector", default="")
    ap.add_argument("--symbol-selector", default="")
    ap.add_argument("--isin-selector", default="")
    ap.add_argument("--side-selector", default="")
    ap.add_argument("--form-scope-selector", default="")
    ap.add_argument("--expected-symbol", default="")
    ap.add_argument("--expected-isin", default="")
    ap.add_argument("--expected-price", type=float, default=None)
    ap.add_argument("--expected-quantity", type=float, default=None)
    ap.add_argument("--side", choices=("buy", "sell"), default="buy")
    a = ap.parse_args(argv)

    import execution_browser as EB
    import execution_browser_host as BH
    import execution_panel as PANEL
    import execution_strategy_core as SC
    import execution_ui_state as UIS

    host = BH.read_status(check=True)
    cdp = str(a.cdp or host.get("cdp_url") or "").strip()
    out: dict = {"host": {k: host.get(k) for k in ("status", "healthy", "url", "name")},
                 "cdp": bool(cdp)}
    if not host.get("healthy") or not cdp:
        out["verdict"] = "NO_HOST"
        out["next_step"] = ("برنامه → سرخطی → «بازکردن پنجرۀ EasyTrader»؛ خودتان وارد "
                            "شوید (رمز/OTP/CAPTCHA را برنامه نمی‌پرسد).")
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    out["tabs"] = PANEL.list_tabs(cdp)
    out["session"] = PANEL.session_presence(cdp)
    broker = [t for t in (out["tabs"].get("tabs") or []) if t.get("is_broker")]
    if not broker:
        out["verdict"] = "NO_BROKER_TAB"
        out["next_step"] = "در همان پنجره، d.easytrader.ir را باز و وارد شوید."
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    saved = SC.StrategySettingsStore().load().get(SC.AUTOCLICKER)
    opt = dict((saved.options if saved else {}) or {})
    ui = UIS.UIOptions(
        submit_selector=a.submit_selector or str(opt.get("submit_selector") or ""),
        price_selector=a.price_selector or str(opt.get("price_selector") or ""),
        quantity_selector=a.quantity_selector or str(opt.get("quantity_selector") or ""),
        symbol_selector=a.symbol_selector or str(opt.get("form_symbol_selector") or ""),
        isin_selector=a.isin_selector or str(opt.get("isin_selector") or ""),
        side_selector=a.side_selector or str(opt.get("side_selector") or ""),
        form_scope_selector=a.form_scope_selector or str(opt.get("form_selector") or ""),
        side=a.side, expected_price=a.expected_price,
        expected_quantity=a.expected_quantity,
        expected_symbol=a.expected_symbol, expected_isin=a.expected_isin)
    out["selectors_configured"] = bool(ui.submit_selector and ui.price_selector
                                       and ui.quantity_selector)
    if not ui.submit_selector:
        out["verdict"] = "SELECTORS_UNCONFIGURED"
        out["next_step"] = ("selectorها را در پنل ذخیره کنید یا با --submit-selector/"
                            "--price-selector/… بدهید؛ ویترینِ پیش‌فرض حدس زده نمی‌شود.")
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(cdp.rstrip("/"), timeout=15000)
            from urllib.parse import urlparse
            pages = []
            for ctx in browser.contexts:
                for pg in ctx.pages:
                    h = (urlparse(pg.url).hostname or "").lower()
                    if any(h == a or h.endswith("." + a)
                           for a in PANEL.EASYTRADER_HOSTS):
                        pages.append(pg)
            if not pages:
                out["verdict"] = "NO_BROKER_PAGE"
                print(json.dumps(out, ensure_ascii=False, indent=1))
                return 0
            state = pages[0].evaluate(UIS.UI_STATE_JS, ui.as_eval_opts())
            res = UIS.judge(state, ui)
    except Exception as e:                                  # noqa: BLE001
        out["verdict"] = "PROBE_FAILED"
        out["detail"] = "%s: %s" % (type(e).__name__, str(e)[:160])
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    out["form"] = {"url_path": state.get("url_path"),
                   "title": state.get("title"),
                   "counts": state.get("counts"),
                   "fields": {k: {"present": (v or {}).get("present"),
                                  "visible": (v or {}).get("visible"),
                                  "count": (v or {}).get("count")}
                              for k, v in (state.get("fields") or {}).items()},
                   "candidates": len(state.get("submit_candidates") or [])}
    out["judge"] = {"verdict": res.verdict, "ok": res.ok, "reason": res.reason,
                    "checks": res.checks,
                    "button": {k: (res.button or {}).get(k) for k in
                               ("index", "text", "aria", "visible", "enabled",
                                "in_viewport", "form_bound", "path")}}
    out["verdict"] = "FORM_UNIQUE" if res.ok else "FORM_NOT_READY"
    out["writes"] = 0
    out["note"] = ("فقط‌خواندنی: هیچ کلیک/تایپ/POSTی انجام نشد و مقدارِ نشست خوانده نشد.")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    try:
        #: کنسولِ ویندوز پیش‌فرض cp1252 است و خروجیِ فارسی همین‌جا می‌شکست.
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
