import { describe, expect, it } from 'vitest';
import { applyAdjustmentToCandles } from '@features/technical/nahayatnegar/lib/adjustments';
import { scanPatterns } from '../index';
import { buildAdjustedTwoPeakSeries } from './helpers';

describe('adjusted candle input (production adjustment path, not reimplemented)', () => {
  const fixture = buildAdjustedTwoPeakSeries();

  it('adjusts every OHLC field through the existing production function', () => {
    expect(fixture.factors).toHaveLength(40);
    expect(fixture.raw[25].high).toBe(200);
    expect(fixture.adjusted[25].high).toBe(100);
    expect(fixture.adjusted[25].open).toBeCloseTo(fixture.raw[25].open * 0.5, 4);
    expect(fixture.adjusted[25].low).toBeCloseTo(fixture.raw[25].low * 0.5, 4);
    expect(fixture.adjusted[38].low).toBe(47);
    expect(fixture.adjusted[55].high).toBe(102);
  });

  it('finds a double top on the adjusted series that the raw series hides', () => {
    const raw = scanPatterns(fixture.raw);
    const adjusted = scanPatterns(fixture.adjusted);
    expect(raw.events.some((e) => e.detector === 'double_top')).toBe(false);
    const event = adjusted.events.find((e) => e.detector === 'double_top');
    expect(event).toBeDefined();
    expect(event?.anchors.map((a) => a.price)).toEqual([100, 102]);
  });

  it('keeps the raw mode compatible (no adjustment, no crash, candle patterns intact)', () => {
    const raw = scanPatterns(fixture.raw);
    expect(raw.events.length).toBeGreaterThan(0);
    const engulfing = [
      { time: 0, open: 60, high: 61, low: 49, close: 50, volume: 1 },
      { time: 1, open: 50, high: 61, low: 49, close: 60, volume: 1 },
    ];
    expect(scanPatterns(engulfing).events.some((e) => e.detector === 'bullish_engulfing')).toBe(
      true,
    );
  });

  it('does not mutate the caller candles', () => {
    const beforeRaw = JSON.parse(JSON.stringify(fixture.raw));
    const beforeAdjusted = JSON.parse(JSON.stringify(fixture.adjusted));
    scanPatterns(fixture.raw);
    scanPatterns(fixture.adjusted);
    expect(fixture.raw).toEqual(beforeRaw);
    expect(fixture.adjusted).toEqual(beforeAdjusted);
  });

  it('uses the production path once: calling it twice is idempotent', () => {
    const again = applyAdjustmentToCandles(
      fixture.raw.map((c) => ({
        timestamp: c.time as number,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume,
      })),
      fixture.factors,
      'combined',
    ).map((c) => ({ ...c }));
    expect(again[25].high).toBe(100);
  });
});
