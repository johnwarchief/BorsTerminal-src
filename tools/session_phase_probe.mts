/** tools/session_phase_probe.mts — اثباتِ زندهٔ بلوکِ «مرحلِ جلسه» (بند ۵)
 *
 * دو چیز مقابله می‌شود:
 *   ۱) آنچه صفحه می‌نویسد = آنچه /api/mstat/phase می‌گوید (یک منبع، نه دو)،
 *   ۲) کنترلِ رسیدن: بلوک واقعاً رویِ صفحۀ «وضعیت بازار» دیدنی است (نه اینکه
 *      با undefined بی‌صدا غایب بماند و آزمونِ «حکم نیست» سبز بخواند).
 *
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types \
 *     tools/session_phase_probe.mts --url http://127.0.0.1:8002/
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
const OUT = arg('out', '_audit/tmp/session_phase');

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
const page = await ctx.newPage();
await page.addInitScript(() => { sessionStorage.setItem('bors_auth_session', 'true'); });

const api = await (await fetch(`${BASE}/api/mstat/phase`)).json();
const summary = await (await fetch(`${BASE}/api/mstat/summary`)).json();

await page.goto(`${BASE}/#/market-status`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(16000);
const dom = await page.evaluate(() => {
  const q = (s: string) => document.querySelector(s);
  const t = (s: string) => (q(s)?.textContent ?? '').replace(/\s+/g, ' ').trim();
  return {
    panel: !!q('[data-testid="status-session-phase"]'),
    phase: q('[data-testid="status-session-phase-label"]')?.getAttribute('data-phase') ?? null,
    labelText: t('[data-testid="status-session-phase-label"]'),
    source: t('[data-testid="status-session-phase-source"]'),
    verdict: t('[data-testid="status-session-phase-verdict"]'),
    missing: t('[data-testid="status-session-phase-missing"]'),
    day: t('[data-testid="status-session-phase-day"]'),
    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  };
});
await page.screenshot({ path: `${OUT}-1366.png` });
await browser.close();

const checks: Array<[string, boolean, unknown]> = [
  ['بلوکِ مرحل رویِ صفحۀ وضعیت بازار دیدنی است (کنترلِ رسیدن)', dom.panel && !!dom.phase, dom.panel],
  ['مرحلِ صفحه = مرحلِ API', dom.phase === api.phase, { dom: dom.phase, api: api.phase }],
  ['برچسبِ فارسیِ همان مرحل رویِ صفحه است', dom.labelText.includes(api.label), dom.labelText],
  ['منبعِ مرحل صریح نوشته می‌شود (رسمی یا تقویم)',
    dom.source.includes('وضعیتِ رسمی') || dom.source.includes('از تقویم'), dom.source],
  ['خطِ حکم با verdict_allowedِ خودِ بک‌اند می‌خواند',
    api.verdict_allowed ? dom.verdict.includes('قابلِ داوری')
                        : dom.verdict.includes('صادر نمی‌شود'),
    { allowed: api.verdict_allowed, verdict: dom.verdict }],
  ['ستونِ مرحل درِ پاسخِ خلاصه هم هست (یک منبع برای هر دو بلوک)',
    summary?.phase?.phase === api.phase, { summary: summary?.phase?.phase, api: api.phase }],
  ['بی‌سرریزِ افقی درِ ۱۳۶×۷۶۸', dom.overflowX <= 0, dom.overflowX],
];
writeFileSync(`${OUT}.json`, JSON.stringify({ api, summary_phase: summary?.phase,
                                              health: summary?.health, dom,
                                              checks: checks.map(([n, ok, d]) => ({ n, ok, d })) },
                                             null, 2));
for (const [n, ok, d] of checks) console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${n}${ok ? '' : '  ' + JSON.stringify(d)}`);
process.exit(checks.every((c) => c[1]) ? 0 : 1);
