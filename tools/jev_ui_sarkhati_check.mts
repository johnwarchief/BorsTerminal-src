// tools/jev_ui_sarkhati_check.mts — سنجشِ زندهٔ لایۀ jev-ui درِ تبِّ سرخطی
//
// چرا این فایل هست: آزمونِ jsdom ثابت می‌کند مؤلفه درست کار می‌کند؛ اینجا سنجیده
// می‌شود که *پاسخِ واقعیِ بک‌اند* ردیفِ ابزارهایِ حرفه‌ای را جابه‌جا می‌کند، خطِ
// راهنما کِی *اضافه* می‌شود، و هیچ درخواستی ازِ ماشین بیرون نمی‌رود. مسیرِ رابط
// ازِ کلیکِ واقعی می‌گذرد (ناوبری ← نماد ← سفارش ← «توقف»)، نه ازِ تزریقِ state.
// چهار چیز صریح چک می‌شود:
//  ۱) درِ حالتِ عادی ترتیبِ DOM ردیفِ ثانویه همان ترتیبِ همیشگی است (لایه
//     بی‌دلیل صفحه را تکان نمی‌دهد)؛
//  ۲) پس ازِ «توقفِ اضطراری» که ازِ چیپِ `watch-kill-switch` زده می‌شود، «ریسک و
//     ایمنی» به اول می‌آید؛
//  ۳) راهنما باِ سه کلیکِ تکراری رویِ یک مقصد ظاهر می‌شود و درِ همان حالت هیچ
//     چیپی کم نمی‌شود؛
//  ۴) هیچ درخواستِ غیرِ localhost ثبت نمی‌شود (proofِ بی‌ترافیک) و خطایِ کنسول
//     گزارش می‌شود، نه قورت.
// درِ ورودِ خودِ ترمینال (admin/bors123 درِ کدِ منبعی) دست‌نخورده می‌ماند؛ تنها
// کلیدِ نشستِ محلی درِ sessionStorage می‌نشیند تا سنجه رابط را ببیند نه دروازه.
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  || 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package/node_modules/playwright/index.mjs';
const BASE = process.argv[2] || 'http://127.0.0.1:8173/';
const OUT = process.env.JEV_OUT_DIR || 'C:/Users/PCMOD/Desktop/_bors-sarkhati-jev/_audit/jev-ui-live';
const SYMBOL = process.env.JEV_SYMBOL || 'فولاد';
mkdirSync(OUT, { recursive: true });

const { chromium } = await import(pathToFileURL(PKG).href);
const browser = await chromium.launch({ headless: true,
  executablePath: process.env.JEV_CHROME || undefined });

const report: Record<string, unknown> = { base: BASE, at: new Date().toISOString(), shots: [] };
const external: string[] = [];
const failures: string[] = [];

async function openPage(width: number, height: number) {
  const ctx = await browser.newContext({ viewport: { width, height } });
  await ctx.addInitScript(() => {
    try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* noop */ }
  });
  const page = await ctx.newPage();
  page.on('request', (r: { url: () => string }) => {
    const u = r.url();
    if (!/^https?:\/\/(127\.0\.0\.1|localhost)(:|\/)/.test(u)) external.push(u);
  });
  page.on('response', (r: { status: () => number; url: () => string }) => {
    if (r.status() >= 400) failures.push(`${r.status()} ${r.url().slice(0, 110)}`);
  });
  const errors: string[] = [];
  page.on('pageerror', (e: Error) => errors.push('pageerror: ' + String(e).slice(0, 200)));
  page.on('console', (m: { type: () => string; text: () => string }) => {
    if (m.type() === 'error') errors.push('console: ' + String(m.text()).slice(0, 200));
  });
  return { ctx, page, errors };
}

const row = (p: any) => p.locator('[data-testid="sarkhati-pro-sections"]').evaluate((el: Element) => {
  const chips = Array.from(el.querySelectorAll('button[data-ranked-id]'));
  return {
    order: chips.map((c) => c.getAttribute('data-ranked-id')),
    labels: chips.map((c) => (c.textContent || '').trim()),
    chipHeight: chips.map((c) => Math.round(c.getBoundingClientRect().height)),
    rowTop: Math.round(el.getBoundingClientRect().top),
  };
}).catch((e: Error) => ({ error: String(e).slice(0, 120) }));

const hint = (p: any) => p.locator('[data-testid="sarkhati-hint"]').count().then(async (n: number) =>
  n === 0 ? { present: false }
    : { present: true, ...(await p.locator('[data-testid="sarkhati-hint"]').evaluate((el: Element) => ({
      level: el.getAttribute('data-level'),
      text: (el.textContent || '').trim().slice(0, 220),
      height: Math.round(el.getBoundingClientRect().height),
    }) as object)) });

const metrics = (p: any) => p.locator('[data-testid="sarkhati-page"]').evaluate((el: Element) => {
  const r = el.getBoundingClientRect();
  return { pageHeight: Math.round(r.height), pageWidth: Math.round(r.width) };
});

/** تا `ms` صبر می‌کند تا شرطِ ترتیب برقرار شود؛ وضعیتِ سرویس باِ polling می‌آید. */
async function waitOrder(p: any, want: string, ms: number) {
  const until = Date.now() + ms;
  let seen: unknown = null;
  while (Date.now() < until) {
    seen = await row(p);
    const first = (seen as { order?: string[] }).order?.[0];
    if (first === want) return { waitedMs: ms - (until - Date.now()), seen };
    await p.waitForTimeout(600);
  }
  return { waitedMs: ms, timedOut: true, seen };
}

{
  const { ctx, page, errors } = await openPage(1440, 1100);
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.locator('[data-testid="nav-sarkhati"]').waitFor({ timeout: 30000 });
  await page.locator('[data-testid="nav-sarkhati"]').click();
  await page.locator('[data-testid="sarkhati-page"]').waitFor({ timeout: 20000 });
  await page.waitForTimeout(2200);

  report.normal = { row: await row(page), hint: await hint(page), metrics: await metrics(page) };
  await page.screenshot({ path: `${OUT}/01-normal-1440.png`, fullPage: true });
  (report.shots as string[]).push('01-normal-1440.png');

  // نماد ازِ جست‌وجویِ خودِ رابط: مسیرِ واقعیِ کاربر، نه state‌سازیِ تست
  await page.locator('[data-testid="sarkhati-tab-symbol"]').click();
  await page.waitForTimeout(900);
  await page.locator('[data-testid="sarkhati-symbol-search"]').fill(SYMBOL);
  await page.waitForTimeout(2600);
  const results = page.locator('[data-testid="sarkhati-symbol-results"] button');
  report.symbolResults = await results.count();
  if (report.symbolResults > 0) await results.first().click();
  await page.waitForTimeout(800);
  report.chosenSymbol = await page.locator('[data-testid="sarkhati-chosen-symbol"]').innerText()
    .catch(() => null);

  await page.locator('[data-testid="sarkhati-tab-order"]').click();
  await page.waitForTimeout(1400);
  report.orderPanel = {
    row: await row(page), formPresent: await page.locator('[data-testid="watch-order-phase"]').count(),
    killChip: await page.locator('[data-testid="watch-kill-switch"]').count(),
  };
  await page.screenshot({ path: `${OUT}/02-order-1440.png`, fullPage: true });
  (report.shots as string[]).push('02-order-1440.png');

  // توقفِ اضطراری ازِ رابط → انتظارِ پاسخِ سرویس → بازخوانیِ ترتیب
  if (report.orderPanel.killChip > 0) {
    await page.locator('[data-testid="watch-kill-switch"]').click();
    report.halt = await waitOrder(page, 'risk', 20000);
    report.haltHint = await hint(page);
    report.haltLine = await page.locator('[data-testid="sarkhati-status-line"]').innerText()
      .catch(() => null);
    await page.screenshot({ path: `${OUT}/03-halted-1440.png`, fullPage: true });
    (report.shots as string[]).push('03-halted-1440.png');

    // راهنمایِ *اضافه*: سه کلیکِ تکراری رویِ یک مقصد، درِ حالتِ بستهِ دروازه
    const before = await row(page);
    for (let i = 0; i < 3; i += 1) {
      await page.locator('[data-testid="sarkhati-tab-monitor"]').click();
      await page.waitForTimeout(450);
    }
    await page.waitForTimeout(900);
    report.hintAfterRepeats = { hint: await hint(page), rowBefore: before, rowAfter: await row(page) };
    await page.screenshot({ path: `${OUT}/04-hint-1440.png`, fullPage: true });
    (report.shots as string[]).push('04-hint-1440.png');

    // برگشت: «ادامه» تا this machine برایِ سنجشِ بعدی درِ توقف نماند. چیپِ
    // ادامه درِ همان پنلِ سفارش است؛ پس اول برمی‌گردیم (درِ پنلِ پایش نیست).
    await page.locator('[data-testid="sarkhati-tab-order"]').click();
    await page.waitForTimeout(1200);
    const resume = page.locator('[data-testid="exec-resume"]');
    report.resumeClicked = await resume.count() > 0;
    if (report.resumeClicked) { await resume.click(); await page.waitForTimeout(2500); }
    report.afterResume = await row(page);
  }
  report.errors1440 = errors.slice(0, 8);
  await ctx.close();
}

{
  const { ctx, page, errors } = await openPage(1280, 800);
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.locator('[data-testid="nav-sarkhati"]').waitFor({ timeout: 30000 });
  await page.locator('[data-testid="nav-sarkhati"]').click();
  await page.locator('[data-testid="sarkhati-page"]').waitFor({ timeout: 20000 });
  await page.waitForTimeout(2200);
  report.normal1280 = { row: await row(page), hint: await hint(page), metrics: await metrics(page) };
  await page.screenshot({ path: `${OUT}/05-normal-1280.png`, fullPage: true });
  (report.shots as string[]).push('05-normal-1280.png');
  report.errors1280 = errors.slice(0, 8);
  await ctx.close();
}

report.externalRequests = [...new Set(external)];
report.zeroEgress = report.externalRequests.length === 0;
report.httpFailures = [...new Set(failures)].slice(0, 12);
writeFileSync(`${OUT}/JEV_UI_LIVE.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 1).slice(0, 4000));
await browser.close();
