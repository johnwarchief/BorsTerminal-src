// Capture pageerror stacks for a single route (default: technical) in a real
// browser. Read-only diagnostic; used to decide whether a console error belongs
// to a performance change or to a pre-existing chart race.
//
// usage: node tools/performance/error_probe.js --route /technical --runs 5
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));

const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const argv = process.argv.slice(2);
const arg = (name, dflt) => {
  const i = argv.indexOf(name);
  return i >= 0 ? argv[i + 1] : dflt;
};
const ROUTE = arg('--route', '/technical');
const RUNS = Number(arg('--runs', '5'));
const SYMBOLS = (arg('--symbols', '') || '').split(',').map((s) => s.trim()).filter(Boolean);

async function loginIfNeeded(page) {
  if (!(await page.evaluate(() => !!document.querySelector('input[type="password"]')))) return;
  const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
  const du = (src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
  const dp = (src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
  await page.locator('input[type="text"]').first().fill(du);
  await page.locator('input[type="password"]').first().fill(dp);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(2500);
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push({ run: currentRun, message: String(e), stack: (e.stack || '').slice(0, 1200) }));
  page.on('console', (m) => { if (m.type() === 'error') errors.push({ run: currentRun, console: m.text().slice(0, 400) }); });
  let currentRun = 0;
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  await loginIfNeeded(page);
  for (currentRun = 1; currentRun <= RUNS; currentRun++) {
    await page.goto(BASE + '/#' + ROUTE, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    for (const s of SYMBOLS) {
      await page.evaluate(([route, sym]) => {
        location.hash = `#${route}/${encodeURIComponent(sym)}`;
      }, [ROUTE, s]);
      await page.waitForTimeout(2500);
    }
    console.log(`run ${currentRun}: errors so far=${errors.length}`);
  }
  fs.writeFileSync(path.join(REPO, 'artifacts', 'performance', '2026-10-22', 'error-probe.json'),
                   JSON.stringify({ route: ROUTE, runs: RUNS, errors }, null, 1));
  console.log(JSON.stringify(errors, null, 1));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
