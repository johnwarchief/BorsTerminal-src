/**
 * tools/rtl_chain_geometry_probe.mts — هندسۀِ بصریِ زنجیرۀ «افزودن فیلتر» درِ RTL
 *
 * دو نماد به زنجیره اضافه می‌شود، ترتیبِ DOM در برابرِ موقعیتِ xِ هر جزء نوشته
 * می‌شود، و اسکرین‌شاتِ خودِ خط می‌ماند. حدس در کار نیست: اگر «گام ۱» سمتِ چپِ
 * «گام ۲» بیفتد، ترتیبِ بصری با ترتیبِ منطقیِ فارسی (راست‌به‌چپ) وارونه است.
 *
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types \
 *     tools/rtl_chain_geometry_probe.mts --url http://127.0.0.1:8002/ --out _audit/tmp/rtl_chain
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
const OUT = arg('out', '_audit/tmp/rtl_chain');
const WAIT = Number.parseInt(arg('wait', '12000'), 10);

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 }, deviceScaleFactor: 2 });
await ctx.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* noop */
  }
});
const page = await ctx.newPage();
await page.goto(`${BASE}/#/master`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(WAIT);

const out: Record<string, unknown> = { base: BASE, at: new Date().toISOString() };

// presetِ Custom تا سازندۀ زنجیره دیده شود
try {
  const custom = page.locator('button:has-text("Custom"), button:has-text("سفارشی")').first();
  await custom.click({ timeout: 5000 });
  await page.waitForTimeout(2500);
} catch (e) {
  out.customPresetError = String(e).slice(0, 160);
}

const builder = page.locator('[data-testid="funnel-custom-builder"]').first();
out.builderVisible = (await builder.count()) > 0;

if (out.builderVisible) {
  await page.locator('[data-testid="funnel-chain-add"]').first().click();
  await page.waitForTimeout(500);
  for (const id of ['f_clock', 'f_jet', 'f_susp']) {
    const menu = page.locator('[data-testid="funnel-chain-menu"]');
    if (!(await menu.count())) {
      await page.locator('[data-testid="funnel-chain-add"]').first().click();
      await page.waitForTimeout(400);
    }
    const pick = page.locator(`[data-testid="funnel-chain-pick-${id}"]`).first();
    if (await pick.count()) {
      await pick.click();
      await page.waitForTimeout(2200);
    }
  }
  out.geometry = await page.evaluate(() => {
    const row = document.querySelector('[data-testid="funnel-chain-row"]');
    if (!row) return null;
    const items = Array.from(row.children).map((el: any) => {
      const r = el.getBoundingClientRect();
      return {
        testid: el.getAttribute('data-testid') || el.tagName,
        text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 46),
        x: Math.round(r.x),
        right: Math.round(r.right),
      };
    });
    const parts = Array.from(row.querySelectorAll('[data-testid^="funnel-chain-"]:not([data-testid="funnel-chain-row"])')).map((el: any) => {
      const r = el.getBoundingClientRect();
      return { testid: el.getAttribute('data-testid'), text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 30), x: Math.round(r.x) };
    });
    return { rowDir: getComputedStyle(row).direction, items, parts, rowRect: { x: Math.round(row.getBoundingClientRect().x), w: Math.round(row.getBoundingClientRect().width) } };
  });
  await builder.screenshot({ path: `${OUT}-builder.png` });
  const note = await page.locator('[data-testid="funnel-chain-note"]').first().textContent().catch(() => null);
  out.noteText = note ? note.replace(/\s+/g, ' ').trim() : null;
}

// صفحۀ تابلو با دو چیپِ روشن: ترتیبِ بصریِ چیپ‌ها و «و»یِ ضمنی
await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(WAIT);
for (const label of ['الگوی ساعت', 'حجم مشکوک']) {
  await page.locator(`[data-testid="quick-filters-bar"] button[aria-pressed]:has-text("${label}")`).first().click();
  await page.waitForTimeout(900);
}
out.tapeBar = await page.evaluate(() => {
  const bar = document.querySelector('[data-testid="market-filters-bar"]');
  if (!bar) return null;
  const items = Array.from(bar.querySelectorAll('[data-testid="quick-filters-bar"] > *')).map((el: any) => {
    const r = el.getBoundingClientRect();
    return { text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 34), x: Math.round(r.x), pressed: el.getAttribute?.('aria-pressed') };
  });
  return { dir: getComputedStyle(bar).direction, items };
});
await page.locator('[data-testid="market-filters-bar"]').first().screenshot({ path: `${OUT}-tapebar.png` });
await page.screenshot({ path: `${OUT}-master-full.png`, fullPage: false });

mkdirSync('_audit/tmp', { recursive: true });
writeFileSync(`${OUT}.json`, JSON.stringify(out, null, 2), 'utf-8');
console.log('WROTE', `${OUT}.json`);
await browser.close();
