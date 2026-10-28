import { pathToFileURL } from 'node:url';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const PW = 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package/node_modules/playwright/index.mjs';
const CHROME = 'C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const OUT = dirname(fileURLToPath(import.meta.url));
const { chromium } = await import(pathToFileURL(PW).href);
const browser = await chromium.launch({ executablePath: CHROME, headless: true });
for (const [w, h] of [[1920, 1080], [2560, 1440]]) {
  const page = await (await browser.newContext({ viewport: { width: w, height: h } })).newPage();
  await page.goto('http://127.0.0.1:5180/#/market', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="board-row"]', { timeout: 40000 });
  await page.waitForSelector('[data-testid="snapshot-strip"]', { timeout: 20000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(OUT, `ws-${w}.png`) });
  const boxes = await page.evaluate(() => ({
    strip: document.querySelector('[data-testid="snapshot-strip"]')?.getBoundingClientRect().height,
    tiles: [...document.querySelectorAll('[data-tile-id]')].map((el) => {
      const r = el.getBoundingClientRect();
      return { id: el.getAttribute('data-tile-id'), w: Math.round(r.width), h: Math.round(r.height) };
    }),
  }));
  console.log(w, JSON.stringify(boxes));
  await page.close();
}
await browser.close();
