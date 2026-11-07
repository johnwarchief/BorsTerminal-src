// model/patterns/types.ts
import type { FormationEstimate } from '../types';

export type PatternKind =
  | 'DOUBLE_TOP' | 'DOUBLE_BOTTOM'
  | 'FLAG_BULL' | 'FLAG_BEAR' | 'PENNANT'
  | 'TRIANGLE_ASC' | 'TRIANGLE_DESC' | 'TRIANGLE_SYM'
  | 'RECTANGLE' | 'WEDGE_RISING' | 'WEDGE_FALLING'
  | 'HEAD_SHOULDERS' | 'INVERSE_HEAD_SHOULDERS'
  | 'TRIPLE_TOP' | 'TRIPLE_BOTTOM'
  | 'CUP_HANDLE' | 'INVERSE_CUP_HANDLE'
  | 'ROUNDING_TOP' | 'ROUNDING_BOTTOM'
  | 'DIAMOND_TOP' | 'DIAMOND_BOTTOM'
  | 'BROADENING_TOP' | 'BROADENING_BOTTOM'
  | 'ISLAND_REVERSAL'
  | 'THREE_RISING_PEAKS' | 'THREE_FALLING_PEAKS';

/** ردهٔ ۱ = پذیرش کامل؛ ردهٔ ۲ = کم‌بسامد، بهترین‌تلاش با برچسب. */
export type PatternTier = 1 | 2;

export type PatternStatus = 'forming' | 'confirmed' | 'invalidated';
export type PatternDirection = 'bullish' | 'bearish' | 'neutral';
export type PatternFamily = 'continuation' | 'reversal';

export interface PatternPoint { index: number; price: number; timestamp?: number }
export interface BoundaryLine { from: PatternPoint; to: PatternPoint }

export interface ChartPattern {
  id: string;
  kind: PatternKind;
  tier?: PatternTier;
  direction: PatternDirection;
  family: PatternFamily;
  anchor: PatternPoint;
  points: PatternPoint[];
  upper: BoundaryLine;
  lower: BoundaryLine;
  neckline?: BoundaryLine;
  breakoutIndex?: number;
  target: number;
  stopLoss: number;
  quality: number;
  status: PatternStatus;
  formation?: FormationEstimate;
  returns?: { h1: number | null; h3: number | null; h5: number | null };
}
