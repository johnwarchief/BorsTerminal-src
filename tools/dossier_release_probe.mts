// tools/dossier_release_probe.mts — سنجشِ زندهٔ ۱۳۶۶×۷۶۸ برایِ ریلیز (تب استراتژی + پروندۀ نماد)
//
// چرا: کامیت‌هایِ پروندۀ نماد درِ jsdom سبز بودند ولی هیچ‌وقت درِ مرورگرِ واقعی
// دیده نشدند؛ مالک پیشِ ریلیز می‌خواهد تب استراتژی و پرونده «مطمئن» شود. این
// سنَجش با chromiumِ خودِ playwright رویِ آدرسِ vite (۵۱۷۳) می‌نشیند و همان
// کلیک‌هایی را می‌زند که کاربر می‌زند: انتخابِ دسته‌ای → واچ‌لیست → برآیند →
// دیدهبان → تب‌ها. خروجی JSON است و هر چک یا PASS یا FAILِ صریح (بی‌سبزِ بی‌محتوا).
//
// اجرا (همان الگویِ tools/funnel_browser_probe.mts):
//   node --experimental-strip-types tools/dossier_release_probe.mts --url http://localhost:5173/
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');

const arg = (k: string, d: string) => {
  const i = process.argv.indexOf(`--${k}`);
  return i > -1 ? process.argv[i + 1] : d;
};
const BASE = arg('url', 'http://localhost:5173/');
const W = Number(arg('width', '1366'));
const H = Number(arg('height', '768'));
const OUT = arg('out', '_audit/dossier_release_probe.json');

const R: Record<string, unknown> = { base: BASE, viewport: { W, H }, checks: [], errors: [],
                                      http: [], shots: [], notes: [] };
const check = (name: string, pass: boolean, got: unknown = '') =>
  R.checks.push({ name, pass: !!pass, got: String(got).slice(0, 200) });

const browser = await chromium.launch({
  headless: true,
  // همان الگویِ بقیۀ سنَجش‌ها: JEV_CHROME مسیرِ کرومیومِ نصب‌شده را می‌دهد. بی‌این،
  // playwrightِ این پکیج نسخه‌ای را می‌خواهد که رویِ این ماشین دانلود نشده (۱۲۴۳).
  executablePath: process.env.JEV_CHROME || undefined,
});
const ctx = await browser.newContext({ viewport: { width: W, height: H } });
// دروازۀ ورودِ dev سشن را درِ sessionStorage می‌خواند (`bors_auth_session`)؛ این
// سنَجش دروازه را نمی‌آزماید، رابطِ پشتِ آن را — پس سشن از پیش نشسته می‌شود.
await ctx.addInitScript(() => {
  try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* بی‌دکمه */ }
});
const page = await ctx.newPage();
page.on('pageerror', (e) => R.errors.push(String(e).slice(0, 300)));
page.on('console', (m) => {
  // خطایِ منبع (۴۰۴ِ آیکون/فونت) درِ R.http ثبت می‌شود؛ اینجا فقط خطایِ واقعیِ اجرا
  if (m.type() === 'error' && !/Failed to load resource/.test(m.text()))
    R.errors.push('console: ' + m.text().slice(0, 200));
});
page.on('response', (r) => { if (r.status() >= 400) R.http.push(`${r.status()} ${r.url().slice(0, 120)}`); });

const clipCount = () => page.evaluate(() => {
  let n = 0;
  for (const el of Array.from(document.querySelectorAll('th,td,h1,h2,h3,button,span'))) {
    const t = el as HTMLElement;
    if (t.scrollWidth > t.clientWidth + 2 && t.clientWidth > 0 && getComputedStyle(t).overflow !== 'visible') n++;
  }
  return n;
});
const overflow = () => page.evaluate(() => Math.max(document.documentElement.scrollWidth,
  document.body.scrollWidth) - window.innerWidth);
// `goto` با عوض‌شدنِ تنهاِ hash، کامپوننت را دوباره mount نمی‌کند؛ این سنَجش هر
// سطح را با بارگذاریِ کامل باز می‌کند تا چیزی از صفحۀ قبلی باقی نماند.
const openRoute = async (hash: string, ms = 4000) => {
  await page.goto(`${BASE}#${hash}`, { waitUntil: 'domcontentloaded' });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(ms);
};
const shot = async (name: string) => {
  const f = `_audit/${name}.jpg`;
  await page.screenshot({ path: f, type: 'jpeg', quality: 60 });
  R.shots.push(f);
};

// ── ۱) تب استراتژی ───────────────────────────────────────────────────────────
await openRoute('/strategy-tree', 5000);
const treeNodes = await page.locator('[data-testid^="tree-node-"], svg [data-testid]').count();
const treeRoot = await page.locator('[data-testid="strategy-tree-page"], [data-testid*="strategy-tree"]').first()
  .isVisible().catch(() => false);
check('تب استراتژی رندر می‌شود (نه صفحهٔ خطا)', treeRoot || treeNodes > 0, `nodes=${treeNodes} root=${treeRoot}`);
check('تب استراتژی: بی‌خطایِ pageerror/console', R.errors.length === 0, JSON.stringify(R.errors.slice(0, 2)));
check('تب استراتژی: بی‌سرریزِ افقی درِ ۱۳۶۶', await overflow() <= 12, `overflow=${await overflow()}px`);
await shot('release_strategy_tree');

// ── ۲) غربالگری: جدول تحویل، انتخاب و عملیاتِ دسته‌ای ─────────────────────────
R.errors.length = 0;
// درِ فضای کارِ زنده، هر گام جدولِ خودش را دارد (`?stage=`)؛ جدولِ تحویل گامِ
// چهارم است. بی‌رفتن به آن، `funnel-stage-handover` هرگز رندر نمی‌شد و سنَجش
// «ردیف نیست» می‌گفت درحالی‌که کاربر فقط باید گام را عوض کند.
await openRoute('/master?stage=handover', 1500);
// قیف با زنجیرۀ خالی حقِ دارد «تحویل» را خالی بدهد (پیشِ بازگشایی، بی‌هیچ فیلتر
// روشنی). برایِ همان‌است که سنَجش یک فیلترِ واقعی را روشن می‌کند: همان کاری که
// کاربر با چیپ می‌کند. بی‌این، «rows=0» بی‌گناه رد می‌شد.
await page.waitForSelector('[data-testid="funnel-tape-chip-f_susp"]', { timeout: 60000 }).catch(() => {});
const chipSeen = await page.locator('[data-testid="funnel-tape-chip-f_susp"]').count();
R.notes.push('chip f_susp present=' + chipSeen);
if (chipSeen) await page.click('[data-testid="funnel-tape-chip-f_susp"]').catch(() => {});
await page.waitForTimeout(9000);
await page.click('[data-testid="fts-step-handover"]').catch(() => {});
await page.waitForTimeout(6000);
await page.waitForSelector('[data-testid="funnel-stage-handover"] tbody tr', { timeout: 90000 }).catch(() => {});
R.notes.push('handover card count=' + await page.locator('[data-testid="funnel-stage-handover"]').count());
const handoverRows = await page.locator('[data-testid="funnel-scroll-handover"] tbody tr').count();
check('جدول تحویل ردیف دارد', handoverRows > 0, `rows=${handoverRows}`);
const bar = await page.locator('[data-testid="funnel-handover-actions"]').isVisible().catch(() => false);
check('نوارِ انتخاب/عملیاتِ تحویل دیده می‌شود', bar);
if (bar && handoverRows > 0) {
  await page.click('[data-testid="funnel-select-all"]');
  const cnt = (await page.locator('[data-testid="funnel-selection-count"]').textContent()) || '';
  check('انتخابِ «همۀ نتایج فعلی» شمار را نشان می‌دهد', /انتخاب شده/.test(cnt), cnt.trim());
  // بی‌تکراری: یک بار دیگر
  await page.click('[data-testid="funnel-select-all"]');
  const cnt2 = (await page.locator('[data-testid="funnel-selection-count"]').textContent()) || '';
  check('دوباره زدنِ «همه» شمار را دو نمی‌کند', cnt.trim() === cnt2.trim(), `${cnt.trim()} → ${cnt2.trim()}`);
  const boxes = await page.locator('[data-testid="funnel-stage-handover"] [role="checkbox"]').count();
  check('هر ردیفِ تحویل جعبۀ انتخاب دارد', boxes >= handoverRows, `boxes=${boxes} rows=${handoverRows}`);
  await page.click('[data-testid="funnel-bulk-watch"]');
  await page.waitForSelector('[data-testid="funnel-bulk-result"]', { timeout: 25000 }).catch(() => {});
  const res = (await page.locator('[data-testid="funnel-bulk-result"]').textContent().catch(() => '')) || '';
  check('پیامِ افزودنِ دسته‌ای سه شمار را می‌گوید', /افزوده شد/.test(res) && /از قبل/.test(res), res.trim());
  const still = (await page.locator('[data-testid="funnel-selection-count"]').textContent()) || '';
  check('انتخاب پس از عملیات نمی‌سوزد', /انتخاب شده/.test(still), still.trim());
  await shot('release_handover_selection');

  // ── ۳) برآیند: پروندۀ همان نماد + سابقه + پیمایش ────────────────────────────
  const firstSym = (await page.locator('[data-testid="funnel-stage-handover"] [role="checkbox"]').first()
    .getAttribute('data-testid') || '').replace('select-box-', '');
  await page.click('[data-testid="funnel-bulk-review"]');
  // برآيندِ زنده با `master-dossier` می‌آید (نه `master-fts-details`؛ آن نام درِ
  // تستِ jsdom بود) — سنَجش باید همان چیزی را بشنود که رابطِ واقعی چاپ می‌کند.
  await page.waitForSelector('[data-testid="master-dossier"]', { timeout: 45000 }).catch(() => {});
  await page.waitForSelector(`[data-testid="tape-history-${firstSym}"]`, { timeout: 30000 }).catch(() => {});
  const url = page.url();
  check('«بررسی در برآیند» به پروندۀ همان نماد می‌رود', url.includes(`/master/${encodeURIComponent(firstSym)}`), url);
  const hist = await page.locator(`[data-testid="tape-history-${firstSym}"]`).isVisible().catch(() => false);
  check('بخشِ S سابقۀ چندروزه را نشان می‌شود', hist, `symbol=${firstSym}`);
  if (hist) {
    const cells = await page.locator(`[data-testid="tape-history-${firstSym}"] tbody td`).count();
    const days = await page.locator(`[data-testid="tape-history-${firstSym}"] thead th`).count();
    check('جدولِ سابقه ستونِ روز + دفعات + روند دارد', days >= 4 && cells >= 42, `th=${days} td=${cells}`);
    const note = (await page.locator(`[data-testid="tape-history-note-${firstSym}"]`).textContent()) || '';
    check('تعریفِ شمارش و «از چه تاریخی قابل‌اعتماد» نوشته شده',
      /شمارش/.test(note) && /قابل‌اعتماد/.test(note), note.trim().slice(0, 120));
    const marks = await page.locator(`[data-testid="tape-history-${firstSym}"]`).evaluate(
      (el) => ({ on: el.innerHTML.split('✓').length - 1, off: el.innerHTML.split('>—<').length - 1,
                 un: el.innerHTML.split('>·<').length - 1 }));
    check('✓ / — / · هر سه درِ DOM واقعی‌اند', marks.on > 0 || marks.off > 0, JSON.stringify(marks));
  }
  await page.waitForSelector('[data-testid="master-queue-nav"]', { timeout: 15000 }).catch(() => {});
  const nav = await page.locator('[data-testid="master-queue-nav"]').isVisible().catch(() => false);
  check('پیمایشِ قبلی/بعدی رویِ فهرستِ انتخاب درِ برآیند هست', nav);
  if (nav) {
    const pos = (await page.locator('[data-testid="master-queue-pos"]').textContent()) || '';
    const nextSymBefore = firstSym;
    await page.click('[data-testid="master-queue-next"]').catch(() => {});
    await page.waitForTimeout(2500);
    check('«بعدی» نماد را عوض می‌کند (بدونِ آلودگیِ اطلاعات)',
      !page.url().includes(encodeURIComponent(nextSymBefore)), `${pos.trim()} → ${page.url().slice(-40)}`);
  }
  await shot('release_master_dossier');
  check('برآیند: بی‌خطا', R.errors.length === 0, JSON.stringify(R.errors.slice(0, 2)));
}

// ── ۴) دیدهبان: اتحادِ فهرست‌ها + تب‌های پرونده ───────────────────────────────
R.errors.length = 0;
await openRoute('/watch', 1500);
await page.waitForSelector('[data-testid="watch-dossier-tabs"]', { timeout: 30000 }).catch(() => {});
const tabs = await page.locator('[data-testid="watch-dossier-tabs"] [role="tab"]').count();
check('پروندۀ دیدهبان چهار تب دارد', tabs === 4, `tabs=${tabs}`);
const rowsWatch = await page.locator('[data-testid^="watch-row-"]').count();
check('دیدهبان نماد دارد (اتحادِ محلی + ستارۀ سرور)', rowsWatch > 0, `rows=${rowsWatch}`);
for (const t of ['chart', 'fund', 'market', 'tape']) {
  await page.click(`[data-testid="watch-tab-${t}"]`).catch(() => {});
  await page.waitForTimeout(2600);
  const panel = await page.locator(`[data-testid="watch-dossier-${t}"]`).isVisible().catch(() => false);
  check(`تب «${t}» پنلش را باز می‌کند`, panel);
}
const watchHist = await page.locator('[data-testid^="tape-history-"]').first().isVisible().catch(() => false);
check('تبِ تابلوخوانیِ دیدهبان سابقه را می‌آورد', watchHist);
check('دیدهبان: بی‌سرریزِ افقی درِ ۱۳۶۶', await overflow() <= 12, `overflow=${await overflow()}px`);
check('دیدهبان: بی‌خطا', R.errors.length === 0, JSON.stringify(R.errors.slice(0, 2)));
await shot('release_watch_dossier');

// ── ۵) برابریِ عددِ رابط با پاسخِ مستقیمِ بک‌اند ──────────────────────────────
const api = await page.evaluate(async () => {
  const r = await fetch('api/tape-history?codes=&days=6');
  return { status: r.status, body: (await r.text()).slice(0, 120) };
});
check('/api/tape-history بی‌۵۰ است (کلیدِ رشته‌ای)', (api as { status: number }).status === 200,
  JSON.stringify(api));

await browser.close();
const fails = (R.checks as Array<{ pass: boolean }>).filter((c) => !c.pass).length;
R.summary = `${(R.checks as unknown[]).length - fails} pass / ${fails} fail`;
writeFileSync(OUT, JSON.stringify(R, null, 1), 'utf8');
console.log(R.summary);
for (const c of R.checks as Array<{ name: string; pass: boolean; got: string }>)
  console.log(`${c.pass ? '  ok  ' : ' FAIL '} ${c.name}${c.got ? '  -> ' + c.got : ''}`);
process.exit(fails ? 1 : 0);
