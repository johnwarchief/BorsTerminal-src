import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SidebarSymbol } from '@app/shell/SidebarSymbol';
import { useBoard } from '@features/market/api/useBoard';
import { useFtsCard } from '@features/fundamental/api/useFtsCard';
import { useWorkspace } from '@shared/workspace/store';

vi.mock('@features/market/api/useBoard', () => ({ useBoard: vi.fn() }));
vi.mock('@features/fundamental/api/useFtsCard', () => ({ useFtsCard: vi.fn() }));
vi.mock('@features/chart/ui/ChartPanel', () => ({
  ChartPanel: ({ symbol }: { symbol: string }) => <div data-testid="chart-stub">{symbol}</div>,
}));
vi.mock('@shared/lib/marketHours', () => ({
  effectivePollMs: (ms: number) => ms, sessionPollMs: (ms: number) => ms,
  isMarketOpen: () => true, CLOSED_POLL_MS: 300_000,
}));

const card = {
  status: 'success',
  symbol: 'فولاد',
  sector: 'فلزات اساسی',
  passes: { '1_growth': true, '2_eps_trend': false, '3_gross_margin': null, '4_sales_to_mcap': true, '5_industry': true },
  indicators: {
    '1': { monetary: { monetary_pct: 62.4, threshold: 60 }, volume: { applicable: true } },
    '2': { eps_series: [120, 150, 180], years_available: 3, years_required: 3 },
    '3': { margin_pct: null },
    '4': { sales_to_mcap: 0.41, sales_threshold: 0.33 },
    '5': { label: 'نرخ‌گذاری بازار', sector: 'فلزات اساسی' },
  },
};

beforeEach(() => {
  localStorage.clear();
  useWorkspace.setState({ activeSymbol: null });
  vi.mocked(useBoard).mockReturnValue({
    data: {
      status: 'success', count: 1, live_count: 1, fossil_count: 0,
      meta: { d_even: 20261028 },
      data: [{ symbol: 'فولاد', ins_code: '10', name: 'فولاد مبارکه', p_last: 5000, percent_change: 1.2 }],
    },
    isLoading: false, isError: false,
  } as never);
  vi.mocked(useFtsCard).mockReturnValue({ data: card, isLoading: false, isError: false } as never);
});

afterEach(cleanup);

describe('SidebarSymbol', () => {
  it('asks for a symbol before anything is selected', () => {
    render(<SidebarSymbol collapsed={false} />);
    expect(screen.getByTestId('sidebar-symbol').textContent).toContain('کلیک');
  });

  it('shows the chart and the five fundamental cards for the active symbol', () => {
    useWorkspace.setState({ activeSymbol: '10' });
    render(<SidebarSymbol collapsed={false} />);
    expect(screen.getByTestId('sidebar-symbol').textContent).toContain('فولاد');
    expect(screen.getByTestId('chart-stub').textContent).toBe('فولاد');
    expect(screen.getAllByTestId(/^fundamental-card-/)).toHaveLength(5);
    expect(screen.getByTestId('fundamental-card-1_growth').textContent).toContain('۶۲٫۴');
  });

  it('withholds the verdict on a data gap instead of painting it red', () => {
    useWorkspace.setState({ activeSymbol: '10' });
    render(<SidebarSymbol collapsed={false} />);
    const margin = screen.getByTestId('fundamental-card-3_gross_margin');
    expect(margin.textContent).toContain('—');
    expect(margin.textContent).toContain('نظر نمی‌دهد');
  });

  it('collapses the chart from the sidebar selector and remembers it', () => {
    useWorkspace.setState({ activeSymbol: '10' });
    render(<SidebarSymbol collapsed={false} />);
    fireEvent.click(screen.getByTestId('sidebar-show-chart'));
    expect(screen.getByTestId('sidebar-show-chart').getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByTestId('sidebar-chart')).toBeNull();
    expect(JSON.parse(localStorage.getItem('bors-sidebar-symbol-v1') ?? '{}').chart).toBe(false);
  });

  it('collapses the fundamental cards from the same selector', () => {
    useWorkspace.setState({ activeSymbol: '10' });
    render(<SidebarSymbol collapsed={false} />);
    fireEvent.click(screen.getByTestId('sidebar-show-fundamental'));
    expect(screen.queryByTestId('fundamental-card-1_growth')).toBeNull();
  });

  it('says the data is unavailable when the fundamental call fails', () => {
    useWorkspace.setState({ activeSymbol: '10' });
    vi.mocked(useFtsCard).mockReturnValue({ data: undefined, isLoading: false, isError: true } as never);
    render(<SidebarSymbol collapsed={false} />);
    expect(screen.getByTestId('fundamental-error').textContent).toContain('در دسترس نیست');
  });
});
