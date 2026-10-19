// tools/sarkhati_har_ui_check.mts — سنجشِ زندهٔ «برداشتِ نشست از HAR» درِ مرورگر
//
// چه چیزی را *نمی*‌سنجد: ورودِ واقعی به کارگزاری. اینجا یکِ HARِ ساختگی باِ
// نشانیِ کاشته‌شده مصرف می‌شود تا سه چیزِ دیدنی سنجیده شود:
//  ۱) رابطِ کارتِ اتصال درِ مرورگرِ واقعی بالا می‌آید و متنِ «چه نشانی‌ای
//     می‌پذیریم» خواناست — بندِ ۷ مأموریت؛
//  ۲) «تحلیلِ مسیرها» پاسخِ *بک‌اندِ* روشن را رندر می‌کند (نه fixtureِ jsdom)،
//     و نشانیِ کاشته‌شده درِ هیچ گوارۀِ DOM نیست؛
//  ۳) باِ آداپتورِ بدل، «برداشتِ نشست» صادقانه رد می‌شود و همان رد درِ رابط
//     می‌ماند — هیچ «متصل شد» ازِ نبودِ قابلیت ساخته نمی‌شود.
// صفرِ درخواستِ برون‌سازمانی: صفحه فقط باِ 127.0.0.1 حرف می‌زند و این فایل هر
// چهار میزبانِ کارگزاری را درِ شنونده ثبت می‌کند؛ اگر یکی‌شان آمد، سنجه قرمز است.
import { mkdirSync, writeFileSync, unlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  || 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package/node_modules/playwright/index.mjs';
const BASE = process.argv[2] || 'http://127.0.0.1:8010/';
const OUT = process.env.JEV_OUT_DIR
  || 'C:/Users/PCMOD/Desktop/_bors-sarkhati-jev/_audit/har-ui';
mkdirSync(OUT, { recursive: true });

const { chromium } = await import(pathToFileURL(PKG).href);
const browser = await chromium.launch({ headless: true,
  executablePath: process.env.JEV_CHROME || undefined });

const TOKEN_SENT = 'eyJhbGciOiJSUzI1Ni0uSENBUi1MSVZFLVNFQVJDVUJTLmNhbGwtbm90LXZlcg';
const COOKIE_SENT = 'BORS-LIVE-PROBE-COOKIE-4471';
const BODY_SENT = 'BORS-LIVE-PROBE-BODY-9931';
const HAR_PATH = join(tmpdir(), 'bors_har_probe.har');
writeFileSync(HAR_PATH, JSON.stringify({ log: { version: '1.2', entries: [
  { request: { method: 'GET',
      url: 'https://api-mts.orbis.easytrader.ir/core/api/order?x=1',
      headers: [{ name: 'Authorization', value: 'Bearer ' + TOKEN_SENT },
        { name: 'Cookie', value: 'SESSION=' + COOKIE_SENT }] },
    response: { status: 200, content: { mimeType: 'application/json',
      text: JSON.stringify({ buyingPower: 123456, rows: [{ id: 1,
        password: BODY_SENT }] }) } } },
  { request: { method: 'GET', url: 'https://login.emofid.com/authorize', headers: [] },
    response: { status: 200, content: { mimeType: 'text/html', text: '<html/>' } } },
] } }), 'utf-8');

const ctx = await browser.newContext({ viewport: { width: 1440, height: 1150 } });
await ctx.addInitScript(() => {
  try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* noop */ }
});
const page = await ctx.newPage();
const brokerHits: string[] = [];
const errors: string[] = [];
page.on('request', (r) => {
  const u = r.url();
  if (/orbis|easytrader\.ir|emofid|codal\.ir|tsetmc/i.test(u)) brokerHits.push(u);
});
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 140)); });
page.on('pageerror', (e) => errors.push('PAGEERROR ' + String(e).slice(0, 140)));

const results: Array<[string, boolean, string]> = [];
const ck = (name: string, ok: boolean, extra = '') =>
  results.push([name, ok, extra]);

await page.goto(BASE, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(1500);
await page.getByTestId('nav-sarkhati').click();
// تبِّ سرخطی رویِ «قدمِ پیشنهادی» فرود می‌آید، پس برایِ دیدنِ کارتِ اتصال باید
// صریحٌاً به سطرِ «اتصال» رفت — همین کاری که خودِ کاربر می‌کند.
await page.getByTestId('sarkhati-tab-connect').click();
await page.waitForSelector('[data-testid="sarkhati-har-block"]', { timeout: 15000 });
await page.waitForSelector('[data-testid="connect-open-browser"]', { timeout: 15000 });

// ۱) نوعِ نشانی درِ رابط نوشته شده است
const label = await page.locator('[data-testid="sarkhati-token-input"]')
  .evaluate((el) => (el.closest('label')?.textContent ?? '').slice(0, 400));
ck('رابط می‌گوید چه نوعِ نشانی‌ای می‌پذیرد', label.includes('Authorization: Bearer'),
  label.slice(0, 120));
const btnLogin = await page.getByTestId('connect-open-browser').innerText();
ck('دکمۀِ ورودِ رسمیِ کارگزاری همان «ورود به ایزی‌تریدر» است',
  btnLogin.trim() === 'ورود به ایزی‌تریدر', btnLogin.trim());

// ۲) تحلیلِ مسیرها رویِ پاسخِ واقعیِ بک‌اند
await page.setInputFiles('[data-testid="sarkhati-har-file"]', HAR_PATH);
await page.getByTestId('sarkhati-har-inspect').click();
await page.waitForSelector('[data-testid="sarkhati-har-paths"] li', { timeout: 20000 });
const seen = await page.locator('[data-testid="sarkhati-har-paths"]').innerText();
ck('مسیرِ واقعیِ wire ازِ بک‌اند درِ صفحه است', seen.includes('/core/api/order'),
  seen.replace(/\s+/g, ' ').slice(0, 160));
ck('نامِ کلیدِ موجودی هم دیده می‌شود', seen.includes('buyingPower'), '');
const meta = await page.locator('[data-testid="sarkhati-har-meta"]').innerText();
ck('شمارش‌هایِ گزارش ازِ خودِ پرونده آمده', meta.includes('۲'), meta);
const bodyText = await page.evaluate(() => document.body.innerText);
ck('هیچ مقدارِ هدر یا بدنه‌ای درِ DOM نیست',
  !bodyText.includes(TOKEN_SENT) && !bodyText.includes(COOKIE_SENT)
  && !bodyText.includes(BODY_SENT) && !bodyText.includes('123456'), '');
const cleared = await page.locator('[data-testid="sarkhati-har-file"]')
  .evaluate((el) => (el as HTMLInputElement).value);
ck('انتخابِ پرونده پسِ خواندن ازِ فیلد پاک شد', cleared === '', cleared);
await page.screenshot({ path: OUT + '/01-inspect.png', fullPage: false });

// ۳) ردِ صادقانه درِ آداپتورِ بدل
await page.setInputFiles('[data-testid="sarkhati-har-file"]', HAR_PATH);
await page.getByTestId('sarkhati-har-import').click();
await page.waitForSelector('[data-testid="sarkhati-session-note"]', { timeout: 20000 });
const note = await page.locator('[data-testid="sarkhati-session-note"]').innerText();
ck('بدل، برداشت را رد می‌کند و علت را می‌گوید',
  /نمی‌پذیرد|مجاز نیست/.test(note) && !/متصل/.test(note), note.slice(0, 160));
const ladder = await page.locator('[data-testid="sarkhati-state-ladder"]').innerText();
ck('هیچ سطرِ پلکان به «تأیید شده» عوض نشد', !/تأیید شده|متصل/.test(ladder),
  ladder.replace(/\s+/g, ' ').slice(0, 160));
await page.screenshot({ path: OUT + '/02-refused.png', fullPage: false });

ck('صفرِ درخواستِ مرورگر به میزبانِ کارگزاری', brokerHits.length === 0,
  brokerHits.slice(0, 2).join(' | '));
ck('بی‌خطایِ کنسول یا صفحۀِ شکسته', errors.length === 0, errors.slice(0, 3).join(' | '));

await browser.close();
unlinkSync(HAR_PATH);

let failed = 0;
console.log('\n== sarkhati_har_ui_check ==');
for (const [n, ok, extra] of results) {
  if (!ok) failed++;
  console.log((ok ? '  ok   ' : '  FAIL ') + n + (extra ? ' — ' + extra : ''));
}
console.log('\n%d passed / %d failed — تصاویر: %s', results.length - failed, failed, OUT);
process.exit(failed ? 1 : 0);
