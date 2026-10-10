/**
 * tools/client_share_probe.mts — اثباتِ زندهٔ درصدِ حقیقی/حقوقی (بند ۲ مأموریت)
 *
 * هر حالت درِ *کانکستِ خودش* باز می‌شود: addInitScript رویِ هر ناوبری دوباره
 * localStorage را می‌نویسد، پس «تغییرِ نماد با setItemِ وسطِ کار» درِ همان
 * context بی‌اثر است (این خودِ پروب درِ دورِ اول همین کنترلِ منفی را گم کرد).
 *
 *   • کنترلِ مثبت: نمادی با ارزشِ مبدأ ⇒ عددِ رابط = عددِ API در همان لحظه،
 *     درِ سه surface (سایدبار، نوارِزمینه، دیدۀبان) و دو سمتِ مستقل.
 *   • کنترلِ منفی: نمادی بی‌ارزشِ مبدأ ⇒ «نامشخص»، و هیچ رقمی رویِ صفحه نیست.
 *   • کنترلِ رسیدن: aria-labelِ پنل باید همان نمادِ مرجع را بگوید — وگرنه
 *     «نامشخص» بی‌دلیلِ درست سبز می‌شود.
 *
 *   MSYS_NO_PATHCONV=1 JEV_CHROME="C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
 *     node --experimental-strip-types tools/client_share_probe.mts --url http://127.0.0.1:8002/ \
 *     --with-symbol عيار --without-symbol آرام
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const BASE = arg('url', 'http://127.0.0.1:8002/').replace(/\/$/, '');
const WITH = arg('with-symbol', 'عيار');
const WITHOUT = arg('without-symbol', 'آرام');
const OUT = arg('out', '_audit/tmp/client_share');

const { chromium } = await imp('node_modules/playwright/index.mjs');
mkdirSync('_audit/tmp', { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });

type Cell = { text: string; state: string | null; title: string | null } | null;
type Snap = {
  hash: string; inspectorLabel: string | null; overflowX: number;
  strip: Cell; stripBuy: Cell; stripSell: Cell;
  inspBuy: Cell; inspSell: Cell;
  watchSymbol: string | null; watchBuy: Cell; watchSell: Cell;
};

async function apiRow(sym: string): Promise<Record<string, unknown> | null> {
  const r = await fetch(`${BASE}/api/market`, { headers: { Accept: 'application/json' } });
  const j = (await r.json()) as { data: Array<Record<string, unknown>> };
  return j.data.find((x) => x.symbol === sym) ?? null;
}

const READ = (): Snap => {
  const q = (s: string) => document.querySelector(s);
  const txt = (el: Element | null) => (el?.textContent || '').replace(/\s+/g, ' ').trim();
  const st = (sel: string) => {
    const el = q(sel);
    return el ? { text: txt(el), state: el.getAttribute('data-state') ?? null,
                  title: el.getAttribute('title') ?? null } : null;
  };
  return {
    hash: location.hash,
    inspectorLabel: q('[data-shell="inspector"]')?.getAttribute('aria-label') ?? null,
    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    strip: st('[data-testid="strip-client-share"]'),
    stripBuy: st('[data-testid="strip-client-share-buy"]'),
    stripSell: st('[data-testid="strip-client-share-sell"]'),
    inspBuy: st('[data-testid="inspector-client-share-buy"]'),
    inspSell: st('[data-testid="inspector-client-share-sell"]'),
    watchSymbol: q('[data-testid="watch-summary"]')?.getAttribute('data-symbol') ?? null,
    watchBuy: st('[data-testid="watch-client-share-buy"]'),
    watchSell: st('[data-testid="watch-client-share-sell"]'),
  };
};

/** یک صفحۀ تازه با نمادِ مشخص (کانکستِ تازه = init scriptِ همان حالت). */
async function openAt(route: string, symbol: string, waitMs = 14000) {
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  await ctx.addInitScript(([sym, watch]: string[]) => {
    sessionStorage.setItem('bors_auth_session', 'true');
    localStorage.setItem('bors-symbol', sym);
    localStorage.setItem('bors-portfolio-watch', JSON.stringify(watch.split(',')));
  }, [symbol, `${WITH},${WITHOUT}`]);
  const page = await ctx.newPage();
  await page.goto(`${BASE}${route}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(waitMs);
  return { ctx, page };
}

const results: Record<string, unknown> = { base: BASE, at: new Date().toISOString(),
                                            with: WITH, without: WITHOUT };
const steps: Array<Record<string, unknown>> = [];
const verdicts: Array<Record<string, unknown>> = [];
const judge = (name: string, cond: boolean, detail: unknown) =>
  verdicts.push({ name, pass: cond, detail });

// ── کنترلِ مثبت ─────────────────────────────────────────────────────────────
const row1 = await apiRow(WITH);
const a1 = await openAt('/#/market', WITH, 15000);
const s1 = await a1.page.evaluate(READ);
steps.push({ case: 'with-value', symbol: WITH,
             api: row1 && { retail_buy_pct: row1.retail_buy_pct, legal_buy_pct: row1.legal_buy_pct,
                            retail_sell_pct: row1.retail_sell_pct, legal_sell_pct: row1.legal_sell_pct,
                            ctv_d: row1.ctv_d, pct_is_current: row1.pct_is_current,
                            pct_basis: row1.pct_basis },
             dom: s1 });
await a1.page.screenshot({ path: `${OUT}-with.png` });
await a1.ctx.close();

// ── کنترلِ منفی ─────────────────────────────────────────────────────────────
const row2 = await apiRow(WITHOUT);
const a2 = await openAt('/#/market', WITHOUT);
const s2 = await a2.page.evaluate(READ);
steps.push({ case: 'without-value', symbol: WITHOUT, api_has_value: row2?.retail_buy_pct != null,
             dom: s2 });
await a2.page.screenshot({ path: `${OUT}-without.png` });
await a2.ctx.close();

// ── دیدۀبان ────────────────────────────────────────────────────────────────
const a3 = await openAt('/#/watch', WITH);
let s3 = await a3.page.evaluate(READ);
if (s3.watchSymbol !== WITH) {
  await a3.page.evaluate((sym: string) => {
    const rows = Array.from(document.querySelectorAll('[data-testid^="watch-row-"]'));
    const hit = rows.find((r) => (r.textContent || '').includes(sym));
    if (hit) (hit as HTMLElement).click();
  }, WITH);
  await a3.page.waitForTimeout(6000);
  s3 = await a3.page.evaluate(READ);
}
const row3 = s3.watchSymbol ? await apiRow(s3.watchSymbol) : null;
steps.push({ case: 'watch', symbol: s3.watchSymbol,
             api: row3 && { retail_buy_pct: row3.retail_buy_pct,
                            retail_sell_pct: row3.retail_sell_pct,
                            pct_is_current: row3.pct_is_current },
             dom: s3 });
await a3.page.screenshot({ path: `${OUT}-watch.png` });
await a3.ctx.close();
results.steps = steps;

// ── داوری‌ها ────────────────────────────────────────────────────────────────
const faToEn = (t: string) => t.replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)));
const firstPct = (t: string | null | undefined): number | null => {
  const m = faToEn(t ?? '').match(/([\d.]+)٪/);
  return m ? Number.parseFloat(m[1]) : null;
};
const text = (x: Cell): string | null => x?.text ?? null;
const nval = (row: Record<string, unknown> | null, k: string): number | null =>
  row && typeof row[k] === 'number' ? (row[k] as number) : null;

judge('کنترلِ رسیدن (مثبت): پنلِ نماد همان نمادِ مرجع باز است',
  (s1.inspectorLabel ?? '').includes(WITH), { label: s1.inspectorLabel });
judge('سایدبار، سهمِ خرید = عددِ API',
  firstPct(text(s1.inspBuy)) === nval(row1, 'retail_buy_pct') && s1.inspBuy?.state === 'ok',
  { dom: text(s1.inspBuy), api: row1?.retail_buy_pct });
judge('سایدبار، سهمِ فروش = عددِ API',
  firstPct(text(s1.inspSell)) === nval(row1, 'retail_sell_pct') && s1.inspSell?.state === 'ok',
  { dom: text(s1.inspSell), api: row1?.retail_sell_pct });
judge('نوارِزمینۀ نماد همان عدد را می‌گوید (یک منبع، دو surface)',
  firstPct(text(s1.stripBuy)) === nval(row1, 'retail_buy_pct'),
  { strip: text(s1.stripBuy), api: row1?.retail_buy_pct });
judge('دو سمت مستقل‌اند: متنِ خرید و فروش یکی نیست',
  text(s1.inspBuy) !== text(s1.inspSell),
  { buy: text(s1.inspBuy), sell: text(s1.inspSell) });
judge('عددِ نشستِ پیشین با تاریخِ خودش خوانده می‌شود (بی‌جازدنِ زنده)',
  /۱۴۰۵[\/-]/.test(s1.inspBuy?.title ?? '') || nval(row1, 'pct_is_current') === 1,
  { title: s1.inspBuy?.title, pct_is_current: row1?.pct_is_current });
judge('کنترلِ رسیدن (منفی): پنلِ نمادِ بی‌مبدأ همان نماد باز است',
  (s2.inspectorLabel ?? '').includes(WITHOUT), { label: s2.inspectorLabel });
judge('نمادِ بی‌مبدأ ⇒ «نامشخص»، نه صفر',
  /نامشخص/.test(text(s2.inspBuy) ?? '') && !/[0-9۰-۹]/.test(text(s2.inspBuy) ?? ''),
  { dom: s2.inspBuy, api_has_value: row2?.retail_buy_pct != null });
judge('دیدۀبان: همان ستون‌ها، برایِ همان نماد، با همان عدد',
  s3.watchSymbol != null && firstPct(text(s3.watchBuy)) === nval(row3, 'retail_buy_pct'),
  { symbol: s3.watchSymbol, dom: text(s3.watchBuy), api: row3?.retail_buy_pct });
judge('بی‌سرریزِ افقی در ۱۳۶×۷۶۸ (تابلو و دیدۀبان)',
  s1.overflowX <= 0 && s3.overflowX <= 0, { market: s1.overflowX, watch: s3.overflowX });

results.verdicts = verdicts;
const failed = verdicts.filter((v) => !v.pass);
writeFileSync(`${OUT}.json`, JSON.stringify(results, null, 2));
console.log(JSON.stringify(verdicts.map((v) => `${v.pass ? 'ok  ' : 'FAIL'} ${v.name}`), null, 2));
console.log(`\n${verdicts.length - failed.length}/${verdicts.length} داوری سبز — json: ${OUT}.json`);
await browser.close();
process.exit(failed.length ? 1 : 0);
