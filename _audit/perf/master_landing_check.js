// _audit/perf/master_landing_check.js — PERFF Stage 6/8: what does the user actually SEE on
// the landing route (#/master) while the first heavy build is still running?
//
// The tab-cycle harness reported that /master never reached its readiness marker inside the
// deadline. That is either (a) a white screen — forbidden by the mission — or (b) a visible
// loading state waiting on a specific endpoint. Only a real browser can tell, so this probe
// samples the DOM and the in-flight API requests on a timeline and keeps screenshots.
//
// usage: cd BorsTerminal-src
//   node _audit/perf/master_landing_check.js            (needs the dev backend on :8000)
const os = require('os');
const fs = require('fs');
const path = require('path');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));

const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const OUT = path.join(REPO, '_audit', 'perf', 'MASTER_LANDING.json');
const SHOTS = path.join(REPO, '_audit', 'perf', 'shots');
const SAMPLE_AT = [1, 2, 3, 4, 6, 8, 12, 20, 30, 45];

const probe = () => {
  const q = (s) => document.querySelectorAll(s).length;
  const text = (document.body.innerText || '').replace(/\s+/g, ' ').trim();
  const pend = performance.getEntriesByType('resource')
    .filter((r) => r.name.includes('/api/') && r.responseEnd === 0)
    .map((r) => decodeURIComponent(r.name.replace(/^https?:\/\/[^/]+/, '')));
  const done = performance.getEntriesByType('resource')
    .filter((r) => r.name.includes('/api/') && r.responseEnd > 0)
    .map((r) => ({ u: decodeURIComponent(r.name.replace(/^https?:\/\/[^/]+/, '')),
                   ms: Math.round(r.duration), status: r.transferSize > 0 ? 'body' : 'empty/304' }));
  return {
    hash: location.hash,
    elements: document.getElementsByTagName('*').length,
    chars: text.length,
    head: text.slice(0, 180),
    spinner: /در حال|در انتظار|Loading|loading/.test(text),
    testids: {
      'fts-funnel-workspace': q('[data-testid="fts-funnel-workspace"]'),
      'funnel-counts': (document.querySelector('[data-testid="funnel-counts"]') || {}).childElementCount || 0,
      'funnel-count-pass': q('[data-testid="funnel-count-pass"]'),
      'master-open-funnel': q('[data-testid="master-open-funnel"]'),
      'funnel-chain-row': q('[data-testid="funnel-chain-row"]'),
      'master-breadcrumb': q('[data-testid="master-breadcrumb"]'),
      'tape-row': q('[data-testid="tape-row"]'),
      'treemap-cell': q('[data-testid^="treemap-cell"]'),
      'fts-screen-row': q('[data-testid="fts-screen-row"]'),
    },
    canvas: q('canvas'),
    pendingApi: pend,
    apiDurations: done.slice(-6),
  };
};

(async () => {
  if (!fs.existsSync(SHOTS)) fs.mkdirSync(SHOTS, { recursive: true });
  const browser = await chromium.launch({
    executablePath: EXE,
    args: ['--no-first-run', '--disable-sync', '--remote-debugging-port=0'],
  });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const page = await ctx.newPage();
  const t0 = Date.now();
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);

  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    const du = (src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
    const dp = (src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
    await page.locator('input[type="text"]').first().fill(du);
    await page.locator('input[type="password"]').first().fill(dp);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2000);
  }

  const timeline = [];
  let next = 0;
  for (let waited = 0; waited < 130; waited++) {
    await page.waitForTimeout(1000);
    const el = (Date.now() - t0) / 1000;
    while (next < SAMPLE_AT.length && el >= SAMPLE_AT[next]) {
      const s = await page.evaluate(probe);
      s.atS = Math.round(el);
      timeline.push(s);
      console.log(`t=${String(s.atS).padStart(3)}s hash=${s.hash} elements=${s.elements} `
        + `chars=${s.chars} spinner=${s.spinner} workspace=${s.testids['fts-funnel-workspace']} `
        + `countCells=${s.testids['funnel-counts']} tapeRows=${s.testids['tape-row']} `
        + `pending=${JSON.stringify(s.pendingApi)}`);
      console.log(`        text: «${s.head}»`);
      await page.screenshot({ path: path.join(SHOTS, `master_t${s.atS}.png`) });
      next++;
    }
  }
  fs.writeFileSync(OUT, JSON.stringify({ base: BASE, ranAt: new Date().toISOString(), timeline }, null, 1));
  console.log(`\nwrote ${OUT}  (+ screenshots in _audit/perf/shots/)`);
  await browser.close();
  return 0;
})().then((rc) => process.exit(rc)).catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
