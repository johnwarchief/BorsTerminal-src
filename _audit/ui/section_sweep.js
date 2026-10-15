// _audit/ui/section_sweep.js — جاروبِ بخش‌به‌بخشِ هرِ صفحه درِ viewport هدف
//
// چرا ابزارِ صفحه‌ای کافی نیست: سه لایۀِ چسبان رویِ اینِ رابط هست (Topbar `sticky top-0 z-40`،
// نوارِ نماد `sticky top-9 z-30`، و ناوبریِ بخش‌ها `sticky top-0 z-20`). وقتیِ کاربر اسکرول
// می‌کند، ممکن است عنوانِ بخش یا کنترل‌هایِ ضروریِ آن زیرِ اینِ لایه‌ها پنهان شود — چیزی که
// درِ اسکرین‌شاتِ بالایِ صفحه دیده نمی‌شود. اینِ جاروب هرِ بخش را بهِ بالایِ ناحیۀِ دید
// می‌آورد و سپس می‌سنجد:
//   · ازِ راهِ خودِ رابط: اگر دکمه‌ی ناوبریِ بخش وجود دارد (`[data-testid="market-section-<id>"]`)
//     همان‌جا کلیک می‌شود؛ `scrollIntoView` ساختگی جایِ تعاملِ کاربر را نمی‌گیرد.
//   · آیا نوارِ چسبان، عنوانِ همانِ بخش را می‌پوشاند؟ (band = بلندترینِ `bottom` لایه‌هایِ چسبان)
//   · کنترل‌هایِ بیرونِ viewport دو می‌شوند: `hiddenByClip` (عیبِ واقعی: ancestors باِ
//     overflow hidden/clip آن را بریده‌اند) و `beyondFold` (زیرِ تا، باِ اسکرولِ صفحه قابلِرس).
//   · برشِ تصویر ازِ خودِ بخش، باِ همانِ موقعیتِ اسکرول.
//
// usage (بک‌اندِ worktree رویِ :8000):
//   MSYS_NO_PATHCONV=1 node _audit/ui/section_sweep.js --routes=/market-status,/master
//   node _audit/ui/section_sweep.js            # همهٔ routeها
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));

const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const argv = process.argv.slice(2);
const arg = (n, d) => { const h = argv.find((a) => a.startsWith('--' + n + '=')); return h ? h.split('=').slice(1).join('=') : d; };
const W = Number(arg('w', 1366)), H = Number(arg('h', 768));
const OUT = path.join(REPO, '_audit', 'ui', arg('out', 'SWEEP.json'));
const SHOTS = arg('shots', '_audit/ui/shots/sweep');
const SETTLE = Number(arg('settle', 1800));
const ROUTES_ARG = arg('routes', '');
const MAXSEC = Number(arg('max', 16));

const ALL = require('./routes.js').ROUTES;
const ROUTES = ROUTES_ARG ? ALL.filter((r) => ROUTES_ARG.split(',').includes(r[0])) : ALL;

// `main section` هر `section` تو در تو را هم می‌گیرد (پنل‌ها داخلِ خودشان `section`
// دارند)؛ جاروب فقط بخش‌هایِ سطحِ صفحه را می‌سنجد، پس والدِ section‌دار حذف می‌شود.
const SECTION_SEL = 'main section, section[id]';

const SWEEP_FN = ({ sel, only }) => {
  const vis = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };
  const inHidden = (el) => {
    for (let p = el; p; p = p.parentElement) {
      // توجه: `inert` رویِ HTMLElement.prototype در Chromium وجود دارد، پس
      // `'inert' in p` برایِ هر عنصری true است و همه‌چیز را «پنهان» می‌کرد؛
      // باید خودِ ویژگی بررسی شود.
      if (p.getAttribute && (p.getAttribute('aria-hidden') === 'true' || p.hasAttribute('inert'))) return true;
    }
    return false;
  };
  const label = (el) => {
    const id = el.id || el.getAttribute('data-testid') || '';
    const txt = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 34);
    return (id ? '#' + id : el.tagName.toLowerCase()) + (txt ? ' «' + txt + '»' : '');
  };
  const zof = (el) => { const z = parseInt(getComputedStyle(el).zIndex, 10); return Number.isNaN(z) ? 0 : z; };

  // لایه‌هایِ چسبان/ثابتِ نوارِ بالایِ صفحه که محتوا زیرِ آن‌ها می‌رود
  const stickies = [...document.querySelectorAll('body *')].filter((el) => {
    const cs = getComputedStyle(el);
    if (cs.position !== 'sticky' && cs.position !== 'fixed') return false;
    if (!vis(el)) return false;
    const r = el.getBoundingClientRect();
    return r.top < 200 && r.bottom > 0 && r.height < window.innerHeight;
  }).map((el) => {
    const r = el.getBoundingClientRect();
    return { el: label(el), top: Math.round(r.top), bottom: Math.round(r.bottom),
             x: Math.round(r.x), w: Math.round(r.width), h: Math.round(r.height), z: zof(el) };
  }).sort((a, b) => b.bottom - a.bottom);

  const all = [...document.querySelectorAll(sel)].filter((el) => vis(el) && !inHidden(el));
  const sections = all.filter((el) => !(el.parentElement && el.parentElement.closest('section')));
  const idxOf = new Map(sections.map((el, i) => [el, i]));

  const targetFor = (el) => el.querySelector('[data-testid^="section-heading-"], [id^="ms-sec"]') || el;
  if (only != null && sections[only]) {
    const t = targetFor(sections[only]);
    t.scrollIntoView({ block: 'start', behavior: 'instant' });
  }

  // بریدگیِ واقعی: عنصری که ازِ جعبۀِ یکِ ancestor باِ overflow hidden/clip بیرونِ
  // آن بزند و **هیچ** اسکرول‌کنندۀِ قابل‌اسکرولی درِ مسیرش نباشد. اگر یکی از
  // اجداد `overflow: auto|scroll` باشد و بتواند اسکرول شود، عنصر فقط زیرِ تا
  // است (beyondFold) و عیب نیست.
  const canScrollAxis = (p, axis) => {
    const cs = getComputedStyle(p);
    if (axis === 'y') return /(auto|scroll)/.test(cs.overflowY) && p.scrollHeight > p.clientHeight + 2;
    return /(auto|scroll)/.test(cs.overflowX) && p.scrollWidth > p.clientWidth + 2;
  };
  const clippedByAncestor = (el) => {
    const r = el.getBoundingClientRect();
    for (let p = el.parentElement; p && p !== document.documentElement; p = p.parentElement) {
      // اسکرول‌کنندۀِ میانی: رسیدن به عنصر با اسکرولِ همان کونتینر ممکن است
      if (canScrollAxis(p, 'y') || canScrollAxis(p, 'x')) return null;
      const cs = getComputedStyle(p);
      const hides = (o) => o === 'hidden' || o === 'clip';
      if (!hides(cs.overflowX) && !hides(cs.overflowY)) continue;
      const pr = p.getBoundingClientRect();
      if (hides(cs.overflowX) && (r.right > pr.right + 2 || r.left < pr.left - 2)) return { by: label(p), axis: 'x' };
      if (hides(cs.overflowY) && (r.bottom > pr.bottom + 2 || r.top < pr.top - 2)) return { by: label(p), axis: 'y' };
    }
    return null;
  };
  // clampِ عمدیِ متن (line-clamp / ellipsis) عیب نیست؛ باید ازِ «بریدۀِ
  // ناخوانا» بیرون بماند، وگرنه هر کارتِ دوخطی به‌عنوانِ ایراد گزارش می‌شود.
  const intentionalTrim = (c, axis) => {
    const cs = getComputedStyle(c);
    if (axis === 'y') return !!cs.webkitLineClamp && cs.webkitLineClamp !== 'none';
    return cs.textOverflow === 'ellipsis';
  };

  const measured = sections.map((el, i) => {
    el = sections[i];
    const r = el.getBoundingClientRect();
    const anchor = el.querySelector('[data-testid^="section-heading-"], [id^="ms-sec"]') || el;
    const ar = anchor.getBoundingClientRect();
    // band = نوارِ چسبانِ رویِ محتوا: لایه‌ای که ازِ نظرِ افقی رویِ بخش است و
    // زایش بالاتر ازِ محتوایِ بخش است (سایدبارِ کنارِ محتوا شمرده نمی‌شود).
    const band = stickies.filter((s) => s.z >= 0 && s.x < r.right && s.x + s.w > r.left
      && s.top < r.top + 2 && s.bottom > r.top + 2);
    const bandBottom = band.reduce((m, s) => Math.max(m, s.bottom), 0);
    const covered = [];
    if (bandBottom > 0) {
      const titles = [...anchor.matches('h1,h2,h3,[role="heading"]') ? [anchor] : [],
                      ...anchor.querySelectorAll('h1,h2,h3,[role="heading"]')];
      for (const t of titles.slice(0, 3)) {
        const tr = t.getBoundingClientRect();
        if (tr.top < bandBottom - 2 && tr.bottom > 2) covered.push({ kind: 'title', el: label(t), y: Math.round(tr.top), h: Math.round(tr.height) });
      }
    }
    const controls = [...el.querySelectorAll('button,input,select,a[href],[role="tab"],[role="menuitem"]')].filter((c) => vis(c) && !inHidden(c));
    const hiddenByClip = [];
    const beyondFold = [];
    for (const c of controls) {
      const cr = c.getBoundingClientRect();
      const out = cr.bottom > window.innerHeight + 1 || cr.top < -1 || cr.right > window.innerWidth + 1 || cr.x < -1;
      if (!out) continue;
      if (cr.bottom <= 0) { beyondFold.push({ el: label(c), y: Math.round(cr.y), why: 'above' }); continue; }
      const cut = clippedByAncestor(c);
      if (cut && !cut.canScroll) hiddenByClip.push({ el: label(c), x: Math.round(cr.x), y: Math.round(cr.y), cut: cut.by, axis: cut.axis });
      else if (cr.top >= window.innerHeight - 1) beyondFold.push({ el: label(c), y: Math.round(cr.y), why: 'below' });
      else beyondFold.push({ el: label(c), x: Math.round(cr.x), y: Math.round(cr.y), why: cut ? 'scrollable-clip' : 'edge' });
    }
    const clipped = [...el.querySelectorAll('h1,h2,h3,p,span,td,th,label,button')].filter((c) => {
      if (!vis(c) || c.children.length || inHidden(c)) return false;
      const cs = getComputedStyle(c);
      return /(hidden|clip)/.test(cs.overflowX) && c.scrollWidth - c.clientWidth > 1 && !intentionalTrim(c, 'x');
    }).slice(0, 6).map((c) => ({ el: label(c), lost: c.scrollWidth - c.clientWidth, text: (c.textContent || '').trim().slice(0, 50) }));
    // محتوایِ بلندِ غیرقابلِاسکرول داخلِ همانِ بخش (clampِ عمدیِ خطی شمرده نمی‌شود)
    const unreachable = [...el.querySelectorAll('*')].filter((c) => {
      const cs = getComputedStyle(c);
      if (!vis(c) || inHidden(c)) return false;
      if (!/(hidden|clip)/.test(cs.overflowY)) return false;
      if (intentionalTrim(c, 'y')) return false;
      return c.scrollHeight - c.clientHeight > 24;
    }).slice(0, 5).map((c) => ({ el: label(c), lost: c.scrollHeight - c.clientHeight }));

    return {
      i, id: (anchor.id || anchor.getAttribute('data-testid') || '').replace(/^section-heading-/, '') || el.id || null,
      label: label(el),
      rect: { x: Math.round(r.x), y: Math.round(ar.top), w: Math.round(r.width), h: Math.round(r.height) },
      band, bandBottom, covered, controls: controls.length,
      hiddenByClip: hiddenByClip.slice(0, 6), beyondFold: beyondFold.length, beyondSample: beyondFold.slice(0, 3),
      clipped, unreachable,
    };
  });
  return { sections: measured, stickies, count: sections.length, scroller: (() => {
    const sc = document.querySelector('.app-content') || document.scrollingElement;
    return { el: sc.className || sc.tagName, top: Math.round(sc.scrollTop), h: sc.clientHeight, sh: sc.scrollHeight };
  })() };
};

// همانِ فیلترِ بخش‌ها را می‌سازد و اگر دکمه‌ی ناوبریِ رابط وجود دارد همان را
// می‌زند؛ `scrollIntoView` ساختگی جایِ تعاملِ کاربر (و `scroll-margin` خودش)
// را نمی‌گیرد و باعث شد «UNDER-STICKY» کاذب گزارش شود.
const NAV_FN = ({ sel, i }) => {
  const vis = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };
  const inHidden = (el) => {
    for (let p = el; p; p = p.parentElement)
      if (p.getAttribute && (p.getAttribute('aria-hidden') === 'true' || p.hasAttribute('inert'))) return true;
    return false;
  };
  const sections = [...document.querySelectorAll(sel)]
    .filter((el) => vis(el) && !inHidden(el))
    .filter((el) => !(el.parentElement && el.parentElement.closest('section')));
  const el = sections[i];
  if (!el) return { via: 'missing', id: null };
  const anchor = el.querySelector('[data-testid^="section-heading-"], [id^="ms-sec"]') || el;
  const id = (anchor.id || anchor.getAttribute('data-testid') || '').replace(/^section-heading-/, '');
  const btn = id && document.querySelector(`[data-testid="market-section-${id}"]`);
  if (btn) { btn.click(); return { via: 'nav-button', id }; }
  anchor.scrollIntoView({ block: 'start', behavior: 'instant' });
  return { via: 'scrollIntoView', id };
};

(async () => {
  const browser = await chromium.launch({
    executablePath: EXE,
    args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1', '--remote-debugging-port=0'],
  });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + String(e).slice(0, 200)));
  page.on('response', (r) => { if (r.status() >= 400) errs.push('HTTP ' + r.status() + ' ' + decodeURIComponent(r.url()).slice(0, 140)); });

  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2500);
  }

  const report = { ranAt: new Date().toISOString(), viewport: { W, H }, pages: [] };
  for (const [route, marker, min] of ROUTES) {
    await page.goto(BASE + '/#' + route, { waitUntil: 'domcontentloaded' });
    if (marker) {
      await page.waitForFunction(([m, k]) => document.querySelectorAll(m).length >= k, [marker, min || 1],
        { timeout: 60000 }).catch(() => {});
    }
    await page.waitForTimeout(SETTLE);
    const first = await page.evaluate(SWEEP_FN, { sel: SECTION_SEL, only: null });
    const n = Math.min(first.count, MAXSEC);
    const rows = [];
    console.log(`\n== ${route}  sections=${first.count}  scroller=${first.scroller.el} ${first.scroller.h}/${first.scroller.sh}`);
    for (const s of first.stickies.filter((s) => s.bottom <= H).slice(0, 8)) {
      console.log(`   layer z${s.z} top=${s.top} bottom=${s.bottom} h=${s.h} x=${s.x} w=${s.w} ${s.el}`);
    }
    for (let i = 0; i < n; i++) {
      // راهِ رابطِ کاربر: اگر دکمه‌ی پرشِ همانِ بخش هست، همان کلیک شود
      const nav = await page.evaluate(NAV_FN, { sel: SECTION_SEL, i });
      await page.waitForFunction(() => {
        const sc = document.querySelector('.app-content') || document.scrollingElement;
        const t = sc.scrollTop;
        const same = window.__swPrev === t;
        window.__swPrev = t;
        return same;
      }, null, { timeout: 4000, polling: 150 }).catch(() => {});
      const out = await page.evaluate(SWEEP_FN, { sel: SECTION_SEL, only: null });
      await page.waitForTimeout(120);
      const me = out.sections[i];
      if (!me) continue;
      me.via = nav.via;
      rows.push(me);
      const dir = path.join(REPO, SHOTS);
      fs.mkdirSync(dir, { recursive: true });
      const safe = route.replace(/[^a-zA-Z0-9_-]+/g, '_').slice(0, 34);
      const tag = (me.id || ('sec' + i)).replace(/[^a-zA-Z0-9_-]+/g, '_').slice(0, 30);
      const top = Math.max(0, me.rect.y);
      const clip = { x: 0, y: Math.min(top, H - 2), width: W, height: Math.max(2, Math.min(me.rect.h, H - Math.min(top, H - 2))) };
      if (clip.height > 3) {
        await page.screenshot({ path: path.join(dir, safe + '__' + tag + '.png'), clip });
      }
      const flags = [];
      if (me.covered.length) flags.push((nav.via === 'nav-button' ? 'TITLE-UNDER-BAND(' : 'band-overlap-after-scrollTo(') + me.bandBottom + 'px)');
      if (me.hiddenByClip.length) flags.push('CLIPPED=' + me.hiddenByClip.length);
      if (me.unreachable.length) flags.push('UNSCROLLABLE=' + me.unreachable.length);
      if (me.clipped.length) flags.push('TEXTCLIP=' + me.clipped.length);
      if (me.beyondFold) flags.push('below-fold=' + me.beyondFold);
      console.log(`${route} [${i}] ${(me.id || '?').padEnd(24)} y=${String(me.rect.y).padStart(5)} h=${String(me.rect.h).padStart(5)} ctl=${String(me.controls).padStart(3)}  ${flags.length ? flags.join(' ') : 'OK'}`);
      for (const c of me.covered.slice(0, 3)) console.log('      covered: ' + c.kind + ' ' + c.el + ' y=' + c.y);
      for (const c of me.hiddenByClip.slice(0, 3)) console.log('      clipped-by ' + c.cut + '(' + c.axis + '): ' + c.el);
      for (const c of me.unreachable.slice(0, 3)) console.log('      unscrollable: ' + c.el + ' −' + c.lost + 'px');
      for (const c of me.clipped.slice(0, 3)) console.log('      textclip: ' + c.el + ' −' + c.lost + 'px «' + c.text + '»');
    }
    report.pages.push({ route, stickies: first.stickies, scroller: first.scroller, sections: rows,
      pageErrors: errs.splice(0, errs.length).slice(0, 8) });
  }
  fs.writeFileSync(OUT, JSON.stringify(report, null, 1));
  console.log('\nwrote ' + OUT);
  await browser.close();
  return 0;
})().then((rc) => process.exit(rc)).catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
