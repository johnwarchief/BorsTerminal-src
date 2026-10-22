// P2-R4 guard: rapid pointer sweeps over funnel rows must not prefetch, while a
// deliberate dwell fires exactly the two intended endpoints. Requests are counted
// at request-start via Playwright network events (Resource Timing entries only
// appear when a fetch completes, which misattributes in-flight prefetches).
const path = require('path'), fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const OUT = path.resolve(REPO, 'artifacts/performance/phase2/hover-scan.json');

async function login(p) {
  if (!(await p.evaluate(() => !!document.querySelector('input[type="password"]')))) return;
  const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
  const u = (src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
  const pw = (src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
  await p.locator('input[type=text]').first().fill(u);
  await p.locator('input[type=password]').first().fill(pw);
  await p.locator('button[type=submit]').first().click();
  await p.waitForTimeout(2200);
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const p = await ctx.newPage();
  const hits = [];
  p.on('request', (r) => {
    const u = decodeURIComponent(r.url());
    if (u.includes('/api/fts/') || u.includes('/key-levels')) hits.push({ u: u.replace(/^https?:\/\/[^/]+/, '').split('?')[0], at: Date.now() });
  });
  await p.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(700);
  await login(p);
  await p.evaluate(() => { location.hash = '#/master?preset=tech_first&stage=technical'; });
  await p.waitForFunction(() => document.querySelectorAll('[data-fkey]').length > 0, null, { timeout: 40000 });
  await p.waitForTimeout(500);
  // bring the table body into the middle of the viewport so row coordinates are stable
  await p.evaluate(() => document.querySelector('[data-testid="funnel-scroll-technical"]')?.scrollIntoView({ block: 'center' }));
  await p.waitForTimeout(400);
  const rows = await p.evaluate(() => [...document.querySelectorAll('[data-fkey]')].slice(0, 8).map((el) => {
    const r = el.getBoundingClientRect();
    return { sym: el.getAttribute('data-fkey'), x: r.x + 30, y: r.y + r.height / 2, top: r.top, bottom: r.bottom };
  }).filter((r) => r.top > 60 && r.bottom < 740));
  if (rows.length < 3) throw new Error('not enough visible rows: ' + JSON.stringify(rows));

  // 1) fast sweep: 120ms per row, well below the 300ms debounce
  const sweepFrom = hits.length;
  const t0 = Date.now();
  for (const r of rows.slice(0, 4)) {
    await p.mouse.move(r.x, r.y);
    await p.waitForTimeout(120);
  }
  await p.mouse.move(rows[0].x, 40); // neutral header -> mouseleave cancels timers
  await p.waitForTimeout(900);
  const sweepHits = hits.slice(sweepFrom);

  // 2) deliberate dwell on one row
  const dwellFrom = hits.length;
  await p.mouse.move(rows[0].x, rows[0].y);
  await p.waitForTimeout(500);
  await p.waitForTimeout(900);
  const dwellHits = hits.slice(dwellFrom);

  const report = {
    rows: rows.map((r) => r.sym),
    sweep: { rows: 4, perRowMs: 120, elapsedMs: Date.now() - t0, requests: sweepHits.map((h) => h.u) },
    dwell: { ms: 500, requests: dwellHits.map((h) => h.u) },
  };
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(report, null, 1));
  console.log(JSON.stringify(report, null, 1));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
