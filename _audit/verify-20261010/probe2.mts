import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR!;
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
await context.addInitScript(() => { sessionStorage.setItem('bors_auth_session', 'true'); });
const page = await context.newPage();
const errs: string[] = [];
page.on('console', (m: any) => { if (m.type() === 'error') errs.push(m.text().slice(0, 200)); });
page.on('pageerror', (e: any) => errs.push(String(e.message)));
await page.goto('http://127.0.0.1:8002/#/portfolio', { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="portfolio-section-watch"]', { timeout: 30000 });
await page.click('[data-testid="portfolio-section-watch"]');
for (const sym of ['شپنا', 'فولاد', 'خساپ']) {
  await page.fill('[data-testid="watch-add-input"]', sym);
  await new Promise(r => setTimeout(r, 600));
  await page.click('[data-testid="watch-add-btn"]');
  await new Promise(r => setTimeout(r, 600));
}
await page.waitForSelector('[data-testid^="watch-row-"]', { timeout: 20000 });
const ids = await page.evaluate(() => Array.from(document.querySelectorAll('[data-testid^="watch-row-"]')).map(e => e.getAttribute('data-testid')));
const out: any = { ids, reads: [] };
for (const tid of ids.slice(0, 3)) {
  await page.click(`[data-testid="${tid}"]`);
  await new Promise(r => setTimeout(r, 12000));
  out.reads.push(await page.evaluate(() => {
    const g = (s: string) => { const el = document.querySelector(s); return el ? { sym: el.getAttribute('data-symbol'), text: (el.textContent ?? '').replace(/\s+/g,' ').trim().slice(0,150), canvas: !!el.querySelector('canvas') } : null; };
    return { chart: g('[data-testid="watch-chart"]'), ob: g('[data-testid="watch-orderbook"]'), sum: g('[data-testid="watch-summary"]') };
  }));
  await page.screenshot({ path: `_audit/verify-20261010/07_watch_settled_${tid.replace('watch-row-','')}.png` });
}
out.errs = errs;
writeFileSync('_audit/verify-20261010/probe2_result.json', JSON.stringify(out, null, 1), 'utf8');
console.log(JSON.stringify(out, null, 1));
await browser.close();
