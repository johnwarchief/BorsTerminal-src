// _audit/net_fail_probe.mts -- علتِ یک error کنسول: کدام درخواست 404 شد؟
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR!;
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const url = process.argv[2];
const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1632, height: 950 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const bad: string[] = [];
const errs: string[] = [];
page.on('response', (r) => { if (r.status() >= 400) bad.push(`${r.status()} ${r.url()}`); });
page.on('requestfailed', (r) => bad.push(`FAILED ${r.url()} ${r.failure()?.errorText}`));
page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 160)); });
await page.goto(url + '#/master', { waitUntil: 'networkidle' });
await page.waitForTimeout(12000);
console.log('HTTP>=400:', JSON.stringify(bad, null, 1));
console.log('console errors:', JSON.stringify(errs, null, 1));
await browser.close();
