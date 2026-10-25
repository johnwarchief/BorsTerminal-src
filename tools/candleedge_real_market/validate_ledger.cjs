const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const readline = require('readline');

const args = Object.fromEntries(
  process.argv.slice(2).map((arg) => {
    const [key, ...rest] = arg.replace(/^--/, '').split('=');
    return [key, rest.join('=')];
  }),
);
const DIR = args.dir ? path.resolve(args.dir) : path.resolve(__dirname, 'evidence');
const OUT = args.out ? path.resolve(args.out) : path.join(DIR, 'ledger-validation.json');

function open(file) {
  const plain = path.join(DIR, file);
  if (fs.existsSync(plain)) return fs.createReadStream(plain);
  const gz = `${plain}.gz`;
  if (fs.existsSync(gz)) return fs.createReadStream(gz).pipe(zlib.createGunzip());
  throw new Error(`missing ${plain} or ${gz}`);
}
const DETECTORS = new Set([
  'doji', 'bullish_engulfing', 'bearish_engulfing', 'hammer', 'shooting_star',
  'double_top', 'double_bottom', 'ascending_triangle', 'descending_triangle',
  'symmetrical_triangle', 'rising_wedge', 'falling_wedge',
  'higher_high', 'higher_low', 'lower_high', 'lower_low',
  'bos_bullish', 'bos_bearish', 'liquidity_sweep_high', 'liquidity_sweep_low',
]);
const LEVELED = new Set([
  'bos_bullish', 'bos_bearish', 'liquidity_sweep_high', 'liquidity_sweep_low',
]);

(async () => {
  const bars = new Map();
  const seriesStream = readline.createInterface({
    input: open('series.ndjson'),
    crlfDelay: Infinity,
  });
  for await (const line of seriesStream) {
    if (!line.trim()) continue;
    const s = JSON.parse(line);
    bars.set(`${s.symbol}|${s.timeframe}`, s.candleCount);
  }

  const stats = {
    lines: 0,
    adjusted: 0,
    raw: 0,
    byMode: {},
    byDetector: {},
    unknownDetector: 0,
    badShape: 0,
    emptyAnchors: 0,
    anchorIndexAfterEvent: 0,
    anchorConfirmedAfterEvent: 0,
    anchorConfirmedBeforeIndex: 0,
    nonFinitePrice: 0,
    levelMissing: 0,
    levelMismatch: 0,
    levelAnchorNotPreconfirmed: 0,
    confirmedOutsideSeries: 0,
    duplicateKey: 0,
    engulfingWithoutPrevious: 0,
    structureBefore41: 0,
    breakCandleNotAtEvent: 0,
    firstExamples: [],
  };
  const keys = new Set();
  const STRUCTURE = new Set([
    'bos_bullish', 'bos_bearish', 'liquidity_sweep_high', 'liquidity_sweep_low',
    'ascending_triangle', 'descending_triangle', 'symmetrical_triangle',
    'rising_wedge', 'falling_wedge', 'double_top', 'double_bottom',
    'higher_high', 'higher_low', 'lower_high', 'lower_low',
  ]);

  const ledgerStream = readline.createInterface({
    input: open('ledger.ndjson'),
    crlfDelay: Infinity,
  });
  for await (const line of ledgerStream) {
    if (!line.trim()) continue;
    stats.lines += 1;
    const e = JSON.parse(line);
    stats.byMode[e.m] = (stats.byMode[e.m] ?? 0) + 1;
    if (e.m === 'adj') stats.adjusted += 1;
    if (e.m === 'raw') stats.raw += 1;
    stats.byDetector[e.d] = (stats.byDetector[e.d] ?? 0) + 1;
    const note = (msg) => {
      if (stats.firstExamples.length < 12) stats.firstExamples.push({ msg, e });
    };
    if (!DETECTORS.has(e.d)) { stats.unknownDetector += 1; note('unknown detector'); }
    if (typeof e.s !== 'string' || typeof e.tf !== 'string' || !Number.isInteger(e.i) || e.i < 0) {
      stats.badShape += 1; note('bad shape'); continue;
    }
    const seriesBars = bars.get(`${e.s}|${e.tf}`);
    if (seriesBars === undefined || e.i >= seriesBars) stats.confirmedOutsideSeries += 1;
    const dkey = `${e.s}|${e.tf}|${e.m}|${e.d}|${e.i}`;
    if (keys.has(dkey)) { stats.duplicateKey += 1; note('duplicate key'); }
    keys.add(dkey);
    if (!Array.isArray(e.a) || e.a.length === 0) { stats.emptyAnchors += 1; note('empty anchors'); continue; }
    let hasLevelAnchor = false;
    let breakCandleAtEvent = false;
    for (const a of e.a) {
      if (!Array.isArray(a) || a.length !== 4) { stats.badShape += 1; note('bad anchor shape'); continue; }
      const [index, role, price, confirmed] = a;
      if (!Number.isInteger(index) || !Number.isInteger(confirmed)) { stats.badShape += 1; note('anchor not integer'); continue; }
      if (index > e.i) { stats.anchorIndexAfterEvent += 1; note('anchor index after event'); }
      if (confirmed > e.i) { stats.anchorConfirmedAfterEvent += 1; note('anchor confirmed after event'); }
      if (confirmed < index) { stats.anchorConfirmedBeforeIndex += 1; note('anchor confirmed before its own bar'); }
      if (!(Number.isFinite(price) && price > 0)) { stats.nonFinitePrice += 1; note('non-finite price'); }
      if (LEVELED.has(e.d) && role !== 'candle' && confirmed < e.i && price === e.l) hasLevelAnchor = true;
      if (LEVELED.has(e.d) && role === 'candle' && index === e.i && confirmed === e.i) breakCandleAtEvent = true;
    }
    if (LEVELED.has(e.d)) {
      if (typeof e.l !== 'number' || !Number.isFinite(e.l)) { stats.levelMissing += 1; note('level missing'); }
      else if (!e.a.some((a) => a[2] === e.l)) { stats.levelMismatch += 1; note('level not among anchors'); }
      if (!hasLevelAnchor) { stats.levelAnchorNotPreconfirmed += 1; note('level anchor not pre-confirmed'); }
      if (!breakCandleAtEvent) { stats.breakCandleNotAtEvent += 1; note('no break candle at event bar'); }
    } else if (e.l !== null) {
      stats.levelMismatch += 1; note('level on non-level detector');
    }
    if ((e.d === 'bullish_engulfing' || e.d === 'bearish_engulfing') && e.i < 1) {
      stats.engulfingWithoutPrevious += 1; note('engulfing without previous bar');
    }
    if (STRUCTURE.has(e.d) && e.i <= 40) {
      stats.structureBefore41 += 1;
      note('structure event before bar 41');
    }
  }

  // cross-check totals against stats.json
  const statsPath = path.join(DIR, 'stats.json');
  const statsJson = JSON.parse(
    fs.existsSync(statsPath)
      ? fs.readFileSync(statsPath, 'utf8')
      : zlib.gunzipSync(fs.readFileSync(`${statsPath}.gz`)).toString('utf8'),
  );
  const summary = {
    ...stats,
    ledgerByMode: stats.byMode,
    statsEvents: statsJson.meta.events,
    ledgerDetectors: Object.keys(stats.byDetector).length,
    statsDetectorCount: new Set(statsJson.detectorStats.map((r) => r.detector)).size,
    seriesCount: bars.size,
  };
  fs.writeFileSync(OUT, JSON.stringify(summary, null, 2));
  console.log(JSON.stringify(summary, null, 2));
})();
