/**
 * tools/telegram_catalog_live_probe.mts — اثبات زندهٔ کاتالوگ تلگرام در برنامۀ مهاجرتی
 *
 * این سنجه عمداً «همۀ ۶۴ عکس پیکسل دارند» را پس از اسکرولِ جعبۀ داخلی می‌سنجد:
 * تصاویر با loading="lazy" پیش از رسیدن به دید بارگذاری نمی‌شوند، پس اندازه‌گیری
 * در حالت اولیه نه نقصِ برنامه که فقط رفتارِ درستِ lazy را نشان می‌دهد.
 *
 * پیش‌نیاز: vite روی ۵۱۸۰. بک‌اند لازم نیست؛ نبودنش فقط فونتِ Vazirmatn و
 * ردیف‌های بازار را عوض می‌کند و در خروجی صریح گزارش می‌شود.
 *
 * Run:
 *   node --no-warnings tools/telegram_catalog_live_probe.mts
 */
import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';

const require = createRequire('C:/Users/PCMOD/');
const { chromium } = require('playwright-core');

const EXE = process.env.JEV_CHROME || 'C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const BASE = 'http://localhost:5180/#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF';
const OUTDIR = 'C:/Users/PCMOD/Desktop/BorsTerminal/_audit/telegram-catalog-live';

mkdirSync(OUTDIR, { recursive: true });

const results: { name: string; pass: boolean; detail?: unknown }[] = [];
const check = (name: string, pass: boolean, detail?: unknown) => {
  results.push({ name, pass, detail });
  console.log(`${pass ? 'PASS' : 'FAIL'} | ${name} | ${JSON.stringify(detail ?? {})}`);
};

const browser = await chromium.launch({ headless: true, executablePath: EXE });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

const failedRequests: Record<string, number> = {};
page.on('response', (r) => {
  if (r.status() >= 400) {
    const key = `${r.status()} ${r.url().replace(/^http:\/\/localhost:5180/, '').slice(0, 60)}`;
    failedRequests[key] = (failedRequests[key] || 0) + 1;
  }
});

await page.goto(BASE, { waitUntil: 'networkidle' });
await page.waitForTimeout(2000);

// ── ۱. تب اندیکاتورها و بلوک کاتالوگ
await page.getByTestId('drawer-tab-indicators').click();
await page.waitForTimeout(900);
check('indicators panel rendered', (await page.getByTestId('indicators-panel').count()) === 1);
check('catalog mounted inside it', (await page.getByTestId('telegram-catalog-list').count()) === 1);

// ── . شمارِ سطرهای واقعیِ DOM
const rowCount = await page.locator('[data-testid^="telegram-row-p"]').count();
check('64 rows in the DOM', rowCount === 64, { rowCount });

// ── ۳. lazy بودنِ تصاویر در حالت اولیه (این رفتار درست است، نه نقص)
const beforeScroll = await page.evaluate(() => {
  let loaded = 0;
  document.querySelectorAll('[data-testid^="telegram-thumb-p"] img').forEach((i) => {
    if ((i as HTMLImageElement).naturalWidth > 0) loaded++;
  });
  return loaded;
});
check('lazy: only the visible band is decoded at first paint', beforeScroll > 0 && beforeScroll < 64, { beforeScroll });

// ── ۴. پس از اسکرول، هر ۶۴ عکس باید پیکسل واقعی داشته باشد
const afterScroll = await page.evaluate(async () => {
  const list = document.querySelector('[data-testid="telegram-catalog-list"]');
  const box = list?.querySelector('.overflow-y-auto') as HTMLElement | null;
  if (!box) return { error: 'no scroll box' };
  const step = Math.max(120, Math.floor(box.clientHeight / 2));
  for (let y = 0; y <= box.scrollHeight; y += step) {
    box.scrollTop = y;
    await new Promise((r) => setTimeout(r, 120));
  }
  box.scrollTop = 0;
  await new Promise((r) => setTimeout(r, 1800));
  const broken: string[] = [];
  document.querySelectorAll('[data-testid^="telegram-thumb-p"] img').forEach((img) => {
    const id = img.closest('[data-testid]')?.getAttribute('data-testid')?.replace('telegram-thumb-', '') ?? '?';
    if (!(img as HTMLImageElement).complete || (img as HTMLImageElement).naturalWidth === 0) broken.push(id);
  });
  return { scrollHeight: box.scrollHeight, clientHeight: box.clientHeight, broken };
});
check('all 64 photos really bundled (decoded after scroll)', !afterScroll.broken || afterScroll.broken.length === 0, afterScroll);

// ── ۵. لایت‌باکس: تصویر کامل، فوکوس داخل دیالوگ، و پرسشِ لایه‌بندی
await page.click('[data-testid="telegram-thumb-p12"]');
await page.waitForTimeout(700);
const lb = await page.evaluate(() => {
  const box = document.querySelector('[data-testid="telegram-lightbox"]');
  if (!box) return null;
  const img = box.querySelector('img') as HTMLImageElement | null;
  const rect = box.getBoundingClientRect();
  const w = window.innerWidth;
  const overToolbar: (string | null)[] = [];
  for (let x = 60; x < w; x += 120) {
    const el = document.elementFromPoint(x, 24);
    overToolbar.push(el?.getAttribute('data-testid') ?? el?.closest('[data-testid]')?.getAttribute('data-testid') ?? (el ? el.tagName : null));
  }
  return {
    naturalWidth: img?.naturalWidth ?? 0,
    naturalHeight: img?.naturalHeight ?? 0,
    scrimCoversViewport: rect.x === 0 && rect.y === 0 && Math.round(rect.width) === w,
    focusInside: box.contains(document.activeElement),
    activeLabel: document.activeElement?.getAttribute('aria-label') ?? document.activeElement?.tagName ?? null,
    overToolbar,
  };
});
check('lightbox shows the full-size photo', !!lb && lb.naturalWidth >= 900, lb && { w: lb.naturalWidth, h: lb.naturalHeight });
check('focus moved into the dialog', !!lb && lb.focusInside, lb && { active: lb.activeLabel });
check('lightbox paints above the toolbar strip', !!lb && lb.overToolbar.every((t) => t === 'telegram-lightbox'), lb && { overToolbar: lb.overToolbar });

// ── ۶. بستن با Escape و بازگشت فوکوس
await page.keyboard.press('Escape');
await page.waitForTimeout(400);
const afterClose = await page.evaluate(() => ({
  lightboxGone: !document.querySelector('[data-testid="telegram-lightbox"]'),
  focusOnThumb: document.activeElement?.getAttribute('data-testid'),
}));
check('Escape closes and returns focus to the thumb', afterClose.lightboxGone && afterClose.focusOnThumb === 'telegram-thumb-p12', afterClose);

// ── ۷. جستجو
await page.fill('[data-testid="telegram-catalog-search"]', 'supertrend');
await page.waitForTimeout(700);
const filtered = await page.locator('[data-testid^="telegram-row-p"]').count();
const countText = (await page.getByTestId('telegram-catalog-count').textContent())?.trim();
check('search narrows the list, count in Persian digits', filtered > 0 && filtered < 64 && /۰|۱|۲|۳|۴|۵|۶|۷|۸|۹/.test(countText || ''), { filtered, countText });

await page.fill('[data-testid="telegram-catalog-search"]', 'Indi 225.txt');
await page.waitForTimeout(600);
check('attachment-name search finds p14', (await page.getByTestId('telegram-row-p14').count()) === 1);

await page.fill('[data-testid="telegram-catalog-search"]', 'zzzz-nothing');
await page.waitForTimeout(500);
check('empty-result state renders', (await page.locator('text=موردی با این عبارت یافت نشد').count()) === 1);
await page.fill('[data-testid="telegram-catalog-search"]', '');
await page.waitForTimeout(500);

// ── ۸. سوئیچِ واقعاً متصل به استور
const before = (await page.getByTestId('toggle-indicator-p12').textContent())?.trim();
await page.click('[data-testid="toggle-indicator-p12"]');
await page.waitForTimeout(500);
const after = (await page.getByTestId('toggle-indicator-p12').textContent())?.trim();
check('toggle flips and writes the store', !!before && !!after && before !== after, { before, after });

const split = await page.evaluate(() => {
  let toggles = 0;
  let notImpl = 0;
  document.querySelectorAll('[data-testid^="toggle-indicator-p"]').forEach(() => toggles++);
  document.querySelectorAll('[data-testid^="telegram-status-p"]').forEach((el) => {
    if (el.textContent?.includes('پیاده‌سازی نشده')) notImpl++;
  });
  return { toggles, notImpl };
});
check('exactly 9 toggles and 55 not-implemented', split.toggles === 9 && split.notImpl === 55, split);

// ── ۹. جهتِ ابعاد در متنِ RTL
const dimsText = await page.evaluate(() => {
  const span = document.querySelector('[data-testid="telegram-row-p01"] [dir="ltr"]');
  return span?.textContent ?? null;
});
check('dims render LTR as 1280×608', dimsText === '1280×608', { dimsText });

// ── ۰. سطرهای بی‌کپشن: عنوانِ جایگزین، نه متنِ ساخته‌شده
const fallbacks = await page.evaluate(() => {
  const read = (id: string) => document.querySelector(`[data-testid="telegram-row-${id}"]`)?.textContent ?? '';
  return { p08: read('p08').slice(0, 40), p10: read('p10').slice(0, 60) };
});
check('caption-less rows fall back, never invent text', fallbacks.p08.includes('p08') && fallbacks.p10.includes('Gold Snap'), fallbacks);

await page.screenshot({ path: `${OUTDIR}/tab-indicators.png` });
await page.click('[data-testid="telegram-thumb-p12"]');
await page.waitForTimeout(600);
await page.screenshot({ path: `${OUTDIR}/lightbox-p12.png` });

const summary = {
  when: new Date().toISOString(),
  base: BASE,
  backendRunning: Object.keys(failedRequests).length === 0,
  failedRequests,
  pass: results.filter((r) => r.pass).length,
  fail: results.filter((r) => !r.pass).length,
  results,
};
writeFileSync(`${OUTDIR}/live-check.json`, JSON.stringify(summary, null, 2));
console.log(`\nSUMMARY: ${summary.pass} passed, ${summary.fail} failed`);
console.log(`failed requests: ${JSON.stringify(failedRequests)}`);
await browser.close();
