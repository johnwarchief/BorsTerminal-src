// P2-R4: same-symbol A/B on the FTS funnel — direct row click vs deliberate
// hover (>=300ms debounce) then click. Each measurement runs in a fresh browser
// context so the TanStack cache is empty and both modes start client-cold.
// The server is warmed once per symbol so both modes see the same backend state.
//
// Reported per measurement:
//   readyMs            click -> dossier rendered with the symbol's /api/fts result
//   clickToFtsEndMs    click -> the symbol's /api/fts response finished
//   ftsMs              /api/fts request duration (server + transfer)
//   prefetchLeadMs     how long the request ran before the click (0 = direct)
// A/B pairs use the same symbol and alternate which mode runs first, so server
// warmth (if any) is balanced across modes.
const path = require('path'), fs = require('fs'), http = require('http');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const argv = process.argv.slice(2); const arg = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
const RUNS = Number(arg('--runs', '2'));
const DWELL = Number(arg('--dwell', '650'));
const OUT = path.resolve(REPO, arg('--out', 'artifacts/performance/phase2/hover.json'));

/** Server-side warm-up: the first /api/fts call for a symbol can cost tens of
 * seconds (آرامش 37.9s, آس 40.6s on this dataset); later calls ~0.7–1.2s.
 * Both A/B modes must see the same server state, so each symbol is warmed once
 * before measuring. Both modes still start with an empty client query cache. */
function hit(url) {
  return new Promise((res) => {
    const t = Date.now();
    const req = http.get(url, (r) => {
      r.resume();
      r.on('end', () => res({ ms: Date.now() - t, code: r.statusCode }));
    });
    req.on('error', (e) => res({ ms: null, err: e.message }));
  });
}
async function warm(sym) {
  const fts = await hit(BASE + '/api/fts/' + encodeURIComponent(sym));
  const levels = await hit(BASE + '/api/chart/' + encodeURIComponent(sym) + '/key-levels');
  return { ftsMs: fts.ms, keyLevelsMs: levels.ms };
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
  // tech_first has candidates on the closed-market dataset; technical stage is
  // rendered open (`only`), so its virtualized rows appear immediately.
  await p.evaluate(() => { location.hash = '#/master?preset=tech_first&stage=technical'; });
  await p.waitForFunction(() => !!document.querySelector('[data-testid="fts-funnel-workspace"]'), null, { timeout: 40000 });
  await p.waitForFunction(() => document.querySelectorAll('[data-fkey]').length > 0, null, { timeout: 30000 });
  await p.waitForTimeout(500);
}

const RES = (p, from) => p.evaluate((from) => performance.getEntriesByType('resource')
  .slice(from)
  .filter((r) => r.name.includes('/api/'))
  .map((r) => ({
    u: decodeURIComponent(r.name).replace(/^https?:\/\/[^/]+/, '').split('?')[0],
    enc: r.encodedBodySize || 0,
    start: r.startTime,
    end: r.startTime + r.duration,
  })), from);

async function waitDossier(p, sym) {
  await p.waitForFunction((sym) => decodeURIComponent(location.hash).includes(sym), sym, { timeout: 15000 });
  await p.waitForFunction((sym) => performance.getEntriesByType('resource').some(
    (r) => decodeURIComponent(r.name).includes('/api/fts/' + sym) && r.responseEnd > 0),
  sym, { timeout: 40000 });
  await p.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
}

async function clickRow(p, sym) {
  const ok = await p.evaluate((s) => {
    const row = document.querySelector(`[data-fkey="${CSS.escape(s)}"]`);
    const btn = row?.querySelector('button');
    if (!btn) return false;
    btn.click();
    return true;
  }, sym);
  if (!ok) throw new Error('row not found: ' + sym);
}

async function measure(p, sym, mode) {
  await openFunnel(p);
  const base = await p.evaluate(() => performance.getEntriesByType('resource').length);
  let hoverMs = null;
  if (mode === 'hover') {
    const t = Date.now();
    await p.hover(`[data-fkey=${JSON.stringify(sym)}]`, { timeout: 10000 });
    await p.waitForTimeout(DWELL);
    hoverMs = Date.now() - t;
  }
  const clickAt = await p.evaluate(() => performance.now());
  const t = Date.now();
  await clickRow(p, sym);
  await waitDossier(p, sym);
  const readyMs = Date.now() - t;
  const reqs = (await RES(p, base))
    .filter((r) => r.u === '/api/fts/' + sym || r.u === '/api/chart/' + sym + '/key-levels')
    .map((r) => ({ ...r, start: Math.round(r.start), end: Math.round(r.end) }));
  const fts = reqs.find((r) => r.u === '/api/fts/' + sym);
  return {
    mode,
    readyMs,
    hoverMs,
    clickToFtsEndMs: fts ? Math.round(fts.end - clickAt) : null,
    ftsMs: fts ? fts.end - fts.start : null,
    prefetchLeadMs: fts ? Math.max(0, Math.round(clickAt - fts.start)) : 0,
    requests: reqs,
  };
}

async function fresh(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const p = await ctx.newPage();
  await p.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(700);
  await login(p);
  return { ctx, p };
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run'] });
  const report = { base: BASE, dwellMs: DWELL, runs: [] };
  for (let run = 1; run <= RUNS; run++) {
    // discover symbols and make sure both are real row entries
    const seed = await fresh(browser);
    await openFunnel(seed.p);
    const rows = await seed.p.evaluate(() => [...document.querySelectorAll('[data-fkey]')]
      .slice(0, 8).map((el) => el.getAttribute('data-fkey')));
    await seed.ctx.close();
    const syms = [rows[0], rows[1]].filter(Boolean);
    if (syms.length < 2) throw new Error('need two funnel rows, got ' + JSON.stringify(rows));

    for (let i = 0; i < 2; i++) {
      const sym = syms[i];
      const warmup = await warm(sym);
      // symbol 0: direct then hover; symbol 1: hover then direct (order balance)
      const order = i === 0 ? ['direct', 'hover'] : ['hover', 'direct'];
      const out = { run, symbol: sym, order, serverWarmup: warmup };
      for (const mode of order) {
        const { ctx, p } = await fresh(browser);
        try {
          out[mode] = await measure(p, sym, mode);
        } finally {
          await ctx.close();
        }
      }
      out.gain = {
        clickToFtsEndMs: out.direct.clickToFtsEndMs - out.hover.clickToFtsEndMs,
        readyMs: out.direct.readyMs - out.hover.readyMs,
      };
      report.runs.push(out);
      console.log(`run ${run} ${sym} [${order.join('→')}] direct: ready=${out.direct.readyMs} ftsEnd=${out.direct.clickToFtsEndMs} fts=${Math.round(out.direct.ftsMs)}` +
        ` | hover: dwell=${out.hover.hoverMs} lead=${out.hover.prefetchLeadMs} ready=${out.hover.readyMs} ftsEnd=${out.hover.clickToFtsEndMs} fts=${Math.round(out.hover.ftsMs)}` +
        ` | gain ready=${out.gain.readyMs} ftsEnd=${out.gain.clickToFtsEndMs}`);
    }
  }
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(report, null, 1));
  console.log('wrote', OUT);
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
