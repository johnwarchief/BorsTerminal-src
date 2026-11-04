import { describe, expect, it } from 'vitest';
import {
  FTS_BASIC_DEFAULTS,
  buildFtsPayload,
  buildResetPayload,
  draftFromConfig,
} from '@features/fundamental/api/useFtsConfig';

const base = {
  ...FTS_BASIC_DEFAULTS,
  hourglass_rsi_period: 9,
  hourglass_rsi_oversold: 25,
  hourglass_ma52_position: 'above' as const,
};

describe('fts config payload', () => {
  it('keeps hourglass keys untouched when saving fundamental settings', () => {
    const draft = {
      ...draftFromConfig(base),
      growth_min: 60,
      volumeGate: false,
      epsGate: false,
      pricingGate: 'all' as const,
      insuranceGate: false,
      holdingsNa: false,
      pharmaExempt: true,
      baseMarketGate: false,
    };
    const payload = buildFtsPayload(base, draft);
    expect(payload.growth_min).toBe(60);
    expect(payload.hourglass_rsi_period).toBe(9);
    expect(payload.hourglass_rsi_oversold).toBe(25);
    expect(payload.hourglass_ma52_position).toBe('above');
    expect(payload.industry_mode).toBe('Rank_Only');
    expect(payload.v10_eps_years).toBe(1);
    expect(payload.v10_volume_breadth_min).toBe(0);
    expect(payload.reject_insurance).toBe(false);
    expect(payload.holdings_sales_na).toBe(false);
    expect(payload.pharma_margin_exempt_min).toBe(50);
    expect(payload.exclude_base_market).toBe(false);
    expect(payload.mandatory_sectors).toEqual(['خودرو', 'نیروگاه', 'لاستیک']);
    expect(payload).not.toHaveProperty('volumeGate');
    expect(payload).not.toHaveProperty('pricingGate');
  });

  it('reset only resets fundamental keys and preserves hourglass', () => {
    const payload = buildResetPayload(base);
    expect(payload.growth_min).toBe(40);
    expect(payload.margin_min).toBe(20);
    expect(payload.v10_sales_to_mcap_min).toBe(0.33);
    expect(payload.industry_mode).toBe('Exclude_Mandatory_Pricing');
    expect(payload.hourglass_rsi_period).toBe(9);
    expect(payload.hourglass_rsi_oversold).toBe(25);
    expect(payload.hourglass_ma52_position).toBe('above');
  });
});
