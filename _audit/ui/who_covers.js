// _audit/ui/who_covers.js — یکِ جفتِ «کنترل + گیرنده» را کاملِ بازِ کن
//
// چرا: overlap_probe فقطِ نامِ عنصرِ رویی را می‌داد؛ برایِ تصمیمِ اصلاح باید
// زنجیرۀِ والدین، classها و موقعیتِ چسبان (inset)ِ هرِ دو را دید وگرنه اصلاح
// برِ پایهٔ حدس است. usage:
//   MSYS_NO_PATHCONV=1 node _audit/ui/who_covers.js --under=[data-testid="open-chart-settings"] --over=".nn-price-axis-buttons"
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const arg = (n, d) => { const h = process.argv.find((a) => a.startsWith('--' + n + '=')); return h ? h.split('=').slice(1).join('=') : d; };
const ROUTE = arg('route', '/technical/فولاد');
const UNDER = arg('under', '[data-testid="open-chart-settings"]');
const OVER = arg('over', '[data-testid="technical-fts-settings"]');

const INFO = ({ under, over }) => {
  const chain = (el) => {
    const rows = [];
    for (let p = el; p && p !== document.body; p = p.parentElement) {
      const cs = getComputedStyle(p);
      const r = p.getBoundingClientRect();
      rows.push({
        tag: p.tagName.toLowerCase(),
        testid: p.getAttribute('data-testid') || null,
        cls: String(p.className || '').slice(0, 70),
        pos: cs.position, z: cs.zIndex, inset: cs.inset, dir: cs.direction,
        ov: cs.overflowX + '/' + cs.overflowY, pe: cs.pointerEvents,
        box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
        shrink: cs.flexShrink, ws: cs.whiteSpace,
      });
    }
    return rows;
  };
  const q = (s) => document.querySelector(s);
  const u = q(under), o = q(over);
  if (!u || !o) return { missing: { under: !u, over: !o } };
  const ru = u.getBoundingClientRect(), ro = o.getBoundingClientRect();
  const cx = Math.round(ru.x + ru.width / 2), cy = Math.round(ru.y + ru.height / 2);
  const hit = document.elementFromPoint(cx, cy);
  const scrollLike = [...document.querySelectorAll('.nn-top-toolbar')].map((t) => ({
    cls: String(t.className), clientW: t.clientWidth, scrollW: t.scrollWidth,
    canScroll: t.scrollWidth - t.clientWidth,
    kids: [...t.children].map((c) => ({ cls: String(c.className).slice(0, 30), w: Math.round(c.getBoundingClientRect().width), sh: getComputedStyle(c).flexShrink })),
  }));
  return {
    vw: innerWidth, vh: innerHeight,
    under: chain(u), over: chain(o),
    center: { cx, cy }, hit: hit ? (hit.getAttribute('data-testid') || hit.tagName + '.' + String(hit.className).slice(0, 40)) : null,
    gap: { overUnderX: Math.round(ro.x - ru.x), overlapX: Math.round(Math.min(ru.right, ro.right) - Math.max(ru.left, ro.left)), overlapY: Math.round(Math.min(ru.bottom, ro.bottom) - Math.max(ru.top, ro.top)) },
    toolbar: scrollLike,
  };
};

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1', '--remote-debugging-port=0'] });
  const ctx = await browser.newContext({ viewport: { width: Number(arg('w', 1366)), height: Number(arg('h', 768)) }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1000);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2200);
  }
  if (arg('pick', '0') === '1') {
    await page.goto(BASE + '/#/market', { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => document.querySelectorAll('[data-testid="tape-row"]').length > 5, null, { timeout: 60000 }).catch(() => {});
    await page.locator('[data-testid="tape-row"]').first().click().catch(() => {});
    await page.waitForTimeout(1200);
  }
  await page.goto(BASE + '/#' + ROUTE, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="chart-area"]').length > 0, null, { timeout: 45000 }).catch(() => {});
  await page.waitForTimeout(2500);
  const info = await page.evaluate(INFO, { under: UNDER, over: OVER });
  console.log(JSON.stringify(info, null, 1));
  await browser.close();
  return 0;
})().then((rc) => process.exit(rc)).catch((e) => { console.error('ERR', e); process.exit(1); });
