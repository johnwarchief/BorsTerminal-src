/** tools/screen_bar_probe.mts — سنجشِ زندهٔ چهار خواستۀ ۱۴۰۵-۰۷-۲۰
 *
 * ۱) سرستون و شمارش‌هایِ «غربالگری FTS» به لبۀِ چپِ صفحه رفته‌اند؛
 * ۲) هر هفت فیلتر درِ نوارِ بالایِ غربالگری عددِ زنده دارد و آن عدد با
 *    `stages.tape.filter_counts`ِ خودِ سرور می‌خواند (نه شمارشِ محلیِ مرورگر)؛
 * ۳) Custom و سازندۀ زنجیره برگشته‌اند و کلیکِ چیپ درِ Custom همان زنجیره را
 *    کم و زیاد می‌کند (دو نما، یک منبع)؛
 * ۴) درِ جدولِ «تحویل» نماد به تبِّ اصلیِ دیده‌بان اضافه می‌شود و همان نماد درِ
 *    دیده‌بان کارتِ نمودارِ چندصفحهای می‌گیرد: ورقۀِ اول دو شاخص، ورقۀِ دوم
 *    سه شاخصِ آخر — شاخصِ ۵ هیچ‌وقت تنها درِ یک کارت نمی‌نشیند؛
 * ۵) «مرحلِ جلسه» ازِ صفحۀِ وضعیتِ بازار رفته است.
 *
 * اجرا (همان harnessِ بقیۀ probeها؛ بکاندِ نامزد با BORS_NO_FETCH_LOOPS=1):
 *   node --experimental-strip-types tools/screen_bar_probe.mts --url http://127.0.0.1:8005
 */
import { pathToFileURL } from 'node:url';
import { writeFileSync } from 'node:fs';

const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:8005').replace(/\/$/, '');
const OUT = arg('out', '_audit/screen_bar_probe.json');
const SHOT = arg('shot', '_audit/screen_bar_probe.png');

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
const page = await ctx.newPage();
const sentBodies: Array<Record<string, unknown>> = [];
page.on('request', (r) => {
  if (!r.url().includes('/api/funnel') || r.method() !== 'POST') return;
  try { sentBodies.push(JSON.parse(r.postData() ?? '{}') as Record<string, unknown>); }
  catch { sentBodies.push({ unparsed: (r.postData() ?? '').slice(0, 80) }); }
});
await page.addInitScript(() => { sessionStorage.setItem('bors_auth_session', 'true'); });

const report: Record<string, unknown> = { base: BASE, checks: [] as string[] };
const check = (name: string, ok: boolean, detail = '') => {
  (report.checks as string[]).push(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`);
  console.log(`${ok ? '  ok  ' : ' FAIL '} ${name}${detail ? ` — ${String(detail).slice(0, 180)}` : ''}`);
};
const FA = (n: number | string) => String(n).split('').map((c) => /[0-9]/.test(c)
  ? String.fromCharCode(0x06f0 + Number(c)) : c).join('');

// ── ۱ و ۲) نوارِ بالایِ غربالگری ───────────────────────────────────────────
await page.goto(`${BASE}/#/master?stage=tape&preset=trend`, { waitUntil: 'domcontentloaded' });
for (let i = 0; i < 40; i++) {
  const has = await page.evaluate(() => !!document.querySelector('[data-testid="funnel-tape-chip-f_susp"]'));
  if (has) break;
  await page.waitForTimeout(2000);
}
await page.waitForTimeout(4000);

const align = await page.evaluate(() => {
  const el = document.querySelector('[data-testid="funnel-counts"]') as HTMLElement | null;
  if (!el) return null;
  const kids = Array.from(el.children) as HTMLElement[];
  if (!kids.length) return null;
  const r = el.getBoundingClientRect();
  const firstLeft = Math.min(...kids.map((k) => k.getBoundingClientRect().left));
  const lastRight = Math.max(...kids.map((k) => k.getBoundingClientRect().right));
  return { gapLeft: Math.round(firstLeft - r.left), gapRight: Math.round(r.right - lastRight) };
});
report.align = align;
check('سرستون و شمارش‌ها به لبۀِ چپِ صفحه چسبیده‌اند (فاصله‌شان سمتِ راست است)',
  !!align && align.gapLeft < 14 && align.gapRight > 60, JSON.stringify(align));

const chips = await page.evaluate(() => {
  const ids = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh', 'f_smart', 'f_legal'];
  return ids.map((id) => {
    const el = document.querySelector(`[data-testid="funnel-tape-chip-${id}"]`);
    const t = el?.getAttribute('title') ?? '';
    const m = t.match(/(\d[\d,٬]*)\s*نامزد از\s*(\d[\d,٬]*)/);
    return { id, text: el?.innerText?.trim() ?? null, named: m ? m[1] : null,
             saidTitle: /بی‌حکم/.test(t) };
  });
});
report.chips = chips;
check('هفت چیپ درِ نوارِ غربالگری هر کدام یک عدد دارند',
  chips.every((c) => c.text && /[()（]/.test(c.text) && /\d|[۰-۹]/.test(c.text ?? '')),
  JSON.stringify(chips.map((c) => c.text)));

const serverCounts = await page.evaluate(async () => {
  const r = await fetch('/api/funnel', {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ preset: 'trend', chain: [], logic: 'and', fund_mode: 'standard',
                           exceptions: {}, drop_suffix: true }),
  });
  const j = await r.json();
  return (j?.stages?.tape?.filter_counts ?? null) as Record<string, { matched: number }> | null;
});
report.serverCounts = serverCounts;
const one = await page.evaluate(() =>
  document.querySelector('[data-testid="funnel-tape-chip-f_susp"]')?.innerText ?? '');
const serverSusp = serverCounts?.f_susp?.matched ?? null;
check('عددِ چیپ با شمارشِ خودِ سرور می‌خواند (فرانت چیزی نمی‌شمارد)',
  serverSusp !== null && (one.includes(FA(serverSusp)) || one.includes(String(serverSusp))),
  `DOM="${one}" سرور=${serverSusp}`);

// ── ۳) Custom برگشته و چیپ همان زنجیره را ویرایش می‌کند ───────────────────
await page.goto(`${BASE}/#/master?stage=tape&preset=custom`, { waitUntil: 'domcontentloaded' });
for (let i = 0; i < 40; i++) {
  const has = await page.evaluate(() => !!document.querySelector('[data-testid="funnel-custom-builder"]'));
  if (has) break;
  await page.waitForTimeout(2000);
}
const builder = await page.evaluate(() => ({
  mode: !!document.querySelector('[data-testid="funnel-mode-custom"]'),
  builder: !!document.querySelector('[data-testid="funnel-custom-builder"]'),
  add: !!document.querySelector('[data-testid="funnel-chain-add"]'),
}));
report.builder = builder;
check('Custom و سازندۀ زنجیره درِ همان workspace برگشته‌اند',
  builder.mode && builder.builder && builder.add, JSON.stringify(builder));

let cursor = sentBodies.length;
await page.locator('[data-testid="funnel-tape-chip-f_jet"]').first().click({ timeout: 8000 });
for (let i = 0; i < 30 && sentBodies.length === cursor; i++) await page.waitForTimeout(2000);
const bodyCustom = sentBodies[sentBodies.length - 1] ?? null;
report.customBody = bodyCustom;
check('کلیکِ چیپ درِ Custom، همان زنجیره را به موتور می‌فرستد',
  JSON.stringify((bodyCustom as { chain?: string[] } | null)?.chain ?? []) === JSON.stringify(['f_jet']),
  JSON.stringify(bodyCustom));
const chainStore = await page.evaluate(() => {
  const raw = localStorage.getItem('fts.funnel.chain.v1');
  return raw ?? null;
});
report.chainStore = chainStore;
check('زنجیره درِ همان کلیدِ سازنده ذخیره می‌شود (دو نما، یک منبع)',
  (chainStore ?? '').includes('f_jet'), String(chainStore));

// ── ۴) «دیده‌بان+» درِ تحویل و کارتِ چندصفحهایِ دیده‌بان ───────────────────
await page.goto(`${BASE}/#/master?stage=handover&preset=trend`, { waitUntil: 'domcontentloaded' });
for (let i = 0; i < 40; i++) {
  const has = await page.evaluate(() => !!document.querySelector('[data-testid^="watch-action-"]'));
  if (has) break;
  await page.waitForTimeout(2000);
}
const watchBtn = await page.evaluate(() => {
  const el = document.querySelector('[data-testid^="watch-action-"]') as HTMLButtonElement | null;
  return el ? { id: el.getAttribute('data-testid'), text: el.innerText.trim() } : null;
});
report.watchBtn = watchBtn;
check('سطرهایِ «تحویل» دکمۀِ افزودن به دیده‌بان دارند', !!watchBtn, JSON.stringify(watchBtn));
if (watchBtn) {
  await page.locator(`[data-testid="${watchBtn.id}"]`).first().click({ timeout: 8000 });
  await page.waitForTimeout(700);
  const stored = await page.evaluate(() => localStorage.getItem('bors-portfolio-watch'));
  const flipped = await page.evaluate((id) =>
    document.querySelector(`[data-testid="${id}"]`)?.getAttribute('aria-pressed') ?? null, watchBtn.id);
  report.storedWatch = stored;
  report.flipped = flipped;
  const sym = (watchBtn.id ?? '').replace('watch-action-', '');
  check('کلیک، نماد را درِ فهرستِ دیده‌بان ذخیره می‌کند و دکمه «درِ دیده‌بان» می‌شود',
    (stored ?? '').includes(sym) && flipped === 'true', `${stored} · pressed=${flipped}`);
  await page.goto(`${BASE}/#/watch`, { waitUntil: 'domcontentloaded' });
  for (let i = 0; i < 40; i++) {
    const has = await page.evaluate(() => !!document.querySelector('[data-testid="watch-chart-deck"]'));
    if (has) break;
    await page.waitForTimeout(2000);
  }
  await page.waitForTimeout(3000);
  const deck1 = await page.evaluate(() => ({
    page: document.querySelector('[data-testid="watch-deck-page"]')?.innerText ?? null,
    tiles: document.querySelectorAll('[data-testid^="watch-ind-"]').length,
    chart: !!document.querySelector('[data-testid="watch-chart"]'),
  }));
  report.deck1 = deck1;
  check('ورقۀِ اولِ کارتِ نمودار دو شاخص دارد', deck1.tiles === 2 && deck1.chart,
    JSON.stringify(deck1));
  await page.locator('[data-testid="watch-deck-next"]').first().click({ timeout: 8000 });
  await page.waitForTimeout(2500);
  const deck2 = await page.evaluate(() => ({
    page: document.querySelector('[data-testid="watch-deck-page"]')?.innerText ?? null,
    tiles: document.querySelectorAll('[data-testid^="watch-ind-"]').length,
    hasFive: !!document.querySelector('[data-testid$="-5"]'),
  }));
  report.deck2 = deck2;
  check('ورقۀِ دوم سه شاخصِ آخر را می‌گذارد و شاخصِ ۵ تنها نمی‌ماند',
    deck2.tiles === 3 && deck2.hasFive, JSON.stringify(deck2));
}

// ── ۵) «مرحلِ جلسه» ازِ وضعیتِ بازار رفت ───────────────────────────────────
await page.goto(`${BASE}/#/market-status`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(6000);
const gone = await page.evaluate(() => ({
  phase: !!document.querySelector('[data-testid="status-session-phase"]'),
  text: document.body.innerText.includes('مرحلِ جلسه'),
  kept: !!document.querySelector('[data-testid="status-phases"]'),
}));
report.sessionPhase = gone;
check('«مرحلِ جلسه» حذف شد و «چرخشِ وضعیتِ نمادها» دست‌نخورده ماند',
  gone.phase === false && gone.text === false && gone.kept === true, JSON.stringify(gone));

await page.goto(`${BASE}/#/master?stage=tape&preset=trend`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(6000);
await page.screenshot({ path: SHOT, fullPage: false });
report.screenshot = SHOT;
writeFileSync(OUT, JSON.stringify(report, null, 1), 'utf-8');
const fails = (report.checks as string[]).filter((c) => c.startsWith('FAIL'));
console.log(`\n${(report.checks as string[]).length - fails.length}/${(report.checks as string[]).length} سبز — ${OUT}`);
await browser.close();
process.exit(fails.length ? 1 : 0);
