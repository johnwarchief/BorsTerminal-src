// _audit/ui/ready_probe.js — نشانۀِ آمادگیِ درستِ هرِ صفحه
//
// چرا: درِ جاروبِ قبلی چندِ route «ready=timeout» شد، یعنی یا نشانۀِ انتخابی
// آنِ صفحه نیست، یا شمارۀِ کمینۀِ آزمون غلط است (example: tape-row≥30 در حالی
// که تابلویِ نشستِ بسته کمتر ردیف دارد). نشانۀِ غلط = صفحۀِ ناشنجانده‌شده که
// درِ گزارش PASS می‌شود؛ پس اول باید فهرستِ testidهایِ واقعیِ هرِ صفحه درآمد.
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const arg = (n, d) => { const h = process.argv.find((a) => a.startsWith('--' + n + '=')); return h ? h.split('=').slice(1).join('=') : d; };
const W = Number(arg('w', 1366)), H = Number(arg('h', 768));
const WAIT = Number(arg('wait', 7000));

const LIST = () => {
  const main = document.querySelector('main') || document.body;
  const ids = [...main.querySelectorAll('[data-testid]')].map((e) => e.getAttribute('data-testid'));
  const uniq = {};
  for (const i of ids) uniq[i] = (uniq[i] || 0) + 1;
  return { total: ids.length, uniq, text: (main.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 160) };
};

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1', '--remote-debugging-port=0'] });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
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
  const routes = require('./routes.js').ROUTES;
  const out = [];
  for (const [route, marker, min] of routes) {
    await page.goto(BASE + '/#' + route, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(WAIT);
    const l = await page.evaluate(LIST);
    const mc = marker ? await page.locator(marker).count() : null;
    console.log(`\n== ${route}   marker=${marker || '(none)'} present=${mc} (need ${min || 1})   testids=${l.total}`);
    console.log('   ' + Object.entries(l.uniq).sort((a, b) => b[1] - a[1]).slice(0, 18).map(([k, v]) => k + (v > 1 ? '×' + v : '')).join(', '));
    console.log('   text: ' + l.text);
    out.push({ route, marker, present: mc, ids: l.uniq, text: l.text });
  }
  fs.writeFileSync(path.join(REPO, '_audit', 'ui', 'READY_PROBE.json'), JSON.stringify(out, null, 1));
  await browser.close();
  return 0;
})().then((rc) => process.exit(rc)).catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
