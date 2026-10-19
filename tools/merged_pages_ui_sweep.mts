// tools/merged_pages_ui_sweep.mts — نگاهِ زنده به صفحه‌هایی که ادغامِ System 1+2 عوض کرد
//
// چرا: آزمون‌هایِ jsdom (۱۹۸ تا) منطق را می‌سنجند؛ این سنجه فقط یک چیز را
// می‌سنجد — که صفحه درِ مرورگرِ واقعی بالا می‌آید، دادهٔ زندهٔ همان بک‌اند را
// نشان می‌دهد، خطایِ کنسول یا پاسخِ ۴xx/۵xx نمی‌دهد، و ارتفاعِ صفحه ازِ حدِ
// معقول بیرون نمی‌زند. رأیِ «درست دیده می‌شود» باِ مالک است، نه باِ این فایل؛
// این‌جا فقط «خراب نشده» سنجیده می‌شود و تصویرِ همان لحظه رویِ دیسک می‌ماند.
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  || 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package/node_modules/playwright/index.mjs';
const BASE = process.argv[2] || 'http://127.0.0.1:8173/';
const OUT = process.env.JEV_OUT_DIR || 'C:/Users/PCMOD/Desktop/_bors-sarkhati-jev/_audit/merged-ui-sweep';
mkdirSync(OUT, { recursive: true });

const { chromium } = await import(pathToFileURL(PKG).href);
const browser = await chromium.launch({ headless: true,
  executablePath: process.env.JEV_CHROME || undefined });

/** نشانه‌هایِ «دادهٔ زنده رسید» درِ هر صفحه — ازِ خودِ مؤلفه‌ها، نه حدس. */
const ROUTES: Array<{ route: string; probe: string; file: string }> = [
  { route: '#/master', probe: 'fts-funnel-workspace', file: '01-master' },
  { route: '#/market', probe: 'market-page', file: '02-market' },
  { route: '#/market-status', probe: 'market-status-page', file: '03-market-status' },
  { route: '#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF', probe: 'chart-area', file: '04-technical' },
  { route: '#/fundamental/%D9%81%D9%88%D9%84%D8%A7%D8%AF', probe: 'fundamental-page', file: '05-fundamental' },
  { route: '#/sarkhati', probe: 'sarkhati-page', file: '06-sarkhati' },
];

const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
await ctx.addInitScript(() => {
  try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* noop */ }
});

const rows: unknown[] = [];
for (const r of ROUTES) {
  const page = await ctx.newPage();
  const errors: string[] = [];
  const bad: string[] = [];
  const external: string[] = [];
  page.on('console', (m: { type: () => string; text: () => string }) => {
    if (m.type() === 'error') errors.push(String(m.text()).slice(0, 180));
  });
  page.on('pageerror', (e: Error) => errors.push('pageerror: ' + String(e).slice(0, 180)));
  page.on('response', (x: { status: () => number; url: () => string }) => {
    if (x.status() >= 400) bad.push(`${x.status()} ${x.url().slice(0, 110)}`);
  });
  page.on('request', (x: { url: () => string }) => {
    const u = x.url();
    if (!/^https?:\/\/(127\.0\.0\.1|localhost)(:|\/)/.test(u)) external.push(u);
  });
  const started = Date.now();
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.locator('[data-testid="nav-sarkhati"], [data-testid="nav-market"]').first()
    .waitFor({ timeout: 30000 }).catch(() => null);
  await page.goto(BASE + r.route, { waitUntil: 'domcontentloaded' });
  const probeCount = await page.locator(`[data-testid="${r.probe}"]`).count();
  await page.waitForTimeout(3500);
  const after = await page.locator(`[data-testid="${r.probe}"]`).count();
  const metrics = await page.evaluate(() => ({
    docHeight: Math.round(document.documentElement.scrollHeight),
    mainHeight: (() => {
      const el = document.querySelector('.app-main') || document.querySelector('main');
      return el ? Math.round(el.getBoundingClientRect().height) : null;
    })(),
    testids: document.querySelectorAll('[data-testid]').length,
    rowsInTables: document.querySelectorAll('table tbody tr').length,
  })).catch(() => null);
  await page.screenshot({ path: `${OUT}/${r.file}.png`, fullPage: true });
  rows.push({ route: r.route, probe: r.probe, probeBeforeData: probeCount, probeAfterWait: after,
    loadMs: Date.now() - started, metrics,
    consoleErrors: [...new Set(errors)].slice(0, 6),
    httpFailures: [...new Set(bad)].slice(0, 8),
    externalRequests: [...new Set(external)].slice(0, 5),
    shot: `${r.file}.png` });
  await page.close();
}

await browser.close();
writeFileSync(`${OUT}/MERGED_UI_SWEEP.json`, JSON.stringify({ base: BASE, at: new Date().toISOString(), rows }, null, 2));
console.log(JSON.stringify(rows, null, 1).slice(0, 4500));
