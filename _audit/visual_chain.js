// Walk the ancestor chain of the FTS table and report each element's width.
// This finds the exact level where the min-w-[1240px] table escapes its
// container and stops overflow-auto from engaging.
const { chromium } = require('playwright-core');

async function main() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true,
    args: ['--no-first-run', '--no-default-browser-check'] });
  const ctx = await browser.newContext({ viewport: { width: 768, height: 900 } });
  const page = await ctx.newPage();
  await page.goto('http://localhost:8001/#/fundamental', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);
  const needsLogin = await page.locator('input[placeholder="admin"]').count().catch(() => 0);
  if (needsLogin > 0) {
    await page.locator('input[placeholder="admin"]').fill('admin');
    await page.locator('input[type="password"]').first().fill('bors123');
    await page.getByRole('button', { name: /ورود به ایستگاه/i }).click();
    await page.waitForTimeout(8000);
    await page.goto('http://localhost:8001/#/fundamental', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(4000);
  }

  const chain = await page.evaluate(() => {
    const tbl = document.querySelector('table.min-w-\\[1240px\\]');
    if (!tbl) return { err: 'table not found' };
    const out = [];
    let el = tbl;
    while (el && el !== document.documentElement) {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      out.push({
        tag: el.tagName,
        cls: (el.className || '').toString().slice(0, 52),
        w: Math.round(r.width),
        left: Math.round(r.left),
        overflowX: s.overflowX,
        minW: s.minWidth,
        flex: s.flex.substring(0, 24),
        display: s.display,
      });
      el = el.parentElement;
    }
    out.push({ tag: 'HTML', w: document.documentElement.clientWidth });
    return out;
  });

  console.log('vw = 768\n');
  for (const c of chain) {
    console.log('%-8s w=%-6s left=%-6s ovx=%-9s minW=%-9s disp=%-7s %s',
      c.tag, c.w, c.left, c.overflowX, c.minW, c.display, c.cls || '');
  }
  await browser.close();
}

main().catch(e => { console.error('FATAL', e); process.exit(1); });
