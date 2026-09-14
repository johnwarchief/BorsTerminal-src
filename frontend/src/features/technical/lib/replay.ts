// features/technical/lib/replay.ts -- کمک‌تابع‌های خالص بازپخش کندل (Bar Replay)
// بدون state؛ فقط برش/کلمپ/گام تا در تست قابل اتکا باشد.

/** سرعت‌های بازپخش (میلی‌ثانیه بین کندل‌ها) */
export const REPLAY_SPEEDS = [1000, 500, 250, 100] as const;
export const REPLAY_DEFAULT_SPEED = 500;

/** کلمپ ایندکس مکان‌نما در بازهٔ معتبر */
export function clampCursor(cursor: number, length: number): number {
  if (!Number.isFinite(cursor) || length <= 0) return 0;
  return Math.max(0, Math.min(length - 1, Math.round(cursor)));
}

/** فقط کندل‌های تا مکان‌نما (شامل خودش) — بقیه پنهان می‌مانند */
export function replaySlice<T>(rows: T[], cursor: number): T[] {
  if (rows.length === 0) return [];
  return rows.slice(0, clampCursor(cursor, rows.length) + 1);
}

/** گام بعد/قبل با کلمپ؛ برگشت مقدار جدید */
export function stepCursor(cursor: number, length: number, dir: 1 | -1): number {
  return clampCursor(clampCursor(cursor, length) + dir, length);
}

/** آیا به انتهای داده رسیده‌ایم؟ (پخش باید متوقف شود) */
export function isAtEnd(cursor: number, length: number): boolean {
  return length <= 0 || clampCursor(cursor, length) >= length - 1;
}

/** درصد پیشرفت بازپخش (۰..۱۰۰) */
export function replayProgress(cursor: number, length: number): number {
  if (length <= 1) return 100;
  return Math.round((clampCursor(cursor, length) / (length - 1)) * 100);
}
