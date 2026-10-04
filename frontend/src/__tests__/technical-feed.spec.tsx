// تست خوراک کندل، اولویتِ وضعیت FTS و قانونِ عبور از گیت
// (تولبار و رپر قدیمی از برنامه بیرون رفتند؛ نوار ابزارِ زنده در
// features/technical/nahayatnegar و پوششش در specهای همان محله است.)
import { describe, expect, it } from 'vitest';
import { toKLineData } from '@features/technical/api/useCandleFeed';
import { gatePassFromCard } from '@features/technical/api/useFundGate';
import { resolveFtsStatusView } from '@features/technical/components/FtsStatusCard';

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
  it('وضعیت از خودِ موتور می‌آید، نه از حدسِ کامپوننت؛ گیت بر همه غالب است', () => {
    const st = (code: string, text: string) => ({ payload: { status: { code, text } } }) as never;
    expect(resolveFtsStatusView(st('entry_trigger', 'تریگرِ فعال'), true).code).toBe('gate_rejected');
    expect(resolveFtsStatusView(st('entry_trigger', 'تریگرِ فعال: جت'), false).code).toBe('entry_trigger');
    // رأیِ دورِ J: وتوی هفتگی با جتِ فعال، «پرواز» نمی‌شود
    const veto = resolveFtsStatusView(st('weekly_veto', 'وتوی تایم هفتگی'), false);
    expect(veto.code).toBe('weekly_veto');
    expect(veto.text).toContain('وتوی');
    expect(resolveFtsStatusView(st('hard_stop', 'حدِ ضرر'), false).tone).toBe('red');
    expect(resolveFtsStatusView(st('warning', 'هشدار'), false).tone).toBe('yellow');
    // بی‌وضعیتِ موتور هیچ متنِ ثابتی ساخته نمی‌شود
    const none = resolveFtsStatusView({ payload: {} } as never, false);
    expect(none.code).toBe('insufficient');
    expect(none.text).toContain('وضعیتِ عمومی');
  });

  it('قانون عبور گیت: بدون حذف و امتیاز دست کم 3', () => {
    expect(gatePassFromCard(null)).toBeNull();
    expect(gatePassFromCard({ excluded: true, score: 5 })).toBe(false);
    expect(gatePassFromCard({ excluded: false, score: 2 })).toBe(false);
    expect(gatePassFromCard({ excluded: false, score: 3 })).toBe(true);
  });
});
