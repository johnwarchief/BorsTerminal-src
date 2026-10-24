// Ported from CandleEdge (https://github.com/michaelsboost/CandleEdge),
// commit 75761e26b23ccaf59b31365e1ec817374673d77b, src/script.js:149-128.
// Copyright (c) 2026 Michael Schwartz. MIT License (see LICENSE-CANDLEEDGE).
// Modified for BorsTerminal: TypeScript types and bounds guards.
import type { Candle } from './types';

export interface CandleParts {
  body: number;
  range: number;
  upper: number;
  lower: number;
}

export function candleParts(candle: Candle): CandleParts {
  const body = Math.abs(candle.close - candle.open);
  const range = candle.high - candle.low || 1;
  const upper = candle.high - Math.max(candle.open, candle.close);
  const lower = Math.min(candle.open, candle.close) - candle.low;
  return { body, range, upper, lower };
}

export function isUptrend(candles: readonly Candle[], idx: number, period = 20): boolean {
  if (idx < period || idx >= candles.length) return false;
  return candles[idx].close > candles[idx - period].close;
}

export function isDowntrend(candles: readonly Candle[], idx: number, period = 20): boolean {
  if (idx < period || idx >= candles.length) return false;
  return candles[idx].close < candles[idx - period].close;
}
