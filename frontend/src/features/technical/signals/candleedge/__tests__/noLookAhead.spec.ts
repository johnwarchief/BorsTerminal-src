import { describe, expect, it } from 'vitest';
import { findSwingPoints, scanPatterns } from '../index';
import type { Candle } from '../types';
import { buildAdjustedTwoPeakSeries, candle, randomWalk } from './helpers';

const confirmedBefore = <T extends { confirmedAtIndex: number }>(items: T[], limit: number) =>
  items.filter((item) => item.confirmedAtIndex < limit);

describe('no look-ahead and prefix stability', () => {
  const { adjusted } = buildAdjustedTwoPeakSeries();
  const full = scanPatterns(adjusted);

  it('events confirmed in a prefix are identical to the full-series run', () => {
    for (const length of [60, 61, 65, 70, 75, 80]) {
      const prefix = scanPatterns(adjusted.slice(0, length));
      expect(confirmedBefore(prefix.events, length)).toEqual(
        confirmedBefore(full.events, length),
      );
      expect(confirmedBefore(prefix.swings.highs, length)).toEqual(
        confirmedBefore(full.swings.highs, length),
      );
      expect(confirmedBefore(prefix.swings.lows, length)).toEqual(
        confirmedBefore(full.swings.lows, length),
      );
    }
  });

  it('appending future bars never rewrites an already-confirmed event', () => {
    const prefix = scanPatterns(adjusted.slice(0, 61));
    const original = prefix.events.find((e) => e.key === 'double_top@60');
    expect(original).toBeDefined();

    const future: Candle[] = Array.from({ length: 120 }, (_, i) => {
      const base = 200 + i * 20;
      const lastTime = adjusted[adjusted.length - 1].time as number;
      return candle(lastTime + (i + 1) * 86_400_000, base, base + 30, base - 5, base + 10);
    });
    const extended = scanPatterns([...adjusted, ...future]);
    expect(extended.events.find((e) => e.key === 'double_top@60')).toEqual(original);
  });

  it('a candle pattern appears at its own bar and never earlier', () => {
    const series = [candle(0, 60, 61, 49, 50), candle(1, 50, 61, 49, 60), candle(2, 61, 62, 55, 56)];
    expect(scanPatterns(series.slice(0, 1)).events).toEqual([]);
    const atBarTwo = scanPatterns(series.slice(0, 2)).events;
    const atBarThree = scanPatterns(series).events;
    expect(atBarTwo.find((e) => e.detector === 'bullish_engulfing')).toBeDefined();
    expect(atBarTwo).toEqual(
      atBarThree.filter((e) => e.confirmedAtIndex < 2),
    );
  });

  it('a tail candidate is provisional and only becomes a swing at its confirmation bar', () => {
    const closes = [100, 101, 102, 103, 104, 105, 106, 107];
    const highs = [101, 102, 103, 104, 105, 106, 110, 108];
    const lows = [99, 100, 101, 102, 103, 104, 105, 105];
    const series: Candle[] = closes.map((close, i) =>
      candle(i, close, highs[i], lows[i], close),
    );
    const before = scanPatterns(series);
    expect(before.provisionalSwings.some((p) => p.index === 6)).toBe(true);
    expect(findSwingPoints(series, 3).highs.some((p) => p.index === 6)).toBe(false);

    const after = [...series, candle(8, 105, 106, 104, 105), candle(9, 104, 105, 103, 104)];
    const confirmed = findSwingPoints(after, 3).highs.find((p) => p.index === 6);
    expect(confirmed?.confirmedAtIndex).toBe(9);
    const scanAfter = scanPatterns(after);
    expect(scanAfter.swings.highs.some((p) => p.index === 6)).toBe(true);
    expect(
      scanAfter.events.some(
        (e) =>
          e.family !== 'candlestick' &&
          e.confirmedAtIndex < 9 &&
          e.anchors.some((a) => a.index === 6),
      ),
    ).toBe(false);
  });

  it('holds for a longer synthetic walk', () => {
    const walk = randomWalk(400, 7);
    const fullWalk = scanPatterns(walk);
    for (const length of [120, 200, 300]) {
      const prefix = scanPatterns(walk.slice(0, length));
      expect(confirmedBefore(prefix.events, length)).toEqual(
        confirmedBefore(fullWalk.events, length),
      );
    }
  });
});
