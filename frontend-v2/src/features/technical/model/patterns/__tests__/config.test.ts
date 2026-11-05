// model/patterns/__tests__/config.test.ts
import { describe, expect, it } from 'vitest';
import { PATTERN_CONFIG } from '../config';

describe('PATTERN_CONFIG', () => {
  it('keeps every window positive and every tolerance in ATR terms', () => {
    for (const key of ['flag', 'pennant', 'triangle', 'rectangle', 'wedge', 'hs', 'triple'] as const) {
      expect(PATTERN_CONFIG[key].maxBars).toBeGreaterThan(2);
    }
    expect(PATTERN_CONFIG.flag.channelMaxWidthPct).toBeGreaterThan(0);
    expect(PATTERN_CONFIG.flag.channelMaxWidthPct).toBeLessThanOrEqual(60);
    expect(PATTERN_CONFIG.triangle.flatToleranceAtr).toBeGreaterThan(0);
    expect(PATTERN_CONFIG.outcomeHorizon).toBe(10);
    expect(PATTERN_CONFIG.returnHorizons).toEqual([1, 3, 5]);
    expect(PATTERN_CONFIG.formationMinResolved).toBe(8);
  });
});
