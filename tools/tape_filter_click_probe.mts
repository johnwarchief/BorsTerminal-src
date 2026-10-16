/**
 * tools/tape_filter_click_probe.mts — اثباتِ زندهٔ «کلیکِ هر فیلترِ نوار تابلو چه می‌کند»
 *
 * برای هر چیپ: شمارندۀ «X از Y» (تعدادِ ردیفِ واقعیِ جدول) پیش و پس از کلیک، وعدۀ
 * نوشتۀ خودِ چیپ، حالتِ aria-pressed، و اثرِ تغییرِ آستانه در پاپ‌اور ⚙ ثبت می‌شود.
 * خروجی فقط JSONِ خودِ مرورگر است — شاهدِ بیرونی ندارد.
 *
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types \
 *     tools/tape_filter_click_probe.mts --url http://127.0.0.1:8002/ --out _audit/tmp/tape_click.json
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';

const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const BASE = arg('url', 'http://127.0.0.1:8002/');
const OUT = arg('out', '_audit/tmp/tape_click.json');
const WAIT = Number.parseInt(arg('wait', '14000'), 10);
const WIDTH = Number.parseInt(arg('width', '1366'), 10);

const { chromium } = await imp('node_modules/playwright/index.mjs');
const CHROME = process.env.JEV_CHROME ?? '';
const launchOpts: Record<string, unknown> = {};
if (CHROME) launchOpts.executablePath = CHROME;

const CHIPS = [
  'الگوی ساعت',
  'حجم مشکوک',
  'فیلتر جت',
  'کف‌روبی',
  'نقطه زنی',
  'ورود پول هوشمند',
  'کد به کد حقوقی به حقیقی',
];

const PROBE_STATE = () => {
  const counter = document.querySelector('[title="تعداد نمادهای فعال در جدول"]');
  const shownText = counter ? (counter as HTMLElement).textContent : null;
  const chips = Array.from(
    document.querySelectorAll('[data-testid="quick-filters-bar"] button[aria-pressed]'),
  ).map((b: any) => ({
    label: (b.textContent || '').replace(/\s+/g, ' ').trim(),
    pressed: b.getAttribute('aria-pressed'),
  }));
  const rendered = document.querySelectorAll('[data-testid="tape-row"]').length;
  const reset = document.querySelector('[data-testid="filters-reset"]');
  return {
    shown: shownText ? shownText.replace(/\s+/g, ' ').trim() : null,
    chips,
    rendered,
    resetLabel: reset ? (reset.textContent || '').trim() : null,
  };
};

const browser = await chromium.launch(launchOpts);
const ctx = await browser.newContext({ viewport: { width: WIDTH, height: 900 } });
await ctx.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* پوستهٔ بدونِ دروازه هم همین را می‌پذیرد */
  }
});
const page = await ctx.newPage();
const consoleErrors: string[] = [];
page.on('console', (m: any) => {
  if (m.type() === 'error') consoleErrors.push(String(m.text()).slice(0, 220));
});

await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(WAIT);

const readState = async () => page.evaluate(PROBE_STATE);

const out: Record<string, unknown> = { base: BASE, width: WIDTH, at: new Date().toISOString(), chips: {} };
const initial = await readState();
out.initial = initial;

const promisedOf = (label: string): string | null => {
  const m = label.match(/\(\s*([\d\u06F0-\u06F9\u0660-\u0669٬]+)\s*\)/);
  return m ? m[1] : null;
};

for (const label of CHIPS) {
  const entry: Record<string, unknown> = {};
  try {
    const btn = page
      .locator(`[data-testid="quick-filters-bar"] button[aria-pressed]:has-text("${label}")`)
      .first();
    const chipText = (await btn.textContent())?.replace(/\s+/g, ' ').trim() ?? '';
    entry.chipText = chipText;
    entry.promisedCount = promisedOf(chipText);
    await btn.click({ timeout: 5000 });
    await page.waitForTimeout(1400);
    const after = await readState();
    entry.shownBefore = initial.shown;
    entry.shownAfter = after.shown;
    entry.pressedAfter = (
      after.chips.find((c: any) => c.label.startsWith(label) && c.pressed === 'true') ?? null
    ) ? 'true' : await btn.getAttribute('aria-pressed');
    entry.renderedAfter = after.rendered;
    entry.resetLabelAfter = after.resetLabel;
    // برگشت تا هر چیپ مستقل سنجیده شود
    await btn.click({ timeout: 5000 });
    await page.waitForTimeout(900);
    entry.shownAfterUntoggle = (await readState()).shown;
  } catch (e) {
    entry.error = String(e).slice(0, 200);
  }
  (out.chips as Record<string, unknown>)[label] = entry;
}

// پاپ‌اور ⚙: آیا تغییرِ آستانه نتیجهٔ جدول را عوض می‌کند؟ (الگوی ساعت)
try {
  const chipOn = page
    .locator(`[data-testid="quick-filters-bar"] button[aria-pressed]:has-text("الگوی ساعت")`)
    .first();
  await chipOn.click();
  await page.waitForTimeout(900);
  const shownBeforeThreshold = (await readState()).shown;
  const gear = page
    .locator(`[data-testid="quick-filters-bar"] button[aria-label="تنظیمات الگوی ساعت"]`)
    .first();
  await gear.click({ timeout: 4000 });
  await page.waitForTimeout(700);
  const popoverVisible = await page.locator('[role="dialog"]').count();
  const sliders = await page.locator('[role="dialog"] input[type="range"]').all();
  const moves: Array<Record<string, unknown>> = [];
  for (let i = 0; i < sliders.length; i += 1) {
    const s = sliders[i];
    const meta: Record<string, unknown> = {
      index: i,
      name: await s.evaluate((el: any) => el.getAttribute('aria-label') ?? el.id ?? ''),
      before: await s.evaluate((el: any) => el.value),
      min: await s.evaluate((el: any) => el.min),
      max: await s.evaluate((el: any) => el.max),
    };
    await s.evaluate((el: any) => {
      const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      const max = Number(el.max || '10');
      const next = String(Math.min(max, Number(el.value || '0') + Math.max(1, (max - Number(el.min || 0)) / 2)));
      set?.call(el, next);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await page.waitForTimeout(1200);
    meta.after = await s.evaluate((el: any) => el.value);
    meta.shownAfter = (await readState()).shown;
    moves.push(meta);
  }
  out.gearPopover = {
    popoverVisible,
    sliderCount: sliders.length,
    shownWithChipOnly: shownBeforeThreshold,
    moves,
  };
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);
  await chipOn.click();
} catch (e) {
  out.gearPopover = { error: String(e).slice(0, 200) };
}

out.consoleErrors = consoleErrors.slice(0, 10);
mkdirSync('_audit/tmp', { recursive: true });
writeFileSync(OUT, JSON.stringify(out, null, 2), 'utf-8');
console.log('WROTE', OUT);
await browser.close();
