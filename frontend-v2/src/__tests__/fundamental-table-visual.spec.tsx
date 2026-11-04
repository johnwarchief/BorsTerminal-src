import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { downloadCsvWithMeta } from '@shared/lib/tableExport';
import { FundamentalScreenTable } from '@features/fundamental/ui/FundamentalScreenTable';
import { useFundamentalPrefs } from '@features/fundamental/stores/prefs';
import { resetExcludeAxes } from '@features/fundamental/lib/exclusionFilter';
import type { ScreenerCoreRow } from '@features/fundamental/api/useScreenerCore';

vi.mock('@shared/lib/tableExport', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@shared/lib/tableExport')>();
  return { ...actual, downloadCsvWithMeta: vi.fn() };
});

const mockedDownload = vi.mocked(downloadCsvWithMeta);

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

// R30/R31: eps_years_available عمداً حذف شده و verdict بیرون از enum است.
const fallbackRows: ScreenerCoreRow[] = [
  { symbol: 'شپنا', name: 'پالایش نفت', sector_name: 'فرآورده‌های نفتی', score: 1, verdict: 'FTS ندارد',
    i1_pass: null, i1_na: true, i2_pass: null, i2_na: true, i3_pass: null, i3_na: true,
    i4_pass: null, i4_na: true, i5_pass: null, i5_na: true,
    rev_growth: null, eps_series: null,
    gross_margin: null, sales_to_mcap: null, profit_potential_pct: null, pricing_mode: null },
];
const thresholds = { growth_min: 60, margin_min: 40, v10_sales_to_mcap_min: 0.33, profit_potential_min: 40, v10_eps_years: 3 };

beforeEach(() => {
  resetExcludeAxes();
  vi.clearAllMocks();
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
    // R33: زمان اسکن فقط در هدر صفحه؛ جدول نسخهٔ تکراری ندارد.
    expect(screen.queryByText(/زمان اسکن/)).toBeNull();
  });
  it('shows charts only in comfortable mode', () => {
    const { container, rerender } = render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(container.querySelectorAll('.fd-axis-chart').length).toBeGreaterThan(0);
    expect(container.querySelectorAll('svg[role="img"]').length).toBeGreaterThan(0);
    act(() => useFundamentalPrefs.setState({ density: 'compact' }));
    rerender(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(container.querySelectorAll('.fd-axis-chart').length).toBe(0);
    expect(container.querySelectorAll('svg[role="img"]').length).toBe(0);
  });
  it('distinguishes N/A/unknown and bank badges', () => {
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(screen.getByTestId('fundamental-bank-وبملت')).toBeTruthy();
    expect(document.querySelectorAll('.fd-status--na').length).toBeGreaterThan(0);
    expect(screen.getByTestId('fundamental-cell-وبملت-margin').getAttribute('data-state')).toBe('na');
  });
  it('sorts rows by the growth axis header and reports aria-sort (R28/R34)', () => {
    const { container } = render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    const rowOrder = () => Array.from(container.querySelectorAll('[data-testid^="fundamental-row-"]'))
      .map((element) => element.getAttribute('data-testid'));
    const growthHeader = () => screen.getByRole('columnheader', { name: /رشد فروش/ });
    expect(growthHeader().getAttribute('aria-sort')).toBe('none');
    fireEvent.click(screen.getByRole('button', { name: 'مرتب‌سازی رشد فروش' }));
    expect(growthHeader().getAttribute('aria-sort')).toBe('descending');
    expect(rowOrder()).toEqual(['fundamental-row-وبملت', 'fundamental-row-رنيك']);
    fireEvent.click(screen.getByRole('button', { name: 'مرتب‌سازی رشد فروش' }));
    expect(growthHeader().getAttribute('aria-sort')).toBe('ascending');
    expect(rowOrder()).toEqual(['fundamental-row-رنيك', 'fundamental-row-وبملت']);
  });
  it('conforms table ARIA: cells, sortable headers and the glyph column label (R32)', () => {
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(screen.getByRole('columnheader', { name: 'نمای پنج‌محور' })).toBeTruthy();
    expect(screen.getByRole('columnheader', { name: 'وضعیت' }).hasAttribute('aria-sort')).toBe(false);
    expect(screen.getByTestId('fundamental-cell-رنيك-growth').getAttribute('role')).toBe('cell');
  });
  it('renders absent EPS years as —/۳ in the cell and the CSV (R30)', () => {
    render(<FundamentalScreenTable rows={fallbackRows} thresholds={thresholds} onSelect={vi.fn()} asOf="۱۴۰۵/۰۸/۱۳" />);
    const epsCell = screen.getByTestId('fundamental-cell-شپنا-eps');
    expect(epsCell.textContent).toContain('—/۳');
    expect(epsCell.textContent).not.toContain('۰/۳');
    fireEvent.click(screen.getByTestId('fundamental-export'));
    expect(mockedDownload).toHaveBeenCalledTimes(1);
    const [, table, meta] = mockedDownload.mock.calls[0]!;
    expect(table.rows[0]![4]).toBe('—/۳');
    expect(meta).toContainEqual(['زمان اسکن', '۱۴۰۵/۰۸/۱۳']);
  });
  it('shows a verdict outside the enum verbatim (R31)', () => {
    render(<FundamentalScreenTable rows={fallbackRows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(screen.getByTestId('fundamental-verdict-شپنا').textContent).toBe('FTS ندارد');
  });
  it('filters by search and calls onSelect with the row symbol (R1)', () => {
    const onSelect = vi.fn();
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={onSelect} asOf={null} />);
    fireEvent.change(screen.getByTestId('fundamental-search'), { target: { value: 'رنيك' } });
    fireEvent.click(screen.getByTestId('fundamental-row-رنيك'));
    expect(onSelect).toHaveBeenCalledWith('رنيك');
  });
});
