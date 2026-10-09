// _audit/ws9_funnel_live.mts — سنجشِ زندۀ تب «غربالگری FTS» (§۱۵.۲۱)
//
// سه چیز که مالک خواسته و باید عدد داشته باشد:
//   ۱ جدول‌ها بی‌درخواستِ اضافی پر می‌شوند و «پوششِ تکنیکال» سرِ جایش است
//     (بی‌صف ⇒ «تکنیکال سنجیده شده: X از Y»؛ با صف ⇒ «در حال محاسبه» — شاخۀ
//     دوم درِ همین نشستِ بازارِ بسته قابلِ ساختن نیست و درِ jsdom پوشش داده شده).
//   ۲ ریتمِ تازه‌سازی: درِ ساعتِ بسته باید آرام باشد (پاسخِ کاملِ قیف ~۰.۸-۱.۵
//     ثانیه کارِ موتور است؛ هر ۶۰ ثانیه قبلاً بیهوده تکرار می‌شد).
//   ۳ ردیف‌ها دیده می‌شوند: شمارِ ردیف‌هایِ نقاشی‌شده، عرضِ جدول، و نبودِ
//     سرریز/بریدگی درِ ستون‌ها.
// اسکرین‌شات برایِ رأیِ خودِ مالک می‌ماند (گیتِ سبزِ jsdom «انجام شد» نیست).
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const BASE = process.argv.includes('--url') ? process.argv[process.argv.indexOf('--url') + 1]
                                            : 'http://127.0.0.1:5175/';
const WAIT_MS = Number(process.argv.includes('--wait') ? process.argv[process.argv.indexOf('--wait') + 1] : 45_000);
mkdirSync('_audit', { recursive: true });
const OUT = '_audit/ws9_funnel_live.json';

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const errs: string[] = [];
const funnelReqs: number[] = [];
const t0 = Date.now();
page.on('pageerror', (e) => errs.push(String(e.message).slice(0, 150)));
page.on('console', (m) => {
  if (m.type() === 'error') {
    const loc = String(m.location?.().url ?? '');
    if (/favicon\.ico/.test(loc)) return;
    errs.push('console: ' + m.text().slice(0, 120) + ' @ ' + loc.slice(0, 70));
  }
});
page.on('request', (r) => {
  if (String(r.url()).includes('/api/funnel')) funnelReqs.push(Date.now() - t0);
});

const navStart = Date.now();
await page.goto(BASE + '#/master?stage=technical&preset=custom', { waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => document.querySelectorAll('[data-testid^="funnel-stage-"]').length >= 1,
  null, { timeout: 120_000 });
// بک‌اندِ تازه‌بالا‌رفته هنوز تابلو را نساخته است («تابلو هنوز در این اجرا ساخته
// نشده») و درِ آن حالت، جدول عمداً خالی است. سنجشِ «ردیف نقاشی می‌شود» باید
// رسیدنِ شمارۀِ غیرصفرِ جامعۀ بازار را صبر کند، وگرنه صفرها را با شکست می‌خوانیم.
await page.waitForFunction(() => /[۱-۹1-9]/.test(document.querySelector('[data-testid="funnel-universe-market"]')?.textContent ?? ''),
  null, { timeout: 180_000 });
const firstRowsMs = Date.now() - navStart;
await page.waitForTimeout(2500);

const view = await page.evaluate(() => {
  const q = (s: string) => document.querySelector(s);
  const tech = q('[data-testid="funnel-stage-technical"]');
  const rows = tech ? tech.querySelectorAll('tbody tr').length : 0;
  const badge = q('[data-testid="funnel-tech-coverage"]') ?? q('[data-testid="funnel-computing"]');
  const universe = ['market', 'screening', 'excluded']
    .map((k) => q(`[data-testid="funnel-universe-${k}"]`)?.textContent?.trim() ?? null);
  // بریدگیِ ستون‌ها: هر سلولی که محتوایش از باکسش بیرون بزند
  const clipped: string[] = [];
  (tech ?? document).querySelectorAll('tbody td').forEach((td) => {
    if (td.scrollWidth > td.clientWidth + 2 && clipped.length < 6) {
      clipped.push(`${(td.textContent ?? '').trim().slice(0, 18)} [${td.scrollWidth}>${td.clientWidth}]`);
    }
  });
  const tableRect = tech?.querySelector('table')?.getBoundingClientRect();
  return {
    rowsPainted: rows,
    badgeTestId: badge?.getAttribute('data-testid') ?? null,
    badgeText: (badge?.textContent ?? '').trim().slice(0, 90),
    universe,
    tableWidth: tableRect ? Math.round(tableRect.width) : null,
    viewportWidth: innerWidth,
    clipped: clipped.slice(0, 6),
    computing: !!q('[data-testid="funnel-computing"]'),
  };
});

await page.screenshot({ path: '_audit/ws9_funnel_tab.png', fullPage: false });

// ریتمِ تازه‌سازی: پنجره‌ای به طولِ WAIT_MS بی‌هیچ تعاملی باز می‌ماند.
const before = funnelReqs.length;
await page.waitForTimeout(WAIT_MS);
const extra = funnelReqs.length - before;

const res = {
  base: BASE, firstRowsMs, view,
  funnelRequests: { total: funnelReqs.length, atMs: funnelReqs, extraInWindow: extra, windowMs: WAIT_MS },
  pageErrors: errs,
};
const checks: [string, boolean][] = [
  ['funnel tab paints rows without a click', view.rowsPainted > 0],
  ['coverage line is present', view.badgeTestId !== null],
  ['settled line reads «سنجیده شده» (no queue right now)', /سنجیده شده/.test(view.badgeText)],
  ['three-universe line present', view.universe.every((u) => u !== null)],
  ['table is the dominant element (> 55% of viewport width)',
      view.tableWidth !== null && view.tableWidth > view.viewportWidth * 0.55],
  ['no clipped cell text in the technical table', view.clipped.length === 0],
  [`closed-market cadence: ≤1 extra /api/funnel in ${Math.round(WAIT_MS / 1000)}s`, extra <= 1],
  ['no page errors', errs.length === 0],
];
res.verdict = checks.map(([k, v]) => ({ check: k, pass: v }));
writeFileSync(OUT, JSON.stringify(res, null, 2));
for (const [k, v] of checks) console.log((v ? 'PASS ' : 'FAIL ') + k);
console.log(`rows=${view.rowsPainted} tableWidth=${view.tableWidth}/${view.viewportWidth} firstRows=${firstRowsMs}ms`);
console.log(`badge=${JSON.stringify(view.badgeText)} universe=${JSON.stringify(view.universe)}`);
console.log(`funnel requests at ms=${JSON.stringify(funnelReqs)} extraInWindow=${extra}`);
if (errs.length) console.log('errors: ' + JSON.stringify(errs.slice(0, 4)));
await browser.close();
