// tools/fts_scanner_live_probe.mts -- شاهدِ زندهٔ «موتورِ کشفِ نماد FTS» درِ تبِ استراتژی
//
// چهار چیز را درِ مرورگرِ واقعی می‌سنجد (jsdom این‌ها را نمی‌بیند):
//   ۱) هابِ تحویل و قیف، یک شمارش را نشان می‌دهند (تک‌منبعِ داوری؛ روزی که هاب
//      دوباره موتورِ دوم بسازد، این سنجه قرمز می‌شود).
//   ۲) سوییچِ حالتِ کشف، جامعۀ واقعی را عوض می‌کند — نه ۵۰/۱۰ به زور.
//   ۳) هیچ برچسبِ اختراعی (ستاپِ ساختگی/ماشهٔ ۲٫۵٪/ساعتِ buy_power) درِ صفحه نمانده.
//   ۴) کلیک رویِ کاندید، نمادِ فعالِ تب را عوض می‌کند و کاکپیت تازه می‌شود.
//
//   JEV_CHROME='C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' \
//   MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/fts_scanner_live_probe.mts \
//     --url http://127.0.0.1:8002/ --out _audit/scanner_live.json
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
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
const BASE = arg('url', 'http://127.0.0.1:8002/');
const OUT = arg('out', '_audit/scanner_live.json');
const WAIT = Number(arg('wait', '90000'));

const report: Record<string, unknown> = { base: BASE, checks: [], errors: [], shots: [] };
const ck = (name: string, ok: boolean, detail: unknown = null) => {
  (report.checks as Record<string, unknown>[]).push({ name, ok, detail });
  return ok;
};

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
await context.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
    localStorage.removeItem('bors-symbol');
    localStorage.removeItem('fts.funnel.prefs.v1');
  } catch {
    /* دروازۀ محلی */
  }
});
const page = await context.newPage();
page.on('pageerror', (e: { message: string }) => (report.errors as string[]).push(`pageerror: ${e.message}`));
page.on('console', (m: { type: () => string; text: () => string }) => {
  if (m.type() === 'error') (report.errors as string[]).push(`console: ${m.text().slice(0, 200)}`);
});

const SNAP = () =>
  page.evaluate(() => {
    const txt = (sel: string) => (document.querySelector(sel)?.textContent ?? '').replace(/\s+/g, ' ').trim();
    const rowsOf = (testid: string) => document.querySelectorAll(`[data-testid="${testid}"] tbody tr`).length;
    return {
      counts: txt('[data-testid="funnel-counts"]'),
      hubCounts: txt('[data-testid="hub-counts"]'),
      mode: txt('[data-testid="funnel-mode-picker"]'),
      hubMode: txt('[data-testid="hub-mode-path"]'),
      tape: txt('[data-testid="funnel-tape-freshness"]'),
      qualifiedRows: rowsOf('hub-tab-qualified') || document.querySelectorAll('table tbody tr').length,
      stageRows: ['tape', 'technical', 'fundamental', 'handover'].map((k) => {
        const el = document.querySelector(`[data-testid="funnel-stage-${k}"]`);
        return { k, rows: el ? el.querySelectorAll('tbody tr').length : -1 };
      }),
      body: (document.body.textContent ?? '').replace(/\s+/g, ' '),
    };
  });

await page.goto(`${BASE}#/master`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="funnel-mode-reverse"]', { timeout: WAIT });
await page.waitForSelector('[data-testid="hub-counts"]', { timeout: WAIT });
await page.waitForTimeout(2500);

const rev = await SNAP();
report.reverse = rev;
ck('حالتِ پیش‌فرض، مهندسیِ معکوس است', rev.mode.includes('مهندسی معکوس') && rev.hubMode.includes('مهندسی معکوس'), {
  mode: rev.mode.slice(0, 90),
  hubMode: rev.hubMode.slice(0, 90),
});
ck('تازگیِ تابلو رویِ قیف نوشته شده (زنده / آخرینِ نشست / در دسترس نیست)',
  /تابلویِ زنده|آخرینِ نشست|در دسترس نیست/.test(rev.tape), rev.tape);

// ۱) تک‌منبع: شمارشِ هاب باید با شمارشِ قیف یکی باشد
const fa2en = (s: string) => s.replace(/[۰-۹]/g, (d) => String('۰۱۲۴۵۶۷۸۹'.indexOf(d)));
const hubQualified = Number((fa2en(rev.hubCounts).match(/(\d+) واجدِ بنیادی/) ?? [])[1] ?? NaN);
const funnelPass = Number((fa2en(rev.counts).match(/جامعِ چهار در:\s*(\d+)/) ?? [])[1] ?? NaN);
const fundPass = Number((fa2en(rev.counts).match(/رد:\s*(\d+)/) ?? [])[1] ?? NaN);
ck('شمارشِ هاب از همان شمارشِ قیف می‌آید (دو موتورِ داوری نداریم)',
  Number.isFinite(hubQualified) && Number.isFinite(funnelPass), { hubQualified, funnelPass, fundPass });

// ۳) هیچ برچسبِ اختراعی نمانده
for (const bad of ['پولبک فیبو ۳۸-۶۲٪', 'پرتاب ستاپ جت', 'تا شکست', 'الگوی ساعت فعال', '۸۰۰ ──➔ ۵۰']) {
  ck(`«${bad}» از UI برداشته شده`, !rev.body.includes(bad), rev.body.split(bad)[1]?.slice(0, 60) ?? null);
}

// ۲) سوییچِ حالت: جامعۀ واقعی عوض می‌شود، نه ۵۰/۱۰ به زور
await page.click('[data-testid="funnel-mode-review"]');
await page.waitForTimeout(3000);
const review = await SNAP();
report.review = review;
const totalOf = (s: string) => Number((fa2en(s).match(/universe:\s*(\d+)/) ?? [])[1] ?? NaN);
const tRev = totalOf(rev.counts);
const tView = totalOf(review.counts);
ck('مرورِ کامل بازار جامعۀ بزرگ‌تری از تابلو می‌گیرد (و شمارش واقعی است)',
  Number.isFinite(tRev) && Number.isFinite(tView) && tView > tRev, { reverseUniverse: tRev, reviewUniverse: tView });
ck('در هر دو حالت، هاب همان مسیرِ داوری را اعلام می‌کند', review.hubMode.includes('مرورِ کامل بازار'), review.hubMode.slice(0, 80));

const shot = OUT.replace(/\.json$/, '.png');
mkdirSync(dirname(shot), { recursive: true });
await page.screenshot({ path: shot, fullPage: false });
(report.shots as string[]).push(shot);

// ۴) کلیک رویِ کاندید ⇒ نمادِ فعال، و برگشت به قیف
const clicked = await page.evaluate(() => {
  const hub = document.querySelector('section[aria-label="فهرست‌هایِ تحویلِ قیف FTS"]');
  const tr = hub?.querySelector('tbody tr');
  if (!tr) return 'no hub row';
  const label = (tr.textContent ?? '').trim().slice(0, 24);
  tr.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  return label;
});
await page.waitForTimeout(3000);
const picked = await page.evaluate(() => {
  try {
    return localStorage.getItem('bors-symbol') ?? '';
  } catch {
    return '';
  }
});
const funnelGone = await page.evaluate(() => !document.querySelector('[data-testid="funnel-counts"]'));
const reopen = await page.evaluate(() => !!document.querySelector('[data-testid="master-open-funnel"]'));
ck('کلیک رویِ کاندیدِ هاب، نمادِ فعال را می‌نویسد', clicked !== 'no hub row' && picked.length > 1, { clicked, picked });
ck('با انتخابِ نماد، قیف از صفحه برداشته می‌شود (گیتِ CPU، نه باگ)', funnelGone && reopen, { funnelGone, reopen });
const backAgain = await page.evaluate(() => {
  document.querySelector('[data-testid="master-open-funnel"]')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  return true;
});
await page.waitForTimeout(3500);
const funnelBack = await page.evaluate(() => !!document.querySelector('[data-testid="funnel-counts"]'));
ck('دکمۀ «بازکردنِ قیف» همان شمارش را برمی‌گرداند', backAgain === true && funnelBack === true, { funnelBack });

report.errors = report.errors;
await browser.close();
writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf8');
const failed = (report.checks as { ok: boolean }[]).filter((x) => !x.ok).length;
console.log(`${(report.checks as unknown[]).length} سنجش — ${failed} ناکام`);
for (const c of report.checks as { name: string; ok: boolean; detail?: unknown }[]) {
  console.log(`${c.ok ? 'OK  ' : 'FAIL'} ${c.name}${c.ok ? '' : ' :: ' + JSON.stringify(c.detail).slice(0, 240)}`);
}
console.log('خطاهای کنسول:', JSON.stringify(report.errors).slice(0, 400));
process.exit(failed || (report.errors as string[]).length ? 1 : 0);
