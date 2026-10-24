// Ported from CandleEdge (https://github.com/michaelsboost/CandleEdge),
// commit 75761e26b23ccaf59b31365e1ec817374673d77b, src/script.js:171-257.
// Copyright (c) 2026 Michael Schwartz. MIT License (see LICENSE-CANDLEEDGE).
// Modified for BorsTerminal: TypeScript types, trendPeriod parameter, bounds guards.
import type { Candle } from './types';
import { candleParts, isDowntrend, isUptrend } from './candleMath';

export function isDoji(candle: Candle): boolean {
  const { body, range } = candleParts(candle);
  return body <= range * 0.12;
}

export function isBullishEngulfing(candles: readonly Candle[], i: number): boolean {
  if (i < 1 || i >= candles.length) return false;
  const previous = candles[i - 1];
  const current = candles[i];
  return (
    previous.close < previous.open &&
    current.close > current.open &&
    current.open <= previous.close &&
    current.close >= previous.open
  );
}

export function isBearishEngulfing(candles: readonly Candle[], i: number): boolean {
  if (i < 1 || i >= candles.length) return false;
  const previous = candles[i - 1];
  const current = candles[i];
  return (
    previous.close > previous.open &&
    current.close < current.open &&
    current.open >= previous.close &&
    current.close <= previous.open
  );
}

export function isHammer(
  candles: readonly Candle[],
  idx: number,
  trendPeriod = 20,
): boolean {
  if (idx < trendPeriod || idx >= candles.length) return false;
  const candle = candles[idx];
  const { body, upper, lower } = candleParts(candle);
  const shape =
    body > 0 && lower > body * 2 && upper < body * 0.5 && candle.close > candle.open;
  return shape && isDowntrend(candles, idx, trendPeriod);
}

export function isShootingStar(
  candles: readonly Candle[],
  idx: number,
  trendPeriod = 20,
): boolean {
  if (idx < trendPeriod || idx >= candles.length) return false;
  const candle = candles[idx];
  const { body, upper, lower } = candleParts(candle);
  const shape =
    body > 0 && upper > body * 2 && lower < body * 0.5 && candle.close < candle.open;
  return shape && isUptrend(candles, idx, trendPeriod);
}
