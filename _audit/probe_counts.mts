import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (r: string) => import(pathToFileURL(`${PKG}/${r}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');
const b = await chromium.launch({ executablePath: process.env.JEV_CHROME || undefined, args: ['--no-sandbox'] });
const p = await b.newPage({ viewport: { width: 1366, height: 1000 } });
await p.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
await p.goto('http://127.0.0.1:8002/#/master', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(16000);
console.log(JSON.stringify(await p.evaluate(() => {
  const out: Record<string, unknown> = {};
  for (const k of ['tape', 'technical', 'fundamental', 'handover']) {
    const s = document.querySelector(`[data-testid="funnel-stage-${k}"]`);
    if (!s) continue;
    out[k] = Array.from(s.querySelectorAll('table')).map((tb) => ({
      th: tb.querySelectorAll('thead th').length,
      tdRow0: (tb.querySelector('tbody tr')?.querySelectorAll('td') ?? []).length,
      tdRow1: (tb.querySelectorAll('tbody tr')[1]?.querySelectorAll('td') ?? []).length,
      tableLayout: getComputedStyle(tb).tableLayout,
      thW: Array.from(tb.querySelectorAll('thead th')).map((e) => Math.round(e.getBoundingClientRect().width)),
      tdW: Array.from((tb.querySelector('tbody tr')?.querySelectorAll('td') ?? []) as Element[]).map((e) => Math.round(e.getBoundingClientRect().width)),
    }));
  }
  return out;
}), null, 1));
await b.close();
