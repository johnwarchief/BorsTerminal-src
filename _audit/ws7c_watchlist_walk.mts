// _audit/ws7c_watchlist_walk.mts — راهِ واقعیِ واچ‌لیست، end-to-end درِ مرورگر
//
// سناریویِ خودِ مالک (§۳۰): از تابلو ★ می‌زند → درِ Portfolio → پرتفوی فعلی →
// واچ‌لیست می‌نشیند → با reload هم می‌ماند → درِ بنیادی هم همان نشان را دارد →
// ★ را می‌زنی و می‌رود بیرون. سه چیزِ دیگر هم سنجیده می‌شود:
//   • add optimistic است و یک add ساده کلِ تابلو را دوباره نمی‌گیرد،
//   • نشانگرِ ستاره با selection (☑) قاطی نمی‌شود،
//   • خطایِ کنسول و پاسخِ بد نداریم.
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:5173/');
const OUT = '_audit/ws7c_watchlist_walk.json';

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const consoleErrors: string[] = [];
page.on('console', (m: any) => {
  if (m.type() === 'error' || m.type() === 'warning') {
    const loc = m.location?.() ?? {};
    consoleErrors.push(`${m.type()}: ${m.text().slice(0, 140)} @ ${String(loc.url ?? '')}`);
  }
});
page.on('pageerror', (e: any) => consoleErrors.push(`pageerror: ${String(e.message).slice(0, 140)}`));
let apiCalls: string[] = [];
const resetCalls = () => { apiCalls = []; };
const snapCalls = () => apiCalls.slice();
page.on('request', (r: any) => {
  const u = String(r.url()).replace(/^https?:\/\/[^/]+/, '');
  if (u.startsWith('/api/')) apiCalls.push(`${r.method()} ${u}`);
});
const badResponses: string[] = [];
page.on('response', (r: any) => { if (r.status() >= 400) badResponses.push(`${r.status()} ${String(r.url()).replace(/^https?:\/\/[^/]+/, '')}`); });

const starState = (sym: string) => page.evaluate((s: string) => {
  const el = document.querySelector(`[data-testid="watch-star-${s}"]`);
  return el ? { present: true, inList: el.getAttribute('data-in-list'),
                label: el.getAttribute('aria-label'), glyph: el.textContent } : { present: false };
}, sym);
const firstStarSymbol = () => page.evaluate(() => {
  const el = Array.from(document.querySelectorAll('[data-testid^="watch-star-"]'))[0];
  return el ? el.getAttribute('data-testid')!.replace('watch-star-', '') : null;
});

const steps: Record<string, unknown> = {};

// ۱) تابلو: نخستین ستاره
await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid^="watch-star-"]', { timeout: 120_000 });
const SYM = (await firstStarSymbol())!;
steps.symbol = SYM;
steps.market_before = await starState(SYM);

// ۲) ★ → optimistic: ستاره بی‌درخواستِ تابلویِ تازه برمی‌گردد
resetCalls();
// نامِ نماد فاصله دارد («پر ر ۶۰») — پس با getByTestId، نه با selectorِ دستی.
await page.getByTestId(`watch-star-${SYM}`).click();
const afterClick = await page.evaluate((s: string) => {
  const el = document.querySelector(`[data-testid="watch-star-${s}"]`);
  return { inList: el?.getAttribute('data-in-list') ?? null, glyph: el?.textContent ?? null };
}, SYM);
await page.waitForTimeout(1500);
steps.market_after_click = afterClick;
steps.calls_for_click = snapCalls();
steps.market_refetch_triggered = snapCalls().some((c) => /GET \/api\/market/.test(c));

// ۳)reload → ماندگاری از سرور
await page.reload({ waitUntil: 'domcontentloaded' });
await page.waitForSelector(`[data-testid="watch-star-${SYM}"]`, { timeout: 60_000 });
steps.market_after_reload = await starState(SYM);

// ۴) Portfolio → پرتفوی فعلی → واچ‌لیست
// سوییچرِ پرتفوی `role="tab"` است، نه `role="button"` — با nameِ button پیدا نمی‌شد
// و view رویِ «هدف» می‌ماند، پس سکشنِ واچ‌لیست هرگز رندر نمی‌شد.
await page.goto(`${BASE}#/portfolio`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(1500);
const currentTab = page.getByRole('tab', { name: 'پرتفوی فعلی' });
steps.current_tab_found = await currentTab.count();
if (await currentTab.count()) await currentTab.first().click();
await page.waitForTimeout(2500);
steps.watchlist_section = await page.evaluate((s: string) => ({
  sectionPresent: !!document.querySelector('[data-testid="portfolio-watchlist"]'),
  rowPresent: !!document.querySelector(`[data-testid="portfolio-watchlist-open-${s}"]`),
  rows: Array.from(document.querySelectorAll('[data-testid^="portfolio-watchlist-open-"]'))
    .map((el) => el.getAttribute('data-testid')!.replace('portfolio-watchlist-open-', '')).slice(0, 12),
  emptyShown: !!document.querySelector('[data-testid="portfolio-watchlist-empty"]'),
}), SYM);

// ۵) بنیادی: همان نشان درِ سطحی دیگر — با نمادِ *خودِ این سطح*، چون «وبشهرح»
// صندوق است و درِ جدولِ اسکرینر (۸۷۳ شرکت) ردیف ندارد؛ نبودش درِ DOM یعنی
// سنسورِ اشتباه، نه نقصِ نشانگر.
await page.goto(`${BASE}#/fundamental`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(3000);
const SYM_B = await page.evaluate(() => {
  const el = Array.from(document.querySelectorAll('[data-testid^="watch-star-"]'))[0];
  return el ? el.getAttribute('data-testid')!.replace('watch-star-', '') : null;
});
steps.symbol_fundamental = SYM_B;
steps.fundamental_before = SYM_B ? await starState(SYM_B) : null;
if (SYM_B) {
  resetCalls();
  await page.getByTestId(`watch-star-${SYM_B}`).click();
  await page.waitForTimeout(1200);
  steps.fundamental_after_click = await starState(SYM_B);
  steps.fundamental_calls = snapCalls();
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid^="watch-star-"]', { timeout: 60_000 });
  const SYM_B2 = await page.evaluate(() => {
    const el = Array.from(document.querySelectorAll('[data-testid^="watch-star-"]'))[0];
    return el ? el.getAttribute('data-testid')!.replace('watch-star-', '') : null;
  });
  steps.fundamental_after_reload = SYM_B2 ? await starState(SYM_B2) : null;
  if (SYM_B2) { await page.getByTestId(`watch-star-${SYM_B2}`).click(); await page.waitForTimeout(900); }
}

// ۶) حذف ازِ همان ستارهٔ تابلو و بررسیِ بیرون‌رفتنِ سطر
await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector(`[data-testid="watch-star-${SYM}"]`, { timeout: 60_000 });
resetCalls();
await page.getByTestId(`watch-star-${SYM}`).click();
await page.waitForTimeout(1200);
steps.market_after_remove = await starState(SYM);
steps.calls_for_remove = snapCalls();

await page.screenshot({ path: '_audit/ws7c_watchlist_market.png' });

const out = { base: BASE, at: new Date().toISOString(), steps,
              consoleErrors: consoleErrors.slice(0, 10), badResponses: badResponses.slice(0, 10),
              verdicts: {
                star_exists_in_market: !!SYM,
                add_flips_marker: (steps.market_after_click as any).inList === '1',
                no_full_market_refetch_on_add: !(steps as any).market_refetch_triggered,
                persists_across_restart: (steps.market_after_reload as any).inList === '1',
                row_in_portfolio_watchlist: (steps.watchlist_section as any).rowPresent,
                fundamental_surface_has_star: !!steps.symbol_fundamental,
                fundamental_add_flips: (steps.fundamental_after_click as any)?.inList === '1',
                fundamental_persists: (steps.fundamental_after_reload as any)?.inList === '1',
                remove_flips_back: (steps.market_after_remove as any).inList === '0',
                zero_bad_responses: badResponses.length === 0,
              } };
mkdirSync('_audit', { recursive: true });
writeFileSync(OUT, JSON.stringify(out, null, 2));
console.log(JSON.stringify(out.verdicts, null, 2));
console.log(`symbol=${SYM} calls_for_click=${JSON.stringify(out.steps.calls_for_click)}`);
console.log(`consoleErrors=${consoleErrors.length} bad=${badResponses.length}`);
await browser.close();
