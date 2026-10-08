// _audit/ws7e_hover_reveal.mts — اثباتِ زندۀ رأیِ مالک (۱۴۰۵-۰۷-۱۷):
// «مربعِ کوچک یا ستاره فقط اگر موس رویِ همان ردیف رفت نشان داده بشه.»
//
// چرا سنجش بر پایهٔ «نمایۀ DOM از بیرون» است و نه kلاس: رأیِ مالک یک رفتارِ دیدنی است،
// پس تنها چیزی که حساب می‌شود `getComputedStyle(...).opacity` رویِ خودِ نشانگر است.
// خواندن بر پایهٔ *اندیسِ ردیف* انجام می‌شود نه نامِ نماد: تابلو مرتب می‌شود، و اگر
// بینِ برداشتنِ نام‌ها و hover کردن ردیف جابه‌جا شود، سنجشِ نام‌محور «ردیفِ دیگری
// را hover کردی» را اشتباه گزارش می‌دهد (این دقیقاً در دورِ اولِ همین probe رخ داد).
//
// checks:
//   ۱ idle (موس رویِ هیچ ردیفی)             → همه ۰
//   ۲ hoverِ ردیف                            → جعبه و ستارهٔ همان ردیف ۱
//   ۳ جدا شدنِ موس                           → بازگشت به ۰
//   ۴ hoverِ ردیفِ دیگر                      → آن ردیف ۱، ردیفِ پیشین ۰ (per-row، نه سراسری)
//   ۵ focus-visible                          → ۱ (کیبورد از دست نمی‌رسد)
//   ۶ عضوِ واچ‌لیست                           → ستاره همیشه ۱ (حتی بی‌hover)
//   ۷ hover:none (دستگاهِ لمسی)               → همه ۱ بی‌hover (اندروید hover ندارد)
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:5175/');
const OUT = '_audit/ws7e_hover_reveal.json';
mkdirSync('_audit', { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });

// خواندنِ حالتِ ردیفِ k ام: نشانگرهایِ *خودش*، نمادش، و اینکه موس فیزیکاً رویِ اوست.
const READ_ROW = (k: number) => {
  const rows = document.querySelectorAll('[data-testid="tape-row"]');
  const row = rows[k] as HTMLElement | undefined;
  if (!row) return { missing: true, k };
  const box = row.querySelector('[data-testid^="select-box-"]');
  const star = row.querySelector('[data-testid^="watch-star-"]');
  const op = (el: Element | null) => (el ? Number(getComputedStyle(el).opacity) : null);
  const m = (window as any).__pm as { x: number; y: number } | undefined;
  const r = row.getBoundingClientRect();
  return {
    k,
    symbol: box ? String(box.getAttribute('data-testid')).replace('select-box-', '') : null,
    box: op(box), star: op(star),
    inList: star ? star.getAttribute('data-in-list') : null,
    inList: star ? star.getAttribute('data-in-list') : null,
    rowIsHovered: row.matches(':hover'),
    mouseInsideRow: m ? (m.x >= r.left && m.x <= r.right && m.y >= r.top && m.y <= r.bottom) : null,
    hoverMedia: matchMedia('(hover: none)').matches,
  };
};

async function desktopRun() {
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
  const page = await ctx.newPage();
  const errs: string[] = [];
  const api: string[] = [];
  page.on('pageerror', (e) => errs.push(String(e.message).slice(0, 140)));
  page.on('request', (r) => {
    const u = String(r.url()).replace(/^https?:\/\/[^/]+/, '');
    if (u.startsWith('/api/watchlist')) api.push(`${r.method()} ${u.split('?')[0]}`);
  });
  await page.goto(BASE + '#/market', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="tape-row"]').length >= 6,
    null, { timeout: 90_000 });
  await page.waitForTimeout(800);
  const rows = page.locator('[data-testid="tape-row"]');
  const read = (k: number) => page.evaluate(READ_ROW, k);
  const settle = () => page.waitForTimeout(320);                 // duration-150 + حاشیه
  const park = async () => {                                     // موس جایی بیرونِ جدول
    await page.mouse.move(3, 3);
    await page.evaluate(() => { (window as any).__pm = { x: 3, y: 3 }; });
    await settle();
  };
  // موس را بر اساسِ مستطیلِ *زنده* ردیف می‌بریم آن‌جا (نه locator.boundingBox که
  // خودش ممکن است ردیف را اسکرول کند و مختصاتِ برگشتی بعدِ اسکرول باقی بماند).
  // اگر یک poll ردیف را جابه‌جا کرده بود، دوباره هدف می‌گیریم و شمارشش می‌کنیم؛
  // retry خودِ سنجش را عوض نمی‌کند: شرطِ رأیِ مالک «موس رویِ همان ردیف» است.
  let hoverRetries = 0;
  const aim = async (k: number) => {
    const pt = await page.evaluate((i: number) => {
      const row = document.querySelectorAll('[data-testid="tape-row"]')[i] as HTMLElement;
      const r = row.getBoundingClientRect();
      return { x: Math.round(r.left + r.width * 0.5), y: Math.round(r.top + r.height * 0.5) };
    }, k);
    await page.mouse.move(pt.x, pt.y);
    await page.evaluate((p: any) => { (window as any).__pm = p; }, pt);
    await settle();
    return await read(k);
  };
  const hover = async (k: number) => {
    let got = await aim(k);
    if (!got.rowIsHovered || !got.mouseInsideRow) { hoverRetries++; got = await aim(k); }
    return got;
  };

  const out: any = { rowsPainted: await rows.count() };
  await park();
  out.idle = { r0: await read(0), r2: await read(2), r4: await read(4) };

  out.hoverRow0 = await hover(0);

  await park();
  out.away = await read(0);

  out.hoverRow2 = await hover(2);
  out.row0WhileRow2Hovered = await read(0);
  out.hoverRetries = hoverRetries;

  // focus-visible: Tab حالتِ «کیبورد» را فعال می‌کند، بعد focusِ برنامه‌ای رویِ نشانگر.
  await park();
  await page.evaluate(() => (document.activeElement instanceof HTMLElement) && document.activeElement.blur());
  await page.keyboard.press('Tab');
  const focusRead = await page.evaluate(() => {
    const box = document.querySelector('[data-testid="tape-row"] [data-testid^="select-box-"]');
    if (!(box instanceof HTMLElement)) return null;
    box.focus();
    return { focused: document.activeElement === box, focusVisible: box.matches(':focus-visible') };
  });
  await settle();
  out.focus = { read: focusRead, row0: await read(0) };

  // ستارۀ نمادی که عضو واچ‌لیست است باید همیشه دیده شود (بی‌hover هم).
  // عضویت از همان ابتدا خوانده می‌شود و در پایانِ تست به همان مقدارِ اول
  // برمی‌گردد؛ واچ‌لیستِ واقعیِ کاربر نباید ردّی از این تست ببیند.
  await park();
  const before = await read(0);
  const wasIn = before.inList === '1';
  const wantAfterFirst = wasIn ? '0' : '1';
  await hover(0);
  await page.locator('[data-testid="tape-row"]').nth(0).locator('[data-testid^="watch-star-"]').click();
  await page.waitForFunction((w: string) => {
    const el = document.querySelector('[data-testid="tape-row"] [data-testid^="watch-star-"]');
    return !!el && el.getAttribute('data-in-list') === w;
  }, wantAfterFirst, { timeout: 20_000 });
  await park();
  const flipped = await read(0);
  await hover(0);
  await page.locator('[data-testid="tape-row"]').nth(0).locator('[data-testid^="watch-star-"]').click();
  await page.waitForFunction((w: string) => {
    const el = document.querySelector('[data-testid="tape-row"] [data-testid^="watch-star-"]');
    return !!el && el.getAttribute('data-in-list') === w;
  }, before.inList, { timeout: 20_000 });
  await park();
  const restored = await read(0);
  out.watchlist = { symbol: before.symbol, wasInList: wasIn, before, flipped, restored,
                    apiCalls: api };

  out.pageErrors = errs;
  await ctx.close();
  return out;
}

async function touchRun() {
  const ctx = await browser.newContext({ viewport: { width: 412, height: 892 }, hasTouch: true, isMobile: true });
  await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  // منبعِ معتبرِ «دستگاهِ لمسی»: ویژگی‌هایِ media برایِ hover/pointer را خودِ مرورگر
  // شبیه‌سازی می‌کند، نه فقط یک کلاسِ دلخواه.
  await cdp.send('Emulation.setEmulatedMedia', { features: [{ name: 'hover', value: 'none' },
                                                             { name: 'pointer', value: 'coarse' }] });
  await page.goto(BASE + '#/market', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="tape-row"]').length >= 6,
    null, { timeout: 90_000 });
  await page.waitForTimeout(800);
  const readings = [];
  for (const k of [0, 1, 2]) readings.push(await page.evaluate(READ_ROW, k));
  const out = { hoverNoneMedia: readings[0]?.hoverMedia, readings };
  await ctx.close();
  return out;
}

const res: any = { base: BASE, desktop: await desktopRun(), touch: await touchRun() };
const d = res.desktop;
const checks: [string, boolean | null][] = [
  ['rows painted >= 6', d.rowsPainted >= 6],
  // ستارۀ نمادی که از قبل در واچ‌لیست است «پنهان» نیست و نباید در idle شکست بخورد.
  ['idle: all markers hidden', [d.idle.r0, d.idle.r2, d.idle.r4]
      .every((r) => r.box === 0 && (r.star === 0 || r.inList === '1'))],
  ['hover row0: box revealed', d.hoverRow0.box === 1],
  ['hover row0: star revealed', d.hoverRow0.star === 1],
  ['hover row0: mouse really inside row', d.hoverRow0.mouseInsideRow === true && d.hoverRow0.rowIsHovered === true],
  ['mouse away: back to hidden', d.away.box === 0 && d.away.rowIsHovered === false],
  ['hover row2: its own box revealed', d.hoverRow2.box === 1],
  ['hover row2: row0 stays hidden (per-row)', d.row0WhileRow2Hovered.box === 0],
  ['keyboard focus-visible reveals', !!d.focus.read?.focusVisible && d.focus.row0.box === 1],
  ['in-list star: always visible (no hover needed)',
      d.watchlist.wasInList ? d.watchlist.before.star === 1
                            : (d.watchlist.before.star === 0 && d.watchlist.flipped.star === 1)],
  ['star hidden when out of list and no hover',
      d.watchlist.wasInList ? d.watchlist.flipped.star === 0 : d.watchlist.restored.star === 0],
  ['watchlist membership restored', d.watchlist.restored.inList === d.watchlist.before.inList],
  ['mouse really parked away for those reads',
      d.watchlist.before.mouseInsideRow === false && d.watchlist.flipped.mouseInsideRow === false],
  ['watchlist API hit', d.watchlist.apiCalls.length >= 1],
  ['touch: hover:none media true', res.touch.hoverNoneMedia === true],
  ['touch: markers visible without hover', res.touch.readings.every((r: any) => r.box === 1 && r.star === 1)],
  ['no page errors', d.pageErrors.length === 0],
];
res.verdict = checks.map(([k, v]) => ({ check: k, pass: v === true, value: v }));
writeFileSync(OUT, JSON.stringify(res, null, 2));
for (const [k, v] of checks) console.log(`${v === true ? 'PASS' : v === false ? 'FAIL' : 'N/A '} ${k}`);
console.log('detail ' + JSON.stringify({
  idle: [d.idle.r0.box, d.idle.r2.box, d.idle.r4.box], hover0: d.hoverRow0.box, away: d.away.box,
  hover2: d.hoverRow2.box, row0While2: d.row0WhileRow2Hovered.box,
  focus: [d.focus.read, d.focus.row0.box],
  star: [d.watchlist.wasInList, d.watchlist.before.star, d.watchlist.flipped.star, d.watchlist.restored.star],
  touch: res.touch.readings.map((r: any) => [r.box, r.star]),
}));
await browser.close();
