// _audit/m1_mobile_routes.mts — آمارِ زندهٔ مسیرهایِ اندروید در هر دو جهت
//
// برایِ هر مسیر، در پرتريت (۳۹۰×۸۴۴) و لندسکپ (۸۴۴×۳۹۰):
//   • سربرگ/عنوانِ دیده‌شده، وجودِ ناوبریِ لمسی،
//   • سرریزِ افقی (scrollWidth > innerWidth) — قاتلِ جدول‌ها در گوشی،
//   • ارتفاعِ واقعاً دیدنیِ جدول و این‌که ردیفِ لمسی هست یا نه،
//   • خطای کنسول/صفحه.
// و یک چرخشِ وسطِ کار: همان صفحۀ باز از پرتريت به لندسکپ می‌رود؛ اگر حالتِ
// کاربر (نمادِ انتخابی/صفحهٔ سایدبار) بپرد، اینجا دیده می‌شود.
// اجرا: JEV_CHROME=... MSYS_NO_PATHCONV=1 node --experimental-strip-types _audit/m1_mobile_routes.mts
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const BASE = 'http://127.0.0.1:8021/';
mkdirSync('_audit/mobile', { recursive: true });

const ROUTES = ['/', '/market', '/fundamental', '/technical', '/master',
                '/strategy-tree', '/portfolio', '/engine-lab', '/no-such-page'];
const P = { width: 390, height: 844 };
const L = { width: 844, height: 390 };

const MEASURE = () => {
  const de = document.documentElement;
  const nav = document.querySelector('[data-shell="sidebar"], [data-testid="mobile-nav"], nav[aria-label]');
  const tables = Array.from(document.querySelectorAll('[data-testid="tape-scroll"], [data-testid="fts-screen-scroll"], [data-testid^="funnel-scroll-"]'));
  const touchTargets = Array.from(document.querySelectorAll('button, a')).filter((n) => {
    const r = n.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.height < 32;
  }).length;
  return {
    url: location.hash || '#/',
    h: (document.querySelector('h1,h2')?.textContent || '').trim().slice(0, 40),
    overflow_x: de.scrollWidth - de.clientWidth,
    overflow_y: de.scrollHeight - de.clientHeight,
    client_w: de.clientWidth,
    nav_present: !!nav,
    nav_visible: !!nav && (nav.getBoundingClientRect().width > 0),
    table_boxes: tables.map((t) => ({
      id: t.getAttribute('data-testid'),
      w: Math.round(t.getBoundingClientRect().width),
      h: Math.round(t.getBoundingClientRect().height),
      inner_w: Math.round((t.querySelector('table,[class*="min-w-"]') as HTMLElement)?.getBoundingClientRect().width ?? 0),
    })),
    small_touch_targets: touchTargets,
    interactive: document.querySelectorAll('button,a,[role="button"]').length,
  };
};

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const rows: any[] = [];
for (const [name, vp] of [['portrait', P], ['landscape', L]] as [string, any][]) {
  const ctx = await browser.newContext({ viewport: vp, deviceScaleFactor: 2, isMobile: name === 'portrait', hasTouch: true });
  await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
  for (const r of ROUTES) {
    const page = await ctx.newPage();
    const errs: string[] = [];
    page.on('pageerror', (e) => errs.push(String(e.message).slice(0, 120)));
    page.on('console', (m) => { if (m.type() === 'error') errs.push('c:' + m.text().slice(0, 100)); });
    await page.goto(BASE + '#' + r, { waitUntil: 'domcontentloaded', timeout: 45_000 });
    await page.waitForTimeout(4500);
    const m = await page.evaluate(MEASURE);
    rows.push({ orient: name, route: r, ...m, errors: errs.slice(0, 4) });
    await page.screenshot({ path: `_audit/mobile/${name}_${r.replace(/[\/.]/g, '_') || 'root'}.png` });
    await page.close();
  }
  await ctx.close();
}

// چرخشِ وسطِ کار رویِ دو صفحۀ پرمصرف: تابلو و غربالگری
const rot: any[] = [];
for (const r of ['/master', '/fundamental']) {
  const ctx = await browser.newContext({ viewport: P, isMobile: true, hasTouch: true });
  await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
  const page = await ctx.newPage();
  await page.goto(BASE + '#' + r, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);
  const before = await page.evaluate(MEASURE);
  await page.setViewportSize(L);
  await page.waitForTimeout(2500);
  const after = await page.evaluate(MEASURE);
  rot.push({ route: r, before, after,
             heading_kept: before.h === after.h, url_kept: before.url === after.url });
  await page.screenshot({ path: `_audit/mobile/rotated_${r.slice(1)}.png` });
  await ctx.close();
}
await browser.close();
writeFileSync('_audit/mobile/m1_routes.json', JSON.stringify({ rows, rot }, null, 2));
const bad = rows.filter((x) => x.overflow_x > 2 || x.errors.length || !x.nav_present);
console.log('routes measured:', rows.length, '| problem rows:', bad.length);
for (const b of bad) console.log('  !', b.orient, b.route, 'overflowX=' + b.overflow_x,
  'nav=' + b.nav_present, 'err=' + b.errors.length, b.errors[0] ?? '');
console.log('rotation:', JSON.stringify(rot.map((x) => ({ r: x.route, ox_b: x.before.overflow_x, ox_a: x.after.overflow_x, kept: x.heading_kept && x.url_kept }))));
