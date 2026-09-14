// تست انواع چارت (T-08 قطعهٔ ۱): Heikin-Ashi / Renko / Kagi / Point & Figure + ATR
import { describe, expect, it } from 'vitest';
import type { KLineData } from '@vendor/klinecharts';
import {
  atr,
  heikinAshi,
  isChartTransform,
  kagi,
  pointAndFigure,
  renko,
  transformCandles,
  trueRange,
  withUniqueTime,
} from '@features/technical/lib/chartTypes';

const t0 = Date.UTC(2025, 0, 1);
function bar(i: number, o: number, h: number, l: number, c: number): KLineData {
  return { timestamp: t0 + i * 86_400_000, open: o, high: h, low: l, close: c, volume: 100 + i };
}
function fromCloses(closes: number[]): KLineData[] {
  return closes.map((c, i) => bar(i, c, c + 1, c - 1, c));
}
/** کندل کاملاً تخت (بدون دامنه) — برای ATR/Renko صفر */
function flatBars(n: number): KLineData[] {
  return Array.from({ length: n }, (_, i) => ({ timestamp: t0 + i * 86_400_000, open: 100, high: 100, low: 100, close: 100 }));
}

describe('شناسایی و نگاشت نوع چارت', () => {
  it('isChartTransform', () => {
    expect(isChartTransform('heikin_ashi')).toBe(true);
    expect(isChartTransform('renko')).toBe(true);
    expect(isChartTransform('candle_solid')).toBe(false);
    expect(isChartTransform('line')).toBe(false);
  });

  it('transformCandles برای انواع موتور، ورودی را دست‌نخورده برمی‌گرداند', () => {
    const rows = fromCloses([10, 11, 12]);
    expect(transformCandles('line', rows)).toBe(rows);
    expect(transformCandles('candle_solid', rows)).toBe(rows);
  });

  it('دادهٔ خالی ⇒ خروجی خالی (بدون ساختگی)', () => {
    expect(heikinAshi([])).toEqual([]);
    expect(renko([])).toEqual([]);
    expect(kagi([])).toEqual([]);
    expect(pointAndFigure([])).toEqual([]);
  });
});

describe('Heikin-Ashi', () => {
  it('فرمول‌های HA و کرانه‌ها درست است', () => {
    const rows = [bar(0, 10, 12, 9, 11), bar(1, 11, 13, 10, 12)];
    const ha = heikinAshi(rows);
    expect(ha).toHaveLength(2);
    // کندل اول: open=(o+c)/2=10.5 ، close=(o+h+l+c)/4=10.5
    expect(ha[0].open).toBeCloseTo(10.5, 6);
    expect(ha[0].close).toBeCloseTo(10.5, 6);
    expect(ha[0].high).toBeCloseTo(12, 6);
    expect(ha[0].low).toBeCloseTo(9, 6);
    // کندل دوم: open=(haOpen+haClose)/2=10.5 ، close=11.5
    expect(ha[1].open).toBeCloseTo(10.5, 6);
    expect(ha[1].close).toBeCloseTo(11.5, 6);
    expect(ha[1].high).toBeCloseTo(13, 6);
    expect(ha[1].low).toBeCloseTo(10, 6);
  });
});

describe('ATR/TR', () => {
  it('trueRange با/بدون بستهٔ قبلی', () => {
    expect(trueRange(null, 12, 9)).toBe(3);
    expect(trueRange(10, 12, 9)).toBe(3);
    expect(trueRange(12, 13, 11)).toBe(2);
  });

  it('ATR سری صعودی مثبت و سری تخت null', () => {
    const rising = fromCloses(Array.from({ length: 30 }, (_, i) => 100 + i * 2));
    expect(atr(rising, 14)).toBeGreaterThan(0);
    expect(atr(flatBars(30), 14)).toBeNull();
  });
});

describe('Renko', () => {
  it('بریک‌های ثابت در جهت درست ساخته می‌شوند', () => {
    const rows = fromCloses([10, 12, 14, 13, 11]);
    const bricks = renko(rows, { boxSize: 2 });
    expect(bricks).toHaveLength(3);
    expect(bricks[0]).toMatchObject({ open: 10, close: 12 });
    expect(bricks[1]).toMatchObject({ open: 12, close: 14 });
    expect(bricks[2]).toMatchObject({ open: 14, close: 12 });
    // زمان‌ها اکیداً صعودی
    for (let i = 1; i < bricks.length; i++) expect(bricks[i].timestamp).toBeGreaterThan(bricks[i - 1].timestamp);
  });

  it('سری تخت ⇒ ATR صفر ⇒ بدون بریک (صادقانه)', () => {
    expect(renko(flatBars(30))).toEqual([]);
  });
});

describe('Kagi', () => {
  it('با برگشت درصدی، سگمنت‌ها ساخته می‌شوند', () => {
    const rows = fromCloses([100, 110, 103]);
    const segs = kagi(rows, { reversalPct: 5 });
    expect(segs).toHaveLength(2);
    expect(segs[0]).toMatchObject({ open: 100, close: 110 });
    expect(segs[1]).toMatchObject({ open: 110, close: 103 });
    expect(segs[1].low).toBe(103);
    expect(segs[1].high).toBe(110);
  });
});

describe('Point & Figure', () => {
  it('ستون X صعودی یک کندل می‌دهد', () => {
    const cols = pointAndFigure(fromCloses([10, 11, 12, 13, 14, 15, 16]), { boxSize: 2, reversal: 3 });
    expect(cols).toHaveLength(1);
    expect(cols[0]).toMatchObject({ open: 10, close: 16 });
    expect(cols[0].high).toBe(16);
    expect(cols[0].low).toBe(10);
  });

  it('برگشت ۳ باکس ⇒ ستون O نزولی', () => {
    const cols = pointAndFigure(fromCloses([10, 16, 10]), { boxSize: 2, reversal: 3 });
    expect(cols).toHaveLength(2);
    expect(cols[0].close).toBeGreaterThan(cols[0].open); // X
    expect(cols[1].close).toBeLessThan(cols[1].open); // O
    expect(cols[1]).toMatchObject({ open: 16, close: 10 });
  });
});

describe('یکتا/صعودی‌سازی زمان', () => {
  it('تکرار زمان با +1ms جدا می‌شود', () => {
    const rows: KLineData[] = [bar(0, 1, 1, 1, 1), bar(0, 2, 2, 2, 2), bar(0, 3, 3, 3, 3)];
    const out = withUniqueTime(rows);
    expect(out[1].timestamp).toBe(out[0].timestamp + 1);
    expect(out[2].timestamp).toBe(out[0].timestamp + 2);
  });
});
