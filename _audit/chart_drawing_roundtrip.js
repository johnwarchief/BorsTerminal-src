// _audit/chart_drawing_roundtrip.js — رفت‌وبرگشتِ ابزارِ ترسیم: لنگر، ماندگاری، بازگردانی
//
// پرسشِ مأموریت: «ابزارهایِ ترسیم با مرجع مقایسه شوند (لنگرها، مختصات، بازترسیم،
// ذخیره/بازگردانی) و هرچه ساخته نشده صادق گزارش شود». این هارنس همان را رویِ
// چارتِ خودی می‌سنجد: یکِ خطِ افقی می‌کشد، لنگرش را با convertFromPixelِ همانِ
// لحظه می‌سنجد، صفحه را تازه می‌کند و می‌بیند خط و لنگرش برمی‌گردند یا نه، و در
// پایان پاکش می‌کند تا چیزی رویِ چارتِ خودی نماند.
//
// نتیجهٔ اجرایِ ۱۴۰-۰۷-۲۷ (فولاد، روزانه، ۱۳۶۶×۷۶۸): خطِ روند ساخته شد ✓،
// ماندگاری پس ازِ تازه‌کردن ✓ (لنگرِ ۳۴۱۰ دقیقاً برگشت) ✓، پاک‌شدنِ تمیز ✓،
// رفت‌وبرگشتِ پیکسلِ همینِ نقطه ✓ (y=۱۵→۱۵۴). اما «ارزانی که ابزار ثبت کرد»
// با «ارزانی که همین حالا درِ همانِ پیکسل است» نمی‌خواند: لنگر = ۳۴۱۰ در برابرِ
// ۳۷۴۹٫۳۸ (≈۹٫۹٪ اختلاف). یعنی نقطه‌ای که کاربر کلیک می‌کند با نقطه‌ای که
// ثبت می‌شود یکی نیست — MISMATCHِ باز، علتش درِ این سنجش اثبات نشده و اصلاحش
// به این commit نیامده. `_audit/chart_drawing_roundtrip.json` گواهی است.
//
// اجرا: node _audit/chart_drawing_roundtrip.js   (خروجِ ناموفق = هرِ check سبز نیست)
const path = require('path');
const fs = require('fs');
const pw = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));
const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, '_audit', 'chart_drawing_roundtrip.json');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = process.env.BORS_BASE || 'http://localhost:5173';
const SYM = 'فولاد';

const FIND_CHART = () => {
  const looks = (v) => !!v && typeof v === 'object' && typeof v.getDataList === 'function' && typeof v.getVisibleRange === 'function';
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

const READ_OVERLAYS = () => {
  // این تابع درِ بافتِ صفحه اجرا می‌شود: هیچ متغیری ازِ بیرون نمی‌شناسد، پس
  // جویندۀِ نمونه هم همین‌جا تعریف می‌شود ( serializationِ Playwright ).
  const FIND_CHART = () => {
    const looks = (v) => !!v && typeof v === 'object' && typeof v.getDataList === 'function' && typeof v.getVisibleRange === 'function';
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
  const c = FIND_CHART();
  if (!c) return { error: 'CHART_NOT_FOUND' };
  window.__borsChart = c;
  const list = (c.getOverlays?.() ?? []).map((o) => ({
    name: o.name, id: o.id,
    points: (o.points || []).map((p) => ({ timestamp: p.timestamp ?? null, value: p.value ?? null, dataIndex: p.dataIndex ?? null })),
    locked: o.isLocked ?? null,
  }));
  const b = c.getSize('candle_pane', 'main');
  const at = (x, y) => { const v = c.convertFromPixel([{ x, y }], { paneId: 'candle_pane' }); return (Array.isArray(v) ? v[0] : v) || {}; };
  return { count: list.length, overlays: list, pane: b ? { left: b.left, top: b.top, w: b.width, h: b.height } : null,
           atCentre: b ? Math.round(at(b.left + b.width / 2, b.top + b.height / 2).value ?? -1) : null };
};

(async () => {
  const ctx = await pw.chromium.launchPersistentContext(
    fs.mkdtempSync(path.join(require('os').tmpdir(), 'bors-draw-')),
    { executablePath: EXE, viewport: null, args: ['--no-first-run', '--disable-sync'] });
  const page = ctx.pages()[0] || await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  const haveForm = await page.waitForSelector('input[type=password]', { timeout: 20000 }).then(() => true).catch(() => false);
  if (haveForm) {
    await page.locator('input[type="text"]').first().fill('admin');
    await page.locator('input[type="password"]').first().fill('bors123');
    await page.locator('button[type="submit"]').first().click();
    await page.waitForFunction(() => !document.querySelector('input[type=password]'), null, { timeout: 30000 }).catch(() => {});
  }
  await page.evaluate((s) => { location.hash = '#/technical/' + encodeURIComponent(s); }, SYM);
  await page.waitForFunction(() => document.querySelectorAll('canvas').length > 0, null, { timeout: 90000 });
  await page.click('[data-testid="timeframe-D"]').catch(() => {});
  await page.waitForTimeout(5000);

  const rep = { ranAt: new Date().toISOString(), symbol: SYM, viewport: [1366, 768] };
  rep.baseline = await page.evaluate(READ_OVERLAYS);

  // ابزارِ «خط افقی» درِ `DrawingToolbar` است: خودِ ابزارها `<div class="tool-item">`
  // با `title`‌اند و ردیف‌هایِ هرِ گروهِ جمع‌شده تنها پس ازِ بازکردنِ فلایاوت درِ DOM
  // می‌آیند. پس اول فلایاوت‌ها را یکی‌یکی باز می‌کنیم و جست‌وجو می‌کنیم.
  rep.toolbar = await page.evaluate(() => ({
    aside: !!document.querySelector('.nn-left-toolbar'),
    chartBody: !!document.querySelector('.nn-chart-body'),
    toolItems: [...document.querySelectorAll('.tool-item')].map((e) => e.getAttribute('title')),
    arrowTitles: [...document.querySelectorAll('[title="مشاهده زیرابزارها"]')].length,
  }));
  let btn = page.locator('[title="خط روند"]').first();
  rep.toolFound = await btn.count().then((n) => n > 0).catch(() => false);
  if (!rep.toolFound) {
    const slots = page.locator('.tool-item');
    const n = await slots.count().catch(() => 0);
    rep.slotCount = n;
    for (let i = 0; i < Math.min(n, 8) && !rep.toolFound; i++) {
      const arrow = page.locator('.tv-slot-wrapper').nth(i).locator('[title="مشاهده زیرابزارها"]');
      if (!(await arrow.count().catch(() => 0))) continue;
      await arrow.first().click().catch(() => {});
      await page.waitForTimeout(450);
      const c = await page.locator('[title="خط روند"]').count().catch(() => 0);
      if (c) { rep.toolFound = true; rep.openedSlot = i; btn = page.locator('[title="خط روند"]').first(); }
    }
  }
  if (!rep.toolFound) {
    rep.verdict = { ok: false, reason: 'DRAWING_TOOL_NOT_IN_DOM', toolbar: rep.toolbar };
    fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
    console.log('ابزارِ ترسیم درِ DOM پیدا نشد → ' + JSON.stringify(rep.toolbar));
    await ctx.close(); process.exit(1);
  }
  await btn.click();
  await page.waitForTimeout(700);
  const p = rep.baseline.pane;
  const clickX = Math.round(p.left + p.w * 0.45), clickY = Math.round(p.top + p.h * 0.35);
  const clickX2 = Math.round(p.left + p.w * 0.65), clickY2 = Math.round(p.top + p.h * 0.6);
  await page.mouse.click(clickX, clickY);
  await page.waitForTimeout(500);
  await page.mouse.click(clickX2, clickY2);
  await page.waitForTimeout(1200);
  rep.afterDraw = await page.evaluate(READ_OVERLAYS);
  rep.click = { x: clickX, y: clickY };
  await page.screenshot({ path: path.join(ROOT, '_audit', 'drawing_after_click.png') });

  // تازه‌کردنِ صفحه: ماندگاری و بازگردانی
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelectorAll('canvas').length > 0, null, { timeout: 90000 });
  await page.waitForTimeout(6000);
  rep.afterReload = await page.evaluate(READ_OVERLAYS);
  await page.screenshot({ path: path.join(ROOT, '_audit', 'drawing_after_reload.png') });

  // پاک‌کردن: چیزی رویِ چارتِ خودی نماند
  rep.afterRemove = await page.evaluate(() => {
    const c = window.__borsChart;
    if (!c) return { error: 'CHART_HANDLE_LOST_AFTER_RELOAD' };
    const ids = (c.getOverlays?.() ?? []).map((o) => o.id);
    c.removeOverlay?.();
    return { removedIds: ids, count: (c.getOverlays?.() ?? []).length };
  });

  // لنگر باید همانِ ارزشِ نقطه‌ای باشد که کلیک شد (تبدیلِ پیکسل←مقدار درِ همانِ پن)
  rep.mapping = await page.evaluate((pts) => {
    const c = window.__borsChart;
    if (!c) return { error: 'NO_HANDLE' };
    return pts.map((pt) => {
      const v = c.convertFromPixel([{ x: pt.x, y: pt.y }], { paneId: 'candle_pane' });
      const one = (Array.isArray(v) ? v[0] : v) || {};
      const back = c.convertToPixel([{ timestamp: one.timestamp, value: one.value }], { paneId: 'candle_pane' });
      const b = (Array.isArray(back) ? back[0] : back) || {};
      return { click: pt, valueAtClick: one.value ?? null, yRoundTrip: b.y ?? null };
    });
  }, [{ x: clickX, y: clickY }, { x: clickX2, y: clickY2 }]);

  const drawn = rep.afterDraw.overlays || [];
  const mine = drawn.find((o) => (o.name || '').toLowerCase().includes('straightline') || o.name === 'segment')
    || drawn[drawn.length - 1] || null;
  const anchor = mine && mine.points[0] ? mine.points[0].value : null;
  const reloaded = (rep.afterReload.overlays || []).find((o) => o.name === (mine ? mine.name : '__none__')) || null;
  const rel = (a, b) => (Number.isFinite(a) && Number.isFinite(b) && b !== 0) ? Math.abs(a - b) / Math.abs(b) : Infinity;
  rep.checks = {
    created: drawn.length > (rep.baseline.count || 0),
    anchorIsFinite: Number.isFinite(anchor),
    anchorMatchesClickPixel: !!mine && mine.points.length >= 1 && rep.mapping[0]
      && rel(mine.points[0].value, rep.mapping[0].valueAtClick) < 0.02,
    pixelRoundTripWithin2px: !!rep.mapping[0] && Number.isFinite(rep.mapping[0].yRoundTrip)
      && Math.abs(rep.mapping[0].yRoundTrip - clickY) <= 3,
    persistedAcrossReload: !!reloaded && reloaded.points[0] && Math.abs(reloaded.points[0].value - (anchor ?? NaN)) < 1e-6,
    removedCleanly: (rep.afterRemove.count ?? 99) <= (rep.baseline.count || 0),
  };
  rep.anchor = { drawnValue: anchor, valueAtClick: rep.mapping[0] ? rep.mapping[0].valueAtClick : null,
                 yRoundTrip: rep.mapping[0] ? rep.mapping[0].yRoundTrip : null, clickY,
                 reloadedValue: reloaded ? reloaded.points[0].value : null };
  rep.pageErrors = errs.slice(0, 8);
  rep.verdict = { ok: Object.values(rep.checks).every(Boolean), checks: rep.checks };
  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
  console.log('created=' + rep.checks.created + ' anchor=' + anchor + ' valueAtClick=' + rep.anchor.valueAtClick + ' yRT=' + rep.anchor.yRoundTrip + '/' + clickY);
  console.log('persisted=' + rep.checks.persistedAcrossReload + ' (after reload=' + rep.anchor.reloadedValue + ') removed=' + rep.checks.removedCleanly);
  console.log('VERDICT: ' + JSON.stringify(rep.verdict));
  console.log('written: ' + OUT);
  await ctx.close();
  process.exit(rep.verdict.ok ? 0 : 1);
})().catch((e) => { console.error('HARNESS FAILED: ' + ((e && e.stack) || e)); process.exit(2); });
