import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FundamentalScreenTable } from '@features/fundamental/ui/FundamentalScreenTable';
import { useFundamentalPrefs } from '@features/fundamental/stores/prefs';
import { resetExcludeAxes } from '@features/fundamental/lib/exclusionFilter';
import type { ScreenerCoreRow } from '@features/fundamental/api/useScreenerCore';

const rows: ScreenerCoreRow[] = [
  { symbol: 'رنيك', name: 'جنرال مکانیک', sector_name: 'خدمات فنی', score: 3, verdict: 'WATCH',
    i1_pass: false, i1_na: false, i2_pass: true, i2_na: false, i3_pass: false, i3_na: false,
    i4_pass: true, i4_na: false, i5_pass: true, i5_na: false,
    rev_growth: 45.9, eps_series: [1119, 1615, 1672], eps_years_available: 3,
    gross_margin: 11.5, sales_to_mcap: 1.15, profit_potential_pct: 13.2, pricing_mode: 'neutral' },
  { symbol: 'وبملت', name: 'بانک ملت', sector_name: 'بانک‌ها', score: 2, verdict: 'REJECT',
    i1_pass: true, i1_na: false, i2_pass: false, i2_na: false, i3_pass: null, i3_na: true,
    i4_pass: null, i4_na: true, i5_pass: true, i5_na: false,
    rev_growth: 83.5, eps_series: [1425, 454, 456], eps_years_available: 3,
    gross_margin: null, sales_to_mcap: null, profit_potential_pct: null, pricing_mode: 'free' },
];
const thresholds = { growth_min: 60, margin_min: 40, v10_sales_to_mcap_min: 0.33, profit_potential_min: 40, v10_eps_years: 3 };

beforeEach(() => {
  resetExcludeAxes();
  useFundamentalPrefs.setState({ density: 'comfortable', surface: 'paper', sortKey: 'score', sortDir: 'desc' });
});
afterEach(cleanup);

describe('fundamental table visual', () => {
  it('renders five axis headers and values', () => {
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf="۱۴۰۵/۰۸/۱۳" />);
    expect(screen.getByRole('table', { name: 'جدول بنیادی' })).toBeTruthy();
    for (const name of ['رشد فروش', 'سودآوری ۳ساله', 'حاشیهٔ ناخالص', 'فروش / ارزش', 'نرخ‌گذاری صنعت']) expect(screen.getByText(name)).toBeTruthy();
    expect(screen.getByText('+۴۵٫۹٪')).toBeTruthy();
    expect(screen.getByText('۱٫۱۵')).toBeTruthy();
  });
  it('shows charts only in comfortable mode', () => {
    const { container, rerender } = render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(container.querySelectorAll('svg[role="img"]').length).toBeGreaterThan(0);
    act(() => useFundamentalPrefs.setState({ density: 'compact' }));
    rerender(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(container.querySelectorAll('svg[role="img"]').length).toBe(0);
  });
  it('distinguishes N/A/unknown and bank badges', () => {
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(screen.getByTestId('fundamental-bank-وبملت')).toBeTruthy();
    expect(document.querySelectorAll('.fd-status--na').length).toBeGreaterThan(0);
  });
  it('sorts rows by the growth axis header (R28)', () => {
    const { container } = render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    const rowOrder = () => Array.from(container.querySelectorAll('[data-testid^="fundamental-row-"]'))
      .map((element) => element.getAttribute('data-testid'));
    fireEvent.click(screen.getByRole('button', { name: 'مرتب‌سازی رشد فروش' }));
    expect(rowOrder()).toEqual(['fundamental-row-وبملت', 'fundamental-row-رنيك']);
    fireEvent.click(screen.getByRole('button', { name: 'مرتب‌سازی رشد فروش' }));
    expect(rowOrder()).toEqual(['fundamental-row-رنيك', 'fundamental-row-وبملت']);
  });
  it('filters by search and calls onSelect with the row symbol (R1)', () => {
    const onSelect = vi.fn();
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={onSelect} asOf={null} />);
    fireEvent.change(screen.getByTestId('fundamental-search'), { target: { value: 'رنيك' } });
    fireEvent.click(screen.getByTestId('fundamental-row-رنيك'));
    expect(onSelect).toHaveBeenCalledWith('رنيك');
  });
});
