// _audit/ws7g_row_geometry.mts — هندسۀ ردیف‌هایِ اولِ تابلو: چرا ردیفِ ۰ زیرِ موس نمی‌نشیند؟
// برایِ k=0..4: مستطیلِ ردیف، اینکه داخلِ viewport است، چه چیزی رویِ مرکزِ آن است،
// و اینکه آیا خودِ ردیف رویِ همان نقطه hover می‌شود (elementFromPoint).
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const BASE = process.argv.includes('--url') ? process.argv[process.argv.indexOf('--url') + 1]
                                            : 'http://127.0.0.1:5175/';
const browser = await chromium.launch({ headless: true,
  executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
await page.goto(BASE + '#/market', { waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => document.querySelectorAll('[data-testid="tape-row"]').length >= 6,
  null, { timeout: 90_000 });
await page.waitForTimeout(900);
const geo = await page.evaluate(() => {
  const rows = [...document.querySelectorAll('[data-testid="tape-row"]')].slice(0, 6);
  return rows.map((row, k) => {
    const r = row.getBoundingClientRect();
    const cx = Math.round(r.left + r.width / 2), cy = Math.round(r.top + r.height / 2);
    const hit = document.elementFromPoint(cx, cy);
    const box = row.querySelector('[data-testid^="select-box-"]');
    const bs = box ? box.getBoundingClientRect() : null;
    return {
      k,
      sym: box ? String(box.getAttribute('data-testid')).replace('select-box-', '') : null,
      rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)],
      center: [cx, cy],
      inViewport: r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth,
      hitAtCenter: hit ? hit.tagName + '.' + String(hit.className || '').split(' ')[0].slice(0, 34) : null,
      hitIsInRow: !!(hit && row.contains(hit)),
      boxRect: bs ? [Math.round(bs.left), Math.round(bs.top), Math.round(bs.width), Math.round(bs.height)] : null,
      rowOpacitySelf: Number(getComputedStyle(row).opacity),
      rowDisplay: getComputedStyle(row).display,
      position: getComputedStyle(row).position,
      transform: getComputedStyle(row).transform.slice(0, 40),
    };
  });
});
console.log(JSON.stringify(geo, null, 1));
// حالا خودِ موس را می‌بریم رویِ مرکزِ ردیفِ ۰ و بعد از settle می‌خوانیم.
const r0 = geo[0];
await page.mouse.move(r0.center[0], r0.center[1]);
await page.waitForTimeout(400);
const after = await page.evaluate((c: any) => {
  const row = document.querySelectorAll('[data-testid="tape-row"]')[0];
  const box = row.querySelector('[data-testid^="select-box-"]');
  const hit = document.elementFromPoint(c[0], c[1]);
  return { rowHovered: row.matches(':hover'), boxOpacity: Number(getComputedStyle(box).opacity),
           hitTag: hit ? hit.tagName + '.' + String(hit.className || '').split(' ')[0].slice(0, 40) : null,
           hitIsSameRow: !!(hit && row.contains(hit)) };
}, r0.center);
console.log('hoverRow0Center => ' + JSON.stringify(after));
await browser.close();
