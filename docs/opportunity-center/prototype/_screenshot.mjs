import { chromium } from 'playwright-core';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const shots = resolve(here, 'evidence');
mkdirSync(shots, { recursive: true });
const exe = process.env.CHROMIUM_PATH || 'C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const url = process.env.PROTOTYPE_URL || 'http://127.0.0.1:8765/';

const browser = await chromium.launch({ headless: true, executablePath: exe });
const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text()}`); });
page.on('pageerror', (e) => { errors.push(`pageerror: ${e.message}`); console.log('PAGEERROR_STACK', e.stack); });
await page.goto(url, { waitUntil: 'load' });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(400);

const shot = (name) => page.screenshot({ path: resolve(shots, name) });
const metrics = async (label) => {
  const m = await page.evaluate(() => ({
    view: document.querySelector('.view.active')?.dataset.panel,
    inner: [window.innerWidth, window.innerHeight],
    docScrollW: document.documentElement.scrollWidth,
    bodyScrollW: document.body.scrollWidth,
    overflowX: document.documentElement.scrollWidth > window.innerWidth,
    font: document.fonts.check('12.5px Vazirmatn'),
    rows: document.querySelectorAll('#opp-body tr').length,
    inspector: getComputedStyle(document.querySelector('.inspector')).display,
    selected: document.querySelectorAll('#opp-body tr.selected').length,
  }));
  console.log(label, JSON.stringify({ ...m, consoleErrors: errors.length }));
};

await metrics('1366-today');
await shot('1366x768-today.png');
await page.click('#opp-body tr[data-i="0"]');
await page.waitForTimeout(250);
await metrics('1366-detail');
await shot('1366x768-detail.png');
await page.keyboard.press('Escape');
await page.waitForTimeout(150);
await page.click('.nav-item[data-view="library"]');
await page.waitForTimeout(150);
await shot('1366x768-library.png');
await page.click('.nav-item[data-view="lab"]');
await page.waitForTimeout(150);
await shot('1366x768-lab.png');

await page.setViewportSize({ width: 1920, height: 1080 });
await page.click('.nav-item[data-view="today"]');
await page.waitForTimeout(300);
await metrics('1920-today');
await shot('1920x1080-today.png');
await page.click('.nav-item[data-view="library"]');
await page.waitForTimeout(150);
await shot('1920x1080-library.png');
await page.click('.nav-item[data-view="lab"]');
await page.waitForTimeout(150);
await shot('1920x1080-lab.png');
await page.click('.nav-item[data-view="compare"]');
await page.waitForTimeout(150);
await shot('1920x1080-compare.png');
await page.click('.nav-item[data-view="monitor"]');
await page.waitForTimeout(150);
await shot('1920x1080-monitor.png');

console.log('errors', JSON.stringify(errors));
await browser.close();
