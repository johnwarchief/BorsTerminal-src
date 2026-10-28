import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { FtsCard } from '@features/fundamental/api/useFtsCard';
import { useFtsCard } from '@features/fundamental/api/useFtsCard';
import { useMa } from '@features/market/api/useMa';
import type { MarketRow } from '@shared/types/market';
import { SymbolSidebar } from '@app/shell/SymbolSidebar';

vi.mock('@features/market/api/useMa', async (original) => {
  const mod = await original<typeof import('@features/market/api/useMa')>();
  return { ...mod, useMa: vi.fn() };
});
vi.mock('@features/fundamental/api/useFtsCard', () => ({ useFtsCard: vi.fn() }));
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
  p_last: 112, p_closing: 110, percent_change: 1.8,
  q_tot_cap: 6e9, q_tot_tran: 2e6, z_tot_tran: 1200,
  pe: 7.4, mcap: 1.2e12, p_min: 100, p_max: 115,
  retail_buy_pct: 62.4,
  f_smart: true, f_legal: false,
} as MarketRow;

const series = (values: number[]): Array<[string, number | null]> =>
  values.map((value, index) => [`2026-10-0${index + 1}`, value]);

const card = {
  status: 'success', symbol: 'الف',
  passes: { '1_growth': true, '2_eps_trend': true, '3_gross_margin': null, '4_sales_to_mcap': false, '5_industry': true },
  indicators: {
    '1': { monetary: { monetary_pct: 20, threshold: 10, data_gap: false } },
    '2': { eps_series: [10, 12, 14], years_available: 3, years_required: 3 },
    '3': { margin_pct: 18 },
    '4': { sales_to_mcap: 0.4, available: true, data_gap: false },
    '5': { label: 'رونق' },
  },
} as unknown as FtsCard;

beforeEach(() => {
  vi.mocked(useMa).mockReturnValue({
    data: { status: 'ok', symbol: 'الف', ma: { ma20: series([100, 101, 102, 103, 104, 105]), ma50: series([90, 90, 90, 90, 90, 90]) } },
    isLoading: false, isError: false, error: null,
  } as never);
  vi.mocked(useFtsCard).mockReturnValue({
    data: card, isLoading: false, isError: false, error: null,
  } as never);
});

afterEach(cleanup);

function mount(patch: Partial<Parameters<typeof SymbolSidebar>[0]> = {}) {
  return render(
    <SymbolSidebar
      row={row}
      symbolKey="10"
      boardDay={20261028}
      chartOpen
      fundamentalsOpen
      onToggleChart={() => undefined}
      onToggleFundamentals={() => undefined}
      {...patch}
    />,
  );
}

describe('SymbolSidebar', () => {
  it('shows the honest empty state without asking for data', () => {
    mount({ symbolKey: null, row: null });
    expect(screen.getByTestId('symbol-sidebar').textContent).toContain('نمادی');
    expect(vi.mocked(useMa)).not.toHaveBeenCalled();
  });

  it('separates a symbol that is absent from the board from a missing selection', () => {
    mount({ symbolKey: '99', row: null });
    expect(screen.getByTestId('symbol-not-in-board').textContent).toContain('در تابلو نیست');
    expect(vi.mocked(useMa)).not.toHaveBeenCalled();
  });

  it('renders the at-a-glance page: stats, seven chips, technical and fundamental summaries', () => {
    mount();
    expect(screen.getByTestId('symbol-title').textContent).toContain('الف');
    expect(screen.getByTestId('symbol-price').textContent).toContain('۱۱۲');
    expect(screen.getAllByTestId(/^symbol-stat-/)).toHaveLength(6);
    expect(screen.getAllByTestId(/^symbol-tape-/)).toHaveLength(7);
    expect(screen.getByTestId('tech-ma20').textContent).toContain('۱۰۵');
    expect(screen.getByTestId('tech-trend').textContent).toContain('صعودی');
    expect(screen.getByTestId('fund-summary-count').textContent).toContain('۳ از ۵');
    expect(screen.getByTestId('book-stub')).toBeTruthy();
  });

  it('says the technical block is unavailable without hiding the rest', () => {
    vi.mocked(useMa).mockReturnValue({
      data: { status: 'error', message: 'x' }, isLoading: false, isError: false, error: null,
    } as never);
    mount();
    expect(screen.getByTestId('tech-unavailable').textContent).toContain('در دسترس نیست');
    expect(screen.getAllByTestId(/^symbol-tape-/)).toHaveLength(7);
  });

  it('switches between the depth and history tabs', () => {
    mount();
    fireEvent.click(screen.getByTestId('symbol-tab-history'));
    expect(screen.getByTestId('history-stub')).toBeTruthy();
  });

  it('hands the dock toggles to the caller and reports their state', () => {
    const onToggleChart = vi.fn();
    const onToggleFundamentals = vi.fn();
    mount({ chartOpen: false, onToggleChart, onToggleFundamentals });
    const chart = screen.getByTestId('dock-toggle-chart');
    expect(chart.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(chart);
    fireEvent.click(screen.getByTestId('dock-toggle-fundamental'));
    expect(onToggleChart).toHaveBeenCalledTimes(1);
    expect(onToggleFundamentals).toHaveBeenCalledTimes(1);
  });

  it('collapses to a rail with one open button', () => {
    const onToggleCollapsed = vi.fn();
    mount({ collapsed: true, onToggleCollapsed });
    expect(screen.queryByTestId('symbol-title')).toBeNull();
    fireEvent.click(screen.getByTestId('symbol-rail-open'));
    expect(onToggleCollapsed).toHaveBeenCalledTimes(1);
  });

  it('keeps the chart inside the narrow variant and drops the dock keys', () => {
    const onToggleChart = vi.fn();
    const view = mount({ variant: 'narrow', chartOpen: false, onToggleChart });
    expect(screen.queryByTestId('dock-toggle-chart')).toBeNull();
    expect(screen.queryByTestId('chart-stub')).toBeNull();
    fireEvent.click(screen.getByTestId('symbol-chart-toggle'));
    expect(onToggleChart).toHaveBeenCalledTimes(1);
    view.rerender(
      <SymbolSidebar row={row} symbolKey="10" boardDay={null} variant="narrow"
        chartOpen fundamentalsOpen onToggleChart={() => undefined} onToggleFundamentals={() => undefined} />,
    );
    expect(screen.getByTestId('chart-stub').textContent).toBe('الف');
  });
});
