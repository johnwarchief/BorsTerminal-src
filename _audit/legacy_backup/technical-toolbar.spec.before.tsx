// تست بازنمونه‌گیری تایم‌فریم و کاتالوگ ابزارهای ترسیم (فاز ۳ — TV parity)
// تولبار و ریل ابزارِ قدیمی از برنامه بیرون رفتند؛ نوارِ زنده در
// features/technical/nahayatnegar است و پوششِ همان در specهای
// technical-compare-overlay و technical-price-alerts است. اینجا دو منطقِ
// خالصِ کتابخانه‌ای می‌ماند که همان نوارِ زنده هم به آن‌ها تکیه می‌کند.
import { describe, expect, it } from 'vitest';
import type { KLineData } from '@vendor/klinecharts';
import { resample } from '@features/technical/lib/resample';
import { buildDrawingGroups } from '@features/technical/lib/drawingTools';

const day = (ts: number, o: number, h: number, l: number, c: number, v: number): KLineData => ({
  timestamp: ts,
  open: o,
  high: h,
  low: l,
  close: c,
  volume: v,
});

describe('بازنمونه‌گیری تایم‌فریم', () => {
  it('روزانه همان لیست است (کپی، نه همان مرجع)', () => {
    const c = [day(Date.UTC(2025, 0, 1), 1, 2, 0.5, 1.5, 10)];
    const out = resample(c, 'day');
    expect(out).toEqual(c);
    expect(out).not.toBe(c);
  });

  it('هفتگی OHLC را تجمیع می‌کند', () => {
    const c = [day(Date.UTC(2025, 0, 6), 10, 12, 9, 11, 100), day(Date.UTC(2025, 0, 7), 11, 15, 8, 14, 200)];
    const out = resample(c, 'week');
    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({ open: 10, high: 15, low: 8, close: 14, volume: 300, timestamp: c[1].timestamp });
  });

  it('ماهانه دو ماه را جدا می‌کند', () => {
    const c = [day(Date.UTC(2025, 0, 20), 1, 2, 0.5, 1.5, 10), day(Date.UTC(2025, 1, 3), 2, 3, 1.5, 2.5, 20)];
    const out = resample(c, 'month');
    expect(out).toHaveLength(2);
    expect(out[0].close).toBe(1.5);
    expect(out[1].close).toBe(2.5);
  });

  it('ورودی ناصعودی نیز درست تجمیع می‌شود', () => {
    const c = [day(Date.UTC(2025, 0, 7), 11, 15, 8, 14, 200), day(Date.UTC(2025, 0, 6), 10, 12, 9, 11, 100)];
    const out = resample(c, 'week');
    expect(out).toHaveLength(1);
    expect(out[0].open).toBe(10);
    expect(out[0].close).toBe(14);
  });
});

describe('کاتالوگ ابزارهای ترسیم', () => {
  it('buildDrawingGroups ابزارهای پشتیبانی‌شده را نگه می‌دارد و سفارشی‌ها همیشه هستند', () => {
    const g = buildDrawingGroups(['straightLine', 'fibonacciLine', 'brush']);
    expect(g.map((x) => x.label)).toEqual(['خطوط', 'فیبوناچی', 'اندازه‌گیری / پوزیشن', 'حاشیه‌نویسی', 'پیشرفته (TV)']);
    expect(g[0].tools.map((t) => t.name)).toEqual(['straightLine']);
    // چارت هیچ اورلی‌ای را پشتیبانی نکند، فقط گروه‌های سفارشیِ FTS می‌مانند
    const empty = buildDrawingGroups([]);
    expect(empty.every((x) => x.tools.every((t) => t.custom === true))).toBe(true);
    expect(empty.length).toBeGreaterThan(0);
  });
});
