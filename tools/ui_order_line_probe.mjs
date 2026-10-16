// tools/ui_order_line_probe.mjs -- سنجشِ زندۀِ سرخطیِ چندنمادی رویِ بیلدِ مرورگر
//
// بندِ ۱.۵ مأموریتِ System 2: «حداقلِ مواردِ زیر را تست کن» -- دوازدهِ سناریو،
// شماره‌گذاری‌شده همان‌طور که درِ دستورِ مالک آمده، رویِ `frontend/dist` باِ
// `uvicorn app:app` وِ آداپتورِ mock. سطحِ هرِ گام درِ خودِ گام نوشته می‌شود:
//   UI/mock-backend      -- کلیکِ واقعی درِ مرورگر، بک‌اندِ آزمایشی
//   backend-probe        -- درخواستِ مستقیم بهِ خودِ سرویس (بی‌رابط)
// اتصالِ واقعی درِ اینِ فایل آزموده نمی‌شود وِ هیچِ گامی ادعایِ آنِ سطح را ندارد.
//
// قفلِ ایمنیِ سنجش: پیش ازِ اولینِ نوشتار، `GET /api/execution/status` خوانده
// می‌شود؛ اگرِ `dry_run` درستِ true، `live_enabled` درستِ false وِ
// `nothing_will_leave_the_machine` درستِ true نباشد، سنجش پیش ازِ هرِ اثرِ جانبی
// می‌ایستد. «تست نمی‌فرستد» بهِ ادبِ برنامه‌نویس واگذار نشده.
//
// اجرا:  node tools/ui_order_line_probe.mjs --base=http://127.0.0.1:8012 \
//          --out=_audit/ui2/order-line-probe.json
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.join(HERE, '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));

const args = Object.fromEntries(process.argv.slice(2).map((a) => {
  const m = /^--([^=]+)=(.*)$/.exec(a);
  return m ? [m[1], m[2]] : [a.replace(/^--/, ''), true];
}));
const BASE = args.base || 'http://127.0.0.1:8012';
const OUT = args.out || path.join('_audit', 'ui2', 'order-line-probe.json');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const AUTH = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
const USER = (AUTH.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
const PASS = (AUTH.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];

const PAGE = '[data-testid="order-line-page"]';
const steps = [];
const step = (no, name, pass, evidence, level = 'UI/mock-backend') => {
  steps.push({ no, name, pass: !!pass, evidence: String(evidence).slice(0, 300), level });
  console.log(`${pass ? '✓' : '✗'} [${no}] ${name} — ${String(evidence).slice(0, 130)}`);
};

const browser = await chromium.launch({ executablePath: EXE, args: ['--force-device-scale-factor=1'] });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 }, locale: 'fa-IR', deviceScaleFactor: 1 });
const page = await ctx.newPage();
const errs = [];
const thrown = [];
const posts = [];
// دوِ دسته جدا: `pageerror` یعنی کدِ رابط استثنا داد (هرگز مجاز)، ولیِ
// `console error`ِ شبکه شاملِ خطاهایِ عمدیِ همینِ سنجش هم می‌شود (route.abort وِ
// HTMLِ تزریق‌شده درِ بندِ ۷) -- پسِ آنِ دوم فهرست می‌شود وِ فقطِ بیرونِ آنِ
// مجموعه قرمز شمرده می‌شود.
const INJECTED = ['ERR_TIMED_OUT', 'Failed to load resource'];
page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 140)); });
page.on('pageerror', (e) => thrown.push(String(e).slice(0, 140)));
page.on('request', (r) => {
  if (r.method() === 'POST' && r.url().includes('/api/execution/')) {
    let body = {};
    try { body = JSON.parse(r.postData() || '{}'); } catch { /* بی‌بدنه */ }
    posts.push({ p: new URL(r.url()).pathname, id: String(body.execution_id ?? ''),
                 mock: body.mock_instrument === true, confirmed: body.confirmed === true, t: Date.now() });
  }
});
const nDispatch = () => posts.filter((p) => p.p.endsWith('/dispatch')).length;
const dispatchPosts = () => posts.filter((p) => p.p.endsWith('/dispatch'));
const nReconcile = () => posts.filter((p) => p.p.includes('/reconcile/')).length;

// ── قفلِ ایمنی + شناختِ قرارداد ازِ خودِ سرویس (بندِ ۱.۱) ─────────────────────
const res0 = await fetch(`${BASE}/api/execution/status`);
const st = await res0.json();
const safeToSend = st.dry_run === true && st.live_enabled === false && st.nothing_will_leave_the_machine === true;
step('۰', 'سرویسِ اجرا درِ حالتِ بدلِ قفل است (بی‌این هیچِ نوشتاری آزموده نمی‌شود)', safeToSend,
  `http=${res0.status} ctype=${res0.headers.get('content-type')} adapter=${st.adapter} dry_run=${st.dry_run} `
  + `live_enabled=${st.live_enabled} nothing_will_leave_the_machine=${st.nothing_will_leave_the_machine} `
  + `blocked_on=${(st.blocked_on || []).join('|')}`, 'backend-probe');
if (!safeToSend) {
  step('۰', 'توقفِ ایمنی: سرویس آمادهٔ آزمودنِ نوشتار نیست', false, 'dry_run/live_enabled مطابقِ انتظار نبود', 'backend-probe');
  await browser.close();
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify({ base: BASE, steps, consoleErrors: errs }, null, 2), 'utf8');
  process.exit(1);
}

await page.goto(`${BASE}/#/order-line`, { waitUntil: 'domcontentloaded' });
if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
  await page.locator('input[type="text"]').first().fill(USER);
  await page.locator('input[type="password"]').first().fill(PASS);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(1200);
}
await page.waitForSelector(`${PAGE} [data-testid="order-add-tab"]`, { timeout: 15000 });
await waitForGate();

async function waitForGate() {
  await page.waitForFunction(() => {
    const el = document.querySelector('[data-testid="order-line-adapter"]');
    return !!el && !/—/.test(el.textContent || '') && !/در حالِ خواندن/.test(document.body.textContent || '');
  }, { timeout: 10000 }).catch(() => {});
}
const roleTabs = () => page.$$eval(`${PAGE} [role="tab"]`, (els) => els.map((e) => e.textContent.replace(/\s+/g, ' ').trim()));
const tabIdOf = async (n) => (await page.$$eval(`${PAGE} [data-testid^="order-tab-"]`,
  (els) => els.map((e) => e.getAttribute('data-testid').replace('order-tab-', ''))))[n];

// ── ۱) سه تب باِ سه نمادِ متفاوت ─────────────────────────────────────────────
for (let i = 0; i < 3; i += 1) {
  await page.click(`${PAGE} [data-testid="order-add-tab"]`);
  await page.waitForTimeout(140);
}
const ids = [await tabIdOf(0), await tabIdOf(1), await tabIdOf(2)];
const panels = await page.$$eval(`${PAGE} [role="tab"]`, (els) => els.map((e) => e.getAttribute('aria-controls')));
step('۱', 'سه تب ساخته شد؛ هرِ تب triggerِ نقش‌دار باِ پنلِ aria-controlsِ خودش', ids.length === 3 && new Set(panels).size === 3,
  `tabs=${ids.length} panels=${new Set(panels).size}`);

const SYMBOLS = [['فولاد', '5170', '50'], ['خودرو', '312', '900'], ['شپنا', '1040', '100']];
for (let i = 0; i < 3; i += 1) {
  await page.click(`${PAGE} [data-testid="order-tab-${ids[i]}"]`);
  await page.waitForTimeout(120);
  await page.fill(`${PAGE} [data-testid="order-symbol-${ids[i]}"]`, SYMBOLS[i][0]);
  await page.fill(`${PAGE} [data-testid="order-price-${ids[i]}"]`, SYMBOLS[i][1]);
  await page.fill(`${PAGE} [data-testid="order-qty-${ids[i]}"]`, SYMBOLS[i][2]);
  // تیکِ صریحِ «شناسۀِ بدلِ کارگزاری» -- همانِ چیزی که درِ §۱-ج قرارداد، نگاشتِ
  // کارگزاری را می‌سازد. بی‌آن preflight باِ NOT_ORDERABLE می‌ایستد.
  if (await page.$(`${PAGE} [data-testid="order-mockswitch-${ids[i]}"] input`)) {
    await page.check(`${PAGE} [data-testid="order-mockswitch-${ids[i]}"] input`);
  }
  await page.waitForTimeout(120);
}
const heads = await roleTabs();
step('۲', 'تغییرِ نماد درِ یکِ تب، دو تبِ دیگر را عوض نمی‌کند (سه سرِ متفاوت)',
  ['فولاد', 'خودرو', 'شپنا'].every((s) => heads.some((h) => h.includes(s))), heads.join(' | '));

// ورودی‌های هرِ تب پس ازِ جابه‌جایی برمی‌گردند
await page.click(`${PAGE} [data-testid="order-tab-${ids[2]}"]`);
await page.click(`${PAGE} [data-testid="order-tab-${ids[0]}"]`);
await page.waitForTimeout(200);
const kept = await page.inputValue(`${PAGE} [data-testid="order-qty-${ids[0]}"]`);
await page.click(`${PAGE} [data-testid="order-tab-${ids[1]}"]`);
await page.waitForTimeout(200);
const kept1 = await page.inputValue(`${PAGE} [data-testid="order-symbol-${ids[1]}"]`);
step('۳', 'جابه‌جاییِ بینِ تب‌ها ورودیِ هرِ تب را نگه می‌دارد (هیچِ فیلدی جابه‌جا نمی‌شود)',
  kept === '50' && kept1 === 'خودرو', `تبِ اول تعداد=${kept} · تبِ دوم نماد=${kept1}`);

const execIds = [];
for (const id of ids) {
  await page.click(`${PAGE} [data-testid="order-tab-${id}"]`);
  await page.waitForTimeout(120);
  execIds.push((await page.textContent(`${PAGE} [data-testid="order-execid-${id}"]`)).replace('شناسه:', '').trim());
}
step('۳-ب', 'هرِ تب شناسۀِ اجرایِ جدا دارد (کلیدِ idempotency درِ هرِ تب جداست)',
  new Set(execIds).size === 3 && execIds.every((x) => /^x-/.test(x)), execIds.join(' · '));

// ── ۵) اعتبارسنجیِ قیمت/تعداد/نماد -- ازِ خودِ سرویس ──────────────────────────
await page.click(`${PAGE} [data-testid="order-tab-${ids[0]}"]`);
await page.click(`${PAGE} [data-testid="order-preflight-${ids[0]}"]`);
await page.waitForSelector(`${PAGE} [data-testid="order-checks-${ids[0]}"]`, { timeout: 8000 });
const c0 = await page.$$eval(`${PAGE} [data-testid="order-checks-${ids[0]}"] li`, (els) =>
  els.map((e) => e.textContent.replace(/\s+/g, ' ').trim()));
const goodInstrument = (c0.find((l) => /instrument/.test(l)) || '').startsWith('قبول');
step('۵', 'اعتبارسنجی، `checks` خودِ سرویس را می‌آورد (نماد باِ ISIN: instrument قبول)',
  c0.length >= 8 && goodInstrument, c0.slice(0, 4).join(' / '));

await page.click(`${PAGE} [data-testid="order-tab-${ids[2]}"]`);
await page.click(`${PAGE} [data-testid="order-preflight-${ids[2]}"]`);
await page.waitForSelector(`${PAGE} [data-testid="order-checks-${ids[2]}"]`, { timeout: 8000 });
const c2 = await page.$$eval(`${PAGE} [data-testid="order-checks-${ids[2]}"] li`, (els) =>
  els.map((e) => e.textContent.replace(/\s+/g, ' ').trim()));
const badInstrument = c2.find((l) => /instrument/.test(l)) || '';
step('۵-ب', 'نمادی که ISIN درِ بانکِ محلی ندارد رد می‌شود وِ رابط نگاشت اختراع نمی‌کند',
  badInstrument.startsWith('رد') && /NOT_ORDERABLE/.test(badInstrument), badInstrument);

// ── ۶) ارسالِ مستقلِ یکِ تب (مسیرِ کامل: record ازِ پاسخِ سرویس) ───────────────
const beforeA = nDispatch();
await page.click(`${PAGE} [data-testid="order-tab-${ids[0]}"]`);
await page.click(`${PAGE} [data-testid="order-dispatch-${ids[0]}"]`);
await page.waitForFunction((id) => {
  const el = document.querySelector(`[data-testid="order-result-${id}"]`);
  return !!el && /record/.test(el.textContent || '');
}, ids[0], { timeout: 8000 }).catch(() => {});
const resA = await page.textContent(`${PAGE} [data-testid="order-result-${ids[0]}"]`);
step('۶', 'ارسالِ یکِ تب دقیقاً یکِ درخواستِ dispatch می‌فرستد', nDispatch() - beforeA === 1,
  `${nDispatch() - beforeA} درخواست · otherTabs=${nDispatch()}`);
step('۶-ب', 'نتیجهٔ همانِ تب ازِ پاسخِ سرویس خوانده می‌شود (record/status/broker_order_id درِ صورتِ ارائه)',
  /"status":/.test(resA) && /execution_id/.test(resA), resA.replace(/\s+/g, ' ').slice(0, 200));
const headsAfterSend = await roleTabs();
const headSent = headsAfterSend.find((h) => h.includes('فولاد')) || '';
const headIdle = headsAfterSend.find((h) => h.includes('خودرو')) || '';
step('۶-پ', 'وضعیتِ هرِ تب درِ سرِ تب جداست: ارسالِ یکِ تب، تبِ بی‌کار را «فرستاده‌شده» نمی‌کند',
  !/بی‌سفارش|پیش‌نویس|ردشده/.test(headSent) && /بی‌سفارش|پیش‌نویس/.test(headIdle),
  `فولاد: ${headSent} || خودرو: ${headIdle}`);
step('۷-ب', 'هرِ نوشتار باِ `confirmed: true` ازِ رابط می‌رود (رأیِ صریحِ کاربر؛ دروازہ درِ mode=safe آن را الزام نمی‌کند — فیکسچر)',
  dispatchPosts().length > 0 && dispatchPosts().every((p) => p.confirmed),
  `${dispatchPosts().length} dispatch، همه باِ confirmed:true`);
step('۷-پ', '`mock_instrument` فقط باِ تیکِ همانِ تب درِ بدنه می‌نشیند',
  dispatchPosts().every((p) => p.mock), `همۀِ dispatchهایِ آزموده: mock=${dispatchPosts().map((p) => p.mock).join(',')}`);

// ── ۹) کلیکِ سریعِ سه‌باره رویِ یکِ تب ────────────────────────────────────────
await page.click(`${PAGE} [data-testid="order-tab-${ids[1]}"]`);
await page.waitForTimeout(200);
const beforeDbl = nDispatch();
// «کلیکِ سریع» همانِ چیزی است که درِ دستِ کاربر می‌افتد: سه رویداد درِ یکِ تسک،
// پیش ازِ آنکه React بتواند دکمه را disabled کند. قفلِ `beginSend` باید همین را
// بشکند؛ اگرِ سه کلیک را باِ فاصله بزنیم، دیگرِ «هم‌زمان» نیست وِ مسائرۀِ دوم
// وظیفۀِ خودِ ردِّپاست (بندِ ۹-د).
const clicked3 = await page.evaluate((sel) => {
  const el = document.querySelector(`[data-testid="${sel}"]`);
  if (!el) return false;
  el.click(); el.click(); el.click();
  return true;
}, `order-dispatch-${ids[1]}`);
await page.waitForTimeout(2000);
step('۹', 'سهِ کلیکِ همِ‌زمان (یکِ تسک) رویِ یکِ تب، یکِ درخواست می‌سازد (قفلِ درِ state)',
  clicked3 && nDispatch() - beforeDbl === 1,
  `${nDispatch() - beforeDbl} درخواست ازِ ۳ کلیکِ همِ‌زمان · کلِ dispatch=${dispatchPosts().length}`);

const beforeSeq = nDispatch();
await page.click(`${PAGE} [data-testid="order-dispatch-${ids[1]}"]`);
await page.waitForTimeout(1500);
const seqRes = (await page.textContent(`${PAGE} [data-testid="order-result-${ids[1]}"]`)) || '';
const seqId = ((await page.textContent(`${PAGE} [data-testid="order-execid-${ids[1]}"]`)) || '').replace('شناسه:', '').trim();
const seqRows = (await (await fetch(`${BASE}/api/execution/ledger`)).json()).records
  .filter((r) => r.execution_id === seqId).length;
step('۹-د', 'کلیکِ دوم پسِ رسیدنِ پاسخ، سفارشِ تازه نمی‌سازد: سرویس duplicate رد می‌کند وِ ردِّپا یکِ سطر می‌ماند',
  nDispatch() - beforeSeq === 1 && /DUPLICATE_GUARD/.test(seqRes) && seqRows <= 1,
  `درخواستِ دوم=${nDispatch() - beforeSeq} · کد=${/DUPLICATE_GUARD/.test(seqRes) ? 'DUPLICATE_GUARD' : '—'} · سطرهایِ همانِ شناسه=${seqRows}`);

// ── ۸) ردِ یکِ سفارش درِ کنارِ وضعیتِ متفاوتِ دیگری ───────────────────────────
await page.click(`${PAGE} [data-testid="order-tab-${ids[2]}"]`);
await page.click(`${PAGE} [data-testid="order-dispatch-${ids[2]}"]`);
await page.waitForFunction((id) => {
  const el = document.querySelector(`[data-testid="order-result-${id}"]`);
  const n = document.querySelector(`[data-testid="order-note-${id}"]`);
  return !!el || !!n;
}, ids[2], { timeout: 8000 }).catch(() => {});
const tabHeads8 = await roleTabs();
const refTab = tabHeads8.find((h) => h.includes('شپنا')) || '';
const okTab = tabHeads8.find((h) => h.includes('فولاد')) || '';
step('۸', 'ردِ «شپنا» وضعیتِ «فولاد» را دست‌نخورده می‌گذارد (دوِ واژگانِ متفاوت درِ دوِ تب)',
  /رد|نامعلوم/.test(refTab) && !/رد/.test(okTab), `شپنا: ${refTab} || فولاد: ${okTab}`);

// ── ۷) timeout / HTML / پاسخِ بی‌قرارداد -- درِ سطحِ UI باِ تزریقِ خطا ─────────
const idT = ids[1];
await page.click(`${PAGE} [data-testid="order-tab-${idT}"]`);
await page.waitForTimeout(150);
const execT = ((await page.textContent(`${PAGE} [data-testid="order-execid-${idT}"]`)) || '')
  .replace('شناسه:', '').trim();
await page.route('**/api/execution/dispatch', async (route) => {
  let b = {};
  try { b = JSON.parse(route.request().postData() || '{}'); } catch { /* بی‌بدنه */ }
  if (b.execution_id === execT) { await route.abort('timedout'); return; }
  await route.continue();
});
await page.click(`${PAGE} [data-testid="order-dispatch-${idT}"]`);
await page.waitForSelector(`${PAGE} [data-testid="order-note-${idT}"]`, { timeout: 8000 }).catch(() => {});
const noteT = (await page.textContent(`${PAGE} [data-testid="order-note-${idT}"]`)) || '';
const phaseT = (await roleTabs()).find((h) => h.includes('خودرو')) || '';
step('۷', 'قطعِ ارتباط «رد» نیست: «نتیجهٔ نامعلوم» باِ همانِ شناسه وِ دکمۀِ مطابقت ظاهر می‌شود',
  /نامعلوم/.test(noteT + phaseT) && await page.$$(`${PAGE} [data-testid="order-reconcile-${idT}"]`).then((e) => e.length > 0),
  `${phaseT} :: ${noteT.slice(0, 120)}`);
await page.unroute('**/api/execution/dispatch');

await page.route('**/api/execution/dispatch', async (route) => {
  await route.fulfill({ status: 200, contentType: 'text/html', body: '<!doctype html><html>fallback</html>' });
});
const beforeHtml = nDispatch();
await page.click(`${PAGE} [data-testid="order-tab-${idT}"]`);
await page.click(`${PAGE} [data-testid="order-dispatch-${idT}"]`);
await page.waitForTimeout(1200);
const afterHtml = nDispatch();
step('۷-ت', 'HTML به‌جایِ JSON (fallbackِ SPA) بهِ «موفق» ترجمه نمی‌شود وِ بی‌retry نمی‌ماند رویِ ادعا',
  afterHtml - beforeHtml <= 1 && /نامعلوم|نرسید/.test((await page.textContent(`${PAGE} [data-testid="order-note-${idT}"]`)) || ''),
  `درخواست‌هایِ افزوده=${afterHtml - beforeHtml} یادداشت=${((await page.textContent(`${PAGE} [data-testid="order-note-${idT}"]`)) || '').slice(0, 90)}`);
await page.unroute('**/api/execution/dispatch');

// retry کنترل‌شده: مطابقت باِ همانِ شناسه، بی‌dispatchِ تازه
const beforeRec = nDispatch();
const beforeRecN = nReconcile();
await page.click(`${PAGE} [data-testid="order-reconcile-${idT}"]`).catch(() => {});
await page.waitForTimeout(1400);
const recPath = posts.slice(-1)[0]?.p ?? '';
step('۹-ب', 'پسِ خطا، «مطابقتِ نتیجه» باِ همانِ شناسه می‌رود وِ dispatchِ تازه نمی‌سازد',
  nDispatch() - beforeRec === 0 && nReconcile() - beforeRecN === 1 && recPath.endsWith(`/reconcile/${execT}`),
  `dispatchِ تازه=${nDispatch() - beforeRec} reconcile=${nReconcile() - beforeRecN} مسیر=${recPath}`);

// ── ۶-پ/۸) ارسالِ گروهی باِ مرور ──────────────────────────────────────────────
await page.click(`${PAGE} [data-testid="order-batch-review"]`);
await page.waitForSelector(`${PAGE} [data-testid="order-batch-review-list"]`, { timeout: 5000 });
const review = (await page.textContent(`${PAGE} [data-testid="order-batch-review-list"]`)) || '';
step('۸-ب', 'ارسالِ گروهی پیش ازِ هرچیز «مرور» می‌خواهد: نماد/قیمت/تعداد/شناسه درِ یکِ چک‌لیست',
  /فولاد/.test(review) && /خودرو/.test(review) && /شپنا|نمی‌نشیند/.test(review) && /x-/.test(review),
  review.replace(/\s+/g, ' ').slice(0, 220));
const beforeBatch = nDispatch();
await page.click(`${PAGE} [data-testid="order-batch-send"]`);
await page.waitForTimeout(3000);
const batchPosts = dispatchPosts().slice(beforeBatch);
step('۶-گ', 'گروهی = چندِ درخواستِ مستقل باِ شناسه‌هایِ متفاوت (بی‌endpointِ گروهیِ ساختگی)',
  batchPosts.length >= 1 && new Set(batchPosts.map((p) => p.id)).size === batchPosts.length,
  `${batchPosts.length} درخواست: ${batchPosts.map((p) => p.id).join(' ')}`);

// ── ۱۰) refresh -- بی‌اجرایِ دوباره ──────────────────────────────────────────
const beforeReload = posts.length;
await page.reload({ waitUntil: 'domcontentloaded' });
await page.waitForSelector(`${PAGE} [data-testid="order-add-tab"]`, { timeout: 15000 });
await page.waitForTimeout(2000);
const writesAfterReload = posts.slice(beforeReload).filter((p) => p.p.endsWith('/dispatch') || p.p.endsWith('/prepare'));
const restored = await roleTabs();
step('۱۰', 'بازخوانیِ صفحه هیچِ سفارشی را دوباره اجرا نمی‌کند (صفرِ نوشتار)',
  writesAfterReload.length === 0, `${writesAfterReload.length} نوشتار پسِ reload · ${posts.slice(beforeReload).length} درخواستِ دیگر`);
step('۱۰-ب', 'پیش‌نویس‌ها ازِ همینِ دستگاه بازیابی می‌شوند وِ حالتِ «در حالِ ارسال» پایین می‌آید',
  restored.join(' ').includes('فولاد') && !/در حالِ ارسال/.test(restored.join(' ')), restored.join(' | '));

// ── ۴) بستنِ تب ──────────────────────────────────────────────────────────────
await page.click(`${PAGE} [data-testid="order-tab-${ids[2]}"]`);
await page.waitForTimeout(150);
await page.click(`${PAGE} [data-testid="order-close-${ids[2]}"]`);
await page.waitForTimeout(400);
const leftTabs = await roleTabs();
await page.click(`${PAGE} [data-testid="order-tab-${ids[1]}"]`);
await page.waitForTimeout(200);
const keptQty = await page.inputValue(`${PAGE} [data-testid="order-qty-${ids[1]}"]`);
step('۴', 'بستنِ یکِ تب، ورودیِ تب‌هایِ دیگر را خراب نمی‌کند', leftTabs.length === 2 && keptQty === '900',
  `تبها=${leftTabs.length} · تعدادِ تبِ دوم=${keptQty}`);

// ── ۱۱) عرض‌هایِ مختلفِ صفحه ─────────────────────────────────────────────────
const fa = (n) => String(n).replace(/\d/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[Number(d)]);
for (const [w, h] of [[1366, 768], [1024, 768], [430, 932], [390, 844], [360, 640]]) {
  await page.setViewportSize({ width: w, height: h });
  await page.waitForTimeout(600);
  const m = await page.evaluate(() => {
    const root = document.querySelector('[data-testid="order-line-page"]');
    const clipped = Array.from(root.querySelectorAll('*'))
      .filter((e) => e.children.length === 0 && (e.textContent || '').trim().length > 1
        && e.scrollWidth > e.clientWidth + 2)
      .slice(0, 3).map((e) => `${e.tagName}:${(e.textContent || '').trim().slice(0, 16)}`);
    return {
      docOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      clipped,
      rows: new Set(Array.from(document.querySelectorAll('[data-testid="order-line-page"] [role="tab"]'))
        .map((e) => Math.round(e.getBoundingClientRect().top))).size,
    };
  });
  step('۱۱', `درِ ${fa(w)}×${fa(h)} سرریزِ افقیِ سند صفر است وِ تب‌ها می‌شکنند`, m.docOverflow <= 0,
    `docOverflow=${fa(m.docOverflow)}px · سطرِ تب=${fa(m.rows)} · بریدگی=[${m.clipped.join('/')}]`);
}

// ── ۱.۴ زمان‌بندی: پنجِ نمونه باِ یکِ ساعت (گزارش، نه گیت) ───────────────────
const timing = await page.evaluate(async () => {
  const rows = [];
  for (let i = 0; i < 5; i += 1) {
    const t0 = performance.now();
    const r = await fetch('/api/execution/preflight', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ execution_id: `probe-t-${Date.now()}-${i}`, symbol: 'فولاد', side: 'buy',
                             mode: 'safe', price: 5170, quantity: 50, confirmed: false, mock_instrument: true }),
    });
    const j = await r.json();
    rows.push({ client_ms: Math.round(performance.now() - t0), svc: j.timings ?? null, ok: j.ok });
  }
  return rows;
});
const clientMs = timing.map((t) => t.client_ms).sort((a, b) => a - b);
step('۱.۴', 'زمانِ پیش‌فرود ازِ مرورگر (۵ نمونه، یکِ ساعت) -- گزارشِ بی‌آستانه', timing.length === 5,
  `client ms min/med/max = ${clientMs[0]}/${clientMs[2]}/${clientMs[4]} · درِ پاسخِ preflight کلیدِ `
  + `timings نیست (svc=${JSON.stringify(timing[0].svc)}) · ok=${timing.map((t) => t.ok).join(',')}`,
  'UI/mock-backend');

// بندِ ۱.۴: ساعتِ دوم رویِ مسیرِ ارسال، بی‌رابط. `dispatch_ms` ازِ
// `time.monotonic()` خودِ دروازہ است وِ `client_ms` ازِ performance.now همینِ
// پروسه (همانِ ماشین، loopback) -- دوِ ساعتِ مستقل، پسِ «تأخیرِ بیرونِ دروازہ»
// ازِ تفاضلشان خوانده می‌شود نه ازِ ادعایِ رابط. `response_ms`
// وِ `observed_ms` درِ dry-run عمداً null‌اند: چیزی بهِ کارگزاری نرفته تاِ RTT یا
// رتبۀِ صف اندازه گرفته شود؛ هرِ عددی که اینجا «سرعتِ ارسالِ سفارش» جا بزند،
// ساختگی است.
const sendTiming = [];
for (let i = 0; i < 5; i += 1) {
  const id = `x-t${Date.now().toString(36)}-${i}`;
  const t0 = performance.now();
  const r = await (await fetch(`${BASE}/api/execution/dispatch`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ execution_id: id, symbol: 'فولاد', side: 'buy', mode: 'safe',
                           price: 5170, quantity: 50, confirmed: true, mock_instrument: true }),
  })).json();
  sendTiming.push({ client_ms: Math.round(performance.now() - t0), svc: r.timings ?? null,
                    status: r.status, kill: r.kill_switch ?? null });
}
const sMs = sendTiming.map((t) => t.client_ms).sort((a, b) => a - b);
const svcMs = sendTiming.map((t) => t.svc?.dispatch_ms ?? 0).sort((a, b) => a - b);
step('۱.۴-ب', 'زمانِ مسیرِ ارسال: دوِ ساعتِ مستقل (ساعتِ پروسه وِ monotonicِ دروازہ) باِ نتیجهٔ acceptance',
  sendTiming.length === 5 && sendTiming.every((t) => t.status === 'success'),
  `client ms min/med/max = ${sMs[0]}/${sMs[2]}/${sMs[4]} · dispatch_msِ سرویس = ${svcMs[0]}/${svcMs[2]}/${svcMs[4]} `
  + `· kill_switch=${sendTiming[0].kill} · response_ms=${sendTiming[0].svc?.response_ms} `
  + `(بی‌ارسالِ واقعی: RTT وِ رتبۀِ صف اندازه‌گرفته نمی‌شوند)`, 'backend-probe');

// ── شاهدِ بک‌اند: ردِّپا -- هرِ execution_id یکِ سطر، وِ تکرارِ همانِ شناسه رد ──
const led = await (await fetch(`${BASE}/api/execution/ledger`)).json();
const idsLed = (led.records || []).map((r) => r.execution_id);
const dupInLedger = idsLed.length - new Set(idsLed).size;
const eidRepeat = idsLed[0];
let repeatRefused = null;
if (eidRepeat) {
  const rr = await fetch(`${BASE}/api/execution/dispatch`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ execution_id: eidRepeat, symbol: 'فولاد', side: 'buy', mode: 'safe',
                           price: 5170, quantity: 50, confirmed: true, mock_instrument: true }),
  });
  const rj = await rr.json().catch(() => null);
  repeatRefused = { http: rr.status, ctype: rr.headers.get('content-type'), status: rj?.status,
                    code: rj?.code, dup_check: rj?.checks?.duplicate ?? null };
}
// قلمروِ اینِ گام «همینِ پروسه» است: ردِّپایِ dry-run پسِ restartِ پروسه
// برنمی‌گردد (open_ids فقطِ حالت‌هایِ نبسته را می‌شمارد) -- آنِ رفتارِ جدا درِ
// `_audit/ui2/order-line-tired.json` وِ `test_execution_recovery.py` ثبت شده.
step('۹-پ', 'درِ یکِ نشستِ پروسه، هرِ شناسه یکِ سطرِ ردِّپا دارد (بی‌سطرِ دوتایی ازِ کلیک/تکرار)',
  dupInLedger === 0, `سطرها=${idsLed.length} منحصربه‌فرد=${new Set(idsLed).size}`);
step('۱۰-پ', 'تکرارِ همانِ execution_id ازِ خودِ سرویس رد می‌شود (check=duplicate، بی‌سفارشِ تازه)',
  repeatRefused && (repeatRefused.status === 'error' || repeatRefused.dup_check === 'FAIL'),
  JSON.stringify(repeatRefused));

const unexpected = errs.filter((e) => !INJECTED.some((t) => e.includes(t)));
step('۱۲', 'بی‌استثنایِ بی‌گرفته (pageerror) درِ کلِ سناریو', thrown.length === 0,
  thrown.slice(0, 2).join(' | ') || 'هیچ', 'UI/mock-backend');
step('۱۲-ب', 'خطایِ کنسول فقطِ مالِ دوِ نقصِ تزریق‌شدۀِ بندِ ۷ است (بی‌خطایِ تازه)',
  unexpected.length === 0,
  `کلِ کنسول=${errs.length} · بیرونِ تزریق=[${unexpected.slice(0, 2).join(' | ')}]`, 'UI/mock-backend');

await page.setViewportSize({ width: 1366, height: 768 });
await page.waitForTimeout(300);
fs.mkdirSync(path.join(REPO, '_audit', 'ui2'), { recursive: true });
await page.screenshot({ path: path.join('_audit', 'ui2', 'order-line-1366.png'), fullPage: false });
await page.setViewportSize({ width: 390, height: 844 });
await page.waitForTimeout(400);
await page.screenshot({ path: path.join('_audit', 'ui2', 'order-line-390.png'), fullPage: false });

const red = steps.filter((s) => !s.pass).length;
fs.writeFileSync(OUT, JSON.stringify({
  base: BASE, generatedAt: new Date().toISOString(),
  level: 'UI test on mock/dry-run backend + direct backend probes (NO live broker connection tested)',
  status: st, steps, consoleErrors: errs, pageErrors: thrown, posts, timing, sendTiming, ledger: { rows: idsLed.length, ids: idsLed },
}, null, 2), 'utf8');
console.log(`\nگام=${steps.length} قرمز=${red} نوشتار=/api/execution/*=${posts.length} → ${OUT}`);
await browser.close();
process.exit(red ? 1 : 0);
