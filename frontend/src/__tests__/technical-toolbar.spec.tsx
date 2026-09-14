// تست تولبار و بازنمونه‌گیری تایم‌فریم (فاز ۳) — هم‌خوانی با تریدینگ‌ویو
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { FtsToolbar } from '@features/technical/components/FtsToolbar';
import { DrawingToolbar } from '@features/technical/components/DrawingToolbar';
import type { ChartDrawApi } from '@features/technical/components/KLineChartWrapper';
import { useFtsConfigStore } from '@features/technical/stores/ftsConfigStore';
import { resample } from '@features/technical/lib/resample';
import { buildDrawingGroups } from '@features/technical/lib/drawingTools';
import type { KLineData } from '@vendor/klinecharts';

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

describe('تولبار تریدینگ‌ویویی', () => {
  it('انتخاب تایم‌فریم استور را عوض می‌کند', () => {
    render(<FtsToolbar />);
    fireEvent.click(screen.getByRole('button', { name: 'هفتگی' }));
    expect(useFtsConfigStore.getState().timeframe).toBe('week');
    fireEvent.click(screen.getByRole('button', { name: 'روزانه' }));
    expect(useFtsConfigStore.getState().timeframe).toBe('day');
  });

  it('انتخاب نوع چارت و کلید اندیکاتور', () => {
    render(<FtsToolbar />);
    fireEvent.click(screen.getByRole('button', { name: 'خط' }));
    expect(useFtsConfigStore.getState().chartType).toBe('line');
    const before = useFtsConfigStore.getState().showRsi;
    fireEvent.click(screen.getByRole('button', { name: 'RSI(14)' }));
    expect(useFtsConfigStore.getState().showRsi).toBe(!before);
  });

  it('لایه‌های FTS همچنان با تولبار عوض می‌شوند', () => {
    render(<FtsToolbar />);
    const before = useFtsConfigStore.getState().showMAs;
    fireEvent.click(screen.getByRole('button', { name: /مووینگ ها/ }));
    expect(useFtsConfigStore.getState().showMAs).toBe(!before);
  });

  it('مقیاس قیمت و کلیدهای نمایش', () => {
    render(<FtsToolbar />);
    fireEvent.click(screen.getByRole('button', { name: 'لگاریتمی' }));
    expect(useFtsConfigStore.getState().priceScale).toBe('logarithm');
    fireEvent.click(screen.getByRole('button', { name: 'خطی' }));
    expect(useFtsConfigStore.getState().priceScale).toBe('normal');
    const gridBefore = useFtsConfigStore.getState().showGrid;
    fireEvent.click(screen.getByRole('button', { name: /شبکه/ }));
    expect(useFtsConfigStore.getState().showGrid).toBe(!gridBefore);
  });

  it('نوع چارت توخالی مقدار معتبر candle.type می‌دهد', () => {
    render(<FtsToolbar />);
    fireEvent.click(screen.getByRole('button', { name: 'کندل توخالی' }));
    expect(useFtsConfigStore.getState().chartType).toBe('candle_stroke');
    fireEvent.click(screen.getByRole('button', { name: 'کندل' }));
    expect(useFtsConfigStore.getState().chartType).toBe('candle_solid');
  });
});

describe('کاتالوگ و ریل ابزارهای ترسیم', () => {
  afterEach(() => {
    (window as unknown as { klinecharts?: unknown }).klinecharts = undefined;
  });

  it('buildDrawingGroups فقط ابزارهای پشتیبانی‌شده را نگه می‌دارد', () => {
    const g = buildDrawingGroups(['straightLine', 'fibonacciLine', 'brush']);
    expect(g.map((x) => x.label)).toEqual(['خطوط', 'فیبوناچی', 'حاشیه‌نویسی']);
    expect(g[0].tools.map((t) => t.name)).toEqual(['straightLine']);
    expect(buildDrawingGroups([])).toEqual([]);
  });

  it('ریل، flyout را باز و startDraw را صدا می‌زند', () => {
    (window as unknown as { klinecharts: unknown }).klinecharts = {
      getSupportedOverlays: () => ['straightLine', 'fibonacciLine'],
    };
    const startDraw = vi.fn();
    const api = { startDraw, undo: vi.fn(), redo: vi.fn(), clearDrawings: vi.fn(), hideDrawings: vi.fn() } as ChartDrawApi;
    render(<DrawingToolbar api={api} />);
    fireEvent.click(screen.getByTestId('draw-group-straightLine'));
    fireEvent.click(screen.getByTestId('draw-straightLine'));
    expect(startDraw).toHaveBeenCalledWith('straightLine');
    // flyout بعد از انتخاب بسته می‌شود
    expect(screen.queryByTestId('draw-flyout')).toBeNull();
  });

  it('دکمه‌های undo/clear/pنهان بدون API غیرفعال‌اند', () => {
    (window as unknown as { klinecharts: unknown }).klinecharts = { getSupportedOverlays: () => ['straightLine'] };
    render(<DrawingToolbar api={null} />);
    expect(screen.getByTestId('draw-undo')).toBeDisabled();
    expect(screen.getByTestId('draw-clear')).toBeDisabled();
  });
});
