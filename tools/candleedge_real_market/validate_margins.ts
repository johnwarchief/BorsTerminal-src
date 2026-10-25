import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import { fileURLToPath } from 'node:url';
import zlib from 'node:zlib';
import { buildTimeframeBars } from '@features/technical/signals/candleedge/research/series';
import type { RealMarketRecord } from '@features/technical/signals/candleedge/research/realMarketTypes';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const NDJSON = process.env.CANDLEEDGE_NDJSON ?? '';
const LEDGER = process.env.CANDLEEDGE_LEDGER
  ?? path.join(HERE, 'evidence/ledger.ndjson.gz');
const OUT = process.env.CANDLEEDGE_MARGINS_OUT
  ?? path.join(HERE, 'evidence/margins.json');
if (!NDJSON) {
  throw new Error('CANDLEEDGE_NDJSON must point at the collector real_market.ndjson');
}
const records = new Map<string, RealMarketRecord>();

function stream(file: string): NodeJS.ReadableStream {
  const raw = fs.createReadStream(file);
  return file.endsWith('.gz') ? raw.pipe(zlib.createGunzip()) : raw;
}

async function loadRecords() {
  const rl = readline.createInterface({
    input: stream(NDJSON),
    crlfDelay: Infinity,
  });
  for await (const line of rl) {
    if (!line.trim()) continue;
    const record = JSON.parse(line) as RealMarketRecord;
    if (record.status === 'success') records.set(record.symbol, record);
  }
}

function quantiles(values: number[]) {
  const sorted = [...values].sort((a, b) => a - b);
  const q = (p: number) => sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))];
  return {
    n: sorted.length,
    min: sorted[0],
    p05: q(0.05),
    p25: q(0.25),
    p50: q(0.5),
    p75: q(0.75),
    p95: q(0.95),
    max: sorted[sorted.length - 1],
  };
}

const buckets = {
  bos: [] as number[],
  bosPriorGap: [] as number[],
  sweepPenetration: [] as number[],
  sweepCloseBack: [] as number[],
};
const counts: Record<string, {
  total: number; below005: number; below01: number; below025: number; below05: number;
}> = {};

function bump(detector: string, margin: number) {
  const c = (counts[detector] ??= {
    total: 0, below005: 0, below01: 0, below025: 0, below05: 0,
  });
  c.total += 1;
  if (margin < 0.0005) c.below005 += 1;
  if (margin < 0.001) c.below01 += 1;
  if (margin < 0.0025) c.below025 += 1;
  if (margin < 0.005) c.below05 += 1;
}

(async () => {
  await loadRecords();
  const rl = readline.createInterface({
    input: stream(LEDGER),
    crlfDelay: Infinity,
  });
  let processed = 0;
  let missing = 0;
  for await (const line of rl) {
    if (!line.trim()) continue;
    const e = JSON.parse(line);
    if (e.m !== 'adj') continue;
    const isBos = e.d === 'bos_bullish' || e.d === 'bos_bearish';
    const isSweep = e.d === 'liquidity_sweep_high' || e.d === 'liquidity_sweep_low';
    if (!isBos && !isSweep) continue;
    const record = records.get(e.s);
    if (!record) { missing += 1; continue; }
    const { adjustedBars } = buildTimeframeBars(record, e.tf);
    const bar = adjustedBars[e.i];
    const prev = adjustedBars[e.i - 1];
    if (!bar || !prev) { missing += 1; continue; }
    processed += 1;
    if (isBos) {
      const margin = e.d === 'bos_bullish'
        ? (bar.close - e.l) / e.l
        : (e.l - bar.close) / e.l;
      const priorGap = e.d === 'bos_bullish'
        ? (e.l - prev.close) / e.l
        : (prev.close - e.l) / e.l;
      buckets.bos.push(margin);
      buckets.bosPriorGap.push(priorGap);
      bump(e.d, margin);
    } else {
      const penetration = e.d === 'liquidity_sweep_high'
        ? (bar.high - e.l) / e.l
        : (e.l - bar.low) / e.l;
      const closeBack = e.d === 'liquidity_sweep_high'
        ? (e.l - bar.close) / e.l
        : (bar.close - e.l) / e.l;
      buckets.sweepPenetration.push(penetration);
      buckets.sweepCloseBack.push(closeBack);
      bump(e.d, penetration);
    }
  }
  const output = {
    processed,
    missing,
    counts,
    bosMargin: quantiles(buckets.bos),
    bosPriorGap: quantiles(buckets.bosPriorGap),
    sweepPenetration: quantiles(buckets.sweepPenetration),
    sweepCloseBack: quantiles(buckets.sweepCloseBack),
  };
  console.log(JSON.stringify(output, null, 2));
  fs.writeFileSync(OUT, JSON.stringify(output, null, 2));
})();
