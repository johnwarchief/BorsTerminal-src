#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""uiux_audit_v1124.py — خطِ پایهٔ (baseline) کمّیِ UI/UX، نه حسِ شخصی

چرا این ابزار هست: مالک می‌گوید «اندازۀِ System 2 را جایِ baselineِ خطِ جاری
استفاده نکن» و «هیچ عددی برایِ سبزکردنِ سنجه جعل نشود». پس پیشِ هر پولیش و
پسِ آن، همانِ یکِ سنجه رویِ همانِ build اجرا می‌شود و خروجی‌اش JSON می‌ماند.

چه چیزی می‌سنجد (برایِ هر route × هر viewport):
  * سرریزِ افقیِ سند (`scrollWidth > innerWidth`) — همان چیزی که درِ گوشی صفحه
    را می‌لغزاند.
  * گره‌هایِ بریده: عنصرِ بی‌فرزند باِ متن که `scrollWidth`اش ازِ `clientWidth`
    بیشتر است و `overflow:hidden` می‌خورد. `sr-only` و `truncate`هایِ عمدی
    شمارش نمی‌شوند (نشانۀِ دسترس‌پذیری و بریدگیِ عمدی، نقص نیست).
  * ریزنقشیِ متن: گره‌هایِ دیدنی باِ `font-size < 11px` — آستانه ازِ همین
    نردبانِ `--fs-3xs = 11px` می‌آید (`tokens.css`)، نه ازِ سلیقه.
  * هدفِ لمسیِ کوچک: المانِ تعاملی باِ ارتفاع یا عرضِ دیدنی < 24px (کفِ WCAG 2.2؛
    48dp فقط درِ Android WebView معنا دارد و آنجا NOT_PROVEN ثبت می‌شود).
  * شمارِ درخواست‌هایِ `/api/*` درِ پنجرۀِ اولیۀِ بارگذاری — «درخواستِ اضافه و
    بی‌دلیل» همین‌جا دیده می‌شود، نه درِ متنِ گزارش.
  * زمانِ آماده‌شدن (cold = اولین بار درِ contextِ تازه، warm = بارِ دوم) باِ
    تکرارِ قابلِ تنظیم، چون نوسانِ ماشینِ من واقعی است.
  * خطاهایِ کنسول و ErrorBoundary.

خروجی: JSON + جدولِ خلاصه. هیچ عددی اینجا ساخته نمی‌شود؛ هرچه هست ازِ خودِ
مرورگر خوانده می‌شود.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

CHROME = r"C:\Users\PCMOD\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe"
SEED = ("try{sessionStorage.setItem('bors_auth_session','true');"
        "sessionStorage.setItem('bors_auth_user','admin');"
        "localStorage.setItem('bors-symbol','فولاد');}catch(e){}")

ROUTES = ["market", "market-status", "technical", "fundamental", "master",
          "strategy-tree", "portfolio", "watch", "notifications", "sarkhati",
          "engine-lab"]
SIZES_WIDE = [(1366, 768), (1280, 720), (1920, 1080), (2560, 1440)]
SIZES_NARROW = [(360, 800), (390, 844), (430, 932), (812, 375)]

# JSِ یکپارچه: همه ازِ getComputedStyle و rect خوانده می‌شود؛ بی‌انتظارِ networkidle
# (فیدِ تابلو مداوم پولینگ می‌کند و هرگز idle نمی‌شود).
MEASURE_JS = r"""
() => {
  const out = {overflow: false, docW: 0, winW: 0, clipped: [], tiny: [],
               smallTargets: [], ellipsisOk: [], bodyH: 0, textLen: 0};
  const de = document.documentElement;
  out.docW = de.scrollWidth; out.winW = window.innerWidth; out.bodyH = de.scrollHeight;
  out.overflow = de.scrollWidth > window.innerWidth + 2;
  out.textLen = (document.body.innerText || '').length;
  const skip = (el) => {
    if (!el || el.closest('[aria-hidden="true"]')) return true;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) return true;
    const cls = (el.className && el.className.toString) ? el.className.toString() : '';
    if (/(^|\s)(sr-only|sr-only-text)(\s|$)/.test(cls)) return true;
    return false;
  };
  const label = (el) => {
    const t = (el.textContent || '').trim().slice(0, 28);
    const id = el.getAttribute && el.getAttribute('data-testid');
    return (id ? id + ' ' : '') + el.tagName.toLowerCase() + (t ? ' «' + t + '»' : '');
  };
  const all = Array.from(document.querySelectorAll('body *'));
  for (const el of all) {
    if (skip(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    const cs = getComputedStyle(el);
    const own = Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
    if (own) {
      const fs = parseFloat(cs.fontSize) || 0;
      if (fs < 11) out.tiny.push({px: Math.round(fs * 10) / 10, at: label(el)});
    }
    if (own && cs.overflowX !== 'visible' && el.scrollWidth > el.clientWidth + 2) {
      const cls = (el.className && el.className.toString) ? el.className.toString() : '';
      const deliberate = cs.textOverflow === 'ellipsis' || /(^|\s)truncate(\s|$)/.test(cls);
      if (!deliberate) {
        out.clipped.push({lost: el.scrollWidth - el.clientWidth, at: label(el)});
      } else {
        out.ellipsisOk.push({lost: el.scrollWidth - el.clientWidth, at: label(el)});
      }
    }
    const inter = el.matches('button, a, input, select, textarea, [role="button"], [role="tab"], summary');
    if (inter && (r.height < 24 || r.width < 24)) {
      out.smallTargets.push({w: Math.round(r.width), h: Math.round(r.height), at: label(el)});
    }
  }
  const cap = (arr, n) => arr.slice(0, n);
  out.tinyCount = out.tiny.length; out.clippedCount = out.clipped.length;
  out.ellipsisCount = out.ellipsisOk.length;
  out.smallTargetsCount = out.smallTargets.length;
  out.tiny = cap(out.tiny, 12); out.clipped = cap(out.clipped, 12);
  out.smallTargets = cap(out.smallTargets, 12);
  return out;
}
"""


def load_once(page, base, route, anchor, net, errors):
    t0 = time.time()
    page.goto("%s/#/%s" % (base, route), wait_until="domcontentloaded", timeout=60000)
    ok = True
    try:
        page.wait_for_selector(anchor, timeout=20000)
    except Exception:
        ok = False
    # پنجرۀِ شمارشِ درخواست: ۳ ثانیه پسِ دیدنِ لنگر، همان چیزی که کاربر «باز شدنِ
    # صفحه» می‌نامد.
    page.wait_for_timeout(3000)
    ms = int((time.time() - t0) * 1000)
    m = page.evaluate(MEASURE_JS)
    m["loaded"] = ok
    m["ms"] = ms
    m["api"] = len([1 for meth, u in net if "/api/" in u])
    m["console"] = len(errors)
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8103")
    ap.add_argument("--out", default="_test_runs/uiux_audit")
    ap.add_argument("--routes", default=",".join(ROUTES))
    ap.add_argument("--sizes", default="wide", help="wide | narrow | both | 1366x768,360x800")
    ap.add_argument("--repeat", type=int, default=2, help="تکرارِ اندازه‌گیریِ زمان (نوسان)")
    ap.add_argument("--tag", default="baseline")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    routes = [r.strip() for r in a.routes.split(",") if r.strip()]
    if a.sizes == "wide":
        sizes = SIZES_WIDE
    elif a.sizes == "narrow":
        sizes = SIZES_NARROW
    elif a.sizes == "both":
        sizes = SIZES_WIDE + SIZES_NARROW
    else:
        sizes = [tuple(int(x) for x in s.split("x")) for s in a.sizes.split(",")]
    base = a.base.rstrip("/")
    from playwright.sync_api import sync_playwright

    report = {"tag": a.tag, "base": base, "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
              "routes": {}}
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME, headless=True)
        for route in routes:
            anchor = "[data-testid='%s']" % {
                # لنگرها ازِ DOMِ واقعیِ همینِ خط کشف شدند: نسخۀِ اولِ اینِ ابزار
                # ششِ route را رویِ انتخابگرِ بی‌وجود ۲۰ ثانیه تایم‌اوت می‌کرد وِ
                # بعدِ آن 23,000ms را «زمانِ بارگذاری» گزارش می‌داد — خطایِ سنجه.
                "market": "market-page", "market-status": "market-status-page",
                "technical": "technical-sidebar", "fundamental": "fundamental-page",
                "master": "master-breadcrumb", "strategy-tree": "strategy-tree-overview",
                "portfolio": "portfolio-page", "watch": "watch-market-workspace",
                "notifications": "notifications-page", "sarkhati": "sarkhati-page",
                "engine-lab": "engine-lab"}.get(route, "#root")
            per_size = {}
            for (w, h) in sizes:
                ctx = b.new_context(viewport={"width": w, "height": h})
                ctx.add_init_script(SEED)
                page = ctx.new_page()
                net, errors = [], []
                page.on("request", lambda r: net.append((r.method, r.url.split("?")[0])))
                page.on("console", lambda m: errors.append(m.text[:140])
                        if m.type == "error" else None)
                runs = []
                for i in range(max(1, a.repeat)):
                    net_len = len(net)
                    m = load_once(page, base, route, anchor, net[net_len:], errors)
                    m["api"] = len([1 for meth, u in net[net_len:] if "/api/" in u])
                    runs.append(m)
                    page.screenshot(path=os.path.join(
                        a.out, "%s_%s_%dx%d_%d.png" % (a.tag, route, w, h, i)),
                        full_page=(i == 0))
                ctx.close()
                cold, warm = runs[0]["ms"], [r["ms"] for r in runs[1:]] or [runs[0]["ms"]]
                per_size["%dx%d" % (w, h)] = {
                    "loaded": all(r["loaded"] for r in runs),
                    "overflow": any(r["overflow"] for r in runs),
                    "docW": max(r["docW"] for r in runs),
                    "clipped": max(r["clippedCount"] for r in runs),
                    "ellipsis": max(r.get("ellipsisCount", 0) for r in runs),
                    "tiny": max(r["tinyCount"] for r in runs),
                    "smallTargets": max(r["smallTargetsCount"] for r in runs),
                    "apiReqs": runs[0]["api"],
                    "consoleErrors": runs[-1]["console"],
                    "coldMs": cold,
                    "warmMsMed": int(statistics.median(warm)),
                    "samples": [r["ms"] for r in runs],
                    "clippedAt": runs[0]["clipped"][:6],
                    "ellipsisAt": runs[0]["ellipsisOk"][:6],
                    "tinyAt": runs[0]["tiny"][:6],
                    "smallAt": runs[0]["smallTargets"][:6],
                }
            report["routes"][route] = per_size
            print("  %s: %s" % (route, " | ".join(
                "%s ovf=%s clip=%d tiny=%d api=%d cold=%dms" % (
                    k, v["overflow"], v["clipped"], v["tiny"], v["apiReqs"], v["coldMs"])
                for k, v in per_size.items())))
        b.close()
    path = os.path.join(a.out, "%s.json" % a.tag)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    tot = sum(v["clipped"] + v["tiny"] + v["smallTargets"]
              for r in report["routes"].values() for v in r.values())
    print("\nپایان: %s — مجموعِ نشانگرهایِ نقص (بریده+ریز+کوچک) درِ همهِ نمون\u200cها: %d" % (path, tot))
    return 0


if __name__ == "__main__":
    sys.exit(main())
