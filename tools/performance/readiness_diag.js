// Diagnose why a route's readiness condition is delayed: poll the same
// conditions the benchmark uses (route, marker count, *-loading elements,
// DOM-quiet age) every 150ms and print the transition.
//
// usage: node tools/performance/readiness_diag.js --route fundamental --marker '[data-testid="fts-screen-row"]' --min 5
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
const ROUTE = '/' + path.basename(arg('--route', 'fundamental'));
const MARKER = arg('--marker', '[data-testid="fts-screen-row"]');
const MIN = Number(arg('--min', '5'));
const SECONDS = Number(arg('--seconds', '15'));
const PRE = arg('--pre', '');
const PRE_WAIT = Number(arg('--pre-wait', '3500'));

async function login(page) {
  if (!(await page.evaluate(() => !!document.querySelector('input[type="password"]')))) return;
  const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
  const u = (src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
  const p = (src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
  await page.locator('input[type="text"]').first().fill(u);
  await page.locator('input[type="password"]').first().fill(p);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(2500);
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const page = await ctx.newPage();
  await page.addInitScript(() => {
    window.__diag = { lastMut: 0 };
    const mark = () => { window.__diag.lastMut = performance.now(); };
    const start = () => new MutationObserver(mark).observe(document.body, { subtree: true, childList: true, characterData: true });
    if (document.body) start(); else addEventListener('DOMContentLoaded', start);
  });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(700);
  await login(page);
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="fts-funnel-workspace"]').length > 0, { timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(500);

  // optional preceding tab, mirrors the benchmark's tab cycle
  const prePath = '/' + path.basename(PRE || 'market');
  const pre = page.locator(`a[href$="${prePath}"]`).first();
  if (await pre.count()) { await pre.evaluate((el) => el.click()); }
  else { await page.evaluate((r) => { location.hash = '#' + r; }, prePath); }
  await page.waitForTimeout(PRE_WAIT);

  const t0 = Date.now();
  let link = page.locator(`a[href$="${ROUTE}"]`).first();
  if (!(await link.count())) link = page.locator(`a[aria-label="بنیادی"]`).first();
  if (await link.count()) {
    await link.evaluate((el) => el.click());
  } else { await page.evaluate((r) => { location.hash = '#' + r; }, ROUTE); }

  const samples = [];
  for (let i = 0; i < SECONDS * 1000 / 150; i++) {
    const s = await page.evaluate(([marker, min]) => {
      const loaders = [...document.querySelectorAll('[data-testid$="-loading"]')]
        .map((el) => el.getAttribute('data-testid'));
      const lm = (window.__diag && window.__diag.lastMut) || 0;
      return {
        t: Math.round(performance.now()),
        hash: location.hash,
        rows: document.querySelectorAll(marker).length,
        loaders,
        quietMs: lm ? Math.round(performance.now() - lm) : -1,
        dom: document.getElementsByTagName('*').length,
        apiPending: performance.getEntriesByType('resource').filter((r) => r.name.includes('/api/') && r.responseEnd === 0).length,
      };
    }, [MARKER, MIN]);
    s.wall = Date.now() - t0;
    const ready = s.hash.startsWith('#' + ROUTE) && s.rows >= MIN && s.loaders.length === 0 && s.quietMs > 700;
    s.ready = ready;
    const prev = samples[samples.length - 1];
    if (!prev || prev.rows !== s.rows || prev.loaders.join('|') !== s.loaders.join('|') || prev.hash !== s.hash || ready)
      samples.push(s);
    if (ready) break;
    await page.waitForTimeout(150);
  }
  console.log(JSON.stringify({ route: ROUTE, marker: MARKER, min: MIN, errors, samples }, null, 1));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
