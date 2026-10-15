// _audit/ui/probe_debug.js — آیا حالتِ «نمادِ انتخابی» ازِ یکِ کیس بهِ کیسِ بعد سرایت می‌کند؟
//
// سه شاهدِ لازم برایِ سه NO-TARGET (C7/C10/C12):
//   ۱) /master تنها (بی‌نماد) → قیف است؟ «fts-step-technical» هست؟
//   ۲) /master/فولاد → دossier چندِ ثانیه بعدِ ناوبری می‌رسد و «fts-analyst-open» کِی؟
//   ۳) بعدِ فولاد، دوباره /master → قیف یا دossier؟ (اگر دossier باشد، NO-TARGETِ
//      C10 سرایتِ حالتِ خودِ جاروب است، نه ایرادِ UI)
// usage: node _audit/ui/probe_debug.js
const path = require('path'); const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

const peek = () => {
  const has = (s) => document.querySelectorAll(s).length;
  const vis = (s) => {
    const e = document.querySelector(s);
    if (!e) return null;
    const r = e.getBoundingClientRect();
    return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)];
  };
  return {
    href: location.hash,
    ids: has('[data-testid]'),
    stepTech: has('[data-testid="fts-step-technical"]'),
    funnel: has('[data-testid="fts-funnel-workspace"]'),
    analyst: has('[data-testid="fts-analyst-open"]'),
    horizon: has('[data-testid="strategy-horizon-selector"]'),
    dossierLoading: has('[data-testid="dossier-loading"]'),
    computing: /در حال محاسبه/.test(String(document.body.innerText || '')),
    analystBox: vis('[data-testid="fts-analyst-open"]'),
    h2: [...document.querySelectorAll('h2')].map((h) => String(h.innerText).trim().slice(0, 40)).slice(0, 3),
    treeRail: has('[data-testid^="tree-flow-rail-"]'),
  };
};

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1', '--remote-debugging-port=0'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + String(e).slice(0, 160)));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 160)); });

  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2500);
  }

  // ۱) /master تنها
  await page.goto(BASE + '/#/master', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(12000);
  console.log('1) /master alone        ' + JSON.stringify(await page.evaluate(peek)));

  // ۲) /master/فولاد — چندِ ثانیه طولِ می‌کشد؟
  await page.goto(BASE + '/#/master/' + encodeURIComponent('فولاد'), { waitUntil: 'domcontentloaded' });
  for (const t of [4000, 8000, 12000, 20000]) {
    await page.waitForTimeout(t);
    const s = await page.evaluate(peek);
    console.log('2) /master/فولاد +' + t + 'ms  ' + JSON.stringify(s));
    if (s.analyst > 0) break;
  }

  // ۳) بازگشتِ بی‌نماد؟ نه: همانِ ناوبریِ قبلی، فقطِ /master
  await page.goto(BASE + '/#/master', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(10000);
  console.log('3) /master after فولاد  ' + JSON.stringify(await page.evaluate(peek)));

  // ۴) /strategy-tree بعدِ همانِ حالت
  await page.goto(BASE + '/#/strategy-tree', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(10000);
  console.log('4) /strategy-tree       ' + JSON.stringify(await page.evaluate(peek)));

  console.log('errors=' + errs.length + (errs.length ? ' :: ' + errs.slice(0, 5).join(' || ') : ''));
  await browser.close();
})();
