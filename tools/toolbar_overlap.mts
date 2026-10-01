/**
 * tools/toolbar_overlap.mts — آیا کلیدهای نوارِ بالا در عرضِ واقعی روی هم می‌افتند؟
 *
 * v1.0.67 تکهٔ «موتور چارت» را با کلاسِ `nn-btn-group` به نوارِ ابزار اضافه کرد؛
 * آن کلاس در stylesheet تعریف نشده بود، پس دو دکمه در جعبه‌ای بلوکی جمع شدند و
 * «موتور دوم» زیرِ «بازپخش» رفت — یعنی کلیکِ «موتور دوم» عملاً «بازپخش» را می‌زد.
 * این ابزار همان را با عدد می‌گوید: نقطهٔ میانیِ هر دکمه hit-test می‌شود و هر
 * دکمه‌ای که در آن نقطه خودش نیست گزارش می‌شود.
 *
 *   JEV_CHROME=<chromium.exe> node --experimental-strip-types tools/toolbar_overlap.mts
 *   (JEV_BASE / JEV_ROUTE / JEV_WIDTH برای سرور و رابطِ دلخواه)
 *
 * هیچ متنِ پروژه‌ای به بیرون نمی‌رود؛ فقط localhost.
 *
 * jev_ui_check و کلیکِ مستقیمِ من روی «موتور دوم» با «subtree intercepts pointer
 * events» شکست خورد؛ یعنی نقطهٔ میانیِ آن دکمه زیرِ عنصرِ دیگری است. این اسکریپت
 * جعبهٔ همهٔ دکمه‌های نوار بالا را می‌خواند و هر جفتِ هم‌پوشان را چاپ می‌کند —
 * حدسِ چیدمان به‌جای عددِ چیدمان نشود.
 */
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);

const BASE = process.env.JEV_BASE ?? 'http://127.0.0.1:8013/';
const ROUTE = process.env.JEV_ROUTE ?? '#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF';
const WIDTH = Number.parseInt(process.env.JEV_WIDTH ?? '1366', 10);

const browser = await chromium.launch({
  ...(process.env.JEV_CHROME ? { executablePath: process.env.JEV_CHROME } : {}),
});
const page = await browser.newPage({ viewport: { width: WIDTH, height: 900 } });
await page.addInitScript(() => { try { sessionStorage.setItem('bors_auth_session', 'true'); } catch {} });
await page.goto(BASE + ROUTE, { waitUntil: 'load' });
await page.waitForTimeout(9000);

const rows = await page.evaluate(() => {
  const bar = document.querySelector('.nn-top-toolbar');
  if (!bar) return [];
  const els = Array.from(bar.querySelectorAll('button, [data-testid^="nn-engine"]')) as HTMLElement[];
  return els.map((e) => {
    const r = e.getBoundingClientRect();
    const mid = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return {
      testid: e.getAttribute('data-testid'),
      title: (e.getAttribute('title') ?? e.textContent ?? '').slice(0, 28),
      x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height),
      covered: !(mid === e || e.contains(mid)),
      coverBy: mid
        ? (() => {
            const m = mid as HTMLElement;
            const r = m.getBoundingClientRect();
            return `${m.tagName}.${String(m.className).slice(0, 30)} ` +
              `text="${(m.textContent ?? '').trim().slice(0, 24)}" ` +
              `rect=[${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.width)}x${Math.round(r.height)}]`;
          })()
        : null,
    };
  });
});
const bad = rows.filter((r) => r.covered);
console.log(JSON.stringify({ width: WIDTH, buttons: rows.length, covered: bad }, null, 1));
console.log('bar scroll', await page.evaluate(() => {
  const b = document.querySelector('.nn-top-toolbar') as HTMLElement | null;
  return b ? { clientWidth: b.clientWidth, scrollWidth: b.scrollWidth } : null;
}));
await browser.close();
