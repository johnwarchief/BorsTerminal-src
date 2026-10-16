// tools/ui_page_inventory.mjs -- برداشتِ صفحهِ‌به‌صفحهِ مسیرهایِ واقعی درِ مرورگر
//
// چرا اینِ فایل هست: ماتریسِ بازطراحی نباید برِ پایِ «حسِّ من» نوشته شود. اینِ
// سنجش برایِ هرِ route همان چیزی را ثبت می‌کند که صفحۀِ بازطراحی باِ آن سنجیده
// می‌شود: سلسلۀِ مراتبِ دیداری (تیترها وِ جایِ آن‌ها)، جایِ کنشِ اصلی، چگالیِ داده
// درِ یکِ screenful، متنِ ریز، بریدگی، ظرفِ اسکرولِ واقعی وِ اسکرین‌شاتِ خودِ صفحه.
//
// اینِ سنجش رویِ `frontend/dist` سرو‌شده باِ FastAPI اجرا می‌شود (نه dev server)
// وِ هرِ route درِ contextِ تازه خوانده می‌شود تاِ داده‌هایِ صفحه سرد باشند.
//
// اجرا:  node tools/ui_page_inventory.mjs --base=http://127.0.0.1:8010 \
//          --viewport=1366x768 --out=_audit/ui2/pages-1366.json --full=true
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.join(HERE, '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));

const args = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const m = /^--([^=]+)=(.*)$/.exec(a);
    return m ? [m[1], m[2]] : [a.replace(/^--/, ''), true];
  })
);
const BASE = args.base || 'http://127.0.0.1:8010';
const OUT = args.out || path.join('_audit', 'ui2', 'pages.json');
const LABEL = args.label || 'نامشخص';
const FULL = args.full !== 'false';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

const VP = /^([0-9]+)x([0-9]+)$/.exec(args.viewport || '1366x768');
const VIEWPORT = { width: Number(VP[1]), height: Number(VP[2]) };
const SETTLE = Number(args.settle || 3200);

// مسیرهایِ واقعیِ ثبت‌شده درِ `frontend/src/routes.tsx`. نمادِ «فولاد» آنهایی است
// که صفحۀِ بدونِ نماد بی‌داده render می‌شود وِ چیزی برایِ دیدنِ چگالیِ داده نمی‌ماند.
const ROUTES = (args.routes || '')
  .split(',')
  .filter(Boolean)
  .map((s) => {
    const [name, p] = s.split('|');
    return { name, path: p };
  });
if (!ROUTES.length) {
  for (const [name, p] of [
    ['market', '/market'],
    ['market-status', '/market-status'],
    ['fundamental', '/fundamental/فولاد'],
    ['technical', '/technical/فولاد'],
    ['strategy-tree', '/strategy-tree/فولاد'],
    ['master', '/master'],
    ['portfolio', '/portfolio/فولاد'],
    ['watch', '/watch'],
    ['notifications', '/notifications'],
  ]) ROUTES.push({ name, path: p });
}

const attach = (pg, errs) => {
  pg.on('console', (m) => {
    if (m.type() === 'error') errs.push(m.text().slice(0, 200));
  });
  pg.on('pageerror', (e) => errs.push(`pageerror: ${String(e).slice(0, 160)}`));
};

async function loginIfNeeded(page) {
  if (!(await page.evaluate(() => !!document.querySelector('input[type="password"]')))) return;
  const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
  const du = (src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
  const dp = (src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
  if (!du || !dp) throw new Error('DEFAULT_USER/DEFAULT_PASS در authStore پیدا نشد');
  await page.locator('input[type="text"]').first().fill(du);
  await page.locator('input[type="password"]').first().fill(dp);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(2200);
}

// برداشتِ درونِ صفحۀ. همه‌چیز ازِ دیدِ کاربرِ نشسته پایِ نمایشگرِ ۱۳۶۶ ثبت می‌شود:
// چه something درِ screenfulِ اول دیده می‌شود، نه صرفِ «درِ DOM هست».
const inventory = () => {
  const de = document.documentElement;
  const VPH = window.innerHeight;
  const VPW = window.innerWidth;
  const px = (v) => Math.round(v);
  const txt = (el) => (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60);
  const visible = (r) => r.width > 1 && r.height > 1;

  const inFlow = (el) => {
    let n = el;
    while (n && n !== document.body) {
      const cs = getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden') return false;
      if (cs.position === 'fixed') return true;
      n = n.parentElement;
    }
    return true;
  };

  // ۱) سلسلۀِ مراتبِ دیداری: هرِ تیتر باِ سطح، فاصلۀِ بالا وِ اندازهِٔ فونتِ واقعی
  const heads = [];
  for (const el of document.querySelectorAll('h1,h2,h3,h4,h5,[role="heading"]')) {
    if (!inFlow(el)) continue;
    const r = el.getBoundingClientRect();
    if (!visible(r)) continue;
    const level = Number(el.getAttribute('aria-level') || el.tagName.replace(/^H/i, '') || 0);
    heads.push({
      level, text: txt(el), top: px(r.top), fontPx: Number(parseFloat(getComputedStyle(el).fontSize).toFixed(1)),
      inFirstScreen: r.top < VPH,
    });
  }
  heads.sort((a, b) => a.top - b.top || a.level - b.level);

  // ۲) کنش‌ها: دکمه/لینک/کمبو باِ موقعیتِ افقیِ راست‌به‌چپِ همانِ screenfulِ اول
  const actions = [];
  for (const el of document.querySelectorAll('button,a[href],[role="combobox"],[role="tab"],select,input[type="search"]')) {
    if (!inFlow(el)) continue;
    const r = el.getBoundingClientRect();
    if (!visible(r)) continue;
    const label = (el.getAttribute('aria-label') || txt(el) || el.getAttribute('placeholder') || '').trim();
    actions.push({
      tag: el.tagName.toLowerCase(), role: el.getAttribute('role') || null, label: label.slice(0, 40),
      top: px(r.top), left: px(r.left), w: px(r.width), h: px(r.height),
      inFirstScreen: r.top >= 0 && r.bottom <= VPH, disabled: el.disabled === true,
      testid: el.getAttribute('data-testid'),
    });
  }
  const firstScreenActions = actions.filter((a) => a.inFirstScreen && a.label);

  // ۳) چگالیِ داده: ردیف‌هایِ جدولِ دیدنی وِ «سلولِ عددی» درِ هرِ screenful
  const tables = [];
  for (const t of document.querySelectorAll('table')) {
    const r = t.getBoundingClientRect();
    if (!visible(r)) continue;
    const headRow = t.querySelector('thead tr, tr');
    const headers = headRow ? Array.from(headRow.querySelectorAll('th,td')).map(txt).filter(Boolean) : [];
    tables.push({
      rows: t.querySelectorAll('tbody tr').length, cols: headers.length, headers: headers.slice(0, 14),
      top: px(r.top), height: px(r.height), stickyHead: !!t.querySelector('thead th[style*="sticky"],thead th.sticky,thead.sticky'),
      scrollParentOverflow: (() => {
        let n = t.parentElement;
        while (n && n !== document.body) {
          const cs = getComputedStyle(n);
          if (/(auto|scroll)/.test(cs.overflowY) && n.scrollHeight > n.clientHeight + 8) break;
          n = n.parentElement;
        }
        return n ? (n.getAttribute('data-testid') || n.className.toString().slice(0, 40)) : null;
      })(),
    });
  }
  const NUM = /^[+−-]?[۰-۹0-9][۰-۹0-9.,%]*(\s*(هزار|میلیون|میلیارد|س\.)?)?$/;
  const numberCells = Array.from(document.querySelectorAll('td,th,span,div')).filter((el) => {
    if (el.children.length) return false;
    if (!inFlow(el)) return false;
    const r = el.getBoundingClientRect();
    if (!visible(r) || r.top < 0 || r.top > VPH) return false;
    return NUM.test((el.textContent || '').trim());
  }).length;

  // ۴) متنِ ریز: هرِ متنِ دیدنیِ زیرِ ۱۰٫۵ پیکسل (آستانۀِ خواناییِ همینِ نمایشگر)
  const tiny = [];
  let tinyCount = 0;
  for (const el of document.querySelectorAll('*')) {
    if (el.children.length) continue;
    const s = (el.textContent || '').trim();
    if (s.length < 2) continue;
    if (!inFlow(el)) continue;
    const r = el.getBoundingClientRect();
    if (!visible(r) || r.top > VPH) continue;
    const f = parseFloat(getComputedStyle(el).fontSize);
    if (f < 10.5) {
      tinyCount += 1;
      if (tiny.length < 6) tiny.push({ text: txt(el), fontPx: Number(f.toFixed(1)), top: px(r.top) });
    }
  }

  // ۵) بریدگیِ متنِ ناخواسته (همانِ تعریفِ دورهایِ پیش: تنها برگِ نهایی باِ overflowِ پنهان)
  const clipped = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE' || el.tagName === 'NOSCRIPT') continue;
    if (el.children.length) continue;
    if (el.closest('.sr-only')) continue;
    const cs = getComputedStyle(el);
    if (cs.clipPath === 'rect(0px, 0px, 0px, 0px)' || cs.clip === 'rect(0px, 0px, 0px, 0px)') continue;
    if (!/hidden|clip/.test(cs.overflowX + ' ' + cs.overflowY)) continue;
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) continue;
    if (el.scrollWidth <= r.width + 1) continue;
    const s = (el.textContent || '').trim();
    if (!s || s.endsWith('…') || s.endsWith('...')) continue;
    clipped.push({ text: s.slice(0, 40), scrollWidth: px(el.scrollWidth), clientWidth: px(r.width) });
    if (clipped.length > 8) break;
  }

  // ۶) ظرفِ اسکرولِ واقعی: کدامِ element خودش اسکرول می‌شود (نه فقطِ بدۀِ سند)
  const scrollers = [];
  for (const el of document.querySelectorAll('*')) {
    const cs = getComputedStyle(el);
    if (!/(auto|scroll)/.test(cs.overflowY)) continue;
    if (el.scrollHeight <= el.clientHeight + 12) continue;
    const r = el.getBoundingClientRect();
    if (!visible(r)) continue;
    scrollers.push({
      sel: el.getAttribute('data-testid') || el.getAttribute('data-shell') || el.tagName.toLowerCase() + '.' + el.className.toString().split(' ')[0],
      scrollH: px(el.scrollHeight), clientH: px(el.clientHeight), top: px(r.top),
    });
  }

  // ۷) حالت‌هایِ خالی وِ بی‌داده: چه چیزی به‌جایِ داده render شده
  const empties = Array.from(document.querySelectorAll('[class*="border-dashed"],[data-testid*="empty"],[data-testid*="no-data"]'))
    .filter(inFlow)
    .map((el) => txt(el).slice(0, 70))
    .filter(Boolean);

  // ۸) پنجزِ جزئیاتِ باز وِ نشانیِ نماد
  const inspector = document.querySelector('[data-shell="inspector"]');

  return {
    route: location.hash, urlSymbol: (() => {
      const m = /#\/[^/]+\/([^?]+)/.exec(location.hash);
      return m ? decodeURIComponent(m[1]) : null;
    })(),
    docScrollH: px(de.scrollHeight), viewportH: VPH, hScrollPx: px(de.scrollWidth - de.clientWidth),
    contentWidthRatio: Number((de.scrollWidth / VPW).toFixed(3)),
    headings: heads.slice(0, 24), headingCount: heads.length,
    actionCount: actions.length, firstScreenActionCount: firstScreenActions.length,
    firstScreenActions: firstScreenActions.slice(0, 12),
    primaryActionTop: firstScreenActions.length ? firstScreenActions[0].top : null,
    tables, numberCellsInFirstScreen: numberCells, tinyTextCount: tinyCount, tinySamples: tiny,
    clippedCount: clipped.length, clippedSamples: clipped, scrollers, empties,
    inspectorOpen: !!inspector, inspectorTestId: inspector ? inspector.getAttribute('data-testid') : null,
    testids: Array.from(document.querySelectorAll('[data-testid]')).length,
  };
};

const browser = await chromium.launch({ executablePath: EXE, args: ['--force-device-scale-factor=1'] });
const consoleErrors = [];
const seed = await browser.newContext({ viewport: VIEWPORT, locale: 'fa-IR', deviceScaleFactor: 1 });
const seedPage = await seed.newPage();
attach(seedPage, consoleErrors);
await seedPage.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
await loginIfNeeded(seedPage);
const bundle = (await seedPage.evaluate(() =>
  Array.from(document.querySelectorAll('script[src]')).map((s) => s.getAttribute('src'))
    .filter((s) => s.includes('/assets/')).join(' ')));
await seed.close();

const shotDir = path.join(REPO, '_audit', 'ui2', 'shots');
fs.mkdirSync(shotDir, { recursive: true });

const pages = [];
for (const r of ROUTES) {
  const ctx = await browser.newContext({ viewport: VIEWPORT, locale: 'fa-IR', deviceScaleFactor: 1 });
  const pg = await ctx.newPage();
  attach(pg, consoleErrors);
  const apiCalls = [];
  pg.on('response', (res) => {
    const u = new URL(res.url());
    if (u.pathname.startsWith('/api/')) apiCalls.push(`${res.status()} ${u.pathname}`);
  });
  await pg.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
  await loginIfNeeded(pg);
  await pg.goto(`${BASE}/#${r.path}`, { waitUntil: 'domcontentloaded' });
  await pg.waitForTimeout(SETTLE);
  const inv = await pg.evaluate(inventory);
  pages.push({ name: r.name, path: r.path, apiCount: apiCalls.length, api: apiCalls.slice(0, 12), ...inv });
  const w = VIEWPORT.width; const h = VIEWPORT.height;
  await pg.screenshot({ path: path.join(shotDir, `${r.name}-${w}x${h}.png`) });
  if (FULL) await pg.screenshot({ path: path.join(shotDir, `${r.name}-full-${w}x${h}.png`), fullPage: true });
  console.log(`  ${r.name.padEnd(16)} heads=${String(inv.headingCount).padStart(3)} act=${String(inv.firstScreenActionCount).padStart(3)}`
    + ` rows=${inv.tables.reduce((a, t) => a + t.rows, 0)} num=${String(inv.numberCellsInFirstScreen).padStart(4)}`
    + ` tiny=${String(inv.tinyTextCount).padStart(3)} clip=${inv.clippedCount} hScroll=${inv.hScrollPx}`
    + ` doc=${inv.docScrollH}/${h} api=${apiCalls.length}`);
  await ctx.close();
}
await browser.close();

const result = {
  base: BASE, buildLabel: LABEL, bundle, viewport: VIEWPORT, browser: EXE,
  generatedAt: new Date().toISOString(), consoleErrors,
  method: {
    density: 'numberCellsInFirstScreen = سلول‌هایِ عددیِ دیدنی درِ ۰ تاِ innerHeight (برازِ «چگالیِ داده درِ یکِ screenful»)',
    hierarchy: 'headings = تیترها باِ level/top/fontPx، مرتب ازِ بالا بهِ پایینِ همانِ صفحه',
    primaryAction: 'primaryActionTop = اولینِ کنشِ دیدنیِ برچسب‌دار درِ screenfulِ اول (RTL: left ازِ راستِ صفحه اندازهِٔ پیکسلی)',
    scrollers: 'scrollers = ظرف‌هایی که خودشون اسکرول می‌شن (scrollH > clientH + 12)، نه بدۀِ سند',
    tiny: 'tinyTextCount = متنِ دیدنیِ زیرِ ۱۰٫۵ پیکسل درِ screenfulِ اول',
  },
  pages,
};
fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(result, null, 1));
console.log(`\nصفحات=${pages.length} خطایِ کنسول=${consoleErrors.length} → ${OUT}`);
