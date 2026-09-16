// features/market/lib/intradayCache.ts -- کش محلی درون‌روزیِ اسنپ‌شات‌های تجمعی تابلو
// در ساعات بازار هر ~۳۰ ثانیه یک نقطهٔ تجمعی ذخیره می‌شود تا سری t1,t2,… ساخته شود
// (فالبکِ خطی وقتی تایم‌لاین بک‌اند کمتر از ۲ نقطه دارد). در شروع هر روز معاملاتیِ
// جدید، کشِ روز قبل خودکار پاک می‌شود و حجم کل زیر ~۱MB نگه داشته می‌شود.
import type { TimelinePoint } from './timelineMath';

export const INTRADAY_CACHE_KEY = 'bors:market:intraday:v1';
/** فاصلهٔ پولینگ اسنپ‌شات (میلی‌ثانیه) */
export const SNAPSHOT_POLL_MS = 30_000;
/** سقف تعداد نقاط نگه‌داشته‌شده */
export const MAX_CACHED_POINTS = 600;
/** سقف حجم کش (بایت) -- گارد ~۱MB */
export const MAX_CACHE_BYTES = 1_000_000;

export type CachedSnapshot = { day: string; points: TimelinePoint[] };

/** کلید روز معاملاتی بر اساس زمان محلی: YYYY-MM-DD */
export function dayKey(d: Date = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** ساعات بازار ایران: شنبه..چهارشنبه، ۰۸:۴۵ تا ۱۲:۳۰ (زمان محلی) */
export function isMarketOpen(d: Date = new Date()): boolean {
  const wd = d.getDay(); // 0=Sun … 6=Sat
  if (wd === 4 || wd === 5) return false; // پنجشنبه/جمعه
  const mins = d.getHours() * 60 + d.getMinutes();
  return mins >= 8 * 60 + 45 && mins <= 12 * 60 + 30;
}

function storageOrNull(storage?: Storage): Storage | null {
  if (storage) return storage;
  try {
    return typeof localStorage === 'undefined' ? null : localStorage;
  } catch {
    return null;
  }
}

function isPoint(p: unknown): p is TimelinePoint {
  return !!p && typeof p === 'object' && typeof (p as TimelinePoint).t === 'string';
}

/** خواندن کش؛ اگر روزِ ذخیره‌شده با روز جاری یکی نیست ⇒ پاک‌سازی خودکار روزانه */
export function readCache(day: string = dayKey(), storage?: Storage): TimelinePoint[] {
  const st = storageOrNull(storage);
  if (!st) return [];
  let raw: string | null = null;
  try {
    raw = st.getItem(INTRADAY_CACHE_KEY);
  } catch {
    return [];
  }
  if (!raw) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return [];
  }
  const obj = parsed as Partial<CachedSnapshot> | null;
  if (!obj || obj.day !== day || !Array.isArray(obj.points)) {
    // روز قبل ⇒ پاک‌سازی (prune خودکار شروع روز جدید)
    try {
      st.removeItem(INTRADAY_CACHE_KEY);
    } catch {
      // نادیده — بی‌دسترسی به storage
    }
    return [];
  }
  return obj.points.filter(isPoint);
}

/** نوشتن کش با تراش حجم؛ نقاط قدیمی‌تر حذف می‌شوند تا زیر سقف بایت بماند */
export function writeCache(day: string, points: TimelinePoint[], storage?: Storage): TimelinePoint[] {
  let kept = points.slice(-MAX_CACHED_POINTS);
  const payload = () => JSON.stringify({ day, points: kept });
  let text = payload();
  while (kept.length > 1 && text.length > MAX_CACHE_BYTES) {
    kept = kept.slice(Math.max(1, Math.ceil(kept.length / 10)));
    text = payload();
  }
  const st = storageOrNull(storage);
  if (st) {
    try {
      st.setItem(INTRADAY_CACHE_KEY, text);
    } catch {
      // نادیده — حافظهٔ پر/دسترسی‌نداشته
    }
  }
  return kept;
}

/** افزودن/به‌روزرسانی یک نقطه (کلید = t) و برگرداندن کل سری مرتب */
export function appendSnapshot(
  point: TimelinePoint,
  day: string = dayKey(),
  storage?: Storage,
): TimelinePoint[] {
  const existing = readCache(day, storage);
  if (!point || typeof point.t !== 'string' || !point.t) return existing;
  const byT = new Map(existing.map((p) => [p.t, p]));
  byT.set(point.t, point);
  const merged = [...byT.values()].sort((a, b) => a.t.localeCompare(b.t));
  return writeCache(day, merged, storage);
}

/** ادغام دو سری بر اساس t (بدون تکرار؛ سری دوم اولویت دارد) */
export function mergePoints(a: TimelinePoint[], b: TimelinePoint[]): TimelinePoint[] {
  const byT = new Map<string, TimelinePoint>();
  for (const p of a) if (isPoint(p) && p.t) byT.set(p.t, p);
  for (const p of b) if (isPoint(p) && p.t) byT.set(p.t, p);
  return [...byT.values()].sort((x, y) => x.t.localeCompare(y.t));
}
