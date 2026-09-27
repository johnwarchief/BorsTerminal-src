/* _audit/tape_window_jev.mts — سنجشِ زندهٔ «پنجرۀ [ih]» درِ جدولِ واقعیِ تابلو
 *
 * چرا این پروب هست: گارد و ویتست منطق را ثابت می‌کنند، ولی هیچ‌کدام نمی‌گویند
 * رویِ مرورگرِ واقعی چیپ‌ها چه شماری نشان می‌دهند و آیا آن شمار با پرچم‌هایِ
 * سرور می‌خواند یا نه. سمتِ مرورگر آستانه‌هایِ کاربر را رویِ همان ستون‌ها
 * دوباره اجرا می‌کند، پس هر ناهمسانیِ «ستونِ نیامده / معنای عوض‌شده» اینجا
 * لو می‌رود. هیچ متنی به سرویسِ بیرونی نمی‌رود — فقط Playwright.
 *
 *   JEV_CHROME=... node --experimental-strip-types _audit/tape_window_jev.mts
 */
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { writeFileSync } from 'node:fs';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const require = createRequire(pathToFileURL(PKG + '/index.js').href);
const { chromium } = require('playwright');

const BASE = process.env.BORS_URL ?? 'http://127.0.0.1:8001/';
const FLAGS = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh'];
const CHIP = {
  f_clock: 'ساعت',
  f_susp: 'مشکوک',
  f_jet: 'جت',
  f_roobi: 'کف',
  f_noqteh: 'نقطه',
} as const;

const browser = await chromium.launch({
  executablePath: process.env.JEV_CHROME || undefined,
  args: ['--disable-dev-shm-usage'],
});
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
await ctx.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* دروازه فقط UI است */
  }
});
const page = await ctx.newPage();
const errors: string[] = [];
page.on('console', (m) => {
  if (m.type() === 'error') errors.push(m.text().slice(0, 200));
});
page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`.slice(0, 200)));

await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(16000);

/** شمارشِ سرور از خودِ /api/market، درِ همان مرورگر (همان مسیری که UI می‌رود) */
const server = await page.evaluate(async (flags: string[]) => {
  const r = await fetch('/api/market', { headers: { Accept: 'application/json' } });
  const j = await r.json();
  const rows: Record<string, unknown>[] =
    (j as { rows?: Record<string, unknown>[] }).rows ??
    Object.values(j as Record<string, unknown>).find(
      (v) => Array.isArray(v) && v.length && (v[0] as Record<string, unknown>).symbol,
    ) as Record<string, unknown>[];
  const live = rows.filter((x) => x.is_live === true);
  // پایهٔ چیپ‌ها درِ MarketPage: ردیف‌هایِ زنده، بی‌نامِ پسوندعددی (قاعدهٔ خودکارِ تابلو)
  const base = live.filter((x) => !/[0-9۰-۹]$/.test(String(x.symbol ?? '').trim()));
  const count = (set: Record<string, unknown>[]) => {
    const out: Record<string, number> = { _n: set.length };
    for (const f of flags) out[f] = set.filter((x) => x[f] === true).length;
    return out;
  };
  const out: Record<string, unknown> = { all: rows.length, live: count(live), base: count(base) };
  out._base_sessions60 = base.filter((x) => Number(x.hist_sessions) >= 60).length;
  out._base_hasVolumeRatio = base.filter((x) => typeof x.vol_ratio_file === 'number').length;
  out._droppedNumericSuffix = live.filter((x) => /[0-9۰-۹]$/.test(String(x.symbol ?? '').trim())).length;
  return out;
}, FLAGS);

/** چیپ‌ها و شمارِ رویِ آن‌ها، آن‌طور که کاربر می‌بیند */
const chips = await page.evaluate((labels: Record<string, string>) => {
  const bar = document.querySelector('[data-testid="quick-filters-bar"]');
  const seen: Record<string, string | null> = {};
  for (const key of Object.keys(labels)) {
    const hit = Array.from(bar?.querySelectorAll('button') ?? []).find((b) =>
      (b.textContent ?? '').includes(labels[key]),
    );
    seen[key] = hit
      ? `${(hit.textContent ?? '').replace(/\s+/g, ' ').trim()} ⟵ ${hit.getAttribute('title') ?? ''}`
      : null;
  }
  return seen;
}, CHIP);

/** کلیکِ تک‌تکِ چیپ‌ها و شمارِ ردیفی که جدول واقعاً نشان می‌دهد */
const SHOWN = '[data-testid="market-filters-bar"] [title="تعداد نمادهای فعال در جدول"]';
const clicked: Record<string, { chip: string; shown: string }> = {};
for (const f of FLAGS) {
  const label = CHIP[f as keyof typeof CHIP];
  const btn = page
    .locator('[data-testid="quick-filters-bar"] button')
    .filter({ hasText: label })
    .first();
  if ((await btn.count()) === 0) {
    clicked[f] = { chip: 'NOT FOUND', shown: '-' };
    continue;
  }
  await btn.click();
  await page.waitForTimeout(2600);
  const box = page.locator(SHOWN).first();
  clicked[f] = {
    chip: (await btn.textContent())?.replace(/\s+/g, ' ').trim() ?? '',
    shown: (await box.count()) ? (await box.innerText()).replace(/\s+/g, ' ').trim() : 'NO COUNTER',
  };
  await btn.click();
  await page.waitForTimeout(1500);
}

const rowsShown = await page.evaluate((sel: string) => {
  const box = document.querySelector(sel);
  return box ? (box.textContent ?? '').replace(/\s+/g, ' ').trim() : 'NO COUNTER';
}, SHOWN);
const shot = '_audit/tape_window_jev.png';
await page.screenshot({ path: shot });
await browser.close();

const report = { base: BASE, server, chips, clicked, rowsShown, consoleErrors: errors.slice(0, 12), shot };
writeFileSync('_audit/tape_window_jev.json', JSON.stringify(report, null, 1), 'utf8');
console.log(JSON.stringify(report, null, 1));
