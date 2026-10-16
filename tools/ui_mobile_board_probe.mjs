// tools/ui_mobile_board_probe.mjs -- تابلوخوانیِ گوشی: آزمونِ تعامل، نه حضورِ کارت
//
// بندِ ۲.۱ مأموریتِ System ۲ پنج چیزِ جدا می‌خواهد: نماد/قیمت/تغییر٪/ارزشِ معاملات
// خوانا، جست‌وجو، مرتب‌سازی، فیلتر، انتخاب نماد وِ جزئیات. «کارت درِ DOM هست» هیچ‌کدام
// ازِ این‌ها را اثبات نمی‌کند (آستانۀِ شواهدِ اینِ مأموریت: یکِ کنترلِ باِ آزمونِ اثرِ
// واقعیِ اندازه‌گیری‌شده می‌گذرد). اینِ فایل پسِ ازِ `ui_mobile_probe.mjs` می‌آید: آنِ
// یکِ هندسه می‌سنجد، اینِ یکِ رفتار.
//
// اجرا: node tools/ui_mobile_board_probe.mjs --base=http://127.0.0.1:8012 \
//         --out=_audit/ui2/mobile-board.json --shots=_audit/ui2
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.join(HERE, '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));

const args = Object.fromEntries(process.argv.slice(2).map((a) => {
  const m = /^--([^=]+)(?:=(.*))?$/.exec(a);
  return m ? [m[1], m[2] === undefined ? true : m[2]] : [a.replace(/^--/, ''), true];
}));
const BASE = args.base || 'http://127.0.0.1:8012';
const OUT = args.out || path.join('_audit', 'ui2', 'mobile-board.json');
const SHOTS = !!args.shots;
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const AUTH = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
const USER = (AUTH.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
const PASS = (AUTH.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
const WIDTHS = (args.widths || '360,390,430').split(',').map(Number);
const HEIGHT = Number(args.height || 844);

/** نمادی که درِ جست‌وجو تست می‌شود -- ازِ خودِ داده‌هایِ زنده برداشته می‌شود، نه سخت‌کد */
// `div` عمدتاً قید شده: کارت‌ها `data-testid="board-card-<نماد>"` دارند وِ اگرِ یکِ
// فرزندِ درونِ کارت هم باِ همینِ پیشوند نامیده شود، شمارشِ کارت‌ها وِ نمادِ استخراج‌شده
// فاسد می‌شود (درِ اجرای اولِ اینِ سنجش دقیقاً همین رخ داد). فیلدها بیرونِ اینِ
// پیشوند‌اند: `data-card-field="price|pct|value"`.
const CARD = 'div[data-testid^="board-card-"]';

const results = { base: BASE, generatedAt: new Date().toISOString(), widths: {} };
const browser = await chromium.launch({ executablePath: EXE, args: ['--force-device-scale-factor=1'] });

for (const w of WIDTHS) {
  const ctx = await browser.newContext({ viewport: { width: w, height: HEIGHT }, locale: 'fa-IR', deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 160)));
  const R = results.widths[w] = {};

  await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
  if (await page.locator('input[type="password"]').count()) {
    await page.locator('input[type="text"]').first().fill(USER);
    await page.locator('input[type="password"]').first().fill(PASS);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(1200);
  }

  // ۱) کارت‌ها: چندِ میلی‌ثانیه تاِ نخستینِ کارتِ باِ داده؟ (صفرِ کارت = یاِ سرد یاِ خراب)
  const t0 = Date.now();
  let firstCardMs = null;
  try {
    await page.waitForSelector(CARD, { timeout: 25000 });
    firstCardMs = Date.now() - t0;
  } catch { firstCardMs = null; }
  R.firstCardMs = firstCardMs;
  R.cardCount = await page.locator(CARD).count();
  if (!R.cardCount) {
    R.boardState = (await page.locator('body').innerText()).replace(/\s+/g, ' ').slice(0, 220);
    R.pageErrors = errs.length;
    await ctx.close();
    continue;
  }

  // ۲) خواناییِ چهارِ فیلدِ لازم رویِ سه کارتِ نخست + بریدگیِ متنِ داخلِ کارت
  R.fieldAudit = await page.evaluate((sel) => {
    const fa = (s) => (s || '').replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
      .replace(/[٠-٩]/g, (d) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
      .replace(/[٬،]/g, ',');
    const field = (c, name) => {
      const el = c.querySelector(`[data-card-field="${name}"]`);
      if (!el) return null;
      const raw = fa((el.textContent || '').trim());
      return { text: raw.slice(0, 18), px: parseFloat(getComputedStyle(el).fontSize),
               num: (/(-?[\d]+(?:\.[\d]+)?)/.exec(raw) || [])[1] != null ? Number(/(-?[\d]+(?:\.[\d]+)?)/.exec(raw)[1]) : null };
    };
    const cards = Array.from(document.querySelectorAll(sel)).slice(0, 3);
    return cards.map((c) => {
      const vw = document.documentElement.clientWidth;
      const leaves = Array.from(c.querySelectorAll('*')).filter((e) => (
        e.children.length === 0 && (e.textContent || '').trim().length > 0));
      return {
        symbol: c.getAttribute('data-testid').replace('board-card-', ''),
        inViewport: c.getBoundingClientRect().right <= vw + 1 && c.getBoundingClientRect().left >= -1,
        cardW: Math.round(c.getBoundingClientRect().width),
        price: field(c, 'price'), pct: field(c, 'pct'), value: field(c, 'value'),
        clipped: leaves.filter((e) => e.scrollWidth > e.clientWidth + 2 && getComputedStyle(e).textOverflow !== 'ellipsis')
          .map((e) => ({ t: (e.textContent || '').trim().slice(0, 18), lost: e.scrollWidth - e.clientWidth })),
        minFontPx: Math.min(...leaves.map((e) => parseFloat(getComputedStyle(e).fontSize))),
      };
    });
  }, CARD);

  // ۳) مرتب‌سازیِ واقعی: سهِ کلید، سهِ ترتیب -- اگرِ کارت‌ها جابه‌جا نشوند، دکمه تزئین است
  const firstSymbols = async () => page.$$eval(CARD, (els) => els.slice(0, 5).map((e) => e.getAttribute('data-testid').replace('board-card-', '')));
  // خواندنِ ستونِ مرتب‌شده ازِ خودِ کارت. یکِ سنجشِ «آیاِ نزولی است» رویِ ستونی که
  // پر ازِ null است بی‌معنی سبز می‌شود؛ پسِ `nulls` هم ثبت می‌شود وِ یکنوا-بودنِ
  // فقطِ وقتی اعتبار دارد که بیشترۀِ ستون عدد داشته باشد.
  const colValues = (name) => page.$$eval(CARD, (els, f) => {
    const fa = (s) => (s || '').replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
      .replace(/[٠-٩]/g, (d) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d))).replace(/[,٬،]/g, '');
    return els.map((e) => {
      const el = e.querySelector(`[data-card-field="${f}"]`);
      if (!el) return null;
      const m = /(-?\d+(?:\.\d+)?)/.exec(fa((el.textContent || '').trim()));
      return m ? Number(m[1]) : null;
    });
  }, name);
  const monotonic = (a, dir) => {
    const v = a.filter((x) => x != null);
    return { checked: v.length, nulls: a.length - v.length,
      ok: v.every((x, i) => i === 0 || (dir === 'desc' ? v[i - 1] >= x : v[i - 1] <= x)) };
  };

  const order = { before: await firstSymbols() };
  await page.selectOption('[data-testid="tape-cards-sort"]', 'q_tot_cap');
  await page.waitForTimeout(500);
  order.byValue = await firstSymbols();
  order.byValueCol = await colValues('value');
  order.byValueMonotonic = monotonic(order.byValueCol, 'desc');
  await page.click('[data-testid="tape-cards-direction"]');
  await page.waitForTimeout(500);
  order.byValueReversed = await firstSymbols();
  order.byValueReversedCol = await colValues('value');
  order.byValueReversedMonotonic = monotonic(order.byValueReversedCol, 'asc');
  await page.selectOption('[data-testid="tape-cards-sort"]', 'percent_change');
  await page.waitForTimeout(500);
  order.byPctDesc = await firstSymbols();
  order.pctValues = await colValues('pct');
  order.pctMonotonic = monotonic(order.pctValues, 'desc');
  R.sort = order;

  const searchSel = 'input[placeholder*="جستجوی"]';
  // ۴) جست‌وجو: یکِ نمادِ واقعی تایپ → فقطِ همان؛ پاک‌کردن → برگشتِ شمارۀِ پیش
  // شمارش ازِ تراشۀِ خودِ تابلو («X از Y نماد») خوانده می‌شود، نه ازِ تعدادِ کارتِ
  // داخلِ DOM: مجازی‌ساز فقطِصفحۀِ اسکرول را می‌سازد وِ مقایسۀِ آن باِ «قبل» بی‌معنی است.
  const shownCount = () => page.evaluate(() => {
    const el = document.querySelector('[data-testid="tape-shown-count"]');
    if (!el) return null;
    const t = (el.textContent || '').replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)));
    const m = /(\d+)/.exec(t);
    return m ? Number(m[1]) : null;
  });
  const countBefore = await shownCount();
  const target = order.before[1] || order.before[0];
  await page.locator(searchSel).first().fill(target);
  await page.waitForTimeout(700);
  const afterSearch = await page.$$eval(CARD, (els) => els.map((e) => e.getAttribute('data-testid').replace('board-card-', '')));
  const shownDuringSearch = await shownCount();
  await page.locator(searchSel).first().fill('');
  await page.waitForTimeout(900);
  R.search = {
    query: target, matched: afterSearch.length, matchedSymbols: afterSearch,
    onlyTarget: afterSearch.length > 0 && afterSearch.every((s) => s.startsWith(target)),
    shownBefore: countBefore, shownDuringSearch, shownAfterClear: await shownCount(),
  };

  // ۵) انتخابِ نماد باِ لمس: اثرِ بینِ اجزایی (کارتِ انتخابی + ریشۀِ نوارِ بالا)
  // نماد ازِ کارت‌هایِ «همین حالاِ رندرشده» برداشته می‌شود؛ مجازی‌ساز فقطِ ~۲۳ کارت
  // درِ DOM دارد وِ نمادِ فهرستِ قدیمی ممکن است اکنون بیرونِ پنجرۀِ اسکرول باشد.
  const live = await page.$$eval(CARD, (els) => els.map((e) => e.getAttribute('data-testid').replace('board-card-', '')));
  const pick = live[2] || live[0];
  await page.click(`[data-testid="board-card-${pick}"]`);
  await page.waitForTimeout(500);
  R.selection = await page.evaluate((p) => {
    const el = document.querySelector(`[data-testid="board-card-${p}"]`);
    const crumb = document.querySelector('header nav');
    return {
      picked: p,
      ariaCurrent: el ? el.getAttribute('aria-current') : null,
      othersCurrent: Array.from(document.querySelectorAll('[data-testid^="board-card-"]'))
        .filter((c) => c.getAttribute('aria-current')).length,
      topbarShowsSymbol: crumb ? (crumb.textContent || '').includes(p) : false,
    };
  }, pick);

  // ۶) پنهان‌نشدنِ محتوا زیرِ نوارِ پایین: آخرینِ کارتِ دیده‌شدنی باید بالایِ نوار باشد
  await page.locator('[data-testid="tape-cards-scroll"]').evaluate((e) => { e.scrollTop = e.scrollHeight; });
  await page.waitForTimeout(500);
  R.occlusion = await page.evaluate((sel) => {
    const bar = document.querySelector('[data-testid="mobile-nav"]');
    if (!bar) return { error: 'no-bottom-nav' };
    const barTop = bar.getBoundingClientRect().top;
    const cards = Array.from(document.querySelectorAll(sel));
    const visible = cards.filter((c) => { const r = c.getBoundingClientRect(); return r.bottom > 0 && r.top < window.innerHeight; });
    const lowest = visible.reduce((m, c) => Math.max(m, c.getBoundingClientRect().bottom), 0);
    return { barTop: Math.round(barTop), lowestVisibleCard: Math.round(lowest), clearBy: Math.round(barTop - lowest), rendered: cards.length };
  }, CARD);

  // ۶-ب) زنجیرۀِ هندسه: کدامِ حلقه رزروِ ۵۶px را می‌شکند؟ (بدونِ این، «زیرِ نوار» فقط
  // یکِ عددِ بی‌نام است وِ اصلاحِ حدسی بهِ همانِ جایِ اول برمی‌گردد)
  R.layoutChain = await page.evaluate(() => {
    const px = (v) => Math.round(parseFloat(v) || 0);
    const chain = [];
    let el = document.querySelector('[data-testid="tape-cards-scroll"]');
    while (el && chain.length < 9) {
      const s = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      chain.push({
        node: el.getAttribute('data-testid') || el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : ''),
        top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height),
        position: s.position, display: s.display, overflowY: s.overflowY,
        height: s.height, minHeight: s.minHeight, flex: s.flex,
        paddingBottom: px(s.paddingBottom), marginBottom: px(s.marginBottom),
      });
      el = el.parentElement;
    }
    const nav = document.querySelector('[data-testid="mobile-nav"]');
    // کودکانِ مستقیمِ ستونِ صفحۀِ تابلو: «کجا ارتفاع می‌رود» را فقطِ همینِ فهرست
    // بی‌نیاز ازِ حدس جواب می‌دهد (بارِ فیلترها درِ گوشی سرِ جدول را می‌خورد).
    const col = document.querySelector('[data-testid="tape-cards"]')?.closest('.glass-panel')?.parentElement;
    const pageChildren = col ? Array.from(col.children).map((c) => {
      const r = c.getBoundingClientRect();
      return { node: c.getAttribute('data-testid') || String(c.className).split(' ').slice(0, 3).join('.'),
               top: Math.round(r.top), h: Math.round(r.height), flex: getComputedStyle(c).flex };
    }) : null;
    return {
      innerHeight: window.innerHeight,
      docScrollH: document.documentElement.scrollHeight,
      navH: nav ? Math.round(nav.getBoundingClientRect().height) : null,
      navTop: nav ? Math.round(nav.getBoundingClientRect().top) : null,
      pageChildren,
      chain,
    };
  });

  // ۷) ناوبریِ پایین: هرِ مقصدِ اصلی باید واقعاً مسیر را عوض کند
  const navSteps = [];
  for (const id of ['mobile-nav-market-status', 'mobile-nav-technical', 'mobile-nav-watch']) {
    const before = page.url();
    await page.click(`[data-testid="${id}"]`);
    await page.waitForTimeout(900);
    navSteps.push({ id, moved: page.url() !== before, to: page.url().split('#')[1] });
  }
  await page.click('[data-testid="mobile-nav-more"]');
  await page.waitForTimeout(300);
  const sheetOpen = await page.locator('#mobile-nav-sheet').count();
  await page.click('[data-testid="mobile-nav-more-order-line"]');
  await page.waitForTimeout(900);
  navSteps.push({ id: 'more→order-line', moved: page.url().includes('/order-line'), sheetOpenBefore: sheetOpen, to: page.url().split('#')[1] });
  R.nav = navSteps;

  if (SHOTS) {
    fs.mkdirSync(path.join(REPO, '_audit', 'ui2'), { recursive: true });
    await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector(CARD, { timeout: 25000 }).catch(() => {});
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join('_audit', 'ui2', `mobile-board-${w}.png`) });
  }
  R.pageErrors = errs.length;
  if (errs.length) R.errorSample = errs.slice(0, 3);
  await ctx.close();
}

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(results, null, 2), 'utf8');

for (const [w, R] of Object.entries(results.widths)) {
  console.log(`\n=== ${w}×${HEIGHT} ===`);
  if (!R.cardCount) { console.log(`  کارت‌ها: ۰ (waitMs=${R.firstCardMs}) -- ${R.boardState}`); continue; }
  console.log(`  نخستینِ کارت: ${R.firstCardMs}ms | شمارۀِ کارت: ${R.cardCount}`);
  console.log(`  مرتب‌سازی: ${R.sort.before[0]} → ${R.sort.byValue[0]} → ${R.sort.byValueReversed[0]} | ارزش نزولی: ${JSON.stringify(R.sort.byValueMonotonic)} | صعودی: ${JSON.stringify(R.sort.byValueReversedMonotonic)} | تغییر٪: ${JSON.stringify(R.sort.pctMonotonic)}`);
  console.log(`  جست‌وجوی «${R.search.query}»: ${R.search.matched} کارت ${JSON.stringify(R.search.matchedSymbols)} | فقطِ خودِ نماد: ${R.search.onlyTarget} | شمارۀِ تابلو ${R.search.shownBefore}→${R.search.shownDuringSearch}→${R.search.shownAfterClear}`);
  console.log(`  انتخاب: aria-current=${R.selection.ariaCurrent} تعدادِ انتخاب‌شده=${R.selection.othersCurrent} نماد درِ نوارِ بالا: ${R.selection.topbarShowsSymbol}`);
  console.log(`  انسدادِ نوار: ${JSON.stringify(R.occlusion)}`);
  console.log(`  ناوبری: ${R.nav.map((n) => `${n.id}→${n.to}(${n.moved ? '✓' : '✗'})`).join('  ')}`);
  console.log(`  خطاهایِ صفحه: ${R.pageErrors}  فیلدِ کارت: ${JSON.stringify(R.fieldAudit[0])}`);
}
console.log(`\n→ ${OUT}`);
await browser.close();
