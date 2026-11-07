// _audit/chart_ref_conditions.js — چارتِ خودی درِ همانِ شرایطی که مرجع الان درِ آن است
//
// مرجع (فولاد، asset/453) درِ نشستِ مجاز، همان‌طور که پیدا شد: 1W، مقیاسِ auto،
// تعدیل «عملکردی»، محورِ قیمتِ راست ۵۲px، پنِ ۸۸۱×۲۳۳، بی‌پنِ حجم، رنگ‌هایِ
// #089981/#f23645 (نمونۀِ بوم). این هارنس همان شرایط را رویِ چارتِ خودی می‌گذارد و
// هندسه/رنگ/متنِ legend را بیرون می‌دهد تا مقایسه عددی باشد، نه ادعایی.
//
// اجرا: node _audit/chart_ref_conditions.js
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const pw = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));
const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, '_audit', 'chart_ref_conditions.json');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = process.env.BORS_BASE || 'http://localhost:5173';
const SYM = '\u0641\u0648\u0644\u0627\u062f';

const GEOM = () => {
  const cs = [...document.querySelectorAll('canvas')].map(c => {
    const r = c.getBoundingClientRect();
    return { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height), attrW: c.width, attrH: c.height };
  }).filter(r => r.w > 0 && r.h > 0);
  const uniq = [];
  for (const r of cs) if (!uniq.some(u => u.w === r.w && u.h === r.h && u.x === r.x && u.y === r.y)) uniq.push(r);
  const big = uniq.slice().sort((a, b) => b.w * b.h - a.w * a.h)[0] || null;
  const axis = uniq.filter(r => r.w < 120 && r.h > 120).sort((a, b) => b.h - a.h)[0] || null;
  const vol = uniq.filter(r => r.h < 130 && r.w > 300 && r.y > (big ? big.y + big.h * 0.6 : 0)).sort((a, b) => a.h - b.h)[0] || null;
  // رنگ‌هایِ اشباعِ پُرتکرارِ پنِ اصلی (نمونۀِ بوم، بی‌اتّفاق)
  let colors = [];
  try {
    const c = [...document.querySelectorAll('canvas')].find(x => { const b = x.getBoundingClientRect(); return b.width > 400 && b.height > 150; });
    const g = c.getContext('2d');
    const img = g.getImageData(0, 0, c.width, c.height).data;
    const hist = {};
    for (let i = 0; i < img.length; i += 4) {
      const r = img[i], gg = img[i + 1], b = img[i + 2], a = img[i + 3];
      if (a < 200) continue;
      if (Math.max(r, gg, b) - Math.min(r, gg, b) < 40) continue;
      const k = r + ',' + gg + ',' + b;
      hist[k] = (hist[k] || 0) + 1;
    }
    colors = Object.entries(hist).sort((x, y) => y[1] - x[1]).slice(0, 5).map(e => ({ rgb: e[0], n: e[1], hex: '#' + e[0].split(',').map(v => (+v).toString(16).padStart(2, '0')).join('') }));
  } catch (e) { colors = [{ error: String(e).slice(0, 60) }]; }
  const legend = [...document.querySelectorAll('div,span')]
    .map(e => (e.textContent || '').replace(/\s+/g, ' ').trim())
    .filter(s => s.length > 12 && s.length < 150 && /O|H|L|C|\u0641\u0648\u0644\u0627\u062f/.test(s))
    .slice(0, 4);
  const toolbar = [...document.querySelectorAll('button')]
    .map(b => ({ t: (b.textContent || '').trim().slice(0, 16), id: b.getAttribute('data-testid'), title: (b.getAttribute('title') || '').slice(0, 26) }))
    .filter(x => x.t || x.id);
  return {
    canvases: uniq.length, pane: big, priceAxis: axis, volumePane: vol,
    axisSide: axis ? (axis.x > (big ? big.x + big.w / 2 : 0) ? 'right' : 'left') : null,
    colors, legend, toolbarButtons: toolbar.slice(0, 60),
  };
};

(async () => {
  const ctx = await pw.chromium.launchPersistentContext(
    fs.mkdtempSync(path.join(require('os').tmpdir(), 'bors-ref-cond-')),
    { executablePath: EXE, viewport: null, args: ['--no-first-run', '--disable-sync'] });
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.setViewportSize({ width: 1366, height: 768 });
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

  const rep = { ranAt: new Date().toISOString(), viewport: [1366, 768], symbol: SYM,
                reference: { interval: '1W', scale: 'auto', adjustment: '\u0639\u0645\u0644\u06a9\u0631\u062f\u06cc',
                             pane: [881, 233], priceAxis: [52, 233], side: 'right', volumePane: 'absent',
                             upHex: '#089981', downHex: '#f23645',
                             legendSample: '\u0641\u0648\u0644\u0627\u062f \u0645\u0628\u0627\u0631\u0643\u0647 \u0627\u0635\u0641\u0647\u0627\u0646- \u0628\u0648\u0631\u0633 \u062a\u0647\u0631\u0627\u0646 \u00b7 1W \u00b7 O 4,410 H 4,410 L 4,410 C 4,410 -130 (-2.86%)' } };

  rep.oursDaily = await page.evaluate(GEOM);
  await page.screenshot({ path: path.join(ROOT, '_audit', 'ours_folad_daily.png') });

  await page.click('[data-testid="timeframe-W"]');
  await page.waitForTimeout(4000);
  rep.oursWeekly = await page.evaluate(GEOM);
  await page.screenshot({ path: path.join(ROOT, '_audit', 'ours_folad_weekly.png') });

  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
  const brief = (o) => JSON.stringify({ pane: o.pane && [o.pane.w, o.pane.h], axis: o.priceAxis && [o.priceAxis.w, o.priceAxis.h], side: o.axisSide, volume: o.volumePane && [o.volumePane.w, o.volumePane.h], colors: (o.colors || []).slice(0, 2).map(c => c.hex) });
  console.log('reference : ' + JSON.stringify(rep.reference));
  console.log('ours daily  : ' + brief(rep.oursDaily));
  console.log('ours weekly : ' + brief(rep.oursWeekly));
  console.log('legend(weekly): ' + JSON.stringify((rep.oursWeekly.legend || []).slice(0, 2)));
  console.log('written: ' + OUT);
  await ctx.close();
})().catch(e => { console.error('HARNESS FAILED: ' + ((e && e.stack) || e)); process.exit(1); });
