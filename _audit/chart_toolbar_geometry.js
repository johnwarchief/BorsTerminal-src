// _audit/chart_toolbar_geometry.js — هندسۀِ نوارِ ابزارِ چارت درِ ۱۳۶۶×۷۶۸ وِ ۱۶۰۰×۹۰۰
//
// نشانه‌ای که درِ اسکرین‌شاتِ «ours_folad_weekly.png» دیده شد: برچسبِ «تنظیمات»
// رویِ آیکنِ خودش و «LineCha» رویِ متنِ کناری نشسته بود. این هارنس همان را
// عدد می‌کند: جعبۀِ هر کنترل، همپوشانیِ دوتایی، و سرریزِ متن (scrollWidth >
// clientWidth) — و اگر چیزی بیرون بزند، با کدِ خروجِ ناموفق تمام می‌شود.
//
// اجرا: node _audit/chart_toolbar_geometry.js
const path = require('path');
const fs = require('fs');
const pw = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));
const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, '_audit', 'chart_toolbar_geometry.json');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = process.env.BORS_BASE || 'http://localhost:5173';
const SYM = 'فولاد';
const VIEWPORTS = [[1366, 768], [1600, 900]];

const MEASURE = () => {
  const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();
  // فقط کنترلِ *دیدنی*: پنلِ جمع‌شده در x منفی یا شاخۀِ aria-hidden، نقصِ
  // هندسی نیست؛ پیش از این همین‌ها ۲۶ سطرِ غلط گزارش می‌شدند.
  const visible = (b) => {
    if (b.closest('[hidden],[aria-hidden="true"]')) return false;
    const cs = getComputedStyle(b);
    if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) === 0) return false;
    if (!b.offsetParent && cs.position !== 'fixed') return false;
    const r = b.getBoundingClientRect();
    return r.width > 2 && r.height > 2 && r.left >= -1 && r.top >= -1;
  };
  const ctrls = [...document.querySelectorAll('button,[role="button"],[role="combobox"],select')]
    .filter(visible)
    .map((b) => {
      const r = b.getBoundingClientRect();
      const label = norm(b.getAttribute('title') || b.getAttribute('aria-label') || b.textContent).slice(0, 28);
      const chain = [];
      for (let a = b.parentElement; a && chain.length < 9; a = a.parentElement) {
        const cs = getComputedStyle(a);
        const r = a.getBoundingClientRect();
        chain.push(((a.className && String(a.className).split(' ')[0]) || a.tagName.toLowerCase())
          + `[${Math.round(r.left)},${Math.round(r.top)} ${Math.round(r.width)}x${Math.round(r.height)} ${cs.display.slice(0, 4)}/${cs.position.slice(0, 3)}]`);
      }
      return {
        label, testid: b.getAttribute('data-testid'), x: Math.round(r.left), y: Math.round(r.top),
        w: Math.round(r.width), h: Math.round(r.height),
        pos: getComputedStyle(b).position, chain: chain.join(' < '),
        clippedX: b.scrollWidth > b.clientWidth + 1, clippedY: b.scrollHeight > b.clientHeight + 1,
        overflow: b.scrollWidth > b.clientWidth + 1 ? b.scrollWidth - b.clientWidth : 0,
      };
    });

  // فقط کنترل‌هایِ هم‌سطح (نوارِ ابزارِ چارت): گروه‌هایی که y نزدیک دارند
  const overlaps = [];
  for (let i = 0; i < ctrls.length; i++) {
    for (let j = i + 1; j < ctrls.length; j++) {
      const a = ctrls[i], b = ctrls[j];
      if (Math.abs(a.y - b.y) > Math.max(a.h, b.h)) continue;
      const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
      const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
      if (ox > 2 && oy > 2) overlaps.push({
        a: a.label, b: b.label, areaPx: ox * oy, ox, oy,
        ra: `${a.x},${a.y} ${a.w}x${a.h} ${a.pos} [${a.chain}]`,
        rb: `${b.x},${b.y} ${b.w}x${b.h} ${b.pos} [${b.chain}]`,
      });
    }
  }
  const clipped = ctrls.filter((c) => c.clippedX || c.clippedY);
  // هر کنترلِ بیرونِ viewport نقصِ هندسی نیست: سطرِ آخرِ یکِ فهرستِ اسکرول‌شدنی
  // (مثلِ دیدهبانِ کناری) نصفه زیرِ تا دیده می‌شود و این رفتارِ درستِ فهرست است.
  const scrollClipped = (el) => {
    for (let a = el.parentElement; a; a = a.parentElement) {
      const cs = getComputedStyle(a);
      if (/(auto|scroll)/.test(cs.overflowY + ' ' + cs.overflowX)) return true;
    }
    return false;
  };
  const outside = [...document.querySelectorAll('button,[role="button"],[role="combobox"],select')]
    .filter(visible)
    .filter((b) => !scrollClipped(b))
    .map((b) => {
      const r = b.getBoundingClientRect();
      return { label: norm(b.getAttribute('title') || b.getAttribute('aria-label') || b.textContent).slice(0, 28),
               testid: b.getAttribute('data-testid'), x: Math.round(r.left), y: Math.round(r.top),
               w: Math.round(r.width), h: Math.round(r.height) };
    })
    .filter((c) => c.x < 0 || c.y < 0 || c.x + c.w > window.innerWidth + 1 || c.y + c.h > window.innerHeight + 1);
  return { viewport: [window.innerWidth, window.innerHeight], controls: ctrls.length, overlaps, clipped, outside,
           toolbars: document.querySelectorAll('.nn-top-toolbar').length,
           canvases: document.querySelectorAll('canvas').length,
           chartRoots: document.querySelectorAll('[data-testid="technical-fts-settings"]').length,
           dpr: window.devicePixelRatio, docScrollX: document.documentElement.scrollWidth - document.documentElement.clientWidth };
};

(async () => {
  const ctx = await pw.chromium.launchPersistentContext(
    fs.mkdtempSync(path.join(require('os').tmpdir(), 'bors-tbgeom-')),
    { executablePath: EXE, viewport: null, args: ['--no-first-run', '--disable-sync'] });
  const page = ctx.pages()[0] || await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 160)));
  await page.setViewportSize({ width: VIEWPORTS[0][0], height: VIEWPORTS[0][1] });
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
  await page.waitForTimeout(6000);

  const rep = { ranAt: new Date().toISOString(), symbol: SYM, views: {} };
  for (const [w, h] of VIEWPORTS) {
    await page.setViewportSize({ width: w, height: h });
    await page.waitForTimeout(2500);
    rep.views[`${w}x${h}`] = await page.evaluate(MEASURE);
    await page.screenshot({ path: path.join(ROOT, `_audit`, `toolbar_${w}x${h}.png`) });
  }
  rep.pageErrors = errs;
  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');

  let bad = 0;
  for (const [k, v] of Object.entries(rep.views)) {
    bad += v.overlaps.length + v.clipped.length + v.outside.length + (v.docScrollX > 1 ? 1 : 0);
    console.log(`${k}: controls=${v.controls} overlaps=${v.overlaps.length} clipped=${v.clipped.length} outside=${v.outside.length} hScroll=${v.docScrollX}`);
    for (const o of v.overlaps.slice(0, 6)) {
      const a = v.controls_list ? null : null;
      console.log(`   overlap ${o.areaPx}px²  «${o.a}» × «${o.b}» (ox=${o.ox} oy=${o.oy})`);
      console.log(`      A: ${o.ra}  B: ${o.rb}`);
    }
    for (const c of v.clipped.slice(0, 6)) console.log(`   clipped  «${c.label}»  w=${c.w} scrollW=${c.overflow ? '+' + c.overflow : '—'} x=${c.x},${c.y}`);
    for (const c of v.outside.slice(0, 6)) console.log(`   outside  «${c.label}»  x=${c.x} w=${c.w}`);
  }
  console.log(bad === 0 ? 'VERDICT: clean' : `VERDICT: ${bad} geometry defect(s)`);
  await ctx.close();
  process.exit(bad === 0 ? 0 : 1);
})().catch((e) => { console.error('HARNESS FAILED: ' + ((e && e.stack) || e)); process.exit(2); });
