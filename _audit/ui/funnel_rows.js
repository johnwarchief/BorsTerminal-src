// _audit/ui/funnel_rows.js — چرا سطرهایِ قیف نیست؟ (تشخیصِ C7/C10)
// usage: MSYS_NO_PATHCONV=1 node _audit/ui/funnel_rows.js
const path = require('path'); const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || String.raw`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`;

const DUMP = () => {
  const txt = (sel) => { const e = document.querySelector(sel); return e ? String(e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 300) : null; };
  const box = (sel) => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; };
  return {
    hash: location.hash,
    trFkey: document.querySelectorAll('tr[data-fkey]').length,
    trFkeySample: [...document.querySelectorAll('tr[data-fkey]')].slice(0, 3).map((t) => String(t.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60)),
    tdButtons: document.querySelectorAll('tr[data-fkey] td button').length,
    emptyTape: txt('[data-testid="funnel-empty-tape"]'),
    emptyTech: txt('[data-testid="funnel-empty-technical"]'),
    pendingTape: txt('[data-testid="funnel-pending-tape"]'),
    stageTape: txt('[data-testid="funnel-stage-tape"]'),
    scrollTapeBox: box('[data-testid="funnel-scroll-tape"]'),
    counts: txt('[data-testid="funnel-counts"]'),
    stepTechBox: box('[data-testid="fts-step-technical"]'),
    stepTechHref: (() => { const a = document.querySelector('[data-testid="fts-step-technical"]'); return a ? a.getAttribute('href') : null; })(),
    ids: [...new Set([...document.querySelectorAll('[data-testid]')].map((e) => e.getAttribute('data-testid')))].filter((x) => /funnel|analyst|horizon/.test(x)).slice(0, 40),
  };
};

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2500);
  }
  await page.goto(BASE + '/#/master', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(25000);
  const before = await page.evaluate(DUMP);
  console.log('BEFORE-CLICK ' + JSON.stringify(before, null, 1));
  // گام ۲ را می‌زنیم و می‌بینیم URL/مرورگر واقعاً کجا می‌نشیند
  await page.locator('[data-testid="fts-step-technical"]').first().click();
  await page.waitForTimeout(6000);
  const after = await page.evaluate(DUMP);
  console.log('AFTER-STEP2 ' + JSON.stringify(after, null, 1));
  // سطرِ قیف (اگر هست) را می‌زنیم تا نماد انتخاب شود
  const has = await page.locator('tr[data-fkey] td button').count();
  console.log('rowButtons=' + has);
  if (has > 0) {
    await page.locator('tr[data-fkey] td button').first().click();
    await page.waitForTimeout(9000);
    console.log('AFTER-PICK ' + JSON.stringify(await page.evaluate(() => ({
      hash: location.hash,
      analyst: (() => { const e = document.querySelector('[data-testid="fts-analyst-open"]'); if (!e) return null; const r = e.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; })(),
      horizon: !!document.querySelector('[data-testid="strategy-horizon-selector"]'),
      titles: [...document.querySelectorAll('h2,h3')].map((h) => String(h.innerText).trim()).slice(0, 8),
    })), null, 1));
  }
  await browser.close();
})();
