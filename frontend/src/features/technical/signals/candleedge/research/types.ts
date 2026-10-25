import type { PatternBias, PatternFamily } from '../types';

export type SalienceBias = PatternBias | 'mixed';

export interface SalienceAnchor {
  index: number;
  role?: string;
  price?: number;
  confirmedAtIndex?: number;
}

export interface SalienceInputEvent {
  key: string;
  detector: string;
  family: PatternFamily | string;
  bias: PatternBias;
  confirmedAtIndex: number;
  confirmedAt?: number;
  anchors: SalienceAnchor[];
  level?: number;
}

export interface SalienceGroup {
  id: string;
  seriesKey: string;
  eventKeys: string[];
  anchorIndices: number[];
  sharedAnchorIndices: number[];
  anchorPriceRange: [number, number] | null;
  detectors: string[];
  families: string[];
  bias: SalienceBias;
  levels: number[];
  earliestConfirmedAtIndex: number;
  latestConfirmedAtIndex: number;
  ageBars: number;
  newestEventKey: string;
  oldestEventKey: string;
  repeatedDetectorAnchorSets: boolean;
}

export type SalienceMethod = 'latest' | 'structure_first' | 'evidence_count';

export interface SalienceResult {
  seriesKey: string;
  groups: SalienceGroup[];
  order: Record<SalienceMethod, string[]>;
  rules: Record<SalienceMethod, string>;
  repeatedGroups: number;
  multiEventGroups: number;
}

export interface ForwardBar {
  time: number;
  open: number;
  close: number;
}

export interface ForwardEvent {
  key: string;
  detector: string;
  bias: PatternBias;
  confirmedAtIndex: number;
  confirmedAt: number;
}

export type ForwardPeriod = 'discovery' | 'evaluation';

export interface ForwardOutcome {
  symbol: string;
  detector: string;
  horizon: number;
  period: ForwardPeriod;
  entryTime: number;
  returnPct: number;
  baselineLocal: number | null;
}

export interface ForwardRow {
  detector: string;
  horizon: number;
  period: ForwardPeriod;
  n: number;
  rightCensored: number;
  mean: number | null;
  median: number | null;
  q05: number | null;
  q25: number | null;
  q50: number | null;
  q75: number | null;
  q95: number | null;
  sd: number | null;
  winRate: number | null;
  winRateCI: [number, number] | null;
  meanCI: [number, number] | null;
  baselineLocalMean: number | null;
  baselineLocalN: number;
  baselineMarketMean: number | null;
  marketBaselineN: number;
  deltaLocal: number | null;
  deltaMarket: number | null;
  lowSample: boolean;
  entryRule: 'next-bar-open';
  exitRule: 'horizon-close';
  note: string;
}
