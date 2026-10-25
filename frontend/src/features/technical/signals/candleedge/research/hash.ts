import { createHash } from 'node:crypto';
import type { RealMarketRecord } from './realMarketTypes';

/**
 * Mirrors tools/candleedge_real_market/collect_real_market.py:input_hash.
 * Fixed six decimals and integer volumes make the digest identical in Python
 * and JavaScript for the same collected payload.
 */
export function recomputeInputSha256(record: RealMarketRecord): string {
  const parts: string[] = [];
  for (const candle of record.rawCandles ?? []) {
    parts.push(
      `C|${String(candle.time).slice(0, 10)}|${Number(candle.open).toFixed(6)}|` +
        `${Number(candle.high).toFixed(6)}|${Number(candle.low).toFixed(6)}|` +
        `${Number(candle.close).toFixed(6)}|${Math.round(Number(candle.volume ?? 0))}`,
    );
  }
  parts.push('F');
  for (const factor of record.factors ?? []) {
    parts.push(
      `F|${String(factor.time).slice(0, 10)}|${Number(factor.factor).toFixed(6)}`,
    );
  }
  return createHash('sha256').update(parts.join('\n'), 'utf8').digest('hex');
}

export function verifyInputSha256(record: RealMarketRecord): boolean {
  if (!record.inputSha256) return false;
  return recomputeInputSha256(record) === record.inputSha256;
}
