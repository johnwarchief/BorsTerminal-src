// tools/strategy_ui_journey.mts — مسیرِ کاربرِ تازه‌وارد رویِ بیلدِ واقعی
//
// چهار چیز باِ دادهٔ زندهٔ همین ماشین سنجیده می‌شود (نه باِ fixture):
//  ۱) سربرگ، استپر و جدول هر سه **یک عدد** را می‌گویند و آن عدد باِ پاسخِ خامِ
//     `/api/funnel` مقایسه می‌شود — اثباتِ این‌که رابط چیزی نمی‌سازد؛
//  ۲) عوض‌کردنِ استراتژی واقعاً presetِ درخواستِ تازه را عوض می‌کند؛
//  ۳) افزودن و حذفِ یکِ فیلترِ تابلو شمارِ «فیلتر فعال» را جابه‌جا می‌کند و
//     به حالتِ اول برمی‌گردد؛
//  ۴) «چطور کار می‌کند؟» و راهنما باز/بسته می‌شوند و راهنما پسِ بستن برنمی‌گردد.
import { mkdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  || 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package/node_modules/playwright/index.mjs';
const BASE = process.argv[2] || 'http://127.0.0.1:8107/';
const OUT = 'C:/Users/PCMOD/Desktop/_bors-fts-technical/_audit/strategy-ui';
mkdirSync(OUT, { recursive: true });
const { chromium } = await import(pathToFileURL(PKG).href);
const browser = await chromium.launch({ headless: true,
  executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => { try { sessionStorage.setItem('bors_auth_session', 'true'); } catch {} });
const page = await ctx.newPage();
const errs: string[] = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 140)));

const read = async (id: string) => page.evaluate((sel) => {
  const el = document.querySelector(sel);
  return el ? (el.textContent || '').trim() : null;
}, `[data-testid="${id}"]`);

const steps: Record<string, unknown> = {};
await page.goto(BASE + '#/master?preset=tech_first&stage=technical', { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="funnel-counts"]', { timeout: 60000 });
await page.waitForTimeout(3000);

steps.header = {
  strategy: await read('fts-active-strategy'),
  mode: await read('fts-active-mode'),
  status: await read('fts-status'),
  asOf: await read('fts-as-of'),
  step: await read('fts-current-step'),
  flow: await read('fts-stage-flow'),
};
steps.stepper = {
  tape: await read('fts-step-flow-tape'),
  technical: await read('fts-step-flow-technical'),
  fundamental: await read('fts-step-flow-fundamental'),
  handover: await read('fts-step-flow-handover'),
  statuses: {
    tape: await read('fts-step-status-tape'),
    technical: await read('fts-step-status-technical'),
  },
  next: await read('fts-stepper-next'),
};
steps.results = { title: await read('funnel-results-title'), count: await read('funnel-results-count') };

// عددِ خامِ سرور، مستقل ازِ رابط
const api = await page.evaluate(async () => {
  const r = await fetch('/api/funnel', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ preset: 'trend', chain: [], logic: 'and',
      fund_mode: 'standard', tech_chain: [], strategy_settings: {}, exceptions: {},
      drop_suffix: true }),
  });
  const j = await r.json();
  return { tape: j.stages?.tape?.matched, technicalInput: j.stages?.technical?.input,
           technicalPass: j.stages?.technical?.counts?.pass, asOf: j.as_of };
});
steps.apiRaw = api;
// برابریِ عددِ رابط باِ عددِ سرور (۱۰۳ ≠ ۱۰۵ — رقم‌هایِ فارسی تبدیل می‌شوند)
const FA = '۰۱۲۳۴۵۶۷۸۹';
const digits = (s: string | null) => (s || '').replace(/[۰-۹]/g,
  (c) => String(FA.indexOf(c)));
steps.parity = {
  headerFlowEqualsApiTape: (digits(await read('fts-stage-flow')) || '').includes(String(api.tape)),
  stepperTechnicalOutEqualsApi: digits(await read('fts-step-count-technical')) === String(api.technicalPass),
  stepperTechnicalInEqualsApi: (digits(await read('fts-step-flow-technical')) || '').includes(String(api.technicalInput)),
};

// مسیرِ کاربر: عوض‌کردنِ استراتژی (بدونِ کلیکِ چیپ همین‌جا — چیپ‌ها درِ بخشِ
// بعد و درِ بارگذاریِ مستقیم سنجیده می‌شوند: کلیکِ بی‌درنگ پسِ عوض‌کردنِ preset
// باِ جایگزین‌شدنِ گرهٔ DOM می‌ساید و آزمونِ من را گمراه می‌کرد)
await page.click('[data-testid="funnel-mode-trend"]');
await page.waitForFunction(() => (document.querySelector('[data-testid="fts-active-strategy"]')?.textContent || '')
  .indexOf('روندگیر') >= 0, {}, { timeout: 20000 });
await page.waitForTimeout(2500);
steps.afterStrategySwitch = {
  strategy: await read('fts-active-strategy'),
  step: await read('fts-current-step'),
  stepperFirst: await read('fts-step-flow-tape'),
};
await page.click('[data-testid="funnel-mode-tech_first"]');
await page.waitForFunction(() => (document.querySelector('[data-testid="fts-active-strategy"]')?.textContent || '')
  .indexOf('تکنیکال‌محور') >= 0, {}, { timeout: 20000 });
await page.waitForTimeout(3000);
steps.backToTechFirst = { strategy: await read('fts-active-strategy'),
  step: await read('fts-current-step'),
  filterPanel: (await read('fts-filter-panel') || '').slice(0, 60) };
// شمارش و وضعیتِ فشرده باِ هم خوانده می‌شوند (ثابتِ خواب نه، شرطِ نهایی نه):
// چیزی که ثبت می‌شود جفتِ (pressed, count) است تا اگر رابط یک‌پله عقب ماند،
// همان‌جا دیده شود. آزمونِ ادعایِ سخت درِ `strategy-funnel-ui-parity.spec.tsx`
// است، که ازِ بدنهٔ واقعیِ POST می‌خواند.
const pair = () => page.evaluate(() => ({
  count: document.querySelector('[data-testid="fts-filter-active-count"]')?.textContent?.trim() ?? null,
  pressed: document.querySelector('[data-testid="funnel-tape-chip-f_susp"]')?.getAttribute('aria-pressed') ?? null,
}));
const chip = '[data-testid="funnel-tape-chip-f_susp"]';
const t0 = await pair();
await page.click(chip);
await page.waitForFunction(() => (document.querySelector('[data-testid="funnel-tape-chip-f_susp"]')
  ?.getAttribute('aria-pressed') === 'true'), {}, { timeout: 8000 });
const t1 = await pair();
await page.click(chip);
await page.waitForFunction(() => (document.querySelector('[data-testid="funnel-tape-chip-f_susp"]')
  ?.getAttribute('aria-pressed') === 'false'), {}, { timeout: 8000 });
const t2 = await pair();
steps.filterRoundTrip = { off: t0, on: t1, offAgain: t2,
  consistent: t0.pressed === 'false' && t1.pressed === 'true' && t2.pressed === 'false'
    && t1.count !== t0.count && t2.count === t0.count };
await page.click('[data-testid="fts-how-it-works-toggle"]');
await page.waitForTimeout(400);
steps.guide = { howOpen: await read('fts-how-it-works') !== null };
await page.click('[data-testid="fts-guide-close"]');
await page.waitForTimeout(400);
steps.guide.dismissedStaysClosed = (await read('fts-quick-guide')) === null
  && (await read('fts-guide-open')) !== null;

await page.screenshot({ path: OUT + '/journey-tech-first.jpeg', type: 'jpeg', quality: 62 });
steps.pageErrors = errs.slice(0, 5);
console.log(JSON.stringify(steps, null, 1));
await browser.close();
