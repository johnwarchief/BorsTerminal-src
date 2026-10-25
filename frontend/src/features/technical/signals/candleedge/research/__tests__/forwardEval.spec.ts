import { describe, expect, it } from 'vitest';
import { FORWARD_HORIZONS, clusterBootstrapMeanCI, evaluateForward } from '../forwardEval';
import type { ForwardBar, ForwardEvent } from '../types';

const DAY = 86_400_000;
const START = Date.UTC(2026, 0, 1);
const CUTOFF = Date.UTC(2026, 0, 5);

function bars(): ForwardBar[] {
  return Array.from({ length: 10 }, (_, i) => ({
    time: START + i * DAY,
    open: 100,
    close: 100 + i * 10,
  }));
}

function ev(overrides: Partial<ForwardEvent> = {}): ForwardEvent {
  return {
    key: 'bos_bullish@2',
    detector: 'bos_bullish',
    bias: 'bullish',
    confirmedAtIndex: 2,
    confirmedAt: START + 2 * DAY,
    ...overrides,
  };
}

function run(events: ForwardEvent[], market?: (entryTime: number, horizon: number) => number | undefined) {
  return evaluateForward({
    seriesKey: 'X|D',
    bars: bars(),
    events,
    cutoffMs: CUTOFF,
    marketBaseline: market,
  });
}

describe('forward evaluation timing', () => {
  it('uses the next bar open as entry and the H-th bar close as exit', () => {
    const result = run([ev()]);
    const row = result.rows.find((r) => r.detector === 'bos_bullish' && r.horizon === 3)!;
    // entry index 3 open 100, exit index 5 close 150
    expect(row.n).toBe(1);
    expect(row.mean).toBeCloseTo(0.5, 12);
    expect(row.entryRule).toBe('next-bar-open');
  });

  it('does not let a change on the confirmation bar alter the entry or return', () => {
    const changed = bars();
    changed[2] = { ...changed[2], close: 9999 };
    const base = evaluateForward({
      seriesKey: 'X|D', bars: bars(), events: [ev()], cutoffMs: CUTOFF,
    });
    const altered = evaluateForward({
      seriesKey: 'X|D', bars: changed, events: [ev()], cutoffMs: CUTOFF,
    });
    const outcomes = (rows: typeof base.rows) =>
      rows.map((r) => ({
        detector: r.detector, horizon: r.horizon, period: r.period,
        n: r.n, mean: r.mean, median: r.median, rightCensored: r.rightCensored,
      }));
    // The local baseline legitimately sees the whole series; the event outcome
    // must not depend on the confirmation bar's close.
    expect(outcomes(altered.rows)).toEqual(outcomes(base.rows));
    expect(altered.rows[0].baselineLocalMean).not.toBe(base.rows[0].baselineLocalMean);
  });

  it('counts events without a full future window as right-censored', () => {
    const result = run([ev({ confirmedAtIndex: 8, confirmedAt: START + 8 * DAY })]);
    const row = result.rows.find((r) => r.horizon === 3)!;
    expect(row.n).toBe(0);
    expect(row.rightCensored).toBe(1);
    expect(row.mean).toBeNull();
  });

  it('uses the fixed horizons and splits discovery from evaluation by confirmation date', () => {
    expect(FORWARD_HORIZONS).toEqual([3, 5, 10, 20]);
    const result = run([
      ev(),
      ev({ key: 'bos_bullish@6', confirmedAtIndex: 6, confirmedAt: START + 6 * DAY }),
    ]);
    const discovery = result.rows.find((r) => r.horizon === 3 && r.period === 'discovery')!;
    const evaluation = result.rows.find((r) => r.horizon === 3 && r.period === 'evaluation')!;
    expect(discovery.n).toBe(1);
    expect(evaluation.n).toBe(1);
  });
});

describe('forward evaluation direction and baselines', () => {
  it('flips the sign for bearish events and uses a directional local baseline', () => {
    const result = run([ev({ key: 'bos_bearish@2', detector: 'bos_bearish', bias: 'bearish' })]);
    const row = result.rows.find((r) => r.detector === 'bos_bearish' && r.horizon === 3)!;
    expect(row.mean).toBeCloseTo(-0.5, 12);
    // Discovery-period directional baseline: t=0..3 -> +0.2..+0.5, mean 0.35.
    expect(row.baselineLocalMean).toBeCloseTo(-0.35, 12);
    expect(row.deltaLocal).toBeCloseTo(-0.15, 12);
  });

  it('uses the supplied market baseline for the same entry bar and horizon', () => {
    const result = run([ev()], (entryTime, horizon) =>
      entryTime === START + 3 * DAY && horizon === 3 ? 0.01 : undefined,
    );
    const row = result.rows.find((r) => r.horizon === 3)!;
    expect(row.baselineMarketMean).toBeCloseTo(0.01, 12);
    expect(row.deltaMarket).toBeCloseTo(0.49, 12);
    expect(row.marketBaselineN).toBe(1);
  });

  it('reports win rate, quantiles, uncertainty and a low-sample flag', () => {
    const result = run([ev()]);
    const row = result.rows.find((r) => r.horizon === 3)!;
    expect(row.winRate).toBe(1);
    expect(row.winRateCI![0]).toBeGreaterThanOrEqual(0);
    expect(row.winRateCI![1]).toBeLessThanOrEqual(1);
    expect(row.q50).toBeCloseTo(0.5, 12);
    expect(row.lowSample).toBe(true);
    expect(row.meanCI![0]).toBeCloseTo(0.5, 12);
    expect(row.meanCI![1]).toBeCloseTo(0.5, 12);
  });

  it('returns no rows for no events but keeps the fixed horizon metadata', () => {
    const result = run([]);
    expect(result.rows).toEqual([]);
    expect(result.horizons).toEqual([3, 5, 10, 20]);
    expect(result.cutoffMs).toBe(CUTOFF);
  });

  it('bootstraps uncertainty by symbol, not by overlapping event', () => {
    expect(clusterBootstrapMeanCI([], 'x')).toBeNull();
    expect(clusterBootstrapMeanCI([[0.5]], 'x')).toEqual([0.5, 0.5]);
    const ci = clusterBootstrapMeanCI([[1, 1], [2, 2], [3, 3]], 'seed')!;
    expect(ci[0]).toBeLessThanOrEqual(2);
    expect(ci[1]).toBeGreaterThanOrEqual(2);
    expect(clusterBootstrapMeanCI([[1], [2], [3]], 'seed')).toEqual(
      clusterBootstrapMeanCI([[1], [2], [3]], 'seed'),
    );
  });
});
