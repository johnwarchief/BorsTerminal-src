import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { toKlineBars, useChart } from '@features/chart/api/useChart';
import { ChartPanel } from '@features/chart/ui/ChartPanel';

vi.mock('@features/chart/api/useChart', async (original) => {
  const mod = await original<typeof import('@features/chart/api/useChart')>();
  return { ...mod, useChart: vi.fn() };
});

const charts: { setDataLoader: ReturnType<typeof vi.fn>; setSymbol: ReturnType<typeof vi.fn>; resetData: ReturnType<typeof vi.fn> }[] = [];
vi.mock('klinecharts', () => ({
  init: () => {
    const chart = { setStyles: vi.fn(), setDataLoader: vi.fn(), setSymbol: vi.fn(), setPeriod: vi.fn(), resetData: vi.fn(), resize: vi.fn() };
    charts.push(chart as never);
    return chart;
  },
  dispose: vi.fn(),
}));

function query(state: Record<string, unknown>) {
  return { data: undefined, isLoading: false, isError: false, error: null, ...state } as never;
}

beforeEach(() => {
  charts.length = 0;
  vi.mocked(useChart).mockReturnValue(query({ data: undefined }));
});

afterEach(cleanup);

describe('chart', () => {
  it('maps candles to kline bars in ascending order', () => {
    const bars = toKlineBars([
      { time: '2026-10-28', open: 10, high: 12, low: 9, close: 11, volume: 100 },
      { time: '2026-10-27', open: 9, high: 10, low: 8, close: 10, volume: 90 },
    ]);
    expect(bars.map((bar) => bar.close)).toEqual([10, 11]);
    expect(bars[1]).toMatchObject({ open: 10, high: 12, low: 9, close: 11, volume: 100 });
  });

  it('shows a loading state', () => {
    vi.mocked(useChart).mockReturnValue(query({ isLoading: true }));
    render(<ChartPanel symbol="الف" />);
    expect(screen.getByTestId('chart-loading')).toBeTruthy();
  });

  it('shows an honest empty state', () => {
    vi.mocked(useChart).mockReturnValue(query({ data: { status: 'success', candles: [] } }));
    render(<ChartPanel symbol="الف" />);
    expect(screen.getByTestId('chart-empty').textContent).toContain('کندلی');
  });

  it('shows the error reason', () => {
    vi.mocked(useChart).mockReturnValue(query({ isError: true, error: new Error('۵۰۲') }));
    render(<ChartPanel symbol="الف" />);
    expect(screen.getByTestId('chart-error').textContent).toContain('۵۰۲');
  });

  it('feeds the mapped bars through the v10 data loader', async () => {
    vi.mocked(useChart).mockReturnValue(query({
      data: {
        status: 'success',
        candles: [
          { time: '2026-10-27', open: 9, high: 10, low: 8, close: 10, volume: 90 },
          { time: '2026-10-28', open: 10, high: 12, low: 9, close: 11, volume: 100 },
        ],
      },
    }));
    render(<ChartPanel symbol="الف" />);

    const chart = await waitFor(() => {
      expect(charts.length).toBe(1);
      return charts[0]!;
    });
    const loader = chart.setDataLoader.mock.calls[0]![0] as {
      getBars: (params: { callback: (data: unknown[], more?: boolean) => void }) => void;
    };
    const callback = vi.fn();
    loader.getBars({ callback });
    expect(callback).toHaveBeenCalledWith(
      [expect.objectContaining({ close: 10 }), expect.objectContaining({ close: 11 })],
      false,
    );
    expect(chart.setSymbol).toHaveBeenCalledWith(expect.objectContaining({ ticker: 'الف' }));
  });
});
