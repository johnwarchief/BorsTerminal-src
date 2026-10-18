// tools/broker_connect_ui_check.mts — سنجشِ زندهٔ «تنظیمِ اتصال» رویِ بیلدِ منبعی
//
// چرا این فایل هست: آزمونِ jsdom ثابت می‌کند مؤلفه درست رندر می‌شود؛ اینجا سنجیده
// می‌شود که *پاسخِ واقعیِ بک‌اند* همان برچسب‌ها را می‌سازد و یکِ کلیکِ ذخیره
// واقعاً به `POST /api/execution/config` می‌نشیند. سه چیز صریح چک می‌شود:
//  ۱) هیچ درخواستی به میزبانِ کارگزاری نمی‌رود (zero-traffic proof)،
//  ۲) «ذخیره شد» و «اعمال شد» دو متنِ جدا می‌مانند،
//  ۳) برچسبِ نشست ازِ `proven` می‌آید، نه ازِ `state: connected`،
//  ۴) پلکانِ چهارسطری (تنظیم / نشستِ واردشده / تأیید / ارسال) هر وضعیت را جدا
//     می‌گوید و فرمِ نشانی، نشانی را هیچ‌جا بازنمی‌گرداند.
// درِ ورودِ خودِ ترمینال (admin/bors123 درِ کدِ منبعی) دست‌نخورده می‌ماند؛ تنها
// کلیدِ نشستِ محلی درِ sessionStorage می‌نشیند تا سنجه رابط را ببیند نه دروازه.
import { mkdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

const PKG = process.env.JEV_BROWSER_DIR
  || 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package/node_modules/playwright/index.mjs';
const BASE = process.argv[2] || 'http://127.0.0.1:8106/';
const OUT = 'C:/Users/PCMOD/Desktop/_bors-fts-technical/_audit/broker-ui';
mkdirSync(OUT, { recursive: true });

const require = createRequire(import.meta.url);
const { chromium } = await import(pathToFileURL(PKG).href);

const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.JEV_CHROME || undefined,
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
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
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 120)); });
page.on('pageerror', (e) => errors.push('PAGEERROR ' + String(e).slice(0, 120)));

await page.goto(BASE + '#/sarkhati', { waitUntil: 'domcontentloaded' });
// صفحۀ «سرخطی» مرحله‌محور است؛ کارتِ اتصال زیرِ قدمِ «۱ اتصال» است و پیش ازِ
// کلیکِ همان قدم درِ DOM نیست (این خودِ صفحه را نباید حدس زد — سنجیده شد).
await page.waitForSelector('[data-testid="sarkhati-tab-connect"]', { timeout: 25000 });
await page.click('[data-testid="sarkhati-tab-connect"]');
await page.waitForSelector('[data-testid="sarkhati-connection-settings"]', { timeout: 25000 });

const read = async (id: string) => page.evaluate((sel) => {
  const el = document.querySelector(sel);
  return el ? (el.textContent || '').trim() : null;
}, `[data-testid="${id}"]`);

/** صبر تا هر چهار سطرِ پلکان از «پاسخی نیامده» (حالتِ میانۀ بارگذاری) دربیایند.
 *  بی‌این، خواندنِ درِ لحظۀِ اول هر چهار را «پاسخی نیامده» نشان می‌دهد و آن
 *  حالتِ گذرا را با نبودِ پاسخِ واقعی اشتباه می‌خوانَد. */
const SETTLED = 'پاسخی نیامده';
await page.waitForFunction(([id, wrong]: string[]) => {
  const el = document.querySelector(`[data-testid="${id}"]`);
  return !!el && (el.textContent || '').trim() !== wrong && (el.textContent || '').trim() !== '';
}, [`sarkhati-gate-config`, SETTLED], { timeout: 20000 }).catch(() => undefined);

// سه دور: `read` فقط می‌خواند (پاسِ پسِ restart)، `save` کلیکِ ذخیرهٔ تنظیم را
// می‌سنجد، و `token` فرمِ نشانیِ نشست را (پاسخِ ردِ بک‌اند درِ آداپتورِ بدل هم
// یکِ پاسخِ صادق است؛ مهم این است که نشانی هیچ‌جا باقی نمانَد).
const MODE = process.argv[3] || 'save';

const pass1: Record<string, unknown> = {
  href: page.url(),
  loginGateShown: await page.evaluate(
    () => !!document.querySelector('input[placeholder="admin"]')),
  traffic: await read('sarkhati-traffic-mode'),
  gates: {
    config: await read('sarkhati-gate-config'),
    entered: await read('sarkhati-gate-entered'),
    proven: await read('sarkhati-gate-proven'),
    writes: await read('sarkhati-gate-writes'),
  },
  tokenInputMasked: await page.evaluate(() => {
    const el = document.querySelector('[data-testid="sarkhati-token-input"]') as HTMLInputElement | null;
    return el ? el.type === 'password' : null;
  }),
  stored: await read('sarkhati-config-stored'),
  effective: await read('sarkhati-config-effective'),
  source: await read('sarkhati-config-source'),
  portfolio: await read('sarkhati-portfolio-status'),
  portfolioError: await read('sarkhati-portfolio-error'),
  restartLine: await read('sarkhati-config-restart'),
  windowVsSession: await read('sarkhati-window-vs-session'),
};

// نشانیِ جعلیِ سنجه: اگر رابط آن را هیچ‌جا بازنگرداند، درِ DOM هم پیدا نمی‌شود.
const PROBE_TOKEN = 'BORS-UIPROBE-NOT-A-REAL-SESSION';
let tokenPass: Record<string, unknown> = { skipped: true };
if (MODE === 'token') {
  await page.fill('[data-testid="sarkhati-token-input"]', PROBE_TOKEN);
  await page.click('[data-testid="sarkhati-token-save"]');
  await page.waitForSelector('[data-testid="sarkhati-session-note"]', { timeout: 15000 });
  tokenPass = {
    note: await read('sarkhati-session-note'),
    gates: {
      entered: await read('sarkhati-gate-entered'),
      proven: await read('sarkhati-gate-proven'),
      writes: await read('sarkhati-gate-writes'),
    },
    tokenStillInDom: await page.evaluate(
      (s) => (document.body.textContent || '').includes(s), PROBE_TOKEN),
    orderishRequests: await page.evaluate(() => performance.getEntriesByType('resource')
      .map((r) => r.name).filter((n) => /preflight|prepare|dispatch|cancel|\/order/i.test(n))),
  };
}

// کلیکِ واقعی: کارگزاری ← فقط‌خواندنی ← ذخیره
const pass2: Record<string, unknown> = { skipped: MODE !== 'save' };
if (MODE === 'save') {
  await page.click('[data-testid="sarkhati-adapter-easytrader"]');
  await page.click('[data-testid="sarkhati-read-only"]');
  const reqsBefore = await page.evaluate(() => performance.getEntriesByType('resource').length);
  await page.click('[data-testid="sarkhati-config-save"]');
  await page.waitForSelector('[data-testid="sarkhati-config-restart"]', { timeout: 15000 });
  pass2.stored = await read('sarkhati-config-stored');
  pass2.effective = await read('sarkhati-config-effective');
  pass2.source = await read('sarkhati-config-source');
  pass2.restartLine = await read('sarkhati-config-restart');
  pass2.traffic = await read('sarkhati-traffic-mode');
  pass2.portfolio = await read('sarkhati-portfolio-status');
  pass2.note = await read('sarkhati-config-note');
  pass2.reqDelta = (await page.evaluate(() => performance.getEntriesByType('resource').length)) - reqsBefore;
}
await page.screenshot({ path: OUT + '/settings.jpeg', type: 'jpeg', quality: 60 });

const card = await page.locator('[data-testid="sarkhati-connection-card"]').boundingBox();
const height = card ? Math.round(card.height) : -1;

const orderPaths = await page.evaluate(() => performance.getEntriesByType('resource')
  .map((r) => r.name)
  .filter((n) => /\/api\/execution\/(preflight|prepare|dispatch|reconcile|refresh|cancel|schedule)/.test(n)));

const result = {
  mode: MODE,
  pass1_mockDefault: pass1,
  pass2_afterSave: pass2,
  tokenPass,
  cardHeightPx: height,
  orderPathRequests: orderPaths,
  brokerTrafficRequests: brokerHits,
  consoleErrors: errors.slice(0, 8),
};
console.log(JSON.stringify(result, null, 2));
await browser.close();
