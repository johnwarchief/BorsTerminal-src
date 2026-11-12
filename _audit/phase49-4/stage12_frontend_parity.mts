/**
 * Phase 4.9.4 stage12: parity of the browser consumption path against Rahavard.
 *
 * The API payload is not what the user sees. frontend-v2's toKlineBars turns it
 * into KLineCharts bars, and that transform is where the destructive rounding
 * and the volume division lived. This harness imports the REAL module — not a
 * copy — and runs it over the real payloads dumped by stage11.
 *
 * Four combinations are measured so each fix's contribution is separable:
 *   before payload x before transform   (the shipped product before this phase)
 *   after  payload x after  transform   (the shipped product after this phase)
 *   plus the two cross terms.
 * The BEFORE transform is read from `git show HEAD:...`, so it is the committed
 * artifact and not a hand-written reconstruction.
 *
 * Run from frontend-v2:  npx vite-node ../_audit/phase49-4/stage12_frontend_parity.mts
 */
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { toKlineBars as afterTransform } from '@features/chart/api/useChart';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const REL = (p: string) => path.join(ROOT, ...p.split('/'));

const EXACT_REL = 1e-9;
const PRICE_FIELDS = ['open', 'high', 'low', 'close'] as const;
type Field = (typeof PRICE_FIELDS)[number];
type Bar = { timestamp: number; open: number; high: number; low: number; close: number; volume: number };
type Rows = Record<string, Record<string, number | null>>;

const payloadsDoc = JSON.parse(readFileSync(REL('_audit/phase49-4/db/api-payloads.json'), 'utf8'));
const barsDoc = JSON.parse(readFileSync(REL('_audit/phase49-4/db/cohort-bars.json'), 'utf8'));

// The committed pre-fix transform, materialized under the gitignored run dir.
const beforePath = REL('_audit/phase49-4/db/useChart.before.ts');
mkdirSync(path.dirname(beforePath), { recursive: true });
const beforeSource = execFileSync(
  'git', ['show', 'HEAD:frontend-v2/src/features/chart/api/useChart.ts'],
  { cwd: ROOT, encoding: 'utf8' }
);
writeFileSync(beforePath, beforeSource, 'utf8');
const beforeTransform = (await import(/* @vite-ignore */ beforePath)).toKlineBars as typeof afterTransform;
if (typeof beforeTransform !== 'function') throw new Error('BEFORE transform did not load');
if (!/Math\.round/.test(beforeSource)) throw new Error('BEFORE source carries no Math.round; wrong artifact');
if (/Math\.round/.test(readFileSync(REL('frontend-v2/src/features/chart/api/useChart.ts'), 'utf8'))) {
  throw new Error('AFTER source still rounds; the fix is not in the working tree');
}

/** type0 exactly as captured, with the engine's own row-skip rules. */
function reference(): { ref0: Record<string, Rows>; ref7: Record<string, Rows> } {
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
  return { ref0, ref7 };
}

const rel = (got: number | null | undefined, want: number | null | undefined) =>
  got === null || got === undefined || want === null || want === undefined
    ? null
    : want ? Math.abs(got / want - 1) : Math.abs(got);

function compare(sym: string, bars: Bar[], ref0: Rows, ref7: Rows) {
  const served: Record<string, Bar> = {};
  for (const b of bars) served[new Date(b.timestamp).toISOString().slice(0, 10)] = b;
  const dates = Object.keys(ref0);
  const missing = dates.filter((d) => !(d in served));
  const extra = Object.keys(served).filter((d) => !(d in ref0));
  const diff: Record<string, number> = {};
  const max: Record<string, number> = {};
  const worst: Record<string, unknown> = {};
  const sample: unknown[] = [];
  let volBad = 0;
  let outside = 0;
  for (const f of PRICE_FIELDS) { diff[f] = 0; max[f] = 0; worst[f] = null; }
  for (const d of dates) {
    const b = served[d];
    if (!b) continue;
    for (const f of PRICE_FIELDS) {
      const want = ref7[d]?.[f];
      const r = rel(b[f], want);
      if (r === null) continue;
      if (r > max[f]) { max[f] = r; worst[f] = { date: d, served: b[f], reference_type7: want }; }
      if (r > EXACT_REL) {
        diff[f] += 1;
        if (sample.length < 20) sample.push({ date: d, field: f, served: b[f], reference_type7: want });
      }
    }
    if (b.volume !== ref0[d].volume) volBad += 1;
    if (b.open > b.high || b.open < b.low) outside += 1;
  }
  const refOutside = dates.filter((d) => {
    const r = ref0[d];
    return r.open !== null && r.high !== null && r.low !== null && (r.open > r.high || r.open < r.low);
  }).length;
  const total = PRICE_FIELDS.reduce((n, f) => n + diff[f], 0);
  return {
    symbol: sym, rows_served: bars.length, rows_reference: dates.length,
    rows_missing: missing.length, rows_extra: extra.length,
    diff_rows: diff, diff_total: total, max_rel: max, worst, sample,
    volume_mismatch_rows: volBad,
    served_open_outside_rows: outside, reference_open_outside_rows: refOutside,
    status: total || volBad || missing.length || extra.length ? 'PARTIAL' : 'PASS',
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
    symbols_pass: per.filter((r) => r.status === 'PASS').length,
    symbols_partial: per.filter((r) => r.status !== 'PASS').map((r) => r.symbol),
    rows_served: per.reduce((n, r) => n + r.rows_served, 0),
    rows_missing: per.reduce((n, r) => n + r.rows_missing, 0),
    rows_extra: per.reduce((n, r) => n + r.rows_extra, 0),
    diff_rows: diff,
    diff_total: PRICE_FIELDS.reduce((n, f) => n + diff[f], 0),
    max_rel: max,
    volume_mismatch_rows: per.reduce((n, r) => n + r.volume_mismatch_rows, 0),
    served_open_outside_rows: per.reduce((n, r) => n + r.served_open_outside_rows, 0),
    reference_open_outside_rows: per.reduce((n, r) => n + r.reference_open_outside_rows, 0),
  };
}

const { ref0, ref7 } = reference();
const symbols = Object.keys(payloadsDoc.payloads.after);
const combos: Record<string, { payload: 'before' | 'after'; transform: 'before' | 'after'; adjustment: number }> = {
  product_before: { payload: 'before', transform: 'before', adjustment: 3 },
  product_after: { payload: 'after', transform: 'after', adjustment: 3 },
  payload_only_fix: { payload: 'after', transform: 'before', adjustment: 3 },
  transform_only_fix: { payload: 'before', transform: 'after', adjustment: 3 },
  product_after_raw_mode: { payload: 'after', transform: 'after', adjustment: 0 },
};

const results: Record<string, unknown> = {};
const failures: string[] = [];
for (const [name, c] of Object.entries(combos)) {
  const fn = c.transform === 'after' ? afterTransform : beforeTransform;
  const per = symbols.map((sym) => {
    const p = payloadsDoc.payloads[c.payload][sym];
    if (p?.status !== 'success') {
      throw new Error(`${name}: ${sym} payload status=${p?.status}`);
    }
    // In raw mode the reference is type0, not type7: adjustment=0 must serve
    // the captured literal series with no scaling at all.
    const bars = fn(p.candles, p.factors, c.adjustment) as Bar[];
    return compare(sym, bars, ref0[sym], c.adjustment === 0 ? ref0[sym] : ref7[sym]);
  });
  const summary = rollUp(per);
  results[name] = { ...c, summary, per_symbol: per };
  console.log(
    `${name}: diff ${summary.diff_total} | volume ${summary.volume_mismatch_rows} | ` +
    `PASS ${summary.symbols_pass}/${summary.symbols} | rows ${summary.rows_served} | ` +
    `max_rel ${JSON.stringify(summary.max_rel)}`
  );
  if (name.startsWith('product_after') && (summary.diff_total || summary.volume_mismatch_rows ||
      summary.symbols_pass !== summary.symbols)) {
    failures.push(`${name}: ${summary.diff_total} price divergences, ` +
      `${summary.volume_mismatch_rows} volume divergences, ` +
      `${summary.symbols_pass}/${summary.symbols} symbols PASS`);
  }
}

const productBefore = (results.product_before as any).summary;
const productAfter = (results.product_after as any).summary;
const evidence = {
  schema: 'phase49-4-frontend-parity-v1',
  mission: 'Phase 4.9.4 runtime parity with Rahavard',
  status: failures.length ? 'PARTIAL' : 'PASS',
  failures,
  measurement: {
    kind: 'the real frontend-v2 toKlineBars over the real API payloads',
    module: 'frontend-v2/src/features/chart/api/useChart.ts',
    before_transform_source: 'git show HEAD:frontend-v2/src/features/chart/api/useChart.ts',
    runner: 'vite-node',
    is_ui_test: false,
    screenshot: 'NOT_MEASURED',
    note: 'this measures the transform the chart widget calls; it is not a ' +
          'browser render and is never reported as a UI test',
  },
  reference_law: {
    statement: 'type7 = type0 x factor for open/high/low/close; volume is never scaled',
    tolerance: EXACT_REL,
    tolerance_unchanged: true,
    raw_mode_reference: 'type0 (adjustment=0 applies no factor)',
  },
  inputs: {
    api_payloads: '_audit/phase49-4/db/api-payloads.json',
    cohort_bars: '_audit/phase49-4/db/cohort-bars.json',
    symbols: symbols.length,
    capture_day: payloadsDoc.capture_day,
  },
  before_after_delta: {
    price_diff_rows_before: productBefore.diff_total,
    price_diff_rows_after: productAfter.diff_total,
    volume_mismatch_before: productBefore.volume_mismatch_rows,
    volume_mismatch_after: productAfter.volume_mismatch_rows,
    symbols_pass_before: productBefore.symbols_pass,
    symbols_pass_after: productAfter.symbols_pass,
    rows_served_before: productBefore.rows_served,
    rows_served_after: productAfter.rows_served,
    max_rel_before: productBefore.max_rel,
    max_rel_after: productAfter.max_rel,
  },
  combinations: results,
  not_measured: {
    ui_screenshot: 'no browser was driven; a real UI screenshot remains NOT_MEASURED',
    canvas_pixels: 'KLineCharts rendering is not exercised here',
  },
};

const outRel = '_audit/phase49-4/evidence/FRONTEND-PARITY.json';
const manRel = '_audit/phase49-4/manifests/stage12-frontend-parity.json';
mkdirSync(path.dirname(REL(outRel)), { recursive: true });
mkdirSync(path.dirname(REL(manRel)), { recursive: true });
const body = JSON.stringify(evidence, null, 1) + '\n';
writeFileSync(REL(outRel), body, 'utf8');
const { createHash } = await import('node:crypto');
const sha = (s: string) => createHash('sha256').update(s).digest('hex');
const outSha = sha(body);
const manifest = {
  stage: 'stage12_frontend_parity',
  finished_utc: new Date().toISOString().replace(/\.\d+Z$/, 'Z'),
  payload_path: outRel,
  payload_sha256: outSha,
  exit_code: failures.length ? 1 : 0,
};
writeFileSync(REL(manRel), JSON.stringify(manifest, null, 1) + '\n', 'utf8');
console.log(`price diff ${productBefore.diff_total} -> ${productAfter.diff_total} | ` +
  `volume ${productBefore.volume_mismatch_rows} -> ${productAfter.volume_mismatch_rows} | ` +
  `PASS symbols ${productBefore.symbols_pass} -> ${productAfter.symbols_pass}`);
for (const f of failures) console.log('FAILURE:', f);
console.log(`wrote ${outRel} (${outSha.slice(0, 16)})`);
process.exit(failures.length ? 1 : 0);