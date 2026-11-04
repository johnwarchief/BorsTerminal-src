import { describe, expect, it } from 'vitest';
import { ScreenerCoreSchema } from '@features/fundamental/api/useScreenerCore';

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
