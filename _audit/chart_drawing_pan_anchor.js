// _audit/chart_drawing_pan_anchor.js — آیا لنگرِ ترسیم با pan/zoom به «همان کندل» می‌چسبد؟
//
// پرسشِ دقیق (پس ازِ این‌که matrix دیدۀ دومِ «خط روند» با pan جابه‌جا شد): کدامِ میدانِ
// نقطه عوض می‌کند — timestamp، dataIndex، یا value — و آیا آن نقطه رویِ بوم به همان
// کندلِ پیشین چسبیده می‌ماند یا رویِ کندلِ دیگری می‌نشیند؟
//
// سنجشِ هرِ مرحله، پیش و پس از تحریف:
//   • نقاطِ ذخیره‌شدهٔ اورلی (timestamp / dataIndex / value)
//   • بازۀِ دید (getVisibleRange) و شمارۀِ کندل‌ها + timestampِ نخستین/آخرینِ داده
//   • پیکسلِ خودِ نقطه (convertToPixel) ⇒ اگر x عوض شده ولی به همان کندل می‌خورد،
//     جابه‌جاییِ پیکسل طبیعیِ pan است؛ اگر dataIndexِ ثابت به کندلِ دیگری رسیده،
//     لنگرِ اندیسی است (نقص)
//   • قیمتِ کندلیِ که نقطه رویِ آن نشسته (dataList[dataIndex].time/close) ⇒ شاهدِ مستقیم
// هیچ عددی پیش‌فرض نیست؛ هرچه نوشته می‌شود از همان اجرایِ زنده خوانده می‌شود.
const path = require('path');
const fs = require('fs');
const os = require('os');
const pw = require(path.join(process.cwd(), 'frontend', 'node_modules', 'playwright-core'));
const ROOT = process.cwd();
const OUT = path.join(ROOT, '_audit', 'chart_drawing_pan_anchor.json');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = process.env.BORS_BASE || 'http://localhost:5173';
const SYM = process.env.BORS_SYM || 'فولاد';

const FIND = `(function(){
  const looks = (v) => !!v && typeof v === 'object' && typeof v.getDataList === 'function';
  let host = document.querySelector('canvas'), c = null;
  while (host && !c) {
    const fk = Object.keys(host).find((k) => k.startsWith('__reactFiber$'));
    if (fk) { let f = host[fk];
      for (let up = 0; f && up < 80 && !c; up++, f = f.return) {
        let h = f.memoizedState;
        for (let g = 0; h && g < 120 && !c; g++, h = h.next) {
          const ms = h.memoizedState;
          if (looks(ms)) c = ms;
          else if (ms && typeof ms === 'object' && looks(ms.current)) c = ms.current;
        } } }
    host = host.parentElement;
  }
  if (c) window.__borsChart = c;
  return !!c;
})()`;

const STATE = `(() => {
  const c = window.__borsChart;
  if (!c) return { error: 'NO_CHART' };
  const data = (c.getDataList && c.getDataList()) || [];
  const all = (c.getOverlays && c.getOverlays()) || [];
  const seg = all.filter(o => o.name === 'segment');
  const vr = (c.getVisibleRange && c.getVisibleRange()) || null;
  const one = (o) => ({
    id: o.id,
    points: (o.points || []).map(p => {
      const idx = p.dataIndex ?? null;
      const bar = (idx != null && data[idx]) ? data[idx] : null;
      const px = (() => {
        try {
          const r = c.convertToPixel([{ dataIndex: idx, timestamp: p.timestamp, value: p.value }],
                                     { paneId: 'candle_pane' });
          const q = Array.isArray(r) ? r[0] : r;
          return q ? { x: Math.round(q.x * 100) / 100, y: Math.round(q.y * 100) / 100 } : null;
        } catch (e) { return null; }
      })();
      return { timestamp: p.timestamp ?? null, dataIndex: idx,
               value: p.value == null ? null : Math.round(p.value * 100) / 100,
               barAtDataIndex: bar ? String(bar.time || '') : null,
               barClose: bar && bar.close != null ? Math.round(bar.close * 100) / 100 : null,
               pixel: px };
    }),
  });
  return {
    segments: seg.map(one),
    visibleRange: vr,
    barCount: data.length,
    firstBarTime: data.length ? String(data[0].time || '') : null,
    lastBarTime: data.length ? String(data[data.length - 1].time || '') : null,
    saved: (() => { try { return JSON.parse(localStorage.getItem('fts.drawings.v1.${SYM}') || '[]').length; }
                    catch (e) { return null; } })(),
  };
})()`;

(async () => {
  const ctx = await pw.chromium.launchPersistentContext(
    fs.mkdtempSync(path.join(os.tmpdir(), 'bors-pananchor-')),
    { executablePath: EXE, viewport: null, args: ['--no-first-run', '--disable-sync'] });
  ctx.on('dialog', (d) => d.dismiss().catch(() => {}));
  const page = ctx.pages()[0] || await ctx.newPage();
  page.on('dialog', (d) => d.dismiss().catch(() => {}));
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
  if (!(await page.evaluate(FIND))) throw new Error('no chart handle');

  const rep = { ranAt: new Date().toISOString(), symbol: SYM, steps: {} };
  const shot = async (label) => {
    const st = await page.evaluate(STATE);
    rep.steps[label] = st;
    return st;
  };

  const NAMES = `(() => {
    const c = window.__borsChart; if (!c) return { error: 'NO_CHART' };
    const all = (c.getOverlays && c.getOverlays()) || [];
    return { segments: all.filter(o => o.name === 'segment')
      .map(o => ({ id: o.id, n: (o.points || []).length,
                   pts: (o.points || []).map(p => ({ ts: p.timestamp ?? null, idx: p.dataIndex ?? null,
                                                     v: p.value == null ? null : Math.round(p.value * 100) / 100 })) })) };
  })()`;

  const before = await shot('beforeDrawing');
  const pane = await page.evaluate(`(() => { const p = window.__borsChart.getSize('candle_pane','main');
    return { left: Math.round(p.left), top: Math.round(p.top), w: Math.round(p.width), h: Math.round(p.height) }; })()`);
  rep.pane = pane;

  // همان توالیِ matrix: بستنِ رسمِ نیمه‌کاره، انتخابِ ابزار، بعد دو کلیکِ پشت‌سرهم
  // بی‌خواندنِ سنگینِ میانی (خواندنِ getOverlays با convertToPixel درِ میانةِ دو کلیک،
  // خودِ رسم را مختل می‌کرد — نخستین اجرایِ همین پروب همان را «بی‌رسم» گزارش داد).
  await page.keyboard.press('Escape').catch(() => {});
  await page.mouse.move(pane.left + Math.round(pane.w / 2), 28).catch(() => {});
  await page.waitForTimeout(300);
  await page.locator('.nn-left-toolbar .tool-item[title="خط روند"]').first().click({ timeout: 5000 });
  await page.waitForTimeout(500);
  const A = [pane.left + Math.round(pane.w * 0.34), pane.top + Math.round(pane.h * 0.38)];
  const B = [pane.left + Math.round(pane.w * 0.62), pane.top + Math.round(pane.h * 0.58)];
  rep.clicks = { A, B };
  rep.namesAfterSelect = await page.evaluate(NAMES);
  await page.mouse.click(A[0], A[1]);
  await page.waitForTimeout(520);
  rep.namesAfterFirstClick = await page.evaluate(NAMES);
  await page.mouse.click(B[0], B[1]);
  await page.waitForTimeout(900);
  const drawn = await shot('afterSecondClick');
  const seg = (drawn.segments || [])[0];
  if (!seg) {
    console.error('CONTROL FAILED: هیچ segment پس ازِ دو کلیک ساخته نشد.');
    fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
    await ctx.close();
    process.exit(3);
  }
  const id = seg.id;

  // pan به چپ (دیدِ کهنه‌تر) — همان کاریِ که مالک می‌کند
  const panBy = async (dx) => {
    await page.mouse.move(pane.left + Math.round(pane.w * 0.55), pane.top + Math.round(pane.h * 0.5));
    await page.mouse.down();
    await page.mouse.move(pane.left + Math.round(pane.w * 0.55) + dx, pane.top + Math.round(pane.h * 0.5), { steps: 12 });
    await page.mouse.up();
    await page.waitForTimeout(1400);
  };
  await panBy(-160);
  const afterPanLeft = await shot('afterPanLeft');
  await panBy(160);
  const afterPanBack = await shot('afterPanBackSamePlace');
  await page.mouse.move(pane.left + Math.round(pane.w / 2), pane.top + Math.round(pane.h / 2));
  await page.mouse.wheel(0, -240);
  await page.waitForTimeout(1200);
  const afterZoom = await shot('afterZoomOut');
  await page.mouse.wheel(0, 240);
  await page.waitForTimeout(1000);
  const afterZoomBack = await shot('afterZoomBack');

  const cmp = (label, st) => {
    const s = (st.segments || []).find((o) => o.id === id) || (st.segments || [])[0] || null;
    if (!s) return { gone: true };
    return { points: s.points.map(p => ({ ts: p.timestamp, idx: p.dataIndex, v: p.value,
                                           barTime: p.barAtDataIndex, barClose: p.barClose,
                                           x: p.pixel && p.pixel.x })) };
  };
  rep.comparison = {
    drawn: cmp('drawn', drawn),
    afterPanLeft: cmp('p', afterPanLeft),
    afterPanBack: cmp('b', afterPanBack),
    afterZoomOut: cmp('z', afterZoom),
    afterZoomBack: cmp('zb', afterZoomBack),
  };
  rep.barCounts = {
    drawn: drawn.barCount, panLeft: afterPanLeft.barCount, panBack: afterPanBack.barCount,
    zoomOut: afterZoom.barCount, zoomBack: afterZoomBack.barCount,
  };
  rep.visibleRanges = {
    drawn: drawn.visibleRange, panLeft: afterPanLeft.visibleRange,
    panBack: afterPanBack.visibleRange, zoomOut: afterZoom.visibleRange,
    zoomBack: afterZoomBack.visibleRange,
  };
  rep.savedAtEnd = afterZoomBack.saved;

  // پاک‌سازیِ رسمِ خودی (و فقط آن)
  await page.evaluate((oid) => window.__borsChart.removeOverlay({ id: oid }), id);
  await page.waitForTimeout(700);
  rep.afterOwnDelete = await shot('afterOwnDeleteRemoved');

  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
  const c = rep.comparison;
  const row = (k) => console.log(k.padEnd(14), JSON.stringify(c[k]).slice(0, 260));
  console.log('bars', JSON.stringify(rep.barCounts));
  console.log('ranges', JSON.stringify(rep.visibleRanges));
  Object.keys(c).forEach(row);
  console.log('saved at end:', rep.savedAtEnd, ' after own delete:', rep.afterOwnDelete.saved);
  console.log('written: ' + OUT);
  await ctx.close();
})().catch((e) => { console.error('FAILED: ' + ((e && e.stack) || e)); process.exit(1); });
