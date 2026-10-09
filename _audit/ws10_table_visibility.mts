// _audit/ws10_table_visibility.mts — روبشِ «جدول بیشتر دیده شود، چیزی تکراری نباشد»
//
// رأیِ مالک: «تمام صفحات از جمله غربالگری FTS بررسی بشن جدول‌ها بیشترین دید رو
// داشته باشن و چیزهای تکراری هم نباشه». این سنجش حرف نمی‌زند، عدد می‌دهد:
//   • عرضِ هر جدول نسبت به viewport (جدول باید مسلط باشد)
//   • سرریزِ افقیِ ظرفِ اسکرول (ستونی که پشتِ لبه رفته)
//   • سلول‌هایِ بریده (scrollWidth > clientWidth) — با نمونۀ متن
//   • ستونِ تکراری: دو ستون که متنِ همهٔ ردیف‌هایشان یکی است، یا دو سرستونِ هم‌نام
// خروجی: `_audit/ws10_table_visibility.json` — هر موردِ باز باید درِ گزارشِ نهایی
// با عددِ خودش بیاید، نه با «به‌نظر درست است».
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const BASE = process.argv.includes('--url') ? process.argv[process.argv.indexOf('--url') + 1]
                                            : 'http://127.0.0.1:5175/';
mkdirSync('_audit', { recursive: true });
const OUT = '_audit/ws10_table_visibility.json';
const ROUTES = ['/market', '/fundamental', '/master?stage=tape&preset=custom',
                '/master?stage=technical&preset=custom', '/master?stage=fundamental&preset=custom',
                '/master?stage=handover&preset=custom', '/portfolio', '/strategy-tree', '/technical'];

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));

const SCAN = () => {
  const tables = [...document.querySelectorAll('table')]
    .filter((t) => t.getBoundingClientRect().width > 60);
  return tables.map((t) => {
    const r = t.getBoundingClientRect();
    const host = t.closest('[class*="overflow-x-auto"], [class*="overflow-auto"]') ?? t.parentElement;
    const heads = [...t.querySelectorAll('thead th')].map((h) => (h.textContent ?? '').trim());
    const rowsN = t.querySelectorAll('tbody tr').length;
    const colText = (i: number) => [...t.querySelectorAll('tbody tr')]
      .map((tr) => (tr.children[i]?.textContent ?? '').trim()).join('|');
    const clipped: { text: string; need: number; got: number }[] = [];
    t.querySelectorAll('tbody td, thead th').forEach((c) => {
      if (c.scrollWidth > c.clientWidth + 2 && clipped.length < 4) {
        clipped.push({ text: (c.textContent ?? '').trim().slice(0, 34),
                       need: c.scrollWidth, got: c.clientWidth });
      }
    });
    const dupHeads: string[] = [];
    heads.forEach((h, i) => { if (h && heads.indexOf(h) < i) dupHeads.push(h); });
    const dupCols: [number, number][] = [];
    for (let i = 0; i < heads.length; i++) {
      for (let j = i + 1; j < heads.length; j++) {
        const a = colText(i), b = colText(j);
        if (a.length > 3 && a === b) dupCols.push([i, j]);
      }
    }
    return {
      testid: t.getAttribute('data-testid') ?? t.closest('[data-testid]')?.getAttribute('data-testid') ?? null,
      widthPx: Math.round(r.width),
      viewportShare: Number((r.width / innerWidth).toFixed(2)),
      rowsN, colN: heads.length, heads: heads.slice(0, 14),
      hostOverflowX: host ? Math.max(0, host.scrollWidth - host.clientWidth) : 0,
      clipped, dupHeads, dupCols,
    };
  });
};

const pages: Record<string, unknown> = {};
for (const route of ROUTES) {
  const page = await ctx.newPage();
  const errs: string[] = [];
  page.on('pageerror', (e) => errs.push(String(e.message).slice(0, 120)));
  await page.goto(BASE + '#' + route, { waitUntil: 'domcontentloaded' });
  // هر صفحه‌ای باید ردیف بنشاند؛ بی‌این، روبشِ خالی «پاک» گزارش می‌شود.
  let painted = true;
  try {
    await page.waitForFunction(() => document.querySelectorAll('table tbody tr').length > 2,
      null, { timeout: 90_000 });
  } catch { painted = false; }
  await page.waitForTimeout(1800);
  const tables = painted ? await page.evaluate(SCAN) : [];
  pages[route] = { painted, tables, pageErrors: errs };
  await page.close();
}

writeFileSync(OUT, JSON.stringify(pages, null, 2));
const rows: string[] = [];
for (const [route, v] of Object.entries<any>(pages)) {
  for (const t of v.tables) {
    rows.push([route, t.testid ?? '-', `${t.rowsN}×${t.colN}`, `${t.widthPx}px (${Math.round(t.viewportShare * 100)}%)`,
               t.hostOverflowX ? `OVERFLOW +${t.hostOverflowX}px` : 'no overflow',
               t.clipped.length ? `CLIPPED ${t.clipped.length}: ${JSON.stringify(t.clipped[0], null, 0)}` : 'no clip',
               t.dupHeads.length ? `DUP HEADS ${JSON.stringify(t.dupHeads)}` : '-',
               t.dupCols.length ? `DUP COLS ${JSON.stringify(t.dupCols)}` : '-'].join('  |  '));
  }
  if (!v.tables.length) rows.push(`${route}  |  ${v.painted ? 'no table found' : 'NOT PAINTED (timeout)'}`);
  if (v.pageErrors.length) rows.push(`${route}  |  errors ${JSON.stringify(v.pageErrors.slice(0, 2))}`);
}
console.log('route | table | size | width | overflow | clipped | dupHeads | dupCols');
for (const r of rows) console.log(r);
await browser.close();
