import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import { fileURLToPath } from 'node:url';
import zlib from 'node:zlib';
import { buildSalience } from '@features/technical/signals/candleedge/research/salience';
import type { SalienceInputEvent } from '@features/technical/signals/candleedge/research/types';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const EVIDENCE = path.join(HERE, 'evidence');
const LEDGER = process.env.CANDLEEDGE_LEDGER
  ?? path.join(EVIDENCE, 'ledger.ndjson.gz');
const SERIES = process.env.CANDLEEDGE_SERIES
  ?? path.join(EVIDENCE, 'series.ndjson.gz');
const OUT = process.env.CANDLEEDGE_SALIENCE_OUT
  ?? path.join(EVIDENCE, 'salience-groups.ndjson.gz');

const FAMILY: Record<string, string> = {
  doji: 'candlestick',
  bullish_engulfing: 'candlestick',
  bearish_engulfing: 'candlestick',
  hammer: 'candlestick',
  shooting_star: 'candlestick',
  double_top: 'chart_structure',
  double_bottom: 'chart_structure',
  ascending_triangle: 'chart_structure',
  descending_triangle: 'chart_structure',
  symmetrical_triangle: 'chart_structure',
  rising_wedge: 'chart_structure',
  falling_wedge: 'chart_structure',
  higher_high: 'market_structure',
  higher_low: 'market_structure',
  lower_high: 'market_structure',
  lower_low: 'market_structure',
  bos_bullish: 'market_structure',
  bos_bearish: 'market_structure',
  liquidity_sweep_high: 'market_structure',
  liquidity_sweep_low: 'market_structure',
};

function stream(file: string): NodeJS.ReadableStream {
  const raw = fs.createReadStream(file);
  return file.endsWith('.gz') ? raw.pipe(zlib.createGunzip()) : raw;
}

async function loadSeriesLengths(): Promise<Map<string, number>> {
  const lengths = new Map<string, number>();
  const rl = readline.createInterface({ input: stream(SERIES), crlfDelay: Infinity });
  for await (const line of rl) {
    if (!line.trim()) continue;
    const row = JSON.parse(line) as { symbol: string; timeframe: string; candleCount: number };
    lengths.set(`${row.symbol}|${row.timeframe}`, row.candleCount);
  }
  return lengths;
}

interface CompactEvent {
  s: string;
  tf: string;
  m: string;
  d: string;
  b: 'bullish' | 'bearish' | 'neutral';
  i: number;
  l: number | null;
  a: [number, string, number, number][];
}

async function main() {
  const lengths = await loadSeriesLengths();
  const bySeries = new Map<string, SalienceInputEvent[]>();
  const rl = readline.createInterface({ input: stream(LEDGER), crlfDelay: Infinity });
  for await (const line of rl) {
    if (!line.trim()) continue;
    const e = JSON.parse(line) as CompactEvent;
    if (e.m !== 'adj') continue;
    const seriesKey = `${e.s}|${e.tf}`;
    const event: SalienceInputEvent = {
      key: `${e.d}@${e.i}`,
      detector: e.d,
      family: FAMILY[e.d] ?? 'unknown',
      bias: e.b,
      confirmedAtIndex: e.i,
      anchors: e.a.map(([index, role, price]) => ({
        index,
        price,
        role,
      })),
      ...(typeof e.l === 'number' ? { level: e.l } : {}),
    };
    const bucket = bySeries.get(seriesKey);
    if (bucket) bucket.push(event);
    else bySeries.set(seriesKey, [event]);
  }

  const out = fs.createWriteStream(OUT);
  const gz = zlib.createGzip({ level: 9 });
  gz.pipe(out);
  let groups = 0;
  let multi = 0;
  let repeated = 0;
  let maxSize = 0;
  const seriesWithGroups = new Set<string>();
  const ordered = [...bySeries.keys()].sort((a, b) => a.localeCompare(b));
  for (const seriesKey of ordered) {
    const events = bySeries.get(seriesKey) ?? [];
    const [symbol, timeframe] = seriesKey.split('|');
    const latestIndex = Math.max(0, (lengths.get(seriesKey) ?? 1) - 1);
    const result = buildSalience(seriesKey, events, latestIndex);
    if (result.groups.length > 0) seriesWithGroups.add(seriesKey);
    const rank = (method: keyof typeof result.order) => {
      const map = new Map<string, number>();
      result.order[method].forEach((id, index) => map.set(id, index + 1));
      return map;
    };
    const latestRank = rank('latest');
    const structureRank = rank('structure_first');
    const evidenceRank = rank('evidence_count');
    for (const group of result.groups) {
      groups += 1;
      if (group.eventKeys.length > 1) multi += 1;
      if (group.repeatedDetectorAnchorSets) repeated += 1;
      maxSize = Math.max(maxSize, group.eventKeys.length);
      const row = {
        symbol,
        timeframe,
        ...group,
        ranks: {
          latest: latestRank.get(group.id),
          structure_first: structureRank.get(group.id),
          evidence_count: evidenceRank.get(group.id),
        },
      };
      gz.write(`${JSON.stringify(row)}\n`);
    }
  }
  gz.end();
  await new Promise<void>((resolve, reject) => {
    out.on('finish', resolve);
    out.on('error', reject);
  });
  const summary = {
    series: bySeries.size,
    seriesWithGroups: seriesWithGroups.size,
    groups,
    multiEventGroups: multi,
    repeatedGroups: repeated,
    maxGroupSize: maxSize,
    out: OUT,
  };
  console.log(JSON.stringify(summary, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
