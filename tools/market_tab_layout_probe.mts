// tools/market_tab_layout_probe.mts — سنجهٔ چیدمانِ «وضعیت بازار»: ارتفاع، تصویر، و سلامتِ داده
//
// چرا: مرحلۀ صفرِ مأموریت می‌گوید پیش ازِ اصلاح، صفحۀ *فعلی* درِ ابعادِ استانداردِ
// دسکتاپ دیده و مستند شود؛ و مرحلۀ ۸ می‌گوید پیش‌ و پس باِ همِ رزولوشن مقایسه شود.
// پس این فایل یکِ ابزارِ اندازه‌گیری است، نه یکِ اسکرین‌شات‌گیر: برایِ هر عرض،
// موقعیتِ عمودی و ارتفاعِ هر بخشِ صفحه را ازِ خودِ DOM می‌خواند و رویِ دیسک
// می‌گذارد — تا «خلوت‌تر شد» عدد داشته باشد، نه ادعا.
//
// سه چیزی که گزارش می‌کند و جایِ حدس را می‌بندد:
//  • ترتیبِ بخش‌ها باِ `top` واقعی‌شان (نه ترتیبِ نوشتن درِ JSX)؛
//  • ارتفاعِ هر بخش و مجموعِ ارتفاعِ بالایِ صفحه تا پیش ازِ اولین نمودار؛
//  • خطاهایِ کنسول و پاسخ‌هایِ ۴xx/۵xx — چون یکِ چیدمانِ «درست» باِ دادهٔ نشکسته
//    معنا دارد.
// رأیِ «خوب دیده می‌شود» باِ مالک است؛ این فایل فقط می‌گوید چه عددی عوض شد.
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  || 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package/node_modules/playwright/index.mjs';
const BASE = process.argv[2] || 'http://127.0.0.1:8001/';
const TAG = process.argv[3] || 'before';
const OUT = process.env.JEV_OUT_DIR
  || 'C:/Users/PCMOD/Desktop/_bors-market-tab/_audit/market-tab-layout';
mkdirSync(OUT, { recursive: true });

const WIDTHS = [1440, 1280, 1100];
const { chromium } = await import(pathToFileURL(PKG).href);
const browser = await chromium.launch({ headless: true,
  executablePath: process.env.JEV_CHROME || undefined });

const report: Record<string, unknown> = { base: BASE, tag: TAG, runs: [] };

for (const width of WIDTHS) {
  const ctx = await browser.newContext({ viewport: { width, height: 900 } });
  await ctx.addInitScript(() => {
    try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* noop */ }
  });
  const page = await ctx.newPage();
  const errors: string[] = [];
  const badStatus: string[] = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 160)); });
  page.on('pageerror', (e) => errors.push('PAGEERROR ' + String(e).slice(0, 160)));
  page.on('response', (r) => { if (r.status() >= 400) badStatus.push(`${r.status()} ${r.url()}`); });

  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  await page.getByTestId('nav-market-status').click();
  await page.waitForSelector('[data-testid="market-status-page"]', { timeout: 25000 });
  await page.waitForTimeout(3500);   // کارت‌ها و نمودارها باِ query می‌آیند

  const geom = await page.evaluate(() => {
    const px = (el: Element | null) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { top: Math.round(r.top + window.scrollY), height: Math.round(r.height),
        width: Math.round(r.width) };
    };
    const secs = Array.from(document.querySelectorAll('[data-testid="market-status-page"] > section'))
      .map((s, i) => {
        const h = s.querySelector('h2, h3');
        return { i, id: s.querySelector('[id]')?.id ?? null,
          title: (h?.textContent ?? '').trim().slice(0, 46), ...px(s) ?? {} };
      });
    const marks = ['status-ticker', 'ms-glance', 'ms-index-cards', 'ms-treemap',
      'ms-compare', 'ms-gold', 'ms-toplists', 'ms-orders'].map((t) => ({ testId: t,
      box: px(document.querySelector(`[data-testid="${t}"]`)) }));
    return { secs, marks, docHeight: Math.round(document.body.scrollHeight),
      overflowX: document.documentElement.scrollWidth > window.innerWidth + 1,
      scrollW: document.documentElement.scrollWidth };
  });

  await page.screenshot({ path: `${OUT}/${TAG}-first-${width}.png`, fullPage: false });
  await page.screenshot({ path: `${OUT}/${TAG}-full-${width}.png`, fullPage: true });
  report.runs.push({ width, ...geom, errors, badStatus: badStatus.slice(0, 12) });
  console.log(`\n== ${width}px == ارتفاعِ کلِ صفحه: ${geom.docHeight}`
    + (geom.overflowX ? `  !! افقی سرریز دارد (${geom.scrollW})` : ''));
  for (const s of geom.secs) {
    console.log(`   ${String(s.i).padStart(2)} ${(s.id ?? '—').padEnd(18)}`
      + ` top=${String(s.top).padStart(5)} h=${String(s.height).padStart(5)}  ${s.title ?? ''}`);
  }
  for (const m of geom.marks) {
    if (m.box) console.log(`   · ${m.testId.padEnd(20)} top=${m.box.top} h=${m.box.height}`);
    else console.log(`   · ${m.testId.padEnd(20)} — درِ این صفحه نیست`);
  }
  if (errors.length) console.log('   خطاها: ' + errors.slice(0, 4).join(' | '));
  if (badStatus.length) console.log('   پاسخِ بد: ' + badStatus.slice(0, 4).join(' | '));
  await ctx.close();
}

await browser.close();
writeFileSync(`${OUT}/${TAG}-layout.json`, JSON.stringify(report, null, 1), 'utf-8');
console.log('\nنوشته شد: ' + OUT + '/' + TAG + '-layout.json');
