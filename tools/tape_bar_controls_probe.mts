/**
 * tools/tape_bar_controls_probe.mts — سنجشِ تک‌تکِ کنترل‌هایِ نوارِ بالایِ جدول
 *
 * هر کنترلِ دیدنیِ نوار (منوی بازارها، صنایع، فقط‌زنده، پسوندِ عددی، بازۀ
 * به‌روزرسانی، جستجو، چیپ‌ها، ⚙ها، پاک‌کردن) یک‌بار operated می‌شود و شمارندۀ
 * «X از Y» + تعدادِ ردیفِ رندرشده + متنِ حالتِ فعال پیش/پس ثبت می‌شود. چیزی که
 * هیچ‌کدام را عوض نکند «بی‌اثر» گزارش می‌شود — حدس در کار نیست.
 *
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types \
 *     tools/tape_bar_controls_probe.mts --url http://127.0.0.1:8001/ --out _audit/tmp/bar_controls.json
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
const BASE = arg('url', 'http://127.0.0.1:8001/');
const OUT = arg('out', '_audit/tmp/bar_controls.json');
const WAIT = Number.parseInt(arg('wait', '13000'), 10);

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
const errors: string[] = [];
page.on('console', (m: any) => {
  if (m.type() === 'error') errors.push(String(m.text()).slice(0, 200));
});

await page.goto(`${BASE.replace(/\/$/, '')}#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(WAIT);

const STATE = () => {
  const counter = document.querySelector('[title="تعداد نمادهای فعال در جدول"]');
  const rows = Array.from(document.querySelectorAll('[data-testid="tape-row"]')).slice(0, 40);
  const firstCol = rows.map((r) => (r.textContent || '').trim().slice(0, 12));
  const toggles = Array.from(
    document.querySelectorAll(
      '[data-testid="live-only-toggle"],[data-testid="numeric-suffix-toggle"],[data-testid="asset-filter"] button',
    ),
  ).map((b: any) => ({
    id: b.getAttribute('data-testid') || '',
    label: (b.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 30),
    cls: (b.className || '').includes('accent-blue') ? 'active-looking' : 'idle',
    pressed: b.getAttribute('aria-pressed'),
  }));
  const sectorSel = document.querySelector('select[aria-label*="صنعت"], select#sector, [data-testid="sector-select"] select');
  const poll = document.querySelector('select#poll-ms');
  return {
    shown: counter ? (counter.textContent || '').replace(/\s+/g, ' ').trim() : null,
    rendered: document.querySelectorAll('[data-testid="tape-row"]').length,
    firstCol,
    toggles,
    sector: sectorSel ? (sectorSel as HTMLSelectElement).value : null,
    poll: poll ? (poll as HTMLSelectElement).value : null,
  };
};

const read = () => page.evaluate(STATE);
const out: Record<string, unknown> = { base: BASE, at: new Date().toISOString(), controls: {} };
const before = await read();
out.before = before;

const record = async (name: string, fn: () => Promise<void>) => {
  const entry: Record<string, unknown> = { attempted: true };
  try {
    await fn();
    await page.waitForTimeout(1200);
    const after = await read();
    entry.shownBefore = before.shown;
    entry.shownAfter = after.shown;
    entry.changedCount = before.shown !== after.shown;
    entry.changedFirstRows = JSON.stringify(before.firstCol) !== JSON.stringify(after.firstCol);
    entry.after = after;
  } catch (e) {
    entry.error = String(e).slice(0, 220);
  }
  (out.controls as Record<string, unknown>)[name] = entry;
  return entry;
};

// ۱) «فقط زنده»
await record('live-only', async () => {
  await page.locator('[data-testid="live-only-toggle"]').first().click();
});
await page.locator('[data-testid="live-only-toggle"]').first().click().catch(() => {});
await page.waitForTimeout(800);

// ۲) «حذفِ پسوندِ عددی»
await record('numeric-suffix', async () => {
  await page.locator('[data-testid="numeric-suffix-toggle"]').first().click();
});
await page.locator('[data-testid="numeric-suffix-toggle"]').first().click().catch(() => {});
await page.waitForTimeout(800);

// ۳) منوی «بازارها / ابزارها»: خاموش‌کردنِ یک نوع دارایی
await record('asset-menu', async () => {
  await page.locator('[data-testid="asset-filter"]').first().click();
  await page.waitForTimeout(600);
  const chips = page.locator('[data-testid="asset-filter-menu"] button');
  const n = await chips.count();
  out.assetMenuOptions = n;
  if (n > 0) await chips.nth(0).click({ timeout: 4000 });
});
await page.keyboard.press('Escape').catch(() => {});
await page.waitForTimeout(600);

// ۴) «بازه: ۵ ثانیه» — فقط تنظیمِ پس‌زمینه؛ اثرِ دیدنی انتظار نمی‌رود
await record('poll-interval', async () => {
  await page.selectOption('select#poll-ms', '60000', { timeout: 4000 });
});
await page.selectOption('select#poll-ms', '5000').catch(() => {});

// ۵) جستجو
await record('search', async () => {
  await page.fill('input[placeholder*="جستجو"]', 'فولاد', { timeout: 4000 });
});
await page.fill('input[placeholder*="جستجو"]', '').catch(() => {});
await page.waitForTimeout(700);

// ۶) صنایع (select)
await record('sector', async () => {
  const sel = page.locator('select[aria-label="فیلتر صنعت"]').first();
  const opts = await sel.locator('option').allTextContents();
  out.sectorOptions = opts.length;
  if (opts.length <= 1) throw new Error('sector select has no options');
  await sel.selectOption({ index: 2 });
});
await page.reload({ waitUntil: 'domcontentloaded' });
await page.waitForTimeout(WAIT);

// ۷) «پاک کردن» پس از فعال‌کردنِ دو چیپ
await record('reset-button', async () => {
  await page
    .locator('[data-testid="quick-filters-bar"] button[aria-pressed]:has-text("حجم مشکوک")')
    .first()
    .click();
  await page.waitForTimeout(700);
  await page
    .locator('[data-testid="quick-filters-bar"] button[aria-pressed]:has-text("فیلتر جت")')
    .first()
    .click();
  await page.waitForTimeout(900);
  const mid = await read();
  out.resetButton = { withTwoChips: mid.shown };
  await page.locator('[data-testid="filters-reset"]').first().click({ timeout: 4000 });
});

out.errors = errors.slice(0, 8);
mkdirSync('_audit/tmp', { recursive: true });
writeFileSync(OUT, JSON.stringify(out, null, 2), 'utf-8');
console.log('WROTE', OUT);
await browser.close();
