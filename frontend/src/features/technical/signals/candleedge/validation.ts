import type { Candle, CandleTime } from './types';

export class CandleEdgeInputError extends Error {
  constructor(
    readonly index: number,
    readonly reason: string,
  ) {
    super(`candle[${index}]: ${reason}`);
    this.name = 'CandleEdgeInputError';
  }
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isTime(value: unknown): value is CandleTime {
  return (
    (typeof value === 'number' && Number.isFinite(value)) ||
    (typeof value === 'string' && value.length > 0)
  );
}

function compareTime(previous: CandleTime, current: CandleTime): number {
  if (typeof previous === 'number' && typeof current === 'number') {
    return current > previous ? 1 : current < previous ? -1 : 0;
  }
  if (typeof previous === 'string' && typeof current === 'string') {
    return current > previous ? 1 : current < previous ? -1 : 0;
  }
  return Number.NaN;
}

export function assertValidCandles(candles: readonly Candle[]): void {
  if (!Array.isArray(candles)) {
    throw new CandleEdgeInputError(-1, 'candles-not-array');
  }

  let previousTime: CandleTime | null = null;
  candles.forEach((candle, index) => {
    if (!candle || typeof candle !== 'object') {
      throw new CandleEdgeInputError(index, 'candle-not-object');
    }
    if (!isTime(candle.time)) {
      throw new CandleEdgeInputError(index, 'time-invalid');
    }

    for (const field of ['open', 'high', 'low', 'close'] as const) {
      const value = candle[field];
      if (!isFiniteNumber(value)) {
        throw new CandleEdgeInputError(index, 'ohlc-not-finite');
      }
      if (value <= 0) {
        throw new CandleEdgeInputError(index, 'price-not-positive');
      }
    }

    if (candle.high < Math.max(candle.open, candle.close)) {
      throw new CandleEdgeInputError(index, 'high-below-body');
    }
    if (candle.low > Math.min(candle.open, candle.close)) {
      throw new CandleEdgeInputError(index, 'low-above-body');
    }

    if (previousTime !== null) {
      const order = compareTime(previousTime, candle.time);
      if (Number.isNaN(order)) {
        throw new CandleEdgeInputError(index, 'time-type-mixed');
      }
      if (order <= 0) {
        throw new CandleEdgeInputError(index, 'time-not-increasing');
      }
    }
    previousTime = candle.time;
  });
}
