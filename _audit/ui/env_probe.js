// _audit/ui/env_probe.js — واقعیتِ نمایشگر و viewport (مرحلۀ ۲ مأموریت UI)
//
// چرا: «رزولوشن فیزیکی مانیتور را با CSS viewport اشتباه نگیر». اینِ اسکریپت
// دو حالت را جدا گزارش می‌کند:
//   --mode=em    → Edge با viewportِ شبیه‌سازی‌شدۀ ۱۳۶۶×۷۶۸ (Playwright emulation)
//   --mode=real  → همانِ Edge به‌صورتِ بیشینۀ واقعی رویِ پنلِ لپ‌تاپ
// و می‌نویسد: screen.avail*، outer/inner، devicePixelRatio، مقیاسِ تخمینی،
// font-size ریشۀ HTML (چون همه‌چیز rem است، همان‌چیز ارتفاعِ هدر را عوض می‌کند)،
// ارتفاعِ واقعیِ نوارهایِ چسبان و عرضِ ستونِ محتوا.
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const arg = (n, d) => { const h = process.argv.find((a) => a.startsWith('--' + n + '=')); return h ? h.split('=').slice(1).join('=') : d; };
const MODE = arg('mode', 'em');
const W = Number(arg('w', 1366)), H = Number(arg('h', 768));
const ROUTE = arg('route', '/market');

const ENV = () => {
  const q = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return { sel, top: Math.round(r.top), h: Math.round(r.height), w: Math.round(r.width),
             fontSize: cs.fontSize, rem: cs.position };
  };
  const html = getComputedStyle(document.documentElement);
  const probe = document.createElement('div');
  probe.style.cssText = 'position:absolute;width:100rem;height:0';
  document.body.appendChild(probe);
  const remPx = Math.round(probe.getBoundingClientRect().width * 100) / 1000;
  probe.remove();
  const dpr = window.devicePixelRatio;
  return {
    url: location.hash || '(none)',
    screen: { width: screen.width, height: screen.height, availW: screen.availWidth, availH: screen.availHeight, colorDepth: screen.colorDepth },
    window: { outerW: window.outerWidth, outerH: window.outerHeight, innerW: window.innerWidth, innerH: window.innerHeight },
    visual: (() => { const v = window.visualViewport; return v ? { w: Math.round(v.width), h: Math.round(v.height), scale: v.scale } : null; })(),
    dpr,
    rootFontSizePx: html.fontSize,
    remUnitPx: remPx,
    bodyFontPx: getComputedStyle(document.body).fontSize,
    zoomEstimated: Math.round((window.visualViewport ? window.visualViewport.width : window.innerWidth) / window.outerWidth * 1000) / 10,
    docScroll: { w: document.scrollingElement.scrollWidth, h: document.scrollingElement.scrollHeight },
    chrome: [q('header.glass-strip'), q('[class*="top-9"]'), q('[data-testid="market-section-nav"]'), q('aside'), q('.app-content'), q('.app-main')].filter(Boolean),
  };
};

(async () => {
  const browser = await chromium.launch({
    executablePath: EXE,
    // «real» باید سربسرِ (headed) باشد: درِ headless مقدارِ screen بهِ ۸۰۰×۶۰۰
    //ِ پیش‌فرض برمی‌گردد وِ `--start-maximized` هیچ پنجرۀِ واقعی را بیشینه نمی‌کند،
    // پس «اندازۀِ واقعیِ مرورگر رویِ همینِ پنل» خوانده نمی‌شود.
    headless: MODE !== 'real',
    args: MODE === 'real'
      ? ['--no-first-run', '--disable-sync', '--start-maximized', '--force-device-scale-factor=1']
      : ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1', '--remote-debugging-port=0'],
  });
  const ctx = MODE === 'real'
    ? await browser.newContext({ viewport: null })
    : await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
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
  // نماد انتخاب‌شده = نوارِ نماد (`sticky top-9 z-30`) هم رندر می‌شود؛ بی‌آن
  // فقط Topbar درِ پشته است و ارتفاعِ پشته اشتباه خوانده می‌شود.
  if (arg('pick', '') === '1') {
    await page.goto(BASE + '/#/market', { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => document.querySelectorAll('[data-testid="tape-row"]').length > 5, null, { timeout: 60000 }).catch(() => {});
    const row = page.locator('[data-testid="tape-row"]').first();
    if (await row.count()) { await row.click(); await page.waitForTimeout(1800); }
  }
  const out = { mode: MODE, picked: arg('pick', '') === '1', ranAt: new Date().toISOString(), routes: [] };
  for (const r of [ROUTE, '/market-status', '/technical/خوز', '/master']) {
    await page.goto(BASE + '/#' + r, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2600);
    out.routes.push({ route: r, env: await page.evaluate(ENV) });
  }
  if (MODE === 'real') {
    await page.screenshot({ path: path.join(REPO, '_audit', 'ui', 'shots', 'real', 'env_real_' + ROUTE.replace(/[^a-z0-9]+/gi, '_') + '.png') });
  }
  console.log(JSON.stringify(out, null, 1));
  fs.writeFileSync(path.join(REPO, '_audit', 'ui', 'ENV_' + MODE + '.json'), JSON.stringify(out, null, 1));
  await browser.close();
  return 0;
})().then((rc) => process.exit(rc)).catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
