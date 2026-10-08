// _audit/ws7_universe_check.mts — سنجشِ زندهٔ «جامعۀ تابلو ≠ جامعۀ غربالگری»
//
// چهار پرسشِ مشخص، همه از خودِ DOM (نه از کد):
//   ۱) خطِ خلاصه هر سه عدد X/Y/Z را نشان می‌دهد و X = Y + Z؟
//   ۲) chipِ «حکم» هر گام با Y می‌خواند (نه با X)؟
//   ۳) خارج‌ها درِ جدولِ گام نمی‌نشینند ولی درِ بخشِ بازشونده با علت‌اند؟
//   ۴) هیچ خطایِ کنسول و هیچ پاسخِ ۴xx/۵xx‌ای نیست؟
// خروجی: _audit/ws7_universe_check.json + اسکرین‌شات. قضاوتِ ظاهری با مالک است.
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
const OUT = '_audit/ws7_universe_check.json';

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const consoleErrors: string[] = [];
page.on('console', (m: any) => {
  if (m.type() === 'error' || m.type() === 'warning') consoleErrors.push(`${m.type()}: ${m.text().slice(0, 160)}`);
});
page.on('pageerror', (e: any) => consoleErrors.push(`pageerror: ${String(e.message).slice(0, 160)}`));
const badResponses: string[] = [];
page.on('response', (r: any) => {
  if (r.status() >= 400) badResponses.push(`${r.status()} ${String(r.url()).replace(/^https?:\/\/[^/]+/, '')}`);
});

const num = (s: string | null) => {
  if (!s) return null;
  const latin = s.replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
                 .replace(/[٠-٩]/g, (d) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)));
  const m = latin.match(/\d[\d,]*/);
  return m ? Number(m[0].replace(/,/g, '')) : null;
};

await page.goto(`${BASE}#/master`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="funnel-stage-tape"]', { timeout: 180_000 });
await page.waitForSelector('[data-testid="funnel-universe-market"]', { timeout: 120_000 });

const read = async () => page.evaluate(() => {
  const t = (sel: string) => document.querySelector(`[data-testid="${sel}"]`)?.textContent ?? null;
  const ruled = Array.from(document.querySelectorAll('[data-testid^="funnel-ruled-"]'))
    .map((el) => ({ key: el.getAttribute('data-testid')!.replace('funnel-ruled-', ''),
                    text: (el.textContent ?? '').replace(/\s+/g, ' ').trim() }));
  const tableSyms = Array.from(document.querySelectorAll('[data-testid^="funnel-why-"]'))
    .map((el) => el.getAttribute('data-testid')!.replace('funnel-why-', ''));
  return {
    market: t('funnel-universe-market'), screening: t('funnel-universe-screening'),
    excluded: t('funnel-universe-excluded'), ruled, tableSyms: Array.from(new Set(tableSyms)),
    panelOpen: !!document.querySelector('[data-testid="funnel-exclusions"]'),
    countsLine: (document.querySelector('[data-testid="funnel-counts"]')?.textContent ?? '')
      .replace(/\s+/g, ' ').trim(),
  };
});

const before = await read();
const X = num(before.market), Y = num(before.screening), Z = num(before.excluded);
await page.screenshot({ path: '_audit/ws7_universe_closed.png' });

let after: any = null;
let excludedSample: string | null = null;
let exclusionChips: { code: string; text: string }[] = [];
if (Z && Z > 0) {
  await page.click('[data-testid="funnel-universe-excluded"]');
  await page.waitForSelector('[data-testid="funnel-exclusions"]', { timeout: 15_000 });
  after = await page.evaluate(() => ({
    chips: Array.from(document.querySelectorAll('[data-testid^="funnel-exclusion-"]'))
      .filter((el) => !el.getAttribute('data-testid')!.startsWith('funnel-exclusion-row-'))
      .map((el) => ({ code: el.getAttribute('data-testid')!.replace('funnel-exclusion-', ''),
                      text: (el.textContent ?? '').replace(/\s+/g, ' ').trim() })),
    rows: Array.from(document.querySelectorAll('[data-testid^="funnel-exclusion-row-"]'))
      .map((el) => ({ symbol: el.getAttribute('data-testid')!.replace('funnel-exclusion-row-', ''),
                      text: (el.textContent ?? '').replace(/\s+/g, ' ').trim() })),
  }));
  exclusionChips = after.chips;
  excludedSample = after.rows.length ? after.rows[0].symbol : null;
  await page.screenshot({ path: '_audit/ws7_universe_open.png' });
}

const ruledAgainst = before.ruled.map((r) => ({
  key: r.key,
  equalsY: num(r.text) === Y,
  saysScreeningUniverse: r.text.includes('کلِ جامعۀ غربالگری'),
}));
const sampleLeakedIntoTable = excludedSample
  ? before.tableSyms.includes(excludedSample) : false;

const result = {
  base: BASE, at: new Date().toISOString(),
  universe: { X, Y, Z, sumOK: X !== null && Y !== null && Z !== null && X === Y + Z },
  countsLine: before.countsLine,
  ruled: before.ruled, ruledAgainst,
  allRuledMatchY: ruledAgainst.every((r) => r.equalsY && r.saysScreeningUniverse),
  excludedSample, sampleLeakedIntoTable,
  exclusionChips, panelRows: after ? after.rows.length : 0,
  panelHiddenBeforeOpen: before.panelOpen === false,
  consoleErrors: consoleErrors.slice(0, 12), consoleErrorCount: consoleErrors.length,
  badResponses: badResponses.slice(0, 12), badResponseCount: badResponses.length,
  verdicts: {
    summary_shows_three_numbers: X !== null && Y !== null && Z !== null,
    X_equals_Y_plus_Z: X === Y + Z,
    every_stage_ruled_equals_Y: ruledAgainst.every((r) => r.equalsY),
    excluded_not_in_stage_tables: !sampleLeakedIntoTable,
    exclusions_panel_opens_with_reasons: exclusionChips.length > 0,
    zero_console_errors: consoleErrors.length === 0,
    zero_bad_responses: badResponses.length === 0,
  },
};
mkdirSync('_audit', { recursive: true });
writeFileSync(OUT, JSON.stringify(result, null, 2));
console.log(JSON.stringify(result.verdicts, null, 2));
console.log(`X=${X} Y=${Y} Z=${Z} excludedSample=${excludedSample} leaked=${sampleLeakedIntoTable}`);
console.log(`consoleErrors=${consoleErrors.length} badResponses=${badResponses.length}`);
await browser.close();
