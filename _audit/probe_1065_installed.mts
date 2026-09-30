import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const b = await chromium.launch({ executablePath: process.env.JEV_CHROME, args: ['--no-sandbox'] });
const p = await b.newPage({ viewport: { width: 1366, height: 900 } });
const errs: string[] = [];
p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 120)); });
await p.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
await p.goto('http://127.0.0.1:8001/#/fundamental', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(40000);
const rowsAll = await p.evaluate(() => document.querySelectorAll('[data-testid="fts-screen-row"]').length);
await p.fill('[data-testid="fts-search"]', 'سرآمد');
await p.waitForTimeout(4000);
const seen = await p.evaluate(() => {
  const rows = Array.from(document.querySelectorAll('[data-testid="fts-screen-row"]'));
  const out = rows.map((tr) => {
    const veto = tr.querySelector('[data-testid="row-assembly-veto-badge"]');
    const near = tr.querySelector('[data-testid="row-assembly-near-badge"]');
    const cap = tr.querySelector('[data-testid="row-capital-increase-badge"]');
    const sym = tr.querySelector('td')?.textContent?.trim() ?? '';
    return {
      sym,
      veto: veto?.textContent?.trim() ?? null,
      veto_color: veto ? getComputedStyle(veto).color : null,
      veto_title: veto?.getAttribute('title') ?? null,
      near_alongside_veto: !!(veto && near),
      capital: cap?.textContent?.trim() ?? null,
      row_greyed: /opacity-|cursor-not-allowed/.test(tr.className),
      row_dir: getComputedStyle(tr).direction,
    };
  });
  return { rows_after_search: rows.length, out };
});
await p.screenshot({ path: '_audit/installed_1065_veto_badge.png' });
console.log(JSON.stringify({ rows_all: rowsAll, ...seen, console_errors: errs.length }, null, 1));
await b.close();
