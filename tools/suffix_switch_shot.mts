// tools/suffix_switch_shot.mts — اثباتِ زندهٔ سوییچِ «حذفِ پسوندِ عددی»: دیده‌شدن، جاشدن و کارکرد
//
// سه چیز درِ مرورگر ثابت می‌شود (تستِ واحد هیچ‌کدام را نمی‌بیند):
//   1) سوییچ در نوارِ فیلتر دیده می‌شود و در هر سه رزولوشن (۱۳۶۶/۱۶۳۲/۱۹۲۰)
//      پشتِ لبهٔ نوار نمی‌رود — نوارِ کنترل overflow ندارد.
//   2) پیش‌فرض = قاعده روشن؛ یک کلیک ردیف‌هایِ پسونددار را به جدول می‌آورد و
//      تولتیپِ چیپ دیگر آن‌ها را به «پسوندِ عددی» نسبت نمی‌دهد.
//   3) تنظیم ماندگار است: reload همان انتخاب را نگه می‌دارد و «پاک کردن» برمی‌گرداند.
//
//   JEV_CHROME='C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' \
//   MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/suffix_switch_shot.mts \
//     --url http://127.0.0.1:5173/ --out _audit/suffix_switch_shot.json
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');

const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};
const BASE = arg('url', 'http://127.0.0.1:5173/');
const OUT = arg('out', '_audit/suffix_switch_shot.json');
const SHOT = arg('shot', '_audit/suffix_switch.png');

const report: Record<string, unknown> = { base: BASE, steps: {}, errors: [], checks: [] };
const ck = (name: string, ok: boolean, detail: unknown = null) => {
  (report.checks as Record<string, unknown>[]).push({ name, ok, detail });
  return ok;
};

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });

/** شمارِ نمادهایِ جدول را از پلاکِ «X از Y نماد» می‌خواند (ارقامِ فارسی) */
const shownCount = async (page: any): Promise<number | null> =>
  page.evaluate(() => {
    const el = document.querySelector('[title="تعداد نمادهای فعال در جدول"]');
    const m = (el ? el.textContent ?? '' : '').match(/[۰-۹]+/g);
    if (!m) return null;
    return Number(m[0].split('').reduce((a: number, d: string) => a * 10 + (d.charCodeAt(0) - 0x06f0), 0));
  });

/** نوارِ فیلتر سرریز ندارد؟ سوییچ درِ «quick-filters-bar» نیست — کنارِ «فقط زنده»
 *  درِ ستónِ چپ (`filters-side`) است، پس معیارِ درست کلِ نوار و لبهٔ صفحه است. */
const barFits = (page: any) =>
  page.evaluate(() => {
    const bar = document.querySelector('[data-testid="market-filters-bar"]');
    const sw = document.querySelector('[data-testid="numeric-suffix-toggle"]');
    if (!bar || !sw) return null;
    const b = bar.getBoundingClientRect();
    const s = sw.getBoundingClientRect();
    return {
      scrollOverflow: bar.scrollWidth - bar.clientWidth,
      insideBar: s.left >= b.left - 1 && s.right <= b.right + 1 && s.bottom <= b.bottom + 1 && s.top >= b.top - 1,
      insideViewport: s.right <= window.innerWidth + 1 && s.left >= 0,
      switchVisible: s.width > 0 && s.height > 0,
    };
  });

const WIDTHS = [1366, 1632, 1920];
for (const w of WIDTHS) {
  const ctx = await browser.newContext({ viewport: { width: w, height: 900 } });
  await ctx.addInitScript(() => {
    sessionStorage.setItem('bors_auth_session', 'true');
    localStorage.removeItem('bors-symbol');
    localStorage.removeItem('bors_tape_show_numeric_suffix_v1');
  });
  const page = await ctx.newPage();
  page.on('pageerror', (e: { message: string }) => (report.errors as string[]).push(`pageerror@${w}: ${e.message}`));
  page.on('console', (m: { type: () => string; text: () => string; location: () => { url?: string } }) => {
    if (m.type() !== 'error') return;
    const url = m.location()?.url ?? '';
    // سروِ dev ویکت favicon.ico ندارد (در اپِ نصب‌شده ۲۰۰ است) — صدایِ واقعی نیست
    if (url.endsWith('/favicon.ico')) return;
    (report.errors as string[]).push(`console@${w}: ${url} :: ${m.text().slice(0, 200)}`);
  });
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  const fits = await barFits(page);
  report.steps[`fit_${w}`] = fits;
  ck(
    `سوییچ درِ رزولوشن ${w} دیده می‌شود و از نوار یا صفحه بیرون نمی‌زند`,
    Boolean(fits?.switchVisible && fits?.insideBar && fits?.insideViewport && fits?.scrollOverflow <= 0),
    fits,
  );
  if (w === 1632) {
    await page.locator('[data-testid="market-filters-bar"]').screenshot({ path: SHOT });
  }
  await ctx.close();
}

// ── کارکرد + ماندگاری رویِ یک صفحه ───────────────────────────────────────────
const ctx = await browser.newContext({ viewport: { width: 1632, height: 950 } });
// پاک‌کردنِ کلید فقط برایِ بارِ اول: addInitScript رویِ هر reload اجرا می‌شود، پس
// بی‌نگهبان خودش تنظیم را می‌دزدد و سنجشِ ماندگاری دروغ می‌گوید.
await ctx.addInitScript(() => {
  sessionStorage.setItem('bors_auth_session', 'true');
  localStorage.removeItem('bors-symbol');
  if (!sessionStorage.getItem('bors_suffix_fresh')) {
    localStorage.removeItem('bors_tape_show_numeric_suffix_v1');
    sessionStorage.setItem('bors_suffix_fresh', '1');
  }
});
const page = await ctx.newPage();
page.on('pageerror', (e: { message: string }) => (report.errors as string[]).push(`pageerror: ${e.message}`));
await page.goto(BASE, { waitUntil: 'networkidle' });
await page.waitForTimeout(3000);

const sw = page.locator('[data-testid="numeric-suffix-toggle"]');
ck('پیش‌فرض: قاعده‌یِ حذف روشن (aria-pressed=true)', (await sw.getAttribute('aria-pressed')) === 'true');
const before = await shownCount(page);
await sw.click();
await page.waitForTimeout(1600);
const after = await shownCount(page);
report.steps.toggle = { before, after, pressed: await sw.getAttribute('aria-pressed') };
ck('یک کلیک: ردیف‌هایِ پسونددار واردِ جدول می‌شوند', before != null && after != null && after > before, { before, after });
ck('سوییچ بعد از کلیک خاموش به نظر می‌رسد', (await sw.getAttribute('aria-pressed')) === 'false');

// ماندگاری: همان context با reload
await page.reload({ waitUntil: 'networkidle' });
await page.waitForTimeout(3000);
const afterReload = await page.locator('[data-testid="numeric-suffix-toggle"]').getAttribute('aria-pressed');
const countReload = await shownCount(page);
report.steps.reload = { afterReload, countReload };
ck('reload همان انتخاب را نگه می‌دارد (تنظیمِ ماندگار)', afterReload === 'false' && countReload === after, { afterReload, countReload, after });

// «پاک کردن» قاعده را برمی‌گرداند
const reset = page.locator('[data-testid="filters-reset"]');
if (await reset.count()) {
  await reset.click();
  await page.waitForTimeout(1600);
  const backPressed = await page.locator('[data-testid="numeric-suffix-toggle"]').getAttribute('aria-pressed');
  const backCount = await shownCount(page);
  ck('«پاک کردن» به پیش‌فرض برمی‌گرداند', backPressed === 'true' && backCount === before, { backPressed, backCount, before });
} else {
  ck('«پاک کردن» به پیش‌فرض برمی‌گرداند', false, 'دکمهٔ پاک کردن پیدا نشد');
}

// تولتیپِ چیپ: نامِ کلید برده می‌شود، استعارهٔ «در» نه
const chipTitle = await page.evaluate(() => {
  const b = Array.from(document.querySelectorAll('button')).find((x) =>
    (x.getAttribute('title') ?? '').includes('دیده نمی‌شوند'),
  );
  return b ? (b.getAttribute('title') ?? '').replace(/\s+/g, ' ') : null;
});
report.steps.chipTitle = chipTitle;
ck('تولتیپ با جملهٔ «دیده نمی‌شوند» توضیح می‌دهد', Boolean(chipTitle), chipTitle);
ck('تولتیپ استعارهٔ «درِ نمایِ فعلی» را ندارد', !chipTitle || !chipTitle.includes('درِ نمای'), chipTitle);

const failed = (report.checks as any[]).filter((c) => !c.ok);
report.verdict = failed.length === 0 && (report.errors as string[]).length === 0 ? 'PASS' : 'FAIL';
report.failed = failed.map((f) => f.name);

mkdirSync(OUT.split('/').slice(0, -1).join('/'), { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2));
console.log(JSON.stringify({ verdict: report.verdict, failed: report.failed, errors: report.errors, checks: report.checks.map((c: any) => ({ n: c.name, ok: c.ok })) }, null, 2));
await browser.close();
