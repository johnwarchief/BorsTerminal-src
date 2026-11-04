import { describe, expect, it } from 'vitest';
import { AXES, statusOf, thresholdOf, valueOf, verdictFa, type ScreenerRowLike } from '@features/fundamental/lib/axisMeta';

const row = {
  symbol: 'رنيك', score: 3, verdict: 'WATCH',
  i1_pass: false, i1_na: false, i2_pass: true, i2_na: false,
  i3_pass: false, i3_na: false, i4_pass: true, i4_na: false,
  i5_pass: true, i5_na: false,
  rev_growth: 45.9, eps_series: [1119, 1615, 1672], eps_years_available: 3,
  gross_margin: 11.5, sales_to_mcap: 1.15, profit_potential_pct: 13.2,
  pricing_mode: 'neutral',
} satisfies ScreenerRowLike;

const thresholds = { growth_min: 60, margin_min: 40, v10_sales_to_mcap_min: 0.33, profit_potential_min: 40, v10_eps_years: 3 };

describe('axis meta', () => {
  it('has the five axes in order', () => {
    expect(AXES.map((axis) => axis.key)).toEqual(['growth', 'eps', 'margin', 'sales', 'industry']);
    expect(AXES.map((axis) => axis.num)).toEqual(['۱', '۲', '۳', '۴', '۵']);
  });
  it('derives pass/fail/na/unknown from the row flags', () => {
    expect(statusOf(row, 'growth')).toBe('fail');
    expect(statusOf(row, 'eps')).toBe('pass');
    expect(statusOf({ ...row, i3_pass: null, i3_na: true }, 'margin')).toBe('na');
    expect(statusOf({ ...row, i2_pass: null, i2_na: false }, 'eps')).toBe('unknown');
  });
  it('reads the axis value and threshold', () => {
    expect(valueOf(row, 'growth')).toBe(45.9);
    expect(valueOf(row, 'eps')).toBe(1672);
    expect(valueOf(row, 'industry')).toBe('neutral');
    expect(thresholdOf(thresholds, 'growth')).toBe(60);
    expect(thresholdOf(thresholds, 'sales')).toBe(0.33);
  });
  it('uses only sales_to_mcap for axis 4, never profit potential', () => {
    expect(valueOf(row, 'sales')).toBe(1.15);
    expect(valueOf({ ...row, sales_to_mcap: null, profit_potential_pct: 13.2 }, 'sales')).toBeNull();
  });
  it('does not invent fallback thresholds', () => {
    expect(thresholdOf({}, 'growth')).toBeNull();
    expect(thresholdOf(null, 'sales')).toBeNull();
    expect(thresholdOf({ margin_min: 40 }, 'growth')).toBeNull();
  });
  it('localizes verdicts', () => {
    expect(verdictFa('STRONG')).toBe('قوی');
    expect(verdictFa('WATCH')).toBe('تحت نظر');
    expect(verdictFa('REJECT')).toBe('رد');
    expect(verdictFa('EXCLUDED')).toBe('خارج از غربال');
    expect(verdictFa('FTS ندارد')).toBe('FTS ندارد');
  });
});
