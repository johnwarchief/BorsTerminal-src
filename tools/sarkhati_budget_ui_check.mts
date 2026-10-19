// tools/sarkhati_budget_ui_check.mts — سنجشِ زندهٔ کارتِ بودجه باِ دادهٔ واقعیِ داروند
//
// چرا: آزمونِ jsdom اجازۀِ عددِ ساختگی را می‌سنجد؛ اینجا دو چیزِ دیگر سنجیده
// می‌شود که فقط رویِ بک‌اندِ روشن ممکن است:
//  ۱) ارقامی که درِ صفحه نوشته شده **عیناً** همان ارقامی است که
//     `GET /api/execution/budget` داده — یعنی نه رقمی درِ رابط جا می‌افتد و نه
//     چیزی به آن اضافه می‌شود (تاریخچۀِ همین مخزن رقم‌دزدی داشته، نه ادعا);
//  ۲) بی‌قدرتِ خریدِ کارگزاری، رابط «محاسبه نشد» می‌نویسد و هیچ تعدادی درِ صفحه
//     نیست — یعنی کمبودِ واقعی باِ عددِ بدل پر نمی‌شود.
// نماد ازِ خودِ رابط جست‌وجو و انتخاب می‌شود (نه seedِ حافظه)، پس مسیرِ واقعیِ
// کاربر طی می‌شود. صفرِ درخواستِ برون‌سازمانی سنجیده می‌شود.
import { mkdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  || 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package/node_modules/playwright/index.mjs';
const BASE = process.argv[2] || 'http://127.0.0.1:8010/';
const SYMBOL = process.argv[3] || 'داروند';
const OUT = process.env.JEV_OUT_DIR
  || 'C:/Users/PCMOD/Desktop/_bors-sarkhati-jev/_audit/budget-ui';
mkdirSync(OUT, { recursive: true });

const { chromium } = await import(pathToFileURL(PKG).href);
const browser = await chromium.launch({ headless: true,
  executablePath: process.env.JEV_CHROME || undefined });
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
const ck = (n: string, ok: boolean, extra = '') => results.push([n, ok, extra]);
/** رقم‌هایِ فارسیِ یکِ متن → لاتینِ بی‌جداکننده (همان تبدیلِ آزمونِ jsdom) */
const num = (t: string) => (t.match(/[۰-۹]/g) ?? [])
  .map((c) => String(c.charCodeAt(0) - 0x06f0)).join('');

await page.goto(BASE, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(1500);
await page.getByTestId('nav-sarkhati').click();
await page.getByTestId('sarkhati-tab-symbol').click();
await page.waitForSelector('[data-testid="sarkhati-symbol-search"]', { timeout: 15000 });
await page.fill('[data-testid="sarkhati-symbol-search"]', SYMBOL);
await page.waitForTimeout(900);
const pick = page.locator(`[data-testid="sarkhati-symbol-pick-${SYMBOL}"]`);
ck(`«${SYMBOL}» درِ جست‌وجویِ خودِ رابط پیدا شد`, await pick.count() > 0);
await pick.first().click();
await page.getByTestId('sarkhati-tab-order').click();
await page.waitForSelector('[data-testid="sarkhati-budget-card"]', { timeout: 15000 });

// مرجعِ مستقل: همان پرسش، بی‌رابطِ کاربری
const api = await page.evaluate(async (s) => {
  const r = await fetch(`/api/execution/budget?symbol=${encodeURIComponent(s)}&side=buy&price=`);
  return await r.json();
}, SYMBOL);
const field = async (id: string) => await page.locator(`[data-testid="${id}"]`).innerText();

const priceTxt = await field('sarkhati-budget-price');
ck('قیمتِ صفحه = قیمتِ خودِ پاسخ (رقم‌دزدی ندارد)',
  num(priceTxt) === String(api.price ?? ''), `${priceTxt} vs ${api.price}`);
const bandTxt = await field('sarkhati-budget-band');
ck('بازۀِ صفحه = بازۀِ پاسخ',
  num(bandTxt).startsWith(String(api.band?.allowed_max ?? 'x'))
  && num(bandTxt).endsWith(String(api.band?.allowed_min ?? 'y')),
  `${bandTxt} vs ${api.band?.allowed_max}..${api.band?.allowed_min}`);
const isinTxt = await field('sarkhati-budget-symbol');
ck('شناسۀِ رسمیِ همان نماد نوشته شده', String(api.instrument?.isin ?? '').length > 0
  && isinTxt.includes(String(api.instrument?.isin)), isinTxt.replace(/\s+/g, ' '));
const powerTxt = await field('sarkhati-budget-power');
const qtyTxt = await field('sarkhati-budget-qty');
const totalTxt = await field('sarkhati-budget-total');
ck('بی‌قدرتِ خریدِ کارگزاری «نرسیده» و «محاسبه نشد» است',
  api.buying_power_rial == null && powerTxt.includes('نرسیده')
  && qtyTxt.includes('محاسبه نشد') && num(totalTxt) === '',
  `${powerTxt} | ${qtyTxt} | ${totalTxt}`);
const blockers = await field('sarkhati-budget-blockers');
ck('علتِ کمبود درِ صفحه است، نه سکوت',
  blockers.includes('قدرت خرید'), blockers.replace(/\s+/g, ' ').slice(0, 150));
const src = await field('sarkhati-budget-source');
ck('برچسبِ مبدأ باِ from_broker می‌خواند',
  (api.from_broker === true) === src.includes('ازِ کارگزاری'), src);
const notOrder = await field('sarkhati-budget-not-order');
ck('کارت خودش را «سفارش» جا نمی‌زند', notOrder.includes('نه سفارش'), notOrder);
await page.screenshot({ path: OUT + '/01-budget.png' });

// و همان قدرتِ خریدِ ساختگی **فرستاده نمی‌شود**: هیچ ورودی‌ای درِ این کارت نیست
const inputs = await page.locator('[data-testid="sarkhati-budget-card"] input').count();
ck('کارت هیچ ورودیِ عددی ندارد (عددی ازِ کاربر نمی‌گیرد و نمی‌سازد)', inputs === 0,
  String(inputs));

ck('صفرِ درخواستِ مرورگر به میزبانِ کارگزاری', brokerHits.length === 0,
  brokerHits.slice(0, 2).join(' | '));
ck('بی‌خطایِ کنسول', errors.length === 0, errors.slice(0, 3).join(' | '));

await browser.close();
let failed = 0;
console.log('\n== sarkhati_budget_ui_check — ' + SYMBOL + ' ==');
for (const [n, ok, extra] of results) {
  if (!ok) failed++;
  console.log((ok ? '  ok   ' : '  FAIL ') + n + (extra ? ' — ' + extra : ''));
}
console.log('\n%d passed / %d failed — تصاویر: %s', results.length - failed, failed, OUT);
process.exit(failed ? 1 : 0);
