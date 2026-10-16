// _audit/ws7f_hover_persistence.mts — آیا reveal با hoverِ خالصِ CSS رویِ تابلویِ زنده می‌ماند؟
//
// سؤالِ واقعی: مالک رویِ ردیف می‌رود، جعبه ظاهر می‌شود، بعد دستش را تکان نمی‌دهد و
// جدولِ زنده (هر poll) ردیف‌ها را دوباره می‌سازد/مرتب می‌کند. اگر در آن لحظه
// `:hover` بیفتد، جعبه زیرِ چشم کاربر ناپدید می‌شود و کلیک از دست می‌رود.
//
// سه چیز هم‌زمان سنجیده می‌شود تا علت جدا شود:
//   ۱) opacityِ نشانگر (چیزی که کاربر می‌بیند)
//   ۲) همان گرهٔ DOM باقی مانده؟ (با یک mark که رویِ خودِ عنصر می‌گذارم)
//   ۳) با یک حرکتِ ۱ پیکسلیِ موس برمی‌گردد؟ (یعنی مشکل فقط style recalc است نه CSS)
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const BASE = process.argv.includes('--url') ? process.argv[process.argv.indexOf('--url') + 1]
                                             : 'http://127.0.0.1:5175/';
mkdirSync('_audit', { recursive: true });
const OUT = '_audit/ws7f_hover_persistence.json';
const browser = await chromium.launch({ headless: true,
  executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(String(e.message).slice(0, 140)));
await page.goto(BASE + '#/market', { waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => document.querySelectorAll('[data-testid="tape-row"]').length >= 6,
  null, { timeout: 90_000 });
await page.waitForTimeout(1000);

// خودِ $$eval بازگشتِ تابع را می‌دهد (این‌جا یک رشته)؛ []set کردنش حرفِ اول را برمی‌دارد.
const symAt = (k: number) => page.$$eval('[data-testid^="select-box-"]',
  (els, i) => String(els[i].getAttribute('data-testid')).replace('select-box-', ''), k);

// SCAFFOLD: علامت‌گذاریِ گرهٔ ردیف و نشانگرش، تا بدانیم «همان DOM است یا نه».
const mark = (sym: string) => page.evaluate((s: string) => {
  const box = document.querySelector('[data-testid="select-box-' + s + '"]');
  const row = box ? box.closest('[data-testid="tape-row"]') : null;
  if (box) (box as HTMLElement).dataset.probeMark = 'M1';
  if (row) (row as HTMLElement).dataset.probeMark = 'R1';
  return { boxed: !!box, rowed: !!row };
}, sym);

// خواندنِ حالتِ یک نماد: opacity، زنده ماندنِ mark، و اینکه آیا موس فیزیکاً رویِ همان
// مستطیل است (elementFromPoint) — تفکیکِ «CSS نیامده» از «موس دیگر آن‌جا نیست».
const read = (sym: string) => page.evaluate((s: string) => {
  const box = document.querySelector('[data-testid="select-box-' + s + '"]');
  const star = document.querySelector('[data-testid="watch-star-' + s + '"]');
  const row = box ? box.closest('[data-testid="tape-row"]') : null;
  if (!box || !row) return { missing: true, sym: s };
  const r = row.getBoundingClientRect();
  const mx = (window as any).__probeMouse ?? { x: 0, y: 0 };
  const overRect = mx.x >= r.left && mx.x <= r.right && mx.y >= r.top && mx.y <= r.bottom;
  const underPoint = document.elementFromPoint(mx.x, mx.y);
  return {
    box: Number(getComputedStyle(box).opacity),
    star: star ? Number(getComputedStyle(star).opacity) : null,
    domMarkAlive: (box as HTMLElement).dataset.probeMark === 'M1',
    rowMarkAlive: (row as HTMLElement).dataset.probeMark === 'R1',
    rowMatchesHover: row.matches(':hover'),
    boxMatchesHover: box.matches(':hover'),
    mouseInsideRowRect: overRect,
    elementFromPointIsInRow: !!(underPoint && row.contains(underPoint)),
    rowTop: Math.round(r.top), rowHeight: Math.round(r.height),
  };
}, sym);

// موس را می‌بریم رویِ مرکزِ ردیفِ k و مختصاتش را در صفحه می‌نویسیم (برایِ read بالا).
const hoverRow = async (k: number) => {
  const sym = await symAt(k);
  const box = await page.locator('[data-testid="tape-row"]').nth(k).boundingBox();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await page.evaluate(({ x, y }) => { (window as any).__probeMouse = { x, y }; },
    { x: box!.x + box!.width / 2, y: box!.y + box!.height / 2 });
  await page.waitForTimeout(300);
  return sym;
};

const steps: any = { base: BASE };
const s0 = await hoverRow(2);
await mark(s0);
steps.sym = s0;
steps.t0 = await read(s0);

// سه بازهٔ صبر بدونِ هیچ حرکتِ موس: poll هایِ خودِ برنامه در این مدت می‌آید.
for (const ms of [1500, 3000, 6000]) {
  await page.waitForTimeout(ms);
  steps['wait' + ms] = await read(s0);
}

// آیا یک تکانِ ۱ پیکسلیِ موس جعبه را برمی‌گرداند؟ (اگر بله، مشکل فقط recalc است.)
const m = await page.evaluate(() => (window as any).__probeMouse);
await page.mouse.move(m.x + 1, m.y);
await page.waitForTimeout(300);
steps.afterTinyMove = await read(s0);

// خطرِ واقعیِ تابلو: جابه‌جا شدنِ خودِ ردیف زیرِ موس (مرتب‌شدنِ زنده). با تغییرِ
// ترتیبِ ستون «تغییر» همان را ساختگی شبیه‌سازی می‌کند؛ بعد opacity را دوباره می‌خوانیم.
await page.mouse.move(m.x, m.y);
const sortClicked = await page.evaluate(() => {
  const h = [...document.querySelectorAll('button, [role="columnheader"], th')]
    .find((e) => /تغییر|٪|درصد/.test(String(e.textContent ?? '')));
  if (h) { (h as HTMLElement).click(); return String(h.textContent).trim().slice(0, 24); }
  return null;
});
await page.waitForTimeout(600);
steps.afterResort = await read(s0);
steps.afterResortSortHeader = sortClicked;

steps.pageErrors = errs;
writeFileSync(OUT, JSON.stringify(steps, null, 2));
const line = (k: string, v: any) => v && !v.missing
  ? console.log(`${k.padEnd(16)} box=${v.box} domMark=${v.domMarkAlive} rowHover=${v.rowMatchesHover} inside=${v.mouseInsideRowRect} underPoint=${v.elementFromPointIsInRow}`)
  : console.log(`${k.padEnd(16)} ${JSON.stringify(v)}`);
console.log('sym=' + steps.sym + ' sortHeader=' + JSON.stringify(steps.afterResortSortHeader));
for (const k of ['t0', 'wait1500', 'wait3000', 'wait6000', 'afterTinyMove', 'afterResort']) line(k, steps[k]);
await browser.close();
