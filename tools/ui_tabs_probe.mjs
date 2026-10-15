// tools/ui_tabs_probe.mjs -- سنجشِ زندهٔ نوارِ تبِ فضایِ کاری درِ مرورگر
//
// چرا اینِ فایل هست: سبزبودنِ jsdom/Vitest اثباتِ رابطِ واقعی نیست (قیدِ AGENTS.md).
// اینِ سنجش رویِ همانِ فایلِ ساخته‌شدہ (frontend/dist که FastAPI سرو می‌کند) اجرا
// می‌شود، نه dev server، وِ درِ دو حالتِ پیش/پس ازِ بازطراحی باِ یکِ کدِ یکسان عدد
// می‌دهد، پس مقایسه معنا دارد.
//
// سه درسِ عملی ازِ دورِ اولِ همینِ سنجش (که اعدادِ غلط می‌داد):
// ۱) `[role="tab"]` تنها، تب‌هایِ FtsDock وِ زیرتب‌هایِ پرتفوی را هم می‌شمارد ⇒
//    همه‌جا دامنه بهِ `[data-shell="workspace-tabs"]` محدود شده.
// ۲) نشانۀِ دیدنیِ هرِ route باید ثابت باشد؛ اگرِ صفحه بی‌داده آنِ را render
//    نمی‌کند، timeoutِ طولانی، «زمانِ ورود» را دروغ می‌گوید ⇒ timeoutِ کوتاهِ
//    مشخص وِ برچسبِ readyBy=settle برایِ همانِ سطرها.
// ۳) «متنِ بریده» فقطِ متنِ برگِ نهایی باِ overflowِ پنهان وِ بی‌سه‌نقطه است،
//    درِ غیرِ اینِ جدولِ مجاز (min-width) وِ لایۀِ کشوییِ آف‌کانواس شمار می‌شد.
//
// اجرا:  node tools/ui_tabs_probe.mjs --base=http://127.0.0.1:8010 --out=_audit/ui2/tabs.json
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
const OUT = args.out || path.join('_audit', 'ui2', 'tabs.json');
const LABEL = args.label || 'نامشخص';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

const STRIP = '[data-shell="workspace-tabs"]';
const TAB = `${STRIP} [role="tab"]`;

// نشانۀِ آمادگیِ هر route — همۀِ اینها درِ سورسِ همینِ بیس دیده شده‌اند؛ جایی که
// نشانۀِ ثابتی وجود ندارد null است وِ سطر باِ readyBy=settle خوانده می‌شود.
const ROUTES = [
  { path: '/market-status', marker: '[data-testid="market-status-page"]' },
  { path: '/market', marker: null },
  { path: '/technical/فولاد', marker: '[data-testid="chart-area"]' },
  { path: '/fundamental', marker: '[data-testid="fts-screen-scroll"]' },
  { path: '/master', marker: '[data-testid="fts-funnel-workspace"]' },
  { path: '/portfolio', marker: null },
  { path: '/watch', marker: '[data-testid="watch-add-area"]' },
  { path: '/notifications', marker: '[data-testid="notice-filters"]' },
  { path: '/strategy-tree', marker: null },
];

const VIEWPORT = { width: 1366, height: 768 };
const MARKER_TIMEOUT = 8000;

// self-contained: هیچ ارجاعی به ثابت‌هایِ بیرون ندارد، چون درِ مرورگر اجرا می‌شود
const layoutProbe = () => {
  const STRIP = '[data-shell="workspace-tabs"]';
  const TAB = '[data-shell="workspace-tabs"] [role="tab"]';
  const de = document.documentElement;
  const panel = document.getElementById('workspace-panel') || document.body;
  const clipped = [];
  const offscreen = [];
  for (const el of panel.querySelectorAll('*')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (el.getAttribute('aria-hidden') === 'true') continue;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none') continue;
    // `sr-only` باِ عرضِ ۱px وِ `clip:rect(0,0,0,0)` **عمداً** بریده است: همانِ متن
    // برایِ صفحۀ‌خوان. شمردنش درِ «متنِ بریدۀِ ناخواسته» خطایِ سنجش بود (دورِ دومِ
    // اینِ ابزار، نشانۀِ `SPAN.sr-only:ارزش کل بازار بدون داده`).
    const visuallyHidden = el.classList.contains('sr-only') || r.width <= 1
      || /rect\(0,\s*0,\s*0,\s*0\)/.test(`${st.clip} ${st.clipPath}`);
    if (visuallyHidden) continue;
    const isTextLeaf = el.children.length === 0 && (el.textContent || '').trim().length > 0;
    if (isTextLeaf && el.scrollWidth > el.clientWidth + 2 && st.textOverflow !== 'ellipsis' && st.overflowX !== 'visible') {
      clipped.push(`${el.tagName}.${String(el.className).slice(0, 36)}:${(el.textContent || '').trim().slice(0, 26)}`);
    }
    if (r.left > de.clientWidth + 2 && st.position !== 'fixed') {
      offscreen.push(`${el.tagName}.${String(el.className).slice(0, 36)}`);
    }
  }
  const strip = document.querySelector(STRIP);
  return {
    hScrollPx: Math.max(0, de.scrollWidth - de.clientWidth),
    clippedText: clipped.length,
    clippedSample: clipped.slice(0, 5),
    offscreenInPanel: offscreen.length,
    offscreenSample: offscreen.slice(0, 5),
    stripH: strip ? Math.round(strip.getBoundingClientRect().height) : 0,
    stripTabs: document.querySelectorAll(TAB).length,
  };
};

// دروازۀ ورود: رمزِ پیش‌فرض از خودِ سورس خوانده می‌شود؛ هیچ اعتبارنامۀ مالک در
// این فایل، در گزارش یا در git نمی‌نشیند.
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

async function measurePage(browser, route, consoleErrors) {
  // هرِ route درِ contextِ تازه: TanStack Queryِ صفحۀِ پیشین درِ حافظه نیست ⇒ شمارشِ
  // `/api/` همان cold-start است. (دورِ اول، هرِ ۹ مسیر درِ یکِ صفحۀِ گرم خوانده
  // می‌شدند وِ سه مسیر `api=0` دادند — دروغِ روشِ سنجش، نه بی‌درخواستِ صفحه.)
  // نشست درِ localStorage/کوکی نمی‌ماند (authStore: سشن عمداً پاک می‌شود) وِ
  // `goto` باِ فقط‌هش تازهدید نیست، پس ورود باید درِ همینِ contextِ تازه باشد.
  const ctx = await browser.newContext({ viewport: VIEWPORT, locale: 'fa-IR', deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  attach(page);
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
  await loginIfNeeded(page);
  const t0 = Date.now();
  let requests = 0;
  const reqListener = (r) => { if (r.url().includes('/api/')) requests += 1; };
  page.on('request', reqListener);
  const before = consoleErrors.length;
  await page.goto(`${BASE}/#${route.path}`, { waitUntil: 'domcontentloaded' });
  let readyBy = 'settle';
  if (route.marker) {
    try {
      await page.waitForSelector(route.marker, { state: 'visible', timeout: MARKER_TIMEOUT });
      readyBy = 'marker';
    } catch {
      readyBy = 'marker-missing';
    }
  }
  if (readyBy !== 'marker') await page.waitForTimeout(1500);
  await page.waitForTimeout(300);
  const layout = await page.evaluate(layoutProbe);
  page.off('request', reqListener);
  await ctx.close();
  return { path: route.path, readyBy, ms: Date.now() - t0, apiRequests: requests, consoleErrors: consoleErrors.length - before, ...layout };
}

const titlesInStrip = (page) => page.$$eval(TAB, (els) => els.map((e) => (e.textContent || '').replace('×', '').trim()));

async function tabScenario(browser, consoleErrors) {
  const ctx = await browser.newContext({ viewport: VIEWPORT, locale: 'fa-IR', deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  attach(page);
  const out = { steps: [] };
  const stored = () => page.evaluate(() => localStorage.getItem('bors-symbol') ?? '');
  const activeIndex = () => page.$$eval(TAB, (els) => els.findIndex((e) => e.getAttribute('aria-selected') === 'true'));

  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
  await loginIfNeeded(page);

  await page.goto(`${BASE}/#/technical/فولاد`, { waitUntil: 'domcontentloaded' });
  const hasStrip = await page.waitForSelector(TAB, { timeout: 8000 }).then(() => true, () => false);
  if (!hasStrip) {                       // دورِ «پیش»: نوارِ تب وجود ندارد ⇒ سنجشِ تب بی‌معناست
    out.stripPresent = false;
    out.steps = [];
    await ctx.close();
    return out;
  }
  // داندۀِ نکتۀِ پیشین: پیامِ پس ازِ ورود، خودِ برنامه را بهِ /master می‌برد وِ اگر
  // زودتر ازِ آنِ چرخشِ hash اندازه بگیریم، «start» تبِ /master را نشان می‌دهد وِ
  // سناریو ازِ همانِ اولِ نادرست شروع می‌شود. پس تاِ دیدنی‌شدنِ نماد صبر می‌کنیم.
  const waitTitle = async (needle, timeoutMs = 6000) => {
    const t0 = Date.now();
    for (;;) {
      const titles = await titlesInStrip(page);
      if (titles.some((t) => t.includes(needle))) return { ok: true, waitedMs: Date.now() - t0 };
      if (Date.now() - t0 > timeoutMs) return { ok: false, waitedMs: Date.now() - t0 };
      await page.waitForTimeout(200);
    }
  };
  out.waitForFirstTab = await waitTitle('فولاد');
  out.steps.push({
    step: 'start',
    tabs: await titlesInStrip(page),
    stored: await stored(),
    hash: await page.evaluate(() => location.hash),
  });

  await page.click(`${STRIP} [data-testid="ws-tab-new"]`);
  await page.waitForTimeout(400);
  await page.goto(`${BASE}/#/technical/فملی`, { waitUntil: 'domcontentloaded' });
  out.waitForSecondTab = await waitTitle('فملی');
  out.steps.push({
    step: 'second-tab',
    tabs: await titlesInStrip(page),
    stored: await stored(),
    hash: await page.evaluate(() => location.hash),
  });

  await page.$$eval(TAB, (els) => els[0].click());
  await page.waitForTimeout(700);
  const a = await stored();
  out.steps.push({ step: 'back-to-first', stored: a, isolated: a === 'فولاد' });

  await page.$$eval(TAB, (els) => els[1].click());
  await page.waitForTimeout(700);
  const b = await stored();
  out.steps.push({ step: 'forward-to-second', stored: b, isolated: b === 'فملی' });

  await page.focus(`${TAB}[aria-selected="true"]`);
  await page.keyboard.press('ArrowLeft');
  await page.waitForTimeout(500);
  out.steps.push({ step: 'arrow-left-in-rtl', activeIndex: await activeIndex(), expect: 0 });

  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  out.steps.push({ step: 'after-reload', tabs: (await titlesInStrip(page)).length });

  for (let i = 0; i < 5; i += 1) {
    await page.click(`${STRIP} [data-testid="ws-tab-new"]`);
    await page.waitForTimeout(150);
  }
  const crowded = await page.evaluate(layoutProbe);
  out.steps.push({ step: 'crowded', ...crowded });

  // نگهبانِ عدم‌تداخل: تب‌هایِ دیگرِ برنامه (FtsDock وِ…) باید دست‌نخورده بمانند
  await page.goto(`${BASE}/#/technical/فولاد`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  out.dockTabsAlive = await page.evaluate(() => {
    const all = document.querySelectorAll('[role="tab"]').length;
    const inStrip = document.querySelectorAll('[data-shell="workspace-tabs"] [role="tab"]').length;
    return all - inStrip;
  });

  await ctx.close();
  return out;
}

const browser = await chromium.launch({ executablePath: EXE, headless: true, args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1'] });
const consoleErrors = [];
const attach = (pg) => {
  pg.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 200)); });
  pg.on('pageerror', (e) => consoleErrors.push('pageerror: ' + String(e).slice(0, 200)));
};

// یکِ نشستِ ورود، سپس stateِ همانِ نشست (localStorage، بی‌رمزِ تازه) درِ هرِ context
// تزریق می‌شود: اعتبارنامۀِ مالک هیچ‌جا نوشته نمی‌شود وِ سنجش بی‌LoginScreen می‌ماند.
const seed = await browser.newContext({ viewport: VIEWPORT, locale: 'fa-IR', deviceScaleFactor: 1 });
const seedPage = await seed.newPage();
attach(seedPage);
await seedPage.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
await loginIfNeeded(seedPage);
const bundle = await seedPage.evaluate(() =>
  [...document.querySelectorAll('script[src]')].map((s) => s.getAttribute('src'))
    .filter((s) => s.includes('/assets/')).join(' '));
await seed.close();

const pages = [];
for (const r of ROUTES) pages.push(await measurePage(browser, r, consoleErrors));
const tabs = await tabScenario(browser, consoleErrors);

const result = {
  base: BASE, buildLabel: LABEL, bundle, viewport: VIEWPORT, browser: EXE,
  generatedAt: new Date().toISOString(),
  method: {
    readyBy: 'marker = نشانۀِ دیدنیِ خودِ صفحه؛ settle = بازمانیِ ثابت؛ marker-missing = نشانۀِ ثابتِ آنِ route درِ اینِ حالتِ داده render نشد',
    tabs: `همۀ شمارش‌هایِ تب درِ ${TAB} (بی‌تب‌هایِ FtsDock/پرتفوی)`,
    coldStart: 'هرِ route درِ contextِ تازه باِ نشستِ ورودِ جدا ⇒ TanStack Query سرد است وِ شمارشِ `/api/` ازِ همانِ route',
    clippedText: 'متنِ بریدۀِ ناخواسته؛ `sr-only` وِ `clip:rect(0,0,0,0)` (پنهانِ عمدی برایِ صفحۀ‌خوان) شمرده نمی‌شود',
  },
  pages,
  tabScenario: tabs,
  consoleErrorCount: consoleErrors.length,
  consoleErrors: consoleErrors.slice(0, 10),
};
fs.mkdirSync(path.dirname(path.join(REPO, OUT)), { recursive: true });
fs.writeFileSync(path.join(REPO, OUT), JSON.stringify(result, null, 2), 'utf8');

console.log(`routes=${pages.length} consoleErrors=${consoleErrors.length}`);
for (const p of pages) {
  console.log(`  ${p.path.padEnd(20)} ${p.readyBy.padEnd(14)} ${String(p.ms).padStart(6)}ms api=${String(p.apiRequests).padStart(3)} hScroll=${p.hScrollPx} clip=${p.clippedText} off=${p.offscreenInPanel} tabs=${p.stripTabs} strip=${p.stripH}px`);
}
for (const s of tabs.steps) console.log(`  tab ${JSON.stringify(s).slice(0, 200)}`);
console.log('  dockTabsAlive=', tabs.dockTabsAlive);
console.log('written →', OUT);
await browser.close();
