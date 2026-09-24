// تجمیع کندل روزانه → هفتگی/ماهانه؛ KLineCharts خودش بازآرایی نمی‌کند، پس این تنها
// جایی است که نمای غیرروزانه داده‌اش را می‌سازد (برچسبِ اشتباه = کندلِ اشتباه).
import { describe, expect, it } from 'vitest';
import { aggregateCandles, SUPPORTED_TIMEFRAMES } from '@features/technical/nahayatnegar/lib/timeframe';
import type { KLineData } from 'klinecharts';

// همان چیزی که parseCandleTimestamp می‌سازد: نیمه‌شبِ UTC، بدونِ جزءِ ساعت
const t = (s: string) => Date.parse(`${s}T00:00:00Z`);
const bar = (d: string, o: number, h: number, l: number, c: number, v?: number) =>
  ({ timestamp: t(d), open: o, high: h, low: l, close: c, volume: v }) as unknown as KLineData;

// شنبه ۲۰۲۶-۰۹-۱۹ … پنجشنبهٔ هفتهٔ بعد. پنجشنبه ۲۰۲۶-۰۹-۲۴ آخرین روزِ معاملاتیِ
// هفتهٔ ایرانی است (جمعه تعطیل) و شنبه ۲۰۲۶-۰۹-۲۶ سطلِ تازه می‌خواهد. این ترکیب
// چهار آستانهٔ ممکن را از هم جدا می‌کند: شنبه→[۲۴,۲۶]، پنجشنبه→[۲۳,۲۶]،
// دوشنبه→[۲۰,۲۶]، یکشنبه→[۱۹,۲۶].
const week = [
  bar('2026-09-19', 100, 110, 95, 105, 10),
  bar('2026-09-20', 105, 120, 100, 118, 20),
  bar('2026-09-21', 118, 122, 110, 112, 30),
  bar('2026-09-22', 112, 115, 90, 98, 40),
  bar('2026-09-23', 98, 99, 80, 85, 50),
  bar('2026-09-24', 85, 88, 82, 86, 60),
  bar('2026-09-26', 86, 92, 84, 90, 70),
];

describe('تجمیع بازهٔ زمانی', () => {
  it('«D» همان سری است (بدون کپی‌کردنِ بی‌مورد)', () => {
    expect(aggregateCandles(week, 'D')).toBe(week);
  });

  it('هفته از شنبه شروع می‌شود؛ پنجشنبه در همان سطل و شنبهٔ بعد سطلِ تازه', () => {
    const w = aggregateCandles(week, 'W');
    expect(w.map((c) => c.timestamp)).toEqual([t('2026-09-24'), t('2026-09-26')]);
  });

  it('OHLC و حجمِ میلهٔ هفتگی: نخستین open، آخرین close، بیشینه/کمینه و جمع حجم', () => {
    const [first, second] = aggregateCandles(week, 'W');
    expect(first).toMatchObject({ open: 100, high: 122, low: 80, close: 86, volume: 210 });
    expect(second).toMatchObject({ open: 86, high: 92, low: 84, close: 90, volume: 70 });
  });

  it('هیچ‌داده ≠ صفر: میله‌هایی که حجم ندارند، حجمِ صفر نمی‌گیرند', () => {
    const noVol = week.map((c) => ({ ...c, volume: undefined })) as unknown as KLineData[];
    expect(aggregateCandles(noVol, 'W')[0].volume).toBeUndefined();
    const half = [...week.slice(0, 2), { ...week[2], volume: undefined } as unknown as KLineData];
    expect(aggregateCandles(half, 'W')[0].volume).toBe(30);
  });

  it('ورودیِ بی‌ترتیب هم سریِ صعودیِ یکتا می‌سازد', () => {
    const shuffled = [week[3], week[0], week[6], week[1], week[5], week[2], week[4]];
    const w = aggregateCandles(shuffled, 'W');
    expect(w.map((c) => c.timestamp)).toEqual([t('2026-09-24'), t('2026-09-26')]);
  });

  it('ماهانه: هر سطل یک ماه؛ مرزِ سال هم درست است', () => {
    const m = aggregateCandles(
      [bar('2026-09-19', 100, 110, 95, 105, 10), bar('2026-09-23', 98, 99, 80, 85, 50),
       bar('2026-10-03', 85, 90, 84, 88, 5), bar('2027-01-04', 88, 92, 87, 90, 7)],
      'M'
    );
    expect(m).toHaveLength(3);
    expect(m[0]).toMatchObject({ open: 100, close: 85, volume: 60 });
    expect(m[1]).toMatchObject({ open: 85, close: 88, volume: 5 });
    expect(m[2]).toMatchObject({ open: 88, close: 90 });
  });

  it('سریِ خالی ⇒ خالی؛ تنها یک کندل ⇒ همان کندل', () => {
    expect(aggregateCandles([], 'W')).toEqual([]);
    expect(aggregateCandles([week[0]], 'M')).toHaveLength(1);
  });

  it('فقط سه بازهٔ روزانه/هفتگی/ماهانه پیشنهاد می‌شود — دادهٔ درون‌روزی وجود ندارد', () => {
    expect([...SUPPORTED_TIMEFRAMES]).toEqual(['D', 'W', 'M']);
  });
});
