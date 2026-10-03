/**
 * tools/jev_tf_degrade_check.mts — اثباتِ زندهٔ «تنزلِ بازۀ بی‌منبع» (کار #73 بخشِ ۲)
 *
 * یکِ قالبِ کهنه درِ localStorage می‌نشیند که بازۀ `1m` می‌خواهد — دقیقاً همان
 * حالتی که پیش از این بی‌سکوتِ بی‌نشانه نادیده گرفته می‌شد. انتظار:
 *  ۱) چارت رویِ روزانه می‌ماند (دکمۀ فعالِ نوارِ بازه «روزانه» است)،
 *  ۲) یادداشتِ `chart-timeframe-note` با دلیلِ «منبعِ داده ندارد» دیدنی می‌شود،
 *  ۳) هیچ برچسبِ دقیقه‌ای رویِ محور نمی‌نشیند (کنترلِ منفیِ متن).
 * اجرا:
 *   JEV_CHROME=… MSYS_NO_PATHCONV=1 node --experimental-strip-types \
 *     tools/jev_tf_degrade_check.mts --url http://127.0.0.1:8002/ --out _audit/tf_degrade.json
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const arg = (n: string, f = ''): string => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};

const BASE = arg('url', 'http://127.0.0.1:8002/');
const SYMBOL = arg('symbol', 'فولاد');
const OUT = arg('out', '_audit/tf_degrade.json');
const WAIT = Number.parseInt(arg('wait', '12000'), 10);
const CHROME = process.env.JEV_CHROME ?? '';

const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const browser = await chromium.launch({
  ...(CHROME ? { executablePath: CHROME } : {}),
  args: ['--no-sandbox', '--disable-gpu'],
});
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1000 } });
await ctx.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
    localStorage.setItem(
      ['fts', 'chart', 'templates', 'v1'].join('.'),
      JSON.stringify({
        templates: [{
          id: 'tfprobe', name: 'کهنهٔ بازۀِ ۱m', indicators: ['VOL'],
          timeframe: '1m', candleType: 'candle_solid', adjustment: 'performance',
          priceScale: 'normal', createdAt: 1,
        }],
      }),
    );
  } catch {
    /* پوستهٔ بدونِ دروازه هم همین را می‌پذیرد */
  }
});
const page = await ctx.newPage();
const report: Record<string, unknown> = { base: BASE, symbol: SYMBOL };

try {
  await page.goto(`${BASE}#/technical/${encodeURIComponent(SYMBOL)}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(WAIT);

  await page.getByTitle('پنل اندیکاتورها').click();
  await page.waitForTimeout(400);
  await page.getByTestId('template-apply-tfprobe').click();
  await page.waitForTimeout(700);

  report.afterApply = await page.evaluate(() => {
    const note = document.querySelector('[data-testid="chart-timeframe-note"]');
    const active = Array.from(document.querySelectorAll('.nn-btn.active')).map((b) =>
      (b.textContent ?? '').replace(/\s+/g, ' ').trim());
    // «ادعایِ دقیقه‌ای» فقط درِ متنِ مالکِ برنامه معنا دارد. خودِ یادداشتِ تنزل
    // (و ردیفِ قالبِ ذخیره‌شده) این واژه‌ها را عمداً می‌آورند، پس از پیمایش
    // بیرون‌اند. پیمایش رویِ برگ‌هاست تا جملهٔ والد دوباره شمرده نشود.
    // محورِ زمانِ چارت رویِ بوم رسم می‌شود، پس درِ DOM نیست؛ سنجیدنی همین است.
    const hits: string[] = [];
    for (const el of Array.from(document.querySelectorAll('body *'))) {
      if (note && (el === note || note.contains(el) || el.contains(note))) continue;
      if (el.closest('[data-testid^="template-"]')) continue;
      if (el.children.length > 0) continue;
      const t = (el.textContent ?? '').replace(/\s+/g, ' ').trim();
      if (t && /(دقیقه|ساعتی|hourly|[0-9۰-۹]m\b)/.test(t)) hits.push(t.slice(0, 48));
    }
    return {
      noteText: note ? (note.textContent ?? '').replace(/\s+/g, ' ').trim() : null,
      noteTitle: note ? note.getAttribute('title') : null,
      activeButtons: active,
      minuteLabelsOnScreen: hits.slice(0, 6),
    };
  });
  const r = report.afterApply as { noteText: string | null; activeButtons: string[]; minuteLabelsOnScreen: string[] };
  report.verdict = {
    note_visible: !!r.noteText && r.noteText.includes('منبع'),
    note_names_the_requested_range: !!r.noteText && r.noteText.includes('1m'),
    still_daily: r.activeButtons.some((b) => b.includes('روزانه')),
    no_minute_axis_claim: r.minuteLabelsOnScreen.length === 0,
  };
} catch (e) {
  report.error = String(e).slice(0, 300);
} finally {
  await page.screenshot({ path: OUT.replace(/json$/, 'png') }).catch(() => {});
  await browser.close();
}
mkdirSync(OUT.split('/')[0] ?? '_audit', { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf-8');
console.log(JSON.stringify(report.verdict ?? { error: report.error }, null, 1));
console.log(JSON.stringify(report.afterApply, null, 1).slice(0, 700));
process.exit(report.error ? 1 : 0);
