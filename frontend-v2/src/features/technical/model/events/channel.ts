import type { EngineCandle } from '../doubleTapEngine';
import type { ChartEvent } from './types';
import type { EventConfig as EventConfigType } from './config';

export type ChannelConfig = EventConfigType['channel'];

/**
 * Regression channel on the last lookback bars.
 * A channel is emitted only when the fit is strong (R²) and both boundaries
 * were touched at least minTouches times; otherwise the event would be a
 * trend line wearing a channel label.
 */
export function detectChannel(
  candles: readonly EngineCandle[],
  atr: readonly number[],
  config: ChannelConfig,
  offset = 0,
): ChartEvent | null {
  const n = candles.length;
  const start = Math.max(0, n - config.lookbackBars);
  const m = n - start;
  if (m < config.minBars) return null;
  const atrLast = atr[n - 1] ?? 0;
  if (!(atrLast > 0)) return null;

  let sumX = 0;
  let sumY = 0;
  let sumXY = 0;
  let sumX2 = 0;
  for (let i = 0; i < m; i++) {
    const y = candles[start + i].close;
    sumX += i;
    sumY += y;
    sumXY += i * y;
    sumX2 += i * i;
  }
  const denom = m * sumX2 - sumX * sumX;
  if (Math.abs(denom) < 1e-12) return null;
  const slope = (m * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / m;

  const meanY = sumY / m;
  let sst = 0;
  let sse = 0;
  for (let i = 0; i < m; i++) {
    const y = candles[start + i].close;
    const fit = intercept + slope * i;
    sst += (y - meanY) ** 2;
    sse += (y - fit) ** 2;
  }
  if (sst <= 0) return null;
  const r2 = Math.max(0, Math.min(1, 1 - sse / sst));
  if (r2 < config.minR2) return null;

  const std = Math.sqrt(sse / m);
  const upper = (i: number) => intercept + slope * i + 2 * std;
  const lower = (i: number) => intercept + slope * i - 2 * std;
  const tol = atrLast * config.touchTolAtr;
  let touchUpper = 0;
  let touchLower = 0;
  for (let i = 0; i < m; i++) {
    const c = candles[start + i].close;
    if (c >= upper(i) - tol) touchUpper += 1;
    if (c <= lower(i) + tol) touchLower += 1;
  }
  if (touchUpper < config.minTouches || touchLower < config.minTouches) return null;

  const slopeAtr = slope / atrLast;
  const direction = slopeAtr > config.directionSlopeAtr
    ? 'bullish'
    : slopeAtr < -config.directionSlopeAtr ? 'bearish' : 'neutral';
  const first = candles[start];
  const last = candles[n - 1];
  const startPoint = { index: offset + start, price: intercept, timestamp: first.timestamp };
  const endPoint = { index: offset + n - 1, price: intercept + slope * (m - 1), timestamp: last.timestamp };
  const upperFrom = { ...startPoint, price: upper(0) };
  const upperTo = { ...endPoint, price: upper(m - 1) };
  const lowerFrom = { ...startPoint, price: lower(0) };
  const lowerTo = { ...endPoint, price: lower(m - 1) };

  return {
    id: `channel:REGRESSION_CHANNEL:${offset + n - 1}:${m}`,
    family: 'channel',
    kind: 'REGRESSION_CHANNEL',
    direction,
    status: 'confirmed',
    anchor: endPoint,
    interval: [offset + start, offset + n - 1],
    quality: Math.round(r2 * 100),
    metrics: {
      mode: 'regression',
      r2: Number(r2.toFixed(4)),
      slope: Number(slope.toFixed(4)),
      slopeAtr: Number(slopeAtr.toFixed(4)),
      widthAtr: Number(((4 * std) / atrLast).toFixed(3)),
      touchesUpper: touchUpper,
      touchesLower: touchLower,
      bars: m,
    },
    evidence: { ruleRef: 'CHANNEL_REGRESSION', source: 'classic' },
    draw: {
      lines: [
        { from: upperFrom, to: upperTo, style: 'solid' },
        { from: lowerFrom, to: lowerTo, style: 'solid' },
      ],
      labelAt: endPoint,
    },
  };
}
