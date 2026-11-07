/**
 * frontend-v2/scripts/build-doubletap-cohort.ts
 *
 * ساخت کوهورت بازار برای احتمال تشکیل الگوی دوقلو از snapshot مرجع RA365.
 * ورودی: JSONL با رکوردهای {asset_id, res, bars[]} — res = D|W
 * خروجی: src/features/technical/data/doubletap-cohort.json
 *
 * اجرا: npx vite-node scripts/build-doubletap-cohort.ts -- --input <path> --out <path>
 */

import fs from 'node:fs';
import readline from 'node:readline';
import path from 'node:path';
import {
  DEFAULT_PRECISION_PARAMS,
  calculateAtr,
  detectDoubleTapPatterns,
  patternOutcome,
} from '../src/features/technical/model/doubleTapEngine';

type Counts = {
  successes: number;
  failures: number;
  resolved: number;
  patterns: number;
  assets?: number;
};

type Band = { min: number; max: number } & Counts;

const args = process.argv.slice(2);
const argValue = (name: string, fallback: string): string => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};

const input = argValue('--input', 'D:/BorsTerminal-tmp/ra365_round32b_v3/reference/ref_bars_v2.jsonl');
const out = argValue(
  '--out',
  path.resolve('src/features/technical/data/doubletap-cohort.json')
);
const horizon = 10;

const market: Record<'1D' | '1W', Counts> = {
  '1D': { successes: 0, failures: 0, resolved: 0, patterns: 0, assets: 0 },
  '1W': { successes: 0, failures: 0, resolved: 0, patterns: 0, assets: 0 },
};
const bands: Record<'1D' | '1W', Band[]> = {
  '1D': [
    { min: 0, max: 59, successes: 0, failures: 0, resolved: 0, patterns: 0 },
    { min: 60, max: 79, successes: 0, failures: 0, resolved: 0, patterns: 0 },
    { min: 80, max: 100, successes: 0, failures: 0, resolved: 0, patterns: 0 },
  ],
  '1W': [
    { min: 0, max: 59, successes: 0, failures: 0, resolved: 0, patterns: 0 },
    { min: 60, max: 79, successes: 0, failures: 0, resolved: 0, patterns: 0 },
    { min: 80, max: 100, successes: 0, failures: 0, resolved: 0, patterns: 0 },
  ],
};
const assets: Record<'1D' | '1W', Set<string>> = { '1D': new Set(), '1W': new Set() };
const bandOf = (q: number): number => (q >= 80 ? 2 : q >= 60 ? 1 : 0);

let records = 0;
let used = 0;
let skipped = 0;

const rl = readline.createInterface({
  input: fs.createReadStream(input, { encoding: 'utf-8' }),
  crlfDelay: Infinity,
});

for await (const line of rl) {
  if (!line.trim()) continue;
  records += 1;
  let rec: { asset_id?: string; res?: string; status?: number; bars?: Array<Record<string, number>> };
  try {
    rec = JSON.parse(line);
  } catch {
    skipped += 1;
    continue;
  }
  if (rec.status !== 200 || !rec.bars || (rec.res !== 'D' && rec.res !== 'W')) {
    skipped += 1;
    continue;
  }
  const key: '1D' | '1W' = rec.res === 'D' ? '1D' : '1W';
  const candles = rec.bars
    .map((b) => ({
      timestamp: b.time ?? 0,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
      volume: b.volume ?? 0,
    }))
    .sort((a, b) => a.timestamp - b.timestamp);
  if (candles.length < 30) {
    skipped += 1;
    continue;
  }

  const patterns = detectDoubleTapPatterns(candles, DEFAULT_PRECISION_PARAMS);
  const atr = calculateAtr(candles, DEFAULT_PRECISION_PARAMS.atrPeriod);
  market[key].patterns += patterns.length;
  if (rec.asset_id) assets[key].add(rec.asset_id);

  for (const p of patterns) {
    if (p.peak2.index + 1 >= candles.length) continue;
    const a = atr[p.peak2.index] || atr[atr.length - 1] || 1;
    const outcome = patternOutcome(p, candles, a, horizon);
    if (outcome === 'unresolved') continue;
    const bucket = bands[key][bandOf(p.quality)];
    bucket.patterns += 1;
    if (outcome === 'success') {
      bucket.successes += 1;
      market[key].successes += 1;
    } else {
      bucket.failures += 1;
      market[key].failures += 1;
    }
    bucket.resolved += 1;
    market[key].resolved += 1;
  }

  used += 1;
  if (used % 500 === 0) {
    process.stderr.write(`[cohort] used=${used} records=${records} D=${market['1D'].resolved} W=${market['1W'].resolved}\n`);
  }
}

for (const key of ['1D', '1W'] as const) {
  market[key].assets = assets[key].size;
}

const payload = {
  generatedAt: new Date().toISOString(),
  source: path.basename(input),
  horizon,
  params: DEFAULT_PRECISION_PARAMS,
  records,
  used,
  skipped,
  market,
  qualityBands: bands,
};

fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, JSON.stringify(payload, null, 2), 'utf-8');
process.stdout.write(`saved ${out}\n`);
process.stdout.write(JSON.stringify(payload.market, null, 2) + '\n');
