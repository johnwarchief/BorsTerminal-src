// tools/funnel_columns_probe.mts -- اثباتِ زنده: هر مرحلۀ قیف ستون‌هایِ خودش را دارد
//
// ادعایِ مالک: «هر بخش باید ستونِ مربوط به خودش را داشته باشد، مثلا تکنیکال
// هفتگی صعودی یا نزولی» و «تکنیکال رد نکند تا به بنیادی برسند». این پروب
// همان‌ها را از DOMِ خودِ برنامه می‌خواند — نه از تستِ jsdom:
//   ۱) سرستون‌هایِ هر چهار مرحله (باید چهار مجموعهٔ متفاوت باشد)
//   ۲) متنِ ستونِ «هفتگی» در ردیف‌هایِ مرحلۀ تکنیکال (صعودی/نزولی/خنثی)
//   ۳) کلیکِ «خودم چک می‌کنم»: شمارِ ردیف‌هایِ مرحلۀ بنیادی باید زیاد شود،
//      چیپِ «رد (بی‌حذف)» ظاهر شود، و برچسبِ رد رویِ همان ردیف بماند
//   ۴) برگشت به «رد می‌کند»: همان عددهایِ اول برمی‌گردند
//
//   JEV_CHROME=... MSYS_NO_PATHCONV=1 node --experimental-strip-types \
//     tools/funnel_columns_probe.mts --url http://127.0.0.1:5173/ --out _audit/funnel_columns.json
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');

const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:5173/');
const ROUTE = arg('route', '#/master');
const OUT = arg('out', '_audit/funnel_columns_probe.json');

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
// --narrow = 1366×768: هفت سرستون در مرحلۀ بنیادی باید درِ کوچک‌ترین رزولوشنِ
// پشتیبانی‌شده هم خوانده شوند، نه اینکه میز را بشکنند.
const NARROW = process.argv.includes('--narrow');
const SHOT = arg('shot', '');
const ctx = await browser.newContext({
  viewport: NARROW ? { width: 1366, height: 768 } : { width: 1632, height: 950 },
});
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const errors: string[] = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
page.on('pageerror', (e) => errors.push('pageerror: ' + String(e).slice(0, 200)));

await page.goto(BASE + ROUTE, { waitUntil: 'networkidle' });
await page.waitForSelector('[data-testid="funnel-stage-technical"]', { timeout: 45_000 });
// پوششِ رأیِ تکنیکال از /api/fts/{symbol} می‌آید و ثانیه‌ها می‌برد
await page.waitForTimeout(9000);

const snap = () =>
  page.evaluate(() => {
    const stage = (k: string) => {
      const el = document.querySelector(`[data-testid="funnel-stage-${k}"]`);
      if (!el) return { k, missing: true };
      const heads = Array.from(el.querySelectorAll('thead th')).map((t) => t.textContent?.trim());
      const rows = Array.from(el.querySelectorAll('tbody tr[data-fkey]'));
      const first = rows[0] ? Array.from(rows[0].children).map((c) => c.textContent?.trim()) : null;
      const count = el.querySelector('header .num')?.textContent?.trim() ?? null;
      const chip = el.querySelector('[data-testid^="funnel-rejected-"]')?.textContent?.trim() ?? null;
      return { k, heads, rowCount: rows.length, count, chip, firstRow: first };
    };
    const gate = (id: string) => {
      const b = document.querySelector(`[data-testid="${id}"]`);
      return b ? b.getAttribute('aria-pressed') : null;
    };
    // ردیف‌هایِ وتوشده درِ تکنیکال: روندِ هفتگی + داوری
    const vetoed = Array.from(
      document.querySelectorAll('[data-testid="funnel-stage-technical"] tbody tr[data-fkey]')
    )
      .filter((tr) => (tr.getAttribute('title') ?? '').includes('وتوی هفتگی'))
      .slice(0, 6)
      .map((tr) => ({
        symbol: tr.getAttribute('data-fkey'),
        cells: Array.from(tr.children).map((c) => c.textContent?.trim()),
      }));
    return {
      stages: ['tape', 'technical', 'fundamental', 'handover'].map(stage),
      techScreens: gate('funnel-tech-screens'),
      selfCheck: gate('funnel-tech-selfcheck'),
      vetoed,
      stored: localStorage.getItem('fts.funnel.prefs.v1'),
    };
  });

const before = await snap();
await page.click('[data-testid="funnel-tech-selfcheck"]');
await page.waitForTimeout(1200);
const off = await snap();
// کفِ بنیادی را پایین می‌آوریم تا ردیفِ قبول‌شده پیدا شود و ستون‌هایِ پنج‌شاخصه
// هم رویِ دادهٔ زنده دیده شوند (با کفِ سه، مرحلۀ بنیادی همین نشست خالی بود).
await page.click('[data-testid="funnel-floor-1"]');
await page.waitForTimeout(1200);
const floor1 = await snap();
await page.click('[data-testid="funnel-prefs-reset"]').catch(() => {});
await page.waitForTimeout(800);
await page.click('[data-testid="funnel-tech-screens"]');
await page.waitForTimeout(1200);
const back = await snap();
// انتخابِ کاربر باید رویِ دیسک بماند (۱٫۰٫۵۵) — یک بار reload
await page.click('[data-testid="funnel-tech-selfcheck"]');
await page.waitForTimeout(400);
await page.reload({ waitUntil: 'networkidle' });
await page.waitForSelector('[data-testid="funnel-stage-technical"]', { timeout: 45_000 });
await page.waitForTimeout(4000);
const afterReload = await snap();
await page.click('[data-testid="funnel-prefs-reset"]').catch(() => {});
await page.waitForTimeout(600);
const reset = await snap();

const fit = await page.evaluate(() => {
  const el = document.querySelector('[data-testid="funnel-stage-fundamental"]');
  const sec = el?.closest('section')?.parentElement;
  return {
    viewport: window.innerWidth,
    docOverflowX: document.documentElement.scrollWidth > window.innerWidth + 1,
    funnelOverflowX: sec ? sec.scrollWidth > sec.clientWidth + 1 : null,
    tableOverflowX: el ? el.scrollWidth > el.clientWidth + 1 : null,
  };
});
if (SHOT) await page.screenshot({ path: SHOT, fullPage: false });

const summary = {
  url: BASE, route: ROUTE, fit,
  headsetsDiffer: new Set(
    [...before.stages, ...floor1.stages].map((s: any) => JSON.stringify(s.heads))
  ).size,
  before, off, floor1, back, afterReload, reset, consoleErrors: errors,
};
writeFileSync(OUT, JSON.stringify(summary, null, 1), 'utf-8');
const line = (s: any) =>
  `  ${s.k}: rows=${s.rowCount} chip=${s.chip ?? '-'} heads=[${(s.heads ?? []).join(' | ')}] first=${JSON.stringify(s.firstRow)}`;
console.log(`fit: ${JSON.stringify(summary.fit)}`);
console.log(`headsetsDiffer=${summary.headsetsDiffer} مجموعهٔ سرستونِ متمایز`);
console.log('BEFORE (جزوه: تکنیکال رد می‌کند)');
before.stages.forEach((s: any) => console.log(line(s)));
console.log('AFTER «خودم چک می‌کنم»');
off.stages.forEach((s: any) => console.log(line(s)));
console.log('AFTER + کفِ بنیادی ۱ (ستون‌های پنج‌شاخصه رویِ دادهٔ زنده)');
floor1.stages.forEach((s: any) => console.log(line(s)));
console.log('گیت:', JSON.stringify({ techScreens: before.techScreens, selfCheck: before.selfCheck }),
  '→', JSON.stringify({ techScreens: off.techScreens, selfCheck: off.selfCheck }));
console.log('ردیف‌هایِ وتوی هفتگی در تکنیکال:', JSON.stringify(off.vetoed.slice(0, 2)));
console.log('پس از reload:', JSON.stringify({ techScreens: afterReload.techScreens, stored: afterReload.stored }));
console.log('پس از «بازگشت به جزوه»:', JSON.stringify({ techScreens: reset.techScreens }));
console.log('console errors:', errors.length, errors.slice(0, 3));
await browser.close();
