/** tools/tape_screening_live.mts — بررسیِ زندهٔ «هماهنگی شمارندۀ تابلو و غربالگری» (گزینهٔ الف)
 *   قیف با دادۀ واقعیِ بک‌اند: بخشِ «خارج از جامعۀ غربالگری» باز می‌شود، شمارۀ
 *   جامعۀ تابلو در برابرِ واجدِ غربالگری و علت‌هایِ خروج دیده می‌شوند، و
 *   توضیحِ تفاوتِ تابلو/غربالگری (`funnel-universe-reconcile`) عیناً حاضر است.
 *   (برچسبِ «خارج از غربالگری» درِ ردیفِ تابلو با آزمونِ واحدِ TapeRow و تولیدِ
 *   فیلد درِ پایتون اثبات می‌شود؛ mockِ زندهٔ تابلو با پولینگِ دلتا شکننده است.)
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (r) => import(pathToFileURL(`${PKG}/${r}`).href);
const arg = (n, f = '') => { const i = process.argv.indexOf(`--${n}`); return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f; };
const BASE = arg('url', 'http://127.0.0.1:5173/').replace(/\/$/, '');
const OUT = arg('out', '_audit/flash/reconcile');
mkdirSync(OUT.replace(/[^/]*$/, ''), { recursive: true });
const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => { sessionStorage.setItem('bors_auth_session', 'true'); });
const page = await ctx.newPage();

await page.goto(`${BASE}/#/master`, { waitUntil: 'domcontentloaded' });
let ok = true;
try {
  await page.waitForSelector('[data-testid="funnel-universe-excluded"]', { timeout: 60000 });
} catch { ok = false; }
let funnel = { ok };
if (ok) {
  await page.waitForTimeout(1500);
  const excl = (await page.locator('[data-testid="funnel-universe-excluded"]').textContent() || '').trim();
  const market = (await page.locator('[data-testid="funnel-universe-market"]').textContent() || '').trim();
  const screening = (await page.locator('[data-testid="funnel-universe-screening"]').textContent() || '').trim();
  await page.click('[data-testid="funnel-universe-excluded"]').catch(() => {});
  await page.waitForTimeout(700);
  funnel = await page.evaluate((x) => {
    const note = document.querySelector('[data-testid="funnel-universe-reconcile"]');
    const reasons = [...document.querySelectorAll('[data-testid^="funnel-exclusion-"]')]
      .map((e) => (e.textContent || '').trim())
      .filter((t) => t && !t.includes('خارج از جامعه نیست'));
    return {
      excludedToggle: x.excl, market: x.market, screening: x.screening,
      hasNote: !!note, noteText: (note?.textContent || '').replace(/\s+/g, ' ').trim(),
      reasonChips: reasons.slice(0, 6),
    };
  }, { excl, market, screening });
  await page.screenshot({ path: `${OUT}-funnel.jpeg`, type: 'jpeg', quality: 72 });
}

const checks = [
  ['قیف باز شد؛ جامعۀ تابلو در برابرِ واجدِ غربالگری دیده می‌شود', ok && /جامعۀ تابلو/.test(funnel.market || '') && /واجدِ غربالگری/.test(funnel.screening || ''), { market: funnel.market, screening: funnel.screening }],
  ['شمارۀ «خارج از جامعۀ غربالگری» دیدنی است', /خارج از جامعۀ غربالگری/.test(funnel.excludedToggle || ''), funnel.excludedToggle],
  ['علتِ خروج (پسوندِ عددی/کهنه/ممنوع/متوقف) شمرده می‌شود', (funnel.reasonChips || []).length > 0, funnel.reasonChips],
  ['توضیحِ تفاوتِ تابلو/غربالگری (#4) حاضر و درست است', funnel.hasNote && /جامعۀ نماد/.test(funnel.noteText || '') && /نه اختلافِ محاسبه/.test(funnel.noteText || ''), (funnel.noteText || '').slice(0, 90)],
];
const failed = checks.filter((x) => !x[1]);
writeFileSync(`${OUT}.json`, JSON.stringify({ base: BASE, funnel, checks }, null, 1));
for (const c of checks) console.log(`${c[1] ? 'PASS' : 'FAIL'} ${c[0]}${c[1] ? '' : '  ' + JSON.stringify(c[2])}`);
await browser.close();
process.exit(failed.length ? 1 : 0);
