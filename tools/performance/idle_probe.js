// Idle-resource probe: stay on a route with no user input and measure the
// renderer's CPU time, API request volume and bytes over a window.
//
// usage: node tools/performance/idle_probe.js --route master --seconds 60 --out <json>
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
const ROUTE = arg('--route', 'master').replace(/^.*[\\/]/, '');
const SECONDS = Number(arg('--seconds', '60'));
const OUT = path.resolve(REPO, arg('--out', 'artifacts/performance/idle.json'));

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
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1000);
  await login(page);
  await page.evaluate((r) => { location.hash = '#/' + r; }, ROUTE);
  await page.waitForTimeout(5000);

  const client = await ctx.newCDPSession(page);
  await client.send('Performance.enable');
  const metrics = async () => Object.fromEntries(
    (await client.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
  const resources = async () => page.evaluate(() => {
    const rs = performance.getEntriesByType('resource').filter((r) => r.name.includes('/api/'));
    return {
      n: rs.length,
      enc: rs.reduce((a, r) => a + (r.encodedBodySize || 0), 0),
      items: rs.map((r) => ({
        u: decodeURIComponent(r.name).replace(/^https?:\/\/[^/]+/, '').split('?')[0],
        method: r.initiatorType,
        ms: Math.round(r.duration),
        enc: r.encodedBodySize || 0,
      })),
    };
  });

  const m0 = await metrics();
  const r0 = await resources();
  await page.waitForTimeout(SECONDS * 1000);
  const m1 = await metrics();
  const r1 = await resources();
  const during = r1.items.slice(r0.n);
  const report = {
    base: BASE, route: '/' + ROUTE, seconds: SECONDS,
    cpu: {
      taskSeconds: +(m1.TaskDuration - m0.TaskDuration).toFixed(3),
      scriptSeconds: +(m1.ScriptDuration - m0.ScriptDuration).toFixed(3),
      layoutSeconds: +(m1.LayoutDuration - m0.LayoutDuration).toFixed(3),
    },
    api: {
      requests: r1.n - r0.n,
      encodedBytes: r1.enc - r0.enc,
      items: during,
    },
    heapMB: +(m1.JSHeapUsedSize / 1e6).toFixed(1),
    nodes: m1.Nodes ?? null,
    listeners: m1.JSEventListeners ?? null,
  };
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(report, null, 1));
  console.log(JSON.stringify(report, null, 1));
  await browser.close();
})().catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
