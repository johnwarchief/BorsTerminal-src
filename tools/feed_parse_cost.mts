// tools/feed_parse_cost.mts — هزینهٔ واقعیِ هر پولینگِ تابلو درِ مرورگر چقدر است؟
//
// چرا: بدنهٔ /api/market با هر تیک درِ کلاینت `zod.parse` می‌شود
// (features/market/api/useMarketFeed.ts → http(..., { schema: MarketFeedSchema })).
// با ~۹۰ فیلد در هر ردیف و هزاران ردیف، شمارِ اعتبارسنجی‌ها درِ هر پولینگ
// صده‌هزارتاست؛ رویِ دستگاهِ ضعیف همین می‌تواند گلو باشد، نه شبکه (GZip روشن است).
// این ابزار همان مسیرِ واقعی را درِ node می‌زند و عدد می‌دهد: JSON.parse،
// schema.parse، و شمارِ ردیف/فیلد.
//
//   JEV... نه، فقط node:
//   node --experimental-strip-types tools/feed_parse_cost.mts --url http://127.0.0.1:8001
//   node --experimental-strip-types tools/feed_parse_cost.mts --file _audit/a_board.json
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..');

const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:8001');
const FILE = arg('file', '');
const OUT = arg('out', '_audit/feed_parse_cost.json');
const RUNS = Number(arg('runs', '5'));

let text: string;
if (FILE) {
  text = readFileSync(FILE, 'utf8');
} else {
  const r = await fetch(`${BASE}/api/market`, { headers: { Accept: 'application/json' } });
  if (!r.ok) throw new Error(`${BASE}/api/market -> HTTP ${r.status}`);
  text = await r.text();
}

const { MarketFeedSchema } = await import(
  pathToFileImport(`${resolve(ROOT, 'frontend/src/shared/types/marketRow.ts')}`)
);

function ms(fn: () => unknown, runs: number): { best: number; median: number; all: number[] } {
  const all: number[] = [];
  for (let i = 0; i < runs; i++) {
    const t0 = performance.now();
    fn();
    all.push(Math.round(performance.now() - t0));
  }
  const sorted = [...all].sort((a, b) => a - b);
  return { best: sorted[0], median: sorted[Math.floor(sorted.length / 2)], all };
}

function pathToFileImport(p: string): string {
  return 'file:///' + p.replace(/\\/g, '/');
}

const bytes = Buffer.byteLength(text, 'utf8');
const json = ms(() => JSON.parse(text), RUNS);
const parsed = JSON.parse(text);
const rows = (parsed.data || []).length;
const fields = rows ? Object.keys(parsed.data[0]).length : 0;
const zodRun = ms(() => MarketFeedSchema.parse(parsed), RUNS);
const clone = ms(() => JSON.parse(JSON.stringify(parsed)), Math.min(RUNS, 3));

const report = {
  base: FILE ? `file:${FILE}` : BASE,
  body_bytes: bytes,
  body_mb: Math.round((bytes / 1e6) * 100) / 100,
  rows,
  fields_per_row: fields,
  validations_per_poll: rows * fields,
  runs: RUNS,
  json_parse_ms: json,
  zod_parse_ms: zodRun,
  deep_clone_ms: clone,
  // پولینگِ تابلو درِ نشست ۵ ثانیه است؛ این دو عدد می‌گویند چند درصدِ آن بازه
  // صرفِ parse می‌شود.
  zod_share_of_5s_tick: Math.round((zodRun.median / 5000) * 1000) / 10,
};
writeFileSync(OUT, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
