// MAIN.app-main is still 1266px wide inside a 704px flex column container,
// even with min-width:0. Test candidate fixes empirically rather than guess.
const { chromium } = require('playwright-core');

const CANDIDATES = [
  ['baseline', ''],
  ['width:100%', 'width:100%'],
  ['align-self:stretch', 'align-self:stretch'],
  ['overflow-x:auto', 'overflow-x:auto'],
  ['max-width:100%', 'max-width:100%'],
  ['w+min+align', 'width:100%;min-width:0;align-self:stretch'],
];

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

  for (const [name, css] of CANDIDATES) {
    const r = await page.evaluate((c) => {
      const main = document.querySelector('main.app-main');
      const tbl = document.querySelector('table.min-w-\\[1240px\\]');
      const scroll = tbl ? tbl.parentElement : null;
      // apply to main, and also to the two intermediate flex wrappers
      const targets = [main];
      let el = tbl;
      while (el && el !== main) {
        targets.push(el);
        el = el.parentElement;
      }
      targets.forEach(t => { if (t && t !== tbl) t.style.cssText += ';' + c; });
      const out = {
        mainW: Math.round(main.getBoundingClientRect().width),
        scrollW: scroll ? Math.round(scroll.getBoundingClientRect().width) : null,
        scrollClientW: scroll ? scroll.clientWidth : null,
        scrollScrollW: scroll ? scroll.scrollWidth : null,
        docScrollW: document.documentElement.scrollWidth,
      };
      targets.forEach(t => { if (t) t.style.cssText = t.style.cssText.replace(';' + c, '').replace(c, ''); });
      return out;
    }, css);
    console.log('%-16s main=%-6s scrollBox=%-6s client=%-6s scroll=%-6s docScroll=%s',
      name, r.mainW, r.scrollW, r.scrollClientW, r.scrollScrollW, r.docScrollW);
  }
  await browser.close();
}

main().catch(e => { console.error('FATAL', e); process.exit(1); });
