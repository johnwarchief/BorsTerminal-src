// _audit/ui/layout_audit.js — ابزارِ سنجشِ Layout رویِ هرِ route درِ viewport هدف
//
// چرا screenshot کافی نیست: بریدگیِ متن، سرریزِ افقی، کنترلِ بیرونِ viewport و
// محتوایِ اسکرول‌نشدنی فقط باِ اندازه‌گیریِ DOM قابلِ شمارش‌اند و باید قبل/بعد
// ازِ اصلاح باِ یکِ معیارِ یکسان سنجیده شوند. اینِ ابزار درِ Edgeِ واقعی اجرا
// می‌شود (jsdom نه) و برایِ هرِ route اینِ پنجِ نشانه را می‌نویسد:
//   ۱) سرریزِ افقیِ ناخواسته درِ بدنهٔ صفحه + عاملِ آن
//   ۲) بریدگیِ سختِ متن (overflow hidden بی‌ellipsis) و بریدگیِ باِ ellipsis
//   ۳) کنترلِ تعاملی که بیرونِ viewport افتاده (چپ/راست/بالا/پایین)
//   ۴) پنلی که محتوا‌اش بلندترِ ارتفاعِ خودش است ولیِ اسکرول ندارد (دسترسیِ ناممکن)
//   ۵) خطایِ کنسول و درخواستِ شکست‌خورده درِ همانِ route
//
// usage (از ریشۀِ worktree، بک‌اند رویِ 127.0.0.1:8000):
//   node _audit/ui/layout_audit.js --mode=em --out _audit/ui/EM_1366x768.json
//   node _audit/ui/layout_audit.js --mode=real --out _audit/ui/REAL_maximized.json
//   node _audit/ui/layout_audit.js --routes=/market,/technical/خوز
const os = require('os');
const fs = require('fs');
const path = require('path');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));

const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const argv = process.argv.slice(2);
const arg = (name, dflt) => {
  const hit = argv.find((a) => a.startsWith('--' + name + '='));
  return hit ? hit.split('=').slice(1).join('=') : dflt;
};
const MODE = arg('mode', 'em');                              // em = viewportِ هدفِ ثابت، real = پنجرۀِ حداکثرشدۀِ واقعی
const W = Number(arg('w', 1366));
const H = Number(arg('h', 768));
const OUT = path.join(REPO, '_audit', 'ui', arg('out', MODE + '_layout.json'));
const SHOTS = arg('shots', '');                              // پوشۀِ اسکرین‌شات (اختیاری)
const DETAIL = arg('detail', '');                            // پوشۀِ برشِ مظنون‌ها (--detail=...)
const ROUTES_ARG = arg('routes', '');
const SETTLE_MS = Number(arg('settle', 2600));
const DEADLINE = Number(arg('deadline', 90000));

// فهرستِ routeها: هرِ سطر = [hash, نشانۀِ آمادگی (CSS selector، دلخواه), حداقلِ تعدادِ لازمِ آن نشانۀِ ready]
const ALL_ROUTES = require('./routes.js').ROUTES;
const ROUTES = ROUTES_ARG
  ? ALL_ROUTES.filter((r) => ROUTES_ARG.split(',').includes(r[0]))
  : ALL_ROUTES;

// اینِ تابع درِ صفحه اجرا می‌شود و فقط می‌خواند؛ چیزی نمی‌نویسد.
const AUDIT_FN = () => {
  const vw = window.innerWidth, vh = window.innerHeight;
  const de = document.documentElement;
  const vis = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };
  const box = (el) => {
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
  };
  const label = (el) => {
    const id = el.getAttribute('data-testid') || el.id || '';
    const cls = (el.className || '').toString().trim().split(/\s+/).slice(0, 3).join('.');
    const txt = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 42);
    return el.tagName.toLowerCase() + (id ? '#' + id : '') + (cls ? '.' + cls : '') + (txt ? ' «' + txt + '»' : '');
  };
  const scrollableH = (el) => {
    for (let p = el.parentElement; p; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (/(auto|scroll)/.test(cs.overflowX)) return true;
    }
    return false;
  };

  const bodyOverflowX = de.scrollWidth - vw;
  const offenders = [];
  if (bodyOverflowX > 1) {
    document.querySelectorAll('body *').forEach((el) => {
      if (offenders.length >= 12 || !vis(el)) return;
      const r = el.getBoundingClientRect();
      if (r.right > vw + 2 && !scrollableH(el)) {
        // فقطِ عنصرهایی که خودشانِ آخرین لایهٔ سرریزند (نهِ جدِ سرریز)
        const parentOver = el.parentElement && el.parentElement.getBoundingClientRect().right > vw + 2
          && !scrollableH(el.parentElement);
        if (!parentOver) offenders.push({ el: label(el), box: box(el), right: Math.round(r.right) });
      }
    });
  }

  const clipped = [], ellipsised = [];
  const withText = [...document.querySelectorAll('body *')].filter((el) =>
    el.children.length === 0 && (el.textContent || '').trim().length > 1 && vis(el));
  withText.forEach((el) => {
    if (el.scrollWidth - el.clientWidth <= 1) return;
    const cs = getComputedStyle(el);
    const hidden = /(hidden|clip)/.test(cs.overflowX);
    if (!hidden) return;
    const item = { el: label(el), lost: el.scrollWidth - el.clientWidth, box: box(el) };
    if (cs.textOverflow === 'ellipsis') { if (ellipsised.length < 12) ellipsised.push(item); }
    else if (clipped.length < 20) clipped.push(item);
  });

  // کنترلِ «بیرون» دو چیزِ متفاوت است: آنچه باِ اسکرولِ هرِ ancestorِ
  // scrollable قابلِرس است (زیرِ تا → طبیعی) و آنچه واقعاً پنهان مانده
  // (درِ مسیرش هیچِ اسکرول‌کننده‌ای نیست، یا داخلِ subtreesِ inert/closed است).
  const inHiddenSubtree = (el) => {
    for (let p = el; p; p = p.parentElement)
      if (p.getAttribute && (p.getAttribute('aria-hidden') === 'true' || p.hasAttribute('inert'))) return true;
    return false;
  };
  const reachableByScroll = (el) => {
    for (let p = el.parentElement; p && p !== document.documentElement; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (/(auto|scroll)/.test(cs.overflowY) && p.scrollHeight > p.clientHeight + 2) return true;
      if (/(auto|scroll)/.test(cs.overflowX) && p.scrollWidth > p.clientWidth + 2) return true;
    }
    return false;
  };
  const offscreen = [];
  let belowFold = 0;
  let inertOffscreen = 0;
  document.querySelectorAll('button,[role="button"],input,select,a[href],a[role="tab"],[role="tab"],[role="menuitem"]')
    .forEach((el) => {
      if (!vis(el)) return;
      const r = el.getBoundingClientRect();
      const bad = r.right <= 1 || r.bottom <= 1 || r.x >= vw - 1 || r.y >= vh - 1;
      if (!bad) return;
      if (inHiddenSubtree(el)) { inertOffscreen++; return; }
      if (reachableByScroll(el)) { belowFold++; return; }
      if (offscreen.length < 15) offscreen.push({ el: label(el), box: box(el), vw, vh });
    });

  const unreachable = [];
  document.querySelectorAll('body *').forEach((el) => {
    if (unreachable.length >= 12 || !vis(el)) return;
    if (el.scrollHeight - el.clientHeight <= 24) return;
    const cs = getComputedStyle(el);
    if (/(auto|scroll)/.test(cs.overflowY)) return;
    // clampِ عمدیِ چندخطی (line-clamp) محتوا را می‌بَرد ولی عیب نیست
    if (cs.webkitLineClamp && cs.webkitLineClamp !== 'none') return;
    if (el === document.body || el === de) return;
    unreachable.push({ el: label(el), hiddenPx: el.scrollHeight - el.clientHeight, box: box(el) });
  });

  const canvases = [...document.querySelectorAll('canvas')].filter(vis).map((c) => box(c));
  const fixedLayers = [...document.querySelectorAll('body *')].filter((el) => {
    const cs = getComputedStyle(el);
    return (cs.position === 'fixed' || cs.position === 'absolute') && vis(el)
      && (el.getBoundingClientRect().bottom > vh + 2 || el.getBoundingClientRect().right > vw + 2);
  }).slice(0, 8).map((el) => ({ el: label(el), box: box(el) }));

  return {
    vw, vh, dpr: window.devicePixelRatio, zoomCssPx: getComputedStyle(de).fontSize,
    docScrollW: de.scrollWidth, docScrollH: de.scrollHeight,
    bodyOverflowX, bodyOverflowY: de.scrollHeight - vh,
    offenders, clipped, ellipsised, offscreen, belowFold, inertOffscreen, unreachable, canvases, fixedLayers,
    domNodes: document.getElementsByTagName('*').length,
    hash: location.hash,
    title: (document.body.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60),
  };
};

// حالتِ تفصیلی: هرِ مظنون (بریدگی/ellipsis/محتوایِ نهفته/کنترلِ بیرون) را باِ
// data-ui-audit نشان‌دار می‌کند، سبک‌هایِ محاسبه‌شدۀِ خودش را برمی‌گرداند و ازِ
// همانِ ناحیه برشِ تصویر می‌گیرد — تا داوری «ایراد است یا طراحی» برِ پایهٔ داده
// باشد نه حدس ازِ اسکرین‌شاتِ کاملِ صفحه.
const DETAIL_FN = () => {
  const out = [];
  const vis = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };
  const mark = (el, kind, extra) => {
    const n = out.length;
    el.setAttribute('data-ui-audit', String(n));
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    out.push({
      n, kind,
      tag: el.tagName.toLowerCase(),
      id: el.id || null,
      testid: el.getAttribute('data-testid') || null,
      cls: (el.className || '').toString().slice(0, 90),
      text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 70),
      styles: {
        overflowX: cs.overflowX, overflowY: cs.overflowY, textOverflow: cs.textOverflow,
        whiteSpace: cs.whiteSpace, lineClamp: cs.webkitLineClamp || null, display: cs.display,
        fontSize: cs.fontSize, direction: cs.direction, position: cs.position,
      },
      lostX: el.scrollWidth - el.clientWidth, lostY: el.scrollHeight - el.clientHeight,
      rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
      vw: window.innerWidth, vh: window.innerHeight, extra: extra || null,
    });
  };
  [...document.querySelectorAll('body *')].forEach((el) => {
    if (!vis(el) || out.length >= 40) return;
    const cs = getComputedStyle(el);
    const hidden = /(hidden|clip)/.test(cs.overflowX);
    if (el.children.length === 0 && hidden && el.scrollWidth - el.clientWidth > 1) {
      mark(el, cs.textOverflow === 'ellipsis' ? 'ellipsis' : 'hard-clip');
    }
    if (el.scrollHeight - el.clientHeight > 24 && /(hidden|clip)/.test(cs.overflowY)
        && el !== document.body && el !== document.documentElement) {
      mark(el, 'unreachable-y', el.scrollHeight - el.clientHeight);
    }
    const r = el.getBoundingClientRect();
    if (r.right < 1 || r.x > window.innerWidth - 1 || r.x < -1) {
      if (/^(BUTTON|INPUT|SELECT|A)$/.test(el.tagName) || el.getAttribute('role') === 'tab') mark(el, 'offscreen-x');
    }
  });
  return out;
};

async function loginIfNeeded(page) {
  if (!(await page.evaluate(() => !!document.querySelector('input[type="password"]')))) return;
  const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
  const du = (src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
  const dp = (src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
  await page.locator('input[type="text"]').first().fill(du);
  await page.locator('input[type="password"]').first().fill(dp);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(3000);
}

(async () => {
  const browser = await chromium.launch({
    executablePath: EXE,
    args: MODE === 'real'
      ? ['--no-first-run', '--disable-sync', '--start-maximized', '--remote-debugging-port=0']
      : ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1', '--remote-debugging-port=0'],
  });
  const ctx = await browser.newContext(MODE === 'real'
    ? { viewport: null }
    : { viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const consoleErrors = [], netErrors = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 220)); });
  page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + String(e).slice(0, 220)));
  page.on('response', (r) => { if (r.status() >= 400) netErrors.push(`HTTP ${r.status()} ${decodeURIComponent(r.url()).slice(0, 160)}`); });
  page.on('requestfailed', (r) => netErrors.push('FAILED(' + ((r.failure() && r.failure().errorText) || '?') + ') '
    + decodeURIComponent(r.url()).slice(0, 160)));

  const env = { mode: MODE, ranAt: new Date().toISOString(), base: BASE, routes: ROUTES.length };
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  await loginIfNeeded(page);
  const shell = await page.evaluate(AUDIT_FN);
  env.physicalViewport = { w: shell.vw, h: shell.vh };
  env.devicePixelRatio = shell.dpr;
  env.userAgent = await page.evaluate(() => navigator.userAgent);

  const report = { env, pages: [] };
  for (const [route, marker, min] of ROUTES) {
    const before = { c: consoleErrors.length, n: netErrors.length };
    await page.goto(BASE + '/#' + route, { waitUntil: 'domcontentloaded' });
    let readyBy = 'timeout';
    if (marker) {
      try {
        await page.waitForFunction(
          ([m, k]) => document.querySelectorAll(m).length >= k, [marker, min || 1],
          { timeout: DEADLINE });
        readyBy = 'marker';
      } catch (e) { /* نشانۀِ خاصِ آنِ صفحه نیامد؛ همان هم اطلاع داده می‌شود */ }
    }
    await page.waitForTimeout(SETTLE_MS);
    const m = await page.evaluate(AUDIT_FN);
    m.route = route;
    m.readyBy = readyBy;
    m.consoleErrors = consoleErrors.slice(before.c);
    m.netErrors = netErrors.slice(before.n);
    if (SHOTS) {
      const dir = path.join(REPO, SHOTS);
      fs.mkdirSync(dir, { recursive: true });
      const safe = route.replace(/[^a-zA-Z0-9_-]+/g, '_').slice(0, 48);
      m.screenshot = SHOTS + '/' + safe + '.png';
      await page.screenshot({ path: path.join(dir, safe + '.png'), fullPage: false });
    }
    if (DETAIL) {
      const suspects = await page.evaluate(DETAIL_FN);
      m.suspects = suspects;
      const dir = path.join(REPO, DETAIL);
      fs.mkdirSync(dir, { recursive: true });
      const safe = route.replace(/[^a-zA-Z0-9_-]+/g, '_').slice(0, 40);
      for (const s of suspects) {
        if (s.rect.w <= 0 || s.rect.h <= 0) continue;
        const clip = {
          x: Math.max(0, s.rect.x - 6), y: Math.max(0, s.rect.y - 6),
          width: Math.min(s.rect.w + 12, s.vw - Math.max(0, s.rect.x - 6)),
          height: Math.min(s.rect.h + 12, s.vh - Math.max(0, s.rect.y - 6)),
        };
        if (clip.width < 2 || clip.height < 2) continue;
        s.crop = DETAIL + '/' + safe + '__' + s.n + '_' + s.kind + '.png';
        await page.screenshot({ path: path.join(dir, safe + '__' + s.n + '_' + s.kind + '.png'), clip });
      }
      console.log('   suspects: ' + suspects.map((s) => `${s.n}:${s.kind}`).join(' '));
    }
    report.pages.push(m);
    console.log(
      `${route.padEnd(26)} ready=${readyBy.padEnd(7)} ovX=${String(m.bodyOverflowX).padStart(5)}px `
      + `ovY=${String(m.bodyOverflowY).padStart(5)}px hardClip=${String(m.clipped.length).padStart(2)} `
      + `ellipsis=${String(m.ellipsised.length).padStart(2)} offscreen=${String(m.offscreen.length).padStart(2)} `
      + `unreachable=${String(m.unreachable.length).padStart(2)} canvas=${String(m.canvases.length).padStart(2)} `
      + `err=${m.consoleErrors.length}/${m.netErrors.length} dom=${m.domNodes}`);
    if (m.clipped.length) console.log('   hard-clip: ' + m.clipped.slice(0, 4).map((c) => `${c.el} (−${c.lost}px)`).join(' | '));
    if (m.offscreen.length) console.log('   offscreen: ' + m.offscreen.slice(0, 4).map((c) => c.el + ' ' + JSON.stringify(c.box)).join(' | '));
    if (m.unreachable.length) console.log('   unreachable: ' + m.unreachable.slice(0, 3).map((c) => `${c.el} (+${c.hiddenPx}px نهفته)`).join(' | '));
    if (m.bodyOverflowX > 1) console.log('   ovX-source: ' + m.offenders.slice(0, 3).map((c) => `${c.el} right=${c.right}`).join(' | '));
    if (m.consoleErrors.length) console.log('   console: ' + m.consoleErrors.slice(0, 2).join(' ⏐ '));
    if (m.netErrors.length) console.log('   network: ' + m.netErrors.slice(0, 3).join(' ⏐ '));
  }
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(report, null, 1));
  console.log('\nwrote ' + OUT);
  await browser.close();
  return 0;
})().then((rc) => process.exit(rc)).catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
