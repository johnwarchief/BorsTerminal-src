/** tools/flash_envelope_probe.mts — اثباتِ زندهٔ «انیمیشنِ نرمِ فلاش» (مأموریتِ یکپارچه‌سازیِ فلاش)
 *
 * سه چیز مقابله می‌شود:
 *   ۱) شکلِ منحنی: فلاش از شفاف بالا می‌آید (fade-in)، لحظه‌ای می‌ماند، و آرام
 *      تا شفاف پایین می‌رود (fade-out) — نه «سبزِ ناگهانی» و نه «پرشِ به عقب».
 *      با انیمیشنِ CSSِ واقعیِ خودِ صفحه (pause + scrubِ currentTime) نمونه‌برداری
 *      می‌شود، پس عددِ قطعی است نه حدس.
 *   ۲) بی‌جابه‌جاییِ چیدمان: عرض/ارتفاعِ سلول در طولِ فلاش ثابت می‌ماند.
 *   ۳) یکپارچگیِ الگو: .live-flash-* همان @keyframes flash-up را می‌خواند (منحنی
 *      یکی است، فقط مدت کم) و @keyframes جداگانهٔ live-flash حذف شده.
 *
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types \
 *     tools/flash_envelope_probe.mts --url http://127.0.0.1:5173/ --out _audit/flash/envelope
 */
import { writeFileSync, mkdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:5173/').replace(/\/$/, '');
const OUT = arg('out', '_audit/flash/envelope');
mkdirSync(OUT.replace(/[^/]*$/, ''), { recursive: true });

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
const page = await ctx.newPage();
await page.addInitScript(() => { sessionStorage.setItem('bors_auth_session', 'true'); });

await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
// سلولِ عددیِ تابلو (ریشۀ FlashNum) دیده شود
await page.waitForSelector('.num.inline-block', { timeout: 45000 });
await page.waitForTimeout(2500); // بگذار داده بنشیند و --bors-flash-dur از ریتمِ تیک بیاید

const result = await page.evaluate(() => {
  const alphaOf = (bg: string): number => {
    if (!bg || bg === 'transparent') return 0;
    const nums = bg.match(/[\d.]+/g);
    if (!nums) return 0;
    // rgba(r,g,b,a) → a؛ rgb(r,g,b) یا color(...) → بی‌پارامترِ آلفا ⇒ ۱، اما
    // color-mix با transparent همیشه چهار عدد می‌دهد.
    if (bg.startsWith('rgb(')) return 1;
    return nums.length >= 4 ? Math.min(1, parseFloat(nums[3])) : 0;
  };

  const cell = document.querySelector('.num.inline-block') as HTMLElement | null;
  if (!cell) return { error: 'no .num.inline-block cell' };

  const flashDurVar = getComputedStyle(document.documentElement)
    .getPropertyValue('--bors-flash-dur').trim();

  const rect0 = cell.getBoundingClientRect();
  cell.classList.remove('flash-up', 'flash-down');
  void cell.offsetWidth;
  cell.classList.add('flash-up');
  const anims = cell.getAnimations();
  const anim = anims[0] as CSSAnimation | undefined;
  if (!anim) return { error: 'no animation on .flash-up cell' };

  const timing = anim.effect!.getComputedTiming();
  const dur = typeof timing.duration === 'number' ? timing.duration : 1600;
  anim.pause();

  // منحنی در درصدهایِ ثابت (تعیینی، مستقل از جیترِ ساعتِ دیوار)
  const stops = [0, 0.03, 0.06, 0.12, 0.2, 0.3, 0.45, 0.6, 0.75, 0.9, 1.0];
  const curve = stops.map((p) => {
    anim.currentTime = p * dur;
    const cs = getComputedStyle(cell);
    const r = cell.getBoundingClientRect();
    return {
      pct: p,
      ms: Math.round(p * dur),
      alpha: +alphaOf(cs.backgroundColor).toFixed(3),
      w: +r.width.toFixed(2),
      h: +r.height.toFixed(2),
    };
  });
  const peak = Math.max(...curve.map((c) => c.alpha));
  const peakPct = (curve.find((c) => c.alpha === peak) || curve[0]).pct;
  anim.cancel();
  const endRect = cell.getBoundingClientRect();
  const widthShift = Math.abs(endRect.width - rect0.width);

  // CSSOM: فهرستِ @keyframes هایِ فلاش (برایِ اثباتِ حذفِ منحنیِ دوتایی)
  const keyframeNames: string[] = [];
  for (const sheet of Array.from(document.styleSheets)) {
    let kr: CSSRuleList;
    try { kr = sheet.cssRules; } catch { continue; }
    for (const rule of Array.from(kr)) {
      if (rule instanceof CSSKeyframesRule) keyframeNames.push(rule.name);
    }
  }

  // یکپارچگیِ الگو — اثباتِ عملکردی: یک اسپنِ زنده با کلاسِ .live-flash-up
  // باید همان @keyframes flash-up را اجرا کند (منحنی یکی، فقط مدت کم).
  // (CSSOMِ خالص زیرِ @layerِ Tailwind قابلِ پیمایشِ سطحی نیست.)
  const liveProbe = document.createElement('span');
  liveProbe.className = 'num inline-block live-flash-up';
  document.body.appendChild(liveProbe);
  const liveName = getComputedStyle(liveProbe).animationName;
  const liveDur = getComputedStyle(liveProbe).animationDuration;
  liveProbe.remove();

  return {
    flashDurVar,
    dur,
    curve,
    peak,
    peakPct,
    widthShift,
    heightShift0: Math.abs(endRect.height - rect0.height),
    liveName,
    liveDur,
    hasOldLiveKeyframes: keyframeNames.includes('live-flash-up') || keyframeNames.includes('live-flash-down'),
    keyframeNames: keyframeNames.filter((n) => /flash/.test(n)),
  };
});

// اسکرین‌شاتِ سه لحظه: fade-in، نزدیکِ اوجِ رنگ، fade-outِ میانی
await page.evaluate(() => {
  const cell = document.querySelector('.num.inline-block') as HTMLElement;
  cell.classList.remove('flash-up', 'flash-down');
  void cell.offsetWidth;
  cell.classList.add('flash-up');
  const a = cell.getAnimations()[0];
  const d = (a.effect!.getComputedTiming().duration as number) || 1600;
  (a as CSSAnimation).pause();
  (a as CSSAnimation).currentTime = 0.12 * d; // نزدیکِ اوج
});
await page.screenshot({ path: `${OUT}-peak.jpeg`, type: 'jpeg', quality: 70 } as any);

const c = result.curve ?? [];
const at = (p: number) => c.find((x) => Math.abs(x.pct - p) < 0.02)?.alpha ?? NaN;
const checks: Array<[string, boolean, unknown]> = [
  ['سلولِ عددیِ تابلو فلاش می‌گیرد (کنترلِ رسیدن)', !result.error && c.length > 0, result],
  ['fade-in وجود دارد: در t≈۰ رنگ تقریباً شفاف است (<۰٫۱۲)', at(0) < 0.12, { a0: at(0) }],
  ['رنگِ اوج دیده می‌شود (>=۰٫۳)', result.peak >= 0.3, { peak: result.peak }],
  ['اوج در کانونِ fade-in است (۶–۳۰٪ از مدت)', result.peakPct >= 0.06 && result.peakPct <= 0.3, { peakPct: result.peakPct }],
  ['fade-out کامل: در پایان رنگ به شفاف برمی‌گردد (<۰٫۰۸) — رنگ گیرکرده نداریم', at(1.0) < 0.08, { aEnd: at(1.0) }],
  ['میانیِ fade-out زیرِ اوج است (تدریجی، نه پلتویِ طولانی)', at(0.6) < result.peak, { a60: at(0.6), peak: result.peak }],
  ['بی‌جابه‌جاییِ چیدمان: عرضِ سلول ثابت ماند (<=۰٫۵px)', (result.widthShift ?? 99) <= 0.5, { wShift: result.widthShift }],
  ['یکپارچگی: .live-flash-up همان flash-up را اجرا می‌کند (منحنیِ یکی)', result.liveName === 'flash-up', { liveName: result.liveName, liveDur: result.liveDur }],
  ['حذفِ منحنیِ دوتایی: @keyframes جداگانهٔ live-flash-* نمانده', result.hasOldLiveKeyframes === false, result.keyframeNames],
  ['مدت از ریتمِ تیک (--bors-flash-dur) می‌آید', !!result.flashDurVar && result.flashDurVar.endsWith('ms'), result.flashDurVar],
];
const failed = checks.filter(([, ok]) => !ok);
writeFileSync(`${OUT}.json`, JSON.stringify({ base: BASE, at: new Date().toISOString(), result, checks: checks.map(([n, ok]) => ({ n, ok })) }, null, 1));
for (const [name, ok, detail] of checks) console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${ok ? '' : '  ' + JSON.stringify(detail)}`);
console.log(`منحنی alpha: ${c.map((x) => `${x.pct}:${x.alpha}`).join('  ')}`);
console.log(`--bors-flash-dur=${result.flashDurVar} dur=${result.dur}ms peak=${result.peak}@${(result.peakPct * 100).toFixed(0)}% wShift=${result.widthShift}px`);
await browser.close();
process.exit(failed.length ? 1 : 0);
