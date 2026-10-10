/** tools/chart_engine_lab_probe.mts — سنجشِ زندهٔ «دو موتور، یک داده» (بند ۳.۲ و ۳.۳)
 *
 * ارزشیابیِ کتابخانه با ذکرِ نامِ پکیج اثبات نمی‌شود؛ این پروب از خودِ
 * `#/engine-lab` می‌خواند و پنج چیز را ثابت می‌کند:
 *   ۱) هر دو موتور واقعاً mount شده‌اند (rendererِ non-null از health، نه فرض)
 *   ۲) شمارۀ کندل درِ دو پنل یکی است و درخواستِ چارت دقیقاً یک‌بار زده می‌شود
 *      (پس تفاوتِ دیدنی اگر بود، تفاوتِ موتور است نه تفاوتِ داده)
 *   ۳) لایه‌های FTS درِ هر دو پنل رفته‌اند (بي‌صفر)
 *   ۴) کنترلِ سنسور: با خاموش‌کردنِ «لایه‌های FTS» شمارۀ لایه درِ هر دو به صفر
 *      می‌افتد، و با تایم‌فریمِ هفتگی شمارۀ کندل عوض می‌شود — وگرنه عددهای
 *      ثابتِ DOM هم می‌توانند یعنی «سنسور کر است»
 *   ۵) mountMs / fps / heap برایِ هر دو اندازه گرفته می‌شود
 *
 * نیازمندِ بیلدِ تازه (`npm run build`) و بک‌اند زنده:
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types \
 *     tools/chart_engine_lab_probe.mts --url http://127.0.0.1:8002
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
const OUT = arg('out', '_audit/tmp/engine_lab');
const SYM = arg('symbol', 'فولاد');

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
const page = await ctx.newPage();
await page.addInitScript(() => { sessionStorage.setItem('bors_auth_session', 'true'); });

let chartReqs = 0;
page.on('request', (r) => { if (/\/api\/chart\//.test(r.url())) chartReqs++; });

/** متنِ نوارِ سنجه‌هایِ هر پنل → واژه‌به‌واژهٔ فارسی، تا بعداً قابلِ بازخوانی بماند */
const strip = (id: string) => page.evaluate((eng) => {
  const col = document.querySelector(`[data-testid="lab-col-${eng}"]`);
  if (!col) return null;
  const box = col.querySelector(`[data-testid="lab-host-${eng}"]`)?.getBoundingClientRect();
  // نوارِ سنجه، پدرِ همان دکمۀ «اندازه‌گیری» است؛ lastElementChildِ ستون
  // سرِ صفحۀ آزمایشگاه را هم می‌گیرد و سنجه‌ها را نمی‌بیند
  const foot = document.querySelector(`[data-testid="lab-measure-${eng}"]`)?.parentElement ?? null;
  const out: Record<string, string | number | null> = {};
  (foot ? Array.from(foot.querySelectorAll('span')) : []).forEach((s) => {
    const t = (s.textContent || '').replace(/\s+/g, ' ').trim();
    const m = /^(رندر|بوم|کندل|لایه|بالا‌آمدن|فریم\/ثانیه|پشته|نامشخص):\s*(.+)$/.exec(t);
    if (m) out[m[1]] = m[2];
  });
  const cs = col.querySelectorAll(`[data-testid="lab-host-${eng}"] canvas`);
  return {
    foot: foot ? (foot.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 400) : null,
    metrics: out,
    canvas: cs.length,
    canvasBox: box ? { w: Math.round(box.width), h: Math.round(box.height) } : null,
    errors: Array.from(col.querySelectorAll('li')).map((li) => (li.textContent || '').trim()).slice(0, 4),
  };
}, id);
const t0 = undefined; // helper placeholder removed below

const num = (v: string | number | null | undefined) => {
  if (v == null) return null;
  const fa = '۰۱۲۳۴۵۶۷۸۹';
  const latin = String(v).replace(/[۰-۹]/g, (d) => String(fa.indexOf(d)));
  const m = /-?\d+(\.\d+)?/.exec(latin.replace(/\s/g, ''));
  return m ? Number(m[0]) : null;
};

const checks: { n: string; ok: boolean; d?: unknown }[] = [];
const push = (n: string, ok: boolean, d?: unknown) => { checks.push({ n, ok, d }); return ok; };

await page.goto(`${BASE}/#/engine-lab`, { waitUntil: 'domcontentloaded' });
// کشِ RAMِ بک‌اند اگر سرد باشد نخستین `/api/chart` چند ده ثانیه طول می‌کشد؛ پنل‌ها
// تا نیامدنِ کندل‌ها سنجه‌ای ندارند، پس سقفِ صبر به ۷۵ ثانیه می‌رود.
// صبر رویِ دکمۀِ سرِ صفحۀ «اندازه‌گیری کارایی» است (پنل‌ها پایین‌تراند و
// waitForSelector رویِ عنصرِ outside-viewport اینجا «دیدنی» گزارش نمی‌کند).
await page.waitForSelector('[data-testid="engine-lab"]', { timeout: 30000 });
await page.waitForSelector('#lab-measure-all', { timeout: 75000 });
const bothHaveBars = async () => {
  const k = num((await strip('klinecharts'))?.metrics['کندل']);
  const f = num((await strip('ffc'))?.metrics['کندل']);
  return k != null && k > 0 && f != null && f > 0;
};
for (let i = 0; i < 30 && !(await bothHaveBars()); i++) await page.waitForTimeout(2500);
await page.waitForTimeout(3500);

const kA = await strip('klinecharts');
const fA = await strip('ffc');

push('هر دو موتور mount شده‌اند (renderer از health)',
  !!kA?.metrics['رندر'] && kA.metrics['رندر'] !== '-' &&
  !!fA?.metrics['رندر'] && fA.metrics['رندر'] !== '-',
  { klinecharts: kA?.metrics['رندر'], ffc: fA?.metrics['رندر'] });

const kb = num(kA?.metrics['کندل']);
const fb = num(fA?.metrics['کندل']);
push('یک داده به هر دو پنل رفته (شمارۀ کندل یکی است)',
  kb != null && kb > 0 && kb === fb, { klinecharts: kb, ffc: fb, chartReqs });
push('درخواستِ چارت دقیقاً یک‌بار زده شده (تفکیک در فرانت است نه دو خواندن)',
  chartReqs === 1, { chartReqs });

const ko = num(kA?.metrics['لایه']);
const fo = num(fA?.metrics['لایه']);
push('لایه‌های FTS درِ هر دو موتور رفته‌اند (بي‌صفر)',
  ko != null && ko > 0 && fo != null && fo > 0, { klinecharts: ko, ffc: fo });

// کنترلِ سنسور ۱: لایه‌ها را خاموش کن — باید درِ هر دو به صفر افتد
await page.click('#lab-toggle-overlays');
await page.waitForTimeout(2200);
const kOff = num((await strip('klinecharts'))?.metrics['لایه']);
const fOff = num((await strip('ffc'))?.metrics['لایه']);
push('سنسورِ لایه کر نیست: خاموش‌کردن درِ هر دو صفر می‌دهد',
  kOff === 0 && fOff === 0, { klinecharts: kOff, ffc: fOff });
await page.click('#lab-toggle-overlays');
await page.waitForTimeout(1500);

// کنترلِ سنسور ۲: هفتگی — باید شمارۀ کندل عوض شود و درِ دو پنل یکی بماند
await page.click('#lab-tf-W');
await page.waitForTimeout(3000);
const kW = num((await strip('klinecharts'))?.metrics['کندل']);
const fW = num((await strip('ffc'))?.metrics['کندل']);
push('سنسورِ کندل کر نیست: تایم‌فریمِ هفتگی شمار را عوض می‌کند',
  kW != null && kW > 0 && kW !== kb && kW === fW, { daily: kb, weekly: kW, ffc_weekly: fW });
await page.click('#lab-tf-D');
await page.waitForTimeout(2500);

// اندازه‌گیریِ کارایی: یک دکمه، دو پنل، پنجرۀ ۳ ثانیه‌ای
await page.click('#lab-measure-all');
await page.waitForTimeout(4500);
const kM = await strip('klinecharts');
const fM = await strip('ffc');
const fpsK = num(kM?.metrics['فریم/ثانیه']);
const fpsF = num(fM?.metrics['فریم/ثانیه']);
const mountK = num(kM?.metrics['بالا‌آمدن']);
const mountF = num(fM?.metrics['بالا‌آمدن']);
push('کارایی درِ هر دو موتور اندازه گرفته شد (fps > ۰)',
  fpsK != null && fpsK > 0 && fpsF != null && fpsF > 0,
  { fps_klinecharts: fpsK, fps_ffc: fpsF });
push('زمانِ بالا‌آمدن درِ هر دو گزارش شد',
  mountK != null && mountK > 0 && mountF != null && mountF > 0,
  { mountMs_klinecharts: mountK, mountMs_ffc: mountF });

await page.screenshot({ path: `${OUT}.png`, fullPage: false });

// مرجعِ بیرونی: شمارۀ کندل‌های روزانۀ همان نماد از خودِ بک‌اند
let backendCandles: number | null = null;
try {
  const r = await fetch(`${BASE}/api/chart/${encodeURIComponent(SYM)}`);
  const j = (await r.json()) as { candles?: { close?: number }[] };
  backendCandles = Array.isArray(j.candles) ? j.candles.length : null;
} catch { backendCandles = null; }

const json = {
  base: BASE, at: new Date().toISOString(), symbol: SYM, viewport: '1366x768',
  backend_candles_daily: backendCandles,
  chart_requests: chartReqs,
  compare_table: await page.evaluate(() =>
    document.querySelector('[data-testid="lab-compare"]')?.textContent?.replace(/\s+/g, ' ').trim().slice(0, 900) ?? null),
  klinecharts: { before: kA?.metrics, measured: kM?.metrics, canvas: kM?.canvas, errors: kM?.errors },
  ffc: { before: fA?.metrics, measured: fM?.metrics, canvas: fM?.canvas, errors: fM?.errors },
  checks,
  passed: checks.filter((c) => c.ok).length,
  failed: checks.filter((c) => !c.ok).map((c) => c.n),
};
writeFileSync(`${OUT}.json`, JSON.stringify(json, null, 2), 'utf8');
for (const c of checks) console.log(`${c.ok ? 'PASS' : 'FAIL'}  ${c.n}  ${JSON.stringify(c.d ?? '')}`);
console.log(`\n${json.passed}/${checks.length} — خروجی: ${OUT}.json`);

await browser.close();
