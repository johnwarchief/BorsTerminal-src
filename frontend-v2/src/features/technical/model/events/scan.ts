import { calculateAtr, type EngineCandle } from '../doubleTapEngine';
import { PATTERN_CONFIG } from '../patterns/config';
import { detectPivotChannel, type ChannelCandidate } from '../patterns/detectChannelPivot';
import { detectAllPatterns } from '../patterns/registry';
import type { ChartPattern } from '../patterns/types';
import { EVENT_CONFIG, type EventConfig } from './config';
import { detectChannel } from './channel';
import { detectPullbackBreakout } from './pullback';
import { detectRsiDivergences } from './rsi';
import { detectSrRetest, type SrRetestZone } from './zone';
import type { ChartEvent, EventFamily, ScanResult } from './types';

export interface ScanOptions {
  symbol?: string;
  timeframe?: string;
  adjustmentMode?: number;
  config?: EventConfig;
}

const STATUS_SCORE: Record<ChartEvent['status'], number> = {
  forming: 3,
  confirmed: 2,
  invalidated: 1,
};

function score(event: ChartEvent): number {
  const tierPenalty = event.family === 'pattern' && event.pattern?.tier === 2 ? 15 : 0;
  return STATUS_SCORE[event.status] * 1000 + event.quality - tierPenalty + event.anchor.index / 1e6;
}

function patternToEvent(pattern: ChartPattern): ChartEvent {
  const stats = pattern.returns
    ? {
        h1: pattern.returns.h1,
        h3: pattern.returns.h3,
        h5: pattern.returns.h5,
        samples: pattern.formation?.resolved ?? 0,
      }
    : undefined;
  return {
    id: `pattern:${pattern.kind}:${pattern.anchor.index}:${pattern.id}`,
    family: 'pattern',
    kind: pattern.kind,
    direction: pattern.direction,
    status: pattern.status,
    anchor: pattern.anchor,
    interval: [pattern.points[0]?.index ?? pattern.anchor.index, pattern.anchor.index],
    quality: pattern.quality,
    metrics: {
      tier: pattern.tier ?? 1,
      target: pattern.target,
      stopLoss: pattern.stopLoss,
      breakoutIndex: pattern.breakoutIndex ?? null,
    },
    evidence: {
      ruleRef: `PATTERN:${pattern.kind}`,
      source: pattern.id.startsWith('DT:') ? 'existing-engine' : 'classic',
    },
    draw: { labelAt: pattern.anchor },
    stats,
    pattern,
  };
}

function pickPrimary(events: readonly ChartEvent[], family: EventFamily): string | undefined {
  const familyEvents = events.filter((event) => event.family === family);
  if (!familyEvents.length) return undefined;
  return [...familyEvents].sort((a, b) => score(b) - score(a))[0]?.id;
}

function channelCandidateToEvent(candidate: ChannelCandidate, offset: number): ChartEvent {
  const anchor = candidate.points[candidate.points.length - 1] ?? candidate.upper.to;
  return {
    id: `channel:${candidate.kind}:${anchor.index + offset}`,
    family: 'channel',
    kind: candidate.kind,
    direction: 'neutral',
    status: candidate.lifecycle === 'broken' || candidate.lifecycle === 'expired' ? 'invalidated' : 'confirmed',
    anchor: { index: anchor.index + offset, price: anchor.price },
    interval: [candidate.upper.from.index + offset, anchor.index + offset],
    quality: candidate.score,
    metrics: {
      grade: candidate.grade,
      touches: candidate.touches.total,
      violations: candidate.violations,
      lateStage: candidate.lateStage ? 1 : 0,
      convergencePct: candidate.convergencePct ?? null,
      barsToApex: candidate.barsToApex ?? null,
    },
    evidence: { ruleRef: 'P19:WEDGE_CHANNEL', source: 'telegram' },
    draw: {
      lines: [
        { from: { index: candidate.upper.from.index + offset, price: candidate.upper.from.price }, to: { index: candidate.upper.to.index + offset, price: candidate.upper.to.price } },
        { from: { index: candidate.lower.from.index + offset, price: candidate.lower.from.price }, to: { index: candidate.lower.to.index + offset, price: candidate.lower.to.price } },
      ],
    },
  };
}

function srRetestZoneToEvent(zone: SrRetestZone, offset: number): ChartEvent {
  const anchorIndex = (zone.retestIndex ?? zone.breakoutIndex ?? zone.toIndex) + offset;
  const anchorPrice = zone.direction === 'bullish' ? zone.upper : zone.lower;
  return {
    id: `breakout:SR_RETEST:${zone.fromIndex + offset}:${zone.direction}`,
    family: 'breakout',
    kind: 'SR_RETEST',
    direction: zone.direction,
    status: Math.abs(zone.state) >= 3 ? 'confirmed' : 'forming',
    anchor: { index: anchorIndex, price: anchorPrice },
    interval: [zone.fromIndex + offset, zone.toIndex + offset],
    quality: Math.abs(zone.state) * 25,
    metrics: {
      state: zone.state,
      breakoutIndex: zone.breakoutIndex != null ? zone.breakoutIndex + offset : null,
      retestIndex: zone.retestIndex != null ? zone.retestIndex + offset : null,
      volumeBalanceAvailable: 0,
    },
    evidence: { ruleRef: 'P21:SR_RETEST', source: 'telegram' },
    draw: {
      lines: [
        { from: { index: zone.fromIndex + offset, price: zone.upper }, to: { index: zone.toIndex + offset, price: zone.upper } },
        { from: { index: zone.fromIndex + offset, price: zone.lower }, to: { index: zone.toIndex + offset, price: zone.lower } },
      ],
    },
  };
}

function hashConfig(value: unknown): string {
  const text = JSON.stringify(value);
  let h = 5381;
  for (let i = 0; i < text.length; i++) h = ((h << 5) + h + text.charCodeAt(i)) >>> 0;
  return h.toString(16);
}

/**
 * One pure scan for the chart (no DOM, no network):
 * patterns over the full loaded series; the other families over the last
 * scanWindow bars. All anchors are absolute indices into `candles`.
 */
export function scanChart(
  candles: readonly EngineCandle[],
  options: ScanOptions = {},
): ScanResult {
  const config = options.config ?? EVENT_CONFIG;
  const timeframe = options.timeframe ?? '1D';
  const adjustmentMode = options.adjustmentMode ?? 3;
  const base: ScanResult = {
    at: Date.now(),
    symbol: options.symbol,
    timeframe,
    adjustmentMode,
    seriesBasis: 'functional',
    bars: candles.length,
    events: [],
    primary: {},
    configHash: hashConfig({ config, pattern: PATTERN_CONFIG }),
  };
  if (candles.length < 30) return base;
  const atrFull = calculateAtr(candles, config.atrPeriod);
  const lastAtr = atrFull[atrFull.length - 1] ?? 0;
  if (!(lastAtr > 0)) return base;

  const patternEvents = detectAllPatterns(candles, PATTERN_CONFIG).map(patternToEvent);
  const start = Math.max(0, candles.length - config.scanWindow);
  const window = candles.slice(start);
  const atrWindow = atrFull.slice(start);
  const divergenceEvents = detectRsiDivergences(window, atrWindow, config.divergence, start);
  const pivotCandidates = detectPivotChannel(window, atrWindow, PATTERN_CONFIG.channelPivot, start);
  const bestPivotChannel = pivotCandidates.length > 0
    ? [...pivotCandidates].sort((a, b) => {
        const kindPriority = (k: string) => k === 'PIVOT_CHANNEL' ? 1 : 0;
        return kindPriority(b.kind) - kindPriority(a.kind) || b.score - a.score;
      })[0]
    : undefined;
  const pivotChannels = bestPivotChannel ? [channelCandidateToEvent(bestPivotChannel, 0)] : [];
  const channel = pivotChannels.length > 0 ? undefined : detectChannel(window, atrWindow, config.channel, start);
  const srZones = detectSrRetest(window, config.srRetest, start)
    .filter((z) => Math.abs(z.state) >= 1)
    .map((z) => srRetestZoneToEvent(z, 0));
  const pullbackEvents = detectPullbackBreakout(window, atrWindow, config.pullback, start);

  const seen = new Set<string>();
  const events = [...patternEvents, ...divergenceEvents, ...pullbackEvents, ...(channel ? [channel] : []), ...pivotChannels, ...srZones]
    .filter((event) => {
      if (seen.has(event.id)) return false;
      seen.add(event.id);
      return true;
    })
    .sort((a, b) => a.anchor.index - b.anchor.index);

  return {
    ...base,
    events,
    primary: {
      pattern: pickPrimary(events, 'pattern'),
      channel: pickPrimary(events, 'channel'),
      divergence: pickPrimary(events, 'divergence'),
      pullback: pickPrimary(events, 'pullback'),
      breakout: pickPrimary(events, 'breakout'),
    },
  };
}
