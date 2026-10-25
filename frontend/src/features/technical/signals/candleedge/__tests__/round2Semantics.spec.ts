import { describe, expect, it } from 'vitest';
import {
  detectAscendingTriangle,
  detectDoubleTop,
  detectLiquiditySweepHigh,
  isDoji,
  isHammer,
  isShootingStar,
  scanPatterns,
} from '../index';
import type { Candle } from '../types';
import { candle, swing } from './helpers';

const flatCandles = (n: number, price = 100): Candle[] =>
  Array.from({ length: n }, (_, i) => candle(i, price, price, price, price));

/**
 * Level 101 is a confirmed swing high at index 10. Bar 45 tests a break, and
 * bar 47 forms a higher swing high whose high pierces the level. The two
 * knobs separate a close-based structural break from an HH / wick event.
 */
function bosFixture(options: {
  breakHigh: number;
  breakClose: number;
  peakHigh: number;
  peakClose: number;
}): Candle[] {
  const out = flatCandles(70, 100);
  out[10] = candle(10, 100, 101, 99.8, 100.4);
  for (const i of [8, 9, 11, 12]) out[i] = candle(i, 100, 100.5, 99.8, 100);
  out[45] = candle(45, 100, options.breakHigh, 99.9, options.breakClose);
  const hold = options.breakClose > 101 ? options.breakClose : 100.7;
  out[46] = candle(46, options.breakClose, Math.max(101.2, hold + 0.2), 99.9, hold);
  out[47] = candle(47, 100.6, options.peakHigh, 100, options.peakClose);
  out[48] = candle(
    48,
    options.peakClose,
    Math.max(100.8, options.peakClose),
    99.9,
    100.2,
  );
  out[49] = candle(49, 100.2, 100.7, 99.8, 100);
  return out;
}

describe('Round 2: BOS measures a close through structure at the break bar', () => {
  it('confirms on the bar that closes through the confirmed swing high', () => {
    const candles = bosFixture({
      breakHigh: 101.7,
      breakClose: 101.2,
      peakHigh: 105.5,
      peakClose: 105.3,
    });
    const full = scanPatterns(candles);
    const bos = full.events.filter((e) => e.detector === 'bos_bullish');

    expect(bos.map((e) => e.confirmedAtIndex)).toEqual([45]);
    expect(bos[0]).toMatchObject({ level: 101, bias: 'bullish', status: 'confirmed' });
    expect(bos[0].anchors).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ index: 10, price: 101, role: 'high' }),
        expect.objectContaining({ index: 45, role: 'candle' }),
      ]),
    );

    const prefix = scanPatterns(candles.slice(0, 46));
    expect(prefix.events.find((e) => e.key === 'bos_bullish@45')).toEqual(bos[0]);
  });

  it('does not treat a higher high whose close stays below the level as BOS', () => {
    const candles = bosFixture({
      breakHigh: 101.4,
      breakClose: 100.9,
      peakHigh: 102.5,
      peakClose: 100.6,
    });
    const events = scanPatterns(candles).events;

    expect(events.filter((e) => e.detector === 'bos_bullish')).toEqual([]);
    expect(
      events.some(
        (e) => e.detector === 'liquidity_sweep_high' && e.confirmedAtIndex === 45,
      ),
    ).toBe(true);
  });

  it('leaves the source 0.5% level distance out of the default break rule', () => {
    const candles = bosFixture({
      breakHigh: 101.4,
      breakClose: 101.2,
      peakHigh: 101.2,
      peakClose: 100.4,
    });
    expect(scanPatterns(candles).events.some((e) => e.detector === 'bos_bullish')).toBe(true);
    expect(
      scanPatterns(candles, { bosThreshold: 0.005 }).events.some(
        (e) => e.detector === 'bos_bullish',
      ),
    ).toBe(false);
  });
});

describe('Round 2: liquidity sweeps require a level known before the bar', () => {
  it('ignores a level confirmed on the sweep bar itself', () => {
    const candles = flatCandles(40);
    candles[30] = candle(30, 108, 111, 107, 109);
    const sameBar = { highs: [swing(10, 100, 13), swing(20, 110, 30)], lows: [] };
    expect(detectLiquiditySweepHigh(candles, 30, sameBar)).toBeNull();

    const knownBefore = { highs: [swing(10, 100, 13), swing(20, 110, 29)], lows: [] };
    expect(detectLiquiditySweepHigh(candles, 30, knownBefore)).toMatchObject({
      detector: 'liquidity_sweep_high',
      sweptLevel: 110,
    });
  });

  it('requires price to be below the level before the sweep bar', () => {
    const candles = flatCandles(40);
    candles[29] = candle(29, 111, 112, 110, 111);
    candles[30] = candle(30, 111, 112, 107, 109);
    const swings = { highs: [swing(10, 100, 13), swing(20, 110, 23)], lows: [] };
    expect(detectLiquiditySweepHigh(candles, 30, swings)).toBeNull();
  });
});

describe('Round 2: triangles need temporal overlap and must not cross', () => {
  it('rejects two boundary lines that never share a bar range', () => {
    const highs = [swing(10, 100, 13), swing(20, 100.02, 23)];
    const lows = [swing(100, 80, 103), swing(110, 90, 113)];
    expect(detectAscendingTriangle(highs, lows)).toBeNull();
  });

  it('rejects an ascending triangle whose support rises through resistance', () => {
    const highs = [swing(10, 100, 13), swing(30, 100.02, 33)];
    const lows = [swing(20, 99, 23), swing(40, 103, 43)];
    expect(detectAscendingTriangle(highs, lows)).toBeNull();
  });

  it('still accepts a triangle whose lines overlap and stay ordered', () => {
    const highs = [swing(10, 100, 13), swing(30, 100.02, 33)];
    const lows = [swing(20, 80, 23), swing(40, 90, 43)];
    expect(detectAscendingTriangle(highs, lows)?.detector).toBe('ascending_triangle');
  });
});

describe('Round 2: double tops reject an intervening higher peak', () => {
  it('does not pair peaks across a higher high', () => {
    const candles = flatCandles(40);
    candles[15] = candle(15, 96, 100, 95, 96);
    candles[25] = candle(25, 105, 110, 104, 105);
    const peaks = [swing(10, 100, 15), swing(19, 110, 24), swing(30, 101, 35)];
    expect(detectDoubleTop(candles, peaks, 35, 15)).toBeNull();
  });

  it('keeps a double top with a lower intervening peak', () => {
    const candles = flatCandles(40);
    candles[15] = candle(15, 96, 100, 95, 96);
    const peaks = [swing(10, 100, 15), swing(13, 99, 18), swing(30, 101, 35)];
    expect(detectDoubleTop(candles, peaks, 35, 15)?.detector).toBe('double_top');
  });
});

describe('Round 2: candlestick geometry with no range', () => {
  it('does not call a locked zero-range bar a doji', () => {
    expect(isDoji(candle(0, 100, 100, 100, 100))).toBe(false);
  });

  it('still accepts a zero body when the bar has range', () => {
    expect(isDoji(candle(0, 100, 101, 99, 100))).toBe(true);
  });
});

describe('Round 2: reversal context excludes the pattern bar', () => {
  const decline = Array.from({ length: 21 }, (_, i) => {
    const close = 101.5 - i * 0.05;
    return candle(i, close, close + 0.2, close - 0.2, close);
  });

  it('accepts a hammer whose own close crosses the 20-bar reference', () => {
    const hammer = candle(21, 100, 102.9, 95.9, 102);
    expect(isHammer([...decline, hammer], 21)).toBe(true);
  });

  it('accepts a shooting star whose own close crosses the 20-bar reference', () => {
    const advance = Array.from({ length: 21 }, (_, i) => {
      const close = 100.5 + i * 0.05;
      return candle(i, close, close + 0.2, close - 0.2, close);
    });
    const star = candle(21, 102, 106.1, 99.9, 100);
    expect(isShootingStar([...advance, star], 21)).toBe(true);
  });
});
