/** tools/screener_gate_check.mts — اثباتِ زندهٔ چیپِ قیف درِ جدولِ غربالگری
 *  (بند ۷.۱ مأموریت: پرچمِ کاندید از قیف می‌آید و شمارشش رویِ صفحه خواندنی است)
 *
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types \
 *     tools/screener_gate_check.mts --url http://127.0.0.1:8002/
 */
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:8002/').replace(/\/$/, '');
const FA = '۰۱۲۳۴۵۶۷۸۹';
const toEn = (s: string) => s.replace(/[۰-۹]/g, (d) => String(FA.indexOf(d)));

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
const page = await ctx.newPage();
await page.addInitScript(() => { sessionStorage.setItem('bors_auth_session', 'true'); });

const api = await (await fetch(`${BASE}/api/screener`)).json();
const apiTapeInput = api?.funnel_gate?.stages?.tape?.input ?? null;
const apiCand = (api.data as any[]).filter((r) => r.funnel_candidate).length;

await page.goto(`${BASE}/#/fundamental`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(17000);
const dom = await page.evaluate(() => {
  const q = (s: string) => document.querySelector(s);
  const t = (s: string) => (q(s)?.textContent ?? '').replace(/\s+/g, ' ').trim();
  return {
    chip: t('[data-testid="fts-funnel-gate"]'),
    chipState: q('[data-testid="fts-funnel-gate"]')?.getAttribute('data-state') ?? null,
    rows: document.querySelectorAll('[data-testid="fts-screen-row"]').length,
    badges: document.querySelectorAll('[data-testid="row-funnel-candidate"]').length,
    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  };
});
await page.screenshot({ path: '_audit/tmp/screener_gate-1366.png' });
await browser.close();

const checks: Array<[string, boolean]> = [
  ['چیپِ قیف رویِ صفحۀِ غربالگری هست و state=applied',
    dom.chip.length > 0 && dom.chipState === 'applied'],
  ['چیپ همان شمارۀِ گامِ اوّلِ API را می‌گوید',
    apiTapeInput != null && toEn(dom.chip).includes(String(apiTapeInput))],
  ['تعدادِ بجِ «کاندیدِ قیف» = تعدادِ کاندیدِ API', dom.badges === apiCand],
  ['ردیف‌هایِ جدول رندر شده‌اند', dom.rows > 0],
  ['بی‌سرریزِ افقی درِ ۱۳۶۶×۷۶۸', dom.overflowX <= 0],
];
console.log(JSON.stringify({ chip: dom.chip, api_tape_input: apiTapeInput,
                             api_candidates: apiCand, dom }, null, 1));
for (const [n, ok] of checks) console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${n}`);
process.exit(checks.every((c) => c[1]) ? 0 : 1);
