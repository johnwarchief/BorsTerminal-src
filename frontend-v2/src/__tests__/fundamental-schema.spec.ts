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

  it('parses the live growth indicator: target threshold and the 1b volume block (R97)', () => {
    const parsed = FtsCardSchema.parse({
      status: 'success',
      symbol: 'رنيك',
      indicators: {
        '1': {
          monetary: {
            monetary_pct: 45.9,
            threshold: 60,
            target_threshold: 60,
            pass: false,
            data_gap: false,
            reason: '',
          },
          volume: {
            applicable: false,
            volume_pct: null,
            real_pct: -8.8,
            pass: false,
            threshold: 0,
            data_gap: false,
            basis: 'price_effect_decomposition',
            note: 'این شرکت کالای وزن‌شدنی تولید نمی‌کند.',
          },
          pass: false,
          reason: 'رشد ریالی زیر کف است.',
        },
      },
    });
    const growth = parsed.indicators?.['1'];
    expect(growth?.monetary?.target_threshold).toBe(60);
    expect(growth?.monetary?.pass).toBe(false);
    expect(growth?.volume?.real_pct).toBe(-8.8);
    expect(growth?.volume?.volume_pct).toBeNull();
    expect(growth?.volume?.applicable).toBe(false);
    expect(growth?.volume?.pass).toBe(false);
    expect(growth?.volume?.basis).toBe('price_effect_decomposition');
    expect(growth?.volume?.note).toContain('وزن‌شدنی');
  });

  it('parses the EPS reason/data-gap and the root thresholds block (R99/R101)', () => {
    const parsed = FtsCardSchema.parse({
      status: 'success',
      symbol: 'رنيك',
      thresholds: { growth_min: 60, margin_min: 40, v10_eps_years: 1 },
      indicators: { '2': { ...liveEpsIndicator, reason: 'روند نزولی', data_gap: true } },
    });
    expect(parsed.thresholds?.v10_eps_years).toBe(1);
    expect(parsed.thresholds?.growth_min).toBe(60);
    expect(parsed.indicators?.['2']?.reason).toBe('روند نزولی');
    expect(parsed.indicators?.['2']?.data_gap).toBe(true);
  });
});
