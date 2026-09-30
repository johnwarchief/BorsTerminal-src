// _audit/funnel_pending_detail.mts -- جزئیاتِ مرحلۀ بنیادی: صفِ انتظار، سرستونِ تکراری، چیپ‌ها
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR!;
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);

const b = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await b.newContext({ viewport: { width: 1632, height: 950 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const p = await ctx.newPage();
await p.goto('http://127.0.0.1:8001/#/master', { waitUntil: 'networkidle' });
await p.waitForSelector('[data-testid="funnel-stage-technical"]', { timeout: 45_000 });
await p.waitForTimeout(9000);
await p.click('[data-testid="funnel-tech-selfcheck"]');
await p.waitForTimeout(1500);
await p.click('[data-testid="funnel-floor-1"]');
await p.waitForTimeout(1500);

const r = await p.evaluate(() => {
  const out: any = {};
  const stage = (k: string) => {
    const sec = document.querySelector(`[data-testid="funnel-stage-${k}"]`);
    if (!sec) return null;
    const tables = [...sec.querySelectorAll('table')];
    const pend = sec.querySelector('[data-testid^="funnel-pending-"]');
    return {
      nTables: tables.length,
      theadTexts: tables.map((t) => [...t.querySelectorAll('thead th')].map((x) => x.textContent?.trim()).join('|')),
      mainRows: [...(tables[0]?.querySelectorAll('tbody tr[data-fkey]') ?? [])].map((t) => t.getAttribute('data-fkey')),
      pendLabel: pend?.querySelector('p')?.textContent?.trim() ?? null,
      pendRows: pend ? [...pend.querySelectorAll('tbody tr[data-fkey]')].map((t) => t.getAttribute('data-fkey')) : null,
      pendFirstCells: pend ? [...(pend.querySelectorAll('tbody tr[data-fkey]')[0]?.children ?? [])].map((c) => c.textContent?.trim()) : null,
      chips: [...sec.querySelectorAll('header .num')].map((e) => e.textContent?.trim()),
      emptyMsg: sec.querySelector('[data-testid^="funnel-empty-"]')?.textContent?.trim() ?? null,
    };
  };
  for (const k of ['tape', 'technical', 'fundamental', 'handover']) out[k] = stage(k);
  out.coverage = document.querySelector('[data-testid="funnel-tech-coverage"]')?.textContent?.trim() ?? null;
  out.prefs = document.querySelector('[data-testid="funnel-prefs"]')?.textContent?.trim() ?? null;
  return out;
});
console.log(JSON.stringify(r, null, 1));
await p.click('[data-testid="funnel-prefs-reset"]').catch(() => {});
await p.waitForTimeout(500);
console.log('prefs after reset:', await p.evaluate(() => localStorage.getItem('fts.funnel.prefs.v1')));
await b.close();
