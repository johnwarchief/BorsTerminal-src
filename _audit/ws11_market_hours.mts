// _audit/ws11_market_hours.mts — سنجشِ «ساعتِ بازار» برایِ غربالگری FTS (§۱۵.۲۱، بازماندۀ ۱۵.۲۴)
//
// آنچه درِ نشستِ بسته قابلِ سنجش نبود و مالک دقیقاً همان را خواسته است:
//   ۱ ریتمِ تازه‌سازی: درِ ساعتِ باز باید ~۲۰ ثانیه باشد (و ۵ ثانیه تا صفِ
//     اسکنِ تکنیکال خالی نشده) — نه ۶۰ ثانیه و نه چیزی که CPU را بخورد.
//   ۲ نمادها «جلویِ چشم» جابه‌جا شوند: درِ پنجرۀ سنجش باید هم انیمیشنِ FLIP
//     دیده شود (document.getAnimations رویِ بدنهٔ جدول) و هم ترتیبِ ردیف‌ها
//     واقعاً عوض شده باشد. بی‌این دو، «در حال محاسبه» فقط یک متن است.
//   ۳ هر پاسخِ کاملِ موتور چقدر طول می‌کشد و چند بار درِ دقیقه اجرا می‌شود
//     (تطبیقِ عددِ warm/cold با بارِ واقعیِ نشست).
//
// تطبیف با TradersArena درِ همین نشست با ابزارِ موجود خودش سنجیده می‌شود
// (پیانگِ هم‌لحظه): `python tools/pulse_ta_snapshot.py` و سپس
// `python tools/pulse_ta_parity.py` — این فایل آن را تکرار نمی‌کند.
//
// اجرا: JEV_BROWSER_DIR + JEV_CHROME + MSYS_NO_PATHCONV=1
//   node --experimental-strip-types _audit/ws11_market_hours.mts --url http://127.0.0.1:5175/ --window 180
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const arg = (n: string, f: string) => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:5175/');
const WINDOW_S = Number(arg('window', '180'));
mkdirSync('_audit', { recursive: true });
const OUT = '_audit/ws11_market_hours.json';

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const errs: string[] = [];
const funnel: { ms: number; dur: number }[] = [];
const t0 = Date.now();
let openAt = 0;
page.on('pageerror', (e) => errs.push(String(e.message).slice(0, 140)));
page.on('request', (r) => { if (String(r.url()).includes('/api/funnel')) openAt = Date.now(); });
page.on('response', async (r) => {
  const u = String(r.url());
  if (!u.includes('/api/funnel') || u.includes('/registry')) return;
  funnel.push({ ms: Date.now() - t0, dur: Number(r.headers()['x-response-time'] ?? 0) || 0 });
});

await page.goto(BASE + '#/master?stage=technical&preset=custom', { waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => /[۱-۹]/.test(document.querySelector('[data-testid="funnel-universe-market"]')?.textContent ?? ''),
  null, { timeout: 240_000 });

// نشانکِ حرکت: ترتیبِ ۲۰ ردیفِ اولِ جدولِ تکنیکال + شمارِ انیمیشن‌هایِ در حالِ اجرا
const sig = () => page.evaluate(() => {
  const t = document.querySelector('[data-testid="funnel-scroll-technical"]');
  if (!t) return { order: '', anims: 0, rows: 0 };
  const order = [...t.querySelectorAll('tbody tr')].slice(0, 20)
    .map((tr) => String(tr.getAttribute('data-fkey') ?? '')).join(',');
  const host = t.querySelector('tbody') ?? t;
  const anims = (host as any).getAnimations ? (host as any).getAnimations().length : -1;
  return { order, anims, rows: t.querySelectorAll('tbody tr').length };
});

const before = await sig();
const animSamples: number[] = [];
const orders: string[] = [before.order];
const endAt = Date.now() + WINDOW_S * 1000;
while (Date.now() < endAt) {
  await page.waitForTimeout(1500);
  const s = await sig();
  animSamples.push(s.anims);
  if (s.order && s.order !== orders[orders.length - 1]) orders.push(s.order);
}

const reqs = funnel.map((f) => f.ms);
const gaps = reqs.slice(1).map((v, i) => v - reqs[i]);
const res = {
  base: BASE, windowS: WINDOW_S,
  marketOpen: (() => {
    const d = new Date();
    const mins = d.getHours() * 60 + d.getMinutes();
    return { localMinuteOfDay: mins, note: 'ساعتِ سیستم محلی است؛ قاعدۀ ۰۸:۴۵-۱۲:۳۰ تهران درِ خودِ برنامه (`shared/lib/marketHours.ts`) پیاده است' };
  })(),
  funnelRequests: { count: funnel.length, atMs: reqs, gapsMs: gaps },
  movement: {
    distinctOrders: orders.length,
    firstOrderSample: before.order.slice(0, 120),
    lastOrderSample: orders[orders.length - 1].slice(0, 120),
    maxConcurrentAnimations: Math.max(0, ...animSamples),
    samplesWithAnimation: animSamples.filter((n) => n > 0).length,
    samples: animSamples.length,
  },
  pageErrors: errs,
};
const checks: [string, boolean][] = [
  ['the session is live (board rows painted)', before.rows > 0],
  ['at least one refresh happened inside the window', funnel.length > 1],
  ['rows actually move: more than one distinct order', orders.length > 1],
  ['movement is animated (FLIP seen)', res.movement.maxConcurrentAnimations > 0],
  ['no page errors', errs.length === 0],
];
res.verdict = checks.map(([k, v]) => ({ check: k, pass: v }));
writeFileSync(OUT, JSON.stringify(res, null, 2));
for (const [k, v] of checks) console.log((v ? 'PASS ' : 'FAIL ') + k);
console.log(`requests=${funnel.length} gaps=${JSON.stringify(gaps.slice(0, 8))} window=${WINDOW_S}s`);
console.log(`orders=${orders.length} animSamples>0 ${res.movement.samplesWithAnimation}/${res.movement.samples} max=${res.movement.maxConcurrentAnimations}`);
if (errs.length) console.log('errors: ' + JSON.stringify(errs.slice(0, 4)));
await browser.close();
