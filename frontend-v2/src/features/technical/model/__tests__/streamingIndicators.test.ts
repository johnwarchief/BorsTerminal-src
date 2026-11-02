import { describe, it, expect, beforeEach } from 'vitest';
import { StreamingIndicatorEngine } from '../streamingIndicators';
import type { Candle } from '../types';

describe('StreamingIndicatorEngine', () => {
  let engine: StreamingIndicatorEngine;

  beforeEach(() => {
    engine = new StreamingIndicatorEngine({
      smaPeriod: 5,
      emaPeriod: 5,
      rsiPeriod: 5,
      macdFast: 3,
      macdSlow: 6,
      macdSignal: 3,
      bbPeriod: 5,
      bbStdDev: 2,
      atrPeriod: 5,
    });
  });

  function makeCandle(i: number, close: number, high?: number, low?: number): Candle {
    return {
      timestamp: 1700000000 + i * 86400,
      open: close - 2,
      high: high ?? close + 5,
      low: low ?? close - 5,
      close,
      volume: 1000 + i * 10,
    };
  }

  it('starts unstable with null values', () => {
    expect(engine.isStable()).toBe(false);
    const initial = engine.getLatestValues();
    expect(initial.sma).toBeNull();
    expect(initial.ema).toBeNull();
    expect(initial.rsi).toBeNull();
    expect(initial.macd).toBeNull();
    expect(initial.bollingerBands).toBeNull();
    expect(initial.atr).toBeNull();
  });

  it('updates incrementally and stabilizes as required bars arrive', () => {
    const prices = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20];

    for (let i = 0; i < prices.length; i++) {
      engine.update(makeCandle(i, prices[i]));
    }

    const latest = engine.getLatestValues();
    expect(engine.isStable()).toBe(true);

    // SMA of last 5 bars: [16, 17, 18, 19, 20] -> 18
    expect(latest.sma).toBe(18);

    // EMA is close to 18-19
    expect(latest.ema).toBeGreaterThan(17);
    expect(latest.ema).toBeLessThanOrEqual(20);

    // RSI should be high because price is monotonically increasing
    expect(latest.rsi).toBe(100);

    // MACD should be defined
    expect(latest.macd).toBeDefined();
    expect(latest.macd?.macd).toBeTypeOf('number');
    expect(latest.macd?.signal).toBeTypeOf('number');
    expect(latest.macd?.histogram).toBeTypeOf('number');

    // BollingerBands
    expect(latest.bollingerBands).toBeDefined();
    expect(latest.bollingerBands?.middle).toBe(18);
    expect(latest.bollingerBands?.upper).toBeGreaterThan(18);
    expect(latest.bollingerBands?.lower).toBeLessThan(18);

    // ATR
    expect(latest.atr).toBeDefined();
    expect(latest.atr).toBeGreaterThan(0);
  });

  it('processes batch historical candles with updateBatch', () => {
    const candles: Candle[] = [];
    for (let i = 0; i < 25; i++) {
      candles.push(makeCandle(i, 100 + (i % 5) * 2));
    }

    const batchResults = engine.updateBatch(candles);
    expect(batchResults.length).toBe(25);
    expect(engine.isStable()).toBe(true);

    const last = batchResults[batchResults.length - 1];
    expect(last.sma).not.toBeNull();
    expect(last.bollingerBands).not.toBeNull();
    expect(last.atr).not.toBeNull();
  });

  it('resets all indicators to unstable state', () => {
    for (let i = 0; i < 15; i++) {
      engine.update(makeCandle(i, 50 + i));
    }
    expect(engine.isStable()).toBe(true);

    engine.reset();
    expect(engine.isStable()).toBe(false);
    const cleared = engine.getLatestValues();
    expect(cleared.sma).toBeNull();
    expect(cleared.ema).toBeNull();
    expect(cleared.rsi).toBeNull();
  });
});
