import { toFaDigits } from '@shared/lib/fa';
import type { ScreenerCoreRow } from '../api/useScreenerCore';

export type AxisKey = 'growth' | 'eps' | 'margin' | 'sales' | 'industry';
export type AxisStatus = 'pass' | 'fail' | 'na' | 'unknown';
export type ScreenerRowLike = Pick<ScreenerCoreRow,
  'symbol' | 'score' | 'verdict' | 'i1_pass' | 'i1_na' | 'i2_pass' | 'i2_na' |
  'i3_pass' | 'i3_na' | 'i4_pass' | 'i4_na' | 'i5_pass' | 'i5_na' |
  'rev_growth' | 'eps_series' | 'eps_years_available' | 'gross_margin' |
  'sales_to_mcap' | 'profit_potential_pct' | 'pricing_mode'
>;

export interface AxisThresholds {
  growth_min?: number | null; margin_min?: number | null; margin_optimal?: number | null;
  v10_sales_to_mcap_min?: number | null; profit_potential_min?: number | null; v10_eps_years?: number | null;
}

export const AXES = [
  { key: 'growth', num: '۱', label: 'رشد فروش', short: 'رشد', thresholdKey: 'growth_min' },
  { key: 'eps', num: '۲', label: 'سودآوری ۳ساله', short: 'سودآوری', thresholdKey: 'v10_eps_years' },
  { key: 'margin', num: '۳', label: 'حاشیهٔ ناخالص', short: 'حاشیه', thresholdKey: 'margin_min' },
  { key: 'sales', num: '۴', label: 'فروش / ارزش', short: 'فروش/ارزش', thresholdKey: 'v10_sales_to_mcap_min' },
  { key: 'industry', num: '۵', label: 'نرخ‌گذاری صنعت', short: 'صنعت', thresholdKey: null },
] as const;
export type AxisMeta = (typeof AXES)[number];

const PASS_KEYS: Record<AxisKey, [keyof ScreenerRowLike, keyof ScreenerRowLike]> = {
  growth: ['i1_pass', 'i1_na'], eps: ['i2_pass', 'i2_na'], margin: ['i3_pass', 'i3_na'],
  sales: ['i4_pass', 'i4_na'], industry: ['i5_pass', 'i5_na'],
};

export function statusOf(row: ScreenerRowLike, axis: AxisKey): AxisStatus {
  const [passKey, naKey] = PASS_KEYS[axis];
  const pass = row[passKey];
  if (pass === true) return 'pass';
  if (pass === false) return 'fail';
  if (row[naKey] === true) return 'na';
  return 'unknown';
}

export function valueOf(row: ScreenerRowLike, axis: AxisKey): number | string | null {
  switch (axis) {
    case 'growth': return row.rev_growth ?? null;
    case 'eps': return Array.isArray(row.eps_series) && row.eps_series.length ? row.eps_series[row.eps_series.length - 1] ?? null : null;
    case 'margin': return row.gross_margin ?? null;
    case 'sales': return row.sales_to_mcap ?? null;
    case 'industry': return row.pricing_mode ?? null;
  }
}

export function thresholdOf(thresholds: AxisThresholds | null | undefined, axis: AxisKey): number | null {
  if (!thresholds) return null;
  switch (axis) {
    case 'growth': return thresholds.growth_min ?? null;
    case 'eps': return thresholds.v10_eps_years ?? null;
    case 'margin': return thresholds.margin_min ?? null;
    case 'sales': return thresholds.v10_sales_to_mcap_min ?? null;
    case 'industry': return null;
  }
}

type ReasonField = 'i1_reason' | 'i2_reason' | 'i3_reason' | 'i4_reason' | 'i5_reason';
export type ScreenerReasonRow = Pick<ScreenerCoreRow, ReasonField | 'eps_data_gap'>;

const REASON_KEYS: Record<AxisKey, ReasonField> = {
  growth: 'i1_reason', eps: 'i2_reason', margin: 'i3_reason', sales: 'i4_reason', industry: 'i5_reason',
};

/** دلیلِ وضعیتِ محور برای tooltip؛ فقط متنِ خودِ پاسخ، بدون ساختِ دلیلِ تازه. */
export function reasonOf(row: ScreenerReasonRow, axis: AxisKey): string | null {
  const reason = row[REASON_KEYS[axis]];
  if (reason) return reason;
  if (axis === 'eps' && row.eps_data_gap) return 'شکاف دادهٔ EPS';
  return null;
}

export function verdictFa(verdict: string | null | undefined): string {
  return ({ STRONG: 'قوی', WATCH: 'تحت نظر', REJECT: 'رد', EXCLUDED: 'خارج از غربال' } as Record<string, string>)[verdict ?? ''] ?? '—';
}

export function statusFa(status: AxisStatus): string {
  return ({ pass: 'قبول', fail: 'رد', na: 'بی‌نظر', unknown: 'نامشخص' } as Record<AxisStatus, string>)[status];
}

export function regimeFa(value: string | null | undefined): string {
  return ({ free: 'آزاد', neutral: 'خنثی', mandatory: 'دستوری' } as Record<string, string>)[value ?? ''] ?? '—';
}

export function formatAxisValue(value: number | string | null, axis: AxisKey): string {
  if (value == null) return '—';
  if (axis === 'industry') return regimeFa(String(value));
  if (axis === 'eps') return toFaDigits(Math.round(Number(value)));
  if (axis === 'sales') return toFaDigits(Number(value).toFixed(2)).replace('.', '٫');
  const n = Number(value);
  const prefix = axis === 'growth' && n > 0 ? '+' : n < 0 ? '−' : '';
  return `${prefix}${toFaDigits(Math.abs(n).toFixed(1)).replace('.', '٫')}٪`;
}
