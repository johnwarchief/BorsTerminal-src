/**
 * tools/jev_click_log_check.mts — اثباتِ زندهٔ قراردادِ رویدادِ کلیک (کار #48)
 *
 * jsdom ثابت می‌کند هندلر نوشته می‌شود؛ این فایل ثابت می‌کند درِ مرورگرِ واقعی:
 *  ۱) خطِ «کلیک» در نوارِ پایینی دیده می‌شود (نه null، نه بریده)،
 *  ۲) یکِ کلیکِ ماوس رویِ بومِ کندل‌ها آن خط را از «—» به یکِ میلهٔ واقعی می‌برد،
 *  ۳) با عوض‌شدنِ نماد، laگِ نمادِ قبلی درِ همان خط نمی‌ماند (نشتِ حالت).
 *
 * اجرا (JEV_BROWSER_DIR/JEV_CHROME از محیط، MSYS_NO_PATHCONV=1):
 *   node --experimental-strip-types tools/jev_click_log_check.mts \
 *     --url http://127.0.0.1:8002/ --symbol فولاد --out _audit/click_log_live.json
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

const BASE = arg('url', 'http://127.0.0.1:8002/');
const SYMBOL = arg('symbol', 'فولاد');
const OTHER = arg('other', 'خودرو');
const OUT = arg('out', '_audit/click_log_live.json');
const WAIT = Number.parseInt(arg('wait', '12000'), 10);
const CHROME = process.env.JEV_CHROME ?? '';

const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);

const browser = await chromium.launch({
  ...(CHROME ? { executablePath: CHROME } : {}),
  args: ['--no-sandbox', '--disable-gpu'],
});
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1000 } });
await ctx.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* پوستهٔ بدونِ دروازه هم همین را می‌پذیرد */
  }
});
const page = await ctx.newPage();

const readChip = () =>
  page.evaluate(() => {
    const el = document.querySelector('[data-testid="chart-click-chip"]');
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const de = document.documentElement;
    return {
      text: (el.textContent ?? '').replace(/\s+/g, ' ').trim(),
      box: { w: Math.round(r.width), h: Math.round(r.height) },
      clipped: r.width > 0 && (el.scrollWidth - el.clientWidth > 1),
      pageOverflowX: de.scrollWidth - de.clientWidth,
    };
  });

/**
 * کلیک رویِ بدنة یک کندل. بدنهٔ کندل باریک است و «xِ ثابت، yِ ثابت» معمولاً
 * بیرونِ آن می‌افتد، پس صفحه درِ ستون‌هایِ پرحجم‌ترِ راست (تازۀ‌ترین‌ها) جارو
 * می‌شود و با اولین تغییری درِ خطِ کلیک می‌ایستد.
 */
async function clickCandle() {
  const box = await page.evaluate(() => {
    const c = document.querySelector('canvas') ?? document.body;
    const r = c.getBoundingClientRect();
    return { left: r.left, top: r.top, w: r.width, h: r.height };
  });
  const attempts: { x: number; y: number }[] = [];
  for (let fx = 0.88; fx >= 0.3; fx -= 0.03) {
    for (let fy = 0.2; fy <= 0.8; fy += 0.06) {
      const x = Math.round(box.left + box.w * fx);
      const y = Math.round(box.top + box.h * fy);
      attempts.push({ x, y });
      await page.mouse.click(x, y);
      await page.waitForTimeout(70);
      const t = await readChipText();
      if (t && !t.includes('—')) return { x, y, of: attempts.length, text: t };
    }
  }
  return { of: attempts.length, text: await readChipText(), exhausted: true };
}

const readChipText = () =>
  page.evaluate(() => {
    const el = document.querySelector('[data-testid="chart-click-chip"]');
    return el ? (el.textContent ?? '').replace(/\s+/g, ' ').trim() : null;
  });

const report: Record<string, unknown> = { base: BASE, symbol: SYMBOL, other: OTHER, steps: [] };
const steps = report.steps as unknown[];

try {
  await page.goto(`${BASE}#/technical/${encodeURIComponent(SYMBOL)}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(WAIT);

  const before = await readChip();
  steps.push({ step: 'chip پیش از کلیک', chip: before });

  const where = await clickCandle();
  const after = await readChip();
  steps.push({ step: 'chip پس از کلیک رویِ بوم', at: where, chip: after });

  // فهرستِ پشتِ همان خط — رویِ همان نماد، پیش ازِ عوض‌کردنِ نماد
  const chipBox = await page.evaluate(() => {
    const el = document.querySelector('[data-testid="chart-click-chip"]');
    const r = el?.getBoundingClientRect();
    return r ? { x: r.x + r.width / 2, y: r.y + r.height / 2 } : null;
  });
  let listed: { present: boolean; rows: number } | false = false;
  if (chipBox) {
    await page.mouse.click(chipBox.x, chipBox.y);
    await page.waitForTimeout(350);
    listed = await page.evaluate(() => ({
      present: !!document.querySelector('[data-testid="chart-click-list"]'),
      rows: document.querySelectorAll('[data-testid="chart-click-row"]').length,
    }));
  }
  steps.push({ step: 'باز‌شدنِ فهرست با کلیک رویِ خط', listVisible: listed });

  // نماد عوض می‌شود ⇒ خطِ کلیک نباید میلهٔ نمادِ قبلی را نگه دارد
  await page.goto(`${BASE}#/technical/${encodeURIComponent(OTHER)}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(WAIT / 2);
  const switched = await readChip();
  steps.push({ step: 'chip پس ازِ عوض‌کردنِ نماد (بی‌کلیکِ تازه ⇒ باید «—» باشد)', chip: switched });

  // ردیفِ ذخیره‌شده، خام از localStorage — تا قالبِ تاریخ درِ UI گم نشود
  report.stored = await page.evaluate(() => localStorage.getItem(['fts', 'chart', 'click-log', 'v1'].join('.')));

  report.verdict = {
    chip_present: !!before,
    chip_has_placeholder_before: !!before && String(before.text).includes('—'),
    chip_changed_after_click: !!after && !String(after.text).includes('—'),
    list_opens_with_row:
      !!listed && typeof listed === 'object' && listed.present && listed.rows >= 1,
    clip_free: [before, after, switched].every((c) => !!c && !c.clipped && (c.pageOverflowX ?? 1) <= 0),
    // با نمادِ تازه باید خط به «—» برگردد (رویدادِ نمادِ قبلی خطِ این نماد نیست)
    chip_reset_on_switch: !!switched && String(switched.text).includes('—'),
  };
} catch (e) {
  report.error = String(e).slice(0, 300);
} finally {
  await page.screenshot({ path: OUT.replace(/json$/, 'png'), fullPage: false }).catch(() => {});
  await browser.close();
}

mkdirSync(OUT.split('/')[0] ?? '_audit', { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf-8');
console.log(JSON.stringify(report.verdict ?? { error: report.error }, null, 1));
for (const s of report.steps as any[]) console.log(' •', s.step, JSON.stringify(s.chip ?? s.listVisible ?? s.at));
process.exit(report.error ? 1 : 0);
