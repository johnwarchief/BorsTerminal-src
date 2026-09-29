/**
 * tools/ta_page_read.mts — چه عددی رویِ صفحۀ «بازار» تریدرزآرنا می‌نشیند؟
 *
 * چرا: مقایسۀ عددیِ برنامه با تریدرزآرنا بدونِ دانستنِ «برچسبِ هر عدد در UI»
 * حدس است. فیدِ خامِ `/data/market0` بی‌نامِ فارسی است؛ این اسکریپت همان
 * متنِ رویِ صفحه را با همان لحظه بیرون می‌آورد تا تطبیقِ عدد↔برچسب کردنی باشد.
 *
 * فقط خواندنی: نشستِ تازهٔ بی‌نام‌کاربر، بدونِ لاگین، بدونِ کلیکِ تغییردهنده.
 *
 *   JEV_CHROME=… MSYS_NO_PATHCONV=1 node --experimental-strip-types \
 *     tools/ta_page_read.mts --url https://tradersarena.ir/market --out _audit/ta_page.json
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';

const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const CHROME = process.env.JEV_CHROME ?? '';
const imp = (rel: string) => import(`file:///${PKG}/${rel}`.replace(/\\/g, '/'));
const { chromium } = await imp('node_modules/playwright/index.mjs');

const arg = (n: string, f = ''): string => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const URL_ = arg('url', 'https://tradersarena.ir/market');
const OUT = arg('out', '_audit/ta_page.json');
const WAIT = Number(arg('wait', '9000'));

const browser = await chromium.launch({ headless: true, executablePath: CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();
const reqs: string[] = [];
page.on('request', (r: any) => {
  const u = r.url();
  if (u.includes('/data/') || u.includes('tradersarena')) reqs.push(u);
});
let err = '';
try {
  await page.goto(URL_, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(WAIT);
} catch (e: any) { err = String(e).slice(0, 200); }

// برچسب↔مقدار: هر گرهٔ کوچکِ حاویِ عدد، با متنِ برچسبِ والد/خواهر
const cells = await page.evaluate(() => {
  const out: { label: string; value: string }[] = [];
  const numRe = /[۰-۹0-9][۰-۹0-9.,]*\s*(همت|میلیارد|هزار میلیارد|درصد|٪|رئال|ریال|تومان)?/;
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
  let n: HTMLElement | null;
  while ((n = walk.nextNode() as HTMLElement | null)) {
    if (n.children.length > 2) continue;
    const t = (n.textContent || '').trim();
    if (t.length === 0 || t.length > 90) continue;
    if (!numRe.test(t)) continue;
    const label = (n.previousElementSibling?.textContent || '').trim().slice(0, 60);
    out.push({ label: label || (n.parentElement?.textContent || '').trim().slice(0, 60), value: t });
  }
  const seen = new Set<string>();
  return out.filter((c) => { const k = c.label + '|' + c.value; if (seen.has(k)) return false; seen.add(k); return true; }).slice(0, 220);
});
const title = await page.title();
const bodyHead = (await page.evaluate(() => document.body.innerText.slice(0, 3000)));
await page.screenshot({ path: OUT.replace(/\.json$/, '.png'), fullPage: false });
await browser.close();

const json = { url: URL_, at: new Date().toISOString(), title, err,
               requests: reqs.slice(0, 40), cells, bodyHead };
mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(json, null, 1), 'utf-8');
console.log(JSON.stringify({ at: json.at, title, err, cells: cells.length,
                             screenshot: OUT.replace(/\.json$/, '.png') }));
