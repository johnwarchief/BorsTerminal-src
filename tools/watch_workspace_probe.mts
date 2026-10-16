/**
 * tools/watch_workspace_probe.mts — اثباتِ زندهٔ «دیده‌بان بازار»
 *
 * از ناوبریِ واقعی واردِ زیرتب می‌شود، نمادِ رصد را از localStorage می‌خواند، و
 * این را اندازه می‌گیرد: ستون‌هایِ مرجع با عددِ واقعی، هماهنگیِ هر سه پنل با یک
 * کلیک، نبودِ درخواستِ عمقِ ردیف‌به‌ردیف (شمارشِ request‌ها)، چیدمانِ ۱۳۶۶×۷۶۸
 * و ۱۹۲۰×۱۰۸۰، و سرریزِ افقی. خروجی JSONِ همین پروب + اسکرین‌شات.
 *
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types \
 *     tools/watch_workspace_probe.mts --url http://127.0.0.1:8002/ --out _audit/tmp/watch_live
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const BASE = arg('url', 'http://127.0.0.1:8002/').replace(/\/$/, '');
const OUT = arg('out', '_audit/tmp/watch_live');
const WAIT = Number.parseInt(arg('wait', '13000'), 10);

const SYMBOLS = ['شپنا', 'فولاد', 'خودرو', 'وغدار', 'کچاد', 'تاپای', 'شتران', 'وزواری'];

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });
mkdirSync('_audit/tmp', { recursive: true });

const STATE = () => {
  const q = (s: string) => document.querySelector(s);
  const qa = (s: string) => Array.from(document.querySelectorAll(s));
  const txt = (el: Element | null) => (el?.textContent || '').replace(/\s+/g, ' ').trim();
  const de = document.documentElement;
  const heads = qa('[data-testid="watch-table"] thead th').map((th) => txt(th));
  const firstRow = q('[data-testid^="watch-row-"]');
  return {
    hash: location.hash,
    overflowX: de.scrollWidth - de.clientWidth,
    tableHeaders: heads,
    rowCount: qa('[data-testid^="watch-row-"]').length,
    firstRowText: txt(firstRow),
    candles: qa('[data-testid="watch-day-candle"]').length,
    chartSymbol: q('[data-testid="watch-chart"]')?.getAttribute('data-symbol') ?? null,
    bookSymbol: q('[data-testid="watch-orderbook"]')?.getAttribute('data-symbol') ?? null,
    summarySymbol: q('[data-testid="watch-summary"]')?.getAttribute('data-symbol') ?? null,
    bookLevels: qa('[data-testid="watch-orderbook-rows"] li').length,
    bookText: txt(q('[data-testid="watch-orderbook"]')).slice(0, 160),
    summaryLast: txt(q('[data-testid="watch-summary-last"]')),
    summaryTime: txt(q('[data-testid="watch-summary-row-time"]')),
    orderPanel: txt(q('[data-testid="watch-order-panel"]')).slice(0, 200),
    buyDisabled: (q('[data-testid="watch-order-buy"]') as HTMLButtonElement | null)?.disabled ?? null,
    killDisabled: (q('[data-testid="watch-kill-switch"]') as HTMLButtonElement | null)?.disabled ?? null,
    heights: {
      table: Math.round(q('[data-testid="watch-table"]')?.getBoundingClientRect().height ?? 0),
      panels: Math.round(q('[data-testid="watch-orderbook"]')?.getBoundingClientRect().height ?? 0),
      page: Math.round(de.scrollHeight),
    },
  };
};

const out: Record<string, unknown> = { base: BASE, at: new Date().toISOString(), symbols: SYMBOLS, runs: {} };

for (const [w, h] of [[1366, 768], [1920, 1080]] as const) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h } });
  const reqs: string[] = [];
  ctx.on('request', (r: any) => {
    const u = String(r.url());
    if (u.includes('/api/')) reqs.push(u.replace(BASE, ''));
  });
  await ctx.addInitScript((syms) => {
    try {
      sessionStorage.setItem('bors_auth_session', 'true');
      localStorage.setItem('bors-portfolio-watch', JSON.stringify(syms));
    } catch {
      /* noop */
    }
  }, SYMBOLS);
  const page = await ctx.newPage();
  const errors: string[] = [];
  page.on('console', (m: any) => {
    if (m.type() === 'error') errors.push(String(m.text()).slice(0, 180));
  });
  const rec: Record<string, unknown> = {};

  const t0 = Date.now();
  await page.goto(`${BASE}/#/portfolio`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(WAIT);
  rec.loadMs = Date.now() - t0;

  await page.locator('button:has-text("دیده‌بان بازار")').first().click();
  await page.waitForTimeout(2500);
  rec.before = await page.evaluate(STATE);
  rec.requestsAfterOpen = reqs.slice();
  await page.screenshot({ path: `${OUT}-${w}-before.png` });

  // کلیک رویِ ردیفِ دوم: هر سه پنل باید به همان نماد بروند
  const rows = await page.locator('[data-testid^="watch-row-"]').all();
  const target = rows.length > 1 ? 1 : 0;
  const targetSymbol = (await rows[target].getAttribute('data-testid'))?.replace('watch-row-', '') ?? '';
  await rows[target].click();
  await page.waitForTimeout(3500);
  rec.clickedSymbol = targetSymbol;
  rec.after = await page.evaluate(STATE);
  await page.screenshot({ path: `${OUT}-${w}-after.png` });

  // حذفِ یک نماد: شمارۀ ردیف‌ها باید کم شود
  const beforeCount = (rec.after as Record<string, unknown>).rowCount;
  const rm = page.locator(`[data-testid="watch-remove-${targetSymbol}"]`).first();
  if (await rm.count()) {
    await rm.click();
    await page.waitForTimeout(1500);
    rec.rowCountAfterRemove = (await page.evaluate(STATE)).rowCount;
    rec.rowCountBeforeRemove = beforeCount;
  }
  rec.perRowBookRequests = reqs.filter((u) => u.includes('/api/order-book/')).length;
  rec.marketRequests = reqs.filter((u) => u.includes('/api/market')).length;
  rec.totalApiRequests = reqs.length;
  rec.errors = errors.slice(0, 5);
  (out.runs as Record<string, unknown>)[`${w}x${h}`] = rec;
  await ctx.close();
}

writeFileSync(`${OUT}.json`, JSON.stringify(out, null, 2), 'utf-8');
console.log('WROTE', `${OUT}.json`);
await browser.close();
