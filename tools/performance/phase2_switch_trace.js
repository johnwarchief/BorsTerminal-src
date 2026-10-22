// P2-R6: one real funnel-row click, with every /api request, response status,
// transfer size and click->dossier-ready timing. Read-only.
const path = require('path'), fs = require('fs'), http = require('http');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const argv = process.argv.slice(2); const arg = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
const SYMBOL = arg('--symbol', 'آبنوس');
const OUT = path.resolve(REPO, arg('--out', 'artifacts/performance/phase2/switch-trace.json'));

function warm(sym) {
  return new Promise((res) => {
    const t = Date.now();
    http.get(BASE + '/api/fts/' + encodeURIComponent(sym), (r) => {
      r.resume(); r.on('end', () => res(Date.now() - t));
    }).on('error', () => res(null));
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

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const p = await ctx.newPage();
  const requests = [];
  const responses = [];
  p.on('request', (r) => {
    const u = decodeURIComponent(r.url());
    if (u.includes('/api/')) requests.push({ method: r.method(), url: u.replace(/^https?:\/\/[^/]+/, '') });
  });
  p.on('response', (r) => {
    const u = decodeURIComponent(r.url());
    if (u.includes('/api/')) responses.push({ status: r.status(), url: u.replace(/^https?:\/\/[^/]+/, '') });
  });
  await p.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(800);
  await login(p);
  await p.evaluate(() => { location.hash = '#/master?preset=tech_first&stage=technical'; });
  await p.waitForFunction(() => document.querySelectorAll('[data-fkey]').length > 0, null, { timeout: 45000 });
  await p.waitForTimeout(500);
  await warm(SYMBOL);
  const base = await p.evaluate(() => performance.getEntriesByType('resource').length);
  const r0 = requests.length;
  const t = Date.now();
  await p.evaluate((s) => {
    const row = document.querySelector(`[data-fkey="${CSS.escape(s)}"]`);
    row?.querySelector('button')?.click();
  }, SYMBOL);
  await p.waitForFunction((s) => decodeURIComponent(location.hash).includes(s), SYMBOL, { timeout: 15000 });
  await p.waitForFunction((s) => performance.getEntriesByType('resource').some(
    (r) => decodeURIComponent(r.name).includes('/api/fts/' + s) && r.responseEnd > 0), SYMBOL, { timeout: 45000 });
  await p.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  const readyMs = Date.now() - t;
  const res = await p.evaluate((base) => performance.getEntriesByType('resource').slice(base)
    .filter((r) => r.name.includes('/api/'))
    .map((r) => ({
      url: decodeURIComponent(r.name).replace(/^https?:\/\/[^/]+/, '').split('?')[0],
      query: decodeURIComponent(r.name).split('?')[1] || '',
      enc: r.encodedBodySize || 0,
      ms: Math.round(r.duration),
    })), base);
  const out = {
    symbol: SYMBOL, readyMs,
    totalKB: Math.round(res.reduce((a, r) => a + r.enc, 0) / 1024),
    requests: res,
    http: responses.slice(-40),
    started: requests.slice(r0).length,
  };
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
  console.log('symbol', SYMBOL, 'readyMs', readyMs, 'requests', res.length, 'totalKiB', out.totalKB);
  for (const r of res) console.log(`  ${r.ms}ms ${Math.round(r.enc / 1024)}KiB ${r.url}${r.query ? '?' + r.query.slice(0, 90) : ''}`);
  console.log('wrote', OUT);
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
