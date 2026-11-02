/**
 * frontend-v2/src/features/technical/model/__tests__/timeframeAggregation.test.ts
 *
 * آزمون‌های موتور تجمیع کندل‌ها بر پایه تقویم کاری بورس تهران:
 * ۱. تجمیع روزانه (1D): بدون تغییر
 * ۲. تجمیع هفتگی (1W): شنبه تا چهارشنبه در قالب یک کندل هفتگی واحد
 * ۳. تجمیع ماهانه (1M): ماه‌های تقویم جلالی (فروردین تا اسفند)
 */

import { describe, it, expect } from 'vitest';
import { aggregateCandles, getTseWeekKey, getJalaliMonthKey } from '../timeframeAggregation';
import type { KLineData } from 'klinecharts';

describe('timeframeAggregation module', () => {
  // نمونه داده کندل‌های یک هفته کاری بورس تهران (شنبه تا چهارشنبه)
  // شنبه ۱۴۰۳/۰۸/۰۵ (2024-10-26)
  // یکشنبه ۱۴۰۳/۰۸/۰۶ (2024-10-27)
  // دوشنبه ۱۴۰۳/۰۸/۰۷ (2024-10-28)
  // سه‌شنبه ۱۴۰۳/۰۸/۰۸ (2024-10-29)
  // چهارشنبه ۱۴۰۳/۰۸/۰۹ (2024-10-30)
  const WEEK_1_CANDLES: KLineData[] = [
    { timestamp: Date.UTC(2024, 9, 26, 6, 0), open: 1000, high: 1050, low: 990, close: 1040, volume: 10000 },
    { timestamp: Date.UTC(2024, 9, 27, 6, 0), open: 1040, high: 1080, low: 1030, close: 1070, volume: 15000 },
    { timestamp: Date.UTC(2024, 9, 28, 6, 0), open: 1070, high: 1100, low: 1050, close: 1060, volume: 20000 },
    { timestamp: Date.UTC(2024, 9, 29, 6, 0), open: 1060, high: 1070, low: 1010, close: 1020, volume: 12000 },
    { timestamp: Date.UTC(2024, 9, 30, 6, 0), open: 1020, high: 1040, low: 980, close: 1030, volume: 18000 },
  ];

  // هفته دوم کاری
  // شنبه ۱۴۰۳/۰۸/۱۲ (2024-11-02)
  // یکشنبه ۱۴۰۳/۰۸/۱۳ (2024-11-03)
  const WEEK_2_CANDLES: KLineData[] = [
    { timestamp: Date.UTC(2024, 10, 2, 6, 0), open: 1030, high: 1090, low: 1020, close: 1085, volume: 25000 },
    { timestamp: Date.UTC(2024, 10, 3, 6, 0), open: 1085, high: 1120, low: 1070, close: 1110, volume: 30000 },
  ];

  it('returns daily candles unmodified for 1D timeframe', () => {
    const aggregated = aggregateCandles(WEEK_1_CANDLES, '1D');
    expect(aggregated).toEqual(WEEK_1_CANDLES);
  });

  it('correctly groups candles of the same TSE week (Saturday to Wednesday) into a single candle', () => {
    const allCandles = [...WEEK_1_CANDLES, ...WEEK_2_CANDLES];
    const aggregated = aggregateCandles(allCandles, '1W');

    expect(aggregated.length).toBe(2);

    // بررسی مشخصات کندل هفته اول
    const w1 = aggregated[0];
    // Open باید قیمت شروع اولین روز کاری هفته (شنبه) باشد
    expect(w1.open).toBe(1000);
    // High باید بیشینه کل جلسات معاملاتی هفته باشد
    expect(w1.high).toBe(1100);
    // Low باید کمینه کل جلسات معاملاتی هفته باشد
    expect(w1.low).toBe(980);
    // Close باید قیمت پایانی آخرین روز کاری هفته (چهارشنبه) باشد
    expect(w1.close).toBe(1030);
    // Volume باید مجموع حجم معاملات کل هفته باشد (10+15+20+12+18 = 75)
    expect(w1.volume).toBe(75000);

    // بررسی مشخصات کندل هفته دوم
    const w2 = aggregated[1];
    expect(w2.open).toBe(1030);
    expect(w2.high).toBe(1120);
    expect(w2.low).toBe(1020);
    expect(w2.close).toBe(1110);
    expect(w2.volume).toBe(55000);
  });

  it('correctly groups candles by Jalali solar month for 1M timeframe', () => {
    // دو کندل در آبان ۱۴۰۳ (2024-10-26 و 2024-11-03) و یک کندل در آذر ۱۴۰۳ (2024-11-25)
    const CANDLES: KLineData[] = [
      { timestamp: Date.UTC(2024, 9, 26, 6, 0), open: 1000, high: 1050, low: 980, close: 1020, volume: 10000 },
      { timestamp: Date.UTC(2024, 10, 3, 6, 0), open: 1020, high: 1100, low: 1000, close: 1080, volume: 20000 },
      // آذر ۱۴۰۳
      { timestamp: Date.UTC(2024, 10, 25, 6, 0), open: 1080, high: 1150, low: 1060, close: 1140, volume: 30000 },
    ];

    const aggregated = aggregateCandles(CANDLES, '1M');
    expect(aggregated.length).toBe(2);

    // ماه اول (آبان)
    expect(aggregated[0].open).toBe(1000);
    expect(aggregated[0].high).toBe(1100);
    expect(aggregated[0].low).toBe(980);
    expect(aggregated[0].close).toBe(1080);
    expect(aggregated[0].volume).toBe(30000);

    // ماه دوم (آذر)
    expect(aggregated[1].open).toBe(1080);
    expect(aggregated[1].high).toBe(1150);
    expect(aggregated[1].low).toBe(1060);
    expect(aggregated[1].close).toBe(1140);
    expect(aggregated[1].volume).toBe(30000);
  });

  it('handles empty or single candle gracefully without errors', () => {
    expect(aggregateCandles([], '1W')).toEqual([]);
    expect(aggregateCandles([], '1M')).toEqual([]);

    const single = [WEEK_1_CANDLES[0]];
    const aggSingle = aggregateCandles(single, '1W');
    expect(aggSingle.length).toBe(1);
    expect(aggSingle[0].open).toBe(single[0].open);
    expect(aggSingle[0].close).toBe(single[0].close);
  });

  it('calculates TSE week keys starting on Saturday', () => {
    // 2024-10-26 is Saturday
    const satKey = getTseWeekKey(Date.UTC(2024, 9, 26, 6, 0));
    // 2024-10-30 is Wednesday of the same week
    const wedKey = getTseWeekKey(Date.UTC(2024, 9, 30, 6, 0));
    expect(satKey).toBe(wedKey);

    // 2024-11-02 is next Saturday
    const nextSatKey = getTseWeekKey(Date.UTC(2024, 10, 2, 6, 0));
    expect(nextSatKey).not.toBe(satKey);

    const mKey1 = getJalaliMonthKey(Date.UTC(2024, 9, 26, 6, 0));
    const mKey2 = getJalaliMonthKey(Date.UTC(2024, 9, 30, 6, 0));
    expect(mKey1).toBe(mKey2);
  });
});
