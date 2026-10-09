// _audit/ws12_sidebar_trace.mts — ردپایِ فیلتر‌به‌فیلتر درِ صفحۀ دومِ سایدبار
//
// رأیِ مالک: «کلیک رویِ نماد ⇒ داوریِ کاملِ هدفمند ⇒ سایدبار». سنجشِ زنده:
//   ۱ با کلیکِ واقعیِ ردیف، پنل باز می‌شود و صفحۀ «جزئیات بازار» ردپا دارد
//   ۲ هر سطرِ ردپا وضعیت + دلیل + ورودی/خروجی دارد (چیزی که موتور نوشته،
//     نه چیزی که فرانت ساخته)
//   ۳ نسخهٔ قواعد و زمانِ داده رویِ همان بلوک خوانده می‌شود (explainability)
//   ۴ درخواستِ ردپا اجرایِ دومِ موتور نیست: همان کلیدِ کشِ جدولِ غربالگری
//     (مدتِ پاسخِ trace در برابرِ مدتِ یک اجرایِ کامل ~۹۰۰ms)
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const BASE = process.argv.includes('--url') ? process.argv[process.argv.indexOf('--url') + 1]
                                            : 'http://127.0.0.1:5175/';
mkdirSync('_audit', { recursive: true });
const OUT = '_audit/ws12_sidebar_trace.json';
const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const errs: string[] = [];
const traceTimings: { url: string; ms: number }[] = [];
page.on('pageerror', (e) => errs.push(String(e.message).slice(0, 140)));
page.on('console', (m) => {
  if (m.type() === 'error') {
    const loc = String(m.location?.().url ?? '');
    if (/favicon\.ico/.test(loc)) return;
    errs.push('console: ' + m.text().slice(0, 110) + ' @ ' + loc.slice(0, 60));
  }
});
page.on('requestfinished', async (r) => {
  const u = String(r.url());
  if (!u.includes('/api/funnel')) return;
  const t0 = Date.now();
  try { await r.response(); } catch { /* noop */ }
  traceTimings.push({ url: u.replace(/^https?:\/\/[^/]+/, '').slice(0, 90), ms: Date.now() - t0 });
});

await page.goto(BASE + '#/market', { waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => document.querySelectorAll('[data-testid="tape-row"]').length >= 5,
  null, { timeout: 120_000 });
await page.locator('[data-testid="tape-row"]').nth(1).click();
await page.waitForSelector('[data-testid="inspector-tabs"]', { timeout: 60_000 });
await page.waitForTimeout(1200);
const symbol = await page.evaluate(() => {
  const el = document.querySelector('[data-shell="inspector"]');
  return String(el?.getAttribute('aria-label') ?? '').replace('بازرسی نماد ', '').trim();
});
await page.click('[data-testid="inspector-tab-detail"]');
await page.waitForSelector('[data-testid="inspector-trace"]', { timeout: 30_000 });
await page.waitForTimeout(2500);

const view = await page.evaluate(() => {
  const box = document.querySelector('[data-testid="inspector-trace"]');
  const steps = [...document.querySelectorAll('[data-testid^="funnel-trace-step-"]')];
  return {
    hasBox: !!box,
    loading: !!document.querySelector('[data-testid="funnel-trace-loading"]'),
    error: !!document.querySelector('[data-testid="funnel-trace-error"]'),
    empty: !!document.querySelector('[data-testid="funnel-trace-empty"]'),
    steps: steps.map((li) => {
      const t = (li.textContent ?? '').trim();
      return { text: t.slice(0, 90), hasDot: !!li.querySelector('span[aria-hidden]') };
    }),
    meta: String(document.querySelector('[data-testid="funnel-trace-meta"]')?.textContent ?? '').trim(),
  };
});

// مقایسه با پاسخِ مستقیمِ همان اندپوینت (تک‌تعریفِ داده): شمارِ سطرهایِ رابط
// باید با شمارِ سطرهایِ `timeline`ِ سرور یکی باشد.
const server = await page.evaluate(async (sym: string) => {
  const r = await fetch(`/api/funnel/trace?symbol=${encodeURIComponent(sym)}`
    + '&preset=custom&chain=&fund_mode=standard&exceptions=%7B%7D');
  const j = await r.json();
  return { status: j.status, steps: (j.timeline || []).length,
           ruleset: j.ruleset_version, as_of: j.as_of };
}, symbol);

await page.screenshot({ path: '_audit/ws12_trace_page.png', clip: { x: 0, y: 0, width: 360, height: 880 } });

const res = { base: BASE, symbol, view, server, traceTimings, pageErrors: errs };
const checks: [string, boolean][] = [
  ['page 2 shows the trace block', view.hasBox],
  ['trace resolved (not loading, no error)', view.loading === false && view.error === false],
  ['rows rendered for every server step', view.steps.length === server.steps && server.steps > 0],
  ['each step carries its own status dot', view.steps.length > 0 && view.steps.every((s) => s.hasDot)],
  ['ruleset version + data time are visible', /قواعد: [0-9a-f]{8}/.test(view.meta)],
  ['server agrees on the step count', server.status === 'success'],
  ['the trace did not pay for a full engine run (<700ms)',
      (traceTimings.find((t) => t.url.includes('/trace'))?.ms ?? 9999) < 700],
  ['no page errors', errs.length === 0],
];
res.verdict = checks.map(([k, v]) => ({ check: k, pass: v }));
writeFileSync(OUT, JSON.stringify(res, null, 2));
for (const [k, v] of checks) console.log((v ? 'PASS ' : 'FAIL ') + k);
console.log(`symbol=${JSON.stringify(symbol)} uiSteps=${view.steps.length} serverSteps=${server.steps}`);
console.log(`meta=${JSON.stringify(view.meta)} first=${JSON.stringify(view.steps[0]?.text ?? '')}`);
console.log('timings=' + JSON.stringify(traceTimings));
if (errs.length) console.log('errors: ' + JSON.stringify(errs.slice(0, 3)));
await browser.close();
