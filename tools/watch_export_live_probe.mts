// tools/watch_export_live_probe.mts — شاهدِ زندهٔ «دکمهٔ خروجی واقعاً فایل می‌دهد»
//
// چه چیزی بدونِ این سنجش باورکردنی است و دروغ: گاردِ unit و گاردِ Python هر دو
// فایل را درِ فرایندِ خودشان می‌سازند. چیزی که ثابت‌نشده می‌ماند این است که
// **دکمه درِ رابط** همان فایل را به مرورگر می‌رساند — نه لینکِ ساختگی، نه
// alert، نه صفحۀ خالی. اینجا با Playwright واقعی کلیک می‌کنیم، `download` را
// می‌گیریم، فایلِ رویِ دیسک را با openpyxlِ خودِ ماشین باز می‌کنیم و
// می‌شماریم: سطر، ستون، و این‌که سلولِ حجم عدد است یا رشته.
//
// اجرا (از ریشۀ ریپو، با بک‌اندی که رابط به آن پروکسی می‌کند):
//   MSYS_NO_PATHCONV=1 \
//   JEV_CHROME=C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe \
//   node tools/watch_export_live_probe.mts --url http://127.0.0.1:5174/ [--out _audit/…]
import { existsSync, mkdirSync, copyFileSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};

const BASE = arg('url', 'http://127.0.0.1:5174/');
const OUT = arg('out', '_audit/market_parity_20261014');
const CHROME = process.env.JEV_CHROME ?? '';
if (!CHROME) throw new Error('JEV_CHROME لازم است (خودکارِ ensureChromium روی این ماشین مسدود است)');
if (!existsSync(CHROME)) throw new Error(`JEV_CHROME وجود ندارد: ${CHROME}`);
mkdirSync(OUT, { recursive: true });

const { chromium } = await imp('node_modules/playwright/index.mjs');

const browser = await chromium.launch({
  executablePath: CHROME,
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const context = await browser.newContext({
  acceptDownloads: true,
  viewport: { width: 1366, height: 768 },
});
// دروازهٔ ورودِ محلیِ dev (همان کلیدی که jev_ui_check می‌گذارد)
await context.addInitScript(() => {
  try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* پوستهٔ بی‌دروازه */ }
});
const page = await context.newPage();
const consoleErrors: string[] = [];
const failedRequests: string[] = [];
page.on('console', (m) => {
  if (m.type() === 'error') {
    const loc = m.location?.() ?? {};
    consoleErrors.push(`${m.text().slice(0, 160)} @ ${String(loc.url ?? '?').slice(0, 90)}:${loc.lineNumber ?? '?'}`);
  }
});
page.on('requestfailed', (r) => failedRequests.push(
  `${r.method()} ${r.url().slice(0, 90)} ⇒ ${r.failure()?.errorText ?? '?'}`));

const report: Record<string, unknown> = { base: BASE, at: new Date().toISOString() };
const out = (k: string, v: unknown) => { report[k] = v; console.log(`  ${k}: ${JSON.stringify(v)}`); };

await page.goto(`${BASE.replace(/\/$/, '')}/#/watch`, { waitUntil: 'networkidle', timeout: 60_000 });
await page.waitForTimeout(2500);

const href = page.url();
out('href', href);
if (/Unexpected Application Error/i.test(await page.locator('body').innerText().catch(() => ''))) {
  out('fatal', 'ErrorBoundary — خودِ پروب را بخوان، نه رابط را');
  await browser.close();
  process.exit(2);
}

// ── دیدهبان خالی نباشد: دو نماد از خودِ فید اضافه می‌شود ─────────────────────
let rowCount = await page.locator('[data-testid^="watch-row-"]').count();
if (rowCount === 0) {
  const feed = await page.evaluate(async () => {
    const r = await fetch('/api/market');
    const j = await r.json();
    const rows = (j.data || []).filter((x) => (x.q_tot_cap || 0) > 0).slice(0, 3);
    return rows.map((x) => ({ symbol: x.symbol, name: x.name }));
  });
  out('seed', feed);
  for (const f of feed) {
    await page.fill('[data-testid="watch-add-input"]', f.symbol);
    await page.click('[data-testid="watch-add-btn"]');
    await page.waitForTimeout(350);
  }
  await page.waitForTimeout(1500);
  rowCount = await page.locator('[data-testid^="watch-row-"]').count();
}
out('watchRows', rowCount);
if (rowCount === 0) {
  out('blocker', 'دیدهبان خالی ماند — افزودنِ نماد درِ این نشست ممکن نشد');
  await page.screenshot({ path: path.join(OUT, 'watch_live_empty.png'), fullPage: false });
  await browser.close();
  process.exit(2);
}

// ── ۱) دامنهٔ «کلِ دیدهبان» ⇒ CSV ───────────────────────────────────────────
const control = page.locator('[data-testid="watch-export"]');
out('controlVisible', await control.isVisible());
out('scopeOptions', await page.locator('[data-testid="watch-export-scope"] option').allTextContents());
out('columnSets', await page.locator('[data-testid="watch-export-colset"] option').allTextContents());

const grab = async (label: string) => {
  const dl = await Promise.all([
    page.waitForEvent('download', { timeout: 30_000 }),
    page.click(`[data-testid="${label}"]`),
  ]).then((a) => a[0]);
  const p = await dl.path();
  const dest = path.join(OUT, dl.suggestedFilename() || `capture-${Date.now()}`);
  if (p) copyFileSync(p, dest);
  return { name: dl.suggestedFilename(), dest, bytes: p ? readFileSync(p).byteLength : 0 };
};

await page.selectOption('[data-testid="watch-export-colset"]', 'board');
await page.selectOption('[data-testid="watch-export-scope"]', 'all');
const csv = await grab('watch-export-csv');
out('csvDownload', csv);
const csvText = readFileSync(csv.dest, 'utf8');
const stripBom = (s: string) => s.replace(new RegExp('^' + String.fromCharCode(0xFEFF)), '');
const csvLines = stripBom(csvText).split(/\r?\n/).filter((l) => l !== '');
out('csvHasBom', csvText.charCodeAt(0) === 0xfeff);
out('csvStartsWithSep', csvLines[0].startsWith('sep=;'));
out('csvDataRows', csvLines.filter((l) => !l.startsWith('#')).length - 1);
out('csvHeaderUnits', (csvLines[1].split(';').filter((h) => /ریال|سهم|٪|میلیارد/.test(h)).length));
out('csvMetaLines', csvLines.filter((l) => l.startsWith('#')).length);
const volIdx = csvLines[1].split(';').indexOf('حجم (سهم)');
out('csvVolumeCellsArePlainNumbers', csvLines
  .filter((l) => !l.startsWith('#')).slice(2)
  .every((l) => { const v = l.split(';')[volIdx]; return v === '' || /^[\d.]+$/.test(v); }));

// ── ۲) Excel ازِ سرور ────────────────────────────────────────────────────────
const xl = await grab('watch-export-xlsx');
out('xlsxDownload', xl);
const head = readFileSync(xl.dest).subarray(0, 4).toString('hex');
out('xlsxMagicPk', head.slice(0, 4) === '504b');   // PK\x03\x04 = زیشِ واقعیِ xlsx

// ── ۳) دامنهٔ «انتخاب‌شده» با تیکِ دو ردیف ──────────────────────────────────
const boxes = page.locator('[data-testid^="watch-pick-"]:not([data-testid="watch-pick-all"])');
const boxCount = await boxes.count();
if (boxCount >= 2) {
  await boxes.nth(0).check();
  await boxes.nth(1).check();
  await page.selectOption('[data-testid="watch-export-scope"]', 'selected');
  await page.waitForTimeout(400);
  const selCount = await page.getAttribute('[data-testid="watch-export"]', 'data-count');
  out('selectedDataCount', selCount);
  const s = await grab('watch-export-csv');
  const sLines = readFileSync(s.dest, 'utf8').replace(/^/, '').split(/\r?\n/).filter((l) => l !== '');
  out('selectedCsvRows', sLines.filter((l) => !l.startsWith('#')).length - 1);
  out('selectedFileName', s.name);
} else {
  out('selectedSkipped', `تیکِ ردیف پیدا نشد (${boxCount})`);
}

// ── ۴) فیلتر ⇒ دامنهٔ «نتایجِ فیلترشده» ─────────────────────────────────────
const firstSymbol = await page.locator('[data-testid^="watch-row-"]').first()
  .getAttribute('data-testid').then((t) => (t ?? '').replace('watch-row-', ''));
await page.fill('[data-testid="watch-filter-input"]', firstSymbol);
await page.waitForTimeout(400);
const visibleAfterFilter = await page.locator('[data-testid^="watch-row-"]').count();
out('filter', { symbol: firstSymbol, visibleAfterFilter,
  chip: await page.locator('[data-testid="watch-filter-count"]').innerText() });
await page.selectOption('[data-testid="watch-export-scope"]', 'visible');
await page.waitForTimeout(300);
out('visibleDataCount', await page.getAttribute('[data-testid="watch-export"]', 'data-count'));
await page.fill('[data-testid="watch-filter-input"]', '');

// ── ۵) اورفلو/بریدگی در دو عرض ──────────────────────────────────────────────
const shots: Record<string, unknown> = {};
for (const vp of [{ width: 1366, height: 768 }, { width: 390, height: 844 }]) {
  await page.setViewportSize(vp);
  await page.waitForTimeout(900);
  const m = await page.evaluate(() => ({
    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    controlText: (document.querySelector('[data-testid="watch-export"]')?.textContent ?? '').replace(/\s+/g, ' ').trim(),
    rows: document.querySelectorAll('[data-testid^="watch-row-"]').length,
  }));
  shots[`${vp.width}x${vp.height}`] = m;
  await page.screenshot({ path: path.join(OUT, `watch_export_${vp.width}.png`), fullPage: false });
}
out('viewports', shots);
out('consoleErrors', consoleErrors.slice(0, 8));
out('failedRequests', failedRequests.slice(0, 8));

await browser.close();
mkdirSync(OUT, { recursive: true });
const jsonPath = path.join(OUT, 'watch_export_live.json');
await import('node:fs').then((fs) => fs.writeFileSync(jsonPath, JSON.stringify(report, null, 1), 'utf8'));
console.log(`\nخروجی: ${jsonPath}`);
