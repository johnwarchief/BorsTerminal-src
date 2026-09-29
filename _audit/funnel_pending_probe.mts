// _audit/funnel_pending_probe.mts -- سنجشِ تکمیلیِ همان درِ نشست: تمامِ ردیف‌هایِ تکنیکال
// + صفِ «سنجیده نشدِ» بنیادی + پوششِ اسکرینر. خروجیِ JSON را tools/funnel_columns_probe.mts
// نمی‌دهد (فقط سطرِ اول را می‌خواند)؛ این پروب برایِ بندِ ۲ و ۶ِ خواسته نوشته شد.
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);

const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:8001/');
const OUT = arg('out', '_audit/funnel_pending_probe.json');

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1632, height: 950 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const errors: string[] = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
page.on('pageerror', (e) => errors.push('pageerror: ' + String(e).slice(0, 200)));

await page.goto(BASE + '#/master', { waitUntil: 'networkidle' });
await page.waitForSelector('[data-testid="funnel-stage-technical"]', { timeout: 45_000 });

// پوششِ رأیِ تکنیکال تا «در حالِ خواندن» از نوارِ بالا بی‌افتد (حداکثر ۹۰s)
for (let i = 0; i < 45; i++) {
  const loading = await page.evaluate(() => {
    const c = document.querySelector('[data-testid="funnel-tech-coverage"]');
    return c ? /در حال/.test(c.textContent ?? '') : false;
  });
  if (!loading) break;
  await page.waitForTimeout(2000);
}

const dump = () =>
  page.evaluate(() => {
    const rowsOf = (sel: string) =>
      Array.from(document.querySelectorAll(`${sel} tbody tr[data-fkey]`)).map((tr) => ({
        symbol: tr.getAttribute('data-fkey'),
        cells: Array.from(tr.children).map((c) => c.textContent?.trim() ?? null),
        title: tr.getAttribute('title'),
      }));
    const stage = (k: string) => {
      const el = document.querySelector(`[data-testid="funnel-stage-${k}"]`);
      const main = el?.querySelector(':scope > div > table');
      const pend = el?.querySelector('[data-testid^="funnel-pending-"]');
      const pendTable = pend?.querySelector('table');
      const cellsOf = (tbl: Element | null | undefined) =>
        Array.from(tbl?.querySelectorAll('tbody tr[data-fkey]') ?? []).map((tr) => ({
          symbol: tr.getAttribute('data-fkey'),
          cells: Array.from(tr.children).map((c) => c.textContent?.trim() ?? null),
        }));
      const headsOf = (tbl: Element | null | undefined) =>
        Array.from(tbl?.querySelectorAll('thead th') ?? []).map((t) => t.textContent?.trim());
      return {
        k,
        heads: headsOf(main),
        rows: cellsOf(main),
        pendingHeads: headsOf(pendTable),
        pending: cellsOf(pendTable),
        pendingLabel: pend?.querySelector('p')?.textContent?.trim() ?? null,
        chips: Array.from(el?.querySelectorAll('header .num') ?? []).map((c) => c.textContent?.trim()),
      };
    };
    return {
      stages: ['tape', 'technical', 'fundamental', 'handover'].map((k) => stage(k)),
      coverage: document.querySelector('[data-testid="funnel-tech-coverage"]')?.textContent?.trim() ?? null,
      scope: document.querySelector('[data-testid="funnel-prefs"]')?.textContent?.trim() ?? null,
    };
  });

// (۱) حالتِ جزوه
const screens = await dump();
// (۲) «خودم چک می‌کنم» + کفِ ۱ تا ردیفِ بنیادی و صفِ انتظار کامل دیده شود
await page.click('[data-testid="funnel-tech-selfcheck"]');
await page.waitForTimeout(1500);
await page.click('[data-testid="funnel-floor-1"]');
await page.waitForTimeout(1500);
const self = await dump();
// (۳) تکلیفِ سنجیده‌نشده = «عبور» تا معلوم شود بی‌داده با رد قاطی می‌شود یا نه
await page.click('[data-testid="funnel-unmeasured-pass"]');
await page.waitForTimeout(1500);
const passMode = await dump();
await page.click('[data-testid="funnel-prefs-reset"]').catch(() => {});

// (۴) پوششِ اسکرینر از خودِ بکاند، برایِ نمادهایِ صفِ انتظار
const api = await page.evaluate(async () => {
  const r = await fetch('/api/screener');
  const j: any = await r.json();
  const rows: any[] = j.data ?? j.rows ?? [];
  const bySym = new Map(rows.map((x: any) => [String(x.symbol ?? x.tsymbol ?? ''), x]));
  return {
    count: rows.length,
    keys: Object.keys(j).slice(0, 12),
    sampleFields: rows[0] ? Object.keys(rows[0]).slice(0, 30) : [],
    sample: rows[0] ?? null,
  };
});

writeFileSync(OUT, JSON.stringify({ screens, self, passMode, api, consoleErrors: errors }, null, 1), 'utf-8');
console.log('coverage chip:', screens.coverage);
console.log('prefs bar:', screens.scope);
console.log('screener rows from API:', api.count, 'keys:', JSON.stringify(api.keys));
console.log('technical rows(screens)=' + screens.stages[1].rows.length,
  'pending=' + screens.stages[1].pending.length);
console.log('fundamental rows(screens)=' + screens.stages[2].rows.length,
  'pending=' + screens.stages[2].pending.length,
  'label=' + screens.stages[2].pendingLabel);
console.log('fundamental heads(main)=' + JSON.stringify(screens.stages[2].heads));
console.log('fundamental heads(pending)=' + JSON.stringify(screens.stages[2].pendingHeads));
console.log('weekly cells (screens):', JSON.stringify(screens.stages[1].rows.map((r: any) => r.cells[1])));
console.log('weekly cells (selfcheck):', JSON.stringify(self.stages[1].rows.map((r: any) => r.cells[1])));
console.log('self fundamental:', self.stages[2].rows.length, 'pending:', self.stages[2].pending.length,
  self.stages[2].pendingLabel);
console.log('passMode fundamental:', passMode.stages[2].rows.length, 'pending:', passMode.stages[2].pending.length,
  'handover:', passMode.stages[3].rows.length);
console.log('passMode fundamental rows:', JSON.stringify(passMode.stages[2].rows.map((r: any) => r.cells)));
console.log('console errors:', errors.length, JSON.stringify(errors.slice(0, 3)));
await browser.close();
