import { describe, expect, it } from 'vitest';
import { findLocalExtrema, findProvisionalSwings, findSwingPoints } from '../index';
import type { Candle } from '../types';

function fromHighsLows(highs: number[], lows: number[]): Candle[] {
  return highs.map((high, i) => {
    const mid = (high + lows[i]) / 2;
    return { time: i, open: mid, high, low: lows[i], close: mid };
  });
}

const symmetric = () =>
  fromHighsLows(
    [10, 11, 12, 13, 20, 13, 12, 11, 10],
    [5, 5.5, 6, 6.5, 7, 6.5, 6, 5.5, 5],
  );

describe('ported swing-point detection', () => {
  it('confirms a strict pivot only after the right window closes', () => {
    const { highs, lows } = findSwingPoints(symmetric(), 3);
    expect(highs.map((p) => [p.index, p.price, p.confirmedAtIndex])).toEqual([[4, 20, 7]]);
    expect(lows).toEqual([]);
  });

  it('rejects equal highs (source uses strict inequality)', () => {
    const candles = fromHighsLows(
      [10, 11, 12, 13, 20, 20, 12, 11, 10],
      [5, 5.5, 6, 6.5, 7, 6.5, 6, 5.5, 5],
    );
    expect(findSwingPoints(candles, 3).highs).toEqual([]);
  });

  it('uses the same strictness for the 5-bar local-extrema scan', () => {
    const candles = fromHighsLows(
      [10, 11, 12, 13, 14, 21, 14, 13, 12, 11, 10],
      [5, 5.5, 6, 6.5, 7, 7.5, 7, 6.5, 6, 5.5, 5],
    );
    const { peaks } = findLocalExtrema(candles, 5);
    expect(peaks.map((p) => [p.index, p.confirmedAtIndex])).toEqual([[5, 10]]);
  });

  it('marks unconfirmed extrema in the tail as provisional, never as swings', () => {
    const candles = fromHighsLows([1, 2, 3, 9, 2], [0.5, 0.6, 0.7, 0.8, 0.9]);
    const { highs } = findSwingPoints(candles, 2);
    expect(highs).toEqual([]);
    const provisional = findProvisionalSwings(candles, 2);
    expect(provisional).toHaveLength(1);
    expect(provisional[0]).toMatchObject({
      detector: 'swing_high',
      index: 3,
      price: 9,
      status: 'provisional',
      confirmedAtIndex: null,
    });
  });

  it('keeps an already-confirmed pivot unchanged when later bars exceed it', () => {
    const base = symmetric();
    const extended = [
      ...base,
      ...Array.from({ length: 10 }, (_, i) => {
        const high = 30 + i;
        return { time: 9 + i, open: 25, high, low: 24, close: 25 };
      }),
    ];
    const before = findSwingPoints(base, 3).highs;
    const after = findSwingPoints(extended, 3).highs;
    expect(after.filter((p) => p.index === 4)).toEqual(before.filter((p) => p.index === 4));
  });
});
