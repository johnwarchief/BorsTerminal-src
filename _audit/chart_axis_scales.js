// _audit/chart_axis_scales.js — مرحلۀِ ۲: صحتِ مقیاسِ خطی و لگاریتمی، با عدد
//
// «درست بودنِ عدد درِ API» با «درست بودنِ جایگاهِ همانِ عدد رویِ بوم» یکی نیست. این
// هارنس همانِ تبدیل‌هایِ خودِ renderer را می‌سنجد (convertToPixel / convertFromPixel
// رویِ پنِ قیمت) و چهار چیز را می‌خواهد:
//   ۱) وارونِ دقیق: قیمت ← پیکسل ← قیمت بی‌خطا برگردد
//   ۲) خطی: Δp ثابت ⇒ Δy ثابت؛ لگاریتمی: Δln(p) ثابت ⇒ Δy ثابت
//   ۳) کنترلِ مثبت: عوض‌کردنِ مقیاس واقعاً پیکسل‌ها را تکان دهد (کنترلِ مرده نه)
//   ۴) پایداری: تازه‌سازیِ اندازه، جابه‌جایی (pan) و برگشت به مقیاسِ اول
// اجرا: node _audit/chart_axis_scales.js
const path = require('path');
const fs = require('fs');
const pw = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));
const ROOT = path.join(__dirname, '..');
const TAG = process.env.BORS_SCALES_TAG || 'final';
const OUT = path.join(ROOT, '_audit', `chart_axis_scales_${TAG}.json`);
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = process.env.BORS_BASE || 'http://localhost:5173';
const SYM = 'فولاد';

const MEASURE = (prices) => {
  const looks = (v) => !!v && typeof v === 'object' && typeof v.getDataList === 'function' && typeof v.getVisibleRange === 'function';
  const find = () => {
    let host = document.querySelector('canvas');
    while (host) {
      const fk = Object.keys(host).find((k) => k.startsWith('__reactFiber$'));
      if (fk) {
        let fiber = host[fk];
        for (let up = 0; fiber && up < 80; up++, fiber = fiber.return) {
          let hook = fiber.memoizedState;
          for (let g = 0; hook && g < 120; g++, hook = hook.next) {
            const ms = hook.memoizedState;
            if (looks(ms)) return ms;
            if (ms && typeof ms === 'object' && looks(ms.current)) return ms.current;
          }
        }
      }
      host = host.parentElement;
    }
    return null;
  };
  const c = find();
  if (!c) return { error: 'CHART_NOT_FOUND' };
  window.__borsChart = c;
  const pane = c.getSize('candle_pane', 'main');
  const dl = c.getDataList() || [];
  const vr = c.getVisibleRange();
  const vis = dl.slice(vr.from, vr.to);
  if (!vis.length) return { error: 'NO_VISIBLE_BARS' };
  const lo = Math.min(...vis.map((d) => d.low));
  const hi = Math.max(...vis.map((d) => d.high));
  const ys = (v) => {
    const r = c.convertToPixel([{ timestamp: vis[vis.length - 1].timestamp, value: v }], { paneId: 'candle_pane' });
    const one = (Array.isArray(r) ? r[0] : r) || {};
    return Number.isFinite(one.y) ? one.y : null;
  };
  const back = (y) => {
    const r = c.convertFromPixel([{ x: pane.left + pane.width / 2, y }], { paneId: 'candle_pane' });
    const one = (Array.isArray(r) ? r[0] : r) || {};
    return Number.isFinite(one.value) ? one.value : null;
  };
  const picks = (prices && prices.length ? prices : [lo, lo + (hi - lo) * 0.25, lo + (hi - lo) * 0.5, lo + (hi - lo) * 0.75, hi])
    .filter((p) => p > 0);
  const pts = picks.map((p) => { const y = ys(p); return { price: p, y, back: y == null ? null : back(y) }; });
  const slopes = [];
  for (let i = 1; i < pts.length; i++) {
    if (pts[i].y == null || pts[i - 1].y == null) continue;
    const dp = pts[i].price - pts[i - 1].price;
    if (Math.abs(dp) < 1e-9) continue;
    slopes.push({ pair: [pts[i - 1].price, pts[i].price], dy: pts[i].y - pts[i - 1].y, dp,
                  dln: Math.log(pts[i].price / pts[i - 1].price) });
  }
  const axisEdges = { top: back(pane.top + 1), bottom: back(pane.top + pane.height - 1) };
  const bad = vis.filter((d) => !(d.low <= Math.min(d.open, d.close) + 1e-9 && d.high >= Math.max(d.open, d.close) - 1e-9 && d.low <= d.high));
  return {
    pane: { w: Math.round(pane.width), h: Math.round(pane.height), top: Math.round(pane.top), left: Math.round(pane.left) },
    visible: { bars: vis.length, lo, hi, nonPositive: vis.filter((d) => d.low <= 0 || d.close <= 0).length, geometryViolations: bad.length },
    points: pts, slopes, axisEdges,
    yAxisName: (() => { try { return c.getStyles().candle ? undefined : undefined; } catch (e) { return undefined; } })(),
  };
};

const analyse = (m) => {
  if (!m || m.error) return { error: (m || {}).error };
  const rt = m.points.filter((p) => p.back != null).map((p) => Math.abs(p.back - p.price) / p.price);
  const rtMax = rt.length ? Math.max(...rt) : null;
  const dyPerP = m.slopes.map((s) => s.dy / s.dp);
  const dyPerLn = m.slopes.map((s) => s.dy / s.dln);
  const spread = (a) => { const mn = Math.min(...a), mx = Math.max(...a); return mn === 0 ? null : Math.abs(mx / mn - 1); };
  // فاصلۀِ پیکسلیِ دو جفتِ هم‌نسبت (کنترلِ قانونِ لگاریتم)
  let ratioPair = null;
  for (let i = 0; i + 1 < m.slopes.length; i++) {
    for (let j = i + 1; j < m.slopes.length; j++) {
      const a = m.slopes[i], b = m.slopes[j];
      const ra = a.pair[1] / a.pair[0], rb = b.pair[1] / b.pair[0];
      if (Math.abs(ra - rb) / ra < 0.02 && Math.abs(a.dy - b.dy) <= 1.5) { ratioPair = { ratio: ra, dyA: a.dy, dyB: b.dy }; break; }
    }
    if (ratioPair) break;
  }
  // گامِ هر پیکسل رویِ محور (خطی و لگاریتمی) — خطایِ وارون نباید ازِ یکِ پیکسل bigger باشد
  const stepLin = (m.axisEdges.top != null && m.axisEdges.bottom != null && m.pane.h)
    ? Math.abs(m.axisEdges.top - m.axisEdges.bottom) / m.pane.h : null;
  const stepLog = (m.axisEdges.top > 0 && m.axisEdges.bottom > 0 && m.pane.h)
    ? Math.abs(Math.log(m.axisEdges.top) - Math.log(m.axisEdges.bottom)) / m.pane.h : null;
  const pxErr = m.points.filter((p) => p.back != null).map((p) => {
    const dy = Math.abs((m.points.find((q) => q.price === p.back) || {}).y ?? NaN);
    return Number.isFinite(dy) ? 0 : Math.abs(p.back - p.price) / (stepLin || 1);
  });
  const maxBackPx = pxErr.length ? Math.max(...pxErr.map(Math.abs)) : null;
  return {
    roundTripMaxRelErr: rtMax,
    pricePerPixelLinear: stepLin, logPerPixel: stepLog, roundTripMaxAsPriceSteps: maxBackPx,
    linearSlopeSpread: dyPerP.length > 1 ? spread(dyPerP.map(Math.abs)) : null,
    logSlopeSpread: dyPerLn.length > 1 ? spread(dyPerLn.map(Math.abs)) : null,
    equalRatioPairPixels: ratioPair,
    monotoneAxis: m.axisEdges.top != null && m.axisEdges.bottom != null && m.axisEdges.top > m.axisEdges.bottom,
  };
};

const setScale = async (page, which) => {
  // تریگرِ درستِ گفت‌وگویِ تنظیماتِ چارت؛ «technical-fts-settings» دکمۀِ دیگری است
  // (تنظیماتِ پیش‌شرط‌های FTS) و نخستین اجرایِ همین هارنس همان را زد و نتیجه
  // «بی‌تغییریِ پیکسل» گزارش کرد — خطایِ ابزار، نه خطایِ محصول.
  await page.click('button[title="تنظیمات چارت"]').catch(() => {});
  await page.waitForTimeout(1200);
  await page.click('[data-testid="settings-tab-scales"]').catch(() => {});
  await page.waitForTimeout(900);
  const label = which === 'logarithm' ? 'لگاریتمی' : 'خطی';
  await page.locator('[data-testid="chart-settings"] button', { hasText: label }).first()
    .click({ timeout: 6000 }).catch(() => {});
  await page.waitForTimeout(2600);
  await page.click('[data-testid="chart-settings-done"]').catch(() => {});
  await page.waitForTimeout(2200);
};

(async () => {
  const ctx = await pw.chromium.launchPersistentContext(
    fs.mkdtempSync(path.join(require('os').tmpdir(), 'bors-scales-')),
    { executablePath: EXE, viewport: null, args: ['--no-first-run', '--disable-sync'] });
  const page = ctx.pages()[0] || await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 160)));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('CONSOLE ' + m.text().slice(0, 140)); });
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  if (await page.waitForSelector('input[type=password]', { timeout: 20000 }).then(() => true).catch(() => false)) {
    await page.locator('input[type="text"]').first().fill('admin');
    await page.locator('input[type="password"]').first().fill('bors123');
    await page.locator('button[type="submit"]').first().click();
    await page.waitForFunction(() => !document.querySelector('input[type=password]'), null, { timeout: 30000 }).catch(() => {});
  }
  await page.evaluate((s) => { location.hash = '#/technical/' + encodeURIComponent(s); }, SYM);
  await page.waitForFunction(() => document.querySelectorAll('canvas').length > 0, null, { timeout: 90000 });
  await page.click('[data-testid="timeframe-D"]').catch(() => {});
  await page.waitForTimeout(6000);

  const rep = { ranAt: new Date().toISOString(), symbol: SYM, viewport: [1366, 768], steps: {} };
  // نخستین سنجش بی‌صبرِ داده، «NO_VISIBLE_BARS» می‌داد — آن را با شرطِ واقعیِ داده منتظر می‌کنیم
  await page.waitForFunction(() => {
    const cs = [...document.querySelectorAll('canvas')];
    return cs.length > 0 && !!window.__borsChart && (window.__borsChart.getDataList?.() || []).length > 0;
  }, null, { timeout: 15000 }).catch(() => {});
  rep.steps.warm = await page.evaluate(MEASURE, []);
  for (let i = 0; i < 12 && (rep.steps.warm.error === 'NO_VISIBLE_BARS'); i++) {
    await page.waitForTimeout(2500);
    rep.steps.warm = await page.evaluate(MEASURE, []);
  }
  rep.steps.linear = rep.steps.warm;
  rep.steps.linearAnalysis = analyse(rep.steps.linear);

  await setScale(page, 'logarithm');
  rep.steps.log = await page.evaluate(MEASURE, []);
  rep.steps.logAnalysis = analyse(rep.steps.log);
  const moved = (rep.steps.linear.points || []).map((p, i) => {
    const q = (rep.steps.log.points || [])[i];
    return q && p.y != null && q.y != null ? Math.abs(p.y - q.y) : null;
  }).filter((v) => v != null);
  rep.positiveControl = { maxPixelShift: moved.length ? Math.max(...moved) : null, scaleActuallyChanged: moved.length > 0 && Math.max(...moved) > 2 };
  await page.screenshot({ path: path.join(ROOT, '_audit', `scales_log_${TAG}.png`) });

  // پایداری زیرِ تغییرِ اندازه
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.waitForTimeout(2500);
  rep.steps.logAt1600 = await page.evaluate(MEASURE, []);
  rep.steps.logAt1600Analysis = analyse(rep.steps.logAt1600);

  // جابه‌جایی افقی: جایِ یکِ قیمتِ ثابت نباید رویِ محورِ عمود تکان بخورد
  const prices = (rep.steps.log.points || []).map((p) => p.price).filter(Number.isFinite);
  await page.mouse.move(700, 300);
  await page.mouse.down(); await page.mouse.move(880, 300, { steps: 8 }); await page.mouse.up();
  await page.waitForTimeout(1500);
  rep.steps.logAfterPan = await page.evaluate(MEASURE, prices);
  rep.steps.logAfterPanAnalysis = analyse(rep.steps.logAfterPan);
  const yBefore = (rep.steps.log.points || []).map((p) => p.y);
  const yAfter = (rep.steps.logAfterPan.points || []).map((p) => p.y);
  rep.panKeepsVertical = yBefore.length && yAfter.length
    ? Math.max(...yBefore.map((y, i) => (yAfter[i] != null && Number.isFinite(y)) ? Math.abs(y - yAfter[i]) : 0)) : null;

  // برگشت به خطی
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.waitForTimeout(1500);
  await setScale(page, 'normal');
  rep.steps.backToLinear = await page.evaluate(MEASURE, prices);
  const b2 = (rep.steps.backToLinear.points || []).map((p) => p.y);
  rep.reversibilityMaxPixelErr = yBefore.length && b2.length ? Math.max(...yBefore.map((y, i) => (b2[i] != null ? Math.abs(y - b2[i]) : 999))) : null;
  rep.steps.backToLinearAnalysis = analyse(rep.steps.backToLinear);
  await page.screenshot({ path: path.join(ROOT, '_audit', `scales_linear_${TAG}.png`) });

  rep.storedSettings = await page.evaluate(() => { try { return JSON.parse(localStorage.getItem('fts.chart.settings.v1') || 'null'); } catch (e) { return null; } });
  rep.pageErrors = errs.slice(0, 10);
  rep.verdict = {
    linearRoundTrip: (rep.steps.linearAnalysis.roundTripMaxAsPriceSteps ?? 99) < 2,
    linearIsLinear: (rep.steps.linearAnalysis.linearSlopeSpread ?? 1) < 0.02,
    logIsLogarithmic: (rep.steps.logAnalysis.logSlopeSpread ?? 1) < 0.05,
    linearStopsBeingLinearUnderLog: (rep.steps.logAnalysis.linearSlopeSpread ?? 0) > 0.05,
    logRoundTrip: (rep.steps.logAnalysis.roundTripMaxAsPriceSteps ?? 99) < 2,
    positiveControl: rep.positiveControl.scaleActuallyChanged,
    logAxisMonotone: !!rep.steps.logAnalysis.monotoneAxis,
    resizeHolds: (rep.steps.logAt1600Analysis.roundTripMaxAsPriceSteps ?? 99) < 2,
    panKeepsInverseExact: ((rep.steps.logAfterPanAnalysis || {}).roundTripMaxAsPriceSteps ?? 99) < 2,
    // برگشت‌پذیری را با «قانونِ» محور می‌سنجیم، نه با پیکسلِ مطلق: پس ازِ pan و
    // resize بازۀِ خودکار عوض می‌شود، پس مقایسۀِ yِ خام بی‌معناست.
    reversibleToLinearLaw: (rep.steps.backToLinearAnalysis.linearSlopeSpread ?? 1) < 0.02
      && (rep.steps.backToLinearAnalysis.logSlopeSpread ?? 0) > 0.05,
    reversibleRoundTrip: (rep.steps.backToLinearAnalysis.roundTripMaxAsPriceSteps ?? 99) < 2,
    noNonPositivePrices: (rep.steps.log.visible || {}).nonPositive === 0,
    noGeometryViolations: (rep.steps.log.visible || {}).geometryViolations === 0,
  };
  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
  console.log('linear : ' + JSON.stringify(rep.steps.linearAnalysis));
  console.log('log    : ' + JSON.stringify(rep.steps.logAnalysis));
  console.log('1600   : ' + JSON.stringify(rep.steps.logAt1600Analysis));
  console.log('after pan: ' + JSON.stringify(rep.steps.logAfterPanAnalysis) + '   Δy(autofit): ' + + rep.panKeepsVertical + '   reverse Δy: ' + rep.reversibilityMaxPixelErr + '   positive control: ' + JSON.stringify(rep.positiveControl));
  console.log('VERDICT: ' + JSON.stringify(rep.verdict));
  console.log('written: ' + OUT);
  await ctx.close();
  process.exit(Object.values(rep.verdict).every(Boolean) ? 0 : 1);
})().catch((e) => { console.error('HARNESS FAILED: ' + ((e && e.stack) || e)); process.exit(2); });
