// Switch through many chart symbols and sample the post-GC JS heap. Used to
// test whether per-symbol HTTP response caching grows without bound.
//
// usage: node tools/performance/chart_symbol_stress.js --symbols 60 --out <json>
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
const N = Number(arg('--symbols', '60'));
const OUT = path.resolve(REPO, arg('--out', 'artifacts/performance/chart-symbol-stress.json'));

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
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--enable-precise-memory-info'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1000);
  await login(page);
  await page.evaluate(() => { location.hash = '#/technical'; });
  await page.waitForTimeout(3000);
  const symbols = await page.evaluate(async () => {
    try {
      const j = await (await fetch('/api/mstat/mainwatch?group=eq_all&industry=')).json();
      return [...new Set((j.rows || []).map((r) => r.symbol).filter(Boolean))];
    } catch (e) { return []; }
  });
  const pick = symbols.slice(0, N);
  if (!pick.length) throw new Error('no symbols from mainwatch');
  const client = await ctx.newCDPSession(page);
  await client.send('Performance.enable');
  await client.send('HeapProfiler.enable');
  const take = async (label, i) => {
    await client.send('HeapProfiler.collectGarbage');
    await page.waitForTimeout(250);
    const m = Object.fromEntries((await client.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
    const dom = await client.send('Memory.getDOMCounters').catch(() => null);
    return {
      label, i,
      heapMB: m.JSHeapUsedSize ? Math.round(m.JSHeapUsedSize / 1e5) / 10 : null,
      nodes: m.Nodes ?? dom?.nodes ?? null,
      listeners: m.JSEventListeners ?? dom?.jsEventListeners ?? null,
      apiResources: await page.evaluate(() => performance.getEntriesByType('resource').filter((r) => r.name.includes('/api/')).length),
    };
  };
  const samples = [await take('baseline', 0)];
  for (let i = 0; i < pick.length; i++) {
    await page.evaluate((s) => { location.hash = '#/technical/' + encodeURIComponent(s); }, pick[i]);
    await page.waitForTimeout(850);
    if ((i + 1) % 10 === 0) {
      const s = await take(`after-${i + 1}`, i + 1);
      samples.push(s);
      console.log(`${i + 1} symbols: heap=${s.heapMB}MB nodes=${s.nodes} listeners=${s.listeners} api=${s.apiResources}`);
    }
  }
  await page.waitForTimeout(1500);
  const end = await take('settled', pick.length);
  samples.push(end);
  console.log(`settled: heap=${end.heapMB}MB nodes=${end.nodes} listeners=${end.listeners}`);
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify({ base: BASE, requested: N, symbols: pick.length, samples, errors }, null, 1));
  console.log('wrote', OUT);
  await browser.close();
})().catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
