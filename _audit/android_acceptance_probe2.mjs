// _audit/android_acceptance_probe2.mjs — سه موردی که در دورِ اول FAIL شد
// (۱) صف/اینسپکتور: ردیفِ تابلو خودش role="button" است، نه یک buttonِ تودرتو
// (۲) اسکرولِ بنیادی: ظرفِ اسکرول خودِ [data-testid='fts-screen-scroll'] است
// (۳) آفلاین: دیتابیس درِ همان صفحه باید بماند؛ ناوبریِ کاملِ مجدد یعنی بارگذاریِ
//     دوبارۀ بسته ⇒ قطعِ شبکه را با تغییرِ هاش می‌کنیم، نه goto.
import { mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const { chromium } = await import(pathToFileURL(
  'C:/Users/PCMOD/Desktop/BorsTerminal-android/frontend/node_modules/playwright/index.mjs').href);

const BASE = process.env.PROBE_URL || 'http://127.0.0.1:4181/';
const OUT = '_audit/acceptance';
mkdirSync(OUT, { recursive: true });
if (!existsSync('C:/Users/PCMOD/Desktop/BorsTerminal-android/frontend/dist/probe_bundle.js')) {
  console.error('dist/probe_bundle.js missing — copy the snapshot there first'); process.exit(2);
}

const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 360, height: 800 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
const page = await ctx.newPage();
await page.addInitScript(() => { try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* noop */ } });
const errs = [];
page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 160)); });
const report = { base: BASE, checks: {} };
const check = (name, rec) => { report.checks[name] = rec; console.log(`${rec.state}  ${name}  ${JSON.stringify(rec).slice(0, 400)}`); };
const geom = (sel) => page.evaluate((s) => {
  const el = document.querySelector(s);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
           bottom: Math.round(r.bottom), scrollW: el.scrollWidth, clientW: el.clientWidth, scrollH: el.scrollHeight };
}, sel);

await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(60000);

// ۱) صف و اینسپکتور
const rowSel = '[data-testid="tape-row"]';
if (!(await page.locator(rowSel).count())) {
  check('queue.inspector', { state: 'FAIL', why: 'no tape row at all' });
} else {
  await page.locator(rowSel).first().click();
  await page.waitForTimeout(5000);
  const insp = await geom('aside[data-shell="inspector"]');
  const nav = await geom('aside[data-shell="sidebar"]');
  const book = await page.evaluate(() => {
    const t = document.querySelector('aside[data-shell="inspector"]')?.innerText ?? '';
    return { depthWords: /عمق|پنج‌سطحی|تقاضا|عرضه/.test(t), bestLimit: /حدِ مجاز|حد مجاز|تأیید/.test(t),
             snippet: t.replace(/\s+/g, ' ').slice(0, 260) };
  });
  check('queue.inspector', {
    state: insp && insp.w > 0 && insp.bottom <= 801 && nav && insp.bottom <= nav.y + 1 ? 'PASS' : 'FAIL',
    inspector: insp, nav, navVisible: !!nav && nav.bottom <= 801, ...book,
  });
  await page.screenshot({ path: `${OUT}/09-inspector-open.png` });
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('aside[data-shell="inspector"] button')].find((x) => (x.textContent ?? '').includes('✕'));
    b?.click();
  });
  await page.waitForTimeout(1500);
}

// ۲) اسکرولِ جدولِ بنیادی
await page.evaluate(() => { location.hash = '#/fundamental'; });
await page.waitForTimeout(20000);
const firstBefore = await page.evaluate(() => document.querySelector('[data-testid="fts-screen-scroll"] tbody tr')?.innerText.replace(/\s+/g, ' ').slice(0, 40) ?? null);
await page.evaluate(() => {
  const el = document.querySelector('[data-testid="fts-screen-scroll"]');
  if (el) el.scrollTop = 30000;
});
await page.waitForTimeout(3000);
const after = await page.evaluate(() => {
  const el = document.querySelector('[data-testid="fts-screen-scroll"]');
  return { top: el?.scrollTop ?? -1, rows: document.querySelectorAll('[data-testid="fts-screen-scroll"] tbody tr').length,
           first: document.querySelector('[data-testid="fts-screen-scroll"] tbody tr')?.innerText.replace(/\s+/g, ' ').slice(0, 40) ?? null };
});
check('fundamental.scrollEnd', {
  state: after.top > 1000 && after.rows > 5 && after.first !== firstBefore ? 'PASS' : 'FAIL',
  rowsInDom: after.rows, scrollTop: after.top, firstBefore, firstAfter: after.first,
});
await page.screenshot({ path: `${OUT}/10-fundamental-scrolled.png` });

// ۳) آفلاینِ گوشی: فقط شبکهٔ بیرونی قطع می‌شود. `ctx.setOffline(true)` کلِ origin را
// می‌بندد و chunk‌هایِ lazyِ خودِ اپ و حتی بستهٔ داده را هم از کار می‌اندازد — رویِ
// گوشی آن فایل‌ها داخلِ APK هستند. پس چیزی که رویِ گوشی می‌شکند این‌جا سنجیده می‌شود.
await ctx.route('**://*.tsetmc.com/**', (r) => r.abort());
await ctx.route('**://github.com/**', (r) => r.abort());
await page.evaluate(() => { location.hash = '#/technical/%D8%AE%DA%AF%D8%B3%D8%AA%D8%B1'; });
await page.waitForTimeout(25000);
const ink = await page.evaluate(() => [...document.querySelectorAll('canvas')].map((c) => {
  const g = c.getContext('2d'); let n = 0;
  if (g && c.width > 20) {
    const d = g.getImageData(0, 0, Math.min(c.width, 600), Math.min(c.height, 600)).data;
    for (let i = 3; i < d.length; i += 4) if (d[i] > 8) n++;
  }
  return n;
}).filter((n) => n > 500).length);
const emptyMsg = await page.locator('text=داده‌ای برای رسم نیست').count();
check('offline.technicalFromSnapshot', {
  state: ink > 0 && emptyMsg === 0 ? 'PASS' : 'FAIL', inkCanvases: ink, emptyState: emptyMsg,
  offline: true, note: 'آفلاین = قطعِ TSETMC/GitHub؛ chunk و اسنپ‌شات از همان اول در حافظه‌اند',
});
await page.screenshot({ path: `${OUT}/11-offline-xgstr.png` });


report.errors = [...new Set(errs)].slice(0, 12);
writeFileSync(`${OUT}/acceptance2.json`, JSON.stringify(report, null, 1));
await browser.close();
