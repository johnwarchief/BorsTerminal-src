// _audit/chart_axis_visibility.js — اثباتِ زندهٔ «نمایش محورِ زمان/قیمت» رویِ خودِ چارت
//
// اجرا: node _audit/chart_axis_visibility.js      (بک‌اند 8001 + vite 5173 بالا باشند)
// چرا: آزمونِ vitest ثابت می‌کند مقدار به `setStyles` می‌رسد؛ این هارنس ثابت می‌کند
// پیکسل عوض می‌شود — محورِ واقعی ازِ بوم می‌رود، جایش به کندل برمی‌گردد، و باِ
// روشن‌کردنِ دوباره همان اندازه‌هایِ اول برمی‌گردند (برگشت‌پذیری).
const path = require('path');
const fs = require('fs');
const pw = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));
const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, '_audit', 'chart_axis_visibility.json');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = process.env.BORS_BASE || 'http://localhost:5173';
const SYM = '\u0641\u0648\u0644\u0627\u062f';
const VW = Number(process.env.BORS_VW || 1366), VH = Number(process.env.BORS_VH || 768);

const GEOM = () => {
  const list = [...document.querySelectorAll('canvas')].map(c => {
    const r = c.getBoundingClientRect();
    return { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) };
  }).filter(r => r.w > 0 && r.h > 0);
  const uniq = [];
  for (const r of list) if (!uniq.some(u => u.w === r.w && u.h === r.h && u.x === r.x && u.y === r.y)) uniq.push(r);
  const widest = uniq.slice().sort((a, b) => b.w - a.w)[0] || null;
  const tallestNarrow = uniq.filter(r => r.w < 120).sort((a, b) => b.h - a.h)[0] || null;
  const shortWide = uniq.filter(r => r.h < 60 && r.w > 200).sort((a, b) => b.y - a.y)[0] || null;
  return {
    canvases: list.length, distinct: uniq,
    paneW: widest ? widest.w : 0, paneH: widest ? widest.h : 0,
    yAxisW: tallestNarrow ? tallestNarrow.w : 0,
    xAxisH: shortWide ? shortWide.h : 0,
    xAxisY: shortWide ? shortWide.y : 0,
  };
};

async function toggle(page, toggleSel) {
  // کلیکِ واقعی (نه evaluate) — خودِ همین هارنس باید ثابت کند کنترل زیرِ لایه نیست
  await page.click('[data-testid="open-chart-settings"]');
  await page.waitForTimeout(800);
  await page.click('[data-testid="settings-tab-scales"]');
  await page.waitForTimeout(400);
  await page.click(toggleSel);   // شناسۀِ پایدار، بی‌وابستگی به ي عربی/فارسی
  await page.waitForTimeout(1000);
  await page.click('[data-testid="chart-settings-close"]').catch(() => {});
  await page.waitForTimeout(1000);
}

(async () => {
  const ctx = await pw.chromium.launchPersistentContext(
    fs.mkdtempSync(path.join(require('os').tmpdir(), 'bors-axis-vis-')),
    { executablePath: EXE, viewport: null, args: ['--no-first-run', '--disable-sync'] });
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.setViewportSize({ width: VW, height: VH });
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  if (await page.evaluate(() => !!document.querySelector('input[type=password]'))) {
    await page.locator('input[type="text"]').first().fill('admin');
    await page.locator('input[type="password"]').first().fill('bors123');
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(3000);
  }
  await page.evaluate((s) => { location.hash = '#/technical/' + encodeURIComponent(s); }, SYM);
  await page.waitForFunction(() => document.querySelectorAll('canvas').length > 0, null, { timeout: 45000 });
  await page.waitForTimeout(4500);

  const rep = { ranAt: new Date().toISOString(), viewport: [VW, VH], symbol: SYM };
  rep.before = await page.evaluate(GEOM);
  await page.screenshot({ path: path.join(ROOT, '_audit', 'cav_before.png') });

  await toggle(page, '[data-testid="settings-toggle-show-y-axis"]');
  rep.afterHideY = await page.evaluate(GEOM);
  await page.screenshot({ path: path.join(ROOT, '_audit', 'cav_no_y_axis.png') });
  await toggle(page, '[data-testid="settings-toggle-show-y-axis"]');
  rep.restoredY = await page.evaluate(GEOM);

  await toggle(page, '[data-testid="settings-toggle-show-x-axis"]');
  rep.afterHideX = await page.evaluate(GEOM);
  await page.screenshot({ path: path.join(ROOT, '_audit', 'cav_no_x_axis.png') });
  await toggle(page, '[data-testid="settings-toggle-show-x-axis"]');
  rep.restoredX = await page.evaluate(GEOM);

  rep.verdict = {
    yAxisRemovedOrShrank: rep.afterHideY.yAxisW < Math.max(1, Math.round(rep.before.yAxisW * 0.5)),
    paneGainedWidth: rep.afterHideY.paneW > rep.before.paneW,
    yAxisRestored: Math.abs(rep.restoredY.yAxisW - rep.before.yAxisW) <= 2
      && Math.abs(rep.restoredY.paneW - rep.before.paneW) <= 2,
    xAxisRemovedOrShrank: rep.afterHideX.xAxisH < Math.max(1, Math.round(rep.before.xAxisH * 0.5)),
    paneGainedHeight: rep.afterHideX.paneH > rep.before.paneH,
    xAxisRestored: Math.abs(rep.restoredX.xAxisH - rep.before.xAxisH) <= 2
      && Math.abs(rep.restoredX.paneH - rep.before.paneH) <= 2,
  };
  rep.allGreen = Object.values(rep.verdict).every(Boolean);
  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');

  console.log('before       : ' + JSON.stringify({ paneW: rep.before.paneW, paneH: rep.before.paneH, yAxisW: rep.before.yAxisW, xAxisH: rep.before.xAxisH }));
  console.log('afterHideY   : ' + JSON.stringify({ paneW: rep.afterHideY.paneW, paneH: rep.afterHideY.paneH, yAxisW: rep.afterHideY.yAxisW }));
  console.log('restoredY    : ' + JSON.stringify({ paneW: rep.restoredY.paneW, yAxisW: rep.restoredY.yAxisW }));
  console.log('afterHideX   : ' + JSON.stringify({ paneW: rep.afterHideX.paneW, paneH: rep.afterHideX.paneH, xAxisH: rep.afterHideX.xAxisH }));
  console.log('restoredX    : ' + JSON.stringify({ paneH: rep.restoredX.paneH, xAxisH: rep.restoredX.xAxisH }));
  console.log('verdict      : ' + JSON.stringify(rep.verdict));
  console.log('ALL GREEN    : ' + rep.allGreen);
  await ctx.close();
  process.exit(rep.allGreen ? 0 : 1);
})().catch(e => { console.error('HARNESS FAILED: ' + ((e && e.stack) || e)); process.exit(1); });
