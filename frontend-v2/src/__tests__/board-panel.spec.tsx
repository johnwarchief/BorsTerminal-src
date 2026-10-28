import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarketFeed, MarketRow } from '@shared/types/market';
import { BoardPanel } from '@features/market/panels/BoardPanel';
import { useBoard } from '@features/market/api/useBoard';

vi.mock('@features/market/api/useBoard', () => ({ useBoard: vi.fn() }));
vi.mock('@tanstack/react-virtual', async (original) => {
  const mod = await original<typeof import('@tanstack/react-virtual')>();
  return {
    ...mod,
    useVirtualizer: ({ count }: { count: number }) => ({
      getVirtualItems: () => Array.from({ length: count }, (_, index) => ({
        index, key: index, start: index * 30, size: 30,
      })),
      getTotalSize: () => count * 30,
      measureElement: () => {},
      measure: () => {},
    }),
  };
});
vi.mock('@shared/lib/marketHours', () => ({
  effectivePollMs: (ms: number) => ms, sessionPollMs: (ms: number) => ms,
  isMarketOpen: () => true, CLOSED_POLL_MS: 300_000,
}));

const rows: MarketRow[] = [
  {
    symbol: 'الف', ins_code: '10', name: 'الف', price_yesterday: 100, p_closing: 110,
    percent_change: 10, q_tot_cap: 5_000_000_000, q_tot_tran: 2_000_000,
  } as MarketRow,
];

const feed = {
  status: 'ok', rev: 1, count: 1, live_count: 1, fossil_count: 0,
  meta: { d_even: 20261028, last_sync: '2026-10-28 12:00:00' }, data: rows,
} as MarketFeed;

function mount(props: Partial<Parameters<typeof BoardPanel>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <BoardPanel selectedKey={null} onSelect={() => {}} onActivate={() => {}} {...props} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.mocked(useBoard).mockReturnValue({
    data: feed, isLoading: false, isError: false, isFetching: false,
    dataUpdatedAt: Date.now(), refetch: vi.fn(), error: null, status: 'success',
  } as never);
});

afterEach(cleanup);

describe('BoardPanel', () => {
  it('renders the row count footer', () => {
    mount();
    expect(screen.getByTestId('board-count').textContent).toContain('۱');
  });

  it('reports the row identity and board day on select', () => {
    const onSelect = vi.fn();
    mount({ onSelect });
    fireEvent.click(screen.getAllByTestId('board-row')[0]!);
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ ins_code: '10' }), 20261028);
  });
});
