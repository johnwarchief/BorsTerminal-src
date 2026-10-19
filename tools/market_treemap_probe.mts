// tools/market_treemap_probe.mts — بازتولیدِ باگِ نقشۀ بازار از رویِ رندرِ واقعی
//
// داده را سنجه نمی‌کند (آن را `tools/market_tab_layout_probe.mts` و یک سنجشِ
// SQLِ جدا می‌سنجند؛ درصدِ هر خانه با (p_closing − price_yesterday)/price_yesterday
// درِ همان لحظه برابر بود). این فایل فقط **هندسه و تعامل** را می‌بیند:
//  ۱) هم‌پوشانیِ دو سلول، بیرون‌زدنِ سلول از قاب، سلولِ صفر/منفی؛
//  ۲) ترتیبِ چیدمان با ترتیبِ size (بزرگ‌ترین باید بزرگ‌ترین مستطیل باشد);
//  ۳) رفتار در سه عرض، با شمارشِ سلول‌هایِ معیوب در هر عرض؛
//  ۴) tooltip و کلیک: کدام نماد باز می‌شود — باید همان نمادی باشد که نشانگر
//     روی آن است، نه همسایه‌اش.
// هیچ عددی ساخته نمی‌شود: اگر سلولی نیست، می‌گوید صفر سلول.
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  || 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package/node_modules/playwright/index.mjs';
const BASE = process.argv[2] || 'http://127.0.0.1:8011/';
const OUT = process.env.JEV_OUT_DIR
  || 'C:/Users/PCMOD/Desktop/_bors-market-tab/_audit/treemap-probe';
mkdirSync(OUT, { recursive: true });

const { chromium } = await import(pathToFileURL(PKG).href);
const browser = await chromium.launch({ headless: true,
  executablePath: process.env.JEV_CHROME || undefined });

const report: Record<string, unknown> = { base: BASE, runs: [] };
const results: Array<[string, boolean, string]> = [];
const ck = (n: string, ok: boolean, extra = '') => results.push([n, ok, extra]);

for (const width of [1440, 1100, 820]) {
  const ctx = await browser.newContext({ viewport: { width, height: 900 } });
  await ctx.addInitScript(() => {
    try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* noop */ }
  });
  const page = await ctx.newPage();
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 120)));
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  await page.getByTestId('nav-market-status').click();
  await page.waitForSelector('[data-testid="ms-treemap"]', { timeout: 25000 });
  await page.locator('[data-testid="ms-treemap"]').scrollIntoViewIfNeeded();
  await page.waitForTimeout(2500);

  const geo = await page.evaluate(() => {
    const host = document.querySelector('[data-testid="ms-treemap"]') as HTMLElement | null;
    const hb = host?.getBoundingClientRect();
    const cells = Array.from(document.querySelectorAll('[data-testid^="treemap-cell-"]'))
      .map((el) => {
        const b = el.getBoundingClientRect();
        return { key: el.getAttribute('data-testid')!.replace('treemap-cell-', ''),
          tone: el.getAttribute('data-tone'),
          x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height),
          area: Math.max(0, b.width) * Math.max(0, b.height) };
      });
    const box = (a: { x: number; y: number; w: number; h: number }) => ({
      l: a.x, t: a.y, r: a.x + a.w, b: a.y + a.h });
    let overlaps = 0; let outside = 0; let degenerate = 0;
    const pairSamples: string[] = [];
    for (let i = 0; i < cells.length; i++) {
      const A = box(cells[i]);
      if (cells[i].w <= 0 || cells[i].h <= 0) degenerate++;
      if (hb && (A.l < Math.floor(hb.x) - 1 || A.t < Math.floor(hb.y) - 1
        || A.r > Math.ceil(hb.right) + 1 || A.b > Math.ceil(hb.bottom) + 1)) outside++;
      for (let j = i + 1; j < cells.length; j++) {
        const B = box(cells[j]);
        const ox = Math.min(A.r, B.r) - Math.max(A.l, B.l);
        const oy = Math.min(A.b, B.b) - Math.max(A.t, B.t);
        if (ox > 2 && oy > 2) {
          overlaps++;
          if (pairSamples.length < 4) pairSamples.push(`${cells[i].key}×${cells[j].key}`);
        }
      }
    }
    // بزرگ‌ترین size باید بزرگ‌ترین مساحت باشد (تقريبی، چون چیدمانِ مربّع‌ساز
    // نسبتِ سطوح را دقیقاً حفظ نمی‌کند — ولی جایِ اولِ هر دو یکی است)
    const byArea = [...cells].sort((a, b) => b.area - a.area);
    return { count: cells.length, overlaps, outside, degenerate, pairSamples,
      top3area: byArea.slice(0, 3).map((c) => c.key),
      hostBox: hb ? { w: Math.round(hb.width), h: Math.round(hb.height) } : null,
      svgBox: (() => {
        const s = document.querySelector('[data-testid="ms-treemap"] svg');
        const r = s?.getBoundingClientRect();
        return r ? { w: Math.round(r.width), h: Math.round(r.height) } : null;
      })() };
  });

  // دامنه‌هایِ خودِ رابط: هر کلیدِ کرکره باید خانه بدهد یا «بی‌داده» باِ علت —
  // هیچ‌کدام نباید خطایِ سرویس باشد. (top50 درِ پایۀِ قبل می‌ترکید.)
  let groups: Array<Record<string, unknown>> = [];
  if (width === 1440) {
    const sel = page.locator('[data-testid="ms-treemap-group"]');
    const opts = await sel.locator('option').allInnerTexts();
    for (const label of opts) {
      await sel.selectOption({ label });
      await page.getByTestId('ms-treemap-apply').click();
      await page.waitForTimeout(1800);
      const st = await page.evaluate(() => {
        const cells = document.querySelectorAll('[data-testid^="treemap-cell-"]').length;
        const err = document.querySelector('[data-testid="ms-treemap-error"]');
        const nodata = document.querySelector('[data-testid="ms-treemap-nodata"]');
        const count = document.querySelector('[data-testid="ms-treemap-count"]');
        return { cells, error: err ? err.textContent : null,
          errorKind: err?.getAttribute('data-error-kind') ?? null,
          nodata: nodata ? String(nodata.textContent).slice(0, 70) : null,
          declared: count ? String(count.textContent).replace(/\s+/g, ' ').slice(0, 90) : null };
      });
      groups.push({ label: label.trim(), ...st });
    }
  }

  // tooltip و کلیک — درِ آخر، چون کلیک ازِ صفحه بیرون می‌رود و کرکره را می‌بَرَد
  let interaction: Record<string, unknown> = { skipped: 'بی‌سلول' };
  if (geo.count) {
    const first = page.locator('[data-testid^="treemap-cell-"]').nth(0);
    const key = await first.evaluate((el) => el.getAttribute('data-testid')!.replace('treemap-cell-', ''));
    await first.hover({ force: true });
    await page.waitForTimeout(500);
    const tip = await page.locator('[data-testid="ms-treemap-tooltip"]').allInnerTexts()
      .catch(() => [] as string[]);
    await first.click({ force: true });
    await page.waitForTimeout(1200);
    const hash = page.url();
    const chosen = await page.locator('[data-testid="sarkhati-chosen-symbol"], .master-symbol, h1')
      .first().innerText().catch(() => '');
    interaction = { key, tipShown: tip.join(' ').slice(0, 120), tipHasKey: tip.join(' ').includes(key),
      urlAfterClick: hash, chosenText: chosen.slice(0, 40) };
  }

  report.runs.push({ width, ...geo, interaction, groups, errors });
  await page.screenshot({ path: `${OUT}/treemap-${width}.png` });
  await ctx.close();
}

await browser.close();
writeFileSync(`${OUT}/treemap-geometry.json`, JSON.stringify(report, null, 1), 'utf-8');

const r0 = report.runs[0] as Record<string, never>;
console.log('\n== market_treemap_probe ==');
for (const run of report.runs as Array<Record<string, unknown>>) {
  const w = run.width;
  console.log(`  ${w}px: cells=${run.count} overlaps=${run.overlaps} outside=${run.outside}`
    + ` degenerate=${run.degenerate} host=${JSON.stringify(run.hostBox)} svg=${JSON.stringify(run.svgBox)}`);
  const it = run.interaction as Record<string, unknown>;
  console.log(`        tooltip: shown="${String(it.tipShown).slice(0, 60)}" hasKey=${it.tipHasKey}`);
  console.log(`        click → ${String(it.urlAfterClick).slice(0, 90)} chosen="${String(it.chosenText).trim()}"`);
  const gs = (run.groups as Array<Record<string, unknown>>) ?? [];
  if (gs.length) {
    console.log(`        دامنه‌هایِ کرکره (${gs.length}):`);
    for (const g of gs) {
      console.log(`          ${String(g.label).padEnd(28)} cells=${String(g.cells).padStart(4)}`
        + ` error=${g.errorKind ?? '—'} declared=${String(g.declared ?? g.nodata ?? '').slice(0, 54)}`);
    }
    const broken = gs.filter((g) => g.error != null);
    ck('هیچ دامنه‌ای از کرکره خطای سرویس نمی‌دهد', broken.length === 0,
      broken.map((b) => `${b.label}: ${String(b.error).slice(0, 60)}`).join(' | '));
    const emptyOk = gs.filter((g) => Number(g.cells) === 0 && g.nodata == null && g.error == null);
    ck('هر دامنۀِ بی‌خانه، علّت را می‌نویسد (نه سکوت)', emptyOk.length === 0,
      emptyOk.map((b) => String(b.label)).join(', '));
  }
  if ((run.errors as string[]).length) console.log('        خطا: ' + (run.errors as string[]).join(' | '));
  ck(`${w}px: بی‌هم‌پوشانی`, Number(run.overlaps) === 0, JSON.stringify(run.pairSamples));
  ck(`${w}px: هیچ سلول بیرونِ قاب نیست`, Number(run.outside) === 0, String(run.outside));
  ck(`${w}px: سلولِ صفراندازه نیست`, Number(run.degenerate) === 0, String(run.degenerate));
  ck(`${w}px: tooltip همان نماد را می‌گوید`, it.tipHasKey === true, String(it.tipShown).slice(0, 80));
}
let failed = 0;
for (const [n, ok, extra] of results) {
  if (!ok) failed++;
  console.log((ok ? '  ok   ' : '  FAIL ') + n + (extra ? ' — ' + extra : ''));
}
console.log('\n%d checks passed / %d failed — JSON: %s', results.length - failed, failed, OUT);
void r0;
process.exit(failed ? 1 : 0);
