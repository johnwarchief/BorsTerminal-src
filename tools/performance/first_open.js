// Measure the first open of a route in a fresh browser context (cold JS/HTTP
// cache). Used for the market-status tab, whose first open fans out to many
// panel endpoints. The caller is responsible for restarting the backend so
// server caches are cold too.
//
// usage: node tools/performance/first_open.js --route /market-status --runs 1 --out <json>
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));

const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
// Git Bash rewrites a leading `/route` into a Windows path; accept either form
// and keep only the last segment.
const ROUTE = '/' + path.basename(arg('--route', 'market-status'));
const RUNS = Number(arg('--runs', '1'));
const OUT = path.resolve(REPO, arg('--out', 'artifacts/performance/first-open.json'));

const MARKERS = {
  '/market-status': '[data-testid^="treemap-cell-"]',
  '/fundamental': '[data-testid="fts-screen-row"]',
  '/market': '[data-testid="tape-row"]',
  '/master': '[data-testid="fts-funnel-workspace"]',
};

const INIT = () => {
  const p = { longtasks: [], lastMut: 0, frames: [] };
  window.__perf = p;
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) p.longtasks.push({ d: Math.round(e.duration) });
    }).observe({ type: 'longtask', buffered: true });
  } catch (e) { /* older engine */ }
  const mark = () => { p.lastMut = performance.now(); };
  const start = () => new MutationObserver(mark).observe(document.body, { subtree: true, childList: true, characterData: true });
  if (document.body) start(); else addEventListener('DOMContentLoaded', start);
  let last = 0;
  const tick = (t) => { if (last) p.frames.push(Math.round(t - last)); last = t; requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
};

async function loginIfNeeded(page) {
  if (!(await page.evaluate(() => !!document.querySelector('input[type="password"]')))) return false;
  const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
  const du = (src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
  const dp = (src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
  await page.locator('input[type="text"]').first().fill(du);
  await page.locator('input[type="password"]').first().fill(dp);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(2500);
  return true;
}

async function clickRoute(page, route) {
  const labelMap = { '/market-status': 'وضعیت بازار', '/fundamental': 'بنیادی', '/market': 'تابلوخوانی', '/master': 'استراتژی FTS' };
  let link = page.locator(`a[aria-label="${labelMap[route] || route}"]`).first();
  if (!(await link.count())) link = page.locator(`a[href$="${route}"]`).first();
  if (await link.count()) {
    try { await link.click({ timeout: 5000 }); return true; } catch { await link.evaluate((el) => el.click()); return true; }
  }
  await page.evaluate((r) => { location.hash = '#' + r; }, route);
  return false;
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--enable-precise-memory-info'] });
  const results = [];
  const marker = MARKERS[ROUTE];
  for (let run = 0; run < RUNS; run++) {
    const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
    const page = await ctx.newPage();
    await page.addInitScript(INIT);
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    const t0 = Date.now();
    await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
    const login = await loginIfNeeded(page);
    // wait for the landing page to settle before opening the target tab
    await page.waitForFunction(`document.querySelectorAll('[data-testid="fts-funnel-workspace"]').length > 0`, { timeout: 60000 }).catch(() => {});
    await page.waitForTimeout(800);
    const pre = await page.evaluate(() => performance.getEntriesByType('resource').length);
    const tClick = Date.now();
    const clicked = await clickRoute(page, ROUTE);
    let ready = null;
    try {
      await page.waitForFunction(`(() => {
        if (!location.hash.startsWith('#${ROUTE}')) return false;
        if (document.querySelectorAll('[data-testid$="-loading"]').length > 0) return false;
        if (document.querySelectorAll('${marker}').length < 1) return false;
        const lm = (window.__perf && window.__perf.lastMut) || 0;
        return lm > 0 && (performance.now() - lm) > 700;
      })()`, { timeout: 45000 });
      ready = Date.now() - tClick;
    } catch (e) { /* keep null = not ready */ }
    const d = await page.evaluate((pre) => {
      const p = window.__perf || { longtasks: [], frames: [] };
      const res = performance.getEntriesByType('resource').slice(pre).filter((r) => r.name.includes('/api/'));
      const by = {};
      for (const r of res) {
        const u = r.name.replace(/^https?:\/\/[^/]+/, '').split('?')[0];
        const b = by[u] || (by[u] = { n: 0, max: 0, sum: 0, enc: 0 });
        b.n++; b.max = Math.max(b.max, r.duration); b.sum += r.duration; b.enc += r.encodedBodySize || 0;
      }
      const fr = (p.frames || []).slice().sort((a, b) => a - b);
      return {
        requests: Object.entries(by).map(([u, v]) => ({ url: u, n: v.n, maxMs: Math.round(v.max), sumMs: Math.round(v.sum), enc: v.enc })),
        requestTotal: res.length,
        encodedBytes: res.reduce((a, r) => a + (r.encodedBodySize || 0), 0),
        longtasks: (p.longtasks || []).length,
        tbt: (p.longtasks || []).reduce((a, x) => a + Math.max(0, x.d - 50), 0),
        framesOver100: fr.filter((x) => x > 100).length,
        heapMB: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1e6) : null,
      };
    }, pre);
    d.run = run + 1; d.login = login; d.clickedNav = clicked; d.readyMs = ready;
    d.fromGotoMs = Date.now() - t0; d.errors = errors;
    results.push(d);
    console.log(`run ${run + 1}: ready=${ready}ms requests=${d.requestTotal} enc=${Math.round(d.encodedBytes / 1024)}KiB ` +
                `longtasks=${d.longtasks} tbt=${d.tbt} maxReq=${Math.max(0, ...d.requests.map((r) => r.maxMs))}ms errors=${errors.length}`);
    await ctx.close();
  }
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify({ route: ROUTE, base: BASE, ranAt: new Date().toISOString(), results }, null, 1));
  console.log('wrote', OUT);
  await browser.close();
})().catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
