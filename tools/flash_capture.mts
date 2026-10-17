/** tools/flash_capture.mts — تصویرِ ثابتِ فلاش رویِ ردیف‌هایِ واقعیِ تابلو
 *   فلاش را رویِ یک خانۀِ «آخرین» می‌زند، انیمیشن را pause و به درصدِ خواسته
 *   می‌بَرَد (scrub) و اسکرین‌شات می‌گیرد تا «اوجِ نرم» قابلِ دیدن باشد.
 *   node --experimental-strip-types tools/flash_capture.mts --url URL --out PATH [--pct 0.12]
 */
import { mkdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (r: string) => import(pathToFileURL(`${PKG}/${r}`).href);
const arg = (n: string, f = '') => { const i = process.argv.indexOf(`--${n}`); return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f; };
const BASE = arg('url').replace(/\/$/, '');
const OUT = arg('out');
const PCT = parseFloat(arg('pct', '0.12'));
mkdirSync(OUT.replace(/[^/]*$/, ''), { recursive: true });
const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
const page = await ctx.newPage();
await page.addInitScript(() => { sessionStorage.setItem('bors_auth_session', 'true'); });
await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="tape-buy-sell"]', { timeout: 60000 });
await page.waitForTimeout(1500);
await page.evaluate((pct: number) => {
  // نخستین خانۀ «آخرین» در ردیفِ واقعی (FlashNum ریشۀ .num.inline-block در ستونِ قیمت)
  const cell = document.querySelector('[data-testid="tape-buy-sell"]')!.parentElement!
    .querySelector('.num.inline-block') as HTMLElement;
  cell.classList.remove('flash-up', 'flash-down');
  void cell.offsetWidth;
  cell.classList.add('flash-up');
  const a = cell.getAnimations()[0] as CSSAnimation;
  const d = (a.effect!.getComputedTiming().duration as number) || 1600;
  a.pause();
  a.currentTime = pct * d;
}, PCT);
await page.screenshot({ path: OUT, type: 'jpeg', quality: 72 } as any);
console.log('shot', OUT, 'pct', PCT);
await browser.close();
