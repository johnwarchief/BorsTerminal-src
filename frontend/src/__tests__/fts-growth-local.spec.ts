import { describe, expect, it } from 'vitest';
import { evaluateRevenueGrowthYoy, roundLikePythonToOne, type MonthlyRevenuePoint } from '@shared/api/local/ftsGrowth';

const point = (periodEnd: string, ytdRevenue: number | null, ytdRevenuePrev: number | null = null): MonthlyRevenuePoint =>
  ({ periodEnd, ytdRevenue, ytdRevenuePrev });
const complete = (...rows: MonthlyRevenuePoint[]) => ({ coverage: 'DESKTOP_COMPATIBLE' as const, rows });

describe('local FTS cumulative revenue growth', () => {
  it('prefers the official comparable-YTD column over older periods', () => {
    const result = evaluateRevenueGrowthYoy(complete(
      point('1405/06/31', 160, 100),
      point('1405/05/31', 120, 90),
      point('1404/06/31', 80),
    ));
    expect(result).toMatchObject({ status: 'EVALUATED', period: '06/1405', growthPct: 60,
      ytdNowBt: 0, ytdPrevBt: 0, denominatorBasis: 'official_comparison', pass: true,
      threshold: 40, beatsInflation: true, growthTarget: 60 });
  });

  it('falls back only to the same month of the previous year and matches desktop rounding', () => {
    const result = evaluateRevenueGrowthYoy(complete(
      point('1405/06/31', 364877646, null),
      point('1405/05/31', 500000000, null),
      point('1404/06/31', 250000000, null),
    ));
    expect(result).toMatchObject({ status: 'EVALUATED', period: '06/1405', growthPct: 46,
      ytdNowBt: 36487.8, ytdPrevBt: 25000, denominatorBasis: 'prior_year_same_month',
      pass: true, threshold: 40, beatsInflation: false, growthTarget: 60 });
  });

  it('does not substitute the previous month when the comparable YTD is missing', () => {
    expect(evaluateRevenueGrowthYoy(complete(
      point('1405/06/31', 364877646, null),
      point('1405/05/31', 250000000, null),
    ))).toMatchObject({ status: 'NOT_EVALUATED', dataGap: true,
      reason: 'comparable_ytd_missing', period: '06/1405' });
  });

  it('keeps the row with the greatest YTD for duplicate year/month records', () => {
    const result = evaluateRevenueGrowthYoy(complete(
      point('1405/06/31', 100, 20),
      point('1405/06/30', 160, 100),
    ));
    expect(result).toMatchObject({ status: 'EVALUATED', growthPct: 60,
      denominatorBasis: 'official_comparison' });
  });

  it('returns NOT_EVALUATED until the desktop-compatible series scope is proven', () => {
    expect(evaluateRevenueGrowthYoy({ coverage: 'INCOMPLETE', rows: [point('1405/06/31', 160, 100)] }))
      .toMatchObject({ status: 'NOT_EVALUATED', reason: 'series_scope_unverified' });
  });

  it('returns NOT_EVALUATED for invalid or absent current periods', () => {
    expect(evaluateRevenueGrowthYoy(complete(point('1405/13/31', 160, 100), point('1405/06/31', 0, 100))))
      .toMatchObject({ status: 'NOT_EVALUATED', reason: 'no_usable_current_period' });
    expect(evaluateRevenueGrowthYoy(complete()))
      .toMatchObject({ status: 'NOT_EVALUATED', reason: 'no_usable_current_period' });
  });

  it('rounds exact binary float ties to even like Python round(value, 1)', () => {
    expect([1.25, 1.35, -1.25, -1.35, 2.25, 2.35].map(roundLikePythonToOne))
      .toEqual([1.2, 1.4, -1.2, -1.4, 2.2, 2.4]);
  });
});
