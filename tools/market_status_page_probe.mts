/**
 * tools/market_status_page_probe.mts — اثباتِ زندهٔ صفحۀ «وضعیت بازار»
 *
 * از ناوبری واقعی کلیک می‌کند (نه بازکردنِ مستقیمِ آدرس)، مسیرِ تازه، شمارش‌هایِ
 * واقعیِ هر بلوک، و نبودِ سرریزِ افقی در ۱۳۶۶×۷۶۸ و ۱۹۲×۱۰۸۰ سنجیده می‌شود.
 * خروجی JSONِ همین پروب است + اسکرین‌شات.
 *
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types \
 *     tools/market_status_page_probe.mts --url http://127.0.0.1:8002/ --out _audit/tmp/status_page
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const BASE = arg('url', 'http://127.0.0.1:8002/').replace(/\/$/, '');
const OUT = arg('out', '_audit/tmp/status_page');
const WAIT = Number.parseInt(arg('wait', '13000'), 10);

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });

const SNAP = () => {
  const de = document.documentElement;
  const ids = [
    'market-status-page',
    'market-status-panel',
    'market-pulse-bar',
    'status-histogram',
    'status-clientsplit',
    'status-phases',
    'status-industries',
    'status-mainwatch',
  ];
  const blocks: Record<string, unknown> = {};
  for (const id of ids) {
    const el = document.querySelector(`[data-testid="${id}"]`);
    if (!el) {
      blocks[id] = null;
      continue;
    }
    const r = el.getBoundingClientRect();
    blocks[id] = {
      h: Math.round(r.height),
      w: Math.round(r.width),
      text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120),
    };
  }
  return {
    hash: window.location.hash,
    overflowX: de.scrollWidth - de.clientWidth,
    blocks,
    bucketCount: document.querySelectorAll('[data-testid^="histo-bucket-"]').length,
    industryRows: document.querySelectorAll('[data-testid^="industry-row-"]').length,
    mainwatchRows: document.querySelectorAll('[data-testid^="mainwatch-row-"]').length,
    loading: document.querySelectorAll('[data-testid$="-loading"]').length,
    errors: Array.from(document.querySelectorAll('[data-testid$="-error"]')).map((e) => e.getAttribute('data-testid')),
    navActive: Array.from(document.querySelectorAll('nav a[aria-label]')).map((a) => ({
      label: a.getAttribute('aria-label'),
      cls: (a.className || '').includes('text-accent-blue') ? 'active' : 'idle',
    })),
  };
};

const out: Record<string, unknown> = { base: BASE, at: new Date().toISOString(), runs: {} };
mkdirSync('_audit/tmp', { recursive: true });

for (const [w, h] of [[1366, 768], [1920, 1080]] as const) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h } });
  await ctx.addInitScript(() => {
    try {
      sessionStorage.setItem('bors_auth_session', 'true');
    } catch {
      /* noop */
    }
  });
  const page = await ctx.newPage();
  const consoleErrors: string[] = [];
  page.on('console', (m: any) => {
    if (m.type() === 'error') consoleErrors.push(String(m.text()).slice(0, 200));
  });
  const rec: Record<string, unknown> = {};

  // ۱) از ناوبری: تابلو → کلیکِ «وضعیت بازار»
  await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(WAIT);
  const nav = page.locator('nav a[aria-label="وضعیت بازار"]').first();
  rec.navLinkFound = (await nav.count()) > 0;
  if (rec.navLinkFound) {
    await nav.click();
    await page.waitForTimeout(4000);
  }
  rec.afterNav = await page.evaluate(SNAP);
  await page.screenshot({ path: `${OUT}-${w}.png` });

  // ۲) برگشت به تابلو و دوباره ورود (مسیرِ رفت‌وبرگشت)
  await page.locator('nav a[aria-label="تابلوخوانی/بازار"]').first().click();
  await page.waitForTimeout(2500);
  rec.backToMarket = await page.evaluate(SNAP);
  await page.goto(`${BASE}/#/market-status`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);
  rec.directUrl = await page.evaluate(SNAP);
  rec.consoleErrors = consoleErrors.slice(0, 6);
  (out.runs as Record<string, unknown>)[`${w}x${h}`] = rec;
  await ctx.close();
}

writeFileSync(`${OUT}.json`, JSON.stringify(out, null, 2), 'utf-8');
console.log('WROTE', `${OUT}.json`);
await browser.close();
