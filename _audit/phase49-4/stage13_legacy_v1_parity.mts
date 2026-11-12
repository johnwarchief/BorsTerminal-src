/**
 * Phase 4.9.4 stage13: MEASURE-ONLY parity of the legacy v1 browser transform.
 *
 * Owner ruling, item 5: «فرانت‌اند قدیمی V1 فقط اندازه‌گیری و مستندسازی شود؛
 * اصلاحش نکن». This harness therefore writes nothing into frontend/ and fails
 * loudly if any legacy file differs from its committed bytes — before AND after
 * the run.
 *
 * The transform is the REAL exported `applyAdjustmentToCandles`, imported from
 * the legacy tree. The payload->KLineData mapping is not rewritten either: it is
 * sliced VERBATIM out of the committed KLineChartWrapper.tsx (a React component
 * that cannot be imported headlessly) with ordering and occurrence assertions.
 *
 * `@shared` is pinned to the LEGACY shared layer by vite.legacy.config.mts;
 * under frontend-v2's own config the same specifier would resolve to a different
 * file and the measurement would silently describe the wrong tree.
 *
 * Run from frontend-v2:
 *   npx vite-node -c ../_audit/phase49-4/vite.legacy.config.mts \
 *       ../_audit/phase49-4/stage13_legacy_v1_parity.mts
 */
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const REL = (p: string) => path.join(ROOT, ...p.split('/'));
const sha = (s: string | Buffer) => createHash('sha256').update(s).digest('hex');

const LEGACY = {
  transform: 'frontend/src/features/technical/nahayatnegar/lib/adjustments.ts',
  wrapper: 'frontend/src/features/technical/nahayatnegar/components/KLineChartWrapper.tsx',
  jalali: 'frontend/src/features/technical/lib/jalaliDate.ts',
  fmt: 'frontend/src/shared/lib/fmt.ts',
};

/** The legacy tree must be byte-identical to HEAD; this is a measurement, not a fix. */
function legacyDigests(): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [name, rel] of Object.entries(LEGACY)) {
    const disk = readFileSync(REL(rel));
    const head = execFileSync('git', ['show', `HEAD:${rel}`], { cwd: ROOT, encoding: 'buffer' });
    if (sha(disk) !== sha(head)) {
      throw new Error(`legacy file ${rel} differs from HEAD; item 5 forbids changing v1`);
    }
    out[name] = sha(disk);
  }
  return out;
}
const digestsBefore = legacyDigests();

// ---------------------------------------------------------------------------
// Verbatim slices of the committed v1 payload mapping.
// ---------------------------------------------------------------------------
const wrapperSource = execFileSync('git', ['show', `HEAD:${LEGACY.wrapper}`],
  { cwd: ROOT, encoding: 'utf8' });

function countOf(hay: string, needle: string): number {
  let n = 0, i = hay.indexOf(needle);
  while (i !== -1) { n += 1; i = hay.indexOf(needle, i + needle.length); }
  return n;
}

/** Slice [startAnchor .. endAnchor] inclusive, asserting a unique, ordered pair. */
function slice(label: string, startAnchor: string, endAnchor: string): string {
  if (countOf(wrapperSource, startAnchor) !== 1) {
    throw new Error(`${label}: start anchor occurs ${countOf(wrapperSource, startAnchor)} times, want 1`);
  }
  const a = wrapperSource.indexOf(startAnchor);
  const b = wrapperSource.indexOf(endAnchor, a);
  if (b === -1 || b < a) throw new Error(`${label}: end anchor not found after start anchor`);
  const text = wrapperSource.slice(a, b + endAnchor.length);
  if (!text.startsWith(startAnchor) || !text.endsWith(endAnchor)) {
    throw new Error(`${label}: slice does not span both anchors`);
  }
  return text;
}

const rawListLine = slice('rawList',
  'let rawList = Array.isArray(json) ? json : (json?.candles || json?.data || []);',
  'let rawList = Array.isArray(json) ? json : (json?.candles || json?.data || []);');

const volStart = 'const volByTime: Record<string, number> = {};';
const volLoop = 'for (const v of rawVols) {';
if (countOf(wrapperSource, volStart) !== 1) throw new Error('volByTime anchor not unique');
const volA = wrapperSource.indexOf(volStart);
const volLoopAt = wrapperSource.indexOf(volLoop, volA);
if (volLoopAt === -1) throw new Error('volByTime loop not found');
const volClose = wrapperSource.indexOf('\n      }', volLoopAt);
if (volClose === -1) throw new Error('volByTime loop close not found');
const volBlock = wrapperSource.slice(volA, volClose + '\n      }'.length);
if (!volBlock.includes('volByTime[v.time] = Number(v.value ?? v.volume ?? 0);')) {
  throw new Error('volByTime slice lost its assignment');
}

const candlesBlock = slice('parsedCandles',
  'const parsedCandles: KLineData[] = rawList',
  '.sort((a: KLineData, b: KLineData) => a.timestamp - b.timestamp);');
if (countOf(candlesBlock, '.filter(') !== 1 || countOf(candlesBlock, '.map(') !== 1) {
  throw new Error('parsedCandles slice must carry exactly one map and one filter');
}
if (!candlesBlock.includes('parseCandleTimestamp(c.timestamp ?? c.time ?? c.date ?? c.dateStr)')) {
  throw new Error('parsedCandles slice lost its timestamp parse');
}

const factorsBlock = slice('parsedFactors',
  'const parsedFactors: AdjustFactor[] = (Array.isArray(json?.factors) ? json.factors : [])',
  '.map((f: any) => ({ time: String(f.time), factor: Number(f.factor) }));');

// Specifiers inside the GENERATED module, resolved from its own directory.
const relFromMappingDir = (target: string) => {
  const r = path.relative(REL('_audit/phase49-4/db'), REL(target)).split(path.sep).join('/');
  return r.startsWith('.') ? r : `./${r}`;
};

const mappingPath = REL('_audit/phase49-4/db/legacyV1.mapping.ts');
mkdirSync(path.dirname(mappingPath), { recursive: true });
const mappingSource = [
  '// GENERATED by stage13_legacy_v1_parity.mts — verbatim slices of the committed',
  '// v1 KLineChartWrapper. Not a reconstruction and not a production file.',
  "import type { KLineData } from 'klinecharts';",
  `import type { AdjustFactor } from '${relFromMappingDir(LEGACY.transform)}';`,
  `import { parseCandleTimestamp } from '${relFromMappingDir(LEGACY.jalali)}';`,
  '',
  'export function mapPayload(json: any): { candles: KLineData[]; factors: AdjustFactor[] } {',
  `  ${rawListLine.trim()}`,
  volBlock,
  candlesBlock,
  factorsBlock,
  '  return { candles: parsedCandles, factors: parsedFactors };',
  '}',
  '',
].join('\n');
writeFileSync(mappingPath, mappingSource, 'utf8');

const { mapPayload } = await import(/* @vite-ignore */ mappingPath);
const legacy = await import(/* @vite-ignore */ REL(LEGACY.transform));
const applyAdjustmentToCandles = legacy.applyAdjustmentToCandles as
  (c: any[], f: any[], m: string) => any[];
const DEFAULT_MODE = legacy.DEFAULT_ADJUSTMENT_MODE as string;
if (typeof applyAdjustmentToCandles !== 'function') throw new Error('v1 transform did not load');
if (DEFAULT_MODE !== 'combined') throw new Error(`v1 default mode is ${DEFAULT_MODE}, expected combined`);

// Prove the loaded function is the real one, not a stub that happens to share a name.
const fnSource = applyAdjustmentToCandles.toString();
if (!fnSource.includes('roundAdjustedPrice')) throw new Error('loaded v1 transform does not round; wrong artifact');
if (!fnSource.includes('volume: candle.volume')) throw new Error('loaded v1 transform does not pass volume through');
if (/volume:\s*[^,\n]*\/\s*factor/.test(fnSource)) throw new Error('loaded v1 transform divides volume');
const transformSource = readFileSync(REL(LEGACY.transform), 'utf8');
if (!/function roundAdjustedPrice\(v: number\): number \{\s*return Math\.round\(v \* 1e4\) \/ 1e4;/.test(transformSource)) {
  throw new Error('v1 rounding is not the documented 4-decimal form');
}

// ---------------------------------------------------------------------------
// Reference: the same captured Rahavard rows stage11/stage12 use.
// ---------------------------------------------------------------------------
const EXACT_REL = 1e-9;
const PRICE_FIELDS = ['open', 'high', 'low', 'close'] as const;
type Field = (typeof PRICE_FIELDS)[number];
type Rows = Record<string, Record<string, number | null>>;

const payloadsDoc = JSON.parse(readFileSync(REL('_audit/phase49-4/db/api-payloads.json'), 'utf8'));
const barsDoc = JSON.parse(readFileSync(REL('_audit/phase49-4/db/cohort-bars.json'), 'utf8'));

const ref0: Record<string, Rows> = {};
const ref7: Record<string, Rows> = {};
for (const [sym, bars] of Object.entries(barsDoc.raw as Record<string, Rows>)) {
  const keep: Rows = {};
  for (const [d, b] of Object.entries(bars)) {
    const c = b.close, v = b.volume;
    if (c === null || c <= 0 || v === null || v <= 0) continue;
    const o = b.open;
    keep[d] = { open: o !== null && o > 0 ? o : c, high: b.high, low: b.low, close: c, volume: v };
  }
  ref0[sym] = keep;
  const adj: Rows = {};
  for (const [d, b] of Object.entries((barsDoc.adj_ohlc?.[sym] ?? {}) as Rows)) {
    adj[d] = { open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume };
  }
  ref7[sym] = adj;
}

const rel = (got: number | null | undefined, want: number | null | undefined) =>
  got === null || got === undefined || want === null || want === undefined
    ? null : want ? Math.abs(got / want - 1) : Math.abs(got);
const round4 = (v: number) => Math.round(v * 1e4) / 1e4;

function compare(sym: string, payload: any, bars: any[], factors: any[], mode: string) {
  const r0 = ref0[sym];
  const r7 = mode === 'none' ? ref0[sym] : ref7[sym];
  const fmap = new Map<string, number>();
  for (const f of factors) fmap.set(String(f.time).slice(0, 10), Number(f.factor));
  const pmap = new Map<string, any>();
  for (const c of payload.candles) pmap.set(String(c.time), c);

  const served: Record<string, any> = {};
  for (const b of bars) served[new Date(b.timestamp).toISOString().slice(0, 10)] = b;
  const dates = Object.keys(r0);
  const missing = dates.filter((d) => !(d in served));
  const extra = Object.keys(served).filter((d) => !(d in r0));

  const diff: Record<string, number> = {};
  const max: Record<string, number> = {};
  const worst: Record<string, unknown> = {};
  const sample: unknown[] = [];
  let volBad = 0, outside = 0, explained = 0, unexplained = 0, diffRows = 0;
  let maxAbs = 0;
  const unexplainedSample: unknown[] = [];
  for (const f of PRICE_FIELDS) { diff[f] = 0; max[f] = 0; worst[f] = null; }

  for (const d of dates) {
    const b = served[d];
    if (!b) continue;
    const k = mode === 'none' ? 1 : (fmap.get(d) ?? 1);
    const pc = pmap.get(d);
    let rowBad = false;
    for (const f of PRICE_FIELDS) {
      const want = r7[d]?.[f];
      const r = rel(b[f], want);
      if (r === null) continue;
      if (r > max[f]) { max[f] = r; worst[f] = { date: d, served: b[f], reference: want }; }
      if (r > EXACT_REL) {
        diff[f] += 1; rowBad = true;
        const abs = Math.abs(b[f] - (want as number));
        if (abs > maxAbs) maxAbs = abs;
        // Attribution: is this divergence exactly the documented 4-decimal round?
        const unrounded = pc ? Number(pc[f]) * k : NaN;
        if (Number.isFinite(unrounded) && round4(unrounded) === b[f]) explained += 1;
        else {
          unexplained += 1;
          if (unexplainedSample.length < 10) {
            unexplainedSample.push({ date: d, field: f, served: b[f], unrounded, reference: want });
          }
        }
        if (sample.length < 12) {
          sample.push({ date: d, field: f, served: b[f], reference: want, factor: k, rel: r });
        }
      }
    }
    if (rowBad) diffRows += 1;
    if (b.volume !== r0[d].volume) volBad += 1;
    if (b.open > b.high || b.open < b.low) outside += 1;
  }
  const refOutside = dates.filter((d) => {
    const r = r0[d];
    return r.open !== null && r.high !== null && r.low !== null && (r.open > r.high || r.open < r.low);
  }).length;
  const total = PRICE_FIELDS.reduce((n, f) => n + diff[f], 0);
  return {
    symbol: sym, rows_served: bars.length, rows_reference: dates.length,
    rows_missing: missing.length, rows_extra: extra.length,
    rows_filtered_by_v1: payload.candles.length - bars.length,
    diff_rows: diff, diff_total: total, rows_with_any_diff: diffRows,
    max_rel: max, max_abs_price_error: maxAbs, worst, sample,
    divergence_attribution: { explained_by_4dp_rounding: explained, unexplained, unexplained_sample: unexplainedSample },
    volume_mismatch_rows: volBad,
    served_open_outside_rows: outside, reference_open_outside_rows: refOutside,
    status: total || volBad || missing.length || extra.length ? 'DIVERGENT' : 'MATCH',
  };
}

function rollUp(per: ReturnType<typeof compare>[]) {
  const diff: Record<string, number> = {};
  const max: Record<string, number> = {};
  for (const f of PRICE_FIELDS) {
    diff[f] = per.reduce((n, r) => n + r.diff_rows[f], 0);
    max[f] = per.reduce((n, r) => Math.max(n, r.max_rel[f]), 0);
  }
  return {
    symbols: per.length,
    symbols_match: per.filter((r) => r.status === 'MATCH').length,
    symbols_divergent: per.filter((r) => r.status !== 'MATCH').map((r) => r.symbol),
    rows_served: per.reduce((n, r) => n + r.rows_served, 0),
    rows_missing: per.reduce((n, r) => n + r.rows_missing, 0),
    rows_extra: per.reduce((n, r) => n + r.rows_extra, 0),
    rows_filtered_by_v1: per.reduce((n, r) => n + r.rows_filtered_by_v1, 0),
    diff_rows: diff,
    diff_total: PRICE_FIELDS.reduce((n, f) => n + diff[f], 0),
    rows_with_any_diff: per.reduce((n, r) => n + r.rows_with_any_diff, 0),
    max_rel: max,
    max_abs_price_error: per.reduce((n, r) => Math.max(n, r.max_abs_price_error), 0),
    explained_by_4dp_rounding: per.reduce((n, r) => n + r.divergence_attribution.explained_by_4dp_rounding, 0),
    unexplained: per.reduce((n, r) => n + r.divergence_attribution.unexplained, 0),
    volume_mismatch_rows: per.reduce((n, r) => n + r.volume_mismatch_rows, 0),
    served_open_outside_rows: per.reduce((n, r) => n + r.served_open_outside_rows, 0),
    reference_open_outside_rows: per.reduce((n, r) => n + r.reference_open_outside_rows, 0),
  };
}

const symbols = Object.keys(payloadsDoc.payloads.after);
const combos: Record<string, { payload: 'before' | 'after'; mode: string }> = {
  v1_on_before_payload: { payload: 'before', mode: DEFAULT_MODE },
  v1_on_after_payload: { payload: 'after', mode: DEFAULT_MODE },
  v1_raw_mode_after_payload: { payload: 'after', mode: 'none' },
};

const results: Record<string, unknown> = {};
for (const [name, c] of Object.entries(combos)) {
  const per = symbols.map((sym) => {
    const p = payloadsDoc.payloads[c.payload][sym];
    if (p?.status !== 'success') throw new Error(`${name}: ${sym} payload status=${p?.status}`);
    const { candles, factors } = mapPayload(p);
    const bars = applyAdjustmentToCandles(candles, factors, c.mode);
    return compare(sym, p, bars, factors, c.mode);
  });
  const summary = rollUp(per);
  results[name] = { ...c, summary, per_symbol: per };
  console.log(
    `${name}: price diff ${summary.diff_total} (4dp-explained ${summary.explained_by_4dp_rounding}, ` +
    `unexplained ${summary.unexplained}) | volume ${summary.volume_mismatch_rows} | ` +
    `MATCH ${summary.symbols_match}/${summary.symbols} | rows ${summary.rows_served} | ` +
    `filtered ${summary.rows_filtered_by_v1} | max_rel ${JSON.stringify(summary.max_rel)}`
  );
}

const digestsAfter = legacyDigests();
for (const k of Object.keys(digestsBefore)) {
  if (digestsBefore[k] !== digestsAfter[k]) throw new Error(`legacy ${k} changed during the run`);
}

const shipped = (results.v1_on_after_payload as any).summary;
const onBefore = (results.v1_on_before_payload as any).summary;
const rawMode = (results.v1_raw_mode_after_payload as any).summary;
const evidence = {
  schema: 'phase49-4-legacy-v1-parity-v1',
  mission: 'Phase 4.9.4 runtime parity with Rahavard',
  owner_ruling: 'item 5 — legacy frontend V1 is measured and documented only, never fixed',
  status: 'MEASURED',
  acceptance_applies: false,
  fix_applied: false,
  measure_only: true,
  measurement: {
    kind: 'the real legacy v1 applyAdjustmentToCandles over the real API payloads',
    transform_module: LEGACY.transform,
    mapping_source: `${LEGACY.wrapper} (verbatim slices, generated module under the gitignored run dir)`,
    generated_mapping: '_audit/phase49-4/db/legacyV1.mapping.ts',
    runner: 'vite-node with @shared pinned to the legacy tree',
    config: '_audit/phase49-4/vite.legacy.config.mts',
    default_mode: DEFAULT_MODE,
    is_ui_test: false,
    screenshot: 'NOT_MEASURED',
    note: 'the transform and the payload mapping are the committed v1 code; no browser was driven',
  },
  legacy_tree_unchanged: {
    verified_against: 'HEAD',
    before_run_sha256: digestsBefore,
    after_run_sha256: digestsAfter,
    identical: true,
  },
  reference_law: {
    statement: 'type7 = type0 x factor for open/high/low/close; volume is never scaled',
    tolerance: EXACT_REL,
    tolerance_unchanged: true,
    raw_mode_reference: 'type0 (mode=none applies no factor)',
  },
  inputs: {
    api_payloads: '_audit/phase49-4/db/api-payloads.json',
    cohort_bars: '_audit/phase49-4/db/cohort-bars.json',
    symbols: symbols.length,
    capture_day: payloadsDoc.capture_day,
  },
  finding: {
    volume: shipped.volume_mismatch_rows === 0
      ? 'v1 already passes volume through untouched; it never divided by the factor'
      : 'v1 volume diverges from the captured type0 volume',
    price: shipped.diff_total === 0
      ? 'v1 prices match Rahavard at 1e-9'
      : 'v1 rounds every adjusted price to 4 decimals (roundAdjustedPrice), which is a ' +
        'real divergence from Rahavard at the 1e-9 tolerance on the old, heavily ' +
        'scaled part of the history',
    attribution: `${shipped.explained_by_4dp_rounding} of ${shipped.diff_total} divergent price fields ` +
      `are exactly round4(payload x factor); ${shipped.unexplained} are not`,
    raw_mode: rawMode.diff_total === 0
      ? 'with mode=none v1 serves the captured literal series exactly (0 divergences)'
      : `mode=none still diverges on ${rawMode.diff_total} fields`,
    not_a_regression: 'this is the pre-existing v1 behaviour, unchanged by Phase 4.9.4; ' +
      'v1 is not the shipped frontend (frontend-v2 is)',
  },
  backend_fix_effect_on_v1: {
    note: 'v1 code is identical on both sides; only the API payload changed, so this ' +
          'isolates what the backend Widen retirement did for the legacy consumer',
    price_diff_fields_before: onBefore.diff_total,
    price_diff_fields_after: shipped.diff_total,
    max_rel_before: onBefore.max_rel,
    max_rel_after: shipped.max_rel,
    volume_mismatch_before: onBefore.volume_mismatch_rows,
    volume_mismatch_after: shipped.volume_mismatch_rows,
    symbols_match_before: onBefore.symbols_match,
    symbols_match_after: shipped.symbols_match,
  },
  combinations: results,
  not_measured: {
    ui_screenshot: 'no browser was driven; a real v1 UI screenshot remains NOT_MEASURED',
    canvas_pixels: 'KLineCharts rendering is not exercised here',
    v1_weekly_monthly_aggregation: 'only the daily series is measured',
  },
};

const outRel = '_audit/phase49-4/evidence/LEGACY-V1-PARITY.json';
const manRel = '_audit/phase49-4/manifests/stage13-legacy-v1-parity.json';
mkdirSync(path.dirname(REL(outRel)), { recursive: true });
mkdirSync(path.dirname(REL(manRel)), { recursive: true });
const body = JSON.stringify(evidence, null, 1) + '\n';
writeFileSync(REL(outRel), body, 'utf8');
const outSha = sha(body);
writeFileSync(REL(manRel), JSON.stringify({
  stage: 'stage13_legacy_v1_parity',
  finished_utc: new Date().toISOString().replace(/\.\d+Z$/, 'Z'),
  payload_path: outRel,
  payload_sha256: outSha,
  measure_only: true,
  exit_code: 0,
}, null, 1) + '\n', 'utf8');
console.log(`v1 shipped mode: price diff ${shipped.diff_total}, volume diff ${shipped.volume_mismatch_rows}, ` +
  `MATCH ${shipped.symbols_match}/${shipped.symbols}, max_rel ${JSON.stringify(shipped.max_rel)}`);
console.log(`legacy tree unchanged: ${Object.keys(digestsBefore).length} files identical to HEAD`);
console.log(`wrote ${outRel} (${outSha.slice(0, 16)})`);