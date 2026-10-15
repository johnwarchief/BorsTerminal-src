// _audit/ui/sticky_probe.js — لایه‌هایِ چسبان درِ حالتِ اسکرول‌شده + هرِ عنصرِ بریده
//
// سؤالِ مشخص: ناوبریِ بخش‌ها `sticky top-0 z-20` است و Topbar `sticky top-0 z-40 h-9`.
// اگر هرِ دو بهِ لبۀِ بالایِ `.app-content` بچسبند، nav زیرِ topbar می‌رود و برایِ
// کاربر ناپدید می‌شود. `elementFromPoint` رویِ مرکزِ nav پاسخِ قطعی می‌دهد (کِسی
// بالاتر ازِ آن نقاشی می‌شود؟). همچنین `#ms-chart-host` باِ overflowhidden و
// scrollHeight > clientHeight گزارش شده: آیا ۱۰۲ پیکسلِ محتوا دست‌نیافتنی است؟
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const arg = (n, d) => { const h = process.argv.find((a) => a.startsWith('--' + n + '=')); return h ? h.split('=').slice(1).join('=') : d; };
const W = Number(arg('w', 1366)), H = Number(arg('h', 768));
const ROUTE = arg('route', '/market-status');

const PROBE = () => {
  const sc = document.querySelector('.app-content') || document.scrollingElement;
  const doc = document.scrollingElement;
  const named = ['header.glass-strip', '[data-testid="market-section-nav"]', '.symbol-context-strip', 'aside', '.app-main', 'main > div']
    .map((sel) => [...document.querySelectorAll(sel)].map((el) => {
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      return { sel, pos: cs.position, z: cs.zIndex, top: Math.round(r.top), bottom: Math.round(r.bottom),
               h: Math.round(r.height), ovY: cs.overflowY };
    })).flat();
  const layers = [...document.querySelectorAll('body *')].filter((el) => {
    const cs = getComputedStyle(el);
    return (cs.position === 'sticky' || cs.position === 'fixed') && el.getBoundingClientRect().height > 1
      && el.getBoundingClientRect().width > 1 && !el.closest('[inert]');
  }).map((el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const cx = Math.round(r.x + r.width / 2), cy = Math.round(r.y + Math.min(r.height / 2, 20));
    const hit = document.elementFromPoint(Math.max(1, Math.min(cx, innerWidth - 2)), Math.max(1, Math.min(cy, innerHeight - 2)));
    const onTop = !!hit && (hit === el || el.contains(hit) || (hit && hit.contains(el)));
    return { sel: (el.id ? '#' + el.id : '') + (el.getAttribute('data-testid') ? '[t=' + el.getAttribute('data-testid') + ']' : '') || el.tagName.toLowerCase(),
      cls: String(el.className).slice(0, 60), z: cs.zIndex || 'auto', pos: cs.position,
      top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height),
      x: Math.round(r.x), w: Math.round(r.width), onTop,
      coveredBy: onTop ? null : (hit ? (hit.id || hit.getAttribute('data-testid') || hit.tagName) + ' «' + String(hit.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 26) + '»' : 'null') };
  }).filter((l) => l.top < 260 && l.bottom > 0);
  const clip = [...document.querySelectorAll('main *')].filter((el) => {
    const cs = getComputedStyle(el);
    if (!/(hidden|clip)/.test(cs.overflowY)) return false;
    if (el.scrollHeight - el.clientHeight <= 24) return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  }).map((el) => ({ sel: (el.id ? '#' + el.id : el.tagName.toLowerCase()) + (el.getAttribute('data-testid') ? '[t=' + el.getAttribute('data-testid') + ']' : ''),
    oy: getComputedStyle(el).overflowY, lost: el.scrollHeight - el.clientHeight, h: Math.round(el.getBoundingClientRect().height),
    last: (el.lastElementChild ? (el.lastElementChild.getAttribute('data-testid') || el.lastElementChild.className || el.lastElementChild.tagName).toString().slice(0, 50) : '') }));
  return { scrollTop: Math.round(sc.scrollTop), clientH: sc.clientHeight, scrollH: sc.scrollHeight,
           docTop: Math.round(doc.scrollTop), docClientH: doc.clientHeight, docScrollH: doc.scrollHeight,
           winY: Math.round(window.scrollY), named, layers, clipped: clip.slice(0, 12) };
};

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1', '--remote-debugging-port=0'] });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2500);
  }
  await page.goto(BASE + '/#' + ROUTE, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2600);

  const shots = arg('shots', '_audit/ui/shots/sticky');
  fs.mkdirSync(path.join(REPO, shots), { recursive: true });

  const clicks = (arg('click', '') || '').split(',').filter(Boolean);
  const scrolls = (arg('scroll', '600') || '').split(',').filter(Boolean).map(Number);
  const seq = [...scrolls.map((y) => ({ step: 'scrollY' + y, nav: null, y })), ...clicks.map((c) => ({ step: 'nav:' + c, nav: c }))];
  for (const s of seq) {
    if (s.nav) {
      const ok = await page.locator(`[data-testid="market-section-${s.nav}"]`).count();
      if (!ok) { console.log('missing nav button ' + s.nav); continue; }
      await page.click(`[data-testid="market-section-${s.nav}"]`);
      await page.waitForTimeout(1400);
    } else {
      await page.evaluate((y) => {
        const sc = document.querySelector('.app-content') || window;
        if (sc === window) window.scrollTo(0, y);
        else sc.scrollTop = y;
      }, s.y);
      await page.waitForTimeout(700);
    }
    const out = await page.evaluate(PROBE);
    console.log(`\n### ${ROUTE} ${s.step}  window.scrollY=${out.winY}  doc=${out.docTop}/${out.docScrollH - out.docClientH}  app-content=${out.scrollTop}/${out.scrollH - out.clientH} (ch ${out.clientH})`);
    for (const n of out.named) console.log(`  named ${n.sel}: ${n.pos} z${n.z} top=${n.top} bottom=${n.bottom} h=${n.h} overflowY=${n.ovY}`);
    for (const l of out.layers) console.log(`  ${l.onTop ? 'VISIBLE ' : 'COVERED '} ${l.sel} ${l.pos} z${l.z} top=${l.top} bottom=${l.bottom} h=${l.h} x=${l.x} w=${l.w}${l.coveredBy ? '  ← by ' + l.coveredBy : ''}  [${l.cls}]`);
    for (const c of out.clipped) console.log(`  CLIP-Y ${c.sel} overflowY=${c.oy} lost=${c.lost}px h=${c.h} last=${c.last}`);
    await page.screenshot({ path: path.join(REPO, shots, ROUTE.replace(/[^a-z0-9]+/gi, '_') + '__' + s.step.replace(/[^a-z0-9]+/gi, '_') + '.png') });
  }
  await browser.close();
  return 0;
})().then((rc) => process.exit(rc)).catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
