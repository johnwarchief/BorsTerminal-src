import type { DetectorId } from '../types';
import type { ForwardResult } from './forwardEval';
import {
  FORWARD_HORIZONS,
  FORWARD_NOTE,
  clusterBootstrapMeanCI,
  summarizeReturns,
} from './forwardEval';
import type { SeriesScan } from './realMarketTypes';
import type { ForwardOutcome } from './types';

export const ALL_DETECTORS: DetectorId[] = [
  'doji',
  'bullish_engulfing',
  'bearish_engulfing',
  'hammer',
  'shooting_star',
  'double_top',
  'double_bottom',
  'ascending_triangle',
  'descending_triangle',
  'symmetrical_triangle',
  'rising_wedge',
  'falling_wedge',
  'higher_high',
  'higher_low',
  'lower_high',
  'lower_low',
  'bos_bullish',
  'bos_bearish',
  'liquidity_sweep_high',
  'liquidity_sweep_low',
];

const STRUCTURE_DETECTORS = new Set<string>([
  'double_top', 'double_bottom',
  'ascending_triangle', 'descending_triangle', 'symmetrical_triangle',
  'rising_wedge', 'falling_wedge',
  'higher_high', 'higher_low', 'lower_high', 'lower_low',
  'bos_bullish', 'bos_bearish',
  'liquidity_sweep_high', 'liquidity_sweep_low',
]);

/** First timeframe bar index on which a detector can fire. */
export function detectorStartIndex(detector: string): number {
  if (STRUCTURE_DETECTORS.has(detector)) return 41;
  if (detector === 'hammer' || detector === 'shooting_star') return 21;
  if (detector === 'bullish_engulfing' || detector === 'bearish_engulfing') return 1;
  return 0;
}

export function detectorEligibleBars(detector: string, candleCount: number): number {
  return Math.max(0, candleCount - detectorStartIndex(detector));
}

export type MarketBaselineMap = Map<string, { sum: number; count: number }>;

interface DetectorAgg {
  mode: string;
  timeframe: string;
  stratum: string;
  detector: string;
  candles: number;
  eligibleBars: number;
  seriesCount: number;
  seriesWithEvents: number;
  eventCount: number;
  maxPerSeries: number;
  repeatedGroups: number;
  errorSeries: number;
  symbols: Array<{ symbol: string; count: number }>;
}

interface LiquidityAgg {
  mode: string;
  timeframe: string;
  stratum: string;
  band: string;
  detector: string;
  candles: number;
  eligibleBars: number;
  seriesCount: number;
  eventCount: number;
}

interface PeriodAgg {
  mode: string;
  timeframe: string;
  stratum: string;
  year: string;
  detector: string;
  eventCount: number;
}

interface RawAdjAgg {
  timeframe: string;
  stratum: string;
  detector: string;
  rawCount: number;
  adjustedCount: number;
  both: number;
  rawOnly: number;
  adjustedOnly: number;
  comparedSeries: number;
  rawUnavailable: number;
  adjustedUnavailable: number;
}

interface ForwardAgg {
  timeframe: string;
  stratum: string;
  detector: string;
  horizon: number;
  period: string;
  returns: number[];
  symbols: string[];
  entryTimes: number[];
  baselineLocal: number[];
  rightCensored: number;
}

interface CapabilityAgg {
  capability: string;
  timeframe: string;
  stratum: string;
  detector: string;
  candles: number;
  eligibleBars: number;
  seriesCount: number;
  seriesWithEvents: number;
  eventCount: number;
}

export interface SeriesSummary {
  symbol: string;
  timeframe: string;
  stratum: string;
  candleCount: number;
  adjustedEvents: number;
  rawEvents: number;
  adjustedError: string | null;
  rawError: string | null;
  hashVerified: boolean;
  adjustSource: string | null;
  combinedAvailable: boolean | null;
  factorCount: number;
  factorOneCount: number;
  adjustEventCount: number;
  adjustRejectedCount: number;
  liquidityBand: string;
  historyBand: string;
  runtimeMs: SeriesScan['runtimeMs'];
}

export interface ErrorRow {
  symbol: string;
  timeframe: string | null;
  stage: string;
  message: string;
}

function bump<T>(map: Map<string, T>, key: string, init: () => T): T {
  const found = map.get(key);
  if (found) return found;
  const created = init();
  map.set(key, created);
  return created;
}

function rate(count: number, denominator: number): number | null {
  return denominator > 0 ? (count / denominator) * 1000 : null;
}

function anchorSignature(event: { detector: string; anchors: Array<{ index: number }> }): string {
  return `${event.detector}|${event.anchors.map((a) => a.index).sort((a, b) => a - b).join(',')}`;
}

function jaccard(a: Set<string>, b: Set<string>): number {
  const union = new Set([...a, ...b]);
  if (union.size === 0) return 1;
  let intersection = 0;
  for (const value of a) if (b.has(value)) intersection += 1;
  return intersection / union.size;
}

export class ResearchStats {
  private detector = new Map<string, DetectorAgg>();
  private liquidity = new Map<string, LiquidityAgg>();
  private period = new Map<string, PeriodAgg>();
  private periodBars = new Map<string, number>();
  private rawAdj = new Map<string, RawAdjAgg>();
  private capability = new Map<string, CapabilityAgg>();
  private cooc = new Map<string, number>();
  private coocBarsWithMultiple = 0;
  private coocEventsInMultiple = 0;
  private forwardAgg = new Map<string, ForwardAgg>();
  private seriesSummaries: SeriesSummary[] = [];
  private errors: ErrorRow[] = [];

  private salience = {
    seriesWithGroups: 0,
    seriesWithMultipleGroups: 0,
    groups: 0,
    singletonGroups: 0,
    multiEventGroups: 0,
    repeatedGroups: 0,
    groupSize: { one: 0, two: 0, three: 0, fourPlus: 0 },
    methodSeries: 0,
    top1Same: {
      latest_structure_first: 0,
      latest_evidence_count: 0,
      structure_first_evidence_count: 0,
    },
    top3Jaccard: {
      latest_structure_first: 0,
      latest_evidence_count: 0,
      structure_first_evidence_count: 0,
    },
  };

  addSeries(series: SeriesScan, forward: ForwardResult | null): void {
    const tf = series.timeframe;
    const stratum = series.stratum;
    const n = series.candleCount;
    for (const mode of ['adjusted', 'raw'] as const) {
      const events = mode === 'adjusted' ? series.adjusted.events : series.raw.events;
      const error = mode === 'adjusted' ? series.adjusted.error : series.raw.error;
      const byDetector = new Map<string, number>();
      for (const event of events) {
        byDetector.set(event.detector, (byDetector.get(event.detector) ?? 0) + 1);
      }
      for (const detector of ALL_DETECTORS) {
        const count = byDetector.get(detector) ?? 0;
        const eligible = detectorEligibleBars(detector, n);
        const key = `${mode}|${tf}|${stratum}|${detector}`;
        const agg = bump(this.detector, key, () => ({
          mode, timeframe: tf, stratum, detector,
          candles: 0, eligibleBars: 0, seriesCount: 0, seriesWithEvents: 0,
          eventCount: 0, maxPerSeries: 0, repeatedGroups: 0, errorSeries: 0,
          symbols: [],
        }));
        agg.candles += n;
        agg.eligibleBars += eligible;
        agg.seriesCount += 1;
        agg.eventCount += count;
        agg.maxPerSeries = Math.max(agg.maxPerSeries, count);
        if (count > 0) {
          agg.seriesWithEvents += 1;
          agg.symbols.push({ symbol: series.symbol, count });
        }
        if (error) agg.errorSeries += 1;

        const liqKey = `${mode}|${tf}|${stratum}|${series.liquidityBand}|${detector}`;
        const liq = bump(this.liquidity, liqKey, () => ({
          mode, timeframe: tf, stratum, band: series.liquidityBand, detector,
          candles: 0, eligibleBars: 0, seriesCount: 0, eventCount: 0,
        }));
        liq.candles += n;
        liq.eligibleBars += eligible;
        liq.seriesCount += 1;
        liq.eventCount += count;

        if (mode === 'adjusted') {
          const capability =
            series.combinedAvailable === true ? 'combined-true'
              : series.combinedAvailable === false ? 'combined-false' : 'unknown';
          const capKey = `${capability}|${tf}|${stratum}|${detector}`;
          const cap = bump(this.capability, capKey, () => ({
            capability, timeframe: tf, stratum, detector,
            candles: 0, eligibleBars: 0, seriesCount: 0, seriesWithEvents: 0, eventCount: 0,
          }));
          cap.candles += n;
          cap.eligibleBars += eligible;
          cap.seriesCount += 1;
          cap.eventCount += count;
          if (count > 0) cap.seriesWithEvents += 1;
        }
      }

      const signatures = new Map<string, number>();
      for (const event of events) {
        signatures.set(anchorSignature(event), (signatures.get(anchorSignature(event)) ?? 0) + 1);
      }
      for (const detector of ALL_DETECTORS) {
        const agg = this.detector.get(`${mode}|${tf}|${stratum}|${detector}`);
        if (agg) {
          const detectorRepeats = [...signatures.entries()].filter(
            ([signature, count]) => count > 1 && signature.startsWith(`${detector}|`),
          ).length;
          agg.repeatedGroups += detectorRepeats;
        }
      }
    }

    // One denominator pass per timeframe series, independent of scan mode.
    const startIndexes = new Map<string, number>();
    for (const detector of ALL_DETECTORS) startIndexes.set(detector, detectorStartIndex(detector));
    for (let i = 0; i < series.barYears.length; i += 1) {
      const year = series.barYears[i];
      for (const detector of ALL_DETECTORS) {
        if (i >= (startIndexes.get(detector) ?? 0)) {
          const key = `${tf}|${stratum}|${year}|${detector}`;
          this.periodBars.set(key, (this.periodBars.get(key) ?? 0) + 1);
        }
      }
    }

    for (const mode of ['adjusted', 'raw'] as const) {
      const events = mode === 'adjusted' ? series.adjusted.events : series.raw.events;
      for (const event of events) {
        const year = event.confirmedAt.slice(0, 4);
        const key = `${mode}|${tf}|${stratum}|${year}|${event.detector}`;
        const agg = bump(this.period, key, () => ({
          mode, timeframe: tf, stratum, year, detector: event.detector, eventCount: 0,
        }));
        agg.eventCount += 1;
      }
    }

    const rawKeys = new Set(
      series.raw.events.map((e) => `${e.detector}|${e.confirmedAtIndex}|${e.bias}`),
    );
    const adjustedKeys = new Set(
      series.adjusted.events.map((e) => `${e.detector}|${e.confirmedAtIndex}|${e.bias}`),
    );
    for (const detector of ALL_DETECTORS) {
      const key = `${tf}|${stratum}|${detector}`;
      const agg = bump(this.rawAdj, key, () => ({
        timeframe: tf, stratum, detector,
        rawCount: 0, adjustedCount: 0, both: 0, rawOnly: 0, adjustedOnly: 0,
        comparedSeries: 0, rawUnavailable: 0, adjustedUnavailable: 0,
      }));
      const rawFor = series.raw.events.filter((e) => e.detector === detector);
      const adjustedFor = series.adjusted.events.filter((e) => e.detector === detector);
      agg.rawCount += rawFor.length;
      agg.adjustedCount += adjustedFor.length;
      if (series.raw.error) agg.rawUnavailable += 1;
      else if (series.adjusted.error) agg.adjustedUnavailable += 1;
      else {
        agg.comparedSeries += 1;
        for (const e of adjustedFor) {
          if (rawKeys.has(`${e.detector}|${e.confirmedAtIndex}|${e.bias}`)) agg.both += 1;
          else agg.adjustedOnly += 1;
        }
        for (const e of rawFor) {
          if (!adjustedKeys.has(`${e.detector}|${e.confirmedAtIndex}|${e.bias}`)) agg.rawOnly += 1;
        }
      }
    }

    const byBar = new Map<number, string[]>();
    for (const event of series.adjusted.events) {
      const bucket = byBar.get(event.confirmedAtIndex);
      if (bucket) bucket.push(event.detector);
      else byBar.set(event.confirmedAtIndex, [event.detector]);
    }
    for (const detectors of byBar.values()) {
      const unique = [...new Set(detectors)];
      if (unique.length < 2) continue;
      this.coocBarsWithMultiple += 1;
      this.coocEventsInMultiple += detectors.length;
      for (let i = 0; i < unique.length; i += 1) {
        for (let j = i + 1; j < unique.length; j += 1) {
          const key = `${tf}|${[unique[i], unique[j]].sort().join('|')}`;
          this.cooc.set(key, (this.cooc.get(key) ?? 0) + 1);
        }
      }
    }

    const sal = series.salience;
    if (sal.groups.length > 0) {
      this.salience.seriesWithGroups += 1;
      this.salience.groups += sal.groups.length;
      this.salience.multiEventGroups += sal.multiEventGroups;
      this.salience.repeatedGroups += sal.repeatedGroups;
      for (const group of sal.groups) {
        if (group.eventKeys.length === 1) this.salience.singletonGroups += 1;
        const size = group.eventKeys.length;
        if (size === 1) this.salience.groupSize.one += 1;
        else if (size === 2) this.salience.groupSize.two += 1;
        else if (size === 3) this.salience.groupSize.three += 1;
        else this.salience.groupSize.fourPlus += 1;
      }
      const methods = {
        latest: sal.order.latest,
        structure_first: sal.order.structure_first,
        evidence_count: sal.order.evidence_count,
      };
      const compare = (a: string, b: string) => {
        if (!methods[a as keyof typeof methods]?.length || !methods[b as keyof typeof methods]?.length) {
          return null;
        }
        const top1Same = methods[a as keyof typeof methods][0] === methods[b as keyof typeof methods][0];
        const topA = new Set(methods[a as keyof typeof methods].slice(0, 3));
        const topB = new Set(methods[b as keyof typeof methods].slice(0, 3));
        return { top1Same, jaccard: jaccard(topA, topB) };
      };
      if (sal.groups.length > 1) {
        const pairs: Array<[string, string, 'latest_structure_first' | 'latest_evidence_count' | 'structure_first_evidence_count']> = [
          ['latest', 'structure_first', 'latest_structure_first'],
          ['latest', 'evidence_count', 'latest_evidence_count'],
          ['structure_first', 'evidence_count', 'structure_first_evidence_count'],
        ];
        this.salience.seriesWithMultipleGroups += 1;
        this.salience.methodSeries += 1;
        for (const [a, b, key] of pairs) {
          const value = compare(a, b);
          if (!value) continue;
          if (value.top1Same) this.salience.top1Same[key] += 1;
          this.salience.top3Jaccard[key] += value.jaccard;
        }
      }
    }

    if (forward) {
      for (const outcome of forward.outcomes) {
        this.addForwardOutcome(tf, stratum, outcome);
      }
      for (const row of forward.rows) {
        if (row.rightCensored === 0) continue;
        const key = `${tf}|${stratum}|${row.detector}|${row.horizon}|${row.period}`;
        const agg = bump(this.forwardAgg, key, () => ({
          timeframe: tf, stratum, detector: row.detector, horizon: row.horizon,
          period: row.period, returns: [], symbols: [], entryTimes: [], baselineLocal: [],
          rightCensored: 0,
        }));
        agg.rightCensored += row.rightCensored;
      }
    }

    if (series.adjusted.error) {
      this.errors.push({
        symbol: series.symbol, timeframe: tf, stage: 'adjusted-scan',
        message: series.adjusted.error,
      });
    }
    if (series.raw.error) {
      this.errors.push({
        symbol: series.symbol, timeframe: tf, stage: 'raw-scan',
        message: series.raw.error,
      });
    }
    if (!series.hashVerified) {
      this.errors.push({
        symbol: series.symbol, timeframe: tf, stage: 'input-hash',
        message: 'recomputed SHA-256 does not match the collector digest',
      });
    }

    this.seriesSummaries.push({
      symbol: series.symbol,
      timeframe: tf,
      stratum,
      candleCount: n,
      adjustedEvents: series.adjusted.events.length,
      rawEvents: series.raw.events.length,
      adjustedError: series.adjusted.error ?? null,
      rawError: series.raw.error ?? null,
      hashVerified: series.hashVerified,
      adjustSource: series.adjustSource,
      combinedAvailable: series.combinedAvailable,
      factorCount: series.factorCount,
      factorOneCount: series.factorOneCount,
      adjustEventCount: series.adjustEventCount,
      adjustRejectedCount: series.adjustRejectedCount,
      liquidityBand: series.liquidityBand,
      historyBand: series.historyBand,
      runtimeMs: series.runtimeMs,
    });
  }

  private addForwardOutcome(
    timeframe: string,
    stratum: string,
    outcome: ForwardOutcome,
  ): void {
    const key = `${timeframe}|${stratum}|${outcome.detector}|${outcome.horizon}|${outcome.period}`;
    const agg = bump(this.forwardAgg, key, () => ({
      timeframe, stratum, detector: outcome.detector, horizon: outcome.horizon,
      period: outcome.period, returns: [], symbols: [], entryTimes: [], baselineLocal: [],
      rightCensored: 0,
    }));
    agg.returns.push(outcome.returnPct);
    agg.symbols.push(outcome.symbol);
    agg.entryTimes.push(outcome.entryTime);
    if (outcome.baselineLocal !== null) agg.baselineLocal.push(outcome.baselineLocal);
  }

  addRecordError(symbol: string, message: string): void {
    this.errors.push({ symbol, timeframe: null, stage: 'collector', message });
  }

  finalize(market: MarketBaselineMap): Record<string, unknown> {
    const detectorStats = [...this.detector.values()].map((agg) => ({
      ...agg,
      eventsPer1000Candles: rate(agg.eventCount, agg.candles),
      eventsPer1000EligibleBars: rate(agg.eventCount, agg.eligibleBars),
      meanPerSeries: agg.seriesCount ? agg.eventCount / agg.seriesCount : null,
      topSymbols: [...agg.symbols].sort((a, b) => b.count - a.count || a.symbol.localeCompare(b.symbol)).slice(0, 5),
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    })).map(({ symbols: _symbols, ...rest }) => rest);

    const detectorStatsByAdjustment = [...this.capability.values()].map((agg) => ({
      ...agg,
      eventsPer1000Candles: rate(agg.eventCount, agg.candles),
      eventsPer1000EligibleBars: rate(agg.eventCount, agg.eligibleBars),
    }));

    const liquidityStats = [...this.liquidity.values()].map((agg) => ({
      ...agg,
      eventsPer1000Candles: rate(agg.eventCount, agg.candles),
      eventsPer1000EligibleBars: rate(agg.eventCount, agg.eligibleBars),
    }));

    const periodStats = [...this.period.values()].map((agg) => {
      const bars = this.periodBars.get(
        `${agg.timeframe}|${agg.stratum}|${agg.year}|${agg.detector}`,
      ) ?? 0;
      return { ...agg, eligibleBars: bars, eventsPer1000EligibleBars: rate(agg.eventCount, bars) };
    });

    const rawVsAdjusted = [...this.rawAdj.values()].map((agg) => ({
      ...agg,
      adjustedMinusRaw: agg.adjustedCount - agg.rawCount,
      matchRate: agg.adjustedCount
        ? agg.both / Math.max(agg.adjustedCount, agg.rawCount)
        : null,
    }));

    const pairs = [...this.cooc.entries()]
      .map(([key, count]) => {
        const [timeframe, a, b] = key.split('|');
        return { timeframe, a, b, count };
      })
      .sort((a, b) => b.count - a.count || a.a.localeCompare(b.a) || a.b.localeCompare(b.b));

    const salience = {
      ...this.salience,
      top3Jaccard: Object.fromEntries(
        Object.entries(this.salience.top3Jaccard).map(([k, v]) => [
          k,
          this.salience.methodSeries ? v / this.salience.methodSeries : null,
        ]),
      ),
      methodAgreementTop1: Object.fromEntries(
        Object.entries(this.salience.top1Same).map(([k, v]) => [
          k,
          this.salience.methodSeries ? v / this.salience.methodSeries : null,
        ]),
      ),
      note:
        'گروه‌بندی فقط با لنگر مشترک است؛ سه روش فقط ترتیب نمایش‌اند و امتیاز احتمال نیستند.',
    };
    const { top1Same: _top1Same, ...salienceRest } = salience;
    void _top1Same;

    const forwardRows = [...this.forwardAgg.values()].map((agg) => {
      const summary = summarizeReturns(agg.returns, `${agg.timeframe}|${agg.detector}|${agg.horizon}|${agg.period}`);
      const markets: number[] = [];
      for (const entryTime of agg.entryTimes) {
        const value = market.get(`${agg.timeframe}|${entryTime}|${agg.horizon}`);
        if (value && value.count > 0) markets.push(value.sum / value.count);
      }
      const marketMean = markets.length
        ? markets.reduce((a, b) => a + b, 0) / markets.length
        : null;
      const localMean = agg.baselineLocal.length
        ? agg.baselineLocal.reduce((a, b) => a + b, 0) / agg.baselineLocal.length
        : null;
      const bySymbol = new Map<string, number[]>();
      agg.returns.forEach((value, index) => {
        const symbol = agg.symbols[index] ?? 'unknown';
        const bucket = bySymbol.get(symbol);
        if (bucket) bucket.push(value);
        else bySymbol.set(symbol, [value]);
      });
      const clusterKey = `${agg.timeframe}|${agg.detector}|${agg.horizon}|${agg.period}`;
      return {
        timeframe: agg.timeframe,
        stratum: agg.stratum,
        detector: agg.detector,
        horizon: agg.horizon,
        period: agg.period,
        n: summary.n,
        nSymbols: bySymbol.size,
        rightCensored: agg.rightCensored,
        mean: summary.mean,
        median: summary.median,
        q05: summary.q05,
        q25: summary.q25,
        q50: summary.q50,
        q75: summary.q75,
        q95: summary.q95,
        sd: summary.sd,
        winRate: summary.winRate,
        winRateCI: summary.winRateCI,
        meanCI: summary.meanCI,
        meanCICluster: clusterBootstrapMeanCI([...bySymbol.values()], clusterKey),
        clusterUnit: 'symbol',
        baselineLocalMean: localMean,
        baselineLocalN: agg.baselineLocal.length,
        baselineMarketMean: marketMean,
        marketBaselineN: markets.length,
        deltaLocal: summary.mean === null || localMean === null ? null : summary.mean - localMean,
        deltaMarket: summary.mean === null || marketMean === null ? null : summary.mean - marketMean,
        lowSample: summary.lowSample,
        entryRule: 'next-bar-open',
        exitRule: 'horizon-close',
        overlapNote:
          'رویدادهای یک نماد می‌توانند همپوشانی زمانی داشته باشند؛ بازهٔ اطمینانِ خوشه‌ای بر پایهٔ نماد است.',
        note: FORWARD_NOTE,
      };
    }).sort(
      (a, b) =>
        a.timeframe.localeCompare(b.timeframe) ||
        a.stratum.localeCompare(b.stratum) ||
        a.detector.localeCompare(b.detector) ||
        a.horizon - b.horizon ||
        a.period.localeCompare(b.period),
    );

    return {
      detectorStats,
      detectorStatsByAdjustment,
      liquidityStats,
      periodStats,
      rawVsAdjusted,
      cooccurrence: {
        pairs: pairs.slice(0, 100),
        pairCount: pairs.length,
        barsWithMultipleDetectors: this.coocBarsWithMultiple,
        eventsInMultipleDetectorBars: this.coocEventsInMultiple,
      },
      salience: salienceRest,
      forward: {
        horizons: [...FORWARD_HORIZONS],
        rows: forwardRows,
        note: FORWARD_NOTE,
      },
      series: this.seriesSummaries.sort(
        (a, b) => a.symbol.localeCompare(b.symbol) || a.timeframe.localeCompare(b.timeframe),
      ),
      errors: this.errors,
    };
  }
}
