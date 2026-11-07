import { createRequire } from 'node:module';
const req = createRequire('C:/Users/Johnkallnaya/Desktop/Borsterminal/.worktrees/system2-ui/frontend/index.js');
const { chromium } = req('playwright-core');
const b = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' });
const c = await b.newContext({ viewport: { width: 1366, height: 768 } });
await c.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const p = await c.newPage();
await p.goto('http://127.0.0.1:8020/#/market', { waitUntil: 'networkidle' });
await p.waitForTimeout(6000);
const sels = ['tbody tr', '[data-testid^="watch-star-"]', '[data-testid^="row-"]',
  '[data-symbol]', '[data-row-index]', '[class*="tabular"]', '[data-freshness]',
  '[data-regulatory-state]', 'a[href*="symbol"]'];
console.log(JSON.stringify(await p.evaluate((ss: string[]) => Object.fromEntries(
  ss.map((s) => [s, document.querySelectorAll(s).length])), sels)));
await b.close();
