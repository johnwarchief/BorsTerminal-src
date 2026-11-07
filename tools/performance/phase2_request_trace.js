// Log every /api request issued by one FTS symbol switch, with method and
// response timing, to detect duplicate calls. Read-only.
//
// usage: node tools/performance/phase2_request_trace.js --symbol سپيدار --out <json>
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
const SYMBOL = arg('--symbol', 'سپيدار');
const OUT = path.resolve(REPO, arg('--out', 'artifacts/performance/phase2/request-trace.json'));

async function login(page) {
  if (!(await page.evaluate(() => !!document.querySelector('input[type="password"]')))) return;
  const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
  const u = (src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
  const p = (src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
  await page.locator('input[type="text"]').first().fill(u);
  await page.locator('input[type="password"]').first().fill(p);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(2200);
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await login(page);
  await page.waitForTimeout(1200);
  const calls = [];
  const t0 = Date.now();
  page.on('request', (req) => {
    if (!req.url().includes('/api/')) return;
    calls.push({ t: Date.now() - t0, method: req.method(),
                 url: decodeURIComponent(req.url()).replace(/^https?:\/\/[^/]+/, ''),
                 body: req.postData() ? req.postData().slice(0, 160) : null });
  });
  const responses = [];
  page.on('response', (res) => {
    if (!res.url().includes('/api/')) return;
    responses.push({ t: Date.now() - t0, status: res.status(),
                     url: decodeURIComponent(res.url()).replace(/^https?:\/\/[^/]+/, ''),
                     reqMs: Math.round(res.request().timing().responseEnd || -1) });
  });
  await page.evaluate((s) => { location.hash = '#/master/' + encodeURIComponent(s); }, SYMBOL);
  await page.waitForTimeout(12000);
  const out = { symbol: SYMBOL, t0: new Date(t0).toISOString(), calls, responses };
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
  console.log('CALLS');
  for (const c of calls) console.log(`+${c.t}ms ${c.method} ${c.url.slice(0, 130)}`);
  console.log('RESPONSES');
  for (const r of responses) console.log(`+${r.t}ms ${r.status} ${r.url.slice(0, 110)} timing=${r.reqMs}`);
  console.log('wrote', OUT);
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
