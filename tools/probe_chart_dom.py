"""نصِ نوارابزار چارت + ردپای خطای «B.map is not a function» از خودِ مرورگر."""
from __future__ import annotations

import json
import re
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8011"
SYM = sys.argv[2] if len(sys.argv) > 2 else "آسود"

DUMP = r"""() => {
  const txt = e => (e.textContent || '').replace(/\s+/g, ' ').trim();
  const bar = document.querySelector('header, [class*="toolbar" i]');
  const btns = [...document.querySelectorAll('button')]
    .map(b => ({ t: txt(b), title: b.getAttribute('title') || '',
                 w: Math.round(b.getBoundingClientRect().width),
                 clipped: b.scrollWidth > b.clientWidth + 1 }))
    .filter(b => b.t);
  const latin = btns.filter(b => /[A-Za-z]/.test(b.t));
  const clipped = btns.filter(b => b.clipped);
  return {
    count: btns.length,
    latin: latin.slice(0, 25),
    clipped: clipped.slice(0, 15),
    first40: btns.slice(0, 40).map(b => b.t),
  };
}"""


def main():
    stacks: list[str] = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1600, "height": 900})
        pg.on("pageerror", lambda e: stacks.append(getattr(e, "stack", str(e)) or str(e)))
        pg.goto(BASE + "/#/fundamental")
        if pg.evaluate("() => !!document.querySelector('input[type=password]')"):
            pg.locator("input").first.fill("admin")
            pg.locator("input[type=password]").first.fill("bors123")
            pg.get_by_role("button", name=re.compile("ورود")).first.click()
        pg.wait_for_timeout(2000)
        pg.goto(f"{BASE}/#/technical/{SYM}")
        pg.wait_for_timeout(9000)
        print(json.dumps(pg.evaluate(DUMP), ensure_ascii=False, indent=1))
        print("\n=== خطاها (%d) ===" % len(stacks))
        seen = set()
        for s in stacks:
            key = s.splitlines()[0][:80] if s else ''
            if key in seen:
                continue
            seen.add(key)
            print(s[:1400])
            print('-' * 60)
        b.close()


if __name__ == "__main__":
    main()
