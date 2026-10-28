import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { FtsCard } from '@features/fundamental/api/useFtsCard';
import { useFtsCard } from '@features/fundamental/api/useFtsCard';
import { FundamentalCards } from '@features/fundamental/ui/FundamentalCards';
import { FundamentalSummary } from '@features/fundamental/ui/FundamentalSummary';

vi.mock('@features/fundamental/api/useFtsCard', () => ({ useFtsCard: vi.fn() }));

const card = {
  status: 'success',
  symbol: 'فولاد',
  sector: 'فلزات اساسی',
  passes: {
    '1_growth': true,
    '2_eps_trend': true,
    '3_gross_margin': null,
    '4_sales_to_mcap': false,
    '5_industry': true,
  },
  indicators: {
    '1': { monetary: { monetary_pct: 24, threshold: 10, data_gap: false } },
    '2': { eps_series: [10, 12, 14], years_available: 3, years_required: 3 },
    '3': { margin_pct: 18, threshold: 15, band: 'ok', optimal: false },
    '4': { sales_to_mcap: 0.42, sales_threshold: 0.3, available: true, data_gap: false },
    '5': { label: 'رونق', sector: 'فلزات اساسی' },
  },
} as unknown as FtsCard;

beforeEach(() => {
  vi.mocked(useFtsCard).mockReturnValue({
    data: card, isLoading: false, isError: false, error: null,
  } as never);
});

afterEach(cleanup);

describe('FundamentalSummary', () => {
  it('counts pass, reject and abstention without inventing a verdict', () => {
    render(<FundamentalSummary symbol="فولاد" expanded onToggle={() => undefined} />);
    const summary = screen.getByTestId('symbol-fund-summary');
    expect(screen.getByTestId('fund-summary-count').textContent).toContain('۳ از ۵');
    expect(summary.textContent).toContain('۱ بینظر');
    expect(summary.textContent).toContain('۱ رد');
    expect(screen.getByTestId('fund-summary-weakest').textContent).toContain('۴. پتانسیل سود');
    expect(summary.getAttribute('aria-expanded')).toBe('true');
  });

  it('renders a static block when no dock toggle is supplied', () => {
    render(<FundamentalSummary symbol="فولاد" />);
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.getByTestId('symbol-fund-summary')).toBeTruthy();
  });

  it('says the fundamental data is unavailable without breaking the sidebar', () => {
    vi.mocked(useFtsCard).mockReturnValue({
      data: undefined, isLoading: false, isError: true, error: new Error('x'),
    } as never);
    render(<FundamentalSummary symbol="فولاد" />);
    expect(screen.getByTestId('symbol-fund-unavailable').textContent).toContain('در دسترس نیست');
  });
});

describe('FundamentalCards', () => {
  it('shows five compact cards and keeps a null verdict as بینظر', () => {
    render(<FundamentalCards symbol="فولاد" />);
    expect(screen.getAllByTestId(/^fundamental-card-/)).toHaveLength(5);
    const axis3 = screen.getByTestId('fundamental-card-3_gross_margin');
    expect(axis3.textContent).toContain('بینظر');
    expect(axis3.textContent).not.toContain('رد');
    expect(axis3.getAttribute('title')).toContain('۳. حاشیه سود ناخالص');
  });

  it('keeps the chart and board untouched when the request fails', () => {
    vi.mocked(useFtsCard).mockReturnValue({
      data: undefined, isLoading: false, isError: true, error: new Error('x'),
    } as never);
    render(<FundamentalCards symbol="فولاد" />);
    expect(screen.getByTestId('fundamental-error').textContent).toContain('چارت و تابلو');
  });
});
