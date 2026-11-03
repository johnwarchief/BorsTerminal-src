// Sustained-session probe: repeat a realistic tab cycle and sample heap, DOM
// nodes and JS listeners after a forced GC. Read-only.
//
// usage: node tools/performance/sustained_session.js --cycles 8 --out <json>
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
const CYCLES = Number(arg('--cycles', '8'));
const OUT = path.resolve(REPO, arg('--out', 'artifacts/performance/sustained.json'));
const ROUTES = ['/market', '/market-status', '/fundamental', '/master', '/technical'];

async function login(page) {
  if (!(await page.evaluate(() => !!document.querySelector('input[type="password"]')))) return false;
  const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
  const u = (src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
  const p = (src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
  await page.locator('input[type="text"]').first().fill(u);
  await page.locator('input[type="password"]').first().fill(p);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(2500);
  return true;
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--enable-precise-memory-info'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  await login(page);
  await page.waitForTimeout(1500);
  const client = await ctx.newCDPSession(page);
  await client.send('Performance.enable');
  await client.send('HeapProfiler.enable');

  const samples = [];
  const take = async (label) => {
    await client.send('HeapProfiler.collectGarbage');
    await page.waitForTimeout(250);
    const m = Object.fromEntries((await client.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
    const heap = m.JSHeapUsedSize ? m.JSHeapUsedSize / 1e6 : null;
    const dom = await client.send('Memory.getDOMCounters').catch(() => null);
    const res = await page.evaluate(() => performance.getEntriesByType('resource').filter((r) => r.name.includes('/api/')).length);
    samples.push({
      label,
      heapMB: heap == null ? null : Math.round(heap * 10) / 10,
      nodes: m.Nodes ?? dom?.nodes ?? null,
      listeners: m.JSEventListeners ?? dom?.jsEventListeners ?? null,
      documents: dom?.documents ?? null,
      apiResources: res,
      route: await page.evaluate(() => location.hash),
    });
  };

  await take('baseline');
  for (let c = 1; c <= CYCLES; c++) {
    for (const r of ROUTES) {
      await page.evaluate((route) => { location.hash = '#' + route; }, r);
      await page.waitForTimeout(1400);
    }
    // symbol switching on the chart, the most allocation-heavy surface
    for (const s of ['سپيدار', 'دزهراوي', 'البرز', 'زگلدشت', 'وتعاون']) {
      await page.evaluate((sym) => { location.hash = '#/technical/' + encodeURIComponent(sym); }, s);
      await page.waitForTimeout(900);
    }
    await take(`cycle-${c}`);
    console.log(`cycle ${c}: heap=${samples[samples.length - 1].heapMB}MB nodes=${samples[samples.length - 1].nodes} listeners=${samples[samples.length - 1].listeners} api=${samples[samples.length - 1].apiResources}`);
  }
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify({ base: BASE, cycles: CYCLES, routes: ROUTES, samples, errors }, null, 1));
  console.log('wrote', OUT);
  await browser.close();
})().catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
