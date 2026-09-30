import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const b = await chromium.launch({ executablePath: process.env.JEV_CHROME, args: ['--no-sandbox'] });
const p = await b.newPage({ viewport: { width: 1366, height: 1000 } });
await p.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
await p.goto('http://127.0.0.1:8002/#/fundamental', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(45000);
const before = await p.evaluate(() => document.querySelectorAll('[data-testid="fts-screen-row"]').length);
await p.fill('[data-testid="fts-search"]', 'ستاره');
await p.waitForTimeout(3000);
const seen = await p.evaluate(() => {
  const el = document.querySelector('[data-testid="row-assembly-veto-badge"]');
  const near = document.querySelector('[data-testid^="row-assembly-near-badge"]');
  const tr = document.querySelector('[data-testid="fts-screen-row"]');
  return {
    veto_found: !!el,
    veto_text: el?.textContent ?? null,
    veto_color: el ? getComputedStyle(el).color : null,
    veto_title: el?.getAttribute('title') ?? null,
    near_alongside: !!near,
    row_greyed: tr ? /opacity-/.test(tr.className) : null,
    rows_before_search: (window as any).__before ?? null,
  };
});
await p.screenshot({ path: '_audit/veto_badge_fundamental.png' });
// قیف: نمادِ وتوشده نباید در مرحلۀ تحویل باشد
await p.goto('http://127.0.0.1:8002/#/master', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(18000);
const funnel = await p.evaluate(() => {
  const chip = document.querySelector('[data-testid^="funnel-assembly-veto-"]');
  const hand = document.querySelector('[data-testid="funnel-stage-handover"]');
  const fund = document.querySelector('[data-testid="funnel-stage-fundamental"]');
  return {
    chip_in_funnel: !!chip,
    chip_text: chip?.textContent ?? null,
    chip_section: chip?.closest('section')?.getAttribute('data-testid') ?? null,
    handover_has_chip: !!hand?.querySelector('[data-testid^="funnel-assembly-veto-"]'),
    fund_rows: fund?.querySelectorAll('tbody tr').length ?? -1,
    handover_rows: hand?.querySelectorAll('tbody tr').length ?? -1,
    empty_why: document.querySelector('[data-testid="funnel-empty-handover"]')?.textContent ?? null,
  };
});
await p.evaluate((n: number) => { (window as any).__before = n; }, before as number);
console.log(JSON.stringify({ fundamental: seen, funnel }, null, 1));
await b.close();
