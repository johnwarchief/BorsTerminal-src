/** tools/fts_overlay_pixel_probe.mts — «لایه‌های FTS رویِ چارت دیده می‌شوند» (بند ۳٫۳)
 *
 * آزمونِ jsdom می‌گوید اورلی «ثبت شده و عددِ سرور رسم می‌شود»؛ این پروب می‌گوید
 * پیکسلِ آن رویِ بوم هست. روشِ تفاوتی (نه شمارشِ رنگ):
 *   ۱) state ON: همۀ بوم‌های چارت را پیکسل‌به‌پیکسل می‌خواند
 *   ۲) لایه‌ها را خاموش می‌کند و دوباره می‌خواند
 *   ۳) روشن می‌کند و سومین بار می‌خواند
 * ادعاها: میانِ ON و OFF باید پیکسلِ تغییریافته باشد (لایه دیدنی است)، و ONِ اول
 * با ONِ سوم باید یکی باشد (تفاوت از لایه بود نه از انیمیشن/ردیفِ تازه/نوسانِ داد).
 * بی‌این سومین خواندن، هر repaintِ بی‌ربط هم «تفاوت» می‌سازد.
 *
 * نیازمندِ بیلدِ تازه و بک‌اند زنده:
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types \
 *     tools/fts_overlay_pixel_probe.mts --url http://127.0.0.1:8002 --symbol فولاد
 */
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:8002').replace(/\/$/, '');
const SYM = arg('symbol', 'فولاد');
const OUT = arg('out', '_audit/tmp/fts_overlay_pixels');
const TOL = 8;   // آستانۀ کانال — زیرِ این، چشمِ خودی هم تفاوت را نمی‌بیند

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
const page = await ctx.newPage();
await page.addInitScript(() => { sessionStorage.setItem('bors_auth_session', 'true'); });

/** پیکسل‌های همۀ بومِ چارت درِ `window.__snaps[نام]` می‌نشینند (انتقالِ چندِ
 *  میلیون عدد به node گران است؛ مقایسه هم همین‌جا درِ صفحه انجام می‌شود) */
const capture = (label: string) => page.evaluate((key) => {
  const w = window as unknown as { __snaps?: Record<string, number[]> };
  w.__snaps ??= {};
  const hosts = Array.from(document.querySelectorAll('canvas')).filter((c) => {
    const r = c.getBoundingClientRect();
    return r.width > 60 && r.height > 60;
  });
  const flat: number[] = [];
  const perCanvas: number[][] = [];
  const sizes: string[] = [];
  let pixels = 0;
  for (const c of hosts) {
    try {
      const g = c.getContext('2d');
      if (!g) continue;
      const d = g.getImageData(0, 0, c.width, c.height).data;
      const one: number[] = [];
      for (let i = 0; i < d.length; i += 4) one.push(d[i], d[i + 1], d[i + 2]);
      perCanvas.push(one);
      for (let i = 0; i < one.length; i++) flat.push(one[i]);
      pixels += c.width * c.height;
      sizes.push(`${c.width}x${c.height}`);
    } catch { /* بومِ WebGL یا cross-origin: شمارش نمی‌شود، ادعا هم نمی‌شود */ }
  }
  w.__snaps[key] = flat;
  (w.__snaps as Record<string, unknown>)[`${key}::per`] = perCanvas;
  let seed = 0;
  for (let i = 0; i < flat.length; i += 3) seed = (seed * 31 + flat[i] + flat[i + 1] * 3 + flat[i + 2] * 7) >>> 0;
  return { canvases: sizes.length, pixels, seed, sizes };
}, label);

const compare = (a: string, b: string, tol: number) => page.evaluate(([ka, kb, t]) => {
  const w = window as unknown as { __snaps?: Record<string, number[]> };
  const x = w.__snaps?.[ka];
  const y = w.__snaps?.[kb];
  if (!x || !y) return { changed: -1, total: 0, note: 'snapshot missing' };
  if (x.length !== y.length) return { changed: -1, total: Math.max(x.length, y.length) / 3, note: 'canvas set differs' };
  let changed = 0;
  let total = 0;
  for (let i = 0; i < x.length; i += 3) {
    total++;
    if (Math.max(Math.abs(x[i] - y[i]), Math.abs(x[i + 1] - y[i + 1]), Math.abs(x[i + 2] - y[i + 2])) > t) changed++;
  }
  return { changed, total };
}, [a, b, tol] as [string, string, number]);

/** تفکیکِ تفاوت به هر بوم — «کدام پنل عوض شد» بدونِ این عدد بی‌نام است */
const comparePer = (a: string, b: string, tol: number) => page.evaluate(([ka, kb, t]) => {
  const w = window as unknown as { __snaps?: Record<string, unknown> };
  const x = w.__snaps?.[`${ka}::per`] as number[][] | undefined;
  const y = w.__snaps?.[`${kb}::per`] as number[][] | undefined;
  if (!x || !y || x.length !== y.length) return null;
  return x.map((arr, i) => {
    const o = y[i];
    let changed = 0;
    let total = 0;
    const n = Math.min(arr.length, o.length);
    for (let k = 0; k < n; k += 3) {
      total++;
      if (Math.max(Math.abs(arr[k] - o[k]), Math.abs(arr[k + 1] - o[k + 1]), Math.abs(arr[k + 2] - o[k + 2])) > t) changed++;
    }
    return { canvas: i, changed, total };
  });
}, [a, b, tol] as [string, string, number]);

const pressed = () => page.getAttribute('[data-testid="nn-fts-layer-toggle"]', 'aria-pressed');

const checks: { n: string; ok: boolean; d?: unknown }[] = [];
const push = (n: string, ok: boolean, d?: unknown) => { checks.push({ n, ok, d }); return ok; };

await page.goto(`${BASE}/#/technical/${encodeURIComponent(SYM)}`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('canvas', { timeout: 40000 });
await page.waitForTimeout(9000);   // کندل + تحلیلِ سرور + اورلی‌ها

const p0 = await pressed();
if (p0 !== 'true') { await page.click('[data-testid="nn-fts-layer-toggle"]'); await page.waitForTimeout(3000); }
const stateOn = await pressed();
push('کلیدِ لایه‌های FTS رویِ چارتِ زنده دیدنی است و حالتش خوانده می‌شود',
  stateOn === 'true', { before: p0, after: stateOn });

// دادِ مبدأ از خودِ سرور — لایه بی‌لایه بودنِ فیبو درِ این نماد ثابت شود
let server: Record<string, unknown> | null = null;
try {
  const r = await fetch(`${BASE}/api/fts/${encodeURIComponent(SYM)}`);
  const j = (await r.json()) as Record<string, unknown>;
  const d = (j.data ?? j) as Record<string, unknown>;
  const fts = (d.fts ?? d) as Record<string, unknown>;
  server = (fts.fib ?? null) as Record<string, unknown> | null;
} catch { server = null; }
const fib = server as { zone_33_40?: unknown; zone_618_70?: unknown; levels?: unknown[] } | null;
push(`فیبو/کمربندهایِ «${SYM}» درِ پاسخِ سرور هست (پس چیزی برای دیدن هست)`,
  !!fib && (fib.zone_33_40 != null || fib.zone_618_70 != null),
  { zone_33_40: fib?.zone_33_40 ?? null, zone_618_70: fib?.zone_618_70 ?? null, levels: fib?.levels?.length ?? 0 });

const A = await capture('on');
await page.click('[data-testid="nn-fts-layer-toggle"]');
await page.waitForTimeout(3500);
const B = await capture('off');
await page.click('[data-testid="nn-fts-layer-toggle"]');
await page.waitForTimeout(3500);
const C = await capture('on_again');
// کنترلِ محیط: بی‌هیچ دکمه‌ای دو بار بخوان — چارتِ زنده خطِ آخرینِ قیمت/ساعتِ
// محور را دوباره می‌کشد، پس «صفرِ دقیق» خواستن از آن خطِ چشمک‌زن است نه از لایه.
await page.waitForTimeout(3500);
const D = await capture('on_control');

const dAB = await compare('on', 'off', TOL);
const dAC = await compare('on', 'on_again', TOL);
const dAmb = await compare('on_again', 'on_control', TOL);
const perAB = await comparePer('on', 'off', TOL);
const perAC = await comparePer('on', 'on_again', TOL);
const pctAB = dAB.total ? (100 * dAB.changed) / dAB.total : 0;

// تفکیکِ تفاوت به اندازۀ بوم: klinecharts هر پنل را با دو بومِ هم‌اندازه
// (پس‌زمینه + اورلی) می‌کشد، پس گروه‌کردن بر پایه‌اندازه درست است نه انتخابِ یکی
const bySize = new Map<string, { changed: number; total: number }>();
if (perAB) {
  perAB.forEach((c, i) => {
    const k = A.sizes[i] ?? `#${i}`;
    const cur = bySize.get(k) ?? { changed: 0, total: 0 };
    cur.changed += c.changed; cur.total += c.total;
    bySize.set(k, cur);
  });
}
const pricePane = [...bySize.entries()].sort((a, b) => b[1].total - a[1].total)[0]?.[1];
const shareBig = perAB && dAB.changed > 0 && pricePane
  ? (100 * pricePane.changed) / dAB.changed : 0;
push('تفاوت درِ پنلِ قیمت است نه فقط نوارِ محور (بیش از ۵۰٪ پیکسلِ عوض‌شده)',
  !!perAB && shareBig > 50,
  { bySize: Object.fromEntries(bySize), sizes: A.sizes, perCanvas: perAB, shareOfChangeInPricePane: Number(shareBig.toFixed(1)) });

push('با خاموش‌کردنِ لایه‌ها پیکسلِ چارت عوض می‌شود (لایه دیدنی است، نه فقط ثبت‌شده)',
  dAB.changed > 0 && pctAB > 0.05,
  { changed: dAB.changed, total: dAB.total, pct: Number(pctAB.toFixed(3)), note: dAB.note ?? null });
push('برگشتنِ لایه‌ها صحنه را به اول برمی‌گرداند؛ باقی‌مانده درِ نوسانِ محیطِ چارتِ زنده است',
  dAC.changed <= Math.max(dAmb.changed, Math.round(dAB.changed * 0.02)),
  { changedBack: dAC.changed, ambientDrift: dAmb.changed, layerDelta: dAB.changed, note: dAC.note ?? null });
push('بوم‌های خوانده‌شده همۀ بزرگ‌تر از آیکون‌اند (سنسور کر نیست)',
  A.canvases >= 1 && A.pixels > 100_000,
  { canvases: A.canvases, pixels: A.pixels, sizes: A.sizes });

await page.screenshot({ path: `${OUT}.png` });

const json = {
  base: BASE, at: new Date().toISOString(), symbol: SYM, viewport: '1366x768', tol: TOL,
  server_fib: fib ? { zone_33_40: fib.zone_33_40, zone_618_70: fib.zone_618_70, levels: fib.levels?.length ?? 0 } : null,
  seeds: { on: A.seed, off: B.seed, on_again: C.seed, on_control: D.seed },
  pixels: { on: A.pixels, off: B.pixels, on_again: C.pixels, on_control: D.pixels },
  canvases: { on: A.canvases, off: B.canvases, on_again: C.canvases, on_control: D.canvases },
  sizes: A.sizes,
  diff_on_vs_off: dAB, diff_on_vs_on_again: dAC, ambient_drift: dAmb,
  per_canvas_on_vs_off: perAB, per_canvas_on_vs_on_again: perAC, by_size: Object.fromEntries(bySize),
  checks,
  passed: checks.filter((c) => c.ok).length,
  failed: checks.filter((c) => !c.ok).map((c) => c.n),
};
writeFileSync(`${OUT}.json`, JSON.stringify(json, null, 2), 'utf8');
for (const c of checks) console.log(`${c.ok ? 'PASS' : 'FAIL'}  ${c.n}  ${JSON.stringify(c.d ?? '')}`);
console.log(`\n${json.passed}/${checks.length} — خروجی: ${OUT}.json`);
await browser.close();
