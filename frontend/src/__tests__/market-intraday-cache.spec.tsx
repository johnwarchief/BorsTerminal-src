// تست کش درون‌روزی اسنپ‌شات‌ها (P-04): روز/ساعت بازار، پاک‌سازی روزانه، سقف حجم، ادغام
import { describe, expect, it } from 'vitest';
import {
  INTRADAY_CACHE_KEY,
  MAX_CACHED_POINTS,
  MAX_CACHE_BYTES,
  SNAPSHOT_POLL_MS,
  appendSnapshot,
  dayKey,
  isMarketOpen,
  mergePoints,
  readCache,
  writeCache,
} from '@features/market/lib/intradayCache';
import type { TimelinePoint } from '@features/market/lib/timelineMath';

class MemStorage {
  private m = new Map<string, string>();
  getItem(k: string): string | null {
    return this.m.has(k) ? (this.m.get(k) as string) : null;
  }
  setItem(k: string, v: string): void {
    this.m.set(k, v);
  }
  removeItem(k: string): void {
    this.m.delete(k);
  }
  get length(): number {
    return this.m.size;
  }
}

function point(t: string, over: Partial<TimelinePoint> = {}): TimelinePoint {
  return { t, bq: 1, sq: 2, pos: 3, neg: 4, ...over };
}

describe('کلید روز و ساعات بازار', () => {
  it('dayKey قالب YYYY-MM-DD محلی', () => {
    expect(dayKey(new Date(2026, 8, 14, 9, 0))).toBe('2026-09-14');
  });

  it('isMarketOpen: شنبه..چهارشنبه ۰۸:۴۵–۱۲:۳۰ (پنجشنبه/جمعه بسته)', () => {
    // ۱۴ سپتامبر ۲۰۲۶ = دوشنبه
    expect(isMarketOpen(new Date(2026, 8, 14, 9, 0))).toBe(true);
    expect(isMarketOpen(new Date(2026, 8, 14, 8, 44))).toBe(false);
    expect(isMarketOpen(new Date(2026, 8, 14, 12, 30))).toBe(true);
    expect(isMarketOpen(new Date(2026, 8, 14, 12, 31))).toBe(false);
    // ۱۹ سپتامبر ۲۰۲۶ = شنبه (باز)
    expect(isMarketOpen(new Date(2026, 8, 19, 10, 0))).toBe(true);
    // ۱۷ سپتامبر = پنجشنبه، ۱۸ سپتامبر = جمعه (بسته حتی در ساعات بازار)
    expect(isMarketOpen(new Date(2026, 8, 17, 10, 0))).toBe(false);
    expect(isMarketOpen(new Date(2026, 8, 18, 10, 0))).toBe(false);
  });

  it('فاصلهٔ پولینگ ۳۰ ثانیه است', () => {
    expect(SNAPSHOT_POLL_MS).toBe(30_000);
  });
});

describe('کش محلی', () => {
  it('افزودن/به‌روزرسانی نقطه با کلید t و مرتب‌سازی', () => {
    const st = new MemStorage();
    appendSnapshot(point('10:00'), '2026-09-14', st as unknown as Storage);
    appendSnapshot(point('09:00'), '2026-09-14', st as unknown as Storage);
    appendSnapshot(point('10:00', { bq: 99 }), '2026-09-14', st as unknown as Storage);
    const out = readCache('2026-09-14', st as unknown as Storage);
    expect(out.map((p) => p.t)).toEqual(['09:00', '10:00']);
    expect(out[1].bq).toBe(99); // به‌روزرسانی همان t
  });

  it('پاک‌سازی خودکار روزانه: کد روز عوض شود، کش خالی و حذف می‌شود', () => {
    const st = new MemStorage();
    appendSnapshot(point('09:00'), '2026-09-14', st as unknown as Storage);
    expect(st.getItem(INTRADAY_CACHE_KEY)).not.toBeNull();
    expect(readCache('2026-09-15', st as unknown as Storage)).toEqual([]);
    expect(st.getItem(INTRADAY_CACHE_KEY)).toBeNull();
  });

  it('سقف تعداد نقاط رعایت می‌شود', () => {
    const st = new MemStorage();
    const many = Array.from({ length: MAX_CACHED_POINTS + 120 }, (_, i) =>
      point(`t${String(i).padStart(4, '0')}`),
    );
    const kept = writeCache('2026-09-14', many, st as unknown as Storage);
    expect(kept.length).toBeLessThanOrEqual(MAX_CACHED_POINTS);
    expect(readCache('2026-09-14', st as unknown as Storage).length).toBeLessThanOrEqual(MAX_CACHED_POINTS);
  });

  it('سقف حجم (≈۱MB): نقاط حجیم تا زیر سقف بایت تراش می‌خورند', () => {
    const st = new MemStorage();
    const heavy = Array.from({ length: 600 }, (_, i) => point(`x${'z'.repeat(2000)}${i}`));
    const kept = writeCache('2026-09-14', heavy, st as unknown as Storage);
    const stored = st.getItem(INTRADAY_CACHE_KEY) as string;
    expect(kept.length).toBeLessThan(heavy.length);
    expect(stored.length).toBeLessThanOrEqual(MAX_CACHE_BYTES);
  });

  it('کش خالی ⇒ آرایهٔ خالی (بدون خطا)', () => {
    expect(readCache('2026-09-14', new MemStorage() as unknown as Storage)).toEqual([]);
  });
});

describe('ادغام سری‌ها', () => {
  it('mergePoints اجتماع بدون تکرار و مرتب بر اساس t', () => {
    const a = [point('09:00', { bq: 1 }), point('10:00', { bq: 2 })];
    const b = [point('10:00', { bq: 22 }), point('11:00', { bq: 3 })];
    const out = mergePoints(a, b);
    expect(out.map((p) => p.t)).toEqual(['09:00', '10:00', '11:00']);
    expect(out[1].bq).toBe(22); // اولویت سری دوم
  });
});
