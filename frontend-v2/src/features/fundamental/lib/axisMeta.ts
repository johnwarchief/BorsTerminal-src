import { toFaDigits } from '@shared/lib/fa';
import type { ScreenerCoreRow } from '../api/useScreenerCore';

export type AxisKey = 'growth' | 'eps' | 'margin' | 'sales' | 'industry';
export type AxisStatus = 'pass' | 'fail' | 'na' | 'unknown';
// R-P0-1: مسیرِ قبولیِ محور ۴ — پتانسیل سود، وگرنه شاهدِ فروش/ارزش، وگرنه هیچ.
export type PotentialPath = 'potential' | 'sales' | null;
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
  // R-P0-1: تیترِ محور ۴ پتانسیل سود است؛ کلیدِ داخلیِ `sales` برای سازگاریِ sortKey می‌ماند.
  { key: 'sales', num: '۴', label: 'پتانسیل سود تا آخر سال', short: 'پتانسیل', thresholdKey: 'profit_potential_min' },
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
    // R-P0-1: مقدارِ محور ۴ درصدِ نهاییِ پتانسیل سود است، نه نسبتِ فروش/ارزش.
    case 'sales': return row.profit_potential_pct ?? null;
    case 'industry': return row.pricing_mode ?? null;
  }
}

export function thresholdOf(thresholds: AxisThresholds | null | undefined, axis: AxisKey): number | null {
  if (!thresholds) return null;
  switch (axis) {
    case 'growth': return thresholds.growth_min ?? null;
    case 'eps': return thresholds.v10_eps_years ?? null;
    case 'margin': return thresholds.margin_min ?? null;
    // R-P0-1: آستانهٔ محور ۴ همان کفِ پتانسیل سود است؛ فروش/ارزش فقط مسیر/شاهد است.
    case 'sales': return thresholds.profit_potential_min ?? null;
    case 'industry': return null;
  }
}

/** وضعیتِ زیرگیتِ پتانسیل سود برای نمودار/تیترِ محور ۴ — نه وضعیتِ ترکیبیِ کارت. */
export function potentialStatusOf(
  row: Pick<ScreenerRowLike, 'profit_potential_pct'>,
  thresholds: AxisThresholds | null | undefined,
): AxisStatus {
  const value = row.profit_potential_pct;
  const threshold = thresholds?.profit_potential_min;
  if (value == null || threshold == null || !Number.isFinite(value) || !Number.isFinite(threshold)) return 'unknown';
  return value >= threshold ? 'pass' : 'fail';
}

/** مسیرِ قبولیِ محور ۴: پتانسیل، وگرنه شاهدِ فروش/ارزش، وگرنه هیچ. */
export function potentialPath(
  row: Pick<ScreenerRowLike, 'profit_potential_pct' | 'sales_to_mcap'>,
  thresholds: AxisThresholds | null | undefined,
): PotentialPath {
  if (potentialStatusOf(row, thresholds) === 'pass') return 'potential';
  const ratio = row.sales_to_mcap;
  const floor = thresholds?.v10_sales_to_mcap_min;
  if (ratio != null && floor != null && Number.isFinite(ratio) && Number.isFinite(floor) && ratio >= floor) return 'sales';
  return null;
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

/** R98: روندِ سری — گیتِ محور ۲ روند است، نه شمارشِ سال. */
export type Trend = 'up' | 'down' | 'flat' | null;

function finiteValues(series: readonly (number | null | undefined)[] | null | undefined): number[] {
  if (!Array.isArray(series)) return [];
  return series.filter((value): value is number => value != null && Number.isFinite(Number(value))).map(Number);
}

/** آخرین مقدارِ متناهیِ سری؛ سری خالی/نامعلوم null است. */
export function lastSeriesValue(series: readonly (number | null | undefined)[] | null | undefined): number | null {
  const values = finiteValues(series);
  return values.length ? values[values.length - 1]! : null;
}

/**
 * R105: روند از کلِ سریِ متناهی — همهٔ اختلاف‌های متوالی مثبت → صعودی، همه منفی →
 * نزولی، وگرنه بی‌تغییر. دو نقطهٔ آخر کافی نیست: [۱۴۲۵, ۴۵۴, ۴۵۶] صعودی نیست.
 * کمتر از دو مقدار = نامشخص، نه «ثابت».
 */
export function trendOf(series: readonly (number | null | undefined)[] | null | undefined): Trend {
  const values = finiteValues(series);
  if (values.length < 2) return null;
  const diffs = values.slice(1).map((value, index) => value - values[index]!);
  if (diffs.every((diff) => diff > 0)) return 'up';
  if (diffs.every((diff) => diff < 0)) return 'down';
  return 'flat';
}

export function trendArrow(trend: Trend): string {
  return trend === 'up' ? '↑' : trend === 'down' ? '↓' : trend === 'flat' ? '→' : '';
}

export function trendFa(trend: Trend): string {
  return trend === 'up' ? 'صعودی' : trend === 'down' ? 'نزولی' : trend === 'flat' ? 'بی‌تغییر' : 'نامشخص';
}

/** سال‌های گیتِ EPS: تنظیمِ ردیف، وگرنه تنظیمِ ریشه؛ نبودِ تنظیم «نامعلوم» است، نه ۳. */
export function epsYearsRequired(
  row: { eps_years_required?: number | null } | null | undefined,
  thresholds: AxisThresholds | null | undefined,
): number | null {
  return row?.eps_years_required ?? thresholds?.v10_eps_years ?? null;
}

/** مقدارِ نمایشیِ محور ۲: آخرین EPS با ارقامِ فارسی + فلشِ روند. */
export function formatEpsTrend(series: readonly (number | null | undefined)[] | null | undefined): string {
  const last = lastSeriesValue(series);
  if (last == null) return '—';
  const arrow = trendArrow(trendOf(series));
  const value = toFaDigits(Math.round(last)).replace(/^-/, '−');
  return arrow ? `${value} ${arrow}` : value;
}

export function verdictFa(verdict: string | null | undefined): string {
  const map: Record<string, string> = { STRONG: 'قوی', WATCH: 'تحت نظر', REJECT: 'رد', EXCLUDED: 'خارج از غربال' };
  // R31: حکمِ خارج از enum (مثل «FTS ندارد») باید عیناً دیده شود، نه '—'.
  if (verdict == null || verdict === '') return '—';
  return map[verdict] ?? verdict;
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
  const n = Number(value);
  // R-P0-1: محور ۴ هم درصدِ علامت‌دار است («+۱۳٫۲٪»).
  const prefix = (axis === 'growth' || axis === 'sales') && n > 0 ? '+' : n < 0 ? '−' : '';
  return `${prefix}${toFaDigits(Math.abs(n).toFixed(1)).replace('.', '٫')}٪`;
}
