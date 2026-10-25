import { describe, expect, it } from 'vitest';
import fixture from './fixtures/apal-d-adjusted.json';
import { scanPatterns } from '../index';
import type { Candle, DetectorId } from '../types';

type Row = [string, number, number, number, number, number];

// A verbatim copy of the production-adjusted اپال daily series from the real
// run. It is the only fixture that triggers every detector family at once.
const bars: Candle[] = (fixture.bars as unknown as Row[]).map(
  ([time, open, high, low, close, volume]) => ({ time, open, high, low, close, volume }),
);

const ALL_DETECTORS: DetectorId[] = [
  'doji',
  'bullish_engulfing',
  'bearish_engulfing',
  'hammer',
  'shooting_star',
  'double_top',
  'double_bottom',
  'ascending_triangle',
  'descending_triangle',
  'symmetrical_triangle',
  'rising_wedge',
  'falling_wedge',
  'higher_high',
  'higher_low',
  'lower_high',
  'lower_low',
  'bos_bullish',
  'bos_bearish',
  'liquidity_sweep_high',
  'liquidity_sweep_low',
];

const confirmedBefore = <T extends { confirmedAtIndex: number }>(items: T[], limit: number) =>
  items.filter((item) => item.confirmedAtIndex < limit);

describe('real-data prefix stability across all detectors', () => {
  const full = scanPatterns(bars);

  it('uses a real series that triggers all 20 detectors', () => {
    const seen = new Set(full.events.map((event) => event.detector));
    expect(seen.size).toBe(20);
    for (const detector of ALL_DETECTORS) expect(seen.has(detector)).toBe(true);
    expect(fixture.barCount).toBe(bars.length);
  });

  it('keeps every detector prefix-stable on the real adjusted series', () => {
    for (const length of [60, 100, 150, 200, 250, 300, 350, 400, 455]) {
      const prefix = scanPatterns(bars.slice(0, length));
      const expected = confirmedBefore(full.events, length);
      const actual = confirmedBefore(prefix.events, length);
      expect(actual).toEqual(expected);
      for (const detector of ALL_DETECTORS) {
        expect(actual.filter((event) => event.detector === detector)).toEqual(
          expected.filter((event) => event.detector === detector),
        );
      }
      expect(confirmedBefore(prefix.swings.highs, length)).toEqual(
        confirmedBefore(full.swings.highs, length),
      );
      expect(confirmedBefore(prefix.swings.lows, length)).toEqual(
        confirmedBefore(full.swings.lows, length),
      );
    }
  });

  it('does not rewrite a real confirmed event when future bars are appended', () => {
    const lastTime = Date.parse(String(bars[bars.length - 1].time));
    const future: Candle[] = Array.from({ length: 120 }, (_, index) => {
      const base = 20_000 + index * 40;
      return {
        time: new Date(lastTime + (index + 1) * 86_400_000).toISOString().slice(0, 10),
        open: base,
        high: base + 80,
        low: base - 40,
        close: base + 20,
        volume: 1000,
      };
    });
    const extended = scanPatterns([...bars, ...future]);
    for (const event of full.events) {
      expect(extended.events.find((candidate) => candidate.key === event.key)).toEqual(event);
    }
  });
});
