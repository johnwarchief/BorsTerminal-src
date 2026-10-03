// tools/map_interaction_probe.mts — سنجشِ زندۀ تعاملِ «نقشۀ چهار صفحۀ FTS»
// چهار چیز را در مرورگر واقعی امتحان می‌کند (نه jsdom):
//   ۱) جمع‌کردنِ یک شاخه فقط سطرهایِ زیرِ همان شاخه را کم می‌کند و بقیه دست‌نخورده است
//   ۲) سوییچِ پرست، گره‌ها را جابه‌جا نمی‌کند؛ فقط ریلِ روشن عوض می‌شود
//   ۳) جست‌وجوی نماد، چیپِ وضعیتِ چهار فاز را رویِ Zoneهایِ خودش می‌نشاند
//   ۴) کلیک رویِ گره، پنلِ بازرسیِ همان گره را باز می‌کند (متنِ جزوه، نه اختراع)
//
//   JEV_CHROME='C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' \
//   MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/map_interaction_probe.mts \
//     --url http://127.0.0.1:8002/ --out _audit/map_live.json --symbol فولاد
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
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
const BASE = arg('url', 'http://127.0.0.1:8002/');
const OUT = arg('out', '_audit/map_live.json');
const SYMBOL = arg('symbol', 'فولاد');
const WAIT = Number(arg('wait', '14000'));

const report: Record<string, unknown> = { base: BASE, symbol: SYMBOL, checks: [], errors: [], shots: [] };
const ck = (name: string, ok: boolean, detail: unknown = null) => {
  (report.checks as Record<string, unknown>[]).push({ name, ok, detail });
  return ok;
};

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
await context.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
    localStorage.removeItem('fts.strategy.custom_parameters.v2');
    localStorage.removeItem('bors-symbol');
  } catch {
    /* دروازۀ محلی */
  }
});
const page = await context.newPage();
page.on('pageerror', (e: { message: string }) => (report.errors as string[]).push(`pageerror: ${e.message}`));
page.on('console', (m: { type: () => string; text: () => string }) => {
  if (m.type() === 'error') (report.errors as string[]).push(`console: ${m.text().slice(0, 160)}`);
});

const ROWS = () =>
  page.evaluate(() =>
    Array.from(document.querySelectorAll('[data-node-id]')).map((g) => ({
      id: g.getAttribute('data-node-id') as string,
      zone: g.getAttribute('data-node-zone') as string,
      rail: g.getAttribute('data-rail') === '1',
      lit: g.getAttribute('data-lit') === '1',
      y: Math.round((g.querySelector('rect') ?? g).getBoundingClientRect().top),
    })),
  );

await page.goto(`${BASE}#/strategy-tree`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-node-id="tape_volume"]', { timeout: WAIT });
await page.waitForTimeout(900);

const before = await ROWS();
ck('هفتاد‌وهشت سطرِ نقشه رسم شده (سی و سه سرِ شاخه + چهل‌وپنج گره)', before.length === 78, before.length);

// ۱) جمع‌کردنِ شاخۀ «انتخاب سبک معامله»
const collapsed = await page.evaluate(() => {
  const g = document.querySelector('[data-collapse-toggle="s_style"]');
  if (!g) return 'no toggle';
  g.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  return 'clicked';
});
await page.waitForTimeout(400);
const after = await ROWS();
const gone = before.map((r) => r.id).filter((id) => !after.some((r) => r.id === id));
ck('جمع‌کردنِ شاخه فقط سطرهایِ همان شاخه را برمی‌دارد', collapsed === 'clicked' && gone.sort().join() === 's_style_swing,s_style_trend', {
  collapsed,
  gone,
});
ck('بقیۀ سطرهایِ سه ستونِ دیگر جابه‌جا نشده‌اند',
  ['F', 'T', 'M'].every((z) => JSON.stringify(before.filter((r) => r.zone === z).map((r) => r.id)) === JSON.stringify(after.filter((r) => r.zone === z).map((r) => r.id))),
  null);
await page.evaluate(() => document.querySelector('[data-collapse-toggle="s_style"]')?.dispatchEvent(new MouseEvent('click', { bubbles: true })));
await page.waitForTimeout(300);

// ۲) سوییچِ پرست: ریل عوض می‌شود، جایِ گره‌ها نه
const trendClick = await page.evaluate(() => {
  const b = Array.from(document.querySelectorAll('button')).find((x) => (x.textContent ?? '').includes('روندگیر'));
  if (!b) return 'no preset button';
  b.click();
  return 'clicked';
});
await page.waitForTimeout(600);
const trend = await ROWS();
const railOf = (rows: { rail: boolean }[]) => rows.filter((r) => r.rail).map((r) => r.id);
ck('سوییچِ پرست جایِ سطرهایِ نقشه را عوض نمی‌کند',
  JSON.stringify(before.map((r) => [r.id, r.y])) === JSON.stringify(trend.map((r) => [r.id, r.y])),
  { trendClick, moved: trend.filter((r, i) => r.y !== before[i]?.y).map((r) => r.id).slice(0, 6) });
const trendRail = railOf(trend);
ck('ریلِ روندگیر: کف‌روبی + نقطه‌زنی + حد ضررِ بنیادی، و هیچ گرهٔ «خروج»ی',
  trendRail.includes('tape_floor_sweep') && trendRail.includes('setup_point_hunt') && trendRail.includes('stop_trend') && !trendRail.includes('exit_half'),
  trendRail);

// ۳) جست‌وجوی نماد درِ نوارِ ابزارِ همین صفحه → چیپِ چهار فاز رویِ Zoneها
const inp = page.locator('input[placeholder*="جستجوی نماد"]');
let typed = 'no search input';
if (await inp.count()) {
  await inp.first().click();
  await inp.first().fill(SYMBOL);
  typed = 'typed';
}
let picked = 'no suggestion';
const sug = page.locator('button', { hasText: SYMBOL }).first();
if (await sug.count()) {
  await sug.click();
  picked = 'clicked';
}
const plaqueSeen = await page
  .waitForSelector('[data-testid="graph-symbol-plaque"]', { timeout: WAIT })
  .then(() => true)
  .catch(() => false);
await page.waitForTimeout(1200);
const phases = await page.evaluate(() =>
  Array.from(document.querySelectorAll('[data-zone-frame]')).map((z) => `${z.getAttribute('data-zone-frame')}=${z.getAttribute('data-phase-status')}`),
);
ck('با انتخابِ نماد، هر چهار فاز رویِ Zoneیِ خودش وضعیت می‌گیرد',
  plaqueSeen && phases.length === 4 && phases.every((p) => p.includes('=')) && phases.some((p) => p.endsWith('=pass') || p.endsWith('=wait') || p.endsWith('=fail')),
  { typed, picked, phases });
const plaque = await page.evaluate(() => (document.querySelector('[data-testid="graph-symbol-plaque"]')?.textContent ?? '').slice(0, 220));
ck('پلاکِ نماد سطوحِ واقعی را نشان می‌دهد', /ورود/.test(plaque) && /حدضرر/.test(plaque), plaque.slice(0, 140));

// ۴) کلیک رویِ یک گره → پنلِ بازرسی
const clickedNode = await page.evaluate(() => {
  const g = document.querySelector('[data-node-id="crit_pricing_regime"]');
  if (!g) return 'no node';
  g.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  return 'clicked';
});
await page.waitForTimeout(500);
const panel = await page.evaluate(() => (document.body.textContent ?? '').replace(/\s+/g, ' '));
ck('کلیک رویِ گره، پنلِ همان گره را با متنِ جزوه باز می‌کند',
  clickedNode === 'clicked' && panel.includes('دستوری نباشد') && panel.includes('نوع نرخ‌گذاری'),
  panel.match(/رکن: بنیادی F[^.]{0,120}/)?.[0] ?? null);

const shot = OUT.replace(/\.json$/, '.png');
mkdirSync(dirname(shot), { recursive: true });
await page.screenshot({ path: shot, fullPage: false });
(report.shots as string[]).push(shot);
await browser.close();
writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf8');
const failed = (report.checks as { ok: boolean }[]).filter((x) => !x.ok).length;
console.log(`${(report.checks as unknown[]).length} سنجش — ${failed} ناکام`);
for (const c of report.checks as { name: string; ok: boolean; detail?: unknown }[]) {
  console.log(`${c.ok ? 'OK  ' : 'FAIL'} ${c.name}${c.ok ? '' : ' :: ' + JSON.stringify(c.detail).slice(0, 300)}`);
}
process.exit(failed ? 1 : 0);
