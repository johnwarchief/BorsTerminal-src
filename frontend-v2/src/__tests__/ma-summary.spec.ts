import { describe, expect, it } from 'vitest';
import { technicalSummary, type MaSeries } from '@features/market/api/useMa';

const series = (values: Array<number | null>): Array<[string, number | null]> =>
  values.map((value, index) => [`2026-10-${String(index + 1).padStart(2, '0')}`, value]);

describe('technicalSummary', () => {
  it('calls an uptrend when price sits above a rising MA20', () => {
    const ma: MaSeries = {
      ma20: series([10, 11, 12, 13, 14, 15]),
      ma50: series([9, 9, 9, 9, 9, 9]),
    };
    const out = technicalSummary(ma, 16);
    expect(out.trend).toBe('up');
    expect(out.ma20?.value).toBe(15);
    expect(out.ma20?.date).toBe('2026-10-06');
    expect(out.ma20?.distancePct).toBeCloseTo((1 / 15) * 100, 6);
    expect(out.slope5Pct).toBeCloseTo(50, 6);
  });

  it('calls a downtrend only when both the position and the slope point down', () => {
    const out = technicalSummary({ ma20: series([20, 19, 18, 17, 16, 15]) }, 14);
    expect(out.trend).toBe('down');
    expect(out.slope5Pct).toBeCloseTo(-25, 6);
  });

  it('stays neutral when the position and the slope disagree', () => {
    expect(technicalSummary({ ma20: series([10, 11, 12, 13, 14, 15]) }, 14).trend).toBe('neutral');
    expect(technicalSummary({ ma20: series([20, 19, 18, 17, 16, 15]) }, 16).trend).toBe('neutral');
  });

  it('refuses a trend without six MA20 points or without a price', () => {
    expect(technicalSummary({ ma20: series([10, 11, 12, 13, 14]) }, 16).trend).toBeNull();
    expect(technicalSummary({ ma20: series([10, 11, 12, 13, 14, 15]) }, null).trend).toBeNull();
    expect(technicalSummary({}, 16)).toEqual({
      price: 16, ma20: null, ma50: null, slope5Pct: null, trend: null,
    });
  });

  it('skips null points at the end of a series', () => {
    const out = technicalSummary({
      ma20: [...series([10, 11, 12, 13, 14, 15]), ['2026-10-07', null]],
    }, 15);
    expect(out.ma20?.value).toBe(15);
    expect(out.slope5Pct).toBeCloseTo(50, 6);
  });
});
