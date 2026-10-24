/**
 * Functional smoke pass for the M1 technical page, against a shell already
 * listening on CDP. Exercises indicator, adjustment, timeframe and drawing
 * controls; verifies the chart canvas survives each action and screenshots it.
 *
 * usage:
 *   node tools/desktop-migration/ui_smoke.mjs --cdp 9810 \
 *     --out artifacts/desktop-migration/ui-smoke
 */
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';
import path from 'node:path';

const require = createRequire(fileURLToPath(new URL('../../frontend/package.json', import.meta.url)));
const puppeteer = require('puppeteer-core');

const arg = (name, fallback) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : fallback;
};
const cdp = Number(arg('cdp', '9810'));
const out = path.resolve(arg('out', 'artifacts/desktop-migration/ui-smoke'));
fs.mkdirSync(out, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.connect({ browserURL: `http://127.0.0.1:${cdp}`, defaultViewport: null });
const pages = await browser.pages();
const page = pages.find((p) => /127\.0\.0\.1:8105/.test(p.url())) || pages[0];
if (!page) throw new Error('no page');
const errors = [];
page.on('pageerror', (e) => errors.push(`pageerror: ${String(e).slice(0, 300)}`));
page.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text().slice(0, 300)}`); });

async function clickText(text, tag = 'button') {
  const ok = await page.evaluate(({ text, tag }) => {
    const el = [...document.querySelectorAll(tag)].find((b) => b.textContent.trim() === text);
    if (!el) return false;
    el.click();
    return true;
  }, { text, tag });
  if (!ok) throw new Error(`control not found: ${text}`);
  await sleep(700);
}

async function state(label) {
  const snap = await page.evaluate(() => ({
    url: location.hash,
    canvases: document.querySelectorAll('[data-testid="chart-host"] canvas').length,
    activeButtons: [...document.querySelectorAll('.seg button.on, .toolbar button.on')].map((b) => b.textContent.trim()),
    errorBox: document.querySelector('.error-box')?.textContent?.trim() || null,
    rows: document.querySelectorAll('[data-testid="market-row"]').length,
  }));
  const file = path.join(out, `${label}.png`);
  await page.screenshot({ path: file });
  return { label, file: path.relative(process.cwd(), file), ...snap };
}

const checks = [];
await page.bringToFront();
if (!(await page.$('[data-testid="proto-shell"]'))) {
  await page.waitForSelector('input[type="password"]', { timeout: 60000 });
  await page.click('input[type="password"]');
  await page.keyboard.type('bors123');
  await page.keyboard.press('Enter');
  await page.waitForSelector('[data-testid="proto-shell"]', { timeout: 60000 });
}
checks.push(await state('00-shell'));

await page.click('[data-testid="proto-nav-market"]');
await page.waitForFunction(() => document.querySelectorAll('[data-testid="market-row"]').length >= 20, { timeout: 120000 });
checks.push(await state('01-market'));

await page.click('[data-testid="proto-nav-technical"]');
await page.waitForSelector('[data-testid="chart-host"] canvas', { timeout: 120000 });
await sleep(1500);
checks.push(await state('02-technical'));

await clickText('RSI');
checks.push(await state('03-rsi'));
await clickText('خام');
checks.push(await state('04-raw'));
await clickText('هفتگی');
checks.push(await state('05-weekly'));
await clickText('ماهانه');
checks.push(await state('06-monthly'));
await clickText('روزانه');
await clickText('تعدیل‌شده');
checks.push(await state('07-combined'));

await clickText('خط روند');
const box = await page.$eval('[data-testid="chart-host"]', (el) => {
  const r = el.getBoundingClientRect();
  return { x: r.x, y: r.y, w: r.width, h: r.height };
});
await page.mouse.move(box.x + box.w * 0.35, box.y + box.h * 0.55);
await page.mouse.down();
await page.mouse.move(box.x + box.w * 0.6, box.y + box.h * 0.35, { steps: 12 });
await page.mouse.up();
await sleep(700);
checks.push(await state('08-drawing'));

const technicalChecks = checks.filter((c) => c.label >= '02-technical');
const result = {
  generatedAt: new Date().toISOString(),
  cdp,
  checks,
  consoleErrors: errors,
  ok: technicalChecks.length >= 7
    && technicalChecks.every((c) => c.canvases > 0)
    && (checks.find((c) => c.label === '01-market')?.rows || 0) >= 20
    && errors.length === 0,
};
fs.writeFileSync(path.join(out, 'result.json'), JSON.stringify(result, null, 2));
console.log(JSON.stringify(result, null, 2));
await browser.disconnect();
