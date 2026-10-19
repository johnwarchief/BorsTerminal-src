// _audit/chart_log_scale_probe.js — مقیاسِ لگاریتمی: مرگِ کنترل یا مرگِ رندر؟
//
// سه راه برایِ رسیدن به «لگاریتمی» و سنجشِ اثرِ هرِ یک رویِ پیکسل‌ها:
//   الف) همانِ مسیری که کاربر می‌رود: دکمۀِ تنظیمات → زبانهٔ «مقیاس‌ها» → «لگاریتمی»
//   ب) نوشتنِ مستقیمِ استور (setPriceScale) — اگر «الف» بی‌اثر بود و «ب» اثر کرد،
//      نقص درِ رابط است؛ اگر هیچ‌کدام اثر نکرد، مقیاس درِ رندر مرده است
//   پ) خواندنِ وضعیتِ واقعیِ محور با دو نقطهٔ شناخته‌شده (قانونِ خطی در برابرِ لگاریتمی)
// اجرا: node _audit/chart_log_scale_probe.js
const path = require('path');
const fs = require('fs');
const pw = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));
const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, '_audit', 'chart_log_scale_probe.json');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = process.env.BORS_BASE || 'http://localhost:5173';
const SYM = 'فولاد';

const AX = () => {
  const looks = (v) => !!v && typeof v === 'object' && typeof v.getDataList === 'function';
  const find = () => {
    let host = document.querySelector('canvas');
    while (host) {
      const fk = Object.keys(host).find((k) => k.startsWith('__reactFiber$'));
      if (fk) { let fiber = host[fk];
        for (let up = 0; fiber && up < 80; up++, fiber = fiber.return) {
          let hook = fiber.memoizedState;
          for (let g = 0; hook && g < 120; g++, hook = hook.next) {
            const ms = hook.memoizedState;
            if (looks(ms)) return ms;
            if (ms && typeof ms === 'object' && looks(ms.current)) return ms.current;
          }
        } }
      host = host.parentElement;
    } return null;
  };
  const c = find();
  if (!c) return { error: 'NO_CHART' };
  window.__borsChart = c;
  const pane = c.getSize('candle_pane', 'main');
  const vr = c.getVisibleRange();
  const vis = (c.getDataList() || []).slice(vr.from, vr.to);
  if (!vis.length) return { error: 'NO_BARS' };
  const yOf = (v) => {
    const r = c.convertToPixel([{ timestamp: vis[vis.length - 1].timestamp, value: v }], { paneId: 'candle_pane' });
    const one = (Array.isArray(r) ? r[0] : r) || {};
    return Number.isFinite(one.y) ? one.y : null;
  };
  const lo = Math.min(...vis.map((d) => d.low)), hi = Math.max(...vis.map((d) => d.high));
  const span = hi - lo;
  // سه قیمتِ شناخته‌شده: پایین، میانهٔ حسابی، میانهٔ هندسی
  const a = lo + span * 0.02, b = lo + span * 0.50, g = Math.sqrt(a * b);
  const ya = yOf(a), yb = yOf(b), yg = yOf(g);
  const linearMid = ya != null && yb != null ? (ya + yb) / 2 : null;
  return {
    lo, hi, a, b, g, ya, yb, yg,
    // درِ مقیاسِ خطی، میانهٔ حسابی دقیقاً وسطِ پیکسلی است؛ درِ لگاریتمی، میانهٔ هندسی
    midArithPixelOffset: linearMid != null && ya != null ? Math.abs(ya + (yb - ya) * 0.5 - yb) : null,
    geometricMidDeltaPx: (yg != null && linearMid != null) ? Math.abs(yg - linearMid) : null,
    arithMid: b, ya, yb,
    paneH: Math.round(pane.height),
    // درِ مقیاسِ لگاریتمی، میانۀِ هندسی دقیقاً وسطِ پیکسلیِ دو سرِ بازه است
    isLog: (function () {
      const ps = [a, g, b].filter((v) => v > 0);
      const ys2 = ps.map(yOf);
      if (ys2.some((v) => v == null)) return null;
      const dln = [Math.log(ps[1] / ps[0]), Math.log(ps[2] / ps[1])];
      const dy = [ys2[1] - ys2[0], ys2[2] - ys2[1]];
      const k = dy.map((v, i) => v / dln[i]);
      const dp = [ps[1] - ps[0], ps[2] - ps[1]];
      const kl = dy.map((v, i) => v / dp[i]);
      const spread = (arr) => Math.abs(Math.max(...arr) / Math.min(...arr) - 1);
      return spread(k) < 0.02 && spread(kl) > 0.05;
    })(),
    // درِ مقیاسِ خطی، میانۀِ حسابی وسطِ پیکسلی است
    isLinear: (yb != null && ya != null) ? Math.abs(((ya + yb) / 2) - yOf(lo + (hi - lo) * 0.5)) < 2 : null,
  };
};

(async () => {
  const ctx = await pw.chromium.launchPersistentContext(
    fs.mkdtempSync(path.join(require('os').tmpdir(), 'bors-logprobe-')),
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
  await page.waitForFunction(() => !!window.__borsChart && (window.__borsChart.getDataList?.() || []).length > 0, null, { timeout: 90000 }).catch(() => {});
  await page.evaluate(AX);  // warm: first call installs the handle
  await page.waitForTimeout(4000);

  const rep = { ranAt: new Date().toISOString(), steps: {} };
  rep.steps.linear = await page.evaluate(AX);

  // الف) رابطِ کاربری
  rep.trigger = await page.evaluate(() => {
    let host = document.querySelector('button[title="تنظیمات چارت"]');
    if (!host) {
      host = [...document.querySelectorAll('button')].find((b) => /تنظیمات\s*چارت/.test(b.getAttribute('title') || ''));
    }
    if (!host) return { present: false };
    const b = host.matches('button') ? host : host.querySelector('button');
    const r = (b || host).getBoundingClientRect();
    return { present: true, hasButton: !!b, tag: (b || host).tagName, text: (b.textContent || host.textContent || '').trim().slice(0, 24),
             x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), w: Math.round(r.width), h: Math.round(r.height),
             expanded: (b || host).getAttribute('aria-expanded'), pe: getComputedStyle(host).pointerEvents };
  });
  if (rep.trigger && rep.trigger.x != null) {
    await page.mouse.click(rep.trigger.x, rep.trigger.y);
  }
  await page.waitForTimeout(1200);
  rep.dialog = await page.evaluate(() => ({
    open: !!document.querySelector('[data-testid="chart-settings"]'),
    tabs: [...document.querySelectorAll('[data-testid^="settings-tab-"]')].map((b) => b.getAttribute('data-testid')),
    buttons: [...document.querySelectorAll('[data-testid="chart-settings"] button')].map((b) => (b.textContent || '').trim()).filter(Boolean).slice(0, 40),
  }));
  await page.click('[data-testid="settings-tab-scales"]').catch((e) => { rep.tabError = String(e).slice(0, 90); });
  await page.waitForTimeout(900);
  rep.dialogScalesTab = await page.evaluate(() => ({
    buttons: [...document.querySelectorAll('[data-testid="chart-settings"] button')].map((b) => (b.textContent || '').trim()).filter(Boolean).slice(0, 40),
    pressed: [...document.querySelectorAll('[data-testid="chart-settings"] [aria-pressed]')]
      .map((b) => ({ t: (b.textContent || '').trim(), pressed: b.getAttribute('aria-pressed') })).slice(0, 30),
  }));
  let logBtn = page.locator('[data-testid="chart-settings"] button', { hasText: 'لگاریتمی' }).first();
  if (!(await logBtn.count().catch(() => 0))) {
    // زبانۀِ «مقیاس‌ها» باز نشسته؟ یک بار دیگر، این بار رویِ خودِ زبانه
    await page.click('[data-testid="settings-tab-scales"]').catch(() => {});
    await page.waitForTimeout(900);
    logBtn = page.locator('[data-testid="chart-settings"] button', { hasText: 'لگاریتمی' }).first();
  }
  rep.uiButtonFound = await logBtn.count().catch(() => 0);
  if (rep.uiButtonFound) { await logBtn.click(); await page.waitForTimeout(2500); }
  rep.steps.afterUiClick = await page.evaluate(AX);
  rep.storeAfterUi = await page.evaluate(() => { try { return (JSON.parse(localStorage.getItem('fts.chart.settings.v1') || '{}')).priceScale; } catch (e) { return null; } });
  await page.click('[data-testid="chart-settings-done"]').catch(() => {});
  await page.waitForTimeout(1500);
  rep.steps.afterUiClose = await page.evaluate(AX);

  // ب) نوشتنِ مستقیمِ استور
  await page.evaluate(() => {
    const w = window;
    return import('/src/features/technical/stores/ftsConfigStore.ts').then((m) => {
      m.useFtsConfigStore.getState().setPriceScale('logarithm');
      return m.useFtsConfigStore.getState().priceScale;
    });
  }).then((v) => { rep.directStore = v; }).catch((e) => { rep.directStoreError = String(e).slice(0, 120); });
  await page.waitForTimeout(3000);
  rep.steps.afterStoreWrite = await page.evaluate(AX);

  rep.diff = {
    uiChangedPixels: rep.steps.afterUiClose.geometricMidDeltaPx !== rep.steps.linear.geometricMidDeltaPx,
    storeChangedPixels: rep.steps.afterStoreWrite.geometricMidDeltaPx !== rep.steps.linear.geometricMidDeltaPx,
    linearSaysLog: rep.steps.linear.isLog,
    uiSaysLog: rep.steps.afterUiClose.isLog,
    storeSaysLog: rep.steps.afterStoreWrite.isLog,
  };
  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
  console.log('dialog: ' + JSON.stringify(rep.dialog).slice(0, 220));
  console.log('scales tab buttons: ' + JSON.stringify((rep.dialogScalesTab || {}).buttons).slice(0, 200));
  console.log('uiButtonFound=' + rep.uiButtonFound + ' storeAfterUi=' + rep.storeAfterUi + ' directStore=' + (rep.directStore || rep.directStoreError));
  console.log('linear Δ=' + rep.steps.linear.geometricMidDeltaPx + ' ui Δ=' + rep.steps.afterUiClose.geometricMidDeltaPx + ' store Δ=' + rep.steps.afterStoreWrite.geometricMidDeltaPx);
  console.log('isLog  linear=' + rep.steps.linear.isLog + ' ui=' + rep.steps.afterUiClose.isLog + ' store=' + rep.steps.afterStoreWrite.isLog);
  console.log('diff: ' + JSON.stringify(rep.diff));
  console.log('written: ' + OUT);
  await ctx.close();
})().catch((e) => { console.error('FAILED: ' + ((e && e.stack) || e)); process.exit(1); });
