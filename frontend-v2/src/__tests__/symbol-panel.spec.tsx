import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { MarketRow } from '@shared/types/market';
import { SymbolPanel } from '@features/market/panels/SymbolPanel';

vi.mock('@features/chart/ui/ChartPanel', () => ({
  ChartPanel: ({ symbol }: { symbol: string }) => <div data-testid="chart-stub">{symbol}</div>,
}));
vi.mock('@features/market/components/OrderBookFive', () => ({
  OrderBookFive: ({ symbol }: { symbol: string }) => <div data-testid="book-stub">{symbol}</div>,
}));
vi.mock('@features/market/components/TapeHistoryPanel', () => ({
  TapeHistoryPanel: ({ symbol }: { symbol: string }) => <div data-testid="history-stub">{symbol}</div>,
}));
vi.mock('@features/market/components/WatchlistButton', () => ({
  WatchlistButton: () => <button type="button">واچ‌لیست</button>,
}));

const row = {
  symbol: 'الف', ins_code: '10', name: 'شرکت الف',
  p_last: 112, p_closing: 110, percent_change: 10, q_tot_cap: 6e9, q_tot_tran: 2e6,
  pe: 7.4, mcap: 1.2e12, p_min: 100, p_max: 115,
} as MarketRow;

function mount(props: Partial<Parameters<typeof SymbolPanel>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SymbolPanel row={row} boardDay={20261028} chartOpen onToggleChart={() => {}} {...props} />
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe('SymbolPanel', () => {
  it('shows an honest empty state', () => {
    mount({ row: null });
    expect(screen.getByTestId('symbol-empty').textContent).toContain('نمادی');
  });

  it('renders the key numbers and the chart', () => {
    mount();
    expect(screen.getByTestId('symbol-title').textContent).toContain('الف');
    expect(screen.getByTestId('symbol-pe').textContent).toContain('۷');
    expect(screen.getByTestId('chart-stub')).toBeTruthy();
  });

  it('hides the chart when collapsed', () => {
    mount({ chartOpen: false });
    expect(screen.queryByTestId('chart-stub')).toBeNull();
    expect(screen.getByTestId('symbol-chart-toggle').textContent).toContain('باز');
  });

  it('switches between depth, history and fundamental tabs', () => {
    mount();
    expect(screen.getByTestId('book-stub')).toBeTruthy();
    fireEvent.click(screen.getByTestId('symbol-tab-history'));
    expect(screen.getByTestId('history-stub')).toBeTruthy();
    fireEvent.click(screen.getByTestId('symbol-tab-fundamental'));
    expect(screen.getByTestId('symbol-fundamental-empty').textContent).toContain('وصل نشده');
  });
});
