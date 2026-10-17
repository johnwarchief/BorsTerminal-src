// features/portfolio/lib/watchExport.ts — ستون‌هایِ خروجیِ «دیدهبانِ بازار»
//
// چرا یکِ فایلِ جدا: جدولِ دیدهبان سلول‌ها را به‌صورتِ JSX می‌سازد، ولی Excelِ
// واقعی به **عددِ تایپ‌شده** نیاز دارد نه رشتهٔ قالب‌بندی‌شده. اگر فهرستِ
// ستون‌ها دو جا نوشته شود، سرستون‌ها و داده از هم می‌افتند. پس اینجا یکِ
// توصیفِ ستون داریم (کلید، برچسبِ فارسی با واحدِ روشن، و خوانندۀ مقدار) که هم
// خروجی از آن ساخته می‌شود و هم گاردِ تست (`watch-export.spec.tsx`) برچسب‌هایش
// را با `<th>`هایِ رندرشدۀ خودِ جدول مقایسه می‌کند.
//
// سه قاعده که نقضشان یعنی خروجیِ دروغ:
//  • عدد، عدد می‌ماند (نه «۱٬۲۳۴»)؛ نبودِ داده `null` است، نه صفر و نه «—».
//  • واحد درِ سرستون نوشته شده: ریال، میلیارد ریال، میلیارد تومان،٪، سهم، نفر.
//  • نمادِ رصدشده‌ای که امروز ردیفی درِ تابلو ندارد حذف نمی‌شود؛ ستونِ
//    «در فیدِ تابلو؟» همان «نیست» را اعلام می‌کند.
import type { ExportCell, ExportTable } from '@shared/lib/tableExport';
import { MATRIX_STATE_LABEL, type MatrixState, type WatchMatrixRow } from '@shared/api/userWatchlist';
import type { MarketRow } from '@shared/types/marketRow';
import { normalizeFa } from '@shared/lib/normalizeFa';
import { patternBadges } from '@features/market/lib/tapeBadges';
import type { TapeFilterConfig } from '@features/market/lib/tapeAlgorithms';
import { hhmm, statusText } from './watchStatus';

/** دامنهٔ خروجی — سنجیده از قابلیتِ واقعیِ خودِ جدول (بی‌صفحه‌بندی؛ سقفِ فهرست ۶۰). */
export type WatchScope = 'selected' | 'visible' | 'all';
export type WatchColumnSet = 'board' | 'full';

export const SCOPE_LABEL: Record<WatchScope, string> = {
  selected: 'ردیف‌های انتخاب‌شده',
  visible: 'نتایجِ فیلترشده',
  all: 'کلِ دیدهبان',
};

export const COLSET_LABEL: Record<WatchColumnSet, string> = {
  board: 'ستون‌های دیدنیِ جدول',
  full: 'همهٔ ستون‌های قابل‌صدور',
};

export type WatchExportItem = {
  symbol: string;
  /** ردیفِ فیدِ تابلو؛ `null` یعنی این نمادِ رصدشده امروز ردیفی درِ تابلو ندارد */
  row: MarketRow | null;
  /** داوریِ ماتریسِ تأیید (تکنیکال/بنیادی) — همان منبعِ دو ستونِ جدول */
  matrix?: WatchMatrixRow;
};

type Reader = (row: MarketRow | null) => ExportCell;

/** قیمتِ روزانهٔ صفر «قیمتِ صفر» نیست. */
const UNPUBLISHED_PRICE_KEYS = new Set<keyof MarketRow>(['p_first', 'p_max', 'p_min']);

/** عددِ خام یا null — نه رشتهٔ فارسی، نه صفرِ جانشین.
 *
 *  سه خانۀ `p_first/p_max/p_min` را تابلو تا وقتی مبادله‌ای نیفتاده (یا منبع
 *  نهایه نکرده) صفر می‌فرستد: سنجشِ ۱۴۰۵-۰۷-۲۲ رویِ همین نشست ۱٬۳۴۰ ردیف با
 *  `pmx/pmn = 0` و ۱٬۳۶۳ ردیف با `pf = 0` داد، درحالی‌که هیچ‌کدام قیمتِ معتبر
 *  صفر نیستند. `FormingCandle` همین را می‌خواند و هندسه را `incomplete` می‌گذارد؛
 *  فایلِ خروجی هم باید همان حکم را بدهد: تهی، نه صفر. این حکم فعلاً درِ لایۀ
 *  خروجی است — بردنِ آن به لایۀ canonical (API) رأیِ مالک می‌خواهد، چون معنای
 *  «بی‌داده» درِ خودِ تابلو را عوض می‌کند (§۷ همان گزارش). */
function numOf(key: keyof MarketRow): Reader {
  return (row) => {
    const v = row == null ? null : (row[key] as unknown);
    if (typeof v !== 'number' || !Number.isFinite(v)) return null;
    if (v <= 0 && UNPUBLISHED_PRICE_KEYS.has(key)) return null;
    return v;
  };
}

function strOf(key: keyof MarketRow): Reader {
  return (row) => {
    const v = row == null ? null : (row[key] as unknown);
    return typeof v === 'string' && v !== '' ? v : null;
  };
}

/** برچسبِ «تکنیکال/بنیادی» به متنِ همان ستونِ جدول (بی‌واژۀ دوم) */
function pillarOf(it: WatchExportItem, pillar: 'tech' | 'fund'): ExportCell {
  const st = (it.matrix?.states?.[pillar] ?? it.matrix?.pillars?.[pillar]?.state) as MatrixState | undefined;
  return st && MATRIX_STATE_LABEL[st] ? MATRIX_STATE_LABEL[st] : null;
}

export const SOURCE_LABEL = 'TSETMC GetMarketWatch (همان فیدِ زندهٔ تابلو)';

export type WatchColumn = {
  key: string;
  label: string;
  set: WatchColumnSet;
  /** خوانندۀ مقدار ازِ ردیفِ فید؛ برایِ ستون‌هایِ محاسبه‌شده ازِ وضعیت/ماتریس خالی است */
  read?: Reader;
  /** برایِ ستون‌هایی که ازِ ماتریس، برچسب‌ها یا وضعیت ساخته می‌شوند */
  readItem?: (it: WatchExportItem, cfg: TapeFilterConfig | null) => ExportCell;
};

export const WATCH_COLUMNS: readonly WatchColumn[] = [
  // ── شناسایی ──
  { key: 'symbol', label: 'نماد', set: 'board', read: (r) => (r?.symbol ? String(r.symbol) : null) },
  { key: 'name', label: 'نام شرکت', set: 'board', read: strOf('name') },
  { key: 'ins_code', label: 'شناسۀ پایدار (insCode)', set: 'full', read: strOf('ins_code') },
  { key: 'sector', label: 'صنعت', set: 'full', read: strOf('sector_name') },
  { key: 'board', label: 'بازار (۱=بورس ۲=فرابورس)', set: 'full', read: numOf('board') },
  { key: 'in_feed', label: 'در فیدِ تابلو؟', set: 'full', read: (r) => (r ? 'هست' : 'نیست') },
  // ── قیمت و تغییر ──
  { key: 'p_last', label: 'آخرین معامله (ریال)', set: 'board', read: numOf('p_last') },
  { key: 'percent_change', label: 'تغییر پایانی (٪)', set: 'board', read: numOf('percent_change') },
  { key: 'p_closing', label: 'قیمت پایانی (ریال)', set: 'board', read: numOf('p_closing') },
  { key: 'p_first', label: 'اولین قیمت (ریال)', set: 'board', read: numOf('p_first') },
  { key: 'p_max', label: 'بیشترین قیمتِ معامله‌شده (ریال)', set: 'board', read: numOf('p_max') },
  { key: 'p_min', label: 'کمترین قیمتِ معامله‌شده (ریال)', set: 'board', read: numOf('p_min') },
  { key: 'percent_last', label: 'تغییرِ آخرین نسبت به دیروز (٪)', set: 'full', read: numOf('percent_last') },
  { key: 'price_yesterday', label: 'قیمت دیروز (ریال)', set: 'full', read: numOf('price_yesterday') },
  { key: 'tmin', label: 'کفِ مجاز قیمت (ریال)', set: 'full', read: numOf('tmin') },
  // ── حجم و ارزش ──
  { key: 'q_tot_tran', label: 'حجم (سهم)', set: 'board', read: numOf('q_tot_tran') },
  { key: 'z_tot_tran', label: 'تعداد معاملات (عدد)', set: 'board', read: numOf('z_tot_tran') },
  { key: 'q_tot_cap', label: 'ارزش معاملات (میلیارد ریال)', set: 'board',
    read: (r) => { const v = r?.q_tot_cap; return typeof v === 'number' && Number.isFinite(v) ? v / 1e9 : null; } },
  { key: 'q_tot_cap_rial', label: 'ارزش معاملات (ریال)', set: 'full', read: numOf('q_tot_cap') },
  // ── ارزش بازار ──
  { key: 'mcap', label: 'ارزش بازار (ریال)', set: 'board', read: numOf('mcap') },
  { key: 'mcap_bt', label: 'ارزش بازار (میلیارد تومان)', set: 'full',
    read: (r) => { const v = r?.mcap; return typeof v === 'number' && Number.isFinite(v) ? v / 1e10 : null; } },
  { key: 'mcap_src', label: 'منبع ارزش بازار', set: 'full', read: strOf('mcap_src') },
  { key: 'pe', label: 'P/E', set: 'full', read: numOf('pe') },
  // ── سفارش‌ها (سطرِ اولِ صف) ──
  { key: 'buy_q1_vol', label: 'حجم صف اول خرید (سهم)', set: 'board', read: numOf('buy_q1_vol') },
  { key: 'buy_q1_px', label: 'قیمت صف اول خرید (ریال)', set: 'board', read: numOf('buy_q1_px') },
  { key: 'sell_q1_px', label: 'قیمت صف اول فروش (ریال)', set: 'board', read: numOf('sell_q1_px') },
  { key: 'sell_q1_vol', label: 'حجم صف اول فروش (سهم)', set: 'board', read: numOf('sell_q1_vol') },
  { key: 'buy_q1_cnt', label: 'تعداد سفارش صف اول خرید (سفارش)', set: 'full', read: numOf('buy_q1_cnt') },
  // ── حقیقی/حقوقی ──
  { key: 'buy_i_vol', label: 'حجم خرید حقیقی (سهم)', set: 'full', read: numOf('buy_i_vol') },
  { key: 'sell_i_vol', label: 'حجم فروش حقیقی (سهم)', set: 'full', read: numOf('sell_i_vol') },
  { key: 'buy_count_i', label: 'تعداد خریدار حقیقی (نفر)', set: 'full', read: numOf('buy_count_i') },
  { key: 'sell_count_i', label: 'تعداد فروشنده حقیقی (نفر)', set: 'full', read: numOf('sell_count_i') },
  { key: 'buy_power_i', label: 'سرانه خرید (سهم به ازای هر نفر)', set: 'full', read: numOf('buy_power_i') },
  { key: 'sell_power_i', label: 'سرانه فروش (سهم به ازای هر نفر)', set: 'full', read: numOf('sell_power_i') },
  { key: 'buyer_power', label: 'قدرت خرید (سرانه خرید ÷ سرانه فروش — بی‌واحد)', set: 'full', read: numOf('buyer_power') },
  { key: 'retail_buy_pct', label: 'سهم حقیقی از ارزش خرید (٪)', set: 'full', read: numOf('retail_buy_pct') },
  { key: 'legal_buy_pct', label: 'سهم حقوقی از ارزش خرید (٪)', set: 'full', read: numOf('legal_buy_pct') },
  { key: 'retail_sell_pct', label: 'سهم حقیقی از ارزش فروش (٪)', set: 'full', read: numOf('retail_sell_pct') },
  { key: 'legal_sell_pct', label: 'سهم حقوقی از ارزش فروش (٪)', set: 'full', read: numOf('legal_sell_pct') },
  { key: 'pct_basis', label: 'مبنای درصد', set: 'full', read: strOf('pct_basis') },
  { key: 'ctv_kind', label: 'منبع ارزشِ مبدأ', set: 'full', read: strOf('ctv_kind') },
  { key: 'ctv_d', label: 'نشستِ عددِ درصد (YYYYMMDD)', set: 'full', read: numOf('ctv_d') },
  { key: 'pct_is_current', label: 'درصد از نشستِ خودِ تابلو؟', set: 'full',
    read: (r) => (r?.pct_is_current == null ? null : Number(r.pct_is_current) === 1 ? 'هست' : 'نیست') },
  // ── حجمِ تاریخی ──
  { key: 'vol_ratio', label: 'نسبت حجم به میانگین (برابر)', set: 'full', read: numOf('vol_ratio') },
  { key: 'vol_ratio_file', label: 'نسبت حجم به کفِ جزوه (برابر)', set: 'full', read: numOf('vol_ratio_file') },
  { key: 'vol_dod', label: 'حجم نسبت به دیروز (برابر)', set: 'full', read: numOf('vol_dod') },
  { key: 'month_avg_vol', label: 'میانگین حجم ۳۰ روزه (سهم)', set: 'full', read: numOf('month_avg_vol') },
  { key: 'hist_sessions', label: 'نشست‌های سابقه (عدد)', set: 'full', read: numOf('hist_sessions') },
  // ── وضعیت ──
  { key: 'status', label: 'وضعیت معاملاتی', set: 'board', readItem: (it) => statusText(it.row).text },
  { key: 'st_title', label: 'عنوانِ رسمیِ وضعیت', set: 'full', read: strOf('st_title') },
  { key: 'badges', label: 'برچسب‌های تابلو', set: 'board', readItem: (it, cfg) => {
      if (!it.row || !cfg) return null;
      const labels = patternBadges(it.row, cfg).filter((b) => b.filter).map((b) => b.label);
      return labels.length ? labels.join(' · ') : 'بی‌برچسب';
    } },
  { key: 'tech', label: 'تکنیکال', set: 'board', readItem: (it) => pillarOf(it, 'tech') },
  { key: 'fund', label: 'بنیادی', set: 'board', readItem: (it) => pillarOf(it, 'fund') },
  // ── تازگی و منشأ ──
  { key: 'row_h', label: 'ساعتِ خودِ ردیف (HH:MM)', set: 'board', read: (r) => (r ? hhmm(r.row_h) : null) },
  { key: 'is_live', label: 'زنده یا آخرینِ نشستِ بسته‌شده', set: 'full',
    read: (r) => (r?.is_live == null ? null : r.is_live ? 'زنده' : 'آخرینِ بسته‌شده') },
  { key: 'source', label: 'منبع داده', set: 'full', read: () => SOURCE_LABEL },
  { key: 'exported_at', label: 'زمانِ گرفتنِ خروجی', set: 'full', read: () => null },
];

/** ستون‌هایِ یکِ دستۀ انتخابی — «full» برابُرِ «board» به‌علاوهٔ بقیه است. */
export function columnsFor(set: WatchColumnSet): WatchColumn[] {
  return set === 'full' ? [...WATCH_COLUMNS] : WATCH_COLUMNS.filter((c) => c.set === 'board');
}

/** نگاشتِ «سرستونِ دیدنیِ جدول → ستونِ خروجی».
 *
 * رابط کوتاه می‌نویسد («حجم»، «تغییر٪») و فایلِ داده واحدِ روشن می‌خواهد
 * («حجم (سهم)»، «تغییر پایانی (٪)»)؛ این نقشه تنها جایی است که دو نام به هم
 * می‌رسند، و گاردِ `watch-export.spec.tsx` متنِ `<th>`هایِ رندرشدۀ خودِ جدول را
 * با کلیدهایِ همان مقایسه می‌کند — پس نه ستونی از دیدهبان بیرون می‌ماند و نه
 * ستونی از هوا ساخته می‌شود. «کندل روز» درِ فایل به چهار قیمتِ سازنده‌اش
 * می‌شکند (p_first/p_max/p_min/p_last) و «حذف» اکشن است، نه داده. */
export const TABLE_HEADER_ALIAS: Record<string, string> = {
  'نماد': 'symbol',
  'حجم': 'q_tot_tran',
  'تعداد': 'z_tot_tran',
  'ارزش (م.ریال)': 'q_tot_cap',
  'آخرین': 'p_last',
  'تغییر٪': 'percent_change',
  'پایانی': 'p_closing',
  'حجم تقاضا': 'buy_q1_vol',
  'قیمت تقاضا': 'buy_q1_px',
  'قیمت عرضه': 'sell_q1_px',
  'حجم عرضه': 'sell_q1_vol',
  'وضعیت': 'status',
  'برچسب‌های تابلو': 'badges',
  'تکنیکال': 'tech',
  'بنیادی': 'fund',
  'به‌روزرسانی': 'row_h',
};

/** دامنه: «کلِ دیدهبان» = هر چه فهرستِ رصد اجازه می‌دهد (بی‌بریدگیِ فیلتر یا صفحه). */
export function scopeItems(
  items: readonly WatchExportItem[],
  scope: WatchScope,
  selected: ReadonlySet<string>,
  query: string,
): WatchExportItem[] {
  if (scope === 'all') return [...items];
  const q = normalizeFa(query.trim());
  const visible = q.length === 0
    ? [...items]
    : items.filter((it) => normalizeFa(it.symbol).includes(q)
      || normalizeFa(String(it.row?.name ?? '')).includes(q));
  if (scope === 'visible') return visible;
  return visible.filter((it) => selected.has(normalizeFa(it.symbol)));
}

/** سلول‌هایِ یکِ ردیف، با همان ترتیبِ `cols`. */
export function watchCellsFor(
  it: WatchExportItem,
  cols: readonly WatchColumn[],
  cfg: TapeFilterConfig | null,
  exportedAt: string,
): ExportCell[] {
  return cols.map((c) => {
    if (c.key === 'exported_at') return exportedAt;
    if (c.readItem) return c.readItem(it, cfg);
    return c.read ? c.read(it.row) : null;
  });
}

export type BuildArgs = {
  items: readonly WatchExportItem[];
  scope: WatchScope;
  selected: ReadonlySet<string>;
  query: string;
  colset: WatchColumnSet;
  cfg: TapeFilterConfig | null;
  exportedAt: string;
  meta: readonly (readonly [string, string])[];
};

/** جدولِ آماده: سرِ ستون + ردیف‌هایِ دامنه‌شده + ردپایِ منشأ (برایِ CSV و Excel یکی). */
export type WatchExportTable = ExportTable & { meta: readonly (readonly [string, string])[] };

export function buildWatchTable(a: BuildArgs): WatchExportTable {
  const cols = columnsFor(a.colset);
  const picked = scopeItems(a.items, a.scope, a.selected, a.query);
  return {
    columns: cols.map((c) => c.label),
    rows: picked.map((it) => watchCellsFor(it, cols, a.cfg, a.exportedAt)),
    meta: a.meta,
  };
}

/** ردیف‌هایِ خامِ POSTِ Excel: سرِ ستون درِ سطرِ اول، سپس داده. */
export function toExportRows(t: WatchExportTable): (readonly ExportCell[])[] {
  return [[...t.columns], ...t.rows.map((r) => [...r])];
}

/** «چند ردیف از چند نماد» — همان شمارشی که کنترلِ خروجی نشان می‌دهد. */
export function scopeCount(
  items: readonly WatchExportItem[], scope: WatchScope,
  selected: ReadonlySet<string>, query: string,
): { shown: number; total: number } {
  return {
    shown: scopeItems(items, scope, selected, query).length,
    total: items.length,
  };
}
