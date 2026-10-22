// P2-R6 startup probe: first load of the default FTS landing (login included),
// then a warm reload in the same context. Data-ready = the /api/funnel response
// has finished and two frames rendered (the workspace shell appears earlier).
const path = require('path'), fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const argv = process.argv.slice(2); const arg = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
const RUNS = Number(arg('--runs', '3'));
const OUT = path.resolve(REPO, arg('--out', 'artifacts/performance/phase2/startup.json'));

const INIT = () => {
  const p = { lt: [] }; window.__perf = p;
  try {
    new PerformanceObserver((l) => { for (const e of l.getEntries()) p.lt.push(Math.round(e.duration)); })
      .observe({ type: 'longtask', buffered: true });
  } catch (e) { /* older engine */ }
};

async function login(p) {
  if (!(await p.evaluate(() => !!document.querySelector('input[type="password"]')))) return false;
  const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
  const u = (src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
  const pw = (src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
  await p.locator('input[type=text]').first().fill(u);
  await p.locator('input[type=password]').first().fill(pw);
  const t = Date.now();
  await p.locator('button[type=submit]').first().click();
  await p.waitForFunction(() => !document.querySelector('input[type="password"]'), null, { timeout: 20000 });
  return Date.now() - t;
}

async function waitData(p, t0) {
  await p.waitForFunction(() => !!document.querySelector('[data-testid="fts-funnel-workspace"]'), null, { timeout: 40000 });
  const tShell = Date.now() - t0;
  await p.waitForFunction(() => performance.getEntriesByType('resource').some(
    (r) => r.name.includes('/api/funnel') && r.responseEnd > 0), null, { timeout: 40000 });
  await p.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  const tData = Date.now() - t0;
  const info = await p.evaluate(() => {
    const rs = performance.getEntriesByType('resource').filter((r) => r.name.includes('/api/'));
    const funnel = rs.find((r) => r.name.includes('/api/funnel'));
    return {
      requests: rs.length,
      bytesKB: Math.round(rs.reduce((a, r) => a + (r.encodedBodySize || 0), 0) / 1024),
      funnelMs: funnel ? Math.round(funnel.duration) : null,
      funnelKB: funnel ? Math.round((funnel.encodedBodySize || 0) / 1024) : null,
      longtasks: (window.__perf?.lt || []).length,
      worstLongtask: (window.__perf?.lt || []).reduce((a, x) => Math.max(a, x), 0),
      dom: document.getElementsByTagName('*').length,
      heapMB: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1e6) : null,
    };
  });
  return { tShell, tData, ...info };
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--enable-precise-memory-info'] });
  const report = { runs: [] };
  for (let run = 1; run <= RUNS; run++) {
    const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
    const p = await ctx.newPage();
    await p.addInitScript(INIT);
    const t0 = Date.now();
    await p.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
    const loginMs = await login(p);
    const cold = await waitData(p, t0);
    // warm reload: same context/HTTP cache, query cache cleared by the reload
    const t1 = Date.now();
    await p.reload({ waitUntil: 'domcontentloaded' });
    const warm = await waitData(p, t1).catch((e) => ({ error: String(e) }));
    report.runs.push({ run, loginMs, cold, warm });
    console.log(`run ${run}: login=${loginMs}ms cold shell=${cold.tShell} data=${cold.tData} (funnel ${cold.funnelMs}ms/${cold.funnelKB}KB, ${cold.requests} req, ${cold.bytesKB}KB, LT ${cold.longtasks}/${cold.worstLongtask}ms)` +
      ` | warm shell=${warm.tShell} data=${warm.tData} (funnel ${warm.funnelMs}ms/${warm.funnelKB}KB, ${warm.requests} req, ${warm.bytesKB}KB)`);
    await ctx.close();
  }
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(report, null, 1));
  console.log('wrote', OUT);
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
