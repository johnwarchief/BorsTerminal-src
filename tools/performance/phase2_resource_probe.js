// P2-R5 resource probe: CPU (CDP TaskDuration/ScriptDuration), JS heap, DOM
// nodes and event listeners across the real FTS/technical workflows.
// GC is forced before heap readings so numbers are comparable, not "one lucky
// sample". Requests are counted per phase at request-start.
const path = require('path'), fs = require('fs'), http = require('http');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const argv = process.argv.slice(2); const arg = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
const OUT = path.resolve(REPO, arg('--out', 'artifacts/performance/phase2/resources.json'));
const FUNNEL = '#/master?preset=tech_first&stage=technical';

// The first /api/fts call for a symbol can take 25-41s; warm the symbols used by
// the repeated-open cycles so the phase measures the client, not a cold server.
function warm(sym) {
  return new Promise((res) => {
    const t = Date.now();
    const r = http.get(BASE + '/api/fts/' + encodeURIComponent(sym), (x) => {
      x.resume();
      x.on('end', () => res(Date.now() - t));
    });
    r.on('error', () => res(null));
  });
}

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

async function openFunnel(p) {
  await p.evaluate((h) => { location.hash = h; }, FUNNEL);
  await p.waitForFunction(() => document.querySelectorAll('[data-fkey]').length > 0, null, { timeout: 45000 });
  await p.waitForTimeout(400);
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const p = await ctx.newPage();
  const cdp = await ctx.newCDPSession(p);
  await cdp.send('Performance.enable');
  await cdp.send('HeapProfiler.enable');

  const reqs = [];
  p.on('request', (r) => {
    const u = decodeURIComponent(r.url()).replace(/^https?:\/\/[^/]+/, '');
    if (u.includes('/api/')) reqs.push({ u: u.split('?')[0], at: Date.now() });
  });

  async function snap(gc = true) {
    if (gc) await cdp.send('HeapProfiler.collectGarbage');
    const m = (await cdp.send('Performance.getMetrics')).metrics;
    const o = {}; for (const x of m) o[x.name] = x.value;
    const dom = await cdp.send('Memory.getDOMCounters');
    return {
      t: Date.now(),
      task: o.TaskDuration, script: o.ScriptDuration,
      layout: o.LayoutDuration, style: o.RecalcStyleDuration,
      heap: o.JSHeapUsedSize, heapTotal: o.JSHeapTotalSize,
      nodes: dom.nodes, listeners: dom.jsEventListeners, documents: dom.documents,
    };
  }
  const d = (a, b) => ({
    wallMs: b.t - a.t,
    cpuMs: Math.round((b.task - a.task) * 1000),
    scriptMs: Math.round((b.script - a.script) * 1000),
    layoutMs: Math.round((b.layout - a.layout) * 1000),
    styleMs: Math.round((b.style - a.style) * 1000),
    heapDeltaKB: Math.round((b.heap - a.heap) / 1024),
    nodesDelta: b.nodes - a.nodes,
    listenersDelta: b.listeners - a.listeners,
    heapKB: Math.round(b.heap / 1024),
    nodes: b.nodes,
    listeners: b.listeners,
    documents: b.documents,
  });

  const report = { base: BASE, route: FUNNEL, phases: {}, cycles: [], technical: [], toggles: null, idleLong: null };
  await p.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(800);
  await login(p);
  await openFunnel(p);
  const syms = await p.evaluate(() => [...document.querySelectorAll('[data-fkey]')].slice(0, 6).map((e) => e.getAttribute('data-fkey')));
  const cycleSyms = [syms[0], syms[1], syms[2], syms[4], syms[5], syms[0]];
  for (const s of [...new Set(cycleSyms)]) await warm(s);
  await p.waitForTimeout(500);

  // A) funnel idle, 10s
  let s0 = await snap();
  const idleReq0 = reqs.length;
  await p.waitForTimeout(10_000);
  let s1 = await snap();
  report.phases.funnelIdle10s = { ...d(s0, s1), requests: reqs.slice(idleReq0).map((r) => r.u) };

  // B) repeated FTS open/close (dossier) — 6 cycles on distinct symbols
  for (let i = 0; i < cycleSyms.length; i++) {
    const sym = cycleSyms[i];
    const a = await snap();
    const req0 = reqs.length;
    const t = Date.now();
    await p.evaluate((s) => document.querySelector(`[data-fkey="${CSS.escape(s)}"] button`)?.click(), sym);
    await p.waitForFunction((s) => decodeURIComponent(location.hash).includes(s), sym, { timeout: 15000 });
    await p.waitForFunction((s) => performance.getEntriesByType('resource').some(
      (r) => decodeURIComponent(r.name).includes('/api/fts/' + s) && r.responseEnd > 0), sym, { timeout: 60000 });
    await p.waitForTimeout(300);
    const openMs = Date.now() - t;
    // The app occasionally re-sets the stored symbol from a stale route right
    // after "back" (observed race in WorkspaceTabs/SymbolInspector). Retry the
    // gesture; record how many attempts were needed instead of hiding it.
    let backRetries = 0, backDone = false;
    while (backRetries < 3 && !backDone) {
      const backVia = await p.evaluate(() => {
        const b = document.querySelector('[data-testid="master-open-funnel"]');
        if (b) { b.click(); return 'open-funnel'; }
        const m = document.querySelector('[data-testid="master-back"]');
        if (m) { m.click(); return 'back'; }
        return null;
      });
      backDone = await p.waitForFunction(() => !!document.querySelector('[data-testid="fts-funnel-workspace"]'), null, { timeout: 8000 })
        .then(() => true).catch(() => false);
      if (!backDone) { backRetries++; await p.waitForTimeout(400); }
    }
    if (!backDone) {
      const diag = await p.evaluate(() => ({
        hash: decodeURIComponent(location.hash),
        stored: localStorage.getItem('bors-symbol'),
        workspace: !!document.querySelector('[data-testid="fts-funnel-workspace"]'),
        dossier: !!document.querySelector('[data-testid="master-dossier"]'),
        fkeys: document.querySelectorAll('[data-fkey]').length,
      }));
      console.log('back diag cycle', i + 1, sym, JSON.stringify(diag));
      throw new Error('could not return to funnel');
    }
    const rowsOk = await p.waitForFunction(() => document.querySelectorAll('[data-fkey]').length > 0, null, { timeout: 20000 })
      .then(() => true).catch(() => false);
    if (!rowsOk) {
      const diag = await p.evaluate(() => ({
        hash: decodeURIComponent(location.hash),
        stored: localStorage.getItem('bors-symbol'),
        workspace: !!document.querySelector('[data-testid="fts-funnel-workspace"]'),
        stage: document.querySelector('[data-testid^="fts-stage-"]')?.getAttribute('data-testid'),
        empty: document.querySelector('[data-testid^="funnel-empty-"]')?.textContent?.slice(0, 160),
        computing: document.querySelector('[data-testid="funnel-computing"]')?.textContent,
        text: document.body.innerText.slice(0, 160),
      }));
      console.log('rows diag cycle', i + 1, sym, JSON.stringify(diag));
      await p.evaluate((h) => { location.hash = h; }, FUNNEL);
      await p.waitForFunction(() => document.querySelectorAll('[data-fkey]').length > 0, null, { timeout: 30000 });
    }
    await p.waitForTimeout(150);
    const b = await snap();
    report.cycles.push({ cycle: i + 1, symbol: sym, openMs, backRetries, ...d(a, b), requests: reqs.slice(req0).map((r) => r.u) });
  }

  // C) technical chart open/back — 3 cycles (Coder2-owned, read-only interaction)
  for (let i = 0; i < 3; i++) {
    const sym = syms[i];
    const a = await snap();
    const req0 = reqs.length;
    const t = Date.now();
    await p.evaluate((s) => { location.hash = '#/technical/' + encodeURIComponent(s); }, sym);
    await p.waitForFunction(() => !!document.querySelector('[data-testid="chart-area"]'), null, { timeout: 30000 });
    await p.waitForTimeout(2500);
    const openMs = Date.now() - t;
    const b = await snap();
    // pattern toggles, if the panel is present
    const toggles = await p.evaluate(() => [...document.querySelectorAll('[data-testid^="pattern-toggle-"]')].map((e) => e.getAttribute('data-testid')));
    if (i === 0 && toggles.length) {
      const tA = await snap();
      for (let round = 0; round < 2; round++) {
        for (const id of toggles) {
          await p.evaluate((id) => document.querySelector(`[data-testid="${id}"]`)?.click(), id);
          await p.waitForTimeout(120);
        }
      }
      await p.waitForTimeout(500);
      const tB = await snap();
      report.toggles = { count: toggles.length, rounds: 2, ...d(tA, tB) };
    }
    await openFunnel(p);
    await p.waitForTimeout(400);
    const c = await snap();
    report.technical.push({ cycle: i + 1, symbol: sym, openMs, ...d(a, c), requests: reqs.slice(req0).map((r) => r.u) });
  }

  // D) sustained funnel idle, 60s
  const l0 = await snap();
  const lr = reqs.length;
  await p.waitForTimeout(60_000);
  const l1 = await snap();
  report.idleLong = { ...d(l0, l1), requests: reqs.slice(lr).map((r) => r.u) };

  // E) final sustained sample after all cycles
  const fr = reqs.length;
  const f0 = await snap();
  await p.waitForTimeout(5_000);
  const f1 = await snap();
  report.phases.finalIdle5s = { ...d(f0, f1), requests: reqs.slice(fr).map((r) => r.u) };

  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(report, null, 1));
  const pick = (x) => x && { wall: x.wallMs, cpu: x.cpuMs, script: x.scriptMs, heapKB: x.heapKB, heapDeltaKB: x.heapDeltaKB, nodes: x.nodes, nodesDelta: x.nodesDelta, listeners: x.listeners, listenersDelta: x.listenersDelta };
  console.log('idle10s', pick(report.phases.funnelIdle10s), 'reqs', report.phases.funnelIdle10s.requests);
  for (const c of report.cycles) console.log('cycle', c.cycle, c.symbol, 'open', c.openMs, 'ms', pick(c), 'reqs', c.requests.length, c.requests.join(','));
  for (const t of report.technical) console.log('tech', t.cycle, t.symbol, 'open', t.openMs, 'ms', pick(t), 'reqs', t.requests.join(','));
  if (report.toggles) console.log('toggles', pick(report.toggles));
  console.log('idle60s', pick(report.idleLong), 'reqs', report.idleLong.requests);
  console.log('wrote', OUT);
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
