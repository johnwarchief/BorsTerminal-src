import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarketFeed } from '@shared/types/market';
import { useBoard } from '@features/market/api/useBoard';
import { MarketPage } from '@features/market/routes/MarketPage';
import { useMarketPrefs } from '@features/market/stores/prefs';

vi.mock('@features/market/api/useBoard', () => ({ useBoard: vi.fn() }));
vi.mock('@features/market/api/useMarketSnapshot', () => ({
  useMarketSnapshot: () => ({ data: undefined, isLoading: false, isError: false }),
}));
vi.mock('@features/chart/ui/ChartPanel', () => ({
  ChartPanel: ({ symbol }: { symbol: string }) => <div data-testid="chart-stub">{symbol}</div>,
}));
vi.mock('@shared/lib/marketHours', () => ({
  effectivePollMs: (ms: number) => ms,
  isMarketOpen: () => true,
  CLOSED_POLL_MS: 300_000,
}));

const mockedUseBoard = vi.mocked(useBoard);

const feed: MarketFeed = {
  status: 'success',
  data: [
    { ins_code: '1', symbol: 'فولاد', name: 'فولاد مبارکه', sector_name: 'فلزات اساسی', is_live: true, percent_change: 5.2, vol_ratio: 4, f_clock: true, f_susp: true },
    { ins_code: '2', symbol: 'خساپا', name: 'سایپا', sector_name: 'خودرو', is_live: true, percent_change: -1, vol_ratio: 2, f_clock: true, f_susp: false },
    { ins_code: '3', symbol: 'وتجارت', name: 'سرمایه‌گذاری تجارت', sector_name: 'سرمایه‌گذاری', is_live: false, percent_change: 6, vol_ratio: 5, f_clock: true, f_susp: true },
    { ins_code: '4', symbol: 'شپنا', name: 'پالایش اصفهان', sector_name: 'فرآورده‌های نفتی', is_live: true, percent_change: 0, vol_ratio: null, f_clock: null, f_susp: null },
    { ins_code: '5', symbol: 'فولاد1', name: 'فولاد عمده', sector_name: 'فلزات اساسی', is_live: true, percent_change: 5.5, vol_ratio: 4.5, f_clock: true, f_susp: true },
  ],
  count: 5,
  live_count: 4,
  fossil_count: 1,
  rev: 8,
  rev_at: 1_000,
  meta: null,
};

beforeEach(() => {
  localStorage.clear();
  useMarketPrefs.persist.clearStorage();
  useMarketPrefs.setState(useMarketPrefs.getInitialState(), true);
  mockedUseBoard.mockReturnValue({
    data: feed,
    dataUpdatedAt: 400_000,
    status: 'success',
    isError: false,
    isLoading: false,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useBoard>);
  vi.spyOn(Date, 'now').mockReturnValue(400_000);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

describe('market page integration', () => {
  it('uses canonical multi-tape AND/OR verdicts for the visible board', () => {
    useMarketPrefs.setState({ quickFilters: ['f_clock', 'f_susp'], quickLogic: 'and' });
    render(<MarketPage />);
    expect(screen.getByTestId('board-count').textContent).toContain('۱');

    fireEvent.click(screen.getByRole('button', { name: 'یا' }));
    expect(useMarketPrefs.getState().quickLogic).toBe('or');
    expect(screen.getByTestId('board-count').textContent).toContain('۲');
  });

  it('applies the complete filter panel to the board evaluator', () => {
    render(<MarketPage />);
    fireEvent.click(screen.getByTestId('filters-btn'));
    fireEvent.click(screen.getByTestId('vol-ratio-toggle'));
    expect(useMarketPrefs.getState().filters.volRatioOn).toBe(true);
    expect(screen.getByTestId('board-count').textContent).toContain('۱');

    expect(screen.getByLabelText('فیلتر صنعت')).toBeTruthy();
    expect(screen.getByTestId('live-only-toggle')).toBeTruthy();
    expect(screen.getByTestId('numeric-suffix-toggle')).toBeTruthy();
    expect(screen.getByLabelText('جهت تغییر')).toBeTruthy();
    expect(screen.getByTestId('exit-accum-toggle')).toBeTruthy();
    expect(screen.getByLabelText('بازه به‌روزرسانی')).toBeTruthy();
  });

  it('names stalled market data separately from a successful HTTP response', () => {
    render(<MarketPage />);
    expect(screen.getByTestId('feed-state').textContent).toContain('ایستاده');
  });
});
