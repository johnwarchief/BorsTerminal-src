// _audit/fts_table_i3_witness.mts -- گواهِ زنده درِ جدولِ بنیادی: سلولِ «حاشیهٔ ناخالص»
//   ردیفِ نمادی که gross_margin تهی است باید «N/A» بخورد، نه ✗ِ «مردود».
//   دو بکاند در یک نشست: 8001 = اپِ نصبی، 8003 = بکاندِ همین ریپو
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR!;
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const SYMS = ['وطوبي', 'چاپ'];
const OUT = '_audit/fts_table_i3_witness.json';
const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const res: any = {};
for (const base of ['http://127.0.0.1:8001/', 'http://127.0.0.1:8003/']) {
  const ctx = await browser.newContext({ viewport: { width: 1632, height: 950 } });
  await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
  const page = await ctx.newPage();
  const errs: string[] = [];
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 140)); });
  res[base] = [];
  await page.goto(base + '#/fundamental', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="fts-screen-row"]', { timeout: 60_000 });
  await page.waitForTimeout(3000);
  for (const sym of SYMS) {
    const box = page.locator('[data-testid="fts-search"]');
    if (await box.count()) { await box.fill(sym); await page.waitForTimeout(2500); }
    const row = await page.evaluate((s: string) => {
      const rows = [...document.querySelectorAll('[data-testid="fts-screen-row"]')];
      const tr = rows.find((r) => r.querySelector('td')?.textContent?.trim().startsWith(s));
      if (!tr) return { sym: s, found: false, total: rows.length };
      const heads = [...document.querySelectorAll('thead th')].map((t) => t.textContent?.trim());
      const cells = [...tr.querySelectorAll('td')].map((c) => c.textContent?.trim().slice(0, 26));
      const titles = [...tr.querySelectorAll('td')].map((c) => (c.getAttribute('title') ?? c.querySelector('[title]')?.getAttribute('title') ?? '').slice(0, 40));
      return { sym: s, found: true, heads, cells, titles, rowIndex: rows.indexOf(tr) };
    }, sym);
    res[base].push({ ...row, errors: errs.length });
    if (await box.count()) { await box.fill(''); await page.waitForTimeout(800); }
  }
  await ctx.close();
}
writeFileSync(OUT, JSON.stringify(res, null, 1), 'utf-8');
for (const k of Object.keys(res)) for (const r of res[k]) {
  console.log('---', k.replace('http://127.0.0.1:', '').replace('/', ''), r.sym, 'found=' + r.found);
  if (r.found) {
    const i = (r.heads as string[]).findIndex((h) => h && h.includes('حاشیه'));
    console.log('   سرستونِ حاشیه:', i, (r.heads as string[])[i], '| سلول:', JSON.stringify((r.cells ?? [])[i]), '| title:', JSON.stringify((r.titles ?? [])[i]));
    console.log('   heads:', JSON.stringify(r.heads));
  }
}
await browser.close();
