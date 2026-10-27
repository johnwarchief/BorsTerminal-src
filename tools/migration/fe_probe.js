// tools/migration/fe_probe.js — frontend baseline in a REAL browser
//
// Copied from tag v1.0.95:_audit/perf/fe_probe.js (PERFF Stage 1.1) for the
// desktop-migration baseline. Changes vs the original: BORS_VIEWPORT selects the
// context viewport (needed for 1366/1920/2560) and the viewport is recorded in
// the report. It still only READS; it never writes user data.
//
// Why jsdom is not enough (owner rule: «نتیجه‌ای را که درِ مرورگر یا تست واقعاً
// مشاهده نکرده‌ای تأییدشده معرفی نکن»): long tasks, paint timing, real gzip
// transfer sizes, JS heap growth and duplicate-request fan-out only exist in an
// actual Chromium.
//
// What it measures, per phase: click→ready latency, long tasks (count/TBT/worst
// stall), the exact request list the UI issued in that window (count, duration,
// encoded vs transfer bytes), and heap growth across tab cycles.
//
// usage:
//   cd BorsTerminal-src
//   BORS_UI_BASE=http://127.0.0.1:8140 BORS_VIEWPORT=1920x1080 node tools/migration/fe_probe.js --out MIG_BASE_1920.json
const os = require('os');
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..' , '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));

const VW = Number((process.env.BORS_VIEWPORT || '1366x768').split('x')[0]) || 1366;
const VH = Number((process.env.BORS_VIEWPORT || '1366x768').split('x')[1]) || 768;
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const LABEL = process.env.BORS_LABEL || `dev-8000-${VW}x${VH}`;
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const PROFILE = path.join(os.tmpdir(), `bors-perf-profile-${VW}x${VH}`);
// Shell mode: attach to an already-running desktop shell (Tauri/WebView2) over
// CDP instead of launching Edge. The viewport is then applied with CDP
// emulation, because the window itself belongs to the shell.
const CDP = process.env.BORS_CDP || '';
const SHOT = process.env.BORS_SHOT || '';
const argv = process.argv.slice(2);
const OUT = path.join(REPO, '_audit', 'perf', argv.includes('--out') ? path.basename(argv[argv.indexOf('--out') + 1]) : `FE_BASELINE_${VW}x${VH}.json`);
const RUNS = Number(process.env.BORS_RUNS || 3);          // repetitions per scenario
const DEADLINE = Number(process.env.BORS_DEADLINE_MS || 120000);

const report = {
  base: BASE, label: LABEL, viewport: { width: VW, height: VH },
  ranAt: new Date().toISOString(), runs: RUNS,
  mode: CDP ? 'shell-cdp' : 'launched-edge', cdp: CDP || null,
  marketState: null, phases: {}, notes: [], consoleErrors: [], netErrors: [],
};
const note = (m) => { report.notes.push(m); console.log('·  ' + m); };

// The collector installed before any app code runs. Everything lands on
// window.__perf so a single evaluate() can drain it per phase.
const INIT = () => {
  const p = { longtasks: [], events: [], heap: [], marks: {}, resCursor: 0 };
  window.__perf = p;
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) p.longtasks.push({ t: Math.round(e.startTime), d: Math.round(e.duration) });
    }).observe({ type: 'longtask', buffered: true });
  } catch (e) { p.noLongtask = String(e); }
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) {
        if (e.duration < 8) continue;
        p.events.push({ name: e.name, t: Math.round(e.startTime), d: Math.round(e.duration),
                        proc: Math.round(e.processingStart - e.startTime),
                        delay: Math.round(e.processingStart - e.startTime) });
      }
    }).observe({ type: 'event', buffered: true });
  } catch (e) { p.noEvent = String(e); }
  const sample = () => {
    if (performance.memory) p.heap.push({ t: Math.round(performance.now()), used: performance.memory.usedJSHeapSize });
    p.domNodes = document.getElementsByTagName('*').length;
  };
  setInterval(sample, 1000);
  addEventListener('DOMContentLoaded', sample);
  addEventListener('load', sample);
  // frame cadence — stutter during zoom/pan/scroll shows up here, not in paint
  p.frames = [];
  let last = 0;
  const tick = (t) => {
    if (last) { p.frames.push(Math.round(t - last)); if (p.frames.length > 4000) p.frames.splice(0, 500); }
    last = t;
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  // content-settle detector: the app is "ready" when the route changed, no
  // *-loading element is left, and the DOM has been quiet for ~700ms
  p.lastMut = 0;
  const mark = () => { p.lastMut = performance.now(); };
  const start = () => {
    try {
      new MutationObserver(mark).observe(document.body, { subtree: true, childList: true, characterData: true });
    } catch (e) { p.noMut = String(e); }
  };
  if (document.body) start(); else addEventListener('DOMContentLoaded', start);
};

// Drain everything collected since the last drain and reduce it.
const DRAIN = (sinceIdx) => {
  const p = window.__perf || (window.__perf = { longtasks: [], events: [], heap: [], frames: [], domNodes: 0 });
  const nav = performance.getEntriesByType('navigation')[0] || {};
  const paint = performance.getEntriesByType('paint');
  const fcp = (paint.find((x) => x.name === 'first-contentful-paint') || {}).startTime;
  const fp = (paint.find((x) => x.name === 'first-paint') || {}).startTime;
  const res = performance.getEntriesByType('resource').slice(sinceIdx ?? 0);
  const api = res.filter((r) => r.name.includes('/api/'));
  const byUrl = {};
  for (const r of api) {
    const u = r.name.replace(/^https?:\/\/[^/]+/, '').split('?')[0];
    const q = r.name.includes('?') ? r.name.slice(r.name.indexOf('?')) : '';
    const k = u + (q.length > 40 ? q.slice(0, 40) : q);
    const b = byUrl[k] || (byUrl[k] = { n: 0, ms: 0, maxMs: 0, encoded: 0, transfer: 0 });
    b.n += 1; b.ms += r.duration; b.maxMs = Math.max(b.maxMs, r.duration);
    b.encoded += r.encodedBodySize || 0; b.transfer += r.transferSize || 0;
  }
  const lt = p.longtasks;
  const tbt = lt.reduce((a, x) => a + Math.max(0, x.d - 50), 0);
  const fr = (p.frames || []).slice();
  fr.sort((a, b) => a - b);
  const frames = {
    n: fr.length,
    med: fr.length ? fr[Math.floor(fr.length / 2)] : 0,
    p95: fr.length ? fr[Math.floor(fr.length * 0.95)] : 0,
    max: fr.length ? fr[fr.length - 1] : 0,
    over32: fr.filter((x) => x > 32).length,
    over100: fr.filter((x) => x > 100).length,
  };
  const heap = p.heap.length ? p.heap[p.heap.length - 1].used : 0;
  const out = {
    firstPaint: fp, firstContentfulPaint: fcp,
    domContentLoaded: nav.domContentLoadedEventEnd, loadEnd: nav.loadEventEnd,
    ttfb: nav.responseStart,
    longtasks: lt.length, tbt, worst: lt.reduce((a, x) => Math.max(a, x.d), 0),
    longtaskList: lt.slice(-40),
    frames,
    inputEvents: p.events.slice(-40),
    requests: Object.entries(byUrl)
      .map(([k, v]) => ({ url: k, n: v.n, avgMs: Math.round(v.ms / v.n), maxMs: Math.round(v.maxMs),
                          encoded: v.encoded, transfer: v.transfer }))
      .sort((a, b) => (b.encoded + b.transfer) - (a.encoded + a.transfer)),
    requestTotal: api.length,
    apiBytesEncoded: api.reduce((a, r) => a + (r.encodedBodySize || 0), 0),
    apiBytesTransfer: api.reduce((a, r) => a + (r.transferSize || 0), 0),
    heapMB: Math.round(heap / 1e6 * 10) / 10,
    domNodes: p.domNodes || 0,
  };
  p.longtasks = []; p.events = []; p.frames = [];
  return { ...out, resIndexAfter: performance.getEntriesByType('resource').length };
};

async function drain(page, since) {
  return page.evaluate(`(() => { const r = (${DRAIN.toString()})(${since === undefined ? 'undefined' : since}); return r; })()`);
}

async function loginIfNeeded(page) {
  const gate = await page.evaluate(() => !!document.querySelector('input[type="password"]'));
  if (!gate) return note('قفلِ ایستگاه دیده نشد — نیازی به ورود نبود');
  const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
  const du = (src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
  const dp = (src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
  if (!du || !dp) throw new Error('پیش‌فرضِ سورس درِ authStore پیدا نشد');
  await page.locator('input[type="text"]').first().fill(du);
  await page.locator('input[type="password"]').first().fill(dp);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(4000);
  note('ورود انجام شد تا مسیرِ واقعیِ کاربر سنجیده شود (هیچ دادهٔ کاربری نوشته نشد)');
}

// Per-route readiness. `marker` is a testid the app only renders once that page
// has REAL rows (read from source, not guessed):
//   tape-row / treemap-cell-* / chart-area canvas / fts-screen-row
const ROUTES = [
  { route: '/market', label: 'تابلوخوانی', marker: '[data-testid="tape-row"]', min: 10 },
  { route: '/market-status', label: 'وضعیت بازار', marker: '[data-testid^="treemap-cell-"]', min: 1 },
  { route: '/technical', label: 'تکنیکال', marker: '[data-testid="chart-area"]', min: 1 },
  { route: '/fundamental', label: 'بنیادی', marker: '[data-testid="fts-screen-row"]', min: 5 },
  // v1.0.98 opens the master workspace on a symbol dossier, so accept either
  // marker as "master drawn" (the funnel element only mounts in the funnel view).
  { route: '/master', label: 'استراتژی FTS', marker: '[data-testid="fts-funnel-workspace"], [data-testid="master-dossier"]', min: 1 },
];
const ROUTE_BY_NAME = {};
for (const r of ROUTES) ROUTE_BY_NAME[r.route.slice(1)] = r;

function routeFromHash(hash) {
  const h = String(hash || '').replace(/^#\/?/, '').split('/')[0];
  return ROUTE_BY_NAME[h] || ROUTES[0];
}

// ready = on the target route + nothing is *-loading + the marker has enough
// nodes + the DOM has been quiet for 700ms (content actually settled)
const READY_FN = (route, marker, min) => `(() => {
  if (!location.hash.startsWith('#${route}')) return false;
  if (document.querySelectorAll('[data-testid$="-loading"]').length > 0) return false;
  if (document.querySelectorAll('${marker}').length < ${min}) return false;
  const lm = (window.__perf && window.__perf.lastMut) || 0;
  return lm > 0 && (performance.now() - lm) > 700;
})()`;

async function measureCold(page, run) {
  // sessionStorage holds the session BY DESIGN (the app asks for the password
  // on every program start), so a cold start is measured in the SAME tab — a new
  // tab would measure the login screen instead of the app.
  const t0 = Date.now();
  // goto (not reload): a reload keeps the hash and re-measures the tab we last
  // visited instead of the program's own landing route.
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  const gate = await page.evaluate(() => !!document.querySelector('input[type="password"]'));
  if (gate) { await loginIfNeeded(page); }
  const hash = await page.evaluate(() => location.hash);
  const rt = routeFromHash(hash);
  let readyMs = null;
  try {
    await page.waitForFunction(READY_FN(rt.route, rt.marker, rt.min), undefined, { timeout: DEADLINE });
    readyMs = Date.now() - t0;
  } catch (e) {
    note(`cold run ${run}: «دادهٔ قابل‌استفاده» تا ${DEADLINE}ms نرسید (route=${rt.route})`);
  }
  const d = await drain(page);
  d.readyMs = readyMs;
  d.loginGate = gate;
  d.landingHash = hash;
  d.landingRoute = rt.route;
  d.wallFromGoto = Date.now() - t0;
  return d;
}

async function clickTab(page, route, label) {
  // Only the main sidebar is navigation. In 1.0.95 a bare aside/a[href$=...]
  // also matched an inspector-stage link and clicked the wrong element.
  const nav = page.locator(`aside[aria-label="نوار کناری"] a[href$="${route}"]`).first();
  if (await nav.count()) {
    try {
      await nav.click({ timeout: 15000 });
      return true;
    } catch (e) {
      note(`کلیک «${label}» از سایدبار نشد؛ هش‌روت جایگزین شد (${String(e).slice(0, 80)})`);
    }
  }
  try {
    await page.evaluate((r) => { location.hash = '#' + r; }, route);
    return true;
  } catch {
    return false;
  }
}

async function measureTabCycle(page) {
  const out = [];
  for (let pass = 0; pass < RUNS; pass++) {
    for (const rt of ROUTES) {
      const since = await page.evaluate(() => performance.getEntriesByType('resource').length);
      const t0 = Date.now();
      if (!(await clickTab(page, rt.route, rt.label))) { note(`تب «${rt.label}» درِ ناوبری پیدا نشد`); continue; }
      let ready = null;
      try {
        await page.waitForFunction(READY_FN(rt.route, rt.marker, rt.min), undefined, { timeout: DEADLINE });
        ready = Date.now() - t0;
      } catch (e) {
        await page.waitForTimeout(5000);
        ready = Date.now() - t0;
        note(`تب «${rt.label}»: آمادگی (route=${rt.route} marker=${rt.marker}≥${rt.min} + settle) نرسید؛ پنجرۀ ۵s جای آن`);
      }
      const d = await drain(page, since);
      d.clickToReady = ready;
      d.tab = rt.label; d.route = rt.route; d.pass = pass;
      d.hash = await page.evaluate(() => location.hash);
      out.push(d);
      console.log(`  [${LABEL}] tab ${rt.label.padEnd(14)} pass${pass}  click→ready=${String(ready).padStart(6)}ms  `
        + `longtasks=${d.longtasks} tbt=${d.tbt} worst=${d.worst} frames>100=${d.frames.over100} `
        + `req=${d.requestTotal} enc=${Math.round(d.apiBytesEncoded / 1024)}KiB  heap=${d.heapMB}MB dom=${d.domNodes}`);
    }
  }
  return out;
}

async function measureChart(ctx, page) {
  if (!(await clickTab(page, '/technical', 'تکنیکال'))) { note('تب تکنیکال پیدا نشد'); return null; }
  await page.waitForFunction(() => document.querySelectorAll('canvas').length >= 1, undefined,
                             { timeout: DEADLINE }).catch(() => note('چارت: canvas اولیه ظاهر نشد'));
  await page.waitForTimeout(2500);

  // نمادها از خودِ برنامه، از مسیرِ سبکِ «نمادهای زیرِ نظر» (نه فهرست دست‌نویس)
  const symbols = await page.evaluate(async () => {
    try {
      const j = await (await fetch('/api/mstat/mainwatch?group=eq_all&industry=')).json();
      return (j.rows || []).slice(0, 5).map((r) => r.symbol).filter(Boolean);
    } catch (e) { return []; }
  });
  if (!symbols.length) { note('چارت: هیچ نمادی از /api/mstat/mainwatch نرسید'); return null; }

  const res = [];
  for (const sym of symbols) {
    const since = await page.evaluate(() => performance.getEntriesByType('resource').length);
    const t0 = Date.now();
    await page.evaluate((s) => { location.hash = '#/technical/' + encodeURIComponent(s); }, sym);
    // «تاریخچه رسید» = پایانِ درخواستِ /api/chart/<sym> برای همین نماد
    let histMs = null;
    try {
      await page.waitForFunction((s) => performance.getEntriesByType('resource')
        .some((r) => decodeURIComponent(r.name).includes('/api/chart/' + s) && r.responseEnd > 0),
        sym, { timeout: DEADLINE });
      histMs = Date.now() - t0;
    } catch (e) { note(`چارت: درخواستِ تاریخچۀ ${sym} دیده نشد`); }
    await page.waitForTimeout(2000);                      // settle: series + indicators
    const d = await drain(page, since);
    d.symbol = sym; d.historyMs = histMs;
    d.chartRequests = d.requests.filter((r) => /\/api\/chart/.test(r.url));
    res.push(d);
    console.log(`  [${LABEL}] symbol ${String(sym).padEnd(9)} history=${String(histMs).padStart(6)}ms  `
      + `longtasks=${d.longtasks} tbt=${d.tbt} worst=${d.worst} frames>100ms=${d.frames.over100} `
      + `req=${d.requestTotal} heap=${d.heapMB}MB`);
  }

  const canvas = page.locator('canvas').first();
  const box = await canvas.boundingBox().catch(() => null);
  if (!box) return { symbols: res, interaction: null };
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.evaluate(() => { window.__perf.frames = []; });
  const t0 = Date.now();
  for (let i = 0; i < 12; i++) await page.mouse.wheel(0, i % 2 ? -120 : 120);
  const wheelMs = Date.now() - t0;
  let dWheel = await drain(page);
  dWheel.label = 'wheel-zoom';
  await page.evaluate(() => { window.__perf.frames = []; window.__perf.longtasks = []; });
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  const t1 = Date.now();
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 240, box.y + box.height / 2 + 40, { steps: 14 });
  await page.mouse.up();
  const panMs = Date.now() - t1;
  await page.waitForTimeout(800);
  let dPan = await drain(page);
  dPan.label = 'drag-pan';
  console.log(`  [${LABEL}] zoom 12×wheel: ${wheelMs}ms longtasks=${dWheel.longtasks} worst=${dWheel.worst} `
    + `frames med/p95/max=${dWheel.frames.med}/${dWheel.frames.p95}/${dWheel.frames.max} >100ms=${dWheel.frames.over100}`);
  console.log(`  [${LABEL}] drag-pan    : ${panMs}ms longtasks=${dPan.longtasks} worst=${dPan.worst} `
    + `frames med/p95/max=${dPan.frames.med}/${dPan.frames.p95}/${dPan.frames.max} >100ms=${dPan.frames.over100}`);
  return { symbols: res, zoom: dWheel, pan: dPan, wheelMs, panMs };
}

async function main() {
  let browser, ctx, p;
  if (CDP) {
    browser = await chromium.connectOverCDP(CDP);
    ctx = browser.contexts()[0] || (await browser.newContext());
    p = ctx.pages()[0] || (await ctx.newPage());
    const session = await ctx.newCDPSession(p);
    await session.send('Emulation.setDeviceMetricsOverride', {
      width: VW, height: VH, deviceScaleFactor: 1, mobile: false,
    });
    await p.addInitScript(INIT);
    note(`پوستۀ دسکتاپ از طریق CDP وصل شد (${CDP})؛ ویوپورت ${VW}x${VH} با emulation اعمال شد`);
  } else {
    browser = await chromium.launch({
      executablePath: EXE,
      args: ['--no-first-run', '--disable-sync', '--enable-precise-memory-info',
             '--disable-features=Translate', '--remote-debugging-port=0'],
    });
    ctx = await browser.newContext({ viewport: { width: VW, height: VH }, storageState: undefined });
    p = await ctx.newPage();
    await p.addInitScript(INIT);
  }

  // market state + one page for the whole run (session lives in sessionStorage,
  // so the tab must survive — see measureCold)
  {
    p.on('console', (m) => { if (m.type() === 'error') report.consoleErrors.push(m.text().slice(0, 200)); });
    p.on('pageerror', (e) => report.consoleErrors.push('pageerror: ' + String(e).slice(0, 200)));
    p.on('response', (r) => { if (r.status() >= 400) report.netErrors.push(`HTTP ${r.status()} ${r.url().slice(0, 140)}`); });
    await p.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
    await p.waitForTimeout(1500);
    await loginIfNeeded(p);
    report.marketState = await p.evaluate(async () => {
      const out = {};
      for (const u of ['/api/market/sync-state', '/api/live-stats']) {
        try { out[u] = await (await fetch(u)).json(); } catch (e) { out[u] = 'err ' + e; }
      }
      out.__hash = location.hash;
      return out;
    });
    await p.waitForTimeout(500);
    report.phaseLogin = await drain(p);

    report.phases.cold = [];
    for (let i = 0; i < RUNS; i++) {
      const d = await measureCold(p, i + 1);
      report.phases.cold.push(d);
      console.log(`  [${LABEL}] cold #${i + 1}: FP=${Math.round(d.firstPaint || 0)}ms FCP=${Math.round(d.firstContentfulPaint || 0)}ms `
        + `firstUseful=${d.readyMs}ms longtasks=${d.longtasks} tbt=${d.tbt} worst=${d.worst}ms `
        + `req=${d.requestTotal} enc=${Math.round(d.apiBytesEncoded / 1024)}KiB gz=${Math.round(d.apiBytesTransfer / 1024)}KiB heap=${d.heapMB}MB `
        + `landing=${d.landingHash}`);
    }

    report.phases.tabs = await measureTabCycle(p);
    try {
      report.phases.chart = await measureChart(ctx, p);
    } catch (e) {
      report.phases.chart = { error: String(e).slice(0, 400) };
      note(`فاز چارت کامل نشد: ${String(e).slice(0, 120)}`);
    }

    // heavy session: market-status open with all panels, then scroll it
    const since = await p.evaluate(() => performance.getEntriesByType('resource').length);
    const t0 = Date.now();
    if (await clickTab(p, '/market-status', 'وضعیت بازار')) {
      const ms = ROUTES.find((r) => r.route === '/market-status');
      await p.waitForFunction(READY_FN(ms.route, ms.marker, ms.min), undefined, { timeout: DEADLINE }).catch(() => {
        note('سناریوی سنگین: آمادگیِ تب وضعیت بازار نرسید');
      });
      const openMs = Date.now() - t0;
      await p.waitForTimeout(3000);
      const t1 = Date.now();
      for (let i = 0; i < 12; i++) await p.mouse.wheel(0, 600);
      const scrollMs = Date.now() - t1;
      const d = await drain(p, since);
      d.openMs = openMs; d.scrollMs = scrollMs;
      report.phases.heavy = d;
      console.log(`  [${LABEL}] heavy: status-tab open=${openMs}ms scroll(12×600px)=${scrollMs}ms `
        + `longtasks=${d.longtasks} tbt=${d.tbt} worst=${d.worst} frames>100=${d.frames.over100} `
        + `req=${d.requestTotal} heap=${d.heapMB}MB dom=${d.domNodes}`);
    } else note('تب وضعیت بازار برای سناریوی سنگین پیدا نشد');
    report.heapEnd = await p.evaluate(() => (performance.memory ? performance.memory.usedJSHeapSize : 0));
    report.allRequests = await p.evaluate(() => performance.getEntriesByType('resource')
      .filter((r) => r.name.includes('/api/'))
      .map((r) => ({ u: decodeURIComponent(r.name).replace(/^https?:\/\/[^/]+/, ''),
                     ms: Math.round(r.duration), enc: r.encodedBodySize, tr: r.transferSize })));
    if (SHOT) {
      try {
        await clickTab(p, '/market', 'تابلوخوانی');
        await p.waitForTimeout(3000);
        await p.screenshot({ path: path.join(REPO, '_audit', 'perf', path.basename(SHOT)) });
        note(`اسکرین‌شات ذخیره شد: ${SHOT}`);
      } catch (e) { note(`اسکرین‌شات گرفته نشد: ${String(e).slice(0, 120)}`); }
    }
    if (!CDP) await p.close();   // closing the shell's page would close its window
  }

  const heapTrace = report.phases.cold.map((c) => c.heapMB);
  report.summary = {
    cold: (report.phases.cold || []).map((c) => ({
      fcp: c.firstContentfulPaint, ready: c.readyMs, tbt: c.tbt, worst: c.worst,
      requests: c.requestTotal, encodedKB: Math.round(c.apiBytesEncoded / 1024), heapMB: c.heapMB,
    })),
    heapTraceMB: heapTrace,
    consoleErrors: report.consoleErrors.length,
    netErrors: report.netErrors.length,
  };
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(report, null, 1));
  console.log(`\nwrote ${OUT}`);
  console.log('console errors:', report.consoleErrors.slice(0, 8));
  console.log('net errors    :', report.netErrors.slice(0, 8));
  await browser.close();
  return 0;
}

main().then((rc) => process.exit(rc)).catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
