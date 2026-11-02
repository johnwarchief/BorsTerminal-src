import { describe, it, expect } from 'vitest';
import {
  detectPatternsAtIndex,
  detectLatestPattern,
  detectFairValueGaps,
  estimateMarketRegime,
  scanCandleEdge,
} from '../candleEdgeScanner';
import type { Candle } from '../types';

describe('candleEdgeScanner pattern detection', () => {
  it('detects a Doji pattern', () => {
    const candles: Candle[] = [
      { timestamp: 1000, open: 100, high: 110, low: 90, close: 100.5, volume: 100 },
    ];
    const patterns = detectPatternsAtIndex(candles, 0);
    expect(patterns.some((p) => p.type === 'DOJI')).toBe(true);
  });

  it('detects a Hammer pattern', () => {
    // Open 100, Close 102 (body = 2), High 103 (upper wick = 1 <= 0.25*range), Low 90 (lower wick = 10 >= 2*body)
    const candles: Candle[] = [
      { timestamp: 1000, open: 100, high: 103, low: 90, close: 102, volume: 100 },
    ];
    const patterns = detectPatternsAtIndex(candles, 0);
    expect(patterns.some((p) => p.type === 'HAMMER')).toBe(true);
    expect(patterns[0].isBullish).toBe(true);
  });

  it('detects an Inverted Hammer pattern', () => {
    // Open 100, Close 102 (body = 2), High 115 (upper wick = 13 >= 2*body), Low 99.5 (lower wick = 0.5 <= 0.25*range)
    const candles: Candle[] = [
      { timestamp: 1000, open: 100, high: 115, low: 99.5, close: 102, volume: 100 },
    ];
    const patterns = detectPatternsAtIndex(candles, 0);
    expect(patterns.some((p) => p.type === 'INVERTED_HAMMER')).toBe(true);
  });

  it('detects Bullish Engulfing pattern', () => {
    const candles: Candle[] = [
      // Bar 0: Red candle open=100, close=90
      { timestamp: 1000, open: 100, high: 102, low: 88, close: 90, volume: 100 },
      // Bar 1: Green candle open=89, close=102 (engulfs 90-100)
      { timestamp: 2000, open: 89, high: 104, low: 87, close: 102, volume: 150 },
    ];
    const patterns = detectPatternsAtIndex(candles, 1);
    expect(patterns.some((p) => p.type === 'BULLISH_ENGULFING')).toBe(true);
  });

  it('detects Bearish Engulfing pattern', () => {
    const candles: Candle[] = [
      // Bar 0: Green candle open=90, close=100
      { timestamp: 1000, open: 90, high: 102, low: 88, close: 100, volume: 100 },
      // Bar 1: Red candle open=101, close=88 (engulfs 90-100)
      { timestamp: 2000, open: 101, high: 103, low: 86, close: 88, volume: 150 },
    ];
    const patterns = detectPatternsAtIndex(candles, 1);
    expect(patterns.some((p) => p.type === 'BEARISH_ENGULFING')).toBe(true);
  });

  it('detects Morning Star pattern', () => {
    const candles: Candle[] = [
      // Bar 0: Long bearish bar
      { timestamp: 1000, open: 120, high: 122, low: 98, close: 100, volume: 100 },
      // Bar 1: Small star/doji
      { timestamp: 2000, open: 98, high: 100, low: 95, close: 97, volume: 80 },
      // Bar 2: Strong bullish bar closing above midpoint (110)
      { timestamp: 3000, open: 98, high: 116, low: 97, close: 114, volume: 160 },
    ];
    const patterns = detectPatternsAtIndex(candles, 2);
    expect(patterns.some((p) => p.type === 'MORNING_STAR')).toBe(true);
  });

  it('detects Evening Star pattern', () => {
    const candles: Candle[] = [
      // Bar 0: Long bullish bar
      { timestamp: 1000, open: 100, high: 122, low: 98, close: 120, volume: 100 },
      // Bar 1: Small star
      { timestamp: 2000, open: 122, high: 125, low: 120, close: 121, volume: 80 },
      // Bar 2: Strong bearish bar closing below midpoint (110)
      { timestamp: 3000, open: 120, high: 121, low: 102, close: 105, volume: 160 },
    ];
    const patterns = detectPatternsAtIndex(candles, 2);
    expect(patterns.some((p) => p.type === 'EVENING_STAR')).toBe(true);
  });

  it('detects Bullish and Bearish Pinbar', () => {
    // Bullish pinbar: lower wick >= 0.6 * range, upper wick <= 0.2 * range
    const bullPin: Candle[] = [
      { timestamp: 1000, open: 108, high: 110, low: 80, close: 107, volume: 100 },
    ];
    expect(detectPatternsAtIndex(bullPin, 0).some((p) => p.type === 'BULLISH_PINBAR')).toBe(true);

    // Bearish pinbar: upper wick >= 0.6 * range, lower wick <= 0.2 * range
    const bearPin: Candle[] = [
      { timestamp: 1000, open: 82, high: 110, low: 80, close: 83, volume: 100 },
    ];
    expect(detectPatternsAtIndex(bearPin, 0).some((p) => p.type === 'BEARISH_PINBAR')).toBe(true);
  });

  it('retrieves the latest pattern accurately', () => {
    const candles: Candle[] = [
      { timestamp: 1000, open: 100, high: 102, low: 98, close: 101, volume: 100 },
      { timestamp: 2000, open: 100, high: 103, low: 85, close: 102, volume: 100 }, // Hammer
    ];
    const latest = detectLatestPattern(candles);
    expect(latest?.type).toBe('HAMMER');
  });
});

describe('SMC Fair Value Gaps and Market Regime', () => {
  it('detects Bullish Fair Value Gap and tracks mitigation', () => {
    const candles: Candle[] = [
      // Candle 0: H=100, L=90
      { timestamp: 1000, open: 92, high: 100, low: 90, close: 98, volume: 100 },
      // Candle 1: Big impulsive green: H=120, L=98
      { timestamp: 2000, open: 99, high: 120, low: 98, close: 118, volume: 200 },
      // Candle 2: H=130, L=105 -> Gap between L(2)=105 and H(0)=100 is 5
      { timestamp: 3000, open: 106, high: 130, low: 105, close: 125, volume: 150 },
    ];

    const zones = detectFairValueGaps(candles);
    expect(zones.length).toBe(1);
    expect(zones[0].isBullish).toBe(true);
    expect(zones[0].top).toBe(105);
    expect(zones[0].bottom).toBe(100);
    expect(zones[0].equilibrium).toBe(102.5);
    expect(zones[0].mitigated).toBe(false);

    // Candle 3: Price retraces and touches 102.0 (below equilibrium 102.5) -> mitigated!
    candles.push({
      timestamp: 4000,
      open: 120,
      high: 122,
      low: 102,
      close: 105,
      volume: 120,
    });
    const updatedZones = detectFairValueGaps(candles);
    expect(updatedZones[0].mitigated).toBe(true);
    expect(updatedZones[0].mitigatedTs).toBe(4000);
  });

  it('estimates market regime correctly', () => {
    const bullCandles: Candle[] = [];
    for (let i = 0; i < 25; i++) {
      bullCandles.push({
        timestamp: 1000 + i * 100,
        open: 100 + i * 5,
        high: 108 + i * 5,
        low: 99 + i * 5,
        close: 106 + i * 5,
        volume: 1000,
      });
    }
    expect(estimateMarketRegime(bullCandles)).toBe('TRENDING_BULL');

    const bearCandles: Candle[] = [];
    for (let i = 0; i < 25; i++) {
      bearCandles.push({
        timestamp: 1000 + i * 100,
        open: 200 - i * 5,
        high: 202 - i * 5,
        low: 190 - i * 5,
        close: 192 - i * 5,
        volume: 1000,
      });
    }
    expect(estimateMarketRegime(bearCandles)).toBe('TRENDING_BEAR');
  });
});

describe('scanCandleEdge empirical edge report', () => {
  it('returns safe fallback on small sample size', () => {
    const candles: Candle[] = [
      { timestamp: 1000, open: 100, high: 105, low: 95, close: 102, volume: 100 },
    ];
    const report = scanCandleEdge(candles, 'TEST');
    expect(report.symbol).toBe('TEST');
    expect(report.sampleCount).toBe(0);
    expect(report.winRate1Bar).toBe(50);
  });

  it('calculates forward statistical edge across historical candles', () => {
    const candles: Candle[] = [];
    let price = 1000;
    // Generate 40 historical candles with upward trend and pullbacks
    for (let i = 0; i < 40; i++) {
      const isUp = i % 3 !== 0;
      const change = isUp ? 15 : -8;
      const open = price;
      price += change;
      const close = price;
      candles.push({
        timestamp: 1700000000 + i * 86400,
        open,
        high: Math.max(open, close) + 5,
        low: Math.min(open, close) - 5,
        close,
        volume: 5000 + i * 100,
      });
    }

    const report = scanCandleEdge(candles, 'FOOLAD');
    expect(report.symbol).toBe('FOOLAD');
    expect(report.sampleCount).toBeGreaterThan(0);
    expect(report.winRate1Bar).toBeGreaterThanOrEqual(0);
    expect(report.winRate1Bar).toBeLessThanOrEqual(100);
    expect(report.winRate3Bar).toBeGreaterThanOrEqual(0);
    expect(report.winRate5Bar).toBeGreaterThanOrEqual(0);
    expect(report.profitFactor).toBeGreaterThan(0);
    expect(report.riskRewardRatio).toBeGreaterThan(0);
    expect(['TRENDING_BULL', 'TRENDING_BEAR', 'RANGING']).toContain(report.marketRegime);
    expect(Array.isArray(report.activeZones)).toBe(true);
  });
});
