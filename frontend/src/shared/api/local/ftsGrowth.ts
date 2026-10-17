/** Local implementation of the desktop FTS cumulative revenue-growth axis. */

export type MonthlyRevenuePoint = {
  periodEnd: string;
  ytdRevenue: number | null;
  ytdRevenuePrev: number | null;
};

export type MonthlyRevenueSeriesInput = {
  /** Caller must apply desktop monthly_series symbol/title eligibility rules. */
  coverage: 'DESKTOP_COMPATIBLE' | 'INCOMPLETE';
  /** Rows may be unsorted; the calculator applies the desktop 60-row window. */
  rows: readonly MonthlyRevenuePoint[];
};

export type RevenueGrowthResult =
  | {
      status: 'EVALUATED';
      dataGap: false;
      period: string;
      growthPct: number;
      ytdNowBt: number;
      ytdPrevBt: number;
      denominatorBasis: 'official_comparison' | 'prior_year_same_month';
      pass: boolean;
      threshold: number;
      beatsInflation: boolean;
      growthTarget: number;
    }
  | {
      status: 'NOT_EVALUATED';
      dataGap: true;
      reason: 'series_scope_unverified' | 'no_usable_current_period' | 'comparable_ytd_missing';
      period?: string;
      threshold: number;
      growthTarget: number;
    };

const DEFAULT_MIN_GROWTH = 40;
const DEFAULT_GROWTH_TARGET = 60;
const MONTHLY_SERIES_LIMIT = 60;

function parsePeriod(value: string): { year: number; month: number } | null {
  const match = /^(\d{4})\/(\d{1,2})\/(\d{1,2})$/.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (!Number.isInteger(year) || year <= 0 || month < 1 || month > 12 || day < 1 || day > 31) return null;
  return { year, month };
}

/** Python round(value, 1): nearest tenth with ties to even on the exact IEEE-754 value. */
export function roundLikePythonToOne(value: number): number {
  if (!Number.isFinite(value) || value === 0) return value;
  const view = new DataView(new ArrayBuffer(8));
  view.setFloat64(0, Math.abs(value), false);
  const high = view.getUint32(0, false);
  const low = view.getUint32(4, false);
  const exponentBits = (high >>> 20) & 0x7ff;
  const fraction = (BigInt(high & 0xfffff) << 32n) | BigInt(low);
  const significand = exponentBits === 0 ? fraction : (1n << 52n) | fraction;
  const exponent = exponentBits === 0 ? -1074 : exponentBits - 1023 - 52;
  let numerator = significand * 10n;
  let denominator = 1n;
  if (exponent >= 0) numerator <<= BigInt(exponent);
  else denominator <<= BigInt(-exponent);
  let rounded = numerator / denominator;
  const remainder = numerator % denominator;
  const doubledRemainder = remainder * 2n;
  if (doubledRemainder > denominator || (doubledRemainder === denominator && rounded % 2n !== 0n)) {
    rounded += 1n;
  }
  return Math.sign(value) * Number(rounded) / 10;
}

function positiveFinite(value: number | null): value is number {
  return value !== null && Number.isFinite(value) && value > 0;
}

function thresholdOrDefault(value: number | undefined, fallback: number): number {
  return value !== undefined && Number.isFinite(value) ? value : fallback;
}

function fail(
  reason: Extract<RevenueGrowthResult, { status: 'NOT_EVALUATED' }>['reason'],
  threshold: number,
  growthTarget: number,
  period?: string,
): RevenueGrowthResult {
  return { status: 'NOT_EVALUATED', dataGap: true, reason, threshold, growthTarget,
    ...(period ? { period } : {}) };
}

/** Mirrors `ytd_denominator` and `revenue_growth_yoy` in desktop `fts_engine.py`. */
export function evaluateRevenueGrowthYoy(
  input: MonthlyRevenueSeriesInput,
  options: { minimumGrowth?: number; growthTarget?: number } = {},
): RevenueGrowthResult {
  const threshold = thresholdOrDefault(options.minimumGrowth, DEFAULT_MIN_GROWTH);
  const growthTarget = thresholdOrDefault(options.growthTarget, DEFAULT_GROWTH_TARGET);
  if (input.coverage !== 'DESKTOP_COMPATIBLE') {
    return fail('series_scope_unverified', threshold, growthTarget);
  }

  const ordered = input.rows.map((row, index) => ({ row, index, period: parsePeriod(row.periodEnd) }))
    .filter((item): item is typeof item & { period: { year: number; month: number } } =>
      item.period !== null && positiveFinite(item.row.ytdRevenue))
    .sort((left, right) => right.period.year - left.period.year
      || right.period.month - left.period.month || left.index - right.index)
    .slice(0, MONTHLY_SERIES_LIMIT);

  const byPeriod = new Map<string, (typeof ordered)[number]>();
  for (const item of ordered) {
    const key = `${item.period.year}/${item.period.month}`;
    const previous = byPeriod.get(key);
    if (!previous || item.row.ytdRevenue! > previous.row.ytdRevenue!) byPeriod.set(key, item);
  }
  const series = [...byPeriod.values()].sort((left, right) => right.period.year - left.period.year
    || right.period.month - left.period.month || left.index - right.index);
  const current = series[0];
  if (!current) return fail('no_usable_current_period', threshold, growthTarget);

  const { year, month } = current.period;
  const period = `${String(month).padStart(2, '0')}/${year}`;
  const ytdNow = current.row.ytdRevenue!;
  const officialComparison = current.row.ytdRevenuePrev;
  let ytdPrev: number | null = positiveFinite(officialComparison) ? officialComparison : null;
  let denominatorBasis: 'official_comparison' | 'prior_year_same_month' = 'official_comparison';
  if (ytdPrev === null) {
    const previousYear = series.find((item) => item.period.year === year - 1
      && item.period.month === month && positiveFinite(item.row.ytdRevenue));
    ytdPrev = previousYear?.row.ytdRevenue ?? null;
    denominatorBasis = 'prior_year_same_month';
  }
  if (!positiveFinite(ytdPrev)) return fail('comparable_ytd_missing', threshold, growthTarget, period);

  const growth = (ytdNow / ytdPrev - 1.0) * 100.0;
  if (!Number.isFinite(growth)) return fail('comparable_ytd_missing', threshold, growthTarget, period);
  return {
    status: 'EVALUATED',
    dataGap: false,
    period,
    growthPct: roundLikePythonToOne(growth),
    ytdNowBt: roundLikePythonToOne(ytdNow * 1e-4),
    ytdPrevBt: roundLikePythonToOne(ytdPrev * 1e-4),
    denominatorBasis,
    pass: growth >= threshold,
    threshold,
    beatsInflation: growth >= growthTarget,
    growthTarget,
  };
}
