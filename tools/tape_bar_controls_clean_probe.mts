/**
 * tools/tape_bar_controls_clean_probe.mts — اثرِ تک‌تکِ کنترل‌هایِ نوار، بی‌آلودگیِ حالت
 *
 * هر کنترل از حالتِ تازه (reload + پاک‌کردنِ localStorage) operated می‌شود تا شمارۀ
 * «X از Y» واقعاً جوابِ همان یک کلیک باشد؛ پس از آن دوباره reload می‌شود.
 *
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types \
 *     tools/tape_bar_controls_clean_probe.mts --url http://127.0.0.1:8002/
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
const OUT = arg('out', '_audit/tmp/bar_clean.json');
const WAIT = Number.parseInt(arg('wait', '12000'), 10);

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
await ctx.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* noop */
  }
});
const page = await ctx.newPage();

const STATE = () => {
  const counter = document.querySelector('[title="تعداد نمادهای فعال در جدول"]');
  const empty = Array.from(document.querySelectorAll('div,p,span'))
    .map((e) => (e.textContent || '').trim())
    .filter((t) => t && t.length < 90 && /ردیف|نیامد|خالی|بی‌داده|بدون داده|پیدا/.test(t))
    .slice(0, 3);
  const menuOpen = !!document.querySelector('[data-testid="asset-filter-menu"]');
  return {
    shown: counter ? (counter.textContent || '').replace(/\s+/g, ' ').trim() : null,
    rendered: document.querySelectorAll('[data-testid="tape-row"]').length,
    emptyText: empty,
    menuOpen,
  };
};
const read = () => page.evaluate(STATE);

const fresh = async () => {
  await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(WAIT);
  return read();
};

const out: Record<string, unknown> = { base: BASE, at: new Date().toISOString(), cases: [] };
out.baseline = await fresh();

const runCase = async (name: string, act: () => Promise<void>) => {
  const before = await fresh();
  const rec: Record<string, unknown> = { name, shownBefore: before.shown, renderedBefore: before.rendered };
  try {
    await act();
    await page.waitForTimeout(1300);
    const after = await read();
    rec.shownAfter = after.shown;
    rec.renderedAfter = after.rendered;
    rec.emptyText = after.emptyText;
    rec.changed = before.shown !== after.shown;
  } catch (e) {
    rec.error = String(e).slice(0, 180);
  }
  (out.cases as unknown[]).push(rec);
  console.log(name, '→', rec.shownBefore, '⇒', rec.shownAfter, rec.changed ? 'CHANGED' : 'NO-CHANGE', rec.error || '');
};

// ۱) چیپ «فقط بازار پایه» داخل منوی بازارها
await runCase('asset-preset: فقط بازار پایه', async () => {
  await page.locator('[data-testid="asset-filter"]').first().click();
  await page.waitForTimeout(500);
  await page.locator('[data-testid="asset-filter-menu"] button:has-text("فقط بازار پایه")').first().click();
});

// ۲) چیپ «فقط سهام بورس/فرابورس»
await runCase('asset-preset: فقط سهام بورس/فرابورس', async () => {
  await page.locator('[data-testid="asset-filter"]').first().click();
  await page.waitForTimeout(500);
  await page.locator('[data-testid="asset-filter-menu"] button:has-text("فقط سهام بورس/فرابورس")').first().click();
});

// ۳) چیپ «همه»
await runCase('asset-menu: همه', async () => {
  await page.locator('[data-testid="asset-filter"]').first().click();
  await page.waitForTimeout(500);
  await page.locator('[data-testid="asset-filter-menu"] button:has-text("همه")').first().click();
});

// ۴) تیکِ یک نوع دارایی (اختیار معامله)
await runCase('asset-checkbox: اختیار معامله', async () => {
  await page.locator('[data-testid="asset-filter"]').first().click();
  await page.waitForTimeout(500);
  await page.locator('[data-testid="asset-filter-menu"] input[aria-label="اختیار معامله"]').first().click({ force: true });
});

// ۵) صنایع
await runCase('sector: اولین صنعتِ فهرست', async () => {
  const sel = page.locator('select[aria-label="فیلتر صنعت"]').first();
  await sel.selectOption({ index: 2 });
});

// ۶) فقط زنده
await runCase('toggle: فقط زنده (خاموش)', async () => {
  await page.locator('[data-testid="live-only-toggle"]').first().click();
});

// ۷) حذفِ پسوندِ عددی
await runCase('toggle: حذفِ پسوندِ عددی (روشن)', async () => {
  await page.locator('[data-testid="numeric-suffix-toggle"]').first().click();
});

// ۸) جستجو
await runCase('search: فولاد', async () => {
  await page.fill('input[aria-label="جستجوی نماد"]', 'فولاد');
});

// ۹) بازۀ به‌روزرسانی
await runCase('poll: ۵ ثانیه ← ۱ دقیقه', async () => {
  await page.selectOption('select#poll-ms', '60000');
});

// ۱۰) «باز کردنِ نمودارها» (MicroChartsDrawer)
await runCase('drawer: نمودارهای جریان سفارش‌ها', async () => {
  const btn = page.locator('button:has-text("باز کردن نمودارها"), button:has-text("باز کردنِ نمودارها")').first();
  await btn.click({ timeout: 4000 });
});

// ۱۱) چیپ‌های پنج‌گانه: شمارۀ وعده در برابرِ نتیجه (تطبیقِ عددی)
for (const label of ['الگوی ساعت', 'حجم مشکوک', 'فیلتر جت', 'کف‌روبی', 'نقطه زنی', 'ورود پول هوشمند', 'کد به کد حقوقی به حقیقی']) {
  await runCase(`chip: ${label}`, async () => {
    const chip = page.locator(`[data-testid="quick-filters-bar"] button[aria-pressed]:has-text("${label}")`).first();
    const txt = (await chip.textContent())?.replace(/\s+/g, ' ').trim() ?? '';
    const promised = txt.match(/\(\s*([\d\u06F0-\u06F9٬]+)\s*\)/);
    (out as any).__promised = promised ? promised[1] : null;
    await chip.click();
  });
  const last = (out.cases as Array<Record<string, unknown>>).slice(-1)[0];
  last.promised = (out as any).__promised;
  last.promiseMatchesResult = String(last.promised ?? '') === String(last.shownAfter ?? '').split('از')[0].trim();
}

mkdirSync('_audit/tmp', { recursive: true });
writeFileSync(OUT, JSON.stringify(out, null, 2), 'utf-8');
console.log('WROTE', OUT);
await browser.close();
