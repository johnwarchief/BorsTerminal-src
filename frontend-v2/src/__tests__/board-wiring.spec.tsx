import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchBoard } from '@features/market/api/boardFeed';
import { useBoard } from '@features/market/api/useBoard';
import { useMarketPrefs } from '@features/market/stores/prefs';

vi.mock('@features/market/api/boardFeed', () => ({ fetchBoard: vi.fn() }));
vi.mock('@shared/lib/marketHours', () => ({ effectivePollMs: (ms: number) => ms }));

const mockedFetchBoard = vi.mocked(fetchBoard);

beforeEach(() => {
  localStorage.clear();
  useMarketPrefs.persist.clearStorage();
  useMarketPrefs.setState(useMarketPrefs.getInitialState(), true);
});

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe('market preferences', () => {
  it('toggles each quick filter without dropping the other selections', () => {
    useMarketPrefs.getState().toggleQuickFilter('f_clock');
    useMarketPrefs.getState().toggleQuickFilter('f_susp');
    expect(useMarketPrefs.getState().quickFilters).toEqual(['f_clock', 'f_susp']);

    useMarketPrefs.getState().toggleQuickFilter('f_clock');
    expect(useMarketPrefs.getState().quickFilters).toEqual(['f_susp']);
  });

  it('stores the selected AND/OR logic', () => {
    useMarketPrefs.getState().setQuickLogic('or');
    expect(useMarketPrefs.getState().quickLogic).toBe('or');
  });

  it('stores complete board filters and the polling interval', () => {
    useMarketPrefs.getState().setFilters({ sector: 'خودرو', volRatioOn: true });
    useMarketPrefs.getState().setPollMs(15_000);
    expect(useMarketPrefs.getState().filters.sector).toBe('خودرو');
    expect(useMarketPrefs.getState().filters.volRatioOn).toBe(true);
    expect(useMarketPrefs.getState().pollMs).toBe(15_000);
  });
});

describe('useBoard', () => {
  it('reads through the delta-aware feed and polls at the requested interval', async () => {
    vi.useFakeTimers();
    mockedFetchBoard.mockResolvedValue({
      status: 'success', data: [], count: 0, live_count: 0, fossil_count: 0, rev: 1, rev_at: 1,
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );

    renderHook(() => useBoard(5_000), { wrapper });
    await act(async () => { await Promise.resolve(); });
    expect(mockedFetchBoard).toHaveBeenCalledTimes(1);

    await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
    expect(mockedFetchBoard).toHaveBeenCalledTimes(2);
    client.clear();
  });
});
