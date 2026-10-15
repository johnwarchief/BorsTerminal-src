// _audit/ui/fit_check.js — جاافتادنِ ظرف‌هایِ تمام‌قد + رسیدن بهِ آخرینِ ردیف
//
// چرا یکِ ابزارِ جدا: مرحلۀِ ۳ مأموریت می‌خواهد بدانی «آیا محتوایِ بلند باِ
// اسکرول درست قابلِمشاهده است» و «آیا ظرفِ تمام‌قد ازِ viewport بیرون نمی‌زند».
// جاروب‌هایِ قبلی یا فقطِ عنصرهایِ تعاملی را می‌دیدند یا فقطِ overflow افقی را.
// اینِ اسکریپت برایِ هرِ route:
//   · جعبۀِ ظرف‌هایِ بزرگ (`.tv-workbench`، `chart-area`، `tape-scroll`، …) و
//     فاصلۀِ لبۀِ پایینشان تاِ viewport (مثبت = بیرون‌زدگی)
//   · `app-content` تاِ کجا اسکرول می‌شود و درِ انتهایِ اسکرول، آخرینِ ردیف/کنترلِ
//     همانِ جدول واقعاً داخلِ viewport است؟
//   · overflow افقی و خطاهایِ کنسول/شبکه
// usage: MSYS_NO_PATHCONV=1 node _audit/ui/fit_check.js [--routes=/technical/فولاد,...]
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const arg = (n, d) => { const h = process.argv.find((a) => a.startsWith('--' + n + '=')); return h ? h.split('=').slice(1).join('=') : d; };
const W = Number(arg('w', 1366)), H = Number(arg('h', 768));
const PICK = arg('pick', '1') === '1';
const ROUTES_ARG = arg('routes', '');

const BOXES = ['header.glass-strip', '[class*="top-9"]', '.app-main', '.tv-workbench',
  '[data-testid="chart-area"]', '[data-testid="tape-scroll"]', '[data-testid="fts-screen-scroll"]',
  '[data-testid="technical-sidebar"]', '[data-testid="fts-dock"]'];

const FIT = ({ boxes }) => {
  const vw = innerWidth, vh = innerHeight;
  const sc = document.querySelector('.app-content') || document.scrollingElement;
  const BOXES = boxes;
  const box = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return null;
    return { sel, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
             belowPx: Math.round(r.bottom - vh), abovePx: Math.round(-r.top) };
  };
  // ظرف‌هایِ اسکرول‌دارِ داخلی: آخرینِ عنصرِ قابلِتعامل بعد ازِ اسکرولِ تاِ آخر دیدنی است؟
  const scrollers = [...document.querySelectorAll('.app-content, [data-testid="tape-scroll"], [data-testid="fts-screen-scroll"], [class*="overflow-y-auto"]')]
    .filter((el) => el.scrollHeight > el.clientHeight + 24)
    .slice(0, 6)
    .map((el) => {
      const tag = el.getAttribute('data-testid') || el.className.toString().slice(0, 24);
      const maxTop = el.scrollHeight - el.clientHeight;
      el.scrollTop = maxTop;
      const ctlSel = 'button,[role="button"],a[href],input,select';
      // فقطِ کنترل‌هایی که «نزدیک‌ترینِ» اسکرول‌کننده‌شان همانِ اینِ ظرف است؛
      // ردیف‌هایِ جدولِ مجازی‌شده بهِ اسکرولرِ داخلیِ خودشان تعلق دارند و
      // بیرونِ تا بودنشان درِ اینجا عیبِ ظرفِ بیرونی نیست
      const nearest = (c) => {
        for (let p = c.parentElement; p; p = p.parentElement) {
          const cs = getComputedStyle(p);
          if (/(auto|scroll)/.test(cs.overflowY) && p.scrollHeight > p.clientHeight + 2) return p;
        }
        return null;
      };
      const kids = [...el.querySelectorAll(ctlSel)].filter((c) => {
        const cs = getComputedStyle(c);
        return cs.display !== 'none' && c.getBoundingClientRect().height > 1 && nearest(c) === el;
      });
      let last = null;
      for (const c of kids) {
        const r = c.getBoundingClientRect();
        if (r.top > vh - 2 && (!last || r.top < last.top)) last = { top: Math.round(r.top), el: (c.getAttribute('data-testid') || c.id || c.tagName) + ' «' + String(c.textContent || '').trim().slice(0, 22) + '»' };
      }
      const reach = kids.length ? kids.every((c) => { const r = c.getBoundingClientRect(); return r.bottom > 0 && r.top < vh; }) || !!last === false : true;
      return { tag, scrollTop: Math.round(el.scrollTop), maxTop: Math.round(maxTop),
               hiddenRows: last ? 1 + [...kids].filter((c) => c.getBoundingClientRect().top > vh - 2).length : 0,
               sample: last ? last.el + ' @' + last.top : null,
               verdict: last ? 'STILL-OFFSCREEN' : (kids.length ? 'REACHABLE' : 'no-controls') };
    });
  document.querySelector('.app-content') && (document.querySelector('.app-content').scrollTop = 0);
  return {
    vw, vh, ovX: document.documentElement.scrollWidth - vw,
    scroller: { h: sc.clientHeight, sh: sc.scrollHeight, top: Math.round(sc.scrollTop) },
    boxes: BOXES.map(box).filter(Boolean),
    scrollers,
  };
};

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1', '--remote-debugging-port=0'] });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + String(e).slice(0, 140)));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 140)); });
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2500);
  }
  if (PICK) {
    await page.goto(BASE + '/#/market', { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => document.querySelectorAll('[data-testid="tape-row"]').length > 5, null, { timeout: 60000 }).catch(() => {});
    const row = page.locator('[data-testid="tape-row"]').first();
    if (await row.count()) { await row.click(); await page.waitForTimeout(1500); }
  }
  const ALL = require('./routes.js').ROUTES;
  const routes = ROUTES_ARG ? ALL.filter((r) => ROUTES_ARG.split(',').includes(r[0])) : ALL;
  const out = { ranAt: new Date().toISOString(), viewport: { W, H }, picked: PICK, routes: [] };
  for (const [route, marker, min] of routes) {
    await page.goto(BASE + '/#' + route, { waitUntil: 'domcontentloaded' });
    if (marker) await page.waitForFunction(([m, k]) => document.querySelectorAll(m).length >= k, [marker, min || 1], { timeout: 45000 }).catch(() => {});
    await page.waitForTimeout(1800);
    const f = await page.evaluate(FIT, { boxes: BOXES });
    const over = f.boxes.filter((b) => b.belowPx > 2 || b.abovePx > 2);
    console.log(`\n== ${route}  ovX=${f.ovX}px  scroller=${f.scroller.h}/${f.scroller.sh}`);
    for (const b of f.boxes) console.log(`   ${b.sel.padEnd(38)} y=${String(b.y).padStart(5)} h=${String(b.h).padStart(5)} bottom=${String(b.y + b.h).padStart(5)} ${b.belowPx > 2 ? 'OVERFLOW+' + b.belowPx : b.abovePx > 2 ? 'CLIPPED-TOP-' + b.abovePx : 'fits'}`);
    for (const s of f.scrollers) console.log(`   scroll «${s.tag}» max=${s.maxTop} → ${s.verdict}${s.sample ? '  ' + s.sample : ''}`);
    out.routes.push({ route, ...f, overflow: over, errors: errs.splice(0, errs.length).slice(0, 5) });
  }
  fs.writeFileSync(path.join(REPO, '_audit', 'ui', 'FIT.json'), JSON.stringify(out, null, 1));
  console.log('\nwrote _audit/ui/FIT.json');
  await browser.close();
  return 0;
})().then((rc) => process.exit(rc)).catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
