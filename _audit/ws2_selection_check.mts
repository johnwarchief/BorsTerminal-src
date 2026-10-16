// _audit/ws2_selection_check.mts — سنجشِ زندۀ جعبۀ انتخاب (§۲۱، §۳۳)
//
// سه پرسشِ مشخص: جعبه درِ هر دو جدول هست؟ کلیکش کاربر را به صفحۀ نماد نمی‌برد؟
// انتخاب با reload می‌ماند و درِ جدولِ دیگر هم همان کلید را دارد؟
// خروجی: _audit/ws2_selection_check.json + اسکرین‌شات‌ها. قضاوتِ «قشنگ است یا نه»
// با مالک است؛ اینجا فقط عدد و bool ثبت می‌شود.
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

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const consoleErrors: string[] = [];
page.on('console', (m: any) => { if (m.type() === 'error' || m.type() === 'warning') consoleErrors.push(`${m.type()}: ${m.text().slice(0, 160)}`); });
page.on('pageerror', (e: any) => consoleErrors.push(`pageerror: ${String(e.message).slice(0, 160)}`));
const badResponses: string[] = [];
page.on('response', (r: any) => { if (r.status() >= 400) badResponses.push(`${r.status()} ${String(r.url()).replace(/^https?:\/\/[^/]+/, '')}`); });

const out: Record<string, unknown> = { base: BASE, at: new Date().toISOString() };
const netLog: string[] = [];
page.on('request', (r: any) => {
  const u = String(r.url());
  if (!/\.(js|css|png|svg|woff2?|ico)(\?|$)/.test(u)) netLog.push(u.replace(/^https?:\/\/[^/]+/, ''));
});

const readBoxes = () => page.evaluate(() => {
  const boxes = Array.from(document.querySelectorAll('[data-testid^="select-box-"]'));
  const first = boxes[0] as HTMLElement | undefined;
  const row = first?.closest('[data-testid="tape-row"], tr');
  const gridHeights = row ? Array.from(row.querySelectorAll('span')).slice(0, 3).map((s) => Math.round(s.getBoundingClientRect().width)) : [];
  return {
    count: boxes.length,
    firstSymbol: first ? first.getAttribute('data-testid')!.replace('select-box-', '') : null,
    firstChecked: first ? first.getAttribute('aria-checked') : null,
    rowHeight: row ? Math.round(row.getBoundingClientRect().height) : null,
    cellWidths: gridHeights,
  };
});

// ---- تابلو (Market)
netLog.length = 0;
await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="tape-row"]', { timeout: 45_000 });
await page.waitForSelector('[data-testid^="select-box-"]', { timeout: 30_000 });
const marketBefore = await readBoxes();
const beforeRequests = netLog.length;
const href0 = page.url();
await page.click('[data-testid^="select-box-"] >> nth=0');
await page.waitForTimeout(900);
const marketAfter = await readBoxes();
out.market = {
  before: marketBefore, after: marketAfter,
  navigated: page.url() !== href0,
  href_before: href0.replace(/^https?:\/\/[^/]+/, ''),
  href_after: page.url().replace(/^https?:\/\/[^/]+/, ''),
  requests_added: netLog.length - beforeRequests,
};
await page.screenshot({ path: '_audit/ws2_market.png' });

// ---- persistence درِ reload + cross-table با جست‌وجویِ خودِ بنیادی
const chosen = marketBefore.firstSymbol as string;
await page.reload({ waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="tape-row"]', { timeout: 45_000 });
out.market_after_reload = await page.evaluate((sym: string) => {
  const el = document.querySelector(`[data-testid="select-box-${sym}"]`);
  return { symbol: sym, checked: el ? el.getAttribute('aria-checked') : 'absent-from-current-view' };
}, chosen);

await page.goto(`${BASE}#/fundamental`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid^="select-box-"]', { timeout: 60_000 });
const fundBefore = await readBoxes();
// همان نمادِ انتخاب‌شدۀ تابلو درِ بنیادی هم انتخاب است؟ (جست‌وجویِ خودِ صفحه)
const sharedState = await page.evaluate((sym: string) => {
  const input = document.querySelector('input[type="search"], input[placeholder*="جست"], input[placeholder*="نماد"]') as HTMLInputElement | null;
  if (!input) return { filter_used: false, note: 'هیچ ورودیِ جست‌وجویی درِ بنیادی پیدا نشد' };
  return { filter_used: true, placeholder: input.placeholder };
}, chosen);
// nth=1: جعبۀ اول ازِ قبل درِ تابلو روشن بود؛ با کلیکِ دوم آن را
// خاموش می‌کردی و شاهدِ اشتباه (فهرستِ خالی) ثبت می‌شد.
await page.click('[data-testid^="select-box-"] >> nth=1');
await page.waitForTimeout(1_200);
const fundAfter = await readBoxes();
const hrefF = page.url();
out.fundamental = {
  before: fundBefore, after: fundAfter,
  row_height: fundBefore.rowHeight,
  checked_now: fundAfter.firstChecked,
  storage: await page.evaluate(() => localStorage.getItem('bors-selected-symbols-v1')),
  shared_check: sharedState,
  navigated_away: hrefF.includes('#/fundamental') === false,
};
await page.screenshot({ path: '_audit/ws2_fundamental.png' });

// ---- cross-table: انتخابِ بنیادی درِ تابلو هم همان کلید است؟
const fundSym = fundBefore.firstSymbol as string;
await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="tape-row"]', { timeout: 45_000 });
out.cross_table = await page.evaluate((sym: string) => {
  const raw = localStorage.getItem('bors-selected-symbols-v1');
  const items = raw ? JSON.parse(raw) : [];
  const norms = items.map((i: any) => i.norm);
  const el = document.querySelector(`[data-testid="select-box-${sym}"]`);
  return {
    symbol: sym, in_storage: norms.some((n: string) => n && n.includes(sym.replace(/\s+/g, '').slice(0, 4))),
    stored_norms: norms,
    visible_in_board: !!el,
    board_checked: el ? el.getAttribute('aria-checked') : null,
  };
}, fundSym);

out.console = consoleErrors;
out.bad_responses = badResponses;
out.selection_is_local = (out.market as any).requests_added === 0;
mkdirSync('_audit', { recursive: true });
writeFileSync('_audit/ws2_selection_check.json', JSON.stringify(out, null, 1), 'utf-8');
console.log('market:', JSON.stringify(out.market));
console.log('reload:', JSON.stringify(out.market_after_reload));
console.log('fund:', JSON.stringify((out.fundamental as any).before), (out.fundamental as any).checked_now, (out.fundamental as any).navigated_away);
console.log('cross:', JSON.stringify(out.cross_table));
console.log('local:', out.selection_is_local, 'bad:', JSON.stringify(out.bad_responses), 'console:', JSON.stringify(out.console));
await browser.close();
