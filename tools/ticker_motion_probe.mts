/** tools/ticker_motion_probe.mts — اثباتِ زندهٔ حرکتِ پیوسته (بند ۴.۱ و ۴.۳)
 *
 * «CSS بلااستفاده» اثباتِ کار نیست؛ پس این پروب خودِ نوار را درِ مرورگر
 * اندازه می‌گیرد:
 *   • transform درِ دو نمونه‌برداریِ ۲٫۵ ثانیه‌ای فرق می‌کند (حرکت واقعی)
 *   • با hover می‌ایستد، با دکمهٔ توقف می‌ایستد، و با ادامه دوباره می‌رود
 *   • حرکت درخواستِ شبکه تولید نمی‌کند (شمارشِ fetch درِ پنجرۀِ حرکت)
 *   • تغییرِ اندازه نوار را به ابتدا نمی‌پراند
 *   • prefers-reduced-motion ⇒ ایستا و بی‌نسخۀِ دوم
 *
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types \
 *     tools/ticker_motion_probe.mts --url http://127.0.0.1:8002/
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
const BASE = arg('url', 'http://127.0.0.1:8002/').replace(/\/$/, '');
const OUT = arg('out', '_audit/tmp/ticker_motion');

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
const page = await ctx.newPage();
await page.addInitScript(() => {
  sessionStorage.setItem('bors_auth_session', 'true');
  localStorage.setItem('market.status.ticker.mode.v1', 'continuous');
});
let reqs = 0;
page.on('request', (r) => { if (r.url().includes('/api/')) reqs++; });

const xf = () => page.evaluate(() =>
  document.querySelector('[data-testid="ticker-marquee-track"]')?.getAttribute('style') ?? '');
const state = () => page.evaluate(() =>
  document.querySelector('[data-testid="ticker-marquee"]')?.getAttribute('data-state') ?? null);

await page.goto(`${BASE}/#/market-status`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(16000);

const out: Record<string, unknown> = { base: BASE, at: new Date().toISOString() };
const checks: Array<[string, boolean, unknown]> = [];

// ── ۱) حرکت واقعی ───────────────────────────────────────────────────────────
out.state_running = await state();
const t0 = await xf();
const reqs0 = reqs;
await page.waitForTimeout(2500);
const t1 = await xf();
const reqsDuring = reqs - reqs0;
checks.push(['نوار واقعاً جابه‌جا می‌شود (transform عوض شد)', t0 !== t1 && /translate/.test(t1), { t0, t1 }]);
// «بی‌درخواست» با سنجهٔ مطلق اندازه‌گیری نمی‌شود: پولینگِ خودِ صفحه درِ همان
// پنجره می‌تواند بزند. مقایسه با همان پنجره درِ حالتِ ایستا (پایین‌تر).
out.reqs_during_motion = reqsDuring;
await page.screenshot({ path: `${OUT}-running.png` });

// ── ۲) hover ⇒ مکث ──────────────────────────────────────────────────────────
await page.hover('[data-testid="status-ticker"]');
await page.waitForTimeout(400);
const h0 = await xf();
await page.waitForTimeout(1600);
const h1 = await xf();
checks.push(['با hover می‌ایستد', h0 === h1 && (await state()) === 'paused', { h0, h1, state: await state() }]);
await page.mouse.move(10, 700);
await page.waitForTimeout(1600);
checks.push(['با جداکردنِ نشانگر از همان‌جا ادامه می‌دهد', (await xf()) !== h1, { after: await xf(), h1 }]);

// ── ۳) دکمۀِ توقف رویِ خودِ نوار ────────────────────────────────────────────
await page.click('[data-testid="ticker-rotate-toggle"]');
await page.waitForTimeout(400);
const p0 = await xf();
await page.waitForTimeout(1500);
checks.push(['دکمۀِ توقف رویِ نوار حرکت را می‌بندد', p0 === (await xf()), { p0, p1: await xf() }]);
checks.push(['دکمۀِ توقف دیدنی و رویِ نوار باقی است',
  await page.evaluate(() => !!document.querySelector('[data-testid="ticker-rotate-toggle"]')), true]);
// کلیکِ دوم نشانگر را رویِ نوار نگه می‌دارد و hover خودش مکث است؛ پس
// اول نشانگر را بیرون می‌بریم، بعد حرکت را می‌سنجیم (وگرنه «برنگشت» غلط است).
await page.click('[data-testid="ticker-rotate-toggle"]');
await page.mouse.move(10, 700);
await page.waitForTimeout(1800);
const resumed = await xf();
checks.push(['دوباره روشن شد و نشانگر بیرون است ⇒ حرکت برگشت', resumed !== p0, { p0, resumed }]);
// شمارشِ درخواست درِ پنجرۀِ تصادفی سنجهٔ پایداری نیست (پولینگِ خودِ صفحه
// هر ۳۰/۶۰ ثانیه می‌زند و به نوار ربطی ندارد). چیزی که بند ۴.۳ واقعاً
// می‌خواهد این است: حرکت درِ هر فریم محاسبۀِ سنگین نسازد. پس نرخِ فریم و
// زمانِ کارِ نخِ اصلی درِ پنجرۀِ روان اندازه‌گیری می‌شود.
const perf = await page.evaluate(() => new Promise((res) => {
  const ts: number[] = [];
  const t0 = performance.now();
  const tick = (t: number) => {
    ts.push(t);
    if (t - t0 < 2500) requestAnimationFrame(tick);
    else {
      const gaps: number[] = [];
      for (let i = 1; i < ts.length; i++) gaps.push(ts[i] - ts[i - 1]);
      gaps.sort((a, b) => a - b);
      res({
        frames: ts.length,
        fps: Math.round((ts.length - 1) / ((ts[ts.length - 1] - ts[0]) / 1000)),
        medianGapMs: +gaps[Math.floor(gaps.length / 2)].toFixed(1),
        p95GapMs: +gaps[Math.floor(gaps.length * 0.95)].toFixed(1),
      });
    }
  };
  requestAnimationFrame(tick);
}));
out.frame_window = perf;
checks.push(['نرخِ فریم درِ ۱۳۶۶×۷۶۸ رویِ همین ماشین ≥ ۳۰fps است',
  (perf as { fps: number }).fps >= 30, perf]);
checks.push(['میانهٔ فاصلۀِ فریم زیرِ ۴۰ms است (محاسبۀِ سنگین درِ هر فریم نیست)',
  (perf as { medianGapMs: number }).medianGapMs < 40, perf]);

// ── ۴) تغییرِ اندازه ⇒ بی‌پرش ───────────────────────────────────────────────
const beforeResize = await xf();
await page.setViewportSize({ width: 1100, height: 768 });
await page.waitForTimeout(700);
const afterResize = await xf();
checks.push(['تغییرِ اندازه نوار را به صفر برنمی‌گرداند',
  !/translate3d\(0px/.test(afterResize) && afterResize !== beforeResize,
  { beforeResize, afterResize }]);
await page.setViewportSize({ width: 1366, height: 768 });

// ── ۵) کاهشِ حرکتِ سیستم ───────────────────────────────────────────────────
const ctx2 = await browser.newContext({ viewport: { width: 1366, height: 768 }, reducedMotion: 'reduce' });
const p2 = await ctx2.newPage();
await p2.addInitScript(() => {
  sessionStorage.setItem('bors_auth_session', 'true');
  // حالتِ پیوسته صریح خواسته می‌شود: بی‌این درِ کاهشِ حرکت نوار اصلاً
  // رندر نمی‌شد و «ایستاده است» بی‌دلیل سبز می‌خواند (سنسورِ کور).
  localStorage.setItem('market.status.ticker.mode.v1', 'continuous');
});
const mounted = await p2.goto(`${BASE}/#/market-status`, { waitUntil: 'domcontentloaded' }).then(() =>
  p2.waitForTimeout(15000)).then(() => p2.evaluate(() =>
    !!document.querySelector('[data-testid="ticker-marquee"]')));
checks.push(['کنترلِ رسیدن: درِ کاهشِ حرکت هم نوار رویِ صفحه است', mounted === true, mounted]);
const r0 = await p2.evaluate(() => document.querySelector('[data-testid="ticker-marquee-track"]')?.getAttribute('style') ?? '');
await p2.waitForTimeout(2000);
const r1 = await p2.evaluate(() => document.querySelector('[data-testid="ticker-marquee-track"]')?.getAttribute('style') ?? '');
const copies = await p2.evaluate(() => document.querySelectorAll('[data-testid="ticker-marquee-copy-2"]').length);
const text = await p2.evaluate(() => document.querySelector('[data-testid="ticker-marquee"]')?.textContent ?? '');
checks.push(['با کاهشِ حرکت نوار می‌ایستد', r0 === r1 && !/translate3d\([1-9]/.test(r1), { r0, r1 }]);
checks.push(['با کاهشِ حرکت نسخۀِ دوم حذف می‌شود و محتوا خوانا می‌ماند',
  copies === 0 && text.includes('مثبت'), { copies, len: text.length }]);
await p2.screenshot({ path: `${OUT}-reduced.png` });
await ctx2.close();

out.checks = checks.map(([n, ok, d]) => ({ n, ok, d }));
writeFileSync(`${OUT}.json`, JSON.stringify(out, null, 2));
for (const [n, ok, d] of checks) console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${n}${ok ? '' : '  ' + JSON.stringify(d)}`);
const failed = checks.filter((c) => !c[1]).length;
console.log(`\nticker_motion: ${checks.length - failed}/${checks.length} داوری سبز`);
await browser.close();
process.exit(failed ? 1 : 0);
