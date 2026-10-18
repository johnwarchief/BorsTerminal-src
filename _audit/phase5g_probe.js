// _audit/phase5g_probe.js — عیب‌یابیِ «چرا بومِ چارت دیده نشد» (مرحلۀ قبل از phase5g_ui_check)
const path = require('path');
const pw = path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core');
const { chromium } = require(pw);

const EXE = process.env.RA_BROWSER || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PROFILE = path.join(process.env.TEMP || '/tmp', 'bors-phase5g-probe');
const URL0 = process.env.BORS_UI_URL || 'http://127.0.0.1:8000/technical/' + encodeURIComponent('فولاژ');

(async () => {
  const ctx = await chromium.launchPersistentContext(PROFILE, {
    executablePath: EXE, headless: false, viewport: { width: 1366, height: 768 },
    args: ['--no-first-run', '--no-default-browser-check', '--disable-features=Translate'],
  });
  const page = ctx.pages()[0] || await ctx.newPage();
  const errs = [];
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 200)); });
  page.on('pageerror', (e) => errs.push('pageerror: ' + String(e.message).slice(0, 200)));
  await page.goto(URL0, { waitUntil: 'load', timeout: 90000 });
  await page.waitForTimeout(12000);
  console.log('title  :', await page.title());
  console.log('url    :', page.url());
  console.log('canvas :', await page.locator('canvas').count());
  console.log('.nn-kline-chart :', await page.locator('.nn-kline-chart').count());
  console.log('buttons:', await page.locator('button').count());
  const text = await page.locator('body').innerText();
  console.log('body head:', text.slice(0, 400).replace(/\n+/g, ' | '));
  console.log('errors(' + errs.length + '):', errs.slice(0, 8).join('\n   '));
  await page.screenshot({ path: path.join(__dirname, 'PHASE5G-PROBE.png'), fullPage: false });
  await ctx.close();
})().catch((e) => { console.error('FATAL ' + String(e)); process.exit(1); });
