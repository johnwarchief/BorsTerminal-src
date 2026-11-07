/**
 * Phase D audit export: 15 symbols x daily/weekly, adjusted DB series.
 * Run with: npx vite-node scripts/pattern_audit_export.ts
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { toKlineBars } from '@features/chart/api/useChart';
import { aggregateCandles } from '@features/technical/model/timeframeAggregation';
import { detectAllPatterns } from '@features/technical/model/patterns/registry';
import type { EngineCandle } from '@features/technical/model/doubleTapEngine';

const BASE = process.env.BORS_BACKEND || 'http://127.0.0.1:8198';
const SYMBOLS = [
  'فولاد', 'وبملت', 'شپنا', 'فارس', 'خودرو', 'شستا', 'فملي', 'وپاسار',
  'وغدير', 'نوري', 'پارسان', 'شتران', 'تاپيكو', 'شبندر', 'اخابر',
];
const OUT = resolve('D:/BorsTerminal-data/phase-d/pattern-audit.json');

async function main(): Promise<void> {
  const result: unknown[] = [];
  for (const symbol of SYMBOLS) {
    const url = `${BASE}/api/chart-db/${encodeURIComponent(symbol)}?adjustment=3`;
    const response = await fetch(url);
    const payload = await response.json();
    if (payload?.status !== 'success' || !Array.isArray(payload.candles)) {
      result.push({ symbol, error: payload?.status ?? 'bad-response' });
      console.log(symbol, 'ERROR', payload?.status);
      continue;
    }
    const bars = toKlineBars(payload.candles, payload.factors, 3);
    for (const timeframe of ['1D', '1W'] as const) {
      const aggregated = aggregateCandles(bars, timeframe);
      const candles: EngineCandle[] = aggregated.map((bar) => ({
        timestamp: bar.timestamp,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
        volume: bar.volume ?? 0,
      }));
      const patterns = detectAllPatterns(candles);
      result.push({ symbol, timeframe, candles, patterns });
      console.log(symbol, timeframe, 'bars', candles.length, 'patterns', patterns.length);
    }
  }
  mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, JSON.stringify(result), 'utf8');
  console.log('wrote', OUT);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
