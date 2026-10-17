/** tools/market_state_probe.mts — اثباتِ زندهٔ «وضعیت بازارِ زمان‌مند» (مأموریت 1405-07-20)
 *
 * سه چیز مقابله می‌شود:
 *   ۱) آنچه پنلِ «ورود به بازار» می‌نویسد = آنچه /api/mstat/smart-money می‌گوید
 *      (تیتر، سطرِ مرحل، چیپ‌ها) — یک منبع، نه دو؛
 *   ۲) درِ ابتدایِ نشست، «امروز وارد نشو» یا هر حکمِ قطعیِ منفی رویِ جمعِ ناقص
 *      صادر نمی‌شود (کنترلِ اصلیِ شکایتِ مالک)؛
 *   ۳) قدِ پنل (مالک: کوتاه‌ترش بکن) — ارتفاعِ VerdictStrip گزارش می‌شود.
 *
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types \
 *     tools/market_state_probe.mts --url http://127.0.0.1:8003/ --out _audit/tmp/mstate_after
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
const BASE = arg('url', 'http://127.0.0.1:8003/').replace(/\/$/, '');
const OUT = arg('out', '_audit/tmp/mstate');

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
const page = await ctx.newPage();
await page.addInitScript(() => { sessionStorage.setItem('bors_auth_session', 'true'); });

const api = await (await fetch(`${BASE}/api/mstat/smart-money`)).json();
const vd = api.verdict ?? {};
const ms = vd.market_state ?? null;

await page.goto(`${BASE}/#/market-status`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="pulse-verdict-label"]', { timeout: 45000 });
await page.waitForTimeout(3000);
const dom = await page.evaluate(() => {
  const q = (s: string) => document.querySelector(s);
  const t = (s: string) => (q(s)?.textContent ?? '').replace(/\s+/g, ' ').trim();
  const el = q('[data-testid="pulse-verdict"]');
  return {
    panel: !!el,
    height: el ? Math.round(el.getBoundingClientRect().height) : null,
    label: t('[data-testid="pulse-verdict-label"]'),
    reason: t('[data-testid="pulse-verdict-reason"]'),
    stage: t('[data-testid="pulse-verdict-stage"]'),
    chips: [...document.querySelectorAll('[data-testid^="pulse-verdict-gate-"]')].map(x => x.textContent),
    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  };
});
const shot = `${OUT}-1366.jpeg`;
await page.screenshot({ path: shot, type: 'jpeg', quality: 70 } as any);

const checks: Array<[string, boolean, unknown]> = [
  ['پنلِ حکم دیدنی است (کنترلِ رسیدن)', dom.panel && !!dom.label, dom.panel],
  ['تیترِ صفحه = تیترِ موتور', dom.label === (vd.label ?? ''), { dom: dom.label, api: vd.label }],
  ['سطرِ مرحل = stage_labelِ موتور (بی‌داوریِ لایۀ نمایش)',
    !ms || dom.stage.includes(ms.stage_label ?? ''), { dom: dom.stage, api: ms?.stage_label }],
  ['هیچ «وارد نشو»ای بی‌رأیِ قاطعِ موتور رویِ صفحه نیست',
    (vd.verdict === 'avoid') === dom.label.includes('وارد نشو'), { dom: dom.label, verdict: vd.verdict }],
  ['افقیِ صفحه سرریز ندارد (RTL)', dom.overflowX <= 0, dom.overflowX],
];
const failed = checks.filter(([, ok]) => !ok);
writeFileSync(`${OUT}.json`, JSON.stringify({ base: BASE, at: new Date().toISOString(),
  api_verdict: vd.verdict, api_label: vd.label, market_state: ms, dom, checks }, null, 1));
for (const [name, ok, detail] of checks) console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${ok ? '' : '  ' + JSON.stringify(detail)}`);
console.log(`قدِ پنل: ${dom.height}px | مرحل: ${ms?.stage} | حکم: ${vd.verdict} "${vd.label}" | ${dom.stage}`);
await browser.close();
process.exit(failed.length ? 1 : 0);
