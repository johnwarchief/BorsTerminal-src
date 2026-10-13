/**
 * tools/fund_stale_probe.mts — سناریوی ۵ و ۶ بندِ ۶ مأموریت: تعویضِ نماد و پاسخِ کهنه.
 *
 * چرا این فایل جدا از `jev_ui_check.mts` است: آن ابزار «یکِ route، یکِ بار» می‌رود
 * و نمی‌تواند دو درخواستِ هم‌زمان با **تأخیرِ وارونه** بسازد. اینجا دقیقاً همان
 * ساختارِ بدترین حالتِ واقعی انجام می‌شود:
 *
 *   ۱) کارت نماد A باز می‌شود (پاسخِ A عمداً دیر می‌رسد — 2600ms)
 *   ۲) پیش از رسیدنِ A به نماد B سوئیچ می‌شود (پاسخِ B زود می‌رسد — 150ms)
 *   ۳) پاسخِ A **بعد از** B می‌رسد؛ اگر رابط نگهبانِ ترتیب نداشته باشد،
 *      محتوای A رویِ هدرِ B می‌نشیند و کاربر عددِ نمادِ دیگر را می‌بیند.
 *
 * شاهدِ خروجی: کدامِ نماد درِ DOM دیده می‌شود، متنِ سلولِ حاشیه، ترتیبِ
 * درخواست/پاسخِ شبکه، و خطاهایِ کنسول. بی‌هیچِ دادهٔ ساختگی — تأخیرها با
 * route-intercept خودِ همان پاسخ‌های زندهٔ بک‌اند ساخته می‌شوند.
 *
 * usage:
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=.../chrome.exe \
 *   node --experimental-strip-types tools/fund_stale_probe.mts \
 *     --url http://127.0.0.1:8002/ --a "شهر فرش" --b "وكادو" --out _audit/live-fund/stale.json
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';

const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};

const BASE = arg('url', 'http://127.0.0.1:8002/');
const A = arg('a', 'شهر فرش');
const B = arg('b', 'وكادو');
const OUT = arg('out', '_audit/live-fund/stale.json');
const A_DELAY = Number.parseInt(arg('a-delay', '2600'), 10);
const B_DELAY = Number.parseInt(arg('b-delay', '150'), 10);

const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);

const CHROME = process.env.JEV_CHROME ?? '';
const browser = await chromium.launch({ headless: true, executablePath: CHROME || undefined });
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
await context.addInitScript(() => {
  sessionStorage.setItem('bors_auth_session', 'true');
});
const page = await context.newPage();

const errors: string[] = [];
page.on('console', (m: any) => { if (m.type() === 'error') errors.push(String(m.text()).slice(0, 200)); });
page.on('pageerror', (e: any) => errors.push(`pageerror: ${String(e.message).slice(0, 200)}`));

const timeline: { t: number; kind: string; sym: string }[] = [];
const t0 = Date.now();
const note = (kind: string, sym: string) => timeline.push({ t: Date.now() - t0, kind, sym });

await page.route('**/api/fundamental/**', async (route: any) => {
  const url: string = route.request().url();
  const sym = decodeURIComponent(url.split('/api/fundamental/')[1] || '');
  const isA = sym.startsWith(A.slice(0, 4)) || sym.replace(/\s+/g, '') === A.replace(/\s+/g, '');
  const delay = isA ? A_DELAY : B_DELAY;
  note('request', `${sym} (+${delay}ms)`);
  let res: any;
  try {
    res = await route.fetch();
  } catch (e) {
    // لینۀِ بی‌مصرف: کاربر پیش از رسیدنِ پاسخ نماد را عوض کرد و خودِ
    // React Query درخواست را abort کرد — این خودش شاهدِ خواستۀ مأموریت است.
    note('aborted', sym);
    try { await route.abort(); } catch { /* بی‌اهمیت */ }
    return;
  }
  const body = await res.text();
  await new Promise((r) => setTimeout(r, delay));
  note('response', sym);
  try {
    await route.fulfill({ response: res, body });
  } catch {
    note('fulfill-dropped', sym);
  }
});

await page.goto(`${BASE}#/fundamental/${encodeURIComponent(A)}`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(1400);
// سوئیچِ واقعی: همان کاری که کاربر می‌کند — هاشِ تازه (کلیکِ رِوِیتِ آدرس)
await page.evaluate((h: string) => { location.hash = h; }, `#/fundamental/${encodeURIComponent(B)}`);
await page.waitForTimeout(6000);

const read = await page.evaluate(() => {
  const cell = document.querySelector('[data-testid="fts-card-cell-3_gross_margin"]');
  const label = document.querySelector('[data-testid="drilldown-margin-reference"]');
  const head = document.querySelector('h1, header h2, [class*="symbol"]');
  const dossier = document.querySelector('[data-testid^="fts-dossier-"]');
  return {
    href: location.href,
    title: document.title,
    headText: (head?.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120),
    bodyHasA: (document.body?.innerText || '').includes('شهر فرش'),
    bodyHasB: (document.body?.innerText || '').includes('وكادو') ||
              (document.body?.innerText || '').includes('تیپیکو'),
    marginCell: (cell?.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 160),
    marginReference: (label?.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 160),
    dossierTestId: dossier?.getAttribute('data-testid') || null,
    dossierCells: Array.from(document.querySelectorAll('[data-testid^="fts-card-cell-"]'))
      .map((n) => (n.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 70)),
  };
});

const body = (await page.evaluate(() => document.body?.innerText || '')).replace(/\s+/g, ' ');
const verdict = {
  expected_symbol: B,
  rendered_head: read.headText,
  stale_A_visible: body.includes('شهر فرش'),
  b_visible: body.includes(B),
  order: timeline,
  consoleErrors: errors.slice(0, 10),
  read,
};
mkdirSync(OUT.replace(/[^/]*$/, ''), { recursive: true });
writeFileSync(OUT, JSON.stringify(verdict, null, 1), 'utf8');
console.log(JSON.stringify({
  rendered_head: read.headText,
  stale_A_visible: verdict.stale_A_visible,
  b_visible: verdict.b_visible,
  marginCell: read.marginCell,
  marginReference: read.marginReference,
  order: timeline,
  consoleErrors: verdict.consoleErrors,
}, null, 1));
await browser.close();
