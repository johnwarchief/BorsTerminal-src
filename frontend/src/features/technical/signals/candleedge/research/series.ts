import type { KLineData } from 'klinecharts';
import { applyAdjustmentToCandles } from '@features/technical/nahayatnegar/lib/adjustments';
import { aggregateCandles } from '@features/technical/nahayatnegar/lib/timeframe';
import { scanPatterns } from '../scanner';
import type { Candle, PatternEvent } from '../types';
import { buildSalience } from './salience';
import type {
  ProvisionalSwingLite,
  RealMarketRecord,
  ResearchEvent,
  ResearchTimeframe,
  SeriesScan,
} from './realMarketTypes';

export function parseDayMs(day: string): number {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(day).slice(0, 10));
  if (!match) throw new Error(`invalid day: ${day}`);
  const ms = Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  if (!Number.isFinite(ms)) throw new Error(`invalid day: ${day}`);
  return ms;
}

export function dayOf(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

function nowMs(): number {
  return typeof performance !== 'undefined' ? performance.now() : Date.now();
}

function toCandle(bar: KLineData): Candle {
  return {
    time: bar.timestamp,
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    volume: bar.volume,
  };
}

export interface TimeframeBars {
  rawBars: Candle[];
  adjustedBars: Candle[];
  rawDailyCount: number;
  adjustedDailyCount: number;
  factorOneCount: number;
}

export function buildTimeframeBars(
  record: RealMarketRecord,
  timeframe: ResearchTimeframe,
): TimeframeBars {
  const rawCandles = record.rawCandles ?? [];
  if (!Array.isArray(rawCandles) || rawCandles.length === 0) {
    throw new Error('record has no raw candles');
  }
  const dailyRaw: KLineData[] = rawCandles.map((c) => ({
    timestamp: parseDayMs(c.time),
    open: Number(c.open),
    high: Number(c.high),
    low: Number(c.low),
    close: Number(c.close),
    volume: Number(c.volume ?? 0),
  }));
  const dailyAdjusted = applyAdjustmentToCandles(
    dailyRaw,
    (record.factors ?? []).map((f) => ({ time: f.time, factor: f.factor })),
    'combined',
  );
  const rawTf = timeframe === 'D' ? dailyRaw : aggregateCandles(dailyRaw, timeframe);
  const adjustedTf =
    timeframe === 'D' ? dailyAdjusted : aggregateCandles(dailyAdjusted, timeframe);
  return {
    rawBars: rawTf.map(toCandle),
    adjustedBars: adjustedTf.map(toCandle),
    rawDailyCount: dailyRaw.length,
    adjustedDailyCount: dailyAdjusted.length,
    factorOneCount: (record.factors ?? []).filter(
      (f) => Math.abs(Number(f.factor) - 1) < 1e-12,
    ).length,
  };
}

export function toResearchEvent(
  event: PatternEvent,
  bars: readonly Candle[],
): ResearchEvent {
  const barTime = (index: number): number => {
    const value = bars[index]?.time;
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if (typeof value === 'string') return parseDayMs(value);
    throw new Error(`event ${event.key} anchors missing bar ${index}`);
  };
  const confirmedTime = barTime(event.confirmedAtIndex);
  return {
    key: event.key,
    detector: event.detector,
    family: event.family,
    bias: event.bias,
    status: event.status,
    confirmedAtIndex: event.confirmedAtIndex,
    confirmedAt: dayOf(confirmedTime),
    confirmedTime,
    startIndex: event.startIndex,
    anchors: event.anchors.map((anchor) => ({
      index: anchor.index,
      time: dayOf(barTime(anchor.index)),
      price: anchor.price,
      role: anchor.role,
      confirmedAtIndex: anchor.confirmedAtIndex,
    })),
    ...(event.level === undefined ? {} : { level: event.level }),
  };
}

function toProvisional(points: ReturnType<typeof scanPatterns>['provisionalSwings']): ProvisionalSwingLite[] {
  return points.map((point) => ({
    detector: point.detector,
    index: point.index,
    time: dayOf(typeof point.time === 'number' ? point.time : parseDayMs(String(point.time))),
    price: point.price,
    status: 'provisional',
  }));
}

function errorText(error: unknown): string {
  return error instanceof Error ? `${error.name}: ${error.message}` : String(error);
}

/**
 * Builds the production adjusted series, then scans raw and adjusted copies.
 * Failures are returned as data, never dropped.
 */
export function scanRecord(
  record: RealMarketRecord,
  timeframe: ResearchTimeframe,
  hashVerified: boolean,
): SeriesScan {
  const seriesKey = `${record.symbol}|${timeframe}`;
  const runtime = { collector: record.runtimeMs ?? 0, build: 0, adjustedScan: 0, rawScan: 0 };
  const base: SeriesScan = {
    symbol: record.symbol,
    timeframe,
    stratum: record.universe?.stratum === 'short' ? 'short' : 'full',
    liquidityBand: record.universe?.liquidityBand ?? 'unknown',
    historyBand: record.universe?.historyBand ?? 'unknown',
    seriesKey,
    candleCount: 0,
    barYears: [],
    adjustedBars: [],
    rawBars: [],
    rawDailyCount: 0,
    adjustedDailyCount: 0,
    dateRange: [record.firstDate ?? '', record.lastDate ?? ''],
    adjustSource: record.adjustSource ?? null,
    combinedAvailable:
      typeof record.adjustCapability?.combined_available === 'boolean'
        ? record.adjustCapability.combined_available
        : null,
    factorCount: record.factorCount ?? 0,
    factorOneCount: 0,
    adjustEventCount: record.adjustEvents?.length ?? 0,
    adjustRejectedCount: record.adjustRejected?.length ?? 0,
    inputSha256: record.inputSha256 ?? '',
    hashVerified,
    runtimeMs: runtime,
    adjusted: { events: [], provisional: [] },
    raw: { events: [] },
    salience: buildSalience(seriesKey, [], 0),
  };

  let bars: TimeframeBars;
  const buildStart = nowMs();
  try {
    bars = buildTimeframeBars(record, timeframe);
  } catch (error) {
    const message = errorText(error);
    base.adjusted.error = message;
    base.raw.error = message;
    runtime.build = nowMs() - buildStart;
    return base;
  }
  runtime.build = nowMs() - buildStart;
  base.candleCount = bars.adjustedBars.length;
  base.adjustedBars = bars.adjustedBars;
  base.rawBars = bars.rawBars;
  base.barYears = bars.adjustedBars.map((bar) =>
    dayOf(typeof bar.time === 'number' ? bar.time : parseDayMs(String(bar.time))).slice(0, 4),
  );
  base.rawDailyCount = bars.rawDailyCount;
  base.adjustedDailyCount = bars.adjustedDailyCount;
  base.factorOneCount = bars.factorOneCount;
  base.dateRange = [
    record.firstDate ?? '',
    record.lastDate ?? '',
  ];

  const adjustedStart = nowMs();
  try {
    const scan = scanPatterns(bars.adjustedBars);
    runtime.adjustedScan = nowMs() - adjustedStart;
    base.adjusted.events = scan.events.map((e) => toResearchEvent(e, bars.adjustedBars));
    base.adjusted.provisional = toProvisional(scan.provisionalSwings);
    base.salience = buildSalience(
      seriesKey,
      base.adjusted.events.map((e) => ({
        key: e.key,
        detector: e.detector,
        family: e.family,
        bias: e.bias,
        confirmedAtIndex: e.confirmedAtIndex,
        confirmedAt: e.confirmedTime,
        anchors: e.anchors,
        level: e.level,
      })),
      Math.max(0, bars.adjustedBars.length - 1),
    );
  } catch (error) {
    runtime.adjustedScan = nowMs() - adjustedStart;
    base.adjusted.error = errorText(error);
  }

  const rawStart = nowMs();
  try {
    const scan = scanPatterns(bars.rawBars);
    runtime.rawScan = nowMs() - rawStart;
    base.raw.events = scan.events.map((e) => toResearchEvent(e, bars.rawBars));
  } catch (error) {
    runtime.rawScan = nowMs() - rawStart;
    base.raw.error = errorText(error);
  }

  return base;
}
