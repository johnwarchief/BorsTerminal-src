// _audit/probe_veto_render.mts -- بجِ «وتوی مجمع» در مرورگرِ واقعی (#53)
// روی ۸۰۰۳ (تقویمِ کپی با یک رویدادِ شرکتیِ ساختگی) — چون تقویمِ امروز هیچ
// شرکتِ دارایِ مجمعِ ۱۴ روزۀ پیشِ رو ندارد. رندرِ بج سنجیده می‌شود، نه داده.
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const BASE = process.env.PROBE_BASE ?? 'http://127.0.0.1:8003';
const SYM = process.argv[2] ?? 'رمپنا';
const b = await chromium.launch({ executablePath: process.env.JEV_CHROME, args: ['--no-sandbox'] });
const p = await b.newPage({ viewport: { width: 1366, height: 1100 } });
await p.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));

await p.goto(`${BASE}/#/fundamental`, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(40000);
const rowsBefore = await p.evaluate(() => document.querySelectorAll('[data-testid="fts-screen-row"]').length);
await p.fill('[data-testid="fts-search"]', SYM);
await p.waitForTimeout(4000);

const table = await p.evaluate(([sym, before]: [string, number]) => {
  const sel = `[data-testid="row-assembly-veto-badge"]`;
  const el = document.querySelector(sel) as HTMLElement | null;
  const row = el?.closest('tr');
  const cs = el ? getComputedStyle(el) : null;
  const cells = row ? [...row.querySelectorAll('td')].map((td) => td.textContent?.trim().slice(0, 26)) : [];
  const basketBtn = row ? [...row.querySelectorAll('button')].map((x) => x.textContent?.trim()).filter(Boolean) : [];
  const cap = document.querySelector(`[data-testid="row-capital-increase-badge"]`) as HTMLElement | null;
  return {
    rows_before_search: before,
    capital_found: !!cap,
    capital_text: cap?.textContent ?? null,
    capital_title: cap?.getAttribute('title') ?? null,
    capital_color: cap ? getComputedStyle(cap).color : null,
    rows_after_search: document.querySelectorAll('[data-testid="fts-screen-row"]').length,
    badge_found: !!el,
    badge_text: el?.textContent ?? null,
    badge_title: el?.getAttribute('title') ?? null,
    badge_color: cs?.color ?? null,
    badge_bg: cs?.backgroundColor ?? null,
    row_greyed: row ? /opacity-|text-text-muted/.test(row.className) : null,
    row_cells: cells,
    row_buttons: basketBtn,
    row_dir: row ? getComputedStyle(row).direction : null,
  };
}, [SYM, rowsBefore]);
await p.screenshot({ path: '_audit/veto_badge_render_proof.png' });

await p.goto(`${BASE}/#/master`, { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(40000);
const funnel = await p.evaluate((sym: string) => {
  const chip = document.querySelector(`[data-testid="funnel-assembly-veto-${CSS.escape(sym)}"]`) as HTMLElement | null;
  const stage = chip?.closest('[data-testid^="funnel-stage-"]')?.getAttribute('data-testid') ?? null;
  const handover = document.querySelector('[data-testid="funnel-stage-handover"]');
  const handKeys = handover ? [...handover.querySelectorAll('tbody tr[data-fkey]')].map((tr) => tr.getAttribute('data-fkey')) : [];
  return {
    chip_found: !!chip,
    chip_stage: stage,
    chip_text: chip?.textContent ?? null,
    chip_title: chip?.getAttribute('title') ?? null,
    chip_color: chip ? getComputedStyle(chip).color : null,
    symbol_in_handover: handKeys.includes(sym),
    handover_rows: handKeys,
  };
}, SYM);

console.log(JSON.stringify({ base: BASE, symbol: SYM, table, funnel }, null, 1));
await b.close();
