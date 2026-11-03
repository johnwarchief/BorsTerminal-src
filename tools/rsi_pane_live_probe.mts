/**
 * tools/rsi_pane_live_probe.mts — اثبات زندهٔ پنلِ نوسان‌گر با پیکسل
 *
 * دو اشتباهی که این سنجه باید از آن‌ها عبور می‌کرد و در نسخۀ اول عبور نکرد:
 * ۱) page.evaluate با *رشتۀ* «() => {...}» مقدارِ خودِ تابع را برمی‌گرداند نه
 *    نتیجه‌اش؛ خروجی null می‌شد و هر سنجهٔ بعدی کور. اینجا تابعِ واقعی پاس می‌شود.
 * ۲) «کنترلِ مثبت» روی دادهٔ خالی همیشه سبز است. پس هر ادعا در همین اجرا با
 *    دو دست‌کاریِ واقعی سنجیده می‌شود: خاموش‌کردنِ سوییچ (پنل باید برود) و
 *    عوض‌کردنِ دراپ‌داون (خطِ رسم‌شده باید عوض شود).
 *
 * جوهرِ پنل با «اختلافِ هر کانال از رنگِ پس‌زمینۀ خودِ پنل» شمارش می‌شود، نه
 * با اشباعِ رنگ: خطِ پیش‌فرضِ اندیکاتور ممکن است کم‌رنگ باشد.
 *
 * پیش‌نیاز: vite روی ۵۱۸۰ + بک‌اند روی ۸۱۰۱.
 * Run: node --no-warnings tools/rsi_pane_live_probe.mts
 */
import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';

const require = createRequire('C:/Users/PCMOD/');
const { chromium } = require('playwright-core');

const EXE = process.env.JEV_CHROME || 'C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const SYMBOL = process.env.SYMBOL || 'فولاد';
const BASE = `http://localhost:5180/#/technical/${encodeURIComponent(SYMBOL)}`;
const OUTDIR = 'C:/Users/PCMOD/Desktop/BorsTerminal/_audit/rsi-pane-live';

mkdirSync(OUTDIR, { recursive: true });

const results: { name: string; pass: boolean; detail?: unknown }[] = [];
const check = (name: string, pass: boolean, detail?: unknown) => {
  results.push({ name, pass, detail });
  console.log(`${pass ? 'PASS' : 'FAIL'} | ${name} | ${JSON.stringify(detail ?? {})}`);
};

/**
 * چیدمانِ لایه‌های canvas و پروفایلِ جوهرِ عمودیِ چارت.
 * paneHeight = ارتفاعِ ردیفِ محتوایِ پایین (پنلِ نوسان‌گر)، صفر اگر هست.
 */
function readChart() {
  const wrap = document.querySelector('[data-testid="kline-chart-wrapper"]');
  if (!wrap) return { error: 'wrapper-missing' as const };
  const wr = wrap.getBoundingClientRect();
  const canvases = [...wrap.querySelectorAll('canvas')];

  type Layer = { w: number; h: number; top: number; kind: string };
  const layers: Layer[] = canvases.map((c) => {
    const r = c.getBoundingClientRect();
    const w = Math.round(r.width);
    const h = Math.round(r.height);
    const top = Math.round(r.top - wr.top);
    const kind = h <= 30 ? 'xaxis' : w <= 80 ? 'yaxis' : 'main';
    return { w, h, top, kind };
  });

  // ردیف‌های محتواییِ متمایز (main)، به‌ترتیبِ بالا به پایین
  const rows = [...new Map(layers.filter((l) => l.kind === 'main').map((l) => [`${l.top}`, l])).values()].sort(
    (a, b) => a.top - b.top
  );

  const off = document.createElement('canvas');
  off.width = Math.max(1, Math.round(wr.width));
  off.height = Math.max(1, Math.round(wr.height));
  const ctx = off.getContext('2d', { willReadFrequently: true });
  if (!ctx) return { error: 'no-2d-context' as const };
  for (const c of canvases) {
    const r = c.getBoundingClientRect();
    ctx.drawImage(c, Math.round(r.left - wr.left), Math.round(r.top - wr.top), Math.round(r.width), Math.round(r.height));
  }
  const { data } = ctx.getImageData(0, 0, off.width, off.height);

  // پس‌زمینۀ خودِ چارت از گوشۀ پایین-چپِ ردیفِ آخر
  const bgIdx = rows.length ? Math.min(off.height - 1, rows[rows.length - 1].top + 2) * off.width * 4 : 0;
  const bg = [data[bgIdx], data[bgIdx + 1], data[bgIdx + 2]];

  const inkRow: number[] = new Array(off.height).fill(0);
  for (let y = 0; y < off.height; y++) {
    for (let x = 0; x < off.width; x++) {
      const i = (y * off.width + x) * 4;
      const d =
        Math.abs(data[i] - bg[0]) + Math.abs(data[i + 1] - bg[1]) + Math.abs(data[i + 2] - bg[2]);
      if (d > 40) inkRow[y]++;
    }
  }
  return { error: null as null, rows, inkRow, width: off.width, height: off.height, canvasCount: canvases.length, bg };
}

function bandInk(prof: ReturnType<typeof readChart>, top: number, height: number) {
  if (prof.error || !prof.inkRow) return { rowsWithInk: 0, peak: 0, total: 0 };
  const slice = prof.inkRow.slice(top, top + height);
  const rowsWithInk = slice.filter((v) => v >= 2).length;
  return { rowsWithInk, peak: Math.max(0, ...slice), total: slice.reduce((a, b) => a + b, 0) };
}

const browser = await chromium.launch({ headless: true, executablePath: EXE });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

const failedRequests: Record<string, number> = {};
page.on('response', (r) => {
  if (r.status() >= 400) {
    const key = `${r.status()} ${r.url().replace(/^http:\/\/localhost:5180/, '').slice(0, 60)}`;
    failedRequests[key] = (failedRequests[key] || 0) + 1;
  }
});

await page.goto(BASE, { waitUntil: 'networkidle' });
await page.waitForTimeout(2500);

const before = await page.evaluate(readChart);
check('chart renders and the probe can read it', !before.error && before.canvasCount > 0, {
  error: before.error,
  canvasCount: before.canvasCount,
  contentRows: before.rows?.length,
});
await page.screenshot({ path: `${OUTDIR}/01_before.png` });

await page.getByTestId('drawer-tab-indicators').click();
await page.waitForTimeout(400);
const toggle = page.getByTestId('toggle-indicator-RsiMaSmooth');
check('RsiMaSmooth toggle exists in the indicators panel', (await toggle.count()) === 1, { count: await toggle.count() });

await toggle.click();
await page.waitForTimeout(2000);
const after = await page.evaluate(readChart);

const rowsBefore = before.rows ?? [];
const rowsAfter = after.rows ?? [];
const lowerRow = rowsAfter.length > rowsBefore.length ? rowsAfter[rowsAfter.length - 1] : undefined;
check('a second content pane is mounted below the price pane', !!lowerRow && rowsAfter.length === rowsBefore.length + 1, {
  before: rowsBefore.map((r) => [r.top, r.h]),
  after: rowsAfter.map((r) => [r.top, r.h]),
});
check('the new pane is the oscillator pane, about 100px tall', !!lowerRow && lowerRow.h >= 90 && lowerRow.h <= 110, {
  height: lowerRow?.h,
});

const lowerInk = bandInk(after, lowerRow?.top ?? 0, lowerRow?.h ?? 0);
check('pixels are actually drawn inside the new pane', lowerInk.rowsWithInk > 5, lowerInk);
await page.screenshot({ path: `${OUTDIR}/02_rsi_pane_on.png` });

// کنترلِ مثبت ۱: خانوادۀ RSI را هم روشن کن — باید پنلِ *جداگانه* بگیرد،
// آنگاه دراپ‌داون هم ظاهر می‌شود و عوض‌کردنش باید شکلِ خط را عوض کند
const multiToggle = page.getByTestId('toggle-indicator-MultiVariantRSI');
check('MultiVariantRSI toggle exists', (await multiToggle.count()) === 1, { count: await multiToggle.count() });
await multiToggle.click();
await page.waitForTimeout(1800);
const withTwo = await page.evaluate(readChart);
check('each oscillator gets its own pane (two rows below the price now)', (withTwo.rows?.length ?? 0) === rowsBefore.length + 2, {
  rows: (withTwo.rows ?? []).map((r) => [r.top, r.h]),
});
await page.screenshot({ path: `${OUTDIR}/03_two_oscillator_panes.png` });

const variantSelect = page.getByTestId('rsi-variant-select');
const hasSelect = (await variantSelect.count()) === 1;
let profileChanged: unknown = { skipped: 'rsi-variant-select absent even with MultiVariantRSI on' };
if (hasSelect) {
  // کدام ردیف مالِ خانوادۀ RSI است؟ قطعی نمی‌دانم، پس «کلِ منطقۀ پایینِ چارتِ قیمت»
  // را می‌سنجم: اگر هر پنلی واقعاً با دراپ‌داون عوض شود، اینجا دیده می‌شود.
  const priceBottom = (withTwo.rows ?? [])[0]?.top ?? 0;
  const priceHeight = (withTwo.rows ?? [])[0]?.h ?? 0;
  const regionTop = priceBottom + priceHeight + 1;
  const beforeCurve = (withTwo.inkRow ?? []).slice(regionTop);
  await variantSelect.selectOption({ value: 'fibo' });
  await page.waitForTimeout(2000);
  const selected = await variantSelect.inputValue();
  const afterSwap = await page.evaluate(readChart);
  const afterCurve = (afterSwap.inkRow ?? []).slice(regionTop);
  const diff = beforeCurve.reduce((a, v, i) => a + Math.abs(v - (afterCurve[i] ?? 0)), 0);
  profileChanged = { regionTop, selectedValue: selected, inkBefore: beforeCurve.reduce((a, b) => a + b, 0), inkAfter: afterCurve.reduce((a, b) => a + b, 0), diffPixels: diff };
  check('POSITIVE CONTROL 1: the dropdown visibly redraws a pane', diff > 200, profileChanged);
  await page.screenshot({ path: `${OUTDIR}/04_variant_swapped.png` });
  await variantSelect.selectOption({ index: 0 });
  await page.waitForTimeout(1200);
} else {
  check('POSITIVE CONTROL 1: the dropdown visibly redraws a pane', false, profileChanged);
}

// کنترلِ مثبت ۲: خاموش‌کردنِ هر دو باید به تک‌پنلِ اول برگردد
await multiToggle.click();
await page.waitForTimeout(1200);
await toggle.click();
await page.waitForTimeout(1800);
const off = await page.evaluate(readChart);
check('POSITIVE CONTROL 2: switching off removes the pane', (off.rows?.length ?? 0) === rowsBefore.length, {
  rowsOff: (off.rows ?? []).map((r) => [r.top, r.h]),
  canvasCount: off.canvasCount,
});
await page.screenshot({ path: `${OUTDIR}/04_rsi_pane_off.png` });

check('no failed network requests', Object.keys(failedRequests).length === 0, failedRequests);

writeFileSync(
  `${OUTDIR}/probe.json`,
  JSON.stringify(
    {
      symbol: SYMBOL,
      viewport: '1440x900',
      method: 'canvas layer rows + per-row ink measured against the pane background',
      before: { canvasCount: before.canvasCount, rows: before.rows, width: before.width, height: before.height },
      after: { canvasCount: after.canvasCount, rows: after.rows, lowerInk: bandInk(after, lowerRow?.top ?? 0, lowerRow?.h ?? 0) },
      off: { canvasCount: off.canvasCount, rows: off.rows },
      positiveControls: { dropdown: profileChanged },
      failedRequests,
      results,
      passed: results.filter((r) => r.pass).length,
      total: results.length,
    },
    null,
    2
  )
);

console.log(`\n${results.filter((r) => r.pass).length}/${results.length} checks passed`);
console.log(`evidence: ${OUTDIR}`);
await browser.close();
