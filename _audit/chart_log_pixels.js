// _audit/chart_log_pixels.js — لگاریتمی: آیا کندل‌ها واقعاً جایِ درست می‌نشینند؟
//
// سنجشِ پیکسلی، نه ادعایِ استور: پنِ قیمت را می‌خوانیم، سطرهایِ رنگیِ کندل‌ها را
// می‌شماریم و توزیعِ ارتفاعیِ آن‌ها را با مقیاسِ خطی مقایسه می‌کنیم. اگر درِ
// لگاریتمی کندل‌ها رویِ هم تلپاف شوند (بسامدِ سطرِ یکسان، بازۀِ ارتفاعیِ ناچیز)
// نقص درِ رندر است؛ اگر توزیعِ منطقی (فشرده‌تر در بالا/بازتر در پایین برایِ
// رشدِ نمایی) ماند، تبدیلِ خودِ renderer درست است و سنجشِ قبلیِ من (که همه
// قیمت‌ها را به y=۷۱۷ می‌برد) ابزارِ غلط بوده است.
//
// اجرا: node _audit/chart_log_pixels.js
const path = require('path');
const fs = require('fs');
const pw = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));
const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, '_audit', 'chart_log_pixels.json');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = process.env.BORS_BASE || 'http://localhost:5173';
const SYM = 'فولاد';

const INK = () => {
  const cs = [...document.querySelectorAll('canvas')].map((c) => {
    const r = c.getBoundingClientRect();
    return { c, r };
  }).filter((x) => x.r.width > 300 && x.r.height > 150);
  if (!cs.length) return { error: 'NO_PANE_CANVAS' };
  cs.sort((a, b) => b.r.width * b.r.height - a.r.width * a.r.height);
  const main = cs[0];
  const off = document.createElement('canvas');
  off.width = Math.round(main.r.width); off.height = Math.round(main.r.height);
  const g = off.getContext('2d', { willReadFrequently: true });
  for (const x of cs) g.drawImage(x.c, 0, 0, off.width, off.height);
  const { data } = g.getImageData(0, 0, off.width, off.height);
  const inkRow = new Array(off.height).fill(0);
  for (let y = 0; y < off.height; y++) {
    for (let x = 0; x < off.width; x++) {
      const i = (y * off.width + x) * 4;
      const mx = Math.max(data[i], data[i + 1], data[i + 2]), mn = Math.min(data[i], data[i + 1], data[i + 2]);
      if (mx > 60 && mx - mn > 40) inkRow[y]++;
    }
  }
  const rows = [];
  for (let y = 0; y < inkRow.length; y++) if (inkRow[y] > off.width * 0.02) rows.push(y);
  if (!rows.length) return { error: 'NO_INK' };
  const first = rows[0], last = rows[rows.length - 1];
  // چگالیِ سطرِ رنگی درِ سه‌سومِ بالا/میانی/پایینِ بازۀِ کندل‌ها
  const band = (a, b) => rows.filter((y) => y >= a && y < b).length;
  const third = Math.max(1, Math.floor((last - first) / 3));
  return {
    pane: { w: off.width, h: off.height },
    inkRows: rows.length, firstRow: first, lastRow: last, extent: last - first,
    topThird: band(first, first + third), midThird: band(first + third, first + 2 * third),
    bottomThird: band(first + 2 * third, last + 1),
    busiestRow: rows.slice().sort((a, b) => inkRow[b] - inkRow[a])[0],
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
    fs.mkdtempSync(path.join(require('os').tmpdir(), 'bors-logpx-')),
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

  const rep = { ranAt: new Date().toISOString(), symbol: SYM, timeframe: 'D', viewport: [1366, 768] };
  rep.linear = await page.evaluate(INK);
  await page.screenshot({ path: path.join(ROOT, '_audit', 'logpx_linear.png') });
  await setScale(page, 'لگاریتمی');
  rep.log = await page.evaluate(INK);
  rep.store = await page.evaluate(() => { try { return (JSON.parse(localStorage.getItem('fts.chart.settings.v1') || '{}')).priceScale; } catch (e) { return null; } });
  await page.screenshot({ path: path.join(ROOT, '_audit', 'logpx_log.png') });
  await setScale(page, 'خطی');
  rep.backToLinear = await page.evaluate(INK);

  rep.reading = {
    storeSaysLog: rep.store,
    logCollapsed: !!(rep.log && rep.log.extent != null && rep.linear && rep.linear.extent != null
      && rep.log.extent < rep.linear.extent * 0.35),
    logStillSpreads: !!(rep.log && rep.log.extent > 60 && rep.log.midThird > 0 && rep.log.bottomThird > 0),
    extentLinear: (rep.linear || {}).extent, extentLog: (rep.log || {}).extent,
    extentLinearAgain: (rep.backToLinear || {}).extent,
    distributionLinear: [(rep.linear || {}).topThird, (rep.linear || {}).midThird, (rep.linear || {}).bottomThird],
    distributionLog: [(rep.log || {}).topThird, (rep.log || {}).midThird, (rep.log || {}).bottomThird],
  };
  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
  console.log('linear : ' + JSON.stringify(rep.linear));
  console.log('log    : ' + JSON.stringify(rep.log));
  console.log('again  : ' + JSON.stringify(rep.backToLinear));
  console.log('reading: ' + JSON.stringify(rep.reading));
  console.log('written: ' + OUT);
  await ctx.close();
})().catch((e) => { console.error('FAILED: ' + ((e && e.stack) || e)); process.exit(1); });
