// تجمیع کندل روزانه → هفتگی/ماهانه؛ KLineCharts خودش بازآرایی نمی‌کند، پس این تنها
// جایی است که نمای غیرروزانه داده‌اش را می‌سازد (برچسبِ اشتباه = کندلِ اشتباه).
import { describe, expect, it } from 'vitest';
import { aggregateCandles, SUPPORTED_TIMEFRAMES } from '@features/technical/nahayatnegar/lib/timeframe';
import type { KLineData } from 'klinecharts';

const t = (s: string) => Date.parse(`${s}T12:00:00Z`);
const bar = (d: string, o: number, h: number, l: number, c: number, v: number) =>
  ({ timestamp: t(d), open: o, high: h, low: l, close: c, volume: v }) as unknown as KLineData;

// شنبه ۲۰۲۶-۰۹-۱۹ … چهارشنبه ۲۰۲۶-۰۹-۲۳ یک هفتهٔ معاملاتیِ ایرانی است (پنجشنبه/جمعه تعطیل)
// و شنبهٔ بعد ۲۰۲۶-۰۹-۲۶ به سطلِ تازه می‌افتد.
const week = [
  bar('2026-09-19', 100, 110, 95, 105, 10),
  bar('2026-09-20', 105, 120, 100, 118, 20),
  bar('2026-09-21', 118, 122, 110, 112, 30),
  bar('2026-09-22', 112, 115, 90, 98, 40),
  bar('2026-09-23', 98, 99, 80, 85, 50),
  bar('2026-09-26', 85, 92, 84, 90, 60),
];

describe('تجمیع بازهٔ زمانی', () => {
  it('«D» همان سری است (بدون کپی‌کردنِ بی‌مورد)', () => {
    expect(aggregateCandles(week, 'D')).toBe(week);
  });

  it('هفتهٔ ایرانی از شنبه شروع می‌شود؛ شنبهٔ بعد سطلِ تازه است', () => {
    const w = aggregateCandles(week, 'W');
    expect(w.map((c) => c.timestamp)).toEqual([t('2026-09-23'), t('2026-09-26')]);
  });

  it('OHLC و حجمِ میلهٔ هفتگی: نخستین open، آخرین close، بیشینه/کمینه و جمع حجم', () => {
    const [first] = aggregateCandles(week, 'W');
    expect(first).toMatchObject({ open: 100, high: 122, low: 80, close: 85, volume: 150 });
  });

  it('ماهانه: هر سطل = یک ماهِ میلادی؛ ماهِ بعد از مرزِ سال هم درست است', () => {
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
