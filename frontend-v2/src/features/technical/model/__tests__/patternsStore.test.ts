import { beforeEach, describe, expect, it } from 'vitest';
import { useTechnicalStore } from '../technicalStore';
import type { ChartPattern } from '../patterns/types';
import type { EngineCandle } from '../doubleTapEngine';

const pattern: ChartPattern = {
  id: 'FLAG_BULL:4:1-2-3-4', kind: 'FLAG_BULL', direction: 'bullish', family: 'continuation',
  anchor: { index: 4, price: 105, timestamp: 4000 }, points: [],
  upper: { from: { index: 4, price: 106, timestamp: 4000 }, to: { index: 4, price: 106, timestamp: 4000 } },
  lower: { from: { index: 4, price: 104, timestamp: 4000 }, to: { index: 4, price: 104, timestamp: 4000 } },
  target: 112, stopLoss: 98, quality: 60, status: 'forming',
};

const candle: EngineCandle = {
  timestamp: 4000, open: 100, high: 106, low: 98, close: 105, volume: 1200,
};

describe('patterns store slice', () => {
  beforeEach(() => useTechnicalStore.getState().reset());

  it('defaults detected patterns and chart candles to empty arrays', () => {
    const state = useTechnicalStore.getState();
    expect(state.detectedPatterns).toEqual([]);
    expect(state.chartCandles).toEqual([]);
  });

  it('stores detected patterns', () => {
    useTechnicalStore.getState().setDetectedPatterns([pattern]);
    expect(useTechnicalStore.getState().detectedPatterns).toHaveLength(1);
  });

  it('publishes chart candles for the pattern engine', () => {
    useTechnicalStore.getState().setChartCandles([candle]);
    expect(useTechnicalStore.getState().chartCandles).toEqual([candle]);
  });
});
