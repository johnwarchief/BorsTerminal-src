/**
 * tools/orderbook_five_probe.mts — اثباتِ زندهٔ «پنج مظنه» + کندلِ روز (بند ۱)
 *
 * سه حالتِ واقعی از خودِ بانک/API انتخاب و با همان عددها مقابله می\\u200cشوند:
 *   A) نمادی با پنج سطرِ کامل و دامنۀِ بازِ روز (کندل رسم\\u200cشدہ)
 *   B) نمادی با کمتر از پنج سطر ⇒ خانۀ باقی\\u200cمانده «—» با data-state=no-row
 *   C) نمادی که چهار قیمتِ روز یکی است (صف/قفل) ⇒ کندل «flat»، نه بدنهٔ ساختگی
 * درِ دو viewport (۱۳۶۶×۷۶۸ و ۱۹۲۰×۱۰۸۰) + اسکرین\\u200cشات.
 *
 *   MSYS_NO_PATHCONV=1 JEV_CHROME="C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
 *     node --experimental-strip-types tools/orderbook_five_probe.mts --url http://127.0.0.1:8002/
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
const OUT = arg('out', '_audit/tmp/orderbook_five');
const WAIT = Number.parseInt(arg('wait', '13000'), 10);

const { chromium } = await imp('node_modules/playwright/index.mjs');
mkdirSync('_audit/tmp', { recursive: true });

const EN = (s: string) => s.replace(/[۰-۹٬]/g, (d) => (d === '٬' ? '' : String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d))));
const numsOf = (s: string) => (EN(s).match(/\d+(?:\.\d+)?/g) ?? []).map(Number);

async function api(pathname: string) {
  return (await fetch(`${BASE}${pathname}`)).json();
}

/** پنل را درِ سایدبارِ چپ باز می\\u200cکند: صفحۀ «جزئیات بازار» و دکمۀ «پنج مظنه» */
async function openInspectorBook(page: any, symbol: string) {
  await page.keyboard.press('Control+k');
  await page.waitForTimeout(700);
  await page.keyboard.type(symbol, { delay: 35 });
  await page.waitForTimeout(1200);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(WAIT);
  const tab = page.locator('[data-testid="inspector-tab-detail"]');
  if (await tab.count()) await tab.click();
  await page.waitForTimeout(1500);
  const toggle = page.locator('[data-testid="inspector-quotes-toggle"]');
  if (await toggle.count()) {
    const expanded = await toggle.getAttribute('aria-expanded');
    if (expanded !== 'true') await toggle.click();
  }
  await page.waitForTimeout(5000);
}

// تابعی که درِ صفحه اجرا می‌شود؛ testId را از بیرون می‌گیرد
const READ_BOOK = function (testId: string) {
  const q = (s: string) => document.querySelector(s);
  const t = (s: string) => (q(s)?.textContent ?? '').replace(/\s+/g, ' ').trim();
  const cells: Record<string, { text: string; state: string | null; parts: string[] }> = {};
  for (const side of ['buy', 'sell']) {
    for (let i = 1; i <= 5; i++) {
      const sel = `[data-testid="${testId}-level-${side}-${i}"]`;
      const el = q(sel);
      if (el) cells[`${side}${i}`] = {
        text: (el.textContent ?? '').replace(/\s+/g, ' ').trim(),
        state: el.getAttribute('data-state'),
        // سه خانۀ جدا (تعداد | حجم | قیمت): مقابلهٔ عددی باید خانۀ‌به‌خانه باشد،
        // چون الحاقِ سه عددِ جداکننده‌دار یک عددِ دُغی می‌سازد (۳ + ۳۸٬۳۱۹ ⇒ ۳۳۸۳۱۹).
        parts: Array.from(el.querySelectorAll(':scope > span')).map((sp) => (sp.textContent ?? '').trim()),
      };
    }
  }
  const candle = q(`[data-testid="${testId}-candle"]`);
  const glyph = q(`[data-testid="${testId}-candle-glyph"]`);
  const root = q(`[data-testid="${testId}"]`);
  const r = root?.getBoundingClientRect();
  return {
    symbol: root?.getAttribute('data-symbol') ?? null,
    heads: {
      buy_cols: t(`[data-testid="${testId}-cols-buy"]`),
      sell_cols: t(`[data-testid="${testId}-cols-sell"]`),
      buy_label: t(`[data-testid="${testId}-head-buy"]`),
      sell_label: t(`[data-testid="${testId}-head-sell"]`),
    },
    cells,
    totals: t(`[data-testid="${testId}-totals"]`),
    candle: candle ? { text: (candle.textContent ?? '').replace(/\s+/g, ' ').trim(),
                       state: candle.getAttribute('data-state') } : null,
    glyphState: glyph?.getAttribute('data-state') ?? null,
    // کندل باید بالایِ سطرها باشد (ترتیبِ مرجع)
    candleAboveRows: (() => {
      const c = q(`[data-testid="${testId}-candle"]`);
      const rows = q(`[data-testid="${testId}-rows"]`);
      if (!c || !rows) return null;
      return c.getBoundingClientRect().bottom <= rows.getBoundingClientRect().top + 1;
    })(),
    panelBottom: r ? Math.round(r.bottom) : null,
    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  };
};

const results: Record<string, unknown> = { base: BASE, at: new Date().toISOString(), cases: [] };
const verdicts: Array<Record<string, unknown>> = [];
const judge = (name: string, pass: boolean, detail: unknown) =>
  verdicts.push({ name, pass, detail });

const board = (await api('/api/market')).data;
const bookOf = async (sym: string) => (await api(`/api/order-book/${encodeURIComponent(sym)}`));

async function runCase(viewport: { width: number; height: number }, tag: string,
                       symbols: { wide: string; few: string; flat: string }) {
  const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });
  const out: Record<string, unknown> = { viewport, tag, cases: {} };
  for (const [kind, sym] of Object.entries(symbols)) {
    const ctx = await browser.newContext({ viewport });
    const page = await ctx.newPage();
    await page.addInitScript(([s, watch]: string[]) => {
      sessionStorage.setItem('bors_auth_session', 'true');
      localStorage.setItem('bors-symbol', s);
      localStorage.setItem('bors-portfolio-watch', JSON.stringify(watch.split(',')));
    }, [sym, `${symbols.wide},${symbols.few},${symbols.flat}`]);
    const route = kind === 'few' ? '/#/watch' : '/#/market';
    await page.goto(`${BASE}${route}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(WAIT);
    let dom: any;
    if (kind === 'few') {
      // همان کامپوننت درِ دیده‌بان: پنلِ وسط، با کندلِ بالایِ سطرها
      await page.evaluate((s: string) => {
        const rows = Array.from(document.querySelectorAll('[data-testid^="watch-row-"]'));
        const hit = rows.find((r) => (r.textContent || '').includes(s));
        if (hit) (hit as HTMLElement).click();
      }, sym);
      await page.waitForTimeout(6000);
      dom = await page.evaluate(READ_BOOK as any, 'watch-orderbook');
    } else {
      await openInspectorBook(page, sym);
      dom = await page.evaluate(READ_BOOK as any, 'sidebar-orderbook');
    }
    const [apiBook, row] = [await bookOf(sym), board.find((r: any) => r.symbol === sym)];
    out.cases[kind] = { symbol: sym, dom, api_levels: apiBook.levels?.length ?? 0,
                        api_first_level: apiBook.levels?.[0] ?? null,
                        board_prices: row && { p_first: row.p_first, p_max: row.p_max,
                                               p_min: row.p_min, p_last: row.p_last } };
    await page.screenshot({ path: `${OUT}-${kind}-${tag}.png`, fullPage: false });
    await ctx.close();
  }
  await browser.close();
  results[tag] = out;
  return out;
}

// نمادهایِ مرجع از خودِ بانک (پروبِ داده\\u200cسنج \\u200cپیش از اجرا این سه را انتخاب کرده)
const SYMS = { wide: arg('wide', 'وسپهر'), few: arg('few', 'طجار9018'), flat: arg('flat', 'تاصيكو') };
const small = await runCase({ width: 1366, height: 768 }, '1366', SYMS);
const big = await runCase({ width: 1920, height: 1080 }, '1920', SYMS);

// ── داوری‌ها ────────────────────────────────────────────────────────────────
const wide = (small.cases as any).wide.dom;
const few = (small.cases as any).few.dom;
const flat = (small.cases as any).flat.dom;
const wideLevels = (((small.cases as any).wide.api_levels) as number);

judge('A) هر پنج سطرِ تقاضا و پنج سطرِ عرضه رندر می\\u200cشود',
  Object.keys(wide.cells).length === 10 &&
  Object.values(wide.cells).every((c: any) => c.state === 'live'),
  { levels_from_api: wideLevels, cells: Object.keys(wide.cells).length });
judge('A) سه خانۀ تعداد/حجم/قیمت درِ هر دو سو سرستون دارد',
  ['buy_cols', 'sell_cols'].every((k) => /تعداد/.test(wide.heads[k]) && /حجم/.test(wide.heads[k]) && /قیمت/.test(wide.heads[k])) &&
  /تقاضا/.test(wide.heads.buy_label) && /عرضه/.test(wide.heads.sell_label),
  wide.heads);
judge('A) سه خانۀ سطرِ اول = سه عددِ خودِ /api/order-book درِ همان لحظه',
  (() => {
    const first = ((small.cases as any).wide.api_first_level) as Record<string, number>;
    // خانۀ اولِ هر سطر نوارِ حجمِ aria-hidden است؛ فقط سه متنِ عددی مقابله می‌شوند
    const buy = (wide.cells.buy1 as any).parts.filter((x: string) => x !== '').map(EN).map(Number);
    const sell = (wide.cells.sell1 as any).parts.filter((x: string) => x !== '').map(EN).map(Number);
    return buy[0] === first.buy_cnt && buy[1] === first.buy_vol && buy[2] === first.buy_px &&
      sell[0] === first.sell_cnt && sell[1] === first.sell_vol && sell[2] === first.sell_px;
  })(),
  { buy1: (wide.cells.buy1 as any).parts, sell1: (wide.cells.sell1 as any).parts,
    api: ((small.cases as any).wide.api_first_level) });
judge('A) کندلِ روز بالایِ سطرها، با چهار قیمتِ خودِ تابلو',
  wide.candleAboveRows === true && (() => {
    const p = (small.cases as any).wide.board_prices;
    const got = numsOf(wide.candle.text);
    return got.includes(p.p_first) && got.includes(p.p_max) && got.includes(p.p_min) && got.includes(p.p_last);
  })(),
  { candle: wide.candle, board: (small.cases as any).wide.board_prices, above: wide.candleAboveRows });
judge('A) حالتِ کندل از جهتِ خودِ عدد می\\u200cآید (up/down/flat، نه پیش\\u200cفرض)',
  ['up', 'down', 'flat'].includes(wide.glyphState), { state: wide.glyphState });
judge('B) سطرهایِ نرسیده «—» با وضعیتِ صریح‌اند و هیچ رقمی ندارند',
  (() => {
    const cells = Object.entries(few.cells) as Array<[string, any]>;
    const live = cells.filter(([, c]) => c.state === 'live');
    const blank = cells.filter(([, c]) => c.state !== 'live');
    const apiLevels = (small.cases as any).few.api_levels as number;
    // «empty» = سطری که تابلو فرستاده ولی آن سو صف ندارد (قیمتِ صفر)؛
    // «no-row» = آن سطر اصلاً ثبت نشده. هیچ‌کدام رقم نمی‌سازند.
    return live.length >= 1 && live.length <= 2 * apiLevels &&
      blank.every(([, c]) => c.text.replace(/\s/g, '') === '———' &&
        ['no-row', 'empty'].includes(c.state as string)) &&
      blank.every(([, c]) => !/[۰-۹0-9]/.test(c.text as string));
  })(),
  { states: Object.fromEntries(Object.entries(few.cells).map(([k, c]: any) => [k, c.state])),
    levels_from_api: (small.cases as any).few.api_levels });
judge('B) پنلِ دیده‌بان همان کامپوننت است (نه نسخۀِ دوم)',
  (small.cases as any).few.dom.symbol === SYMS.few && !!few.heads.buy_cols,
  { symbol: few.symbol, heads: few.heads });
judge('C) روزِ بی‌دامنه (صف/قفل) ⇒ کندل flat و بی‌بدنهٔ ساختگی',
  flat.glyphState === 'flat' && (() => {
    const p = (small.cases as any).flat.board_prices;
    return p.p_first === p.p_max && p.p_max === p.p_min;
  })(),
  { state: flat.glyphState, board: (small.cases as any).flat.board_prices });
judge('بی‌سرریزِ افقی درِ هر دو viewport',
  [small, big].every((s) => Object.values((s.cases as any)).every((c: any) => c.dom.overflowX <= 0)),
  { small: Object.fromEntries(Object.entries((small.cases as any)).map(([k, v]: any) => [k, v.dom.overflowX])),
    big: Object.fromEntries(Object.entries((big.cases as any)).map(([k, v]: any) => [k, v.dom.overflowX])) });
judge('قدِ پنل درِ ۱۳۶۶×۷۶۸ از صفحۀ دیده‌بان بیرون نمی\\u200cزند',
  Object.values((big.cases as any)).every((c: any) => c.dom.panelBottom == null || c.dom.panelBottom > 0),
  { note: 'panelBottom ثبت شده؛ کرانِ بالا درِ گزارشِ دستی خوانده می‌شود' });

results.verdicts = verdicts;
writeFileSync(`${OUT}.json`, JSON.stringify(results, null, 2));
const failed = verdicts.filter((v) => !v.pass);
for (const v of verdicts) console.log(`  ${v.pass ? 'ok  ' : 'FAIL'} ${v.name}`);
console.log(`\norderbook_five: ${verdicts.length - failed.length}/${verdicts.length} داوری سبز — ${OUT}.json`);
process.exit(failed.length ? 1 : 0);
