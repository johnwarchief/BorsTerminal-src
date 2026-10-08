// _audit/ws7e_diag.mts — چرا رویِ #/market جعبۀ انتخاب نیست؟ شمارشِ testid ها
// و HTMLِ سلولِ نمادِ ردیفِ اول (تشخیصِ نبود، نه حدس).
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const browser = await chromium.launch({ headless: true,
  executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const logs = [];
page.on('console', (m) => { if (m.type() === 'error') logs.push(m.text().slice(0, 160)); });
page.on('pageerror', (e) => logs.push('pageerror: ' + String(e.message).slice(0, 160)));
await page.goto('http://127.0.0.1:5173/#/market', { waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => document.querySelectorAll('[data-testid="tape-row"]').length >= 5,
  null, { timeout: 90_000 });
await page.waitForTimeout(1200);
const info = await page.evaluate(() => {
  const ids = {};
  document.querySelectorAll('[data-testid]').forEach((e) => {
    const k = String(e.getAttribute('data-testid')).replace(/-[^-]+$/, '-*');
    ids[k] = (ids[k] ?? 0) + 1;
  });
  const row = document.querySelector('[data-testid="tape-row"]');
  return {
    url: location.hash,
    rowCount: document.querySelectorAll('[data-testid="tape-row"]').length,
    selectBox: document.querySelectorAll('[data-testid^="select-box-"]').length,
    star: document.querySelectorAll('[data-testid^="watch-star-"]').length,
    groups: document.querySelectorAll('[data-testid="tape-row"].group, [data-testid="tape-row"] [class*=group]').length,
    rowHtml: row ? row.innerHTML.slice(0, 700) : null,
    idCounts: Object.fromEntries(Object.entries(ids).sort((a, b) => b[1] - a[1]).slice(0, 25)),
  };
});
console.log(JSON.stringify(info, null, 2));
console.log('ERRORS: ' + JSON.stringify(logs.slice(0, 6)));
await browser.close();
