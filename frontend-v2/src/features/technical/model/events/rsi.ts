import type { EngineCandle } from '../doubleTapEngine';
import { isPivotHigh, isPivotLow } from '../patterns/pivots';
import type { ChartEvent, DivergenceKind } from './types';
import type { EventConfig as EventConfigType } from './config';

export type RsiDivergenceConfig = EventConfigType['divergence'];

export function computeRsi(closes: readonly number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(closes.length).fill(null);
  if (period <= 0 || closes.length <= period) return out;
  let gain = 0;
  let loss = 0;
  for (let i = 1; i <= period; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff >= 0) gain += diff;
    else loss -= diff;
  }
  let avgGain = gain / period;
  let avgLoss = loss / period;
  const value = (g: number, l: number) => (l === 0 ? 100 : g === 0 ? 0 : 100 - 100 / (1 + g / l));
  out[period] = value(avgGain, avgLoss);
  for (let i = period + 1; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    const g = diff > 0 ? diff : 0;
    const l = diff < 0 ? -diff : 0;
    avgGain = (avgGain * (period - 1) + g) / period;
    avgLoss = (avgLoss * (period - 1) + l) / period;
    out[i] = value(avgGain, avgLoss);
  }
  return out;
}

/**
 * چهار نوع واگرایی، فقط روی پیوت تأییدشده:
 * - عادی صعودی: کف پایین‌تر، RSI بالاتر
 * - عادی نزولی: سقف بالاتر، RSI پایین‌تر
 * - مخفی صعودی (H+): کف بالاتر، RSI پایین‌تر
 * - مخفی نزولی (H-): سقف پایین‌تر، RSI بالاتر
 */
export function classifyDivergence(
  kind: 'high' | 'low',
  p1: number,
  p2: number,
  r1: number,
  r2: number,
  atr: number,
  config: RsiDivergenceConfig,
): DivergenceKind | null {
  const tol = atr * config.priceTolAtr;
  if (!(atr > 0) || !Number.isFinite(tol)) return null;
  const priceUp = p2 > p1 + tol;
  const priceDown = p2 < p1 - tol;
  const rsiUp = r2 > r1 + config.rsiTol;
  const rsiDown = r2 < r1 - config.rsiTol;
  if (kind === 'high') {
    if (priceUp && rsiDown) return 'RSI_REGULAR_BEARISH';
    if (priceDown && rsiUp) return 'RSI_HIDDEN_BEARISH';
  } else {
    if (priceDown && rsiUp) return 'RSI_REGULAR_BULLISH';
    if (priceUp && rsiDown) return 'RSI_HIDDEN_BULLISH';
  }
  return null;
}

function directionOf(kind: DivergenceKind): 'bullish' | 'bearish' {
  return kind.endsWith('BULLISH') ? 'bullish' : 'bearish';
}

export function detectRsiDivergences(
  candles: readonly EngineCandle[],
  atr: readonly number[],
  config: RsiDivergenceConfig,
  offset = 0,
): ChartEvent[] {
  const n = candles.length;
  if (n < config.rsiPeriod + config.pivLeft + config.pivRight + 5) return [];
  const rsi = computeRsi(candles.map((c) => c.close), config.rsiPeriod);
  const highs: { index: number; price: number }[] = [];
  const lows: { index: number; price: number }[] = [];
  for (let i = config.pivLeft; i < n - config.pivRight; i++) {
    if (isPivotHigh(candles, i, config.pivLeft, config.pivRight)) {
      highs.push({ index: i, price: candles[i].high });
    }
    if (isPivotLow(candles, i, config.pivLeft, config.pivRight)) {
      lows.push({ index: i, price: candles[i].low });
    }
  }
  const events: ChartEvent[] = [];
  const emit = (
    kind: DivergenceKind,
    pivotKind: 'high' | 'low',
    p1: { index: number; price: number },
    p2: { index: number; price: number },
    r1: number,
    r2: number,
  ) => {
    const atrValue = atr[p2.index] ?? 0;
    const priceDelta = p2.price - p1.price;
    const rsiDelta = r2 - r1;
    const priceStrength = Math.min(1, Math.abs(priceDelta) / Math.max(atrValue * 3, 1e-9));
    const rsiStrength = Math.min(1, Math.abs(rsiDelta) / Math.max(config.rsiTol * 3, 1e-9));
    const quality = Math.round(50 + 50 * (0.5 * priceStrength + 0.5 * rsiStrength));
    const a1 = { index: offset + p1.index, price: p1.price, timestamp: candles[p1.index].timestamp };
    const a2 = { index: offset + p2.index, price: p2.price, timestamp: candles[p2.index].timestamp };
    events.push({
      id: `divergence:${kind}:${a2.index}:${a1.index}`,
      family: 'divergence',
      kind,
      direction: directionOf(kind),
      status: 'confirmed',
      anchor: a2,
      interval: [a1.index, a2.index],
      quality,
      metrics: {
        pivot: pivotKind,
        price1: p1.price,
        price2: p2.price,
        rsi1: Number(r1.toFixed(2)),
        rsi2: Number(r2.toFixed(2)),
        priceDeltaAtr: Number((priceDelta / Math.max(atrValue, 1e-9)).toFixed(3)),
        rsiDelta: Number(rsiDelta.toFixed(2)),
      },
      evidence: { ruleRef: 'RSI_DIVERGENCE', source: 'rsi' },
      draw: { lines: [{ from: a1, to: a2, style: 'solid' }], labelAt: a2 },
    });
  };

  const pairs = (
    pivots: { index: number; price: number }[],
    pivotKind: 'high' | 'low',
  ) => {
    for (let i = 1; i < pivots.length; i++) {
      const p1 = pivots[i - 1];
      const p2 = pivots[i];
      const gap = p2.index - p1.index;
      if (gap < config.minPivotGap || gap > config.lookbackBars) continue;
      const r1 = rsi[p1.index];
      const r2 = rsi[p2.index];
      if (r1 == null || r2 == null) continue;
      const kind = classifyDivergence(pivotKind, p1.price, p2.price, r1, r2,
        atr[p2.index] ?? 0, config);
      if (kind) emit(kind, pivotKind, p1, p2, r1, r2);
    }
  };
  pairs(highs, 'high');
  pairs(lows, 'low');
  return events.sort((a, b) => a.anchor.index - b.anchor.index);
}
