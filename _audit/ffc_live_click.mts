/**
 * _audit/ffc_live_click.mts — سنجشِ زندهٔ «موتور دوم» با همان Chromium محلی
 *
 * jev_ui_check با `[title=…]` کلیک می‌کند و آن انتخابگر اینجا صفر شد، پس این
 * اسکریپت مستقیم با testid کلیک می‌کند و سه چیز را گزارش می‌دهد: آیا پنلِ FFC
 * بالا آمد (WebGL2 در این مرورگر هست یا نه)، چند کندل/لایه رسم شد، و متنِ
 * صادقانۀ پایینِ پنل چیست. فقط localhost — هیچ متنِ پروژه‌ای بیرون نمی‌رود.
 */
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);

const BASE = process.env.JEV_BASE ?? 'http://127.0.0.1:8013/';
const ROUTE = process.env.JEV_ROUTE ?? '#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF';
const CHROME = process.env.JEV_CHROME ?? '';

const browser = await chromium.launch({
  ...(CHROME ? { executablePath: CHROME } : {}),
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
const errs: string[] = [];
page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 160)); });

await page.addInitScript(() => { try { sessionStorage.setItem('bors_auth_session', 'true'); } catch {} });
await page.goto(BASE + ROUTE, { waitUntil: 'load' });
await page.waitForTimeout(9000);

const titles = await page.$$eval('[data-testid^="nn-engine-"]', (els) =>
  els.map((e) => ({ id: e.getAttribute('data-testid'), title: e.getAttribute('title'), text: e.textContent })));
console.log('ENGINE BUTTONS', JSON.stringify(titles, null, 1));

const webgl2 = await page.evaluate(() => {
  const c = document.createElement('canvas');
  return !!(c.getContext('webgl2'));
});
console.log('WEBGL2 in this browser:', webgl2);

await page.click('[data-testid="nn-engine-ffc"]');
await page.waitForTimeout(9000);

const pane = await page.evaluate(() => {
  const root = document.querySelector('[data-testid="fts-engine-chart"]');
  if (!root) return { present: false };
  const host = document.querySelector('[data-testid="fts-engine-host"]');
  const err = document.querySelector('[data-testid="fts-engine-error"]');
  const status = root.querySelector('div:last-child');
  const canvases = Array.from((host ?? root).querySelectorAll('canvas'))
    .map((c) => ({ w: c.width, h: c.height }));
  return {
    present: true,
    canvases,
    error: err ? err.textContent : null,
    status: status ? status.textContent : null,
    hostBox: host ? { w: host.clientWidth, h: host.clientHeight } : null,
  };
});
console.log('FFC PANE', JSON.stringify(pane, null, 1));
await page.screenshot({ path: '_audit/ffc_live_click.png', fullPage: false });

// بازگشت به موتورِ اصلی هم باید همان‌جا در دسترس باشد
const back = await page.$('[data-testid="fts-engine-back"]');
console.log('BACK BUTTON present:', !!back);
if (back) {
  await back.click();
  await page.waitForTimeout(6000);
  const nn = await page.$('[data-testid="nn-chart-host"]');
  console.log('KLineCharts host back:', !!nn);
}

console.log('CONSOLE ERRORS', JSON.stringify(errs.slice(0, 6), null, 1));
await browser.close();
