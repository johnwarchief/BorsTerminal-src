// tools/node223_tree_probe.mts — شاهدِ زندهٔ #223: سه گرهٔ درخت به واژۀ خودِ جزوه رسیدند
//
//   1) سه برچسبِ تازه در بومِ SVG دیده می‌شوند و ادعاهایِ بی‌منبع (DPS/مجمع/
//      سود انباشته/R1/ذخیرۀ سود) دیگر در هیچ‌جای تب نیستند.
//   2) با کلیک روی گرهٔ «شاخص ۵» پنلِ نما «دستوری نباشد» را نشان می‌دهد.
//   3) پیچِ درصدِ فروش درِ پنل، برچسبِ گره را زنده تغییر می‌دهد (۵۰٪ ← ۳۰٪).
//   4) هیچ متنِ SVG از کادرِ بوم بیرون نمی‌زند (در سه رزولوشن) — برچسب‌ها کوتاه شدند.
//
//   JEV_CHROME='C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' \
//   MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/node223_tree_probe.mts \
//     --url http://127.0.0.1:5173/ --out _audit/node223_tree.json
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');

const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};
const BASE = arg('url', 'http://127.0.0.1:5173/');
const OUT = arg('out', '_audit/node223_tree.json');
const WAIT = Number(arg('wait', '22000'));
const FA = '۰۱۲۳۴۵۶۷۸۹';
const fa = (n: string) => Array.from(n).map((d) => (/[0-9]/.test(d) ? FA[+d] : d)).join('');

const report: Record<string, unknown> = { base: BASE, steps: {}, errors: [], checks: [] };
const ck = (name: string, ok: boolean, detail: unknown = null) => {
  (report.checks as Record<string, unknown>[]).push({ name, ok, detail });
  return ok;
};

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const context = await browser.newContext({ viewport: { width: 1632, height: 950 } });
await context.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
    localStorage.removeItem('bors-symbol');
    localStorage.removeItem('fts.strategy.custom_parameters.v2');
  } catch {
    /* دروازۀ محلی */
  }
});
const page = await context.newPage();
page.on('pageerror', (e: { message: string }) => (report.errors as string[]).push(`pageerror: ${e.message}`));
page.on('console', (m: { type: () => string; text: () => string; location: () => { url?: string } }) => {
  if (m.type() !== 'error') return;
  const url = m.location()?.url ?? '';
  if (url.endsWith('/favicon.ico')) return; // سرو dev هیچ آیکونی ندارد؛ در اپِ نصبی ۲۰۰ می‌گیرد
  (report.errors as string[]).push(`console: ${url} :: ${m.text().slice(0, 200)}`);
});

await page.goto(`${BASE}#/strategy-tree`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="obsidian-strategy-canvas"]', { timeout: WAIT });
await page.waitForFunction(
  () => (document.body.textContent ?? '').includes('شاخص ۵'),
  {},
  { timeout: WAIT },
);

const SNAP = () =>
  page.evaluate(() => ({
    body: (document.body.textContent ?? '').replace(/\s+/g, ' '),
  }));

const s1 = await SNAP();
const body = s1.body;
ck('برچسبِ شاخص ۵ = نوع نرخ‌گذاری', body.includes('شاخص ۵: نوع نرخ\u200cگذاری'), body.match(/شاخص ۵[^.] {0,30}/)?.[0] ?? null);
ck('برچسبِ خروج = فروش ۵۰٪ در اولین سقف', body.includes(`فروش ${fa('50')}٪ در اولین سقف`), body.match(/💰[^🏔]{0,40}/)?.[0] ?? null);
ck('برچسبِ ریسک = R/R کم ➔ ریسک بالا', body.includes('R/R کم'), body.match(/⚖[^📊]{0,40}/)?.[0] ?? null);
for (const bad of ['DPS', 'سود انباشته', 'مجمع', 'R1', 'ذخیره سود', '۱ به ۲']) {
  ck(`«${bad}» دیگر در تبِ درخت نیست`, !body.includes(bad), body.split(bad)[1]?.slice(0, 60) ?? null);
}

// کلیک روی گرهٔ شاخص ۵ → پنلِ نما
const clickedFifth = await page.evaluate(() => {
  const texts = Array.from(document.querySelectorAll('#obsidian-strategy-canvas text, text'));
  const t = texts.find((e) => (e.textContent ?? '').includes('شاخص ۵'));
  if (!t) return false;
  (t.closest('g') ?? t).dispatchEvent(new MouseEvent('click', { bubbles: true }));
  return true;
});
await page.waitForTimeout(700);
const s2 = await SNAP();
ck('کلیک روی گرهٔ پنجم، حکمِ «دستوری نباشد» را در پنل نشان می‌دهد',
  clickedFifth && s2.body.includes('دستوری نباشد') && s2.body.includes('حجم انبار'),
  s2.body.match(/جزوه صفت[^.]{0,160}/)?.[0] ?? null);

// کلیک روی گرهٔ خروج + پیچِ درصد
const clickedExit = await page.evaluate(() => {
  const texts = Array.from(document.querySelectorAll('text'));
  const t = texts.find((e) => (e.textContent ?? '').includes('در اولین سقف'));
  if (!t) return false;
  (t.closest('g') ?? t).dispatchEvent(new MouseEvent('click', { bubbles: true }));
  return true;
});
await page.waitForTimeout(500);
const dial = await page.evaluate(() => {
  const btns = Array.from(document.querySelectorAll('button')).filter((b) =>
    (b.textContent ?? '').replace(/\s+/g, ' ').trim().startsWith('۳۰٪'),
  );
  if (!btns.length) return 'no ۳۰٪ button';
  btns[0].click();
  return 'clicked';
});
await page.waitForTimeout(700);
const s3 = await SNAP();
ck('گرهٔ خروج انتخاب شد', clickedExit, null);
ck(`پیچِ درصد، برچسبِ گره را زنده به ${fa('30')}٪ می‌برد`, dial === 'clicked' && s3.body.includes(`فروش ${fa('30')}٪ در اولین سقف`), {
  dial,
  label: s3.body.match(/💰[^🏔]{0,40}/)?.[0] ?? null,
});

// هیچ متنِ SVG از کادرِ بوم بیرون نمی‌زند — در سه رزولوشن
const overflow = await page.evaluate(() => {
  const canvas = document.querySelector('[data-testid="obsidian-strategy-canvas"]');
  if (!canvas) return { error: 'no canvas' };
  const c = canvas.getBoundingClientRect();
  const bad: string[] = [];
  canvas.querySelectorAll('text').forEach((t) => {
    const r = t.getBoundingClientRect();
    if (!r.width) return;
    const pad = 1;
    if (r.left < c.left - pad || r.right > c.right + pad || r.top < c.top - pad || r.bottom > c.bottom + pad) {
      bad.push(`${(t.textContent ?? '').slice(0, 28)} | left=${Math.round(r.left - c.left)} right=${Math.round(r.right - c.right)}`);
    }
  });
  return { texts: canvas.querySelectorAll('text').length, outOfBounds: bad };
});
report.overflow1632 = overflow;

await page.setViewportSize({ width: 1180, height: 900 });
await page.waitForTimeout(600);
const overflow1180 = await page.evaluate(() => {
  const canvas = document.querySelector('[data-testid="obsidian-strategy-canvas"]');
  if (!canvas) return { error: 'no canvas' };
  const c = canvas.getBoundingClientRect();
  let worstRight = 0;
  canvas.querySelectorAll('text').forEach((t) => {
    const r = t.getBoundingClientRect();
    if (r.width) worstRight = Math.max(worstRight, r.right - c.right);
  });
  return { worstRightOverflowPx: Math.round(worstRight) };
});
await page.setViewportSize({ width: 1920, height: 1080 });
await page.waitForTimeout(600);
const overflow1920 = await page.evaluate(() => {
  const canvas = document.querySelector('[data-testid="obsidian-strategy-canvas"]');
  if (!canvas) return { error: 'no canvas' };
  const c = canvas.getBoundingClientRect();
  let worstRight = 0;
  canvas.querySelectorAll('text').forEach((t) => {
    const r = t.getBoundingClientRect();
    if (r.width) worstRight = Math.max(worstRight, r.right - c.right);
  });
  return { worstRightOverflowPx: Math.round(worstRight) };
});
report.overflow1180 = overflow1180;
report.overflow1920 = overflow1920;
ck(
  'هیچ متنِ درختی از کادرِ بوم بیرون نمی‌زند (سه رزولوشن)',
  !(overflow as any).error &&
    (overflow as any).outOfBounds.length === 0 &&
    (overflow1180 as any).worstRightOverflowPx <= 0 &&
    (overflow1920 as any).worstRightOverflowPx <= 0,
  { at1632: (overflow as any).outOfBounds, at1180: overflow1180, at1920: overflow1920 },
);

await page.screenshot({ path: '_audit/node223_tree.png', fullPage: false });

const failed = (report.checks as any[]).filter((c) => !c.ok);
report.verdict = failed.length === 0 && (report.errors as string[]).length === 0 ? 'PASS' : 'FAIL';
report.failed = failed.map((f) => f.name);

mkdirSync(OUT.split('/').slice(0, -1).join('/'), { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2));
console.log(JSON.stringify({ verdict: report.verdict, failed: report.failed, errors: report.errors }, null, 2));
await browser.close();
