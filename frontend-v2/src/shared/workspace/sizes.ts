import { PANEL_MIN } from './types';

export const SIDE_WIDTH = { min: 260, max: 420, default: 320 } as const;
export const DOCK_HEIGHT = { min: 160, max: 360, default: 200 } as const;
export const CHART_SHARE = { min: 0.3, max: 0.75, default: 0.6 } as const;

/** عرضِ ریلِ ناوبری در حالتِ باز؛ کفِ محافظه‌کارانهٔ محاسبهٔ جا. */
export const RAIL_WIDTH = 208;

/** سایدبار هرگز نباید دو پنلِ میزکار را از حدِ کمینه‌شان کوچک‌تر کند. */
export function maxSideWidth(viewportWidth: number): number {
  // ۱px هم برایِ خودِ مرزِ کشیدنی کنار می‌رود تا پنل‌ها هرگز از لبه بیرون نزنند.
  const room = viewportWidth - RAIL_WIDTH - 1 - PANEL_MIN.board.w - PANEL_MIN.watch.w;
  if (!Number.isFinite(room)) return SIDE_WIDTH.default;
  return Math.max(SIDE_WIDTH.min, Math.min(SIDE_WIDTH.max, Math.floor(room)));
}
