import type { ChartPattern, PatternPoint } from '../patterns/types';

export type EventFamily = 'pattern' | 'channel' | 'divergence' | 'pullback' | 'breakout';
export type EventDirection = 'bullish' | 'bearish' | 'neutral';
export type EventStatus = 'forming' | 'confirmed' | 'invalidated';

export type DivergenceKind =
  | 'RSI_REGULAR_BULLISH'
  | 'RSI_REGULAR_BEARISH'
  | 'RSI_HIDDEN_BULLISH'
  | 'RSI_HIDDEN_BEARISH';

export type ChannelKind = 'REGRESSION_CHANNEL';
export type PullbackKind = 'PULLBACK_BULLISH' | 'PULLBACK_BEARISH';
export type BreakoutKind = 'BREAKOUT_UP' | 'BREAKOUT_DOWN';

export interface EventLine {
  from: PatternPoint;
  to: PatternPoint;
  style?: 'solid' | 'dashed';
}

export interface EventDrawing {
  lines?: EventLine[];
  label?: string;
  labelAt?: PatternPoint;
  color?: string;
}

export interface EventMetrics {
  [key: string]: number | string | null | undefined;
}

export interface EventStats {
  h1: number | null;
  h3: number | null;
  h5: number | null;
  samples: number;
  interval?: [number, number];
}

export interface EventEvidence {
  ruleRef: string;
  source: 'classic' | 'telegram' | 'existing-engine' | 'rsi';
}

export interface ChartEvent {
  id: string;
  family: EventFamily;
  kind: string;
  direction: EventDirection;
  status: EventStatus;
  anchor: PatternPoint;
  interval?: [number, number];
  quality: number;
  metrics: EventMetrics;
  evidence: EventEvidence;
  draw: EventDrawing;
  stats?: EventStats;
  /** Payload for pattern events; the existing pattern overlay keeps consuming it. */
  pattern?: ChartPattern;
}

export interface ScanResult {
  at: number;
  symbol?: string;
  timeframe: string;
  adjustmentMode: number;
  seriesBasis: 'functional';
  bars: number;
  events: ChartEvent[];
  primary: Partial<Record<EventFamily, string>>;
  configHash: string;
}
