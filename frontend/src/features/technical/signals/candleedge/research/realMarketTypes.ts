import type { Candle, PatternBias, PatternFamily } from '../types';
import type { SalienceResult } from './types';

export type ResearchTimeframe = 'D' | 'W' | 'M';
export type ScanMode = 'adjusted' | 'raw';
export type HistoryStratum = 'full' | 'short';

export interface RecordCandle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface RecordFactor {
  time: string;
  factor: number;
}

export interface RecordUniverse {
  symbol: string;
  rows: number;
  firstDate: string;
  lastDate: string;
  zeroVolumeRows: number;
  avgTurnover: number;
  sector?: string;
  paperType?: number;
  aliasCount: number;
  historyBand: string;
  liquidityBand: string;
  stratum: HistoryStratum;
}

export interface RealMarketRecord {
  schema: string;
  symbol: string;
  status: 'success' | 'error';
  error?: string;
  collectedAt: string;
  universe: RecordUniverse;
  collector: string;
  candleCount?: number;
  firstDate?: string;
  lastDate?: string;
  rawCandles?: RecordCandle[];
  factors?: RecordFactor[];
  factorCount?: number;
  adjustEvents?: unknown[];
  adjustRejected?: unknown[];
  adjustSource?: string;
  adjustCapability?: {
    combined_available?: boolean;
    functional_available?: boolean;
    availability?: string;
    source?: string;
    [key: string]: unknown;
  };
  corporateEventCount?: number;
  dbRows?: number;
  dbNoTradeRows?: number;
  dbInvalidRows?: number;
  liveInjected?: boolean;
  liveError?: string | null;
  priceBasis?: unknown;
  priceBasisNote?: string;
  ftsPresent?: boolean;
  inputSha256?: string;
  runtimeMs?: number;
}

export interface ResearchAnchor {
  index: number;
  time: string;
  price: number;
  role: string;
  confirmedAtIndex?: number;
}

export interface ResearchEvent {
  key: string;
  detector: string;
  family: PatternFamily;
  bias: PatternBias;
  status: 'confirmed';
  confirmedAtIndex: number;
  confirmedAt: string;
  confirmedTime: number;
  startIndex: number;
  anchors: ResearchAnchor[];
  level?: number;
}

export interface ProvisionalSwingLite {
  detector: 'swing_high' | 'swing_low';
  index: number;
  time: string;
  price: number;
  status: 'provisional';
}

export interface SeriesScan {
  symbol: string;
  timeframe: ResearchTimeframe;
  stratum: HistoryStratum;
  liquidityBand: string;
  historyBand: string;
  seriesKey: string;
  candleCount: number;
  barYears: string[];
  adjustedBars: Candle[];
  rawBars: Candle[];
  rawDailyCount: number;
  adjustedDailyCount: number;
  dateRange: [string, string];
  adjustSource: string | null;
  combinedAvailable: boolean | null;
  factorCount: number;
  factorOneCount: number;
  adjustEventCount: number;
  adjustRejectedCount: number;
  inputSha256: string;
  hashVerified: boolean;
  runtimeMs: {
    collector: number;
    build: number;
    adjustedScan: number;
    rawScan: number;
  };
  adjusted: {
    events: ResearchEvent[];
    provisional: ProvisionalSwingLite[];
    error?: string;
  };
  raw: {
    events: ResearchEvent[];
    error?: string;
  };
  salience: SalienceResult;
}
