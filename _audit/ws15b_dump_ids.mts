// _audit/ws15b_dump_ids.mts — چه testidهایی رویِ صفحۀ قیف هست؟ (کمکیِ سنجد)
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const b = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const c = await b.newContext({ viewport: { width: 1600, height: 900 } });
await c.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const p = await c.newPage();
const BASE = process.argv.includes('--url') ? process.argv[process.argv.indexOf('--url') + 1] : 'http://127.0.0.1:8021/';
await p.goto(BASE, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(12000);
console.log('LANDING_URL: ' + p.url());
console.log('FUNNEL_ON_LANDING: ' + await p.evaluate(() =>
  document.querySelectorAll('[data-testid="fts-funnel-workspace"]').length));
console.log('TAPE_ON_LANDING: ' + await p.evaluate(() =>
  document.querySelectorAll('[data-testid="tape-scroll"]').length));
console.log('SIDEBAR_ACTIVE: ' + await p.evaluate(() =>
  Array.from(document.querySelectorAll('[data-shell="sidebar"] a[aria-current="page"]'))
    .map((n) => (n.textContent || '').trim()).join('|')));
const ids = await p.evaluate(() =>
  Array.from(document.querySelectorAll('[data-testid]')).map((n) => n.getAttribute('data-testid')));
console.log('TESTIDS: ' + JSON.stringify(ids));
const btns = await p.evaluate(() => Array.from(document.querySelectorAll('button')).slice(0, 70)
  .map((n) => `${n.getAttribute('data-testid') || '-'}::${(n.textContent || '').trim().slice(0, 20)}`));
console.log('BUTTONS: ' + JSON.stringify(btns));
await b.close();
