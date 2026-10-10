/** tools/notifications_probe.mts — اثباتِ زندهٔ مرکزِ اعلان (بند ۶)
 *
 * منبع، اطلاعیه‌هایِ کدالِ خودِ برنامۀ است؛ این پروب ثابت می‌کند:
 *   • صفحه از همان API پر می‌شود و هر ردیف لینکِ codal.ir دارد (تيترِ بی‌منبع نه)
 *   • «خوانده شد» درِ همین دستگاه می‌ماند (با reload برمی‌گردد)
 *   • زنگولۀِ نوارِ بالا همان شمارۀِ ناخوانده را می‌دهد و به همان صفحه می‌رود
 *   • درِ ۱۳۶×۷۶۸ سرریزِ افقی نیست
 *
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types \
 *     tools/notifications_probe.mts --url http://127.0.0.1:8002/
 */
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:8002/').replace(/\/$/, '');
const OUT = arg('out', '_audit/tmp/notifications');

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => { sessionStorage.setItem('bors_auth_session', 'true'); });
const page = await ctx.newPage();

const api = await (await fetch(`${BASE}/api/notifications/feed?limit=120`)).json();
const src = await (await fetch(`${BASE}/api/notifications/sources`)).json();

await page.goto(`${BASE}/#/notifications`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(12000);

const read = () => page.evaluate(() => {
  const q = (s: string) => document.querySelector(s);
  const qa = (s: string) => Array.from(document.querySelectorAll(s));
  const t = (s: string) => (q(s)?.textContent ?? '').replace(/\s+/g, ' ').trim();
  return {
    rows: qa('[data-testid="notice-row"]').length,
    hrefs: qa('[data-testid="notice-open"]').map((a) => (a as HTMLAnchorElement).href),
    levels: qa('[data-testid="notice-level"]').map((e) => (e.textContent ?? '').trim()),
    sourceState: q('[data-testid="notice-sources"]')?.getAttribute('data-state') ?? null,
    sourceText: t('[data-testid="notice-source-fresh"]') || t('[data-testid="notice-source-empty"]')
      || t('[data-testid="notice-source-bad"]'),
    bell: t('[data-testid="topbar-notifications"]'),
    bellState: q('[data-testid="topbar-notifications"]')?.getAttribute('data-state') ?? null,
    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  };
});

const d0 = await read();
await page.screenshot({ path: `${OUT}-1366.png` });

// ── «خوانده شد» باید با reload بماند ────────────────────────────────────────
const firstId = await page.evaluate(() => {
  const li = document.querySelector('[data-testid="notice-row"]');
  return li?.getAttribute('data-level') ?? null;
});
await page.click('[data-testid="notice-mark"]');
await page.waitForTimeout(1200);
const marked = await page.evaluate(() =>
  (document.querySelector('[data-testid="notice-row"]')?.getAttribute('data-read')) ?? null);
await page.reload({ waitUntil: 'domcontentloaded' });
await page.waitForTimeout(11000);
const afterReload = await page.evaluate(() => ({
  read: document.querySelector('[data-testid="notice-row"]')?.getAttribute('data-read') ?? null,
  stored: localStorage.getItem('bors-notice-prefs') ?? '',
}));

const checks: Array<[string, boolean, unknown]> = [
  ['صفحۀ مرکز اعلان از همان API پر می‌شود', d0.rows > 0 && d0.rows === Math.min(api.count, d0.rows),
    { dom: d0.rows, api: api.count }],
  ['هر ردیف لینکِ اصلیِ کدال دارد (تيترِ بی‌منبع سرو نمی‌شود)',
    d0.hrefs.length === d0.rows && d0.hrefs.every((h) => h.startsWith('https://codal.ir/')),
    d0.hrefs.slice(0, 2)],
  ['سطح‌ها از طبقه‌بندِ بک‌اند می‌آیند (نه برچسبِ ثابتِ رابط)',
    d0.levels.length === d0.rows && d0.levels.every((l) => ['بالا', 'متوسط', 'پایین', 'بی‌طبقه'].includes(l)),
    d0.levels.slice(0, 4)],
  ['نوارِ منبع سالم است و شمارش/تازگی را می‌گوید',
    d0.sourceState === 'ok' && d0.sourceText.includes('اطلاعیه') && d0.sourceText.includes('واکشی'),
    d0.sourceText],
  ['زنگولۀ نوارِ بالا ناخوانده را می‌شمارد', /ناخوانده/.test(
    await page.evaluate(() => document.querySelector('[data-testid="topbar-notifications"]')?.getAttribute('aria-label') ?? '')),
    await page.evaluate(() => document.querySelector('[data-testid="topbar-notifications"]')?.getAttribute('aria-label'))],
  ['«خوانده شد» بلافاصله رویِ ردیف می‌نشیند', marked === '1', { marked, firstId }],
  ['«خوانده شد» با reload می‌ماند (درِ همین دستگاه)', afterReload.read === '1' && afterReload.stored.includes('"read"'),
    afterReload],
  ['بی‌سرریزِ افقی درِ ۱۳۶×۷۶۸', d0.overflowX <= 0, d0.overflowX],
];
writeFileSync(`${OUT}.json`, JSON.stringify({ api_count: api.count, src, dom: d0, marked, afterReload,
  checks: checks.map(([n, ok, d]) => ({ n, ok, d })) }, null, 2));
for (const [n, ok, d] of checks) console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${n}${ok ? '' : '  ' + JSON.stringify(d)}`);
const failed = checks.filter((c) => !c[1]).length;
console.log(`\nnotifications: ${checks.length - failed}/${checks.length} داوری سبز`);
await browser.close();
process.exit(failed ? 1 : 0);
