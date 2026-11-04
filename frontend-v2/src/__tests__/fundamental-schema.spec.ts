import { describe, expect, it } from 'vitest';
import { FtsCardSchema } from '@features/fundamental/api/useFtsCard';
import { ScreenerCoreSchema } from '@features/fundamental/api/useScreenerCore';

/**
 * R82: زیرمجموعهٔ واقعیِ `indicators['2']` از پاسخ زندهٔ `GET /api/fundamental/رنيك`
 * (D:/BorsTerminal-tmp/fund-card-renik.json). شواهد اینجا آرایهٔ رشته‌هاست، نه رشته.
 */
const liveEpsIndicator = {
  years_required: 3,
  years_available: 3,
  in_progress_year: null,
  fiscal_years: ['1403', '1404', '1405'],
  eps_series: [1119, 1615, 1672],
  period_slots: ['1403', '1404', '1405'],
  partial: false,
  available_periods: 3,
  periods_missing: 0,
  period_ends: ['1403/12/30', '1404/12/29', '1405/03/31'],
  evidence: ['audited_year_end', 'audited_year_end', 'annualized_interim_short'],
  period_months: [12, 12, 3],
  net_profit_series: [6322707, 9125963, null],
  ref_tracing_nos: [1371777, 1549029, 1569581],
  consecutive_years: true,
  strictly_rising: true,
  all_profitable: true,
  consolidated_used: false,
  audited_only: false,
  evidence_tier: 'year_end_plus_interim',
  evidence_label: 'برآورد میان‌دوره',
  source: 'کدال — صورت‌های مالی سالانه + میاندوره',
  pass: true,
  rule_ref: 'F-02',
};

describe('screener schema', () => {
  it('accepts thresholds, eps series and timestamps', () => {
    const parsed = ScreenerCoreSchema.parse({
      status: 'success', count: 1, as_of: 1793789441,
      thresholds: { growth_min: 60, margin_min: 40, v10_sales_to_mcap_min: 0.33, profit_potential_min: 40 },
      data: [{ symbol: 'رنيك', eps_series: [1119, 1615, 1672], margin_tier: 'below', i1a_pass: true, i1b_pass: false, i4_na: false }],
    });
    expect(parsed.thresholds?.growth_min).toBe(60);
    expect(parsed.data[0]?.eps_series).toEqual([1119, 1615, 1672]);
  });
});

describe('fts card schema (R82)', () => {
  it('accepts the live evidence array in indicators[2]', () => {
    const parsed = FtsCardSchema.parse({
      status: 'success',
      symbol: 'رنيك',
      indicators: { '2': liveEpsIndicator },
    });
    expect(parsed.indicators?.['2']?.evidence).toEqual([
      'audited_year_end',
      'audited_year_end',
      'annualized_interim_short',
    ]);
    expect(parsed.indicators?.['2']?.period_ends).toEqual(['1403/12/30', '1404/12/29', '1405/03/31']);
    expect(parsed.indicators?.['2']?.consolidated_used).toBe(false);
  });

  it('still accepts a plain string and a missing evidence', () => {
    const asString = FtsCardSchema.parse({
      status: 'success',
      symbol: 'رنيك',
      indicators: { '2': { ...liveEpsIndicator, evidence: 'تلفیقی' } },
    });
    expect(asString.indicators?.['2']?.evidence).toBe('تلفیقی');

    const asNull = FtsCardSchema.parse({
      status: 'success',
      symbol: 'رنيك',
      indicators: { '2': { ...liveEpsIndicator, evidence: null } },
    });
    expect(asNull.indicators?.['2']?.evidence).toBeNull();
  });
});
