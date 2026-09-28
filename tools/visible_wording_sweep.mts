// tools/visible_wording_sweep.mts — جاروبِ متنِ دیدنی: هیچ استعارۀ «درِ» در رابط نماند
//
// مالک پرسید «منظورت از در چیه؟» — این سنجش درِ مرورگر ثابت می‌کند که آن واژه و
// دو غلطِ اضافه‌ت («درِ میانگین»، «درِ بانک ریال») از متنِ دیدنی رفته‌اند، و
// سرشمارۀ قیف همان «مرحلۀ بنیادی» را می‌برد که جزوه می‌گوید.
//
//   JEV_CHROME='...chrome.exe' MSYS_NO_PATHCONV=1 \
//   node --experimental-strip-types tools/visible_wording_sweep.mts \
//     --url http://127.0.0.1:5173/ --out _audit/visible_wording.json
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
const OUT = arg('out', '_audit/visible_wording.json');
const WAIT = Number(arg('wait', '3500'));

const ROUTES = ['#/', '#/fundamental', '#/technical', '#/strategy-tree', '#/portfolio', '#/master'];
// «درِ» با اضافه‌ت تنها خواندۀ استعاره/غلطِ دستوری است؛ «در » ساده حرفِ اضافه است
const DOOR_RE = new RegExp('در' + String.fromCharCode(0x200c) + ' ', 'u');

const report: Record<string, unknown> = { base: BASE, routes: {}, errors: [], checks: [] };
const ck = (name: string, ok: boolean, detail: unknown = null) => {
  (report.checks as Record<string, unknown>[]).push({ name, ok, detail });
  return ok;
};

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const context = await browser.newContext({ viewport: { width: 1632, height: 950 } });
await context.addInitScript(() => {
  sessionStorage.setItem('bors_auth_session', 'true');
  localStorage.removeItem('bors-symbol');
});
const page = await context.newPage();
page.on('pageerror', (e: { message: string }) => (report.errors as string[]).push(`pageerror: ${e.message}`));
page.on('console', (m: { type: () => string; text: () => string; location: () => { url?: string } }) => {
  if (m.type() !== 'error') return;
  const url = m.location()?.url ?? '';
  if (url.endsWith('/favicon.ico')) return;
  (report.errors as string[]).push(`console: ${url} :: ${m.text().slice(0, 200)}`);
});

const hits: { route: string; where: string; text: string }[] = [];
for (const route of ROUTES) {
  await page.goto(BASE + route, { waitUntil: 'networkidle' });
  await page.waitForTimeout(WAIT);
  const found = await page.evaluate((reSrc: string) => {
    const re = new RegExp(reSrc, 'u');
    const out: { where: string; text: string }[] = [];
    const push = (where: string, raw: string | null | undefined) => {
      const t = (raw ?? '').replace(/\s+/g, ' ').trim();
      if (t && re.test(t)) out.push({ where, text: t.slice(0, 160) });
    };
    // متنِ دیدنی
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const el = (n as Text).parentElement;
      // offsetParent برایِ position:fixed هم null است، پس از checkVisibility
      // استفاده می‌شود؛ معیارِ درستِ «آیا کاربر این را می‌بیند».
      if (!el || !(el as HTMLElement).checkVisibility({ visibilityProperty: true })) continue;
      push('text:' + (el.tagName || '?'), (n as Text).nodeValue);
    }
    // متنِ راهنما که با hover دیده می‌شود، بخشِ دیدنیِ همان کنترل است
    for (const el of Array.from(document.querySelectorAll('[title],[data-hint],[aria-label]'))) {
      push('title:' + (el.getAttribute('data-testid') || el.tagName), el.getAttribute('title'));
      push('hint:' + (el.getAttribute('data-testid') || el.tagName), el.getAttribute('data-hint'));
    }
    return out;
  }, DOOR_RE.source);
  report.routes[route] = { doorHits: found.length, samples: found.slice(0, 6) };
  for (const f of found) hits.push({ route, ...f });
}

ck('هیچ «درِ» ای در متنِ دیدنیِ شش تب نمانده', hits.length === 0, hits.slice(0, 12));

// سرشمارۀ قیف: واژۀ جزوه («مرحلۀ بنیادی») به‌جای استعاره
await page.goto(BASE + '#/master', { waitUntil: 'networkidle' });
await page.waitForTimeout(WAIT);
const funnelText = await page.evaluate(() => {
  const bar = document.querySelector('[data-testid="funnel-prefs"]');
  return bar ? (bar.textContent ?? '').replace(/\s+/g, ' ').trim() : null;
});
report.funnelPrefs = funnelText;
ck('نوارِ تنظیمِ قیف «مرحلۀ بنیادی» را می‌برد', Boolean(funnelText && funnelText.includes('مرحلۀ بنیادی')), funnelText);
ck(
  'عبورِ نمادها به همان زبانِ «عبور می‌کند» نوشته می‌شود',
  Boolean(funnelText && /عبور می‌کند/.test(funnelText)),
  funnelText,
);

// ستون‌هایِ تابلو: راهنمایِ ستون نامِ متغیرِ TSETMC را با «در فیلترنویسی» می‌گوید
await page.goto(BASE + '#/', { waitUntil: 'networkidle' });
await page.waitForTimeout(WAIT);
const hints = await page.evaluate(() => {
  // سرستونِ تابلو th نیست: درِ [data-testid="tape-head"] هر ستون یک
  // button/span با title=راهنما است، پس همان‌جا خوانده می‌شود.
  const head = document.querySelector('[data-testid="tape-head"]');
  const get = (label: string) => {
    const el = head
      ? Array.from(head.querySelectorAll('[title]')).find((x) => (x.textContent ?? '').includes(label))
      : null;
    return el ? (el.getAttribute('title') ?? '') : '';
  };
  return { taghir: get('تغییر'), tedad: get('تعداد') };
});
report.columnHints = hints;
ck(
  'راهنمایِ «تغییر٪» متغیرِ plp را به فیلترنویسیِ TSETMC وصل می‌کند',
  hints.taghir.includes('plp') && hints.taghir.includes('فیلترنویسی'),
  hints,
);
ck(
  'راهنمایِ «تعداد» متغیرِ tno را به فیلترنویسیِ TSETMC وصل می‌کند',
  hints.tedad.includes('tno') && hints.tedad.includes('فیلترنویسی'),
  hints,
);

const failed = (report.checks as any[]).filter((c) => !c.ok);
report.verdict = failed.length === 0 && (report.errors as string[]).length === 0 ? 'PASS' : 'FAIL';
report.failed = failed.map((f) => f.name);
report.doorHits = hits;

mkdirSync(OUT.split('/').slice(0, -1).join('/'), { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2));
console.log(JSON.stringify({ verdict: report.verdict, failed: report.failed, errors: report.errors, doorHits: hits.slice(0, 8) }, null, 2));
await browser.close();
