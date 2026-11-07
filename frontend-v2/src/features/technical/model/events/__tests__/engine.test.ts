import { describe, expect, it } from 'vitest';
import { calculateAtr, type EngineCandle } from '../../doubleTapEngine';
import { EVENT_CONFIG } from '../config';
import { detectChannel } from '../channel';
import { detectPullbackBreakout } from '../pullback';
import { classifyDivergence, computeRsi } from '../rsi';
import { scanChart } from '../scan';

function makeCandles(closes: number[], spread = 1): EngineCandle[] {
  return closes.map((close, i) => ({
    timestamp: 1_700_000_000_000 + i * 86_400_000,
    open: close - 0.2,
    high: close + spread,
    low: close - spread,
    close,
    volume: 1_000_000 + i,
  }));
}

describe('RSI divergence primitives', () => {
  it('computes 100 for an all-gain series and 0 for an all-loss series', () => {
    const up = Array.from({ length: 20 }, (_, i) => 100 + i);
    const down = Array.from({ length: 20 }, (_, i) => 100 - i);
    expect(computeRsi(up, 14).at(-1)).toBe(100);
    expect(computeRsi(down, 14).at(-1)).toBe(0);
  });

  it('classifies all four divergence types and rejects a flat pair', () => {
    const cfg = EVENT_CONFIG.divergence;
    expect(classifyDivergence('high', 100, 110, 70, 60, 2, cfg)).toBe('RSI_REGULAR_BEARISH');
    expect(classifyDivergence('high', 110, 100, 60, 70, 2, cfg)).toBe('RSI_HIDDEN_BEARISH');
    expect(classifyDivergence('low', 100, 90, 30, 40, 2, cfg)).toBe('RSI_REGULAR_BULLISH');
    expect(classifyDivergence('low', 90, 100, 40, 30, 2, cfg)).toBe('RSI_HIDDEN_BULLISH');
    expect(classifyDivergence('high', 100, 100.5, 70, 60, 2, cfg)).toBeNull();
  });
});

describe('channel detector', () => {
  it('finds a high-R² rising regression channel', () => {
    const closes = Array.from({ length: 120 }, (_, i) => 100 + i * 0.5);
    const candles = makeCandles(closes, 0.8);
    const event = detectChannel(candles, calculateAtr(candles, 14), EVENT_CONFIG.channel);
    expect(event).not.toBeNull();
    expect(event!.kind).toBe('REGRESSION_CHANNEL');
    expect(event!.direction).toBe('bullish');
    expect(Number(event!.metrics.r2)).toBeGreaterThan(0.99);
    expect(event!.draw.lines).toHaveLength(2);
  });

  it('rejects a flat noisy series', () => {
    const closes = Array.from({ length: 120 }, (_, i) => (i % 2 ? 101 : 100));
    const candles = makeCandles(closes, 1.2);
    expect(detectChannel(candles, calculateAtr(candles, 14), EVENT_CONFIG.channel)).toBeNull();
  });
});

describe('pullback / breakout detector', () => {
  it('emits a bullish breakout when the last close clears the last pivot high', () => {
    const closes = Array.from({ length: 70 }, (_, i) => {
      if (i <= 50) return 100 + i * 0.4;
      if (i <= 60) return 120 - (i - 50) * 0.8;
      return 112 + (i - 60) * 0.4;
    });
    closes[69] = 126;
    const candles = makeCandles(closes, 1.2);
    candles[69] = { ...candles[69], open: 118, high: 127, low: 117, close: 126 };
    candles[68] = { ...candles[68], close: 118, open: 117.5, high: 119, low: 117 };
    const events = detectPullbackBreakout(candles, calculateAtr(candles, 14), EVENT_CONFIG.pullback);
    expect(events.some((event) => event.kind === 'BREAKOUT_UP')).toBe(true);
    expect(events.find((event) => event.kind === 'BREAKOUT_UP')!.family).toBe('breakout');
  });
});

describe('p19/p21 integration', () => {
  /**
   * کانال افقی موازی (سقف‌ها ۱۰۰، کف‌ها ۹۰) + شکست بالا در ۲۰۰ و ریتست در ۲۰۶.
   * هر دو خانواده باید در یک اسکن پیدا شوند.
   */
  function horizontalChannelWithRetest(): EngineCandle[] {
    const anchors = [
      { index: 0, price: 94 }, { index: 30, price: 100 }, { index: 50, price: 90 },
      { index: 70, price: 100 }, { index: 90, price: 90 }, { index: 110, price: 100 },
      { index: 130, price: 90 }, { index: 150, price: 100 }, { index: 170, price: 90 },
      { index: 190, price: 100 }, { index: 199, price: 100 }, { index: 200, price: 103 },
      { index: 202, price: 104 }, { index: 205, price: 104 }, { index: 206, price: 99.8 },
      { index: 207, price: 100.1 }, { index: 210, price: 104 }, { index: 239, price: 104 },
    ];
    const bars: EngineCandle[] = [];
    for (let i = 0; i < 240; i++) {
      let price = anchors[anchors.length - 1].price;
      for (let a = 0; a < anchors.length - 1; a++) {
        const from = anchors[a];
        const to = anchors[a + 1];
        if (i >= from.index && i <= to.index) {
          const t = to.index === from.index ? 0 : (i - from.index) / (to.index - from.index);
          price = from.price + (to.price - from.price) * t;
          break;
        }
      }
      bars.push({
        timestamp: 1_700_000_000_000 + i * 86_400_000,
        open: price - 0.05,
        high: price + 0.3,
        low: price - 0.3,
        close: price,
        volume: 1_000_000 + i,
      });
    }
    return bars;
  }

  it('produces a pivot-channel primary and a p21 retest primary', () => {
    const candles = horizontalChannelWithRetest();
    const result = scanChart(candles);
    expect(result.primary.channel).toBeTruthy();
    const channel = result.events.find((event) => event.id === result.primary.channel)!;
    expect(channel.family).toBe('channel');
    expect(['PIVOT_CHANNEL', 'CHANNEL_STRUCTURE']).toContain(channel.kind);
    expect(channel.draw.lines?.length).toBe(2);
    expect(Number(channel.metrics.quality ?? channel.quality)).toBeGreaterThan(0);

    expect(result.primary.breakout).toBeTruthy();
    const retest = result.events.find(
      (event) => event.kind === 'SR_RETEST' && event.status === 'confirmed',
    )!;
    expect(retest).toBeTruthy();
    expect(retest.kind).toBe('SR_RETEST');
    expect(retest.family).toBe('breakout');
    expect(retest.metrics.retestIndex).toBe(206);
  });

  it('keeps W/M pattern events from the DoubleTap engine only', () => {
    const closes = [95, 96, 97, 97.5, 98, 99.5, 97, 94, 90.5, 93, 96, 99.5, 89.5];
    const highs = [95.5, 96.5, 97.5, 98, 98.5, 100, 97.5, 94.5, 91.5, 93.5, 96.5, 100.4, 90.5];
    const lows = [94.5, 95.5, 80, 96.5, 97, 98.5, 96.5, 93, 90, 92.5, 95.5, 98.5, 88.5];
    const bars: EngineCandle[] = closes.map((close, i) => ({
      timestamp: 1_700_000_000_000 + i * 86_400_000,
      open: close, high: highs[i], low: lows[i], close, volume: 1_000,
    }));
    for (let i = 13; i < 60; i++) {
      bars.push({ timestamp: 1_700_000_000_000 + i * 86_400_000, open: 88, high: 88.2, low: 87.8, close: 88, volume: 1_000 });
    }
    const result = scanChart(bars);
    const doubleEvents = result.events.filter(
      (event) => event.kind === 'DOUBLE_TOP' || event.kind === 'DOUBLE_BOTTOM',
    );
    expect(doubleEvents.length).toBeGreaterThan(0);
    for (const event of doubleEvents) {
      expect(event.pattern!.id.startsWith('DT:')).toBe(true);
      expect(event.evidence.source).toBe('existing-engine');
    }
  });
});

describe('scanChart', () => {
  it('returns a functional-basis result with primaries and deterministic ids', () => {
    const closes = Array.from({ length: 160 }, (_, i) => 100 + i * 0.4);
    const candles = makeCandles(closes, 0.8);
    const a = scanChart(candles, { symbol: 'TEST', timeframe: '1D', adjustmentMode: 3 });
    const b = scanChart(candles, { symbol: 'TEST', timeframe: '1D', adjustmentMode: 3 });
    expect(a.seriesBasis).toBe('functional');
    expect(a.adjustmentMode).toBe(3);
    expect(a.bars).toBe(160);
    expect(a.primary.channel).toBeTruthy();
    expect(a.events.map((event) => event.id)).toEqual(b.events.map((event) => event.id));
  });

  it('stays inside the scan budget on 500 bars', () => {
    const closes = Array.from({ length: 500 }, (_, i) => 100 + Math.sin(i / 11) * 6 + i * 0.08);
    const candles = makeCandles(closes, 1);
    scanChart(candles);
    const started = performance.now();
    const result = scanChart(candles);
    const elapsed = performance.now() - started;
    expect(result.bars).toBe(500);
    expect(elapsed).toBeLessThan(50);
  });
});
