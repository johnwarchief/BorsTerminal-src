// _audit/ws14_table_size.mts — اندازهٔ واقعیِ جدول‌ها بعد از درشت‌کردن
//
// مالک: «جداول رو بزرگتر کن؛ مهم‌ترین چیز دیدنِ درست جدول‌هاست». این عدد
// می‌آورد، نه نظر:
//   • ارتفاعِ واقعیِ ردیف در برابرِ ثابتِ ROW_Hِ مجازی‌سازی (نخواند => اسکرول
//     می‌لنگد و ردیف‌ها روی هم می‌افتند)،
//   • قدِ فونتِ سرستون و بدنه،
//   • چند ردیف *واقعاً* در ویوپورت دیده می‌شود (ارتفاعِ ظرف ÷ ارتفاعِ ردیف)،
//   • و ستون‌هایِ بریده (scrollWidth > clientWidth).
// اجرا: JEV_CHROME=... MSYS_NO_PATHCONV=1 node --experimental-strip-types _audit/ws14_table_size.mts --url http://127.0.0.1:8021/
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const argv = process.argv;
const BASE = argv.includes('--url') ? argv[argv.indexOf('--url') + 1] : 'http://127.0.0.1:8021/';
mkdirSync('_audit', { recursive: true });

const SIZES = [
  { w: 1366, h: 768 },
  { w: 1920, h: 1080 },
];
const PAGES = [
  { hash: '#/master', rows: '[data-testid^="funnel-scroll-"]', label: 'استراتژی FTS' },
  { hash: '#/fundamental', rows: '[data-testid="fts-screen-scroll"]', label: 'بنیادی' },
  { hash: '#/market', rows: '[data-testid="tape-scroll"]', label: 'تابلو' },
];

const browser = await chromium.launch({ headless: true,
  executablePath: process.env.JEV_CHROME || undefined });
const out: any = { base: BASE, runs: [] };

for (const vp of SIZES) {
  const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h } });
  await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
  for (const pg of PAGES) {
    const page = await ctx.newPage();
    const errs: string[] = [];
    page.on('pageerror', (e) => errs.push(String(e.message).slice(0, 120)));
    await page.goto(BASE + pg.hash, { waitUntil: 'networkidle', timeout: 60_000 });
    await page.waitForTimeout(6_000);
    const m = await page.evaluate((sel: string) => {
      const boxes = Array.from(document.querySelectorAll(sel));
      return boxes.map((box) => {
        const table = box.querySelector('table') || box;
        // جدولِ تابلو grid از div است، نه <table>؛ ردیفِ آن با testid خوانده
        // می‌شود وگرنه قدِ ردیف null برمی‌گشت و «بزرگ‌تر شدن» سنجیده نمی‌شد.
        const row = table.querySelector('tbody tr[data-fkey], tbody tr[data-testid], tbody tr')
          || box.querySelector('[data-testid="tape-row"]');
        const cell = row ? (row.querySelector('td, span, div') || row.firstElementChild) : null;
        const head = table.querySelector('thead tr') || box.querySelector('[data-testid="tape-head"]');
        const headCell = head ? (head.querySelector('th, span, div') || head.firstElementChild) : null;
        let clipped = 0, cells = 0;
        table.querySelectorAll('tbody tr').forEach((tr) => {
          tr.querySelectorAll('td').forEach((td) => {
            cells++;
            if (td.scrollWidth > td.clientWidth + 1) clipped++;
          });
        });
        if (!cells) {
          box.querySelectorAll('[data-testid="tape-row"] > *').forEach((d) => {
            cells++;
            if (d.scrollWidth > d.clientWidth + 1) clipped++;
          });
        }
        const cs = (n: Element | null) => n ? getComputedStyle(n) : null;
        return {
          box_h: Math.round(box.getBoundingClientRect().height),
          box_scroll_h: box.scrollHeight,
          row_h: row ? Math.round(row.getBoundingClientRect().height) : null,
          body_font: cs(cell)?.fontSize ?? null,
          head_font: cs(headCell)?.fontSize ?? null,
          table_w: Math.round((table as HTMLElement).getBoundingClientRect().width),
          visible_rows: row ? Math.round(box.getBoundingClientRect().height / row.getBoundingClientRect().height) : 0,
          clipped_cells: clipped, dom_cells: cells,
        };
      });
    }, pg.rows);
    const rec = { viewport: `${vp.w}x${vp.h}`, page: pg.label, hash: pg.hash,
      boxes: m, page_errors: errs };
    out.runs.push(rec);
    console.log(JSON.stringify(rec));
    await page.screenshot({ path: `_audit/ws14_${pg.hash.replace(/[#/]/g, '')}_${vp.w}.png` });
    await page.close();
  }
  await ctx.close();
}
await browser.close();
writeFileSync('_audit/ws14_table_size.json', JSON.stringify(out, null, 2));
console.log('WROTE _audit/ws14_table_size.json');
