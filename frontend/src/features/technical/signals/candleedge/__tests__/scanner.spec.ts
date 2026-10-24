import { describe, expect, it } from 'vitest';
import { scanPatterns } from '../index';
import { buildAdjustedTwoPeakSeries, candle } from './helpers';

describe('scanPatterns event contract', () => {
  const { adjusted } = buildAdjustedTwoPeakSeries();

  it('emits the double top once, at the confirmation bar of the second peak', () => {
    const result = scanPatterns(adjusted);
    const doubleTops = result.events.filter((e) => e.detector === 'double_top');
    expect(doubleTops).toHaveLength(1);
    expect(doubleTops[0]).toMatchObject({
      detector: 'double_top',
      family: 'chart_structure',
      bias: 'bearish',
      status: 'confirmed',
      confirmedAtIndex: 60,
    });
    expect(doubleTops[0].anchors.map((a) => a.index)).toEqual([25, 55]);
    expect(doubleTops[0].key).toBe('double_top@60');
  });

  it('every event is confirmed with anchors no later than its confirmation bar', () => {
    const result = scanPatterns(adjusted);
    expect(result.events.length).toBeGreaterThan(0);
    const keys = new Set<string>();
    let previous = -1;
    for (const event of result.events) {
      expect(event.status).toBe('confirmed');
      expect(event.key).toBe(`${event.detector}@${event.confirmedAtIndex}`);
      expect(keys.has(event.key)).toBe(false);
      keys.add(event.key);
      expect(event.confirmedAtIndex).toBeGreaterThanOrEqual(previous);
      previous = event.confirmedAtIndex;
      expect(event.confirmedAt).toBe(adjusted[event.confirmedAtIndex].time);
      expect(event.startIndex).toBeLessThanOrEqual(event.confirmedAtIndex);
      for (const anchor of event.anchors) {
        expect(anchor.index).toBeLessThanOrEqual(event.confirmedAtIndex);
        expect(anchor.index).toBeGreaterThanOrEqual(event.startIndex);
        expect(anchor.time).toBe(adjusted[anchor.index].time);
      }
    }
  });

  it('never turns a swing into a pattern event', () => {
    expect(
      scanPatterns(adjusted).events.some((e) => String(e.detector).startsWith('swing')),
    ).toBe(false);
  });

  it('reports swings with their confirmation index', () => {
    const { highs } = scanPatterns(adjusted).swings;
    const first = highs.find((p) => p.index === 25);
    expect(first).toMatchObject({ price: 100, confirmedAtIndex: 28 });
  });

  it('times a candle pattern at its own bar', () => {
    const series = [candle(0, 60, 61, 49, 50), candle(1, 50, 61, 49, 60)];
    const result = scanPatterns(series);
    const event = result.events.find((e) => e.detector === 'bullish_engulfing');
    expect(event).toMatchObject({
      confirmedAtIndex: 1,
      confirmedAt: 1,
      family: 'candlestick',
      bias: 'bullish',
    });
    expect(event?.anchors.map((a) => a.index)).toEqual([0, 1]);
  });

  it('does not evaluate chart structure before the source 41-bar minimum', () => {
    const result = scanPatterns(adjusted.slice(0, 41));
    expect(result.events.every((e) => e.family === 'candlestick')).toBe(true);
  });

  it('returns provisional tail extrema separately from confirmed swings', () => {
    const series = [
      candle(0, 10, 11, 9, 10),
      candle(1, 10.5, 12, 10, 11),
      candle(2, 11, 13, 10.5, 12),
      candle(3, 12, 20, 11, 19),
      candle(4, 19, 19.5, 18, 18.5),
    ];
    const result = scanPatterns(series);
    expect(result.provisionalSwings.some((p) => p.index === 3 && p.detector === 'swing_high')).toBe(
      true,
    );
    expect(result.swings.highs.some((p) => p.index === 3)).toBe(false);
  });
});
