// تست خوراک کندل، اولویتِ وضعیت FTS و قانونِ عبور از گیت
// (تولبار و رپر قدیمی از برنامه بیرون رفتند؛ نوار ابزارِ زنده در
// features/technical/nahayatnegar و پوششش در specهای همان محله است.)
import { describe, expect, it } from 'vitest';
import { toKLineData } from '@features/technical/api/useCandleFeed';
import { gatePassFromCard } from '@features/technical/api/useFundGate';
import { resolveFtsStatus } from '@features/technical/components/FtsStatusCard';

describe('خوراک کندل', () => {
  it('تبدیل تاریخ و مرتب سازی', () => {
    const out = toKLineData(
      [
        { time: '2025-03-22', open: 10, high: 12, low: 9, close: 11 },
        { time: '2025-03-21', open: 9, high: 11, low: 8, close: 10 },
      ],
      [{ time: '2025-03-21', value: 500 }],
    );
    expect(out).toHaveLength(2);
    expect(out[0].timestamp).toBeLessThan(out[1].timestamp);
    expect(out[0].volume).toBe(500);
    expect(out[1].volume).toBe(0);
  });

  it('ردیف خراب حذف می شود', () => {
    const out = toKLineData(
      [
        { time: 'bad-date', open: 10, high: 12, low: 9, close: 11 },
        { time: '2025-03-21', open: 0, high: 0, low: 0, close: 0 },
      ],
      [],
    );
    expect(out).toEqual([]);
  });
});

describe('وضعیت FTS', () => {
  it('اولویت وضعیت: گیت سپس پرواز سپس هشدار', () => {
    const jet = { payload: { setups: ['breakout'] } } as never;
    const choch = { payload: { setups: ['choch'] } } as never;
    expect(resolveFtsStatus(jet, true)).toBe('gate_rejected');
    expect(resolveFtsStatus(jet, false)).toBe('jet_active');
    expect(resolveFtsStatus(choch, false)).toBe('choch_warning');
    expect(resolveFtsStatus(null, false)).toBe('awaiting_break');
  });

  it('قانون عبور گیت: بدون حذف و امتیاز دست کم 3', () => {
    expect(gatePassFromCard(null)).toBeNull();
    expect(gatePassFromCard({ excluded: true, score: 5 })).toBe(false);
    expect(gatePassFromCard({ excluded: false, score: 2 })).toBe(false);
    expect(gatePassFromCard({ excluded: false, score: 3 })).toBe(true);
  });
});
