import { describe, expect, it } from 'vitest';
import {
  AXES,
  epsYearsRequired,
  formatEpsTrend,
  statusOf,
  thresholdOf,
  trendArrow,
  trendFa,
  trendOf,
  valueOf,
  verdictFa,
  type ScreenerRowLike,
} from '@features/fundamental/lib/axisMeta';

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
  it('derives the EPS trend from the whole finite series (R98/R105)', () => {
    expect(trendOf([1119, 1615, 1672])).toBe('up');
    expect(trendOf([1672, 1615])).toBe('down');
    expect(trendOf([500, 500])).toBe('flat');
    expect(trendOf([1672])).toBeNull();
    expect(trendOf(null)).toBeNull();
    expect(trendOf([null, null])).toBeNull();
    // نقطهٔ null نادیده گرفته می‌شود و سریِ متناهی ملاک است.
    expect(trendOf([100, null, 90])).toBe('down');
    // R105: جهشِ دو نقطهٔ آخر روند را نمی‌سازد؛ کل سری باید هم‌جهت باشد.
    expect(trendOf([1425, 454, 456])).toBe('flat');
    expect(trendOf([1425, 454, 456])).not.toBe('up');
    expect(trendOf([100, 200, 150])).toBe('flat');
    expect(trendOf([300, 200, 100])).toBe('down');
    expect(trendOf([100, 200, 300])).toBe('up');
    expect(formatEpsTrend([1425, 454, 456])).toBe('۴۵۶ →');
  });
  it('renders trend arrows and Persian words (R98)', () => {
    expect([trendArrow('up'), trendArrow('down'), trendArrow('flat'), trendArrow(null)])
      .toEqual(['↑', '↓', '→', '']);
    expect([trendFa('up'), trendFa('down'), trendFa('flat'), trendFa(null)])
      .toEqual(['صعودی', 'نزولی', 'بی‌تغییر', 'نامشخص']);
    expect(formatEpsTrend([1119, 1615, 1672])).toBe('۱۶۷۲ ↑');
    expect(formatEpsTrend([1672, 1615])).toBe('۱۶۱۵ ↓');
    expect(formatEpsTrend(null)).toBe('—');
  });
  it('reads the EPS years gate from the row and then the root thresholds (R99)', () => {
    expect(epsYearsRequired({ eps_years_required: 2 }, thresholds)).toBe(2);
    expect(epsYearsRequired({}, thresholds)).toBe(3);
    expect(epsYearsRequired({}, { v10_eps_years: 1 })).toBe(1);
    expect(epsYearsRequired({}, null)).toBeNull();
  });
});
