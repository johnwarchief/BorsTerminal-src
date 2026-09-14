// تست سیگنال بنیادی: شرط صعودی بالای 70 و کهنگی و خلاء داده
import { describe, expect, it } from 'vitest';
import { BaseSignal, FundamentalPayload } from '@contracts/index';
import {
  FUND_VALID_MS,
  fundamentalSignal,
  type FundamentalInput,
} from '@features/fundamental/signals/fundamentalSignals';

function input(patch: Partial<FundamentalInput> = {}): FundamentalInput {
  return {
    symbol: 'شپنا',
    ftsScore: 3,
    passes: { '1_growth': true, '2_eps_trend': false, '3_gross_margin': true, '4_sales_to_mcap': false, '5_industry': true },
    epsSeries: [100, 120, null],
    pe: 5,
    sectorMedianPE: 7,
    profitYoY: 20,
    statementAgeDays: 30,
    hasStatements: true,
    epsPartial: false,
    ...patch,
  };
}

describe('سیگنال بنیادی', () => {
  it('خلاء داده سیگنال خنثی ناقص می دهد', () => {
    const s = fundamentalSignal(input({ hasStatements: false }), 1726000000000);
    expect(s.direction).toBe('neutral');
    expect(s.confidence).toBe('nodata');
    expect(s.score).toBeNull();
    expect(s.payload.dataQuality).toBe('incomplete');
    expect(BaseSignal.safeParse(s).success).toBe(true);
    expect(FundamentalPayload.safeParse(s.payload).success).toBe(true);
  });

  it('تخفیف به صنعت با رشد مثبت امتیاز بالای 70 می گیرد', () => {
    const s = fundamentalSignal(input(), 1726000000000);
    expect(s.direction).toBe('bullish');
    expect(s.score).not.toBeNull();
    expect(s.score as number).toBeGreaterThan(70);
    expect(s.confidence).toBe('high');
    expect(s.payload.staleness).toBe(false);
    expect(s.payload.dataQuality).toBe('complete');
    expect(s.validForMs).toBe(FUND_VALID_MS);
    expect(s.payload.peVsSector).toBeCloseTo(5 / 7, 4);
    expect(BaseSignal.safeParse(s).success).toBe(true);
    expect(FundamentalPayload.safeParse(s.payload).success).toBe(true);
  });

  it('کهنگی بالای 120 روز اعتماد را متوسط و پرچم را روشن می کند', () => {
    const s = fundamentalSignal(input({ statementAgeDays: 150 }), 1726000000000);
    expect(s.payload.staleness).toBe(true);
    expect(s.confidence).toBe('medium');
    expect(s.payload.dataQuality).toBe('partial');
    expect(s.rationale).toContain('۱۵۰');
  });

  it('گرانی به صنعت با افت سود سیگنال نزولی می دهد', () => {
    const s = fundamentalSignal(input({ pe: 12, profitYoY: -10 }), 1726000000000);
    expect(s.direction).toBe('bearish');
    expect(s.score as number).toBeLessThanOrEqual(29);
  });

  it('P/E نامعتبر شرط صعودی را فعال نمی کند', () => {
    const s = fundamentalSignal(input({ pe: null }), 1726000000000);
    expect(s.score as number).toBeLessThanOrEqual(70);
  });
});
