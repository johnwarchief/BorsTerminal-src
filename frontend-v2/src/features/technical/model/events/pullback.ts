import type { EngineCandle } from '../doubleTapEngine';
import { isPivotHigh, isPivotLow } from '../patterns/pivots';
import type { ChartEvent } from './types';
import type { EventConfig as EventConfigType } from './config';

export type PullbackConfig = EventConfigType['pullback'];

function ema(values: readonly number[], period: number): number[] {
  const out = new Array(values.length).fill(0);
  if (!values.length) return out;
  const k = 2 / (period + 1);
  out[0] = values[0];
  for (let i = 1; i < values.length; i++) out[i] = values[i] * k + out[i - 1] * (1 - k);
  return out;
}

function qualityOf(distanceAtr: number, volumeRatio: number, trendAtr: number): number {
  const d = Math.min(1, Math.max(0, distanceAtr / 1.5));
  const v = Math.min(1, Math.max(0, (volumeRatio - 0.8) / 1.2));
  const t = Math.min(1, Math.max(0, trendAtr / 2));
  return Math.round(50 + 50 * (0.4 * d + 0.3 * v + 0.3 * t));
}

/**
 * One breakout and one pullback at most, both on the last closed bar:
 * - breakout: close crosses the last confirmed pivot with an ATR buffer;
 * - pullback: in an EMA trend, the bar retests the fast EMA and closes back
 *   in the trend direction without breaking the last pivot.
 */
export function detectPullbackBreakout(
  candles: readonly EngineCandle[],
  atr: readonly number[],
  config: PullbackConfig,
  offset = 0,
): ChartEvent[] {
  const n = candles.length;
  if (n < config.emaSlow + 5) return [];
  const closes = candles.map((c) => c.close);
  const fast = ema(closes, config.emaFast);
  const slow = ema(closes, config.emaSlow);
  const last = n - 1;
  const prev = n - 2;
  const lastCandle = candles[last];
  const atrLast = atr[last] ?? 0;
  if (!(atrLast > 0)) return [];

  let lastHigh: { index: number; price: number } | null = null;
  let lastLow: { index: number; price: number } | null = null;
  const from = Math.max(config.pivLeft, n - config.lookbackBars);
  for (let i = n - 1 - config.pivRight; i >= from; i--) {
    if (!lastHigh && isPivotHigh(candles, i, config.pivLeft, config.pivRight)) {
      lastHigh = { index: i, price: candles[i].high };
    }
    if (!lastLow && isPivotLow(candles, i, config.pivLeft, config.pivRight)) {
      lastLow = { index: i, price: candles[i].low };
    }
    if (lastHigh && lastLow) break;
  }

  const avgVol = candles.slice(Math.max(0, last - 20), last)
    .reduce((s, c) => s + (c.volume || 0), 0) / Math.max(1, Math.min(20, last));
  const volumeRatio = avgVol > 0 ? (lastCandle.volume || 0) / avgVol : 1;
  const events: ChartEvent[] = [];
  let broke = false;

  const buffer = atrLast * config.breakoutBufferAtr;
  if (lastHigh && lastCandle.close > lastHigh.price + buffer
      && candles[prev].close <= lastHigh.price + buffer) {
    const distance = (lastCandle.close - lastHigh.price) / atrLast;
    const anchor = { index: offset + last, price: lastCandle.close, timestamp: lastCandle.timestamp };
    const levelFrom = { index: offset + lastHigh.index, price: lastHigh.price, timestamp: candles[lastHigh.index].timestamp };
    events.push({
      id: `breakout:BREAKOUT_UP:${offset + last}:${offset + lastHigh.index}`,
      family: 'breakout',
      kind: 'BREAKOUT_UP',
      direction: 'bullish',
      status: 'confirmed',
      anchor,
      interval: [offset + lastHigh.index, offset + last],
      quality: qualityOf(distance, volumeRatio, (fast[last] - slow[last]) / atrLast),
      metrics: {
        level: lastHigh.price,
        close: lastCandle.close,
        bufferAtr: config.breakoutBufferAtr,
        distanceAtr: Number(distance.toFixed(3)),
        volumeRatio: Number(volumeRatio.toFixed(2)),
      },
      evidence: { ruleRef: 'BREAKOUT_PIVOT', source: 'classic' },
      draw: {
        lines: [{ from: levelFrom, to: anchor, style: 'dashed' }],
        labelAt: anchor,
      },
    });
    broke = true;
  }
  if (lastLow && lastCandle.close < lastLow.price - buffer
      && candles[prev].close >= lastLow.price - buffer) {
    const distance = (lastLow.price - lastCandle.close) / atrLast;
    const anchor = { index: offset + last, price: lastCandle.close, timestamp: lastCandle.timestamp };
    const levelFrom = { index: offset + lastLow.index, price: lastLow.price, timestamp: candles[lastLow.index].timestamp };
    events.push({
      id: `breakout:BREAKOUT_DOWN:${offset + last}:${offset + lastLow.index}`,
      family: 'breakout',
      kind: 'BREAKOUT_DOWN',
      direction: 'bearish',
      status: 'confirmed',
      anchor,
      interval: [offset + lastLow.index, offset + last],
      quality: qualityOf(distance, volumeRatio, (slow[last] - fast[last]) / atrLast),
      metrics: {
        level: lastLow.price,
        close: lastCandle.close,
        bufferAtr: config.breakoutBufferAtr,
        distanceAtr: Number(distance.toFixed(3)),
        volumeRatio: Number(volumeRatio.toFixed(2)),
      },
      evidence: { ruleRef: 'BREAKDOWN_PIVOT', source: 'classic' },
      draw: {
        lines: [{ from: levelFrom, to: anchor, style: 'dashed' }],
        labelAt: anchor,
      },
    });
    broke = true;
  }

  if (!broke) {
    const trendUp = fast[last] > slow[last] && fast[last] > fast[Math.max(0, last - 5)];
    const trendDown = fast[last] < slow[last] && fast[last] < fast[Math.max(0, last - 5)];
    const tol = atrLast * config.retestTolAtr;
    const nearFast = Math.abs(lastCandle.low - fast[last]) <= tol
      || Math.abs(lastCandle.high - fast[last]) <= tol;
    const bullishBar = lastCandle.close > lastCandle.open;
    const bearishBar = lastCandle.close < lastCandle.open;
    if (trendUp && nearFast && bullishBar && lastCandle.close > fast[last]) {
      const anchor = { index: offset + last, price: lastCandle.close, timestamp: lastCandle.timestamp };
      const lineFrom = { index: offset + Math.max(0, last - 10), price: fast[last], timestamp: candles[Math.max(0, last - 10)].timestamp };
      const distance = Math.abs(lastCandle.low - fast[last]) / atrLast;
      const quality = qualityOf(distance, volumeRatio, (fast[last] - slow[last]) / atrLast);
      if (quality >= config.minQuality) {
        events.push({
          id: `pullback:PULLBACK_BULLISH:${offset + last}`,
          family: 'pullback',
          kind: 'PULLBACK_BULLISH',
          direction: 'bullish',
          status: 'confirmed',
          anchor,
          interval: [offset + Math.max(0, last - 10), offset + last],
          quality,
          metrics: { ema: Number(fast[last].toFixed(2)), low: lastCandle.low, close: lastCandle.close },
          evidence: { ruleRef: 'PULLBACK_EMA', source: 'classic' },
          draw: { lines: [{ from: lineFrom, to: anchor, style: 'dashed' }], labelAt: anchor },
        });
      }
    } else if (trendDown && nearFast && bearishBar && lastCandle.close < fast[last]) {
      const anchor = { index: offset + last, price: lastCandle.close, timestamp: lastCandle.timestamp };
      const lineFrom = { index: offset + Math.max(0, last - 10), price: fast[last], timestamp: candles[Math.max(0, last - 10)].timestamp };
      const distance = Math.abs(lastCandle.high - fast[last]) / atrLast;
      const quality = qualityOf(distance, volumeRatio, (slow[last] - fast[last]) / atrLast);
      if (quality >= config.minQuality) {
        events.push({
          id: `pullback:PULLBACK_BEARISH:${offset + last}`,
          family: 'pullback',
          kind: 'PULLBACK_BEARISH',
          direction: 'bearish',
          status: 'confirmed',
          anchor,
          interval: [offset + Math.max(0, last - 10), offset + last],
          quality,
          metrics: { ema: Number(fast[last].toFixed(2)), high: lastCandle.high, close: lastCandle.close },
          evidence: { ruleRef: 'PULLBACK_EMA', source: 'classic' },
          draw: { lines: [{ from: lineFrom, to: anchor, style: 'dashed' }], labelAt: anchor },
        });
      }
    }
  }
  return events;
}
