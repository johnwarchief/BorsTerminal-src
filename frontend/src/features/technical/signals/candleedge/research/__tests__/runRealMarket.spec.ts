import { createHash } from 'node:crypto';
import {
  closeSync,
  existsSync,
  mkdirSync,
  openSync,
  readFileSync,
  statSync,
  writeFileSync,
  writeSync,
} from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { CANDLEEDGE_SOURCE } from '../../index';
import { EVAL_CUTOFF_MS, FORWARD_HORIZONS, FORWARD_NOTE, evaluateForward } from '../forwardEval';
import { verifyInputSha256 } from '../hash';
import { buildSalience } from '../salience';
import type {
  RealMarketRecord,
  ResearchEvent,
  ResearchTimeframe,
  SeriesScan,
} from '../realMarketTypes';
import { dayOf, scanRecord } from '../series';
import { ResearchStats, type SeriesSummary, type ErrorRow } from '../stats';

const NDJSON = process.env.CANDLEEDGE_NDJSON;
const OUT = process.env.CANDLEEDGE_OUT;
const LIMIT = Number(process.env.CANDLEEDGE_LIMIT ?? 0);
const TIMEFRAMES: ResearchTimeframe[] = ['D', 'W', 'M'];
const STRUCTURE = new Set<string>([
  'double_top', 'double_bottom',
  'ascending_triangle', 'descending_triangle', 'symmetrical_triangle',
  'rising_wedge', 'falling_wedge',
  'higher_high', 'higher_low', 'lower_high', 'lower_low',
  'bos_bullish', 'bos_bearish',
  'liquidity_sweep_high', 'liquidity_sweep_low',
]);

function sha256File(path: string): string {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

function round(value: number, digits = 3): number {
  return Number(value.toFixed(digits));
}

function chooseViewerSymbols(records: RealMarketRecord[]): string[] {
  const override = (process.env.CANDLEEDGE_VIEWER_SYMBOLS ?? '')
    .split(',').map((s) => s.trim()).filter(Boolean);
  if (override.length) return [...new Set(override)];
  const full = records
    .filter((r) => r.status === 'success' && r.universe?.stratum === 'full')
    .sort((a, b) => a.symbol.localeCompare(b.symbol));
  const picks: string[] = [];
  for (const band of ['Q4-high', 'Q3', 'Q2', 'Q1-low']) {
    for (const record of full.filter((r) => r.universe.liquidityBand === band).slice(0, 2)) {
      picks.push(record.symbol);
    }
  }
  const withEvents = full.find(
    (r) => (r.adjustEvents?.length ?? 0) > 0 && r.adjustCapability?.combined_available === true,
  );
  const withoutChain = full.find(
    (r) => r.adjustCapability?.combined_available === false,
  );
  if (withEvents) picks.push(withEvents.symbol);
  if (withoutChain) picks.push(withoutChain.symbol);
  return [...new Set(picks)].slice(0, 12);
}

function compactEvent(event: ResearchEvent): Record<string, unknown> {
  return {
    d: event.detector,
    b: event.bias,
    i: event.confirmedAtIndex,
    t: event.confirmedAt,
    l: event.level ?? null,
    a: event.anchors.map((a) => [a.index, a.role, a.price, a.confirmedAtIndex ?? a.index]),
  };
}

function barsForForward(bars: SeriesScan['adjustedBars']) {
  return bars.map((bar) => ({
    time: Number(bar.time),
    open: bar.open,
    close: bar.close,
  }));
}

function addMarketBaseline(
  market: Map<string, { sum: number; count: number }>,
  timeframe: ResearchTimeframe,
  bars: SeriesScan['adjustedBars'],
): void {
  for (let t = 0; t < bars.length; t += 1) {
    if (!(bars[t].open > 0)) continue;
    for (const horizon of FORWARD_HORIZONS) {
      const exit = t + horizon - 1;
      if (exit >= bars.length) continue;
      const key = `${timeframe}|${Number(bars[t].time)}|${horizon}`;
      const value = bars[exit].close / bars[t].open - 1;
      const found = market.get(key);
      if (found) {
        found.sum += value;
        found.count += 1;
      } else {
        market.set(key, { sum: value, count: 1 });
      }
    }
  }
}

function viewerSeries(series: SeriesScan) {
  return {
    timeframe: series.timeframe,
    candleCount: series.candleCount,
    dateRange: series.dateRange,
    adjustedError: series.adjusted.error ?? null,
    rawError: series.raw.error ?? null,
    adjusted: series.adjustedBars.map((bar) => [
      dayOf(Number(bar.time)), bar.open, bar.high, bar.low, bar.close, bar.volume ?? 0,
    ]),
    raw: series.rawBars.map((bar) => [
      dayOf(Number(bar.time)), bar.open, bar.high, bar.low, bar.close, bar.volume ?? 0,
    ]),
    events: series.adjusted.events.map((event) => ({
      key: event.key,
      detector: event.detector,
      family: event.family,
      bias: event.bias,
      confirmedAtIndex: event.confirmedAtIndex,
      confirmedAt: event.confirmedAt,
      confirmedTime: event.confirmedTime,
      startIndex: event.startIndex,
      level: event.level ?? null,
      anchors: event.anchors,
    })),
    rawEvents: series.raw.events.map((event) => ({
      key: event.key,
      detector: event.detector,
      family: event.family,
      bias: event.bias,
      confirmedAtIndex: event.confirmedAtIndex,
      confirmedAt: event.confirmedAt,
      confirmedTime: event.confirmedTime,
      startIndex: event.startIndex,
      level: event.level ?? null,
      anchors: event.anchors,
    })),
    provisional: series.adjusted.provisional,
    salience: {
      groups: series.salience.groups,
      order: series.salience.order,
      rules: series.salience.rules,
      repeatedGroups: series.salience.repeatedGroups,
      multiEventGroups: series.salience.multiEventGroups,
    },
  };
}

interface Finalized {
  detectorStats: unknown[];
  liquidityStats: unknown[];
  periodStats: unknown[];
  rawVsAdjusted: unknown[];
  cooccurrence: unknown;
  salience: unknown;
  forward: unknown;
  series: SeriesSummary[];
  errors: ErrorRow[];
}

describe('CandleEdge real-market validation run', () => {
  it.skipIf(!NDJSON || !OUT)(
    'collects the real ledger and per-detector statistics',
    () => {
      if (!NDJSON || !OUT) throw new Error('missing CANDLEEDGE_NDJSON / CANDLEEDGE_OUT');
      mkdirSync(OUT, { recursive: true });
      const runStarted = Date.now();
      const memStart = process.memoryUsage();
      let peakRss = memStart.rss;

      const allRecords = readFileSync(NDJSON, 'utf8')
        .split('\n')
        .filter(Boolean)
        .map((line) => JSON.parse(line) as RealMarketRecord)
        .sort((a, b) => a.symbol.localeCompare(b.symbol));
      const records = LIMIT > 0 ? allRecords.slice(0, LIMIT) : allRecords;
      const viewerSymbols = new Set(chooseViewerSymbols(records));
      const viewer = new Map<string, Record<string, unknown>>();
      const recordBySymbol = new Map(records.map((r) => [r.symbol, r]));

      const stats = new ResearchStats();
      const market = new Map<string, { sum: number; count: number }>();
      const ledgerPath = join(OUT, 'ledger.ndjson');
      const ledgerFd = openSync(ledgerPath, 'w');
      let ledgerBuffer: string[] = [];
      const flushLedger = () => {
        if (ledgerBuffer.length === 0) return;
        writeSync(ledgerFd, `${ledgerBuffer.join('\n')}\n`);
        ledgerBuffer = [];
      };

      let collectorErrors = 0;
      let hashMismatches = 0;
      let seriesCount = 0;
      let adjustedEvents = 0;
      let rawEvents = 0;
      let monthlyFull = 0;
      let monthlyEligible = 0;
      let monthlyStructureEvents = 0;
      let weeklyEligible = 0;
      let dailyEligible = 0;
      const coverageByAdjustment = {
        combinedTrue: { series: 0, adjustedEvents: 0, rawEvents: 0 },
        combinedFalse: { series: 0, adjustedEvents: 0, rawEvents: 0 },
        unknown: { series: 0, adjustedEvents: 0, rawEvents: 0 },
      };
      const recordManifest: Array<Record<string, unknown>> = [];

      try {
        records.forEach((record, recordIndex) => {
          const hashVerified = record.status === 'success' ? verifyInputSha256(record) : false;
          if (record.status === 'success' && !hashVerified) hashMismatches += 1;
          recordManifest.push({
            symbol: record.symbol,
            stratum: record.universe?.stratum ?? null,
            inputSha256: record.inputSha256 ?? null,
            recomputedMatch: hashVerified,
            candleCount: record.candleCount ?? 0,
            factorCount: record.factorCount ?? 0,
            adjustSource: record.adjustSource ?? null,
            combinedAvailable: record.adjustCapability?.combined_available ?? null,
            adjustEvents: record.adjustEvents?.length ?? 0,
            adjustRejected: record.adjustRejected?.length ?? 0,
            liquidityBand: record.universe?.liquidityBand ?? null,
            historyBand: record.universe?.historyBand ?? null,
            collectorRuntimeMs: record.runtimeMs ?? null,
          });
          if (record.status !== 'success') {
            collectorErrors += 1;
            stats.addRecordError(record.symbol, record.error ?? 'collector status error');
            return;
          }
          if (record.universe.stratum === 'full') {
            monthlyFull += 1;
          }
          for (const timeframe of TIMEFRAMES) {
            const series = scanRecord(record, timeframe, hashVerified);
            seriesCount += 1;
            adjustedEvents += series.adjusted.events.length;
            rawEvents += series.raw.events.length;
            addMarketBaseline(market, timeframe, series.adjustedBars);
            const forward = evaluateForward({
              seriesKey: series.seriesKey,
              bars: barsForForward(series.adjustedBars),
              events: series.adjusted.events.map((event) => ({
                key: event.key,
                detector: event.detector,
                bias: event.bias,
                confirmedAtIndex: event.confirmedAtIndex,
                confirmedAt: event.confirmedTime,
              })),
              cutoffMs: EVAL_CUTOFF_MS,
            });
            stats.addSeries(series, forward);
            for (const event of series.adjusted.events) {
              ledgerBuffer.push(
                JSON.stringify({
                  s: series.symbol, tf: timeframe, m: 'adj', ...compactEvent(event),
                }),
              );
            }
            if (viewerSymbols.has(series.symbol)) {
              for (const event of series.raw.events) {
                ledgerBuffer.push(
                  JSON.stringify({
                    s: series.symbol, tf: timeframe, m: 'raw', ...compactEvent(event),
                  }),
                );
              }
              const current = viewer.get(series.symbol) ?? {};
              current[timeframe] = viewerSeries(series);
              viewer.set(series.symbol, current);
            }
            const key =
              series.combinedAvailable === true ? 'combinedTrue'
                : series.combinedAvailable === false ? 'combinedFalse' : 'unknown';
            coverageByAdjustment[key].series += 1;
            coverageByAdjustment[key].adjustedEvents += series.adjusted.events.length;
            coverageByAdjustment[key].rawEvents += series.raw.events.length;
            if (timeframe === 'M') {
              if (series.stratum === 'full' && series.candleCount > 41) monthlyEligible += 1;
              if (series.stratum === 'full') {
                monthlyStructureEvents += series.adjusted.events.filter((e) =>
                  STRUCTURE.has(e.detector),
                ).length;
              }
            }
            if (timeframe === 'W' && series.stratum === 'full' && series.candleCount > 41) {
              weeklyEligible += 1;
            }
            if (timeframe === 'D' && series.stratum === 'full' && series.candleCount > 41) {
              dailyEligible += 1;
            }
          }
          if (ledgerBuffer.length >= 2_000) flushLedger();
          if (recordIndex % 50 === 0) {
            const rss = process.memoryUsage().rss;
            peakRss = Math.max(peakRss, rss);
            console.log(
              `[candleedge-real] ${recordIndex + 1}/${records.length} ` +
                `series=${seriesCount} adjustedEvents=${adjustedEvents} rss=${Math.round(rss / 1e6)}MB`,
            );
          }
        });
      } finally {
        flushLedger();
        closeSync(ledgerFd);
      }

      const finalized = stats.finalize(market) as unknown as Finalized;
      const salienceRules = buildSalience('meta', [], 0).rules;
      const fullRecords = records.filter((r) => r.universe?.stratum === 'full');
      const shortRecords = records.filter((r) => r.universe?.stratum === 'short');
      const sources: Record<string, number> = {};
      const combined: Record<string, number> = {};
      let factorChangedSymbols = 0;
      let factorCompleteSymbols = 0;
      let factorAllOneSymbols = 0;
      let liveInjected = 0;
      let appliedEvents = 0;
      let rejectedEvents = 0;
      let dbRowsTotal = 0;
      let dbNoTradeRowsTotal = 0;
      let dbInvalidRowsTotal = 0;
      const liquidityBands: Record<string, number> = {};
      const historyBands: Record<string, number> = {};
      const sectors: Record<string, number> = {};
      for (const record of records) {
        const source = record.adjustSource ?? 'unknown';
        sources[source] = (sources[source] ?? 0) + 1;
        const key = String(record.adjustCapability?.combined_available);
        combined[key] = (combined[key] ?? 0) + 1;
        const factors = record.factors ?? [];
        const factorOnes = factors.filter((f) => Math.abs(f.factor - 1) < 1e-12).length;
        if ((record.factorCount ?? 0) > 0 && factors.length === (record.candleCount ?? 0)) {
          factorCompleteSymbols += 1;
        }
        if (factors.length > 0 && factorOnes === factors.length) factorAllOneSymbols += 1;
        if ((record.factorCount ?? 0) > 0 && factorOnes < factors.length) {
          factorChangedSymbols += 1;
        }
        if (record.liveInjected) liveInjected += 1;
        appliedEvents += record.adjustEvents?.length ?? 0;
        rejectedEvents += record.adjustRejected?.length ?? 0;
        dbRowsTotal += record.dbRows ?? 0;
        dbNoTradeRowsTotal += record.dbNoTradeRows ?? 0;
        dbInvalidRowsTotal += record.dbInvalidRows ?? 0;
        const band = record.universe?.liquidityBand ?? 'unknown';
        liquidityBands[band] = (liquidityBands[band] ?? 0) + 1;
        const history = record.universe?.historyBand ?? 'unknown';
        historyBands[history] = (historyBands[history] ?? 0) + 1;
        if (record.universe?.stratum === 'full') {
          const sector = record.universe.sector ?? 'unknown';
          sectors[sector] = (sectors[sector] ?? 0) + 1;
        }
      }
      const collectorMs = records
        .map((r) => r.runtimeMs ?? 0)
        .filter((v) => v > 0)
        .sort((a, b) => a - b);
      const p95 = collectorMs.length
        ? collectorMs[Math.min(collectorMs.length - 1, Math.floor(collectorMs.length * 0.95))]
        : null;
      const scanMs = finalized.series.reduce(
        (acc, s) => acc + s.runtimeMs.build + s.runtimeMs.adjustedScan + s.runtimeMs.rawScan,
        0,
      );
      const memEnd = process.memoryUsage();
      const generatedAt = new Date().toISOString();
      const collectorSummaryPath = `${NDJSON}.summary.json`;
      const collectorSummary = existsSync(collectorSummaryPath)
        ? JSON.parse(readFileSync(collectorSummaryPath, 'utf8'))
        : null;
      const meta = {
        generatedAt,
        baseSha: process.env.CANDLEEDGE_BASE_SHA ?? null,
        source: CANDLEEDGE_SOURCE,
        collector: 'api.chart.get_chart_db on a read-only SQLite copy',
        ndjson: NDJSON,
        ndjsonSha256: sha256File(NDJSON),
        records: records.length,
        allRecordsInFile: allRecords.length,
        series: seriesCount,
        timeframes: TIMEFRAMES,
        events: { adjusted: adjustedEvents, raw: rawEvents },
        universe: {
          fullSymbols: fullRecords.length,
          shortSymbols: shortRecords.length,
          fullDateRange: [
            fullRecords.map((r) => r.firstDate ?? '').filter(Boolean).sort()[0] ?? null,
            fullRecords.map((r) => r.lastDate ?? '').filter(Boolean).sort().at(-1) ?? null,
          ],
          dailyCandles: records.reduce((acc, r) => acc + (r.candleCount ?? 0), 0),
          liquidityBands,
          historyBands,
          topSectors: Object.entries(sectors)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 15)
            .map(([sector, count]) => ({ sector, count })),
        },
        collectorSummary,
        adjustment: {
          sources,
          combinedAvailable: combined,
          factorChangedSymbols,
          factorCompleteSymbols,
          factorAllOneSymbols,
          appliedEvents,
          rejectedEvents,
          liveInjected,
          coverageByAdjustment,
          dbRowsTotal,
          dbNoTradeRowsTotal,
          dbInvalidRowsTotal,
          contractDroppedRows: dbRowsTotal - records.reduce(
            (acc, r) => acc + (r.candleCount ?? 0), 0,
          ),
        },
        coverage: {
          dailyFullSeriesWithStructureWindow: dailyEligible,
          weeklyFullSeriesWithStructureWindow: weeklyEligible,
          monthlyFullSeries: monthlyFull,
          monthlyFullSeriesWithStructureWindow: monthlyEligible,
          monthlyStructureEvents,
          monthlyStructureStatus:
            monthlyEligible > 0 ? 'MEASURED' : 'INSUFFICIENT_HISTORY',
          monthlyStructureNote:
            'ساختار/سوئیپ در اسکنر از ایندکس ۴۱ به بعد ارزیابی می‌شود؛ سری ماهانهٔ این بانک حدود ۲۶ کندل است.',
          shortHistorySymbols: shortRecords.length,
        },
        hash: {
          definition:
            'sha256 of C|date|o6|h6|l6|c6|intVolume lines plus F marker and F|date|factor6 lines',
          mismatches: hashMismatches,
          verified: hashMismatches === 0,
        },
        runtimeMs: {
          collectorTotal: round(collectorMs.reduce((a, b) => a + b, 0), 1),
          collectorMean: collectorMs.length
            ? round(collectorMs.reduce((a, b) => a + b, 0) / collectorMs.length, 1)
            : null,
          collectorP95: p95 === null ? null : round(p95, 1),
          scanAndBuildTotal: round(scanMs, 1),
          wallTotal: Date.now() - runStarted,
        },
        memoryBytes: {
          startRss: memStart.rss,
          peakRss,
          endRss: memEnd.rss,
          endHeapUsed: memEnd.heapUsed,
        },
        salience: {
          rules: salienceRules,
          methods: ['latest', 'structure_first', 'evidence_count'],
          note: 'روش‌ها فقط ترتیب نمایش‌اند؛ هیچ‌کدام احتمال یا اعتبار تجاری نیست.',
        },
        forward: {
          horizons: [...FORWARD_HORIZONS],
          cutoffMs: EVAL_CUTOFF_MS,
          cutoff: dayOf(EVAL_CUTOFF_MS),
          entryRule: 'next-bar-open',
          exitRule: 'horizon-close',
          note: FORWARD_NOTE,
          discoveryEvaluationSplit: 'entry bar date < cutoff => discovery',
        },
        viewerSymbols: [...viewerSymbols],
        collectorErrors,
      };

      const statsPath = join(OUT, 'stats.json');
      writeFileSync(
        statsPath,
        JSON.stringify({ meta, ...finalized }, null, 2),
        'utf8',
      );
      const seriesPath = join(OUT, 'series.ndjson');
      writeFileSync(
        seriesPath,
        `${finalized.series.map((s) => JSON.stringify(s)).join('\n')}\n`,
        'utf8',
      );
      const manifestPath = join(OUT, 'record-manifest.ndjson');
      writeFileSync(
        manifestPath,
        `${recordManifest.map((r) => JSON.stringify(r)).join('\n')}\n`,
        'utf8',
      );
      const viewerPath = join(OUT, 'viewer-data.json');
      writeFileSync(
        viewerPath,
        JSON.stringify({
          meta: {
            generatedAt,
            horizons: [...FORWARD_HORIZONS],
            cutoff: dayOf(EVAL_CUTOFF_MS),
            salienceRules,
            disclaimer: FORWARD_NOTE,
            symbols: [...viewerSymbols],
          },
          symbols: [...viewer.entries()].map(([symbol, timeframes]) => ({
            symbol,
            sector: recordBySymbol.get(symbol)?.universe?.sector ?? null,
            liquidityBand: recordBySymbol.get(symbol)?.universe?.liquidityBand ?? null,
            historyBand: recordBySymbol.get(symbol)?.universe?.historyBand ?? null,
            adjustSource: recordBySymbol.get(symbol)?.adjustSource ?? null,
            combinedAvailable:
              recordBySymbol.get(symbol)?.adjustCapability?.combined_available ?? null,
            adjustEventCount: recordBySymbol.get(symbol)?.adjustEvents?.length ?? 0,
            timeframes,
          })),
        }),
        'utf8',
      );
      const outputs = [statsPath, seriesPath, manifestPath, viewerPath, ledgerPath].map((path) => ({
        path,
        bytes: statSync(path).size,
        sha256: sha256File(path),
      }));
      const finalManifest = {
        generatedAt,
        baseSha: process.env.CANDLEEDGE_BASE_SHA ?? null,
        ndjson: NDJSON,
        ndjsonSha256: sha256File(NDJSON),
        records: records.length,
        series: seriesCount,
        hashMismatches,
        collectorErrors,
        elapsedMs: Date.now() - runStarted,
        node: process.version,
        platform: process.platform,
        outputs,
      };
      writeFileSync(join(OUT, 'manifest.json'), JSON.stringify(finalManifest, null, 2), 'utf8');
      console.log(
        `[candleedge-real] DONE records=${records.length} series=${seriesCount} ` +
          `events=${adjustedEvents} hashMismatch=${hashMismatches} ` +
          `elapsed=${round((Date.now() - runStarted) / 1000, 1)}s ` +
          `peakRss=${round(peakRss / 1e6, 1)}MB`,
      );

      expect(existsSync(statsPath)).toBe(true);
      expect(finalized.series.length).toBe(seriesCount);
      expect(hashMismatches).toBe(0);
      expect(collectorErrors).toBe(0);
    },
    60 * 60 * 1000,
  );
});
