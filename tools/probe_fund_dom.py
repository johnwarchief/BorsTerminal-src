"""کاوشِ زندهٔ DOMِ تب «بنیادی» تا لوکاتورهایِ واقعیِ جدول و کارتِ نماد دستم بیاید.
قصدِ ما خواندنِ JSX نیست؛ آنچه مرورگر واقعاً رندر کرده می‌سنجیم.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001"


def dump(page, label: str, js: str):
    out = page.evaluate(js)
    print(f"\n### {label}")
    if isinstance(out, list):
        for line in out:
            print("  ", line)
    else:
        print("  ", out)


with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    pg.goto(BASE + "/#/fundamental")
    # صفحهٔ ورودِ محلی رویِ مسیر است؛ اگر بود رد شو (رمزِ پیش‌فرضِ خودِ برنامه)
    if pg.evaluate("() => !!document.querySelector('input[type=password]')"):
        print("login gate seen")
        u = pg.locator("input[type=text], input[name*=user i], input[autocomplete=username]").first
        u.fill("admin")
        pg.locator("input[type=password]").first.fill("bors123")
        pg.get_by_role("button", name=__import__("re").compile(r"ورود")).first.click()
        pg.wait_for_timeout(4000)

    # جدولِ بنیادی سرد است؛ تا آمدنِ اولینِ ردیف صبر کن وگرنه DOM نصفه می‌بینیم
    try:
        pg.wait_for_function(
            "() => document.querySelectorAll('tbody *, [role=row]').length > 5", timeout=90000
        )
    except Exception as e:  # noqa: BLE001
        print("!! ردیف نیامد:", e)
    pg.wait_for_timeout(3000)
    print("body chars:", len(pg.evaluate("() => document.body.innerText || ''")))
    print("url:", pg.url)

    dump(pg, "headings/buttons text", """
      () => [...document.querySelectorAll('h1,h2,h3,h4,button[title],[aria-label]')]
        .slice(0,40)
        .map(e => e.tagName + ' | ' + (e.getAttribute('data-testid')||'-') + ' | '
                    + (e.title || e.getAttribute('aria-label') || '') + ' | '
                    + (e.textContent||'').trim().slice(0,60))
    """)
    dump(pg, "testids present", """
      () => [...new Set([...document.querySelectorAll('[data-testid]')]
              .map(e => e.getAttribute('data-testid')))].slice(0,60)
    """)
    dump(pg, "clickable rows", """
      () => {
        const cands = ['tr','[role=row]','tbody > div','[data-testid^="fts-row"]','[data-symbol]'];
        const out = [];
        for (const sel of cands) {
          const n = document.querySelectorAll(sel).length;
          if (n) out.push(sel + ' = ' + n);
        }
        return out;
      }
    """)
    dump(pg, "first row text", """
      () => {
        const r = document.querySelector('tbody > div, tbody tr, [role=row]:not([role=rowheader])');
        return r ? (r.textContent||'').trim().slice(0,160) : 'none';
      }
    """)
    b.close()
