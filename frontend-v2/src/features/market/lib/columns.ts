import { changePct } from '@shared/lib/fa';
import type { MarketRow } from '@shared/types/market';
import { lastCloseDiff } from './tapePatterns';

export type ColumnKey =
  | 'symbol'
  | 'last'
  | 'close'
  | 'last_vs_close'
  | 'pct_close'
  | 'pct_last'
  | 'volume'
  | 'value'
  | 'trades'
  | 'vol_ratio'
  | 'buy_sell'
  | 'patterns'
  | 'pe'
  | 'eps'
  | 'mcap'
  | 'tech';

interface ColumnDef {
  label: string;
  /** عرضِ ستون — همان minmaxِ پروتوتایپ تا در 2560 کشیده شود */
  width: string;
  num?: boolean;
  /** منبعِ داده وصل است؟ ستونِ ناوصل در پروفایلِ پیش‌فرض نمی‌آید. */
  available: boolean;
  hint?: string;
}

export const COLUMNS: Record<ColumnKey, ColumnDef> = {
  symbol: {
    label: 'نماد',
    width: 'minmax(154px, var(--sym-max))',
    available: true,
    hint: 'نماد و نام شرکت',
  },
  last: { label: 'آخرین', width: 'minmax(62px, 1fr)', num: true, available: true, hint: 'آخرین قیمت معامله (ریال)' },
  close: { label: 'پایانی', width: 'minmax(62px, 1fr)', num: true, available: true, hint: 'قیمت پایانی (ریال)' },
  last_vs_close: {
    label: 'اختلاف٪',
    width: 'minmax(56px, .9fr)',
    num: true,
    available: true,
    hint: 'اختلاف آخرین معامله و قیمت پایانی',
  },
  pct_close: {
    label: 'تغییر٪',
    width: 'minmax(56px, .95fr)',
    num: true,
    available: true,
    hint: 'قیمت پایانی نسبت به دیروز',
  },
  pct_last: {
    label: 'آخرین٪',
    width: 'minmax(56px, .95fr)',
    num: true,
    available: true,
    hint: 'آخرین معامله نسبت به دیروز',
  },
  volume: { label: 'حجم', width: 'minmax(58px, .95fr)', num: true, available: true, hint: 'حجم معاملات' },
  value: {
    label: 'ارزش',
    width: 'minmax(58px, .95fr)',
    num: true,
    available: true,
    hint: 'ارزش معاملات (میلیارد ریال)',
  },
  trades: { label: 'معاملات', width: 'minmax(52px, .8fr)', num: true, available: true, hint: 'تعداد معاملات' },
  vol_ratio: {
    label: 'حجم/ماه',
    width: 'minmax(54px, .85fr)',
    num: true,
    available: true,
    hint: 'نسبت حجم به میانگین ماه',
  },
  buy_sell: {
    label: 'خرید / فروش',
    width: 'minmax(118px, 1.35fr)',
    num: true,
    available: true,
    hint: 'سرانهٔ حقیقی و نسبت قدرت خریدار به فروشنده',
  },
  patterns: {
    label: 'الگو',
    width: 'minmax(112px, 1.4fr)',
    available: true,
    hint: 'نشان‌های تابلوخوانی از داوری canonical',
  },
  pe: { label: 'P/E', width: 'minmax(44px, .7fr)', num: true, available: true, hint: 'نسبت قیمت به درآمد' },
  eps: { label: 'EPS', width: 'minmax(46px, .75fr)', num: true, available: false, hint: 'در /api/market نیست' },
  mcap: {
    label: 'ارزش بازار',
    width: 'minmax(62px, .95fr)',
    num: true,
    available: true,
    hint: 'ارزش بازار (همت)',
  },
  tech: { label: 'اسکن', width: 'minmax(58px, .8fr)', available: false, hint: 'اندپوینتِ اسکن وصل نیست' },
};

export const COLUMN_ORDER: ColumnKey[] = [
  'symbol',
  'last',
  'close',
  'last_vs_close',
  'pct_close',
  'pct_last',
  'volume',
  'trades',
  'value',
  'vol_ratio',
  'buy_sell',
  'patterns',
  'pe',
  'eps',
  'mcap',
  'tech',
];

export type ProfileKey = 'general' | 'trading' | 'fundamental' | 'technical';

export const PROFILES: Record<ProfileKey, { label: string; columns: ColumnKey[] }> = {
  general: {
    label: 'عمومی',
    columns: ['symbol', 'last', 'pct_close', 'close', 'volume', 'value', 'trades', 'patterns', 'pe', 'eps', 'mcap', 'tech'],
  },
  trading: {
    label: 'معاملات',
    columns: [
      'symbol', 'last', 'close', 'last_vs_close', 'pct_close', 'pct_last',
      'volume', 'trades', 'value', 'vol_ratio', 'buy_sell', 'patterns',
    ],
  },
  fundamental: {
    label: 'بنیادی',
    columns: ['symbol', 'last', 'pct_close', 'pe', 'eps', 'mcap'],
  },
  technical: {
    label: 'تکنیکال',
    columns: ['symbol', 'last', 'pct_close', 'volume', 'tech'],
  },
};

export const PROFILE_ORDER: ProfileKey[] = ['general', 'trading', 'fundamental', 'technical'];

/** ستون‌های پیش‌فرضِ هر پروفایل: فقط ستون‌هایی که منبعشان وصل است */
export function defaultColumns(profile: ProfileKey): ColumnKey[] {
  return PROFILES[profile].columns.filter((k) => COLUMNS[k].available);
}

export function gridTemplate(columns: readonly ColumnKey[]): string {
  return columns.map((k) => COLUMNS[k].width).join(' ');
}

export type SortKey =
  | 'symbol' | 'last' | 'close' | 'last_vs_close' | 'pct_close' | 'pct_last'
  | 'volume' | 'value' | 'trades' | 'vol_ratio' | 'buy_sell' | 'pe' | 'mcap';
export type SortDir = 'asc' | 'desc';

export const SORT_LABEL: Record<SortKey, string> = {
  symbol: COLUMNS.symbol.label,
  last: COLUMNS.last.label,
  close: COLUMNS.close.label,
  last_vs_close: COLUMNS.last_vs_close.label,
  pct_close: COLUMNS.pct_close.label,
  pct_last: COLUMNS.pct_last.label,
  volume: COLUMNS.volume.label,
  value: COLUMNS.value.label,
  trades: COLUMNS.trades.label,
  vol_ratio: COLUMNS.vol_ratio.label,
  buy_sell: COLUMNS.buy_sell.label,
  pe: COLUMNS.pe.label,
  mcap: COLUMNS.mcap.label,
};

export function isSortable(key: ColumnKey): key is SortKey {
  return key in SORT_LABEL;
}

/** مقدارِ مرتب‌سازی؛ غایب = null تا در هر دو جهت آخرِ فهرست بماند */
export function sortValue(row: MarketRow, key: SortKey): number | string | null {
  switch (key) {
    case 'symbol':
      return row.symbol;
    case 'last':
      return row.p_last ?? row.p_closing ?? null;
    case 'close':
      return row.p_closing ?? null;
    case 'last_vs_close':
      return lastCloseDiff(row);
    case 'pct_close':
      return changePct(row.percent_change, row.price_change, row.price_yesterday);
    case 'pct_last':
      return row.percent_last ?? null;
    case 'volume':
      return row.q_tot_tran ?? null;
    case 'value':
      return row.q_tot_cap ?? null;
    case 'trades':
      return row.z_tot_tran ?? null;
    case 'vol_ratio':
      return row.vol_ratio ?? null;
    case 'buy_sell':
      return row.buyer_power ?? null;
    case 'pe':
      return row.pe ?? null;
    case 'mcap':
      return row.mcap ?? null;
  }
}

export function sortRows(rows: readonly MarketRow[], key: SortKey, dir: SortDir): MarketRow[] {
  const sign = dir === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    const va = sortValue(a, key);
    const vb = sortValue(b, key);
    if (va == null && vb == null) return a.symbol.localeCompare(b.symbol, 'fa');
    if (va == null) return 1;
    if (vb == null) return -1;
    if (typeof va === 'string' || typeof vb === 'string') {
      return String(va).localeCompare(String(vb), 'fa') * sign;
    }
    if (va === vb) return a.symbol.localeCompare(b.symbol, 'fa');
    return (va < vb ? -1 : 1) * sign;
  });
}
