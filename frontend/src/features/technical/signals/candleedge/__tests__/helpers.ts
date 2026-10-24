import { applyAdjustmentToCandles } from '@features/technical/nahayatnegar/lib/adjustments';
import type { Candle, SwingPoint } from '../types';

export const DAY = 86_400_000;
export const START = Date.UTC(2024, 0, 1);

export function candle(
  time: number,
  open: number,
  high: number,
  low: number,
  close: number,
  volume = 1_000,
): Candle {
  return { time, open, high, low, close, volume };
}

/** Candle with an exact body/range ratio, used for the boundary tests. */
export function bodyCandle(body: number, range: number, up = true, time = 0): Candle {
  const low = 1;
  const high = low + range;
  const open = up ? low + (range - body) / 2 : low + (range + body) / 2;
  const close = up ? open + body : open - body;
  return candle(time, open, high, low, close);
}

export function swing(index: number, price: number, confirmedAtIndex = index + 3): SwingPoint {
  return { index, price, time: START + index * DAY, confirmedAtIndex };
}

export interface PeaksFixture {
  raw: Candle[];
  adjusted: Candle[];
  factors: Array<{ time: string; factor: number }>;
}

function closeAt(i: number): number {
  if (i <= 25) return 150 + (198 - 150) * (i / 25);
  if (i <= 38) return 198 - (198 - 95) * ((i - 25) / 13);
  if (i === 39) return 96;
  if (i === 40) return 50;
  if (i <= 55) return 52 + (100 - 52) * ((i - 40) / 15);
  return 100 - 10 * ((i - 55) / 24);
}

/**
 * Two peaks that only become comparable after the pre-event half is adjusted:
 * raw peak 200 vs 102 (49% apart), adjusted peak 100 vs 102 (2% apart).
 * A trough between them (adjusted low 47) satisfies the 1% pullback check.
 */
export function buildRawTwoPeakSeries(): Candle[] {
  const out: Candle[] = [];
  for (let i = 0; i < 80; i += 1) {
    const close = closeAt(i);
    // The reopening bar trades at the new base price; inheriting the previous
    // raw close would manufacture a giant gap candle that is not a real peak.
    const open = i === 0 || i === 40 ? close : closeAt(i - 1);
    let high = Math.max(open, close) + 0.5;
    let low = Math.min(open, close) - 0.5;
    if (i === 25) high = 200;
    if (i === 38) low = 94;
    if (i === 55) high = 102;
    out.push(candle(START + i * DAY, open, high, low, close, 1_000 + i));
  }
  return out;
}

export function buildAdjustedTwoPeakSeries(): PeaksFixture {
  const raw = buildRawTwoPeakSeries();
  const factors = raw
    .filter((c) => (c.time as number) < START + 40 * DAY)
    .map((c) => ({ time: new Date(c.time as number).toISOString().slice(0, 10), factor: 0.5 }));
  const adjusted = applyAdjustmentToCandles(
    raw.map((c) => ({
      timestamp: c.time as number,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
      volume: c.volume,
    })),
    factors,
    'combined',
  ).map((c) => candle(c.timestamp, c.open, c.high, c.low, c.close, c.volume ?? 0));
  return { raw, adjusted, factors };
}

/** Deterministic random walk with repeating regimes, for stability and bench tests. */
export function randomWalk(
  n: number,
  seed = 42,
): Candle[] {
  let state = seed >>> 0;
  const next = () => {
    state = (state * 1_664_525 + 1_013_904_223) >>> 0;
    return state / 0x1_0000_0000;
  };
  const out: Candle[] = [];
  let price = 10_000;
  for (let i = 0; i < n; i += 1) {
    const drift = Math.sin(i / 37) * 0.0008;
    const change = (next() - 0.5) * 0.012 + drift;
    const open = price;
    const close = Math.max(1, open * (1 + change));
    const wick = 0.002 + next() * 0.004;
    const high = Math.max(open, close) * (1 + wick);
    const low = Math.min(open, close) * (1 - wick);
    out.push(candle(START + i * 3_600_000, open, high, low, close, 1_000 + Math.round(next() * 1_000)));
    price = close;
  }
  return out;
}
