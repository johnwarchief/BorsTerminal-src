// _audit/ws15_live_changes.mts — «تغییرِ زنده دیده می‌شود؟»
//
// ادعایِ کار: قیف فقط عددِ کل را تکان نمی‌دهد؛ ردیفی که حکمش عوض شده علامت
// می‌گیرد و سرِ هر گام دلتایِ دور نشان می‌دهد. این پروب درِ مرورگرِ واقعی
// نشسته و می‌شمارد: چند بار `tr[data-changed]` دیده شد، چیپِ دلتا ظاهر شد،
// و شمارِ «عبور» چند بار عوض شد. بی‌این، «زنده» فقط یک صفت است.
// اجرا: JEV_CHROME=... MSYS_NO_PATHCONV=1 node --experimental-strip-types _audit/ws15_live_changes.mts --url http://127.0.0.1:8021/ --seconds 60
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const argv = process.argv;
const BASE = argv.includes('--url') ? argv[argv.indexOf('--url') + 1] : 'http://127.0.0.1:8021/';
const SECONDS = argv.includes('--seconds') ? Number(argv[argv.indexOf('--seconds') + 1]) : 60;

const browser = await chromium.launch({ headless: true,
  executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const errs: string[] = [];
page.on('pageerror', (e) => errs.push(String(e.message).slice(0, 140)));
await page.goto(BASE + '#/master', { waitUntil: 'networkidle', timeout: 60_000 });

// گامِ تکنیکال را انتخاب می‌کنیم: کلیدِ «رد نکند/رد کند» رویِ همان کارت است و
// با زدنش داوریِ صدها نماد واقعاً عوض می‌شود — بی‌این درِ بازارِ بسته هیچ حکمی
// جابه‌جا نمی‌شود و صفرِ نمونه چیزی را اثبات نمی‌کرد.
// گامِ تکنیکال + کلیدِ «حالت»: حالت، حکمِ صدها نماد را درِ همین گام عوض می‌کند.
// (درِ گامِ تابلو هیچ چیز با حالت جابه‌جا نمی‌شود و نمونه‌ها صفر می‌ماندند.)
await page.click('[data-testid="funnel-step-technical"]', { timeout: 8000 });
await page.waitForTimeout(4000);
const stages = await page.evaluate(() => Array.from(document.querySelectorAll('[data-testid^="funnel-stage-"]'))
  .map((n) => n.getAttribute('data-testid')));
const gate = await page.locator('[data-testid="funnel-tech-gate"]').count();
await page.click('[data-testid="funnel-mode-swing"]', { timeout: 8000 });
await page.waitForTimeout(4000);
const samples: any[] = [];
const t0 = Date.now();
let shot = false;
// «تغییر» باید ساخته شود، وگرنه صفرِ نمونه چیزی را اثبات نمی‌کند: درِ بازارِ
// بسته اسکن تمام است و هیچ حکمی جابه‌جا نمی‌شود. کلیدِ درِ گامِ تکنیکال را
// می‌زنیم تا داوریِ واقعاً تازه تولید شود و نشانه‌یِ ردیف آزموده شود.
let toggled = false;
while (Date.now() - t0 < SECONDS * 1000) {
  const s = await page.evaluate(() => {
    const changed = Array.from(document.querySelectorAll('tr[data-changed="1"]'));
    const deltas = Array.from(document.querySelectorAll('[data-testid^="funnel-delta-"]'));
    const ruled = Array.from(document.querySelectorAll('[data-testid^="funnel-ruled-"]'))
      .map((n) => (n.textContent || '').trim());
    return {
      changed_rows: changed.length,
      changed_symbols: changed.slice(0, 6).map((n) => n.getAttribute('data-fkey')),
      delta_chips: deltas.map((n) => (n.textContent || '').trim()),
      ruled,
      computing: !!Array.from(document.querySelectorAll('p,span,div'))
        .find((n) => (n.textContent || '').includes('در حال محاسبه')),
    };
  });
  samples.push({ ms: Date.now() - t0, ...s });
  if (!shot && s.changed_rows > 0) {
    await page.screenshot({ path: '_audit/ws15_live_changed.png' });
    shot = true;
  }
  if (!toggled && Date.now() - t0 > 6_000) {
    await page.click('[data-testid="funnel-mode-custom"]', { timeout: 8000 });
    toggled = true;
  }
  await page.waitForTimeout(1500);
}
const ruledSets = new Set(samples.map((s) => s.ruled.join('|')));
const report = {
  seconds: SECONDS,
  samples: samples.length,
  samples_with_changed_rows: samples.filter((s) => s.changed_rows > 0).length,
  max_changed_rows: Math.max(0, ...samples.map((s) => s.changed_rows)),
  distinct_ruled_counters: ruledSets.size,
  delta_chips_seen: samples.some((s) => s.delta_chips.length > 0),
  computing_seen: samples.some((s) => s.computing),
  gate_toggled: toggled, stage_cards: stages, tech_gate_present: gate,
  screenshot: shot ? '_audit/ws15_live_changed.png' : null,
  page_errors: errs,
  first: samples[0] ?? null,
  last: samples[samples.length - 1] ?? null,
};
writeFileSync('_audit/ws15_live_changes.json', JSON.stringify({ report, samples }, null, 2));
console.log(JSON.stringify(report, null, 2));
await browser.close();
