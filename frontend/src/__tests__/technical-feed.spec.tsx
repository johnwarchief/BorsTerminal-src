// تست خوراک کندل و رفتار رپر و تولبار FTS
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { toKLineData } from '@features/technical/api/useCandleFeed';
import { gatePassFromCard } from '@features/technical/api/useFundGate';
import { KLineChartWrapper } from '@features/technical/components/KLineChartWrapper';
import { FtsToolbar } from '@features/technical/components/FtsToolbar';
import { resolveFtsStatus } from '@features/technical/components/FtsStatusCard';
import { useFtsConfigStore } from '@features/technical/stores/ftsConfigStore';

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

describe('رپر چارت', () => {
  it('بدون کتابخانه پیام تمیز نشان می دهد', () => {
    render(
      <KLineChartWrapper
        data={[]}
        palette={{ up: '#10b981', down: '#f43f5e', grid: '#000', text: '#fff', background: '#000' }}
      />,
    );
    expect(screen.getByText('کتابخانه چارت بارگذاری نشد؛ صفحه را تازه کن')).toBeInTheDocument();
  });
});

describe('تولبار و وضعیت FTS', () => {
  it('کلیدها وضعیت استور را عوض می کنند', () => {
    render(<FtsToolbar />);
    const btn = screen.getByRole('button', { name: /مووینگ ها/ });
    const before = useFtsConfigStore.getState().showMAs;
    fireEvent.click(btn);
    expect(useFtsConfigStore.getState().showMAs).toBe(!before);
    fireEvent.click(btn);
    expect(useFtsConfigStore.getState().showMAs).toBe(before);
  });

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
