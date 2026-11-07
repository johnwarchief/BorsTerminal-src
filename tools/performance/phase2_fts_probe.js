// Phase-2 FTS workflow probe. Measures each workflow from the user action to
// the relevant API response + render settle, so unrelated global loading
// indicators (e.g. the inspector on pages that show it) do not inflate a
// different tab's number.
//
// Scenarios: cold FTS funnel, warm funnel, symbol dossier switch, same-symbol
// reopen, strategy tree, technical chart open/switch, repeated dossier cycles.
//
// usage: node tools/performance/phase2_fts_probe.js --runs 2 --out <json>
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
const RUNS = Number(arg('--runs', '2'));
const OUT = path.resolve(REPO, arg('--out', 'artifacts/performance/phase2/workflows.json'));

const INIT = () => {
  const p = { longtasks: [], lastMut: 0, frames: [] };
  window.__perf = p;
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) p.longtasks.push(Math.round(e.duration));
    }).observe({ type: 'longtask', buffered: true });
  } catch (e) { /* ignore */ }
  const mark = () => { p.lastMut = performance.now(); };
  const start = () => new MutationObserver(mark).observe(document.body, { subtree: true, childList: true, characterData: true });
  if (document.body) start(); else addEventListener('DOMContentLoaded', start);
  let last = 0;
  const tick = (t) => { if (last) p.frames.push(Math.round(t - last)); last = t; requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
};

async function login(page) {
  if (!(await page.evaluate(() => !!document.querySelector('input[type="password"]')))) return false;
  const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
  const u = (src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
  const p = (src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
  await page.locator('input[type="text"]').first().fill(u);
  await page.locator('input[type="password"]').first().fill(p);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(2200);
  return true;
}

const countResources = (page) => page.evaluate(() => performance.getEntriesByType('resource').length);

async function collect(page, since) {
  return page.evaluate((since) => {
    const p = window.__perf || { longtasks: [], frames: [] };
    const res = performance.getEntriesByType('resource').slice(since).filter((r) => r.name.includes('/api/'));
    const by = {};
    for (const r of res) {
      const u = decodeURIComponent(r.name).replace(/^https?:\/\/[^/]+/, '').split('?')[0];
      const b = by[u] || (by[u] = { n: 0, maxMs: 0, sumMs: 0, enc: 0 });
      b.n += 1; b.maxMs = Math.max(b.maxMs, r.duration); b.sumMs += r.duration; b.enc += r.encodedBodySize || 0;
    }
    const lt = p.longtasks || [];
    const fr = (p.frames || []).slice().sort((a, b) => a - b);
    return {
      requests: Object.entries(by).map(([u, v]) => ({
        url: u, n: v.n, maxMs: Math.round(v.maxMs), sumMs: Math.round(v.sumMs), enc: v.enc,
      })).sort((a, b) => b.maxMs - a.maxMs),
      requestTotal: res.length,
      encodedBytes: res.reduce((a, r) => a + (r.encodedBodySize || 0), 0),
      longtasks: lt.length,
      tbt: lt.reduce((a, x) => a + Math.max(0, x - 50), 0),
      worst: lt.reduce((a, x) => Math.max(a, x), 0),
      frames: fr.length ? { n: fr.length, med: fr[Math.floor(fr.length / 2)], p95: fr[Math.floor(fr.length * 0.95)], max: fr[fr.length - 1], over100: fr.filter((x) => x > 100).length } : null,
      heapMB: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1e6) : null,
      domNodes: document.getElementsByTagName('*').length,
    };
  }, since);
}

async function resetPerf(page) {
  await page.evaluate(() => {
    const p = window.__perf || (window.__perf = { longtasks: [], frames: [], lastMut: 0 });
    p.longtasks = []; p.frames = [];
  });
}

async function waitApi(page, since, needle, timeout = 60000) {
  await page.waitForFunction(([n, s]) => performance.getEntriesByType('resource').slice(s)
    .some((r) => decodeURIComponent(r.name).includes(n) && r.responseEnd > 0), [needle, since], { timeout });
}

async function backToFunnel(page) {
  const back = page.locator('[data-testid="master-back"]');
  if (await back.count()) {
    await back.evaluate((el) => el.click());
    await page.waitForTimeout(350);
  } else {
    await page.evaluate(() => { location.hash = '#/master'; });
    await page.waitForTimeout(350);
  }
}

async function scenario(page, label, action, needles, marker, opts = {}) {
  await resetPerf(page);
  const since = await countResources(page);
  const t = Date.now();
  await action();
  const waits = needles.map((n) => waitApi(page, since, n, opts.apiTimeout ?? 60000)
    .catch(() => null));
  if (marker) {
    await page.waitForFunction((m) => document.querySelectorAll(m).length > 0, marker,
                               { timeout: opts.markerTimeout ?? 60000 }).catch(() => null);
  }
  await Promise.all(waits);
  await page.waitForTimeout(opts.settle ?? 400);
  const d = await collect(page, since);
  d.readyMs = Date.now() - t;
  d.label = label;
  return d;
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--enable-precise-memory-info'] });
  const report = { base: BASE, ranAt: new Date().toISOString(), runs: [] };
  for (let run = 1; run <= RUNS; run++) {
    const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
    const page = await ctx.newPage();
    await page.addInitScript(INIT);
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e).slice(0, 220)));
    const client = await ctx.newCDPSession(page);
    await client.send('Performance.enable');
    await client.send('HeapProfiler.enable');

    // Cold: measure from goto, and do NOT wait for a specific API that may
    // already have fired during login. The workspace + quiet DOM is the user
    // signal; resources are collected from index 0.
    await resetPerf(page);
    const t0 = Date.now();
    await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
    const loginGate = await login(page);
    let cold;
    try {
      await page.waitForFunction(`(() => {
        if (document.querySelectorAll('[data-testid="fts-funnel-workspace"]').length < 1) return false;
        if (document.querySelectorAll('[data-testid$="-loading"]').length > 0) return false;
        const lm = (window.__perf && window.__perf.lastMut) || 0;
        return lm > 0 && (performance.now() - lm) > 700;
      })()`, { timeout: 90000 });
      cold = await collect(page, 0);
    } catch (e) {
      cold = { error: String(e).slice(0, 200), requests: [], requestTotal: 0, encodedBytes: 0, tbt: 0 };
    }
    cold.readyMs = Date.now() - t0;
    cold.loginGate = loginGate;

    const symbols = await page.evaluate(async () => {
      try {
        const j = await (await fetch('/api/mstat/mainwatch?group=eq_all&industry=')).json();
        return [...new Set((j.rows || []).map((r) => r.symbol).filter(Boolean))].slice(0, 3);
      } catch (e) { return ['فولاد']; }
    });

    // leave and come back to the funnel
    await page.evaluate(() => { location.hash = '#/market'; });
    await page.waitForTimeout(6000);
    const warm = await scenario(page, 'warm-funnel', async () => {
      await page.evaluate(() => { location.hash = '#/master'; });
    }, [], '[data-testid="fts-funnel-workspace"]', { settle: 500 });

    // symbol dossier switches (plan response is the true data dependency)
    const switches = [];
    for (const sym of symbols.slice(0, 2)) {
      await backToFunnel(page);
      const enc = encodeURIComponent(sym);
      const d = await scenario(page, 'switch-' + sym, async () => {
        await page.evaluate((s) => { location.hash = '#/master/' + s; }, sym);
      }, ['/api/fts/' + sym, '/api/chart/' + sym + '/key-levels'],
        '[data-testid="master-dossier"]', { settle: 400, apiTimeout: 15000 });
      d.symbol = sym;
      switches.push(d);
    }

    // same-symbol reopen after returning to the funnel
    const sym0 = symbols[0];
    await backToFunnel(page);
    const reopen = await scenario(page, 'reopen-' + sym0, async () => {
      await page.evaluate((s) => { location.hash = '#/master/' + s; }, sym0);
    }, [], '[data-testid="master-dossier"]', { settle: 400, apiTimeout: 2000 });
    reopen.symbol = sym0;

    // strategy tree
    const tree = await scenario(page, 'strategy-tree', async () => {
      await page.evaluate(() => { location.hash = '#/strategy-tree'; });
    }, [], '[data-testid="strategy-tree-workspace"]', { settle: 700 });
    const treePages = {};
    for (const zone of ['S', 'T', 'F', 'M', 'master']) {
      await resetPerf(page);
      const since = await countResources(page);
      const tt = Date.now();
      await page.evaluate((z) => { document.querySelector(`[data-testid="tree-page-${z}"]`)?.click(); }, zone);
      await page.waitForTimeout(650);
      treePages[zone] = { ms: Date.now() - tt, ...(await collect(page, since)) };
    }

    // technical chart open + one symbol switch (read-only)
    const tech = await scenario(page, 'technical-open', async () => {
      await page.evaluate((s) => { location.hash = '#/technical/' + encodeURIComponent(s); }, sym0);
    }, ['/api/chart/' + sym0], '[data-testid="chart-area"]', { settle: 900 });
    const techSwitch = await scenario(page, 'technical-switch', async () => {
      await page.evaluate((s) => { location.hash = '#/technical/' + encodeURIComponent(s); }, symbols[1] || sym0);
    }, ['/api/chart/' + (symbols[1] || sym0), '/api/patterns/' + (symbols[1] || sym0)], '[data-testid="chart-area"]', { settle: 1200, apiTimeout: 4000 });
    techSwitch.symbol = symbols[1] || sym0;

    // repeated dossier open/close
    const cycles = [];
    for (let i = 0; i < 5; i++) {
      await backToFunnel(page);
      const d = await scenario(page, 'cycle-' + i, async () => {
        await page.evaluate((s) => { location.hash = '#/master/' + s; }, sym0);
      }, [], '[data-testid="master-dossier"]', { settle: 250, apiTimeout: 2000 });
      cycles.push(d);
    }

    await client.send('HeapProfiler.collectGarbage');
    await page.waitForTimeout(300);
    const m = Object.fromEntries((await client.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
    const dom = await client.send('Memory.getDOMCounters').catch(() => null);
    report.runs.push({
      run, loginGate, symbols, cold, warm, switches, reopen, tree, treePages,
      tech, techSwitch, cycles, errors,
      end: { heapMB: m.JSHeapUsedSize ? Math.round(m.JSHeapUsedSize / 1e5) / 10 : null,
             nodes: m.Nodes ?? dom?.nodes ?? null,
             listeners: m.JSEventListeners ?? dom?.jsEventListeners ?? null },
    });
    console.log(`run ${run}: cold=${cold.readyMs} warm=${warm.readyMs} ` +
      `switch=${switches.map((x) => `${x.symbol}:${x.readyMs}`).join(',')} reopen=${reopen.readyMs} ` +
      `tree=${tree.readyMs} tech=${tech.readyMs} techSwitch=${techSwitch.readyMs} cycles=${cycles.map((x) => x.readyMs).join('/')}`);
    await ctx.close();
  }
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(report, null, 1));
  console.log('wrote', OUT);
  await browser.close();
})().catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
