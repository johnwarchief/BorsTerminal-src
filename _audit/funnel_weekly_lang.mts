// _audit/funnel_weekly_lang.mts -- زبانِ ستونِ هفتگی/روزانه در همهٔ ردیف‌هایِ زنده + علتِ صفِ انتظار
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR!;
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);

const b = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await b.newContext({ viewport: { width: 1632, height: 950 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const p = await ctx.newPage();
const errs: string[] = [];
p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 160)); });
p.on('pageerror', (e) => errs.push('pageerror: ' + String(e).slice(0, 160)));
await p.goto('http://127.0.0.1:8001/#/master', { waitUntil: 'domcontentloaded' });
await p.waitForSelector('[data-testid="funnel-stage-technical"]', { timeout: 45_000 });
await p.waitForTimeout(10_000);
await p.click('[data-testid="funnel-tech-selfcheck"]');
await p.waitForTimeout(1500);

const r = await p.evaluate(() => {
  const FA = /[؀-ۿ]/;
  const tech = [...document.querySelectorAll('[data-testid="funnel-stage-technical"] tbody tr[data-fkey]')]
    .map((tr) => ({
      sym: tr.getAttribute('data-fkey'),
      w: tr.children[1]?.textContent?.trim(),
      d: tr.children[2]?.textContent?.trim(),
      mark: tr.children[4]?.textContent?.trim(),
      why: (tr.getAttribute('title') ?? '').slice(0, 90),
    }));
  const pend = [...document.querySelectorAll('[data-testid="funnel-pending-fundamental"] tbody tr[data-fkey]')]
    .map((tr) => ({
      sym: tr.getAttribute('data-fkey'),
      cells: [...tr.children].map((c) => c.textContent?.trim()),
      why: (tr.getAttribute('title') ?? '').slice(0, 120),
    }));
  const fund = [...document.querySelectorAll('[data-testid="funnel-stage-fundamental"] table')[0]
    ?.querySelectorAll('tbody tr[data-fkey]') ?? []]
    .map((tr) => ({
      sym: tr.getAttribute('data-fkey'),
      cells: [...tr.children].map((c) => c.textContent?.trim()),
      why: (tr.getAttribute('title') ?? '').slice(0, 120),
    }));
  return {
    tech,
    nonFaWeekly: tech.filter((t) => t.w && (!FA.test(t.w) || /^(up|down|range|na)$/i.test(t.w))),
    blankWeekly: tech.filter((t) => !t.w),
    pend, fund,
    coverage: document.querySelector('[data-testid="funnel-tech-coverage"]')?.textContent?.trim() ?? null,
  };
});
writeFileSync('_audit/funnel_weekly_lang.json', JSON.stringify({ ...r, consoleErrors: errs }, null, 1), 'utf-8');
console.log('tech rows:', r.tech.length, '| non-Persian weekly:', JSON.stringify(r.nonFaWeekly), '| blank weekly:', r.blankWeekly.length);
console.log('coverage:', r.coverage);
console.log('fundamental accepted:', JSON.stringify(r.fund.map((f) => [f.sym, f.cells.slice(1).join('|'), f.why]), null, 0));
console.log('pending (سنجیده نشد):', JSON.stringify(r.pend.map((f) => [f.sym, f.cells.slice(1).join('|'), f.why]), null, 0));
console.log('console errors:', errs.length, errs.slice(0, 2));
await p.click('[data-testid="funnel-prefs-reset"]').catch(() => {});
await b.close();
