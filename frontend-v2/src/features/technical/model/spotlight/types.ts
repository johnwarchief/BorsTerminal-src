/**
 * model/spotlight/types.ts
 *
 * مدل مشترک «اسپات‌لایت الگو» (spec §3.1):
 * دو منبعِ الگو — موتور W/M (`DoubleTapPattern`) و الگوهای کلاسیک (`ChartPattern`) —
 * به یک شکلِ واحد تبدیل می‌شوند تا لایهٔ ۳D فقط یک زبانِ بصری داشته باشد.
 *
 * این فایل/آداپترها هیچ وابستگی‌ای به React یا KLineCharts ندارند.
 */
import type { PatternPoint } from '../patterns/types';

export type SpotlightSource = 'doubleTap' | 'classic';

/** وضعیت‌های چرخهٔ p12 + وضعیت‌های الگوهای کلاسیک. */
export type SpotlightStatus =
  | 'forming'
  | 'confirmed'
  | 'active'
  | 'tp1_hit'
  | 'tp2_hit'
  | 'invalidated'
  | 'failed'
  | 'timed_out';

export type SpotlightDirection = 'bullish' | 'bearish' | 'neutral';

export type SpotlightGrade = 'A' | 'B' | 'C';

/** تفکیک امتیاز p12 (۲۵/۲۰/۱۵/۱۵/۱۰/۱۵). */
export interface SpotlightScoreBreakdown {
  match: number;
  rsi: number;
  volume: number;
  height: number;
  symmetry: number;
  trend: number;
}

export interface SpotlightModel {
  id: string;
  source: SpotlightSource;
  kind: string;
  kindLabel: string;
  direction: SpotlightDirection;
  status: SpotlightStatus;
  grade?: SpotlightGrade;
  /** امتیاز p12 (۰..۱۰۰)؛ الگوهای کلاسیک امتیاز p12 ندارند. */
  score?: number;
  quality: number;
  anchorIndex: number;
  points: PatternPoint[];
  /** سطحِ مرز بالا (قلهٔ بلندتر در W/M یا مقدار مرز بالا در لنگر). */
  upper: number;
  /** سطحِ مرز پایین. */
  lower: number;
  neckline?: number;
  target: number;
  stop: number;
  breakoutIndex?: number;
  tp1?: number;
  tp2?: number;
  /** مسیر پاهای W/M برای polylineِ سایه‌دار. */
  legs?: PatternPoint[];
  scoreBreakdown?: SpotlightScoreBreakdown;
  notes?: string;
  /** ATR جاری در زمان تشخیص؛ عمقِ ۳D از آن ساخته می‌شود. */
  atr?: number;
}
