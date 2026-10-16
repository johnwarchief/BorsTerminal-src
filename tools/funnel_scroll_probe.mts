/** _audit/funnel_scroll_probe.mts — جدولِ مجازی‌شدهٔ قیف با اسکرولِ واقعی ردیف‌هایش را می‌سازد؟
 *
 * چرا: درِ StageCard مجازی‌ساز `getScrollElement: () => scrollRef.current` می‌خواند،
 * ولی همان قوسِ اسکرول با `bodyRef` به DOM وصل شده است. اگر scrollRef هیچ‌وقت
 * وصل نشود، مجازی‌ساز فقط پنجرۀ initialRect (۳۸۰ پیکسل) را می‌بیند و ردیف‌هایِ
 * پایین‌تر هرگز ساخته نمی‌شوند — یعنی «جدولِ ۱۰۶۵ ردیفه» رویِ صفحه ~۱۱ ردیف
 * بیشتر ندارد و اسکرول هم چیزی اضافه نمی‌کند. این اسکریپت همان را اندازه می‌گیرد:
 * شمارشِ سرور، شمارشِ DOM درِ بالا، شمارشِ DOM بعد از اسکرولِ واقعی تا انتها.
 */
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:8124').replace(/\/$/, '');
const STAGE = arg('stage', 'tape');

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
const page = await ctx.newPage();
await page.addInitScript(() => { sessionStorage.setItem('bors_auth_session', 'true'); });

const server = await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' })
  .then(() => page.evaluate(async (st) => {
    const j = await (await fetch(`/api/funnel?preset=custom&stage=${st}`)).json();
    const e = (j.entries || {})[st] || [];
    return { rows: e.length, first: e[0]?.symbol ?? null, last: e[e.length - 1]?.symbol ?? null };
  }, STAGE));
console.log(`سرور: ${server.rows} ردیف درِ entries.${STAGE} (نخست ${server.first} · آخر ${server.last})`);

await page.goto(`${BASE}/#/master?stage=${STAGE}&preset=custom`, { waitUntil: 'domcontentloaded' });
const sel = `[data-testid="funnel-scroll-${STAGE}"]`;
for (let i = 0; i < 20; i++) {
  const has = await page.evaluate((s) => !!document.querySelector(s), sel);
  if (has) break;
  await page.waitForTimeout(1000);
}
await page.waitForTimeout(4000);

const measure = () => page.evaluate(async (s) => {
  const el = document.querySelector(s) as HTMLElement | null;
  if (!el) return null;
  const trs = el.querySelectorAll('tbody tr');
  const txt = (n: number) => trs[n]?.querySelector('td')?.innerText?.trim() ?? null;
  return {
    domRows: trs.length,
    scrollHeight: el.scrollHeight,
    clientHeight: el.clientHeight,
    scrollTop: el.scrollTop,
    firstSymbol: txt(0),
    lastSymbol: txt(Math.max(0, trs.length - 1)),
  };
}, sel);

const top = await measure();
console.log('درِ بالایِ اسکرول:', JSON.stringify(top));
if (top) {
  await page.evaluate((s) => {
    const el = document.querySelector(s) as HTMLElement;
    el.scrollTop = el.scrollHeight;
    el.dispatchEvent(new Event('scroll'));
  }, sel);
  await page.waitForTimeout(2500);
  const bottom = await measure();
  console.log('بعد از اسکرول تا انتها:', JSON.stringify(bottom));
  const grew = (bottom?.domRows ?? 0) > (top.domRows ?? 0) || bottom?.lastSymbol !== top?.lastSymbol;
  console.log(grew
    ? 'PASS  اسکرولِ واقعی ردیف‌هایِ تازه می‌سازد'
    : 'FAIL  اسکرول هیچ ردیفِ تازه‌ای نساخت — مجازی‌ساز عنصرِ اسکرول را نمی‌بیند');
}
await page.screenshot({ path: '_audit/funnel_scroll_probe.png' });
await browser.close();
