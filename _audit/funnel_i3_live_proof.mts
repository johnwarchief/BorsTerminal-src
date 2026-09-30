// _audit/funnel_i3_live_proof.mts -- شاهدِ زندهٔ UI: شاخص ۳ بی‌داده «—» است نه «✗»
//   یک نماد با حاشیۀ تهی (وطوبي) و یک نماد با حاشیۀ عدددارِ زیرِ آستانه (شپلي)
//   را در هر دو بکاند می‌خواند: 8001 = نسخۀ نصبی (کدِ کهنه) و 8003 = بکاندِ اصلاح‌شده.
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR!;
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const arg = (n: string, f = '') => { const i = process.argv.indexOf(`--${n}`); return i >= 0 ? process.argv[i + 1] : f; };
const OUT = arg('out', '_audit/funnel_i3_live_proof.json');
const TARGETS = ['وطوبي', 'شپلي', 'اندوخته داريوش'];

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const result: any = {};
for (const base of ['http://127.0.0.1:8001/', 'http://127.0.0.1:8003/']) {
  const ctx = await browser.newContext({ viewport: { width: 1632, height: 950 } });
  await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
  const page = await ctx.newPage();
  const errs: string[] = [];
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 140)); });
  await page.goto(base + '#/master', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="funnel-stage-technical"]', { timeout: 60_000 });
  await page.waitForTimeout(9000);
  // کفِ بنیادی را ۱ می‌کنیم تا ردیف‌هایِ پنج‌شاخصه درِ جدولِ اصلی دیده شوند
  await page.click('[data-testid="funnel-tech-selfcheck"]').catch(() => {});
  await page.waitForTimeout(900);
  await page.click('[data-testid="funnel-floor-1"]').catch(() => {});
  await page.waitForTimeout(1500);
  // ستونِ سومِ جدولِ بنیادی = حاشیه ناخالص (ستونِ ۱ نماد است)
  result[base] = await page.evaluate((syms: string[]) => {
    const sec = document.querySelector('[data-testid="funnel-stage-fundamental"]');
    const rows = [...sec!.querySelectorAll('tbody tr[data-fkey]')];
    const hit = (s: string) => rows.find((r) => r.getAttribute('data-fkey') === s);
    return syms.map((s) => {
      const tr = hit(s);
      return { sym: s, found: !!tr, cells: tr ? [...tr.children].map((c) => c.textContent?.trim()) : null };
    });
  }, TARGETS);
  result[base + '__errors'] = errs.length;
  await page.click('[data-testid="funnel-prefs-reset"]').catch(() => {});
  await ctx.close();
}
writeFileSync(OUT, JSON.stringify(result, null, 1), 'utf-8');
for (const k of Object.keys(result)) {
  if (k.endsWith('__errors')) { console.log(k, '=', result[k]); continue; }
  console.log(k);
  for (const r of result[k] as any[]) console.log('   ', r.sym, r.found ? r.cells?.join('|') : 'NOT IN FUNNEL');
}
await browser.close();
