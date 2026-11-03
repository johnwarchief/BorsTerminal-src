// _audit/chart_log_cause.js — چرا درِ لگاریتمی کندل‌ها به کفِ پن می‌چسبند؟
//
// آزمونِ حذفِ مرحله‌ای: درِ مقیاسِ لگاریتمی، یکی‌یکی لایه‌هایی را که مقدارشان درِ
// مرتبۀِ میلیارد است (نمایندۀِ حجم) یا رویِ پنِ قیمت رسم می‌شود خاموش می‌کنیم و
// هر بار دو انتهای محورِ قیمت را می‌خوانیم. هر لایه‌ای که با خاموش‌کردنش بازِ
// محور ازِ میلیارد به هزارتو‌ها برگردد، علت است.
// اجرا: node _audit/chart_log_cause.js
const path = require('path');
const fs = require('fs');
const pw = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));
const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, '_audit', 'chart_log_cause.json');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = process.env.BORS_BASE || 'http://localhost:5173';
const SYM = 'فولاد';

const AXES = () => {
  const looks = (v) => !!v && typeof v === 'object' && typeof v.getDataList === 'function';
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
  if (!c) return { error: 'NO_CHART' };
  window.__borsChart = c;
  const pane = c.getSize('candle_pane', 'main');
  const at = (y) => {
    const r = c.convertFromPixel([{ x: pane.left + pane.width / 2, y }], { paneId: 'candle_pane' });
    const one = (Array.isArray(r) ? r[0] : r) || {};
    return Number.isFinite(one.value) ? one.value : null;
  };
  const vr = c.getVisibleRange();
  const vis = (c.getDataList() || []).slice(vr.from, vr.to);
  const yOf = (v) => {
    const r = c.convertToPixel([{ timestamp: vis.length ? vis[vis.length - 1].timestamp : Date.now(), value: v }], { paneId: 'candle_pane' });
    const one = (Array.isArray(r) ? r[0] : r) || {};
    return Number.isFinite(one.y) ? one.y : null;
  };
  const lo = vis.length ? Math.min(...vis.map((d) => d.low)) : null;
  const hi = vis.length ? Math.max(...vis.map((d) => d.high)) : null;
  return {
    paneH: Math.round(pane.height), bars: vis.length, dataLo: lo, dataHi: hi,
    axisTop: at(pane.top + 1), axisBottom: at(pane.top + pane.height - 1),
    yOfDataLo: lo != null ? yOf(lo) : null, yOfDataHi: hi != null ? yOf(hi) : null,
    indicators: (c.getIndicators?.() ?? []).map((i) => ({ name: i.name, paneId: i.paneId })),
    overlays: (c.getOverlays?.() ?? []).length,
  };
};

const setScale = async (page, label) => {
  await page.click('button[title="تنظیمات چارت"]').catch(() => {});
  await page.waitForTimeout(1200);
  await page.click('[data-testid="settings-tab-scales"]').catch(() => {});
  await page.waitForTimeout(900);
  await page.locator('[data-testid="chart-settings"] button', { hasText: label }).first().click({ timeout: 6000 }).catch(() => {});
  await page.waitForTimeout(2600);
  await page.click('[data-testid="chart-settings-done"]').catch(() => {});
  await page.waitForTimeout(2200);
};

(async () => {
  const ctx = await pw.chromium.launchPersistentContext(
    fs.mkdtempSync(path.join(require('os').tmpdir(), 'bors-logcause-')),
    { executablePath: EXE, viewport: null, args: ['--no-first-run', '--disable-sync'] });
  const page = ctx.pages()[0] || await ctx.newPage();
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
  await page.waitForTimeout(7000);
  await page.evaluate(AXES);
  await page.waitForTimeout(1500);

  const rep = { ranAt: new Date().toISOString(), steps: {} };
  rep.steps.linear = await page.evaluate(AXES);
  await setScale(page, 'لگاریتمی');
  rep.steps.logAll = await page.evaluate(AXES);

  // ۱) حجم ازِ پنِ فرعی برداشته شود
  rep.steps.afterRemoveVol = await page.evaluate(() => {
    const c = window.__borsChart;
    const removed = c.removeIndicator({ paneId: 'sub_pane_vol' });
    return { removed, stillThere: (c.getIndicators?.() ?? []).map((i) => i.name + '@' + i.paneId) };
  });
  await page.waitForTimeout(2500);
  rep.steps.logNoVol = await page.evaluate(AXES);

  // ۲) اورلی‌هایِ FTS هم برداشته شوند
  rep.steps.afterRemoveOverlays = await page.evaluate(() => {
    const c = window.__borsChart;
    const n = (c.getOverlays?.() ?? []).length;
    c.removeOverlay();
    return { hadOverlays: n, now: (c.getOverlays?.() ?? []).length };
  });
  await page.waitForTimeout(2500);
  rep.steps.logNoOverlays = await page.evaluate(AXES);
  await page.screenshot({ path: path.join(ROOT, '_audit', 'logcause_log_novol_nooverlays.png') });

  const sane = (m) => m && Number.isFinite(m.axisTop) && m.dataHi && m.axisTop < m.dataHi * 4;
  rep.reading = {
    linearSane: sane(rep.steps.linear),
    logAllSane: sane(rep.steps.logAll),
    logNoVolSane: sane(rep.steps.logNoVol),
    logNoOverlaysSane: sane(rep.steps.logNoOverlays),
    axisTopLinear: rep.steps.linear.axisTop,
    axisTopLogAll: rep.steps.logAll.axisTop,
    axisTopLogNoVol: rep.steps.logNoVol.axisTop,
    axisTopLogNoOverlays: rep.steps.logNoOverlays.axisTop,
    dataHi: rep.steps.linear.dataHi,
    conclusion: sane(rep.steps.logNoVol) && !sane(rep.steps.logAll)
      ? 'LOG_RANGE_INCLUDES_VOLUME: حجمِ پنِ فرعی واردِ بازۀِ لگاریتمیِ پنِ قیمت می‌شود'
      : (sane(rep.steps.logNoOverlays) && !sane(rep.steps.logNoVol)
        ? 'OVERLAY_VALUES_ENTER_LOG_RANGE: مقدارهایِ اورلیِ FTS بازۀِ لگاریتمی را می‌ترکانند'
        : 'LOG_RANGE_STILL_BROKEN_WITHOUT_VOL_AND_OVERLAYS: علت درِ خودِ تبدیلِ محور است'),
  };
  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
  console.log('linear      : ' + JSON.stringify(rep.steps.linear).slice(0, 220));
  console.log('log all     : ' + JSON.stringify(rep.steps.logAll).slice(0, 220));
  console.log('log no vol  : ' + JSON.stringify(rep.steps.logNoVol).slice(0, 220));
  console.log('log no over : ' + JSON.stringify(rep.steps.logNoOverlays).slice(0, 220));
  console.log('READING     : ' + JSON.stringify(rep.reading, null, 1));
  console.log('written: ' + OUT);
  await ctx.close();
})().catch((e) => { console.error('FAILED: ' + ((e && e.stack) || e)); process.exit(1); });
