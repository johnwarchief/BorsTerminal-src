// _audit/funnel_i3_witness.mts -- شاهدِ UI رویِ اپِ نصبی: ردیف‌هایِ بنیادی که حاشیه ندارند و ✗ می‌خورند
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR!;
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const BASE = process.argv[2] ?? 'http://127.0.0.1:8001/';

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1632, height: 950 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const errs: string[] = [];
page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 140)); });
await page.goto(BASE + '#/master', { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="funnel-stage-technical"]', { timeout: 60_000 });
await page.waitForTimeout(9000);
const api = await page.evaluate(async (b: string) => {
  const j = await (await fetch(b + 'api/screener')).json();
  const m: Record<string, any> = {};
  for (const r of j.data) m[r.symbol] = { gm: r.gross_margin, i3: r.i3_pass, app: r.applicable };
  return m;
}, BASE);
await page.click('[data-testid="funnel-tech-selfcheck"]').catch(() => {});
await page.waitForTimeout(800);
await page.click('[data-testid="funnel-floor-1"]').catch(() => {});
await page.waitForTimeout(1600);
const rows = await page.evaluate(() => {
  const sec = document.querySelector('[data-testid="funnel-stage-fundamental"]')!;
  const t = [...sec.querySelectorAll('table')];
  const grab = (tb: Element) => [...tb.querySelectorAll('tbody tr[data-fkey]')].map((tr) => ({
    sym: tr.getAttribute('data-fkey'),
    margin: tr.children[3]?.textContent?.trim(),
    why: (tr.getAttribute('title') ?? '').slice(0, 100),
  }));
  return { main: grab(t[0]), pend: t[1] ? grab(t[1]) : [] };
});
const witness = [...rows.main, ...rows.pend].map((r) => ({
  ...r, api: api[r.sym ?? ''] ?? null,
  badUiVsData: !!(api[r.sym ?? ''] && api[r.sym ?? ''].gm == null && /✗/.test(r.margin ?? '')),
}));
writeFileSync('_audit/funnel_i3_witness.json', JSON.stringify({ base: BASE, apiOf: Object.keys(api).length, rows: witness, errors: errs }, null, 1), 'utf-8');
console.log('rows:', witness.length, '| ✗ با حاشیۀ تهی (bug witness):', witness.filter((w) => w.badUiVsData).length);
for (const w of witness) console.log('  ', w.sym, '| ستون حاشیه:', JSON.stringify(w.margin), '| api gm=', w.api?.gm, 'i3=', w.api?.i3, 'applicable=', w.api?.app, '|', w.why);
console.log('console errors:', errs.length);
await page.click('[data-testid="funnel-prefs-reset"]').catch(() => {});
await browser.close();
