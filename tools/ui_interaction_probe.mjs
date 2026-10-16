// tools/ui_interaction_probe.mjs -- آزمونِ تعاملاتِ واقعیِ صفحات درِ مرورگر (۱۳۶۶×۷۶۸)
//
// چرا اینِ فایل هست: «دکمه وجود دارد» باِ «دکمه کارِ خودش را می‌کند» فرق دارد. اینِ
// سنجش هرِ سناریو را باِ یکِ کارِ کاربر می‌سنجد (یکِ ردیف را باز کن، فیلتر بزن،
// ستون را مرتب کن، برگرد، نشانیِ مستقیم باز کن، تب ببند) وِ نتیجه را باِ شاهدِ
// عددیِ همانِ کار ثبت می‌کند؛ بی‌گذشتنِ آنِ کار، سطرِ سناریو قرمز است.
//
// اجرا:  node tools/ui_interaction_probe.mjs --base=http://127.0.0.1:8010 \
//          --out=_audit/ui2/interactions-before.json --label="پیش ازِ بازطراحی"
// خروجی: ۰ = همه سبز؛ ۱ = دستِ‌کمِ یکِ سطرِ قرمز (پس درِ گیتِ دستِ‌یافتنی قابلِ استفاده است).
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
const OUT = args.out || path.join('_audit', 'ui2', 'interactions.json');
const LABEL = args.label || 'بی‌برچسب';
const ONLY = (args.only || '').split(',').filter(Boolean);
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const VP = /^([0-9]+)x([0-9]+)$/.exec(args.viewport || '1366x768');
const VIEWPORT = { width: Number(VP[1]), height: Number(VP[2]) };

let bundleLabel = '';
const AUTH_SRC = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
const USER = (AUTH_SRC.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
const PASS = (AUTH_SRC.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];

const FA = '۰۱۲۳۴۵۶۷۸۹';
const AR = '٠١٢٣٤٥٦٧٨٩';
const num = (s) => Number(String(s || '')
  .replace(/[۰-۹]/g, (d) => String(FA.indexOf(d)))
  .replace(/[٠-٩]/g, (d) => String(AR.indexOf(d)))
  .replace(/[,\s٪%×]/g, '').replace('−', '-'));

const scenarios = [];
const mk = (id, title) => {
  const s = { id, title, steps: [] };
  scenarios.push(s);
  const step = (what, pass, evidence) => { s.steps.push({ what, pass: !!pass, evidence: String(evidence).slice(0, 220) }); return !!pass; };
  return { s, step };
};

async function newSession(browser, bootPath = null) {
  const ctx = await browser.newContext({ viewport: VIEWPORT, locale: 'fa-IR', deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = [];
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 160)); });
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 160)));
  let t0 = Date.now();
  const reqs = [];
  page.on('request', (r) => {
    const u = new URL(r.url());
    if (u.pathname.startsWith('/api/')) reqs.push({ p: u.pathname, q: u.search, start: Date.now() - t0, end: null });
  });
  page.on('response', (res) => {
    const u = new URL(res.url());
    if (!u.pathname.startsWith('/api/')) return;
    const hit = [...reqs].reverse().find((r) => r.p === u.pathname && r.end === null);
    if (hit) { hit.end = Date.now() - t0; hit.status = res.status(); }
  });
  await page.goto(`${BASE}/${bootPath ? `#${bootPath}` : ''}`, { waitUntil: 'domcontentloaded' });
  if (USER && PASS && await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    await page.locator('input[type="text"]').first().fill(USER);
    await page.locator('input[type="password"]').first().fill(PASS);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2000);
  }
  if (!bundleLabel) {
    // همانِ درسی که دورِ پیش ازِ سنجشِ تب گرفته شد: شاهدی که بیلدِ خودش را
    // نمی‌نویسد، درِ مقایسهٔ پیش/پس بی‌ارزش است.
    bundleLabel = await page.evaluate(() => Array.from(document.querySelectorAll('script[src]'))
      .map((x) => x.getAttribute('src')).filter((x) => x.includes('/assets/')).join(' '));
  }
  return { ctx, page, errs, reqs, mark: () => { reqs.length = 0; t0 = Date.now(); }, rebase: () => { t0 = Date.now(); } };
}

// زمانِ رسیدنِ داده‌یِ دیدنی: هرِ ۱۵۰ms شرطِ داده را می‌خواند؛ بی‌این، «۳ ثانیه
// صبر کردم» خودش یکِ عددِ ساختگی است.
async function waitFor(page, fn, ms = 9000) {
  const t = Date.now();
  for (;;) {
    if (await page.evaluate(fn)) return Date.now() - t;
    if (Date.now() - t > ms) return null;
    await page.waitForTimeout(150);
  }
}

/* ─────────────────────────── ۱) بازکردنِ سردِ «وضعیت بازار» ─────────────────────────── */
async function s_cold_open(browser) {
  const { step } = mk('cold-open', 'بازکردنِ سردِ /market-status: داده‌هایِ خودِ صفحه زودتر ازِ بارِ پوسته می‌رسد');
  // «مسیرِ مستقیمِ نشانی» خودِ مأموریت است: کاربرِ نشانک‌زده نباید بهایِ کارِ
  // صفحۀِ دیگری را بپردازد، پس همین‌جا ازِ همانِ route بالا می‌آییم.
  const { ctx, page, reqs, errs, rebase } = await newSession(browser, '/market-status');
  rebase(); // صفرِ ساعت = لحظۀِ پایانِ ورود؛ پرسش‌هایِ پیش ازِ آن آفستِ منفی می‌گیرند
  const dataMs = await waitFor(page, () => {
    const el = document.querySelector('[data-testid="ms-index-cards-span"]');
    return !!el && /[۰-۹]/.test(el.textContent || '');
  });
  const mine = reqs.filter((r) => r.p.includes('/mstat/'));
  // سکرینر وِ قیف کارِ صفحۀِ غربالگری‌اند، نه اینِ صفحه. خوراکِ تابلو از اینِ فهرست
  // بیرون است، چون «نمودارِ پیشرفته»یِ خودِ اینِ صفحه (MarketChartSection) فهرستِ نمادها
  // را ازِ همانِ نشانی می‌خواند؛ شمردنش یعنی کارِ خودِ صفحه بهِ حسابِ پوسته.
  const heavy = reqs.filter((r) => ['/api/screener', '/api/funnel'].includes(r.p));
  const board = reqs.filter((r) => r.p === '/api/market');
  const firstMine = mine.length ? Math.min(...mine.map((r) => r.start)) : null;
  const blocking = heavy.filter((r) => r.end == null || r.end > (firstMine ?? 0));
  step('درخواست‌هایِ mstatِ خودِ صفحه ثبت شد', mine.length >= 5,
    `${mine.length} درخواست: ${mine.map((r) => `${r.p.split('/').pop()}@${r.start}ms`).join(' ')}`.slice(0, 200));
  step('کارتِ شاخص باِ عددِ واقعی نشست (نه «بدون داده»)', dataMs != null,
    `داده درِ ${dataMs == null ? 'ناخوانده' : `${dataMs}ms`} ازِ ناوبری`);
  step('اولینِ درخواستِ صفحه پیش ازِ ۱۵۰۰ms آغاز شد', firstMine != null && firstMine < 1500, `اولینِ mstat درِ ${firstMine}ms`);
  step('هیچِ درخواستِ سنگینِ بی‌ربطی (سکرینر/قیف/تابلو) راهِ درخواستِ صفحه را نبسته',
    blocking.length === 0,
    `سنگین‌هایِ بی‌ربط: ${heavy.map((r) => `${r.p.split('/').pop()} ${r.start}→${r.end}ms`).join(' ') || 'هیچ'} · خوراکِ تابلویِ خودِ صفحه: ${board.length ? `${board[0].start}→${board[0].end}ms` : 'پرسیده نشد'}`.slice(0, 220));
  step('بی‌خطایِ کنسول', errs.length === 0, errs.slice(0, 2).join(' | ') || 'هیچ');
  await ctx.close();
}

/* ─────────────────────────── ۲) کلیکِ ردیفِ تابلو ─────────────────────────── */
async function s_row_click(browser) {
  const { step } = mk('row-click', 'کلیکِ یکِ ردیفِ تابلو: پنجرۀِ جزئیات باِ همانِ نماد باز می‌شود');
  const { ctx, page, errs } = await newSession(browser);
  await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
  await waitFor(page, () => document.querySelectorAll('[data-testid="tape-row"]').length > 3);
  const rows = await page.locator('[data-testid="tape-row"]').count();
  step('ردیفِ تابلو نشسته', rows > 3, `${rows} ردیفِ دیدنی`);
  const target = page.locator('[data-testid="tape-row"]').nth(2);
  // نماد ازِ گره‌هایِ متنیِ خودِ سلول خوانده می‌شود: جعبه وِ ستاره عنصر‌اند، نشانیِ ردیف نه
  const sym = await target.evaluate((el) => {
    const cell = el.firstElementChild;
    if (!cell) return '';
    return Array.from(cell.childNodes).filter((n) => n.nodeType === 3).map((n) => n.textContent.trim()).join('').trim();
  });
  await target.click();
  await page.waitForTimeout(1200);
  const insp = await page.evaluate(() => {
    const el = document.querySelector('[data-shell="inspector"]');
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { left: Math.round(r.left), width: Math.round(r.width), text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 90) };
  });
  step('پنجرۀِ جزئیات رویِ صحنه آمد (ازِ کناری بیرون نیفتاده)', !!insp && insp.left >= 0, JSON.stringify(insp));
  step('نمادِ انتخاب‌شده باِ ردیفِ کلیک‌شده یکی است', !!insp && sym.length >= 2 && insp.text.includes(sym),
    `کلیک: «${sym}» → پنجره: «${insp ? insp.text.slice(0, 40) : '—'}»`);
  step('بی‌خطایِ کنسول', errs.length === 0, errs.slice(0, 2).join(' | ') || 'هیچ');
  await ctx.close();
}

/* ─────────────────────────── ۳) تراشۀِ فیلتر وِ جست‌وجو ─────────────────────────── */
async function s_filters(browser) {
  const { step } = mk('filters', 'تراشۀِ فیلتر وِ جست‌وجو: شمارندۀِ خودِ نوار («N از M نماد») باید عوض شود');
  const { ctx, page } = await newSession(browser);
  await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
  await waitFor(page, () => document.querySelectorAll('[data-testid="tape-row"]').length > 3);
  // شمارندۀِ دیدنیِ نوار، نه شمارشِ ردیف‌هایِ رندرشده: جدول مجازی‌سازی شده است وِ
  // تعدادِ ردیفِ DOM همیشه ~۲۵ می‌ماند؛ «دکمه کار کرد» باِ این عدد سنجیده نمی‌شود.
  const shown = () => page.evaluate(() => {
    const bar = document.querySelector('[data-testid="market-filters-bar"]');
    if (!bar) return null;
    const fa = '۰۱۲۳۴۵۶۷۸۹';
    const toNum = (t) => Number(String(t).replace(/,/g, '').replace(/[۰-۹]/g, (d) => String(fa.indexOf(d))));
    const spans = Array.from(bar.querySelectorAll('span'));
    const i = spans.findIndex((e) => (e.textContent || '').trim() === 'از');
    if (i < 1 || !spans[i - 1] || !spans[i + 1]) return null;
    return { n: toNum(spans[i - 1].textContent), total: toNum(spans[i + 1].textContent) };
  });
  const base = await shown();
  step('شمارندۀِ نمادها رویِ صحنه خوانده می‌شود', !!base && base.n > 0, JSON.stringify(base));
  const chip = page.locator('button').filter({ hasText: /مشکوک|هوشمند|زنده/ }).first();
  const chipText = ((await chip.textContent().catch(() => '')) || '').replace(/\s+/g, ' ').trim();
  await chip.click().catch(() => null);
  await page.waitForTimeout(1600);
  const afterChip = await shown();
  step(`تراشۀِ فیلتر «${chipText}» شمارندۀِ نمادها را عوض کرد`,
    !!base && !!afterChip && afterChip.n !== base.n, `${base && base.n} → ${afterChip && afterChip.n} نماد`);
  await chip.click().catch(() => null);
  await page.waitForTimeout(900);
  const box = page.locator('input[placeholder*="جستجوی نماد"]').first();
  await box.fill('فولاد');
  await page.waitForTimeout(1600);
  const afterQuery = await shown();
  const texts = await page.locator('[data-testid="tape-row"]').evaluateAll((els) =>
    els.slice(0, 5).map((e) => (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 30)));
  step('جست‌وجویِ «فولاد» شمارندۀِ نمادها را کم کرد وِ ردیف‌ها همانِ نام را دارند',
    !!afterQuery && !!base && afterQuery.n > 0 && afterQuery.n < base.n && texts.some((t) => t.includes('فولاد')),
    `${base && base.n} → ${afterQuery && afterQuery.n} نماد · رديف‌ها: ${texts.join(' | ') || 'هیچ'}`);
  await box.fill('');
  const clear = page.locator('[data-testid="tape-clear-filters"], [data-testid="filters-reset"]').first();
  if (await clear.count()) {
    await clear.click();
    await page.waitForTimeout(1200);
    const back = await shown();
    step('پاک‌کردنِ فیلتر شمارندۀِ کاملِ تابلو را بازمی‌گرداند', !!back && !!base && Math.abs(back.n - base.n) <= 2,
      `${afterQuery && afterQuery.n} → ${back && back.n} نماد`);
  } else {
    step('دکمهٔ پاک‌کردنِ فیلتر رویِ صحنه است', false, 'یافت نشد');
  }
  await ctx.close();
}

/* ─────────────────────────── ۴) مرتب‌سازیِ ستون ─────────────────────────── */
async function s_sort(browser) {
  const { step } = mk('sort', 'مرتب‌سازیِ ستون: کلیکِ سرستون باید همانِ ستون را مرتب وِ جهت را برگرداند');
  const { ctx, page } = await newSession(browser);
  await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
  await waitFor(page, () => document.querySelectorAll('[data-testid="tape-row"]').length > 5);
  const idx = await page.evaluate(() => {
    const hs = Array.from(document.querySelectorAll('[data-testid="tape-head"] > *'));
    return hs.findIndex((e) => (e.textContent || '').trim() === 'تغییر٪');
  });
  const head = page.locator('[data-testid="tape-head"] > *').nth(idx);
  // ستون باِ اندیسِ سرستون خوانده می‌شود؛ «اولینِ سلولِ درصددار» سه ستونِ درصدی را قاطی می‌کرد
  const readCol = (i) => page.evaluate((k) => Array.from(document.querySelectorAll('[data-testid="tape-row"]')).slice(0, 8)
    .map((r) => (r.children[k] ? r.children[k].textContent : '').trim()), i);
  const a = await readCol(idx);
  await head.click().catch(() => null);
  await page.waitForTimeout(1400);
  const b = await readCol(idx);
  await head.click().catch(() => null);
  await page.waitForTimeout(1400);
  const c = await readCol(idx);
  const sorted = (v) => {
    const n = v.map(num);
    if (n.some((x) => Number.isNaN(x))) return false;
    return n.every((x, i) => i === 0 || n[i - 1] >= x) || n.every((x, i) => i === 0 || n[i - 1] <= x);
  };
  step('سرستونِ «تغییر٪» درست پیدا شد', idx > 0, `اندیسِ ستون: ${idx}`);
  step('کلیکِ سرستون همانِ ستون را مرتب کرد', sorted(b), `${a.slice(0, 4).join(' ')} → ${b.slice(0, 4).join(' ')}`);
  step('کلیکِ دوم جهتِ ترتیب را برگرداند', JSON.stringify(b) !== JSON.stringify(c), `${b.slice(0, 3).join(' ')} ⇄ ${c.slice(0, 3).join(' ')}`);
  await ctx.close();
}

/* ─────────────────────────── ۵) اسکرول وِ سرستونِ چسبان ─────────────────────────── */
async function s_scroll(browser) {
  const { step } = mk('scroll', 'اسکرولِ تابلو: سرستون باید بماند وِ ردیف‌ها باید عوض شوند');
  const { ctx, page } = await newSession(browser);
  await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
  await waitFor(page, () => document.querySelectorAll('[data-testid="tape-row"]').length > 5);
  const first = () => page.evaluate(() => {
    const r = document.querySelector('[data-testid="tape-row"]');
    const head = document.querySelector('[data-testid="tape-head"]');
    return { row: r ? (r.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 18) : null,
      headTop: head ? Math.round(head.getBoundingClientRect().top) : null,
      docTop: Math.round(window.scrollY) };
  });
  const a = await first();
  await page.evaluate(() => { const el = document.querySelector('[data-testid="tape-scroll"]'); if (el) el.scrollTop += 3000; });
  await page.waitForTimeout(900);
  const b = await first();
  step('اسکرولِ درونیِ فهرست ردیف‌ها را عوض کرد', a.row !== b.row, `${a.row} → ${b.row}`);
  step('سرستونِ جدول رویِ صحنه ماند', b.headTop != null && b.headTop >= 0 && b.headTop < 400, `headTop ${a.headTop} → ${b.headTop}`);
  const doc = await page.evaluate(() => ({ h: document.documentElement.scrollHeight, v: window.innerHeight }));
  step('بدۀِ سند بی‌اسکرولِ اضافه است (پوسته قدِ خودش می‌ماند)', doc.h <= doc.v + 4, `document ${doc.h}px درِ برابرِ viewport ${doc.v}px`);
  await ctx.close();
}

/* ─────────────────────────── ۶) برگشت، پیش‌روی وِ نشانیِ مستقیم ─────────────────────────── */
async function s_history(browser) {
  const { step } = mk('history', 'برگشتِ مرورگر، پیش‌روی وِ نشانیِ مستقیم: نماد وِ صفحه باید حفظ شوند');
  const { ctx, page, reqs } = await newSession(browser);
  await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
  await waitFor(page, () => document.querySelectorAll('[data-testid="tape-row"]').length > 3);
  const row = page.locator('[data-testid="tape-row"]').nth(1);
  const code = await row.evaluate((el) => (el.textContent || '').trim().slice(0, 12));
  await row.click();
  await page.waitForTimeout(900);
  await page.goto(`${BASE}/#/technical/${encodeURIComponent('فولاد')}`, { waitUntil: 'domcontentloaded' });
  const techMs = await waitFor(page, () => !!document.querySelector('[data-testid="chart-area"]'));
  step('نشانیِ مستقیمِ /technical/فولاد چارت را می‌آورد', techMs != null, `چارت درِ ${techMs}ms`);
  // پرسشِ شمع‌ها پس ازِ آمدنِ میزبانِ چارت آغاز می‌شود؛ خواندنِ بی‌درنگِ فهرستِ
  // درخواست‌ها «بی‌پرسش» می‌داد در حالی که ۳۰۰ms بعد همان پرسش ثبت شده بود.
  let chartQ = '';
  let asked = '';
  for (let i = 0; i < 40; i += 1) {
    chartQ = reqs.filter((r) => /^\/api\/chart(\/|$)/.test(r.p)).map((r) => decodeURIComponent(r.p)).join(' ');
    asked = ((/\/api\/chart\/([^\s?]+)/.exec(chartQ) || [])[1] || '').trim();
    if (asked) break;
    await page.waitForTimeout(150);
  }
  const crumb = await page.evaluate(() => { const n = document.querySelector('header nav'); return n ? n.textContent.replace(/\s+/g, ' ').trim() : ''; });
  step('چارت باِ نمادِ همانِ نشانی ازِ سرور داده خواست', asked === 'فولاد', `پرسشِ چارت: ${chartQ.slice(0, 90) || 'بی‌پرسش'}`);
  step('نشانِ بالایِ صفحه همانِ نمادِ نشانی را می‌گوید', crumb.includes('فولاد'), `نشان: «${crumb}»`);
  await page.goBack();
  await page.waitForTimeout(1200);
  const back = await page.evaluate(() => ({ hash: location.hash, rows: document.querySelectorAll('[data-testid="tape-row"]').length }));
  step('برگشتِ مرورگر بهِ تابلو بازمی‌گرداند', back.hash.includes('/market') && back.rows > 3, `${back.hash} · ${back.rows} ردیف`);
  await page.goForward();
  await page.waitForTimeout(1200);
  const fwd = await page.evaluate(() => location.hash);
  step('پیش‌رویِ مرورگر دوباره چارت را می‌آورد', fwd.includes('/technical'), fwd);
  // نشانِ بالا نشانیِ URL را می‌گوید (درستِ خودش)؛ برایِ «حفظِ نماد» باید خودِ
  // تابلو نگاه کرد: کدامِ ردیف هنوز انتخاب‌شده نشان داده می‌شود.
  await page.goBack();
  await page.waitForTimeout(1400);
  const sel = await page.evaluate(() => {
    const hit = Array.from(document.querySelectorAll('[data-testid="tape-row"]'))
      .find((r) => /bg-accent-blue/.test(r.className));
    if (!hit) return '';
    const cell = hit.firstElementChild;
    return cell ? Array.from(cell.childNodes).filter((n) => n.nodeType === 3).map((n) => n.textContent.trim()).join('').trim() : '';
  });
  const want = (code || '').replace(/[^؀-ۿA-Za-z]/g, '').slice(0, 4);
  step('نمادِ انتخاب‌شدهٔ کاربر پس ازِ برگشت همانِ ردیفِ انتخابی می‌ماند', sel.includes(want),
    `کلیک: «${want}» → ردیفِ انتخابی پس ازِ برگشت: «${sel}»`);
  await ctx.close();
}

/* ─────────────────────────── ۷) ساخت وِ بستنِ تب ─────────────────────────── */
async function s_tabs(browser) {
  const { step } = mk('tabs', 'ساخت وِ بستنِ تبِ فضایِ کاری: تبِ تازه نشانیِ خودش را دارد وِ بستنش بهِ تبِ کناری می‌رود');
  const { ctx, page } = await newSession(browser);
  const strip = '[data-shell="workspace-tabs"] [role="tab"]';
  await page.goto(`${BASE}/#/market-status`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1800);
  const n0 = await page.locator(strip).count();
  await page.locator('[data-testid="ws-tab-new"]').click();
  await page.waitForTimeout(1200);
  const n1 = await page.locator(strip).count();
  const h1 = await page.evaluate(() => location.hash);
  step('تبِ تازه ساخته شد وِ تبِ پیشین سرِ جایش ماند', n1 === n0 + 1 && /\/master|market-status/.test(h1), `${n0} → ${n1} تب · تبِ تازه ${h1}`);
  await page.goto(`${BASE}/#/watch`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  const titles = await page.locator(strip).evaluateAll((els) => els.map((e) => (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 14)));
  step('تبِ تازه نشانیِ خودش را نگه داشت', (await page.evaluate(() => location.hash)).includes('/watch'), `تب‌ها: ${titles.join(' | ')}`);
  const closeBtn = page.locator('[data-testid^="ws-tab-close-"]').last();
  await closeBtn.click();
  await page.waitForTimeout(1400);
  const n2 = await page.locator(strip).count();
  const h3 = await page.evaluate(() => location.hash);
  step('بستنِ تبِ فعال یکی کم می‌کند وِ بهِ تبِ کناری بازمی‌گردد', n2 === n1 - 1 && !h3.includes('/watch'), `${n1} → ${n2} تب · ${h3}`);
  const alive = await page.evaluate(() => (document.querySelector('main') ? document.querySelector('main').innerText : '').trim().length);
  step('پس ازِ بستن، صفحۀِ فعال بی‌محتوا نمی‌ماند', alive > 40, `${alive} نویسه درِ main`);
  await ctx.close();
}

/* ─────────────────────────── ۸) کیبورد درِ RTL ─────────────────────────── */
async function s_keyboard(browser) {
  const { step } = mk('keyboard', 'کیبورد: پالتِ فرمان، حرکتِ تب‌ها درِ RTL وِ ورودِ فوریِ نتایجِ جست‌وجو');
  const { ctx, page } = await newSession(browser);
  await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  await page.keyboard.press('Control+k');
  await page.waitForTimeout(700);
  const palette = await page.evaluate(() => {
    const i = document.querySelector('[data-testid="command-palette"] input, [role="dialog"] input');
    return i ? (i.getAttribute('placeholder') || 'input') : null;
  });
  step('Ctrl+K پالتِ فرمان را باز می‌کند', !!palette, palette || 'ورودیِ پالت پیدا نشد');
  await page.keyboard.type('فولاد');
  await page.waitForTimeout(1200);
  const hits = await page.evaluate(() => Array.from(document.querySelectorAll('[role="option"], [data-testid^="palette-row"]')).slice(0, 4)
    .map((e) => (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 18)));
  step('تایپِ نماد درِ پالت نتیجه می‌دهد', hits.length > 0, hits.join(' | ') || 'بی‌نتیجه');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(1500);
  const after = await page.evaluate(() => location.hash);
  step('Enter ازِ پالت بهِ صفحۀِ نماد می‌برد', /technical|fundamental|master/.test(after), after);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(400);
  const still = await page.evaluate(() => !!document.querySelector('[role="dialog"] input'));
  step('Escape پالت را می‌بندد', !still, still ? 'پالت باز ماند' : 'بسته شد');
  await ctx.close();
}

/* ─────────────────────────── ۹) فرم‌ها وِ دیالوگ‌ها ─────────────────────────── */
async function s_forms(browser) {
  const { step } = mk('forms', 'فرم وِ دیالوگ: افزودنِ نماد بهِ دیدهبان وِ بستنِ دیالوگ باِ Escape');
  const { ctx, page } = await newSession(browser);
  await page.goto(`${BASE}/#/watch`, { waitUntil: 'domcontentloaded' });
  // «دو‌ودو‌ثانیه صبر کردم» درِ دورِ شلوغِ سناریوها خودبه‌خود قرمز می‌شود؛ نشاندۀِ
  // خودِ فرم خوانده می‌شود تاِ عددِ زمان، نتیجۀِ کارِ کاربر نشود.
  await waitFor(page, () => !!document.querySelector('[data-testid="watch-add-area"] input, input[placeholder*="نماد"]'), 7000);
  const box = page.locator('[data-testid="watch-add-area"] input, input[placeholder*="نماد"]').first();
  const has = await box.count();
  step('فرمِ افزودنِ نماد رویِ صحنه است', has > 0, has ? 'پیدا شد' : 'یافت نشد');
  if (has) {
    await box.fill('فولاد');
    await page.keyboard.press('Enter');
    await page.waitForTimeout(1800);
    const listed = await page.evaluate(() => (document.body.innerText || '').includes('فولاد'));
    step('افزودنِ نماد واقعاً درِ فهرست می‌نشیند', listed, 'متنِ «فولاد» درِ صفحه دیده شد');
    const rows = await page.evaluate(() => document.querySelectorAll('[data-testid^="watch-row"]').length);
    step('ردیفِ دیدهبان ساخته شد', rows > 0, `${rows} ردیف`);
  }
  await ctx.close();
}

const ALL = [s_cold_open, s_row_click, s_filters, s_sort, s_scroll, s_history, s_tabs, s_keyboard, s_forms];
const chosen = ONLY.length ? ALL.filter((f) => ONLY.includes(f.name.replace(/^s_/, '').replace(/_/g, '-'))) : ALL;

const browser = await chromium.launch({ executablePath: EXE, args: ['--force-device-scale-factor=1'] });
for (const f of chosen) {
  try {
    await f(browser);
  } catch (e) {
    scenarios.push({ id: f.name.replace(/^s_/, ''), title: 'خطایِ خودِ سنجش', steps: [{ what: 'اجرایِ سناریو', pass: false, evidence: String(e).slice(0, 200) }] });
  }
  const last = scenarios[scenarios.length - 1];
  const bad = last.steps.filter((x) => !x.pass);
  console.log(`${bad.length ? '✗' : '✓'} ${last.id.padEnd(12)} ${bad.length}/${last.steps.length} قرمز${bad.length ? ' → ' + bad.map((b) => b.what).join('؛ ') : ''}`);
}
await browser.close();

const flat = scenarios.flatMap((s) => s.steps);
const result = {
  base: BASE, buildLabel: LABEL, bundle: bundleLabel, viewport: VIEWPORT, browser: EXE, generatedAt: new Date().toISOString(),
  totals: { scenarios: scenarios.length, steps: flat.length, failed: flat.filter((x) => !x.pass).length },
  scenarios,
};
fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(result, null, 1));
console.log(`\nسناریو=${result.totals.scenarios} گام=${result.totals.steps} قرمز=${result.totals.failed} → ${OUT}`);
process.exit(result.totals.failed ? 1 : 0);
