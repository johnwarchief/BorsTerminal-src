// Measure the default landing (/master) in a fresh browser context: time to a
// usable funnel, API request list/bytes, long tasks/TBT. Read-only.
//
// usage: node tools/performance/landing_probe.js --runs 3 --out <json>
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
const RUNS = Number(arg('--runs', '3'));
const OUT = path.resolve(REPO, arg('--out', 'artifacts/performance/landing.json'));

const INIT = () => {
  const p = { longtasks: [], lastMut: 0 };
  window.__perf = p;
  try {
    new PerformanceObserver((l) => { for (const e of l.getEntries()) p.longtasks.push(Math.round(e.duration)); })
      .observe({ type: 'longtask', buffered: true });
  } catch (e) { /* ignore */ }
  const mark = () => { p.lastMut = performance.now(); };
  const start = () => new MutationObserver(mark).observe(document.body, { subtree: true, childList: true, characterData: true });
  if (document.body) start(); else addEventListener('DOMContentLoaded', start);
};

async function login(page) {
  if (!(await page.evaluate(() => !!document.querySelector('input[type="password"]')))) return false;
  const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
  const u = (src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
  const p = (src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
  await page.locator('input[type="text"]').first().fill(u);
  await page.locator('input[type="password"]').first().fill(p);
  await page.locator('button[type="submit"]').first().click();
  return true;
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--enable-precise-memory-info'] });
  const results = [];
  for (let run = 0; run < RUNS; run++) {
    const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
    const page = await ctx.newPage();
    await page.addInitScript(INIT);
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    const t0 = Date.now();
    await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
    const gate = await login(page);
    let ready = null;
    try {
      await page.waitForFunction(`(() => {
        if (document.querySelectorAll('[data-testid="fts-funnel-workspace"]').length < 1) return false;
        if (document.querySelectorAll('[data-testid$="-loading"]').length > 0) return false;
        const lm = (window.__perf && window.__perf.lastMut) || 0;
        return lm > 0 && (performance.now() - lm) > 700;
      })()`, { timeout: 45000 });
      ready = Date.now() - t0;
    } catch (e) { /* keep null */ }
    const d = await page.evaluate(() => {
      const p = window.__perf || { longtasks: [] };
      const api = performance.getEntriesByType('resource').filter((r) => r.name.includes('/api/'));
      const nav = performance.getEntriesByType('navigation')[0] || {};
      const paint = performance.getEntriesByType('paint');
      const fcp = (paint.find((x) => x.name === 'first-contentful-paint') || {}).startTime ?? null;
      return {
        fcp: fcp == null ? null : Math.round(fcp),
        ttfb: Math.round(nav.responseStart || 0),
        api: api.map((r) => ({
          u: decodeURIComponent(r.name).replace(/^https?:\/\/[^/]+/, '').split('?')[0],
          ms: Math.round(r.duration), enc: r.encodedBodySize || 0,
        })),
        encodedTotal: api.reduce((a, r) => a + (r.encodedBodySize || 0), 0),
        longtasks: (p.longtasks || []).length,
        tbt: (p.longtasks || []).reduce((a, x) => a + Math.max(0, x - 50), 0),
        heapMB: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1e6) : null,
      };
    });
    d.run = run + 1; d.loginGate = gate; d.readyMs = ready; d.errors = errors;
    results.push(d);
    console.log(`run ${run + 1}: ready=${ready}ms FCP=${d.fcp}ms api=${d.api.length} enc=${Math.round(d.encodedTotal / 1024)}KiB tbt=${d.tbt} errors=${errors.length}`);
    await ctx.close();
  }
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify({ base: BASE, ranAt: new Date().toISOString(), results }, null, 1));
  console.log('wrote', OUT);
  await browser.close();
})().catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
