// تست موتور تعدیلِ چارت نهایت‌نگر (T-17): منبع واحد = نسبت گسست قیمت پایهٔ سرور ({date,ratio})
import { describe, expect, it } from 'vitest';
import {
  applyAdjustmentToCandles,
  mapBackendAdjustEvents,
} from '@features/technical/nahayatnegar/lib/adjustments';
import type { KLineData } from 'klinecharts';

const t = (s: string) => Date.parse(`${s}T00:00:00Z`);

const candles = [
  { timestamp: t('2020-01-08'), open: 100, high: 110, low: 95, close: 100, volume: 1000 },
  { timestamp: t('2020-01-09'), open: 100, high: 110, low: 95, close: 100, volume: 1000 },
  { timestamp: t('2020-01-12'), open: 50, high: 55, low: 48, close: 50, volume: 2000 },
] as unknown as KLineData[];

const events = mapBackendAdjustEvents([{ date: '2020-01-11', ratio: 0.5 }]);

describe('تعدیل چارت نهایت‌نگر (نسبت سرور)', () => {
  it('«بدون تعدیل» ⇒ قیمت خام دست‌نخورده', () => {
    const out = applyAdjustmentToCandles(candles, events, 'none');
    expect(out[0].close).toBe(100);
    expect(out[2].close).toBe(50);
  });

  it('تعدیل ترکیبی ⇒ کندل‌های پیش از رویداد در نسبت ضرب، حجم تقسیم، پس از رویداد خام', () => {
    const out = applyAdjustmentToCandles(candles, events, 'combined');
    expect(out[0].close).toBe(50);       // 100 × 0.5
    expect(out[1].close).toBe(50);
    expect(out[0].volume).toBe(2000);    // 1000 ÷ 0.5
    expect(out[2].close).toBe(50);       // کندلِ پس از رویداد دست‌نخورده
    expect(out[2].volume).toBe(2000);
  });

  it('نگاشت رویدادِ سرور نسبت را حفظ می‌کند و timestamp درست می‌سازد', () => {
    expect(events).toHaveLength(1);
    expect(events[0].ratio).toBe(0.5);
    expect(events[0].timestamp).toBe(t('2020-01-11'));
  });

  it('بدون رویداد ⇒ همان سری (بدون تغییر)', () => {
    const out = applyAdjustmentToCandles(candles, [], 'combined');
    expect(out.map((c) => c.close)).toEqual([100, 100, 50]);
  });
});
