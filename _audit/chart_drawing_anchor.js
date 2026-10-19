// _audit/chart_drawing_anchor.js — لنگرِ ترسیم: درِ لحظۀِ کلیک درست است یا بعدش جابه‌جا می‌شود؟
//
// گزارشِ پیشین: کلیک رویِ پیکسلِ P قیمتِ ۳۴۱۰ را ثبت کرد، در حالی که وارونِ همانِ P
// بعداً ۳۷۴۹٫۳۸ داده بود (≈۹٪). دو توضیحِ ممکن وجود دارد و این هارنس میانِ آن‌ها
// فرق می‌گذارد:
//   (الف) نقشه درِ لحظۀِ کلیک غلط بوده ⇒ نقصِ تبدیلِ رابط به موتور
//   (ب) نقشه درست بوده، ولی رسمِ خط خودش بازۀِ محور را جابه‌جا کرده (اورلی واردِ
//       auto-fit می‌شود) ⇒ وارونِ «بعد از» با «قبل از» فرق می‌کند و خط رویِ بوم
//       به نظر جابه‌جا می‌آید
// ترتیبِ سنجش: وارونِ پیش از کلیک → کلیک → مقدارِ ثبت‌شده → وارونِ پس از کلیک →
// reload → مقدارِ ثبت‌شده. هیچ عددی درِ کد ثابت نمی‌شود.
// اجرا: node _audit/chart_drawing_anchor.js
const path = require('path');
const fs = require('fs');
const pw = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));
const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, '_audit', 'chart_drawing_anchor.json');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = process.env.BORS_BASE || 'http://localhost:5173';
const SYM = 'فولاد';

const FIND_SRC = function () {
  const looks = (v) => !!v && typeof v === 'object' && typeof v.getDataList === 'function';
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
        } } }
    host = host.parentElement;
  }
  return null;
};

const INV = (pts) => {
  // جویندۀِ نمونه درِ همین تابع است: توابعِ بیرونی درِ بافتِ صفحه دیده نمی‌شوند
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
  const inv = (p) => {
    const r = c.convertFromPixel([{ x: p.x, y: p.y }], { paneId: 'candle_pane' });
    const one = (Array.isArray(r) ? r[0] : r) || {};
    return { value: Number.isFinite(one.value) ? one.value : null, timestamp: one.timestamp ?? null };
  };
  const overlays = (c.getOverlays?.() ?? []).map((o) => ({
    name: o.name, id: o.id, points: (o.points || []).map((q) => ({ value: q.value ?? null, timestamp: q.timestamp ?? null })),
  }));
  return { before: pts.map(inv), overlays, pane: c.getSize('candle_pane', 'main') };
};

(async () => {
  const ctx = await pw.chromium.launchPersistentContext(
    fs.mkdtempSync(path.join(require('os').tmpdir(), 'bors-anchor-')),
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
  await page.evaluate(`1`);

  const rep = { ranAt: new Date().toISOString(), symbol: SYM, viewport: [1366, 768] };
  const base = await page.evaluate(INV, []);
  const pane = base.pane;
  const P1 = { x: Math.round(pane.left + pane.width * 0.45), y: Math.round(pane.top + pane.height * 0.35) };
  const P2 = { x: Math.round(pane.left + pane.width * 0.65), y: Math.round(pane.top + pane.height * 0.60) };
  rep.points = [P1, P2];
  rep.baselineCount = base.overlays.length;

  // وارونِ پیش ازِ کلیک (مرجعِ «زیرِ نشانگر چه قیمتی است»)
  rep.pre = await page.evaluate(INV, [P1, P2]);

  // ابزارِ خط روند و دو کلیک
  await page.click('button[title="خط روند"]').catch(() => {});
  await page.waitForTimeout(700);
  await page.mouse.click(P1.x, P1.y);
  await page.waitForTimeout(400);
  await page.mouse.click(P2.x, P2.y);
  await page.waitForTimeout(1500);

  rep.post = await page.evaluate(INV, [P1, P2]);
  const drawn = rep.post.overlays.filter((o) => !rep.pre.overlays.some((p) => p.id === o.id));
  rep.drawn = drawn;

  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelectorAll('canvas').length > 0, null, { timeout: 90000 });
  await page.waitForTimeout(7000);
  rep.afterReload = await page.evaluate(INV, [P1, P2]);
  const kept = rep.afterReload.overlays.filter((o) => drawn.some((d) => d.id === o.id || (d.name === o.name &&
    JSON.stringify(d.points) === JSON.stringify(o.points))));
  rep.persistedSameValues = kept.length > 0;

  const stored = (drawn[0] || {}).points || [];
  const v1 = stored[0] ? stored[0].value : null;
  const rel = (a, b) => (a != null && b != null && b !== 0) ? (a - b) / b * 100 : null;
  rep.reading = {
    storedFirstValue: v1,
    preClickInverseAtP1: rep.pre.before[0].value,
    postClickInverseAtP1: rep.post.before[0].value,
    reloadInverseAtP1: rep.afterReload.before[0].value,
    errStoredVsPrePct: rel(v1, rep.pre.before[0].value),
    errStoredVsPostPct: rel(v1, rep.post.before[0].value),
    axisMovedByDrawingPct: rel(rep.post.before[0].value, rep.pre.before[0].value),
    axisMovedByReloadPct: rel(rep.afterReload.before[0].value, rep.post.before[0].value),
    verdict: v1 != null && Math.abs(rel(v1, rep.pre.before[0].value)) < 0.5
      ? 'B_AXIS_MOVED_AFTER_DRAW: کلیک درست بود؛ خودِ ترسیم بازۀِ محور را جابه‌جا کرد'
      : (v1 != null && Math.abs(rel(v1, rep.post.before[0].value)) < 0.5
        ? 'A_MAPPING_WRONG_AT_CLICK_THEN_CONSISTENT: مقدارِ ثبت‌شده با نقشۀِ پس ازِ کلیک می‌خواند، نه پیش از آن'
        : 'C_NEITHER: مقدارِ ثبت‌شده با هیچِ نگاشتِ فعلیِ محور نمی‌خواند'),
  };
  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
  console.log('stored  : ' + JSON.stringify(stored));
  console.log('pre P1  : ' + rep.pre.before[0].value + '   post P1: ' + rep.post.before[0].value + '   reload P1: ' + rep.afterReload.before[0].value);
  console.log('READING : ' + JSON.stringify(rep.reading, null, 1));
  console.log('written: ' + OUT);
  await ctx.close();
})().catch((e) => { console.error('FAILED: ' + ((e && e.stack) || e)); process.exit(1); });
