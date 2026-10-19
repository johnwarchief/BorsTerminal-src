// tools/merged_pages_ui_sweep.mts — نگاهِ زنده به صفحه‌هایی که ادغامِ System 1+2 عوض کرد
//
// چرا: آزمون‌هایِ jsdom (۱۹۸ تا) منطق را می‌سنجند؛ این سنجه فقط یک چیز را
// می‌سنجد — که صفحه درِ مرورگرِ واقعی بالا می‌آید، دادهٔ زندهٔ همان بک‌اند را
// نشان می‌دهد، خطایِ کنسول یا پاسخِ ۴xx/۵xx نمی‌دهد، و ارتفاعِ صفحه ازِ حدِ
// معقول بیرون نمی‌زند. رأیِ «درست دیده می‌شود» باِ مالک است، نه باِ این فایل؛
// این‌جا فقط «خراب نشده» سنجیده می‌شود و تصویرِ همان لحظه رویِ دیسک می‌ماند.
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { readRoutes } from './qa_routes.mts';

const PKG = process.env.JEV_BROWSER_DIR
  || 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package/node_modules/playwright/index.mjs';
const BASE = process.argv[2] || 'http://127.0.0.1:8173/';
const OUT = process.env.JEV_OUT_DIR || 'C:/Users/PCMOD/Desktop/_bors-sarkhati-jev/_audit/merged-ui-sweep';
mkdirSync(OUT, { recursive: true });

const { chromium } = await import(pathToFileURL(PKG).href);
const browser = await chromium.launch({ headless: true,
  executablePath: process.env.JEV_CHROME || undefined });

/**
 * نشانه‌هایِ «دادهٔ زنده رسید» — فقط *نامِ* مسیر اینجا هست، فهرستِ مسیرها از
 * `tools/qa_routes.mts` خوانده می‌شود (گاردِ `dev/qa_routes_guard.py` جدولِ دستی
 * را قرمز می‌کند؛ نسخهٔ اولِ همین فایل قرمز کرد و به‌همین دلیل اصلاح شد).
 * مسیری که درِ این نقشه نیست هم سنجیده می‌شود، ولی `probeExpected: false`
 * می‌خورد تا ادعایِ پوششِ نشانه دروغ نباشد.
 */
const PROBES: Record<string, string> = {
  'master': 'master-breadcrumb',
  'market': 'market-page',
  'market-status': 'market-status-page',
  'technical': 'chart-area',
  'fundamental': 'fundamental-page',
  'sarkhati': 'sarkhati-page',
};

const ROUTES = readRoutes('.').filter((r) => r.kind === 'page');

const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
await ctx.addInitScript(() => {
  try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* noop */ }
});

const rows: unknown[] = [];
for (const r of ROUTES) {
  const probe = PROBES[r.name] ?? null;
  const file = r.name.replace(/[^a-z0-9_-]/gi, '_');
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
  await page.goto(BASE + r.hash, { waitUntil: 'domcontentloaded' });
  const probeCount = probe ? await page.locator(`[data-testid="${probe}"]`).count() : null;
  await page.waitForTimeout(3500);
  const after = probe ? await page.locator(`[data-testid="${probe}"]`).count() : null;
  const metrics = await page.evaluate(() => ({
    docHeight: Math.round(document.documentElement.scrollHeight),
    mainHeight: (() => {
      const el = document.querySelector('.app-main') || document.querySelector('main');
      return el ? Math.round(el.getBoundingClientRect().height) : null;
    })(),
    testids: document.querySelectorAll('[data-testid]').length,
    rowsInTables: document.querySelectorAll('table tbody tr').length,
  })).catch(() => null);
  await page.screenshot({ path: `${OUT}/${file}.png`, fullPage: true });
  rows.push({ route: r.hash, name: r.name, probe, probeExpected: Boolean(probe), probeBeforeData: probeCount, probeAfterWait: after,
    loadMs: Date.now() - started, metrics,
    consoleErrors: [...new Set(errors)].slice(0, 6),
    httpFailures: [...new Set(bad)].slice(0, 8),
    externalRequests: [...new Set(external)].slice(0, 5),
    shot: `${file}.png` });
  await page.close();
}

await browser.close();
writeFileSync(`${OUT}/MERGED_UI_SWEEP.json`, JSON.stringify({ base: BASE, at: new Date().toISOString(), rows }, null, 2));
console.log(JSON.stringify(rows, null, 1).slice(0, 4500));
