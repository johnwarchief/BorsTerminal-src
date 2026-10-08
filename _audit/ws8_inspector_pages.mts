// _audit/ws8_inspector_pages.mts — اثباتِ زندهٔ «در یک نگاه»ِ دوصفحه‌ای (§۱۵.۲۰)
//
// چه چیزی باید ثابت شود (همه از بیرونِ DOM، نه از کلاس‌ها):
//   ۱ ترتیبِ سطرها درِ صفحۀ اول همان رأیِ مالک است (قیمت ← حجم/ارزش ← ارزشِ بازار ←
//     قدرت خرید/فروش ← وضعیت تابلو ← تکنیکال ← بنیادی ← غربالگری ← رویدادها ← جمع‌بندی).
//   ۲ جابه‌جاییِ صفحّه بی‌درخواستِ شبکه است (نه refetch، نه پرسشِ تازه).
//   ۳ پنج مظنه تا صفحۀ دوم باز نشود اصلاً درِ DOM نیست، و تا بازشده پرسیده نمی‌شود
//     (انبارِ عمق بی‌مصرف درخواست نمی‌زند).
//   ۴ بعد از بازگشت به صفحۀ اول و آمدنِ دوباره، حالتِ بازشو حفظ است و درخواستِ
//     دومی به /api/order-book نمی‌رود.
//   ۵ ارتفاعِ هر صفحۀ محلی (مالک: کوتاه‌ترش بکن — عددِ پیکسل لازم است).
// اسکرین‌شاتِ هر دو صفحّه برایِ رأیِ خودِ مالک درِ `_audit/ws8_*.png` می‌ماند؛
// گاردِ sبزِ jsdom به‌تنهایی «انجام شد» نیست.
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
const OUT = '_audit/ws8_inspector_pages.json';
mkdirSync('_audit', { recursive: true });

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const errs: string[] = [];
const reqs: string[] = [];
const bad: string[] = [];
page.on('pageerror', (e) => errs.push(String(e.message).slice(0, 160)));
page.on('console', (m) => {
  if (m.type() === 'error') {
    const loc = String(m.location?.().url ?? '');
    // ۴۰۴ِ فایل‌یکِ dev-server سرِ صد بار هم که باشد ربطی به کارِ ما نیست؛ ولی
    // بی‌URLِ کامل این فیلتر کور است، پس URL را می‌نویسم و بعد فیلتر می‌کنم.
    if (/favicon\.ico/.test(loc)) return;
    errs.push('console: ' + m.text().slice(0, 120) + ' @ ' + loc.slice(0, 80));
  }
});
page.on('response', (r) => {
  const u = String(r.url()).replace(/^https?:\/\/[^/]+/, '');
  if (r.status() >= 400) bad.push(`${r.status()} ${u}`);
});
// شمارشِ «درخواستِ اضافه» باید pollingِ همیشگیِ تابلو را کنار بگذارد، وگرنه هر
// صبرِ ۵۰۰ms دو سه درخواستِ طبیعیِ خودِ برنامه را «اضافه» گزارش می‌کند.
const POLL = /^\/api\/(market|live-stats|sync-state|funnel($|\/)|watchlist($|\?))/;
const T0 = Date.now();
const timeline: { ms: number; url: string }[] = [];
page.on('request', (r) => {
  const u = String(r.url()).replace(/^https?:\/\/[^/]+/, '');
  if (!u.startsWith('/api/')) return;
  const clean = u.split('?')[0];
  reqs.push(clean);
  timeline.push({ ms: Date.now() - T0, url: clean });
});
const obReqs = () => reqs.filter((u) => u.startsWith('/api/order-book/')).length;
const nonPoll = () => reqs.filter((u) => !POLL.test(u));
const since = (n: number) => reqs.length - n;
const sinceNonPoll = (n: number) => nonPoll().length - n;

await page.goto(BASE + '#/market', { waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => document.querySelectorAll('[data-testid="tape-row"]').length >= 5,
  null, { timeout: 90_000 });

// نماد را با کلیکِ واقعیِ خودِ کاربر انتخاب می‌کنیم (نه ستورِ داخلی): رأیِ مالک
// «کلیک رویِ نماد = ارزیابیِ هدفمند» است و سایدبار هم از همان باز می‌شود.
await page.locator('[data-testid="tape-row"]').nth(1).click();
await page.waitForSelector('[data-testid="inspector-tabs"]', { timeout: 30_000 });
await page.waitForTimeout(1200);

const symbol = await page.evaluate(() => {
  const el = document.querySelector('[data-shell="inspector"]');
  return String(el?.getAttribute('aria-label') ?? '');
});

// ترتیبِ دیدنیِ صفحۀ اول: زمینۀ‌نشان‌ها به همان ترتیبی که درِ DOM می‌آیند.
const order = await page.evaluate(() => {
  const want = ['inspector-volume', 'inspector-market-cap', 'inspector-power',
                'inspector-regulatory', 'تکنیکال FTS', 'نمره بنیادی',
                'inspector-stage', 'inspector-events', 'inspector-veto-why'];
  const g = document.querySelector('[data-testid="inspector-page-glance"]');
  if (!g) return { seen: [], found: false };
  const seen: string[] = [];
  g.querySelectorAll('*').forEach((el) => {
    const tid = el.getAttribute('data-testid');
    const t = (el.textContent ?? '').trim();
    const hit = tid && want.includes(tid) ? tid : (want.includes(t) ? t : null);
    if (hit && !seen.includes(hit)) seen.push(hit);
  });
  const h = Math.round(g.getBoundingClientRect().height);
  const scrollH = g.scrollHeight;
  return { seen, found: true, heightPx: h, scrollHeightPx: scrollH };
});

// چیزهایی که باید درِ صفحۀ اول نباشند (رفتگیِ محلی، نه حذف).
const absentOnGlance = await page.evaluate(() => ({
  quotes: !!document.querySelector('[data-testid="inspector-quotes"]'),
  techLink: [...document.querySelectorAll('a')].some((a) => /چارت تکنیکال/.test(a.textContent ?? '')),
}));

// روبشِ سرریز: هر عنصرِ داخلِ صفحۀ اول که عرضِ محتوایش از باکسِ خودش بیشتر است
// یا از لبۀ پنل بیرون زده، «بریده» حساب می‌شود. عددِ چشمی در اسکرین‌شاتِ ۳۶۰
// پیکسلی خوانا نیست؛ این سنجش عددی است.
const overflow = await page.evaluate(() => {
  const panel = document.querySelector('[data-shell="inspector"]');
  if (!panel) return { panel: null, clipped: [] };
  const pr = panel.getBoundingClientRect();
  const clipped: { testid: string; text: string; why: string }[] = [];
  panel.querySelectorAll('[data-testid]').forEach((el) => {
    const r = el.getBoundingClientRect();
    const scrollOver = el.scrollWidth > el.clientWidth + 1;
    const outOfPanel = r.right > pr.right + 0.5 || r.left < pr.left - 0.5;
    if (scrollOver || outOfPanel) {
      clipped.push({
        testid: String(el.getAttribute('data-testid')),
        text: (el.textContent ?? '').trim().slice(0, 46),
        ellipsised: /truncate|text-ellipsis/.test(String(el.className)),
        why: `${scrollOver ? `scrollW=${el.scrollWidth}>clientW=${el.clientWidth}` : ''}`
           + `${outOfPanel ? ` rect=[${Math.round(r.left)},${Math.round(r.right)}] panel=[${Math.round(pr.left)},${Math.round(pr.right)}]` : ''}`,
      });
    }
  });
  const cells = [...document.querySelectorAll('[data-testid="inspector-volume"] > div')]
    .map((d) => (d.textContent ?? '').trim());
  return { panel: { left: Math.round(pr.left), right: Math.round(pr.right), width: Math.round(pr.width) },
           volumeCells: cells, clipped: clipped.slice(0, 14) };
});

const n0 = reqs.length;
const np0 = nonPoll().length;
const beforeOb = obReqs();
await page.click('[data-testid="inspector-tab-detail"]');
await page.waitForTimeout(500);
const afterTab = { reqsDelta: since(n0), nonPollDelta: nonPoll().length - np0,
                   obDelta: obReqs() - beforeOb, nonPoll: nonPoll().slice(np0) };
const collapsed = await page.evaluate(() => ({
  quotes: !!document.querySelector('[data-testid="inspector-quotes"]'),
  orderbookInDom: !!document.querySelector('[data-testid="sidebar-orderbook"]'),
  toggleLabel: String(document.querySelector('[data-testid="inspector-quotes-toggle"]')?.textContent ?? '').trim(),
}));

await page.click('[data-testid="inspector-quotes-toggle"]');
await page.waitForTimeout(1200);
const opened = await page.evaluate(() => ({
  orderbookInDom: !!document.querySelector('[data-testid="sidebar-orderbook"]'),
  rows: document.querySelectorAll('[data-testid="sidebar-orderbook"] li').length,
  detailHeightPx: Math.round(document.querySelector('[data-testid="inspector-page-detail"]')?.getBoundingClientRect().height ?? 0),
}));
const afterOpen = { obTotal: obReqs(), obDelta: obReqs() - beforeOb };

// رفت‌وبرگشت: حالتِ بازشو باید بماند و درخواستِ دومی نرود.
const n1 = reqs.length, np1 = nonPoll().length, ob1 = obReqs();
await page.click('[data-testid="inspector-tab-glance"]');
await page.waitForTimeout(300);
await page.click('[data-testid="inspector-tab-detail"]');
await page.waitForTimeout(700);
const roundTrip = await page.evaluate(() => {
  const g = document.querySelector('[data-testid="inspector-page-glance"]');
  return {
    stillOpen: !!document.querySelector('[data-testid="sidebar-orderbook"]'),
    toggleLabel: String(document.querySelector('[data-testid="inspector-quotes-toggle"]')?.textContent ?? '').trim(),
    glanceHidden: !!g && g.classList.contains('hidden'),
  };
});
const roundTripReqs = { reqsDelta: since(n1), nonPollDelta: nonPoll().length - np1,
                        obDelta: obReqs() - ob1, nonPoll: nonPoll().slice(np1) };

await page.screenshot({ path: '_audit/ws8_page_detail.png', clip: { x: 0, y: 0, width: 360, height: 880 } });
await page.click('[data-testid="inspector-tab-glance"]');
await page.waitForTimeout(400);
await page.screenshot({ path: '_audit/ws8_page_glance.png', clip: { x: 0, y: 0, width: 360, height: 880 } });

const res = {
  base: BASE, symbol,
  glance: order,
  absentOnGlance,
  tabSwitch: afterTab,
  collapsed,
  opened,
  afterOpen,
  roundTrip,
  roundTripReqs,
  pageErrors: errs,
  http4xx: bad,
  overflow,
  timeline,
};
const checks: [string, boolean][] = [
  ['inspector opened on a real row click', order.found],
  ['page 1 order matches the ruling', JSON.stringify(order.seen) === JSON.stringify([
    'inspector-volume', 'inspector-market-cap', 'inspector-power', 'inspector-regulatory',
    'تکنیکال FTS', 'نمره بنیادی', 'inspector-stage', 'inspector-events', 'inspector-veto-why'])],
  ['page 2 content absent while on page 1', absentOnGlance.quotes === false && absentOnGlance.techLink === false],
  // جابه‌جاییِ صفحّه باید هیچ درخواستِ «غیرِ polling»ی نسازد؛ pollingِ همیشگیِ
  // تابلو (/api/market/delta و …) کارِ خودِ خوراک است و به این رأی ربطی ندارد.
  // درِ حالتِ توسعه، اپ داخل `<StrictMode>` است و اولین mount را دو بار اجرا
  // می‌کند؛ اثرش درِ همین timeline دیده می‌شود (دو درخواستِ یکسان با فاصلۀ
  // چند میلی‌ثانیه). سنجشِ درست پس همین است: پنل‌هایِ تازه‌mount درخواستِ خودشان
  // را می‌زنند، و هیچ درخواستِ دیگری به نامِ «صفحّه عوض شد» ساخته نمی‌شود.
  ['first page-2 open only asks its own panels\' data',
      afterTab.nonPoll.every((u) => /^\/api\/(selection\/portfolio|order-book\/)/.test(u))],
  ['no refetch on later switches (cached)', roundTripReqs.nonPollDelta === 0 && roundTripReqs.obDelta === 0],
  ['quotes collapsed by default (not in DOM)', collapsed.orderbookInDom === false],
  ['opening quotes fetches the book and paints the five levels',
      afterOpen.obDelta >= 1 && opened.orderbookInDom === true && opened.rows === 10],
  ['returning keeps it open (state preserved)', roundTrip.stillOpen === true],
  ['no page errors', errs.length === 0],
  // هیچ عددِ صفحۀ اول نباید بریده باشد: «truncate» هم بریدگی است، نه راه‌حل.
  ['no page-1 value clipped or overflowing', overflow.clipped.length === 0],
  ['no failed API responses (4xx/5xx)', bad.filter((b) => !/favicon/.test(b)).length === 0],
];
res.verdict = checks.map(([k, v]) => ({ check: k, pass: v }));
writeFileSync(OUT, JSON.stringify(res, null, 2));
for (const [k, v] of checks) console.log((v ? 'PASS ' : 'FAIL ') + k);
console.log('order=' + JSON.stringify(order.seen));
console.log(`heights glance=${order.heightPx}/${order.scrollHeightPx}px detail=${opened.detailHeightPx}px`);
console.log('symbols=' + JSON.stringify(symbol) + ' toggle=' + JSON.stringify([collapsed.toggleLabel, roundTrip.toggleLabel])
  + ' rows=' + opened.rows + ' obTotal=' + afterOpen.obTotal
  + ' tabNonPoll=' + JSON.stringify(afterTab.nonPoll) + ' tripNonPoll=' + JSON.stringify(roundTripReqs.nonPoll));
if (errs.length) console.log('errors: ' + JSON.stringify(errs.slice(0, 4)));
if (bad.length) console.log('http>=400: ' + JSON.stringify(bad.slice(0, 6)));
console.log('overflow sweep = ' + JSON.stringify(overflow));
console.log('timeline (non-poll) = ' + JSON.stringify(timeline.filter((t) => !POLL.test(t.url))));
await browser.close();
