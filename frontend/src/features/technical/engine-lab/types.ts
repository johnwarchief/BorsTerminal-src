// features/technical/engine-lab/types.ts -- واژه‌هایِ خودِ آزمایشگاه.
// «سلامتِ موتور» درِ EngineHealth است؛ این‌ها چیزِ دیگری‌اند: مدتِ بالا‌آمدن،
// نرخِ فریم و حافظه — چیزی که هیچ موتوری خودش گزارش نمی‌کند و مالک برایِ
// مقایسه لازم دارد. برایِ همین این‌جا نگه داشته شده، نه درِ لایۀ engine.
import type { ChartCapabilities } from '@features/technical/engine';

export type LabTimeframe = 'D' | 'W' | 'M';

export const LAB_TIMEFRAMES: LabTimeframe[] = ['D', 'W', 'M'];

export type LabMetrics = {
  /** میلی‌ثانیۀ create() تا نخستین فریمِ نقاشی‌شده */
  mountMs: number | null;
  /** نرخِ فریمِ واقعی درِ پنجرۀ ۳ ثانیه‌ای؛ null یعنی هنوز اندازه گرفته نشده */
  fps: number | null;
  /** مصرفِ پشته درِ همان پنجره؛ Firefox/Safari این عدد را هیچ‌وقت نمی‌دهند */
  heapDeltaMb: number | null;
  canvasCount: number;
  barCount: number;
  overlayCount: number;
  /** health().renderer — موتوری که mount نشده null می‌ماند تا «صفر» خوانده نشود */
  renderer: string | null;
  /** جدولِ قابلیت‌ها از همین خوانده می‌شود؛ موتورِ بالا‌نیامده null است */
  capabilities: ChartCapabilities | null;
  measuredAt: number | null;
};

export const EMPTY_LAB_METRICS: LabMetrics = {
  mountMs: null,
  fps: null,
  heapDeltaMb: null,
  canvasCount: 0,
  barCount: 0,
  overlayCount: 0,
  renderer: null,
  capabilities: null,
  measuredAt: null,
};
