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
    i4_pass: null, i4_na: true, i4_reason: 'معاف: بانک و مؤسسهٔ اعتباری',
    i5_pass: true, i5_na: false,
    rev_growth: 83.5, eps_series: [1425, 454, 456], eps_years_available: 3,
    gross_margin: null, sales_to_mcap: null, profit_potential_pct: 0, pricing_mode: 'free' },
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
  useFundamentalPrefs.setState({ density: 'comfortable', sortKey: 'score', sortDir: 'desc' });
});
afterEach(cleanup);

describe('fundamental table visual', () => {
  it('renders five axis headers and values', () => {
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf="۱۴۰۵/۰۸/۱۳" />);
    expect(screen.getByRole('table', { name: 'جدول بنیادی' })).toBeTruthy();
    for (const name of ['رشد فروش', 'سودآوری ۳ساله', 'حاشیه سود ناخالص', 'پتانسیل سود تا آخر سال', 'نرخ‌گذاری صنعت']) expect(screen.getByText(name)).toBeTruthy();
    expect(screen.getByText('+۴۵٫۹٪')).toBeTruthy();
    expect(screen.getByTestId('fundamental-cell-رنيك-sales').textContent).toContain('۱٫۱۵');
    // R33: زمان اسکن فقط در هدر صفحه؛ جدول نسخهٔ تکراری ندارد.
    expect(screen.queryByText(/زمان اسکن/)).toBeNull();
  });
  it('shows potential profit as the axis-4 headline with the sales path', () => {
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(screen.getByText('پتانسیل سود تا آخر سال')).toBeTruthy();
    // خطِ آستانهٔ سرستون: کفِ پتانسیل + شاهدِ فروش/ارزش.
    expect(screen.getByRole('columnheader', { name: /پتانسیل سود/ }).textContent).toContain('≥ ۴۰٪ · ۰٫۳۳');
    const cell = screen.getByTestId('fundamental-cell-رنيك-sales');
    expect(cell.textContent).toContain('+۱۳٫۲٪');
    expect(cell.textContent).toContain('۱٫۱۵');
    expect(cell.getAttribute('data-path')).toBe('sales');
    expect(cell.textContent).toContain('مسیر فروش/ارزش');
    // وضعیتِ ترکیبیِ سلول قبول است، ولی نمودار فقط زیرگیتِ پتانسیل را می‌سنجد.
    expect(cell.getAttribute('data-state')).toBe('pass');
    expect(cell.querySelector('svg[role="img"]')?.getAttribute('aria-label')).toContain('رد');
  });
  it('shows no 4a/4b badge or path wording unless the combined axis-4 verdict passes', () => {
    const gated: ScreenerCoreRow[] = [
      // حکمِ ترکیبی رد/بی‌نظر است، هرچند مقادیرِ نشان مسیرِ فروش/ارزش را برمی‌آورند.
      { ...rows[0]!, i4_pass: false },
      { ...rows[0]!, symbol: 'ومعادن', i4_pass: null, i4_na: true },
    ];
    render(<FundamentalScreenTable rows={gated} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    for (const symbol of ['رنيك', 'ومعادن']) {
      const cell = screen.getByTestId(`fundamental-cell-${symbol}-sales`);
      expect(cell.getAttribute('data-path')).toBe('none');
      expect(cell.textContent).not.toContain('۴الف');
      expect(cell.textContent).not.toContain('۴ب');
      expect(cell.textContent).not.toContain('مسیر فروش/ارزش');
      // شاهدِ فروش/ارزش همچنان دیده می‌شود.
      expect(cell.textContent).toContain('فروش/ارزش');
      expect(cell.textContent).toContain('۱٫۱۵');
    }
  });
  it('shows 1a/1b sub-statuses in the growth column', () => {
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    const cell = screen.getByTestId('fundamental-cell-رنيك-growth');
    expect(cell.textContent).toContain('۱الف');
    expect(cell.textContent).toContain('۱ب');
  });
  it('applies the 1a/1b data-gap precedence in the growth column (R-P1-9)', () => {
    const growthRows: ScreenerCoreRow[] = [
      // هر دو زیرگیت پاس.
      { ...rows[0]!, symbol: 'پاس', i1_pass: true, i1a_pass: true, i1b_applicable: true, i1b_pass: true, i1b_data_gap: false },
      // هر دو زیرگیت رد.
      { ...rows[0]!, symbol: 'ردي', i1_pass: false, i1a_pass: false, i1b_applicable: true, i1b_pass: false, i1b_data_gap: false },
      // ۱ب برای غیرتولیدی applicable نیست؛ حکمِ ترکیبی از ۱الف می‌آید → قبول.
      { ...rows[0]!, symbol: 'ناظر', i1_pass: true, i1a_pass: true, i1b_applicable: false, i1b_pass: true, i1b_data_gap: false },
      // همان حالت با ۱الفِ رد → حکمِ ترکیبی رد است، نه بی‌نظر.
      { ...rows[0]!, symbol: 'ناظررد', i1_pass: false, i1a_pass: false, i1b_applicable: false, i1b_pass: false, i1b_data_gap: false },
      // همان حالت بدون حکمِ قطعیِ ۱الف → بی‌نظر.
      { ...rows[0]!, symbol: 'ناظرنام', i1_pass: null, i1a_pass: null, i1b_applicable: false, i1b_pass: true, i1b_data_gap: false },
      // شکافِ داده بر pass=false مقدم است → نامشخص، نه رد.
      { ...rows[0]!, symbol: 'شکاف', i1_pass: true, i1a_pass: true, i1b_applicable: true, i1b_pass: false, i1b_data_gap: true },
      // بی‌نظریِ ۱الف بر حکمِ زیرگیت مقدم است.
      { ...rows[0]!, symbol: 'نابل', i1_pass: null, i1_na: true, i1a_pass: false, i1b_applicable: true, i1b_pass: true, i1b_data_gap: false },
    ];
    render(<FundamentalScreenTable rows={growthRows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    const cell = (symbol: string) => screen.getByTestId(`fundamental-cell-${symbol}-growth`);
    expect(cell('پاس').textContent).toContain('۱الف قبول');
    expect(cell('پاس').textContent).toContain('۱ب قبول');
    expect(cell('پاس').getAttribute('data-state')).toBe('pass');
    expect(cell('ردي').textContent).toContain('۱الف رد');
    expect(cell('ردي').textContent).toContain('۱ب رد');
    expect(cell('ردي').getAttribute('data-state')).toBe('fail');
    expect(cell('ناظر').textContent).toContain('۱ب بی‌نظر');
    expect(cell('ناظر').getAttribute('data-state')).toBe('pass');
    expect(cell('ناظررد').textContent).toContain('۱ب بی‌نظر');
    expect(cell('ناظررد').getAttribute('data-state')).toBe('fail');
    expect(cell('ناظرنام').textContent).toContain('۱ب بی‌نظر');
    expect(cell('ناظرنام').getAttribute('data-state')).toBe('na');
    expect(cell('شکاف').textContent).toContain('۱ب نامشخص');
    expect(cell('شکاف').textContent).not.toContain('۱ب رد');
    expect(cell('شکاف').getAttribute('data-state')).toBe('unknown');
    expect(cell('نابل').textContent).toContain('۱الف بی‌نظر');
    expect(cell('نابل').getAttribute('data-state')).toBe('na');
  });
  it('hides the 1a/1b sub-status line in compact density (R-P1-2)', () => {
    const growthRow: ScreenerCoreRow[] = [
      { ...rows[0]!, symbol: 'پاس', i1_pass: true, i1a_pass: true, i1b_applicable: true, i1b_pass: true, i1b_data_gap: false },
    ];
    const { container, rerender } = render(<FundamentalScreenTable rows={growthRow} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(screen.getByTestId('fundamental-cell-پاس-growth').textContent).toContain('۱الف قبول');
    act(() => useFundamentalPrefs.setState({ density: 'compact' }));
    rerender(<FundamentalScreenTable rows={growthRow} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(container.querySelectorAll('.fd-axis-threshold').length).toBe(0);
    expect(screen.getByTestId('fundamental-cell-پاس-growth').textContent).not.toContain('۱الف');
    expect(screen.getByTestId('fundamental-cell-پاس-growth').textContent).not.toContain('۱ب');
  });
  it('sorts axis 4 by the potential percentage', () => {
    const onSelect = vi.fn();
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={onSelect} asOf={null} />);
    fireEvent.click(screen.getByRole('button', { name: /مرتب‌سازی پتانسیل سود/ }));
    const order = [...document.querySelectorAll('[data-testid^="fundamental-row-"]')].map((el) => el.getAttribute('data-testid'));
    // کلیکِ اول روی ستونِ جدید، نزولی است: پتانسیل ۱۳٫۲ (رنيك) بالاتر از ۰ (وبملت) است.
    expect(order[0]).toBe('fundamental-row-رنيك');
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
  it('drops the axis threshold line in compact rows and keeps it comfortable (R92)', () => {
    const { container, rerender } = render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(container.querySelectorAll('.fd-axis-threshold').length).toBeGreaterThan(0);
    act(() => useFundamentalPrefs.setState({ density: 'compact' }));
    rerender(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(container.querySelectorAll('.fd-axis-threshold').length).toBe(0);
  });
  it('labels the i4_na badge as exempt, not a bank, and keeps the reason as title (R100)', () => {
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    const badge = screen.getByTestId('fundamental-bank-وبملت');
    expect(badge.textContent).toBe('معاف / N/A');
    expect(badge.getAttribute('title')).toContain('معاف: بانک');
    expect(badge.textContent).not.toContain('بانک');
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
  it('conforms table ARIA: cells, sortable headers and the glyph column label (R32/R87)', () => {
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    const glyphHeader = screen.getByRole('columnheader', { name: 'نمای پنج‌محور' });
    expect(glyphHeader).toBeTruthy();
    // R87: ستونِ ۳۸px خالی نیست و «#» دیده می‌شود.
    expect(glyphHeader.textContent).toContain('#');
    expect(screen.getByRole('columnheader', { name: 'وضعیت' }).hasAttribute('aria-sort')).toBe(false);
    expect(screen.getByTestId('fundamental-cell-رنيك-growth').getAttribute('role')).toBe('cell');
  });
  it('renders the EPS cell as the last EPS plus a trend arrow, never N/N (R98)', () => {
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    const epsCell = screen.getByTestId('fundamental-cell-رنيك-eps');
    expect(epsCell.textContent).toContain('۱۶۷۲');
    // R-UNSLOP-3: روند با شکلِ SVG و نامِ فارسی گفته می‌شود، نه کاراکترِ فلش.
    expect(epsCell.querySelector('[data-trend="up"]')?.getAttribute('aria-label')).toBe('روند صعودی');
    expect(epsCell.textContent).not.toContain('↑');
    expect(epsCell.textContent).not.toContain('۳/۳');
    // خطِ آستانه = سال‌های تنظیم‌شده، نه ۳ سخت‌کد.
    expect(epsCell.textContent).toContain('≥ ۳ سال');
    expect(screen.getByRole('button', { name: 'مرتب‌سازی سودآوری ۳ساله' })).toBeTruthy();
  });
  it('sorts the EPS column by the displayed last EPS (R98)', () => {
    const { container } = render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    const rowOrder = () => Array.from(container.querySelectorAll('[data-testid^="fundamental-row-"]'))
      .map((element) => element.getAttribute('data-testid'));
    fireEvent.click(screen.getByRole('button', { name: 'مرتب‌سازی سودآوری ۳ساله' }));
    expect(rowOrder()).toEqual(['fundamental-row-رنيك', 'fundamental-row-وبملت']);
    fireEvent.click(screen.getByRole('button', { name: 'مرتب‌سازی سودآوری ۳ساله' }));
    expect(rowOrder()).toEqual(['fundamental-row-وبملت', 'fundamental-row-رنيك']);
  });
  it('honors the EPS years setting in the header and the cell (R99)', () => {
    const oneYear = { ...thresholds, v10_eps_years: 1 };
    render(<FundamentalScreenTable rows={rows} thresholds={oneYear} onSelect={vi.fn()} asOf={null} />);
    const header = screen.getByRole('columnheader', { name: /سودآوری ۳ساله/ });
    expect(header.textContent).toContain('۱ سال');
    expect(header.textContent).not.toContain('۳ سال');
    expect(screen.getByTestId('fundamental-cell-رنيك-eps').textContent).toContain('≥ ۱ سال');
    // تنظیمِ ردیف بر ریشه مقدم است.
    cleanup();
    const overridden = rows.map((row) => (row.symbol === 'رنيك' ? { ...row, eps_years_required: 2 } : row));
    render(<FundamentalScreenTable rows={overridden} thresholds={oneYear} onSelect={vi.fn()} asOf={null} />);
    expect(screen.getByTestId('fundamental-cell-رنيك-eps').textContent).toContain('≥ ۲ سال');
  });
  it('keeps the EPS trend arrow in compact mode while dropping the threshold line (R92/R98)', () => {
    const { container } = render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    act(() => useFundamentalPrefs.setState({ density: 'compact' }));
    expect(container.querySelectorAll('.fd-axis-threshold').length).toBe(0);
    expect(screen.getByTestId('fundamental-cell-رنيك-eps').querySelector('[data-trend="up"]')).toBeTruthy();
  });
  it('renders absent EPS years as — in the cell and the CSV (R30/R98)', () => {
    render(<FundamentalScreenTable rows={fallbackRows} thresholds={thresholds} onSelect={vi.fn()} asOf="۱۴۰۵/۰۸/۱۳" />);
    const epsCell = screen.getByTestId('fundamental-cell-شپنا-eps');
    expect(epsCell.textContent).toContain('—');
    expect(epsCell.textContent).not.toContain('۰/۳');
    expect(epsCell.textContent).not.toContain('—/۳');
    fireEvent.click(screen.getByTestId('fundamental-export'));
    expect(mockedDownload).toHaveBeenCalledTimes(1);
    const [, table, meta] = mockedDownload.mock.calls[0]!;
    expect(table.rows[0]![4]).toBe('—');
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
