import { describe, expect, it } from 'vitest';
import { scanPatterns } from '../index';
import { randomWalk } from './helpers';

describe('scan performance (informational, repeatable input)', () => {
  it('scans 20,000 deterministic candles three times with stable output', () => {
    const candles = randomWalk(20_000, 2026);
    const durations: number[] = [];
    const counts: number[] = [];
    const results: ReturnType<typeof scanPatterns>[] = [];

    for (let run = 0; run < 3; run += 1) {
      const start = performance.now();
      const result = scanPatterns(candles);
      durations.push(performance.now() - start);
      results.push(result);
      counts.push(result.events.length);
      expect(result.events.length).toBeGreaterThan(0);
    }

    expect(new Set(counts).size).toBe(1);
    expect(durations.every((value) => value < 20_000)).toBe(true);
    const lastResult = results[results.length - 1];
    const breakdown = lastResult.events.reduce<Record<string, number>>((acc, event) => {
      acc[event.detector] = (acc[event.detector] ?? 0) + 1;
      return acc;
    }, {});
    console.info(
      `[candleedge-bench] n=20000 runs_ms=${durations.map((d) => d.toFixed(1)).join('/')} events=${counts[0]} breakdown=${JSON.stringify(breakdown)}`,
    );
  }, 120_000);
});
