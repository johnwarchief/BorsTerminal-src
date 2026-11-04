import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FundamentalPage } from '@features/fundamental/routes/FundamentalPage';
import { useScreenerCore } from '@features/fundamental/api/useScreenerCore';
import { useFundamentalPrefs } from '@features/fundamental/stores/prefs';
import { resetExcludeAxes } from '@features/fundamental/lib/exclusionFilter';
import { downloadCsvWithMeta } from '@shared/lib/tableExport';

vi.mock('@features/fundamental/api/useScreenerCore', () => ({ useScreenerCore: vi.fn() }));
vi.mock('@shared/lib/tableExport', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@shared/lib/tableExport')>()),
  downloadCsvWithMeta: vi.fn(),
}));

const rows = [{
  symbol: 'رنيك', name: 'جنرال مکانیک', sector_name: 'خدمات فنی', score: 3, verdict: 'WATCH',
  i1_pass: false, i1_na: false, i2_pass: true, i2_na: false, i3_pass: false, i3_na: false,
  i4_pass: true, i4_na: false, i5_pass: true, i5_na: false,
  rev_growth: 45.9, eps_series: [1119, 1615, 1672], eps_years_available: 3,
  gross_margin: 11.5, sales_to_mcap: 1.15, profit_potential_pct: 13.2, pricing_mode: 'neutral',
}];
const thresholds = { growth_min: 60, margin_min: 40, v10_sales_to_mcap_min: 0.33, profit_potential_min: 40, v10_eps_years: 3 };

const mockedScreener = vi.mocked(useScreenerCore);
const mockedDownload = vi.mocked(downloadCsvWithMeta);

function mockScreener(overrides: Record<string, unknown> = {}) {
  mockedScreener.mockReturnValue({
    data: { status: 'success', count: 1, data: rows, as_of: 1793789441, thresholds },
    isLoading: false,
    isFetching: false,
    isError: false,
    refetch: vi.fn(),
    ...overrides,
  } as never);
}

function renderPage() {
  return render(<MemoryRouter initialEntries={['/fundamental']}><FundamentalPage /></MemoryRouter>);
}

beforeEach(() => {
  resetExcludeAxes();
  vi.clearAllMocks();
  useFundamentalPrefs.setState({ density: 'comfortable', surface: 'paper', sortKey: 'score', sortDir: 'desc' });
  mockScreener();
});
afterEach(cleanup);

describe('fundamental page visual', () => {
  it('sets paper surface by default and switches to ink (R35/R37/R39)', () => {
    renderPage();
    const page = screen.getByTestId('fundamental-page');
    // R35: ریشهٔ صفحه هم توکن‌های سطح را می‌گیرد و هم صفت سطح را.
    expect(page.getAttribute('data-fund-surface')).toBe('paper');
    expect(page.className).toContain('fundamental-surface');
    expect(page.className).toContain('bg-[var(--fd-bg)]');
    expect(page.className).toContain('text-[var(--fd-text)]');
    expect(screen.getByTestId('fundamental-surface-paper').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('fundamental-surface-paper').textContent).toBe('کاغذی');
    expect(screen.getByTestId('fundamental-surface-ink').getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByTestId('fundamental-surface-ink').textContent).toBe('تیره');
    // R42: هر دو دکمه در گروه «سطح داده»اند و کلاس tape-btn را حفظ می‌کنند؛
    // قاعدهٔ سطح‌محور styles.css دقیقاً با همین دو انتخابگر رنگ می‌دهد.
    const surfaceGroup = screen.getByRole('group', { name: 'سطح داده' });
    expect(within(surfaceGroup).getByTestId('fundamental-surface-paper').className).toBe('tape-btn');
    expect(within(surfaceGroup).getByTestId('fundamental-surface-ink').className).toBe('tape-btn');

    fireEvent.click(screen.getByTestId('fundamental-surface-ink'));
    expect(useFundamentalPrefs.getState().surface).toBe('ink');
    expect(screen.getByTestId('fundamental-page').getAttribute('data-fund-surface')).toBe('ink');
    expect(screen.getByTestId('fundamental-surface-ink').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('fundamental-surface-paper').getAttribute('aria-pressed')).toBe('false');

    fireEvent.click(screen.getByTestId('fundamental-surface-paper'));
    expect(useFundamentalPrefs.getState().surface).toBe('paper');
    expect(screen.getByTestId('fundamental-page').getAttribute('data-fund-surface')).toBe('paper');
  });

  it('density buttons drive the measured chart effect, not just presence (R40/R41)', () => {
    renderPage();
    const table = screen.getByTestId('fundamental-screen-table');
    // پیش‌فرض comfortable → نمودارهای SVG محورها هست.
    expect(table.querySelectorAll('svg[role="img"]').length).toBeGreaterThan(0);
    expect(screen.getByTestId('fundamental-density-comfortable').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('fundamental-density-compact').textContent).toBe('فشرده');
    expect(screen.getByTestId('fundamental-density-comfortable').textContent).toBe('راحت');
    expect(within(screen.getByRole('group', { name: 'تراکم جدول' })).getByTestId('fundamental-density-compact')).toBeTruthy();

    fireEvent.click(screen.getByTestId('fundamental-density-compact'));
    expect(useFundamentalPrefs.getState().density).toBe('compact');
    expect(screen.getByTestId('fundamental-density-compact').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('fundamental-density-comfortable').getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByTestId('fundamental-screen-table').querySelectorAll('svg[role="img"]').length).toBe(0);

    fireEvent.click(screen.getByTestId('fundamental-density-comfortable'));
    expect(useFundamentalPrefs.getState().density).toBe('comfortable');
    expect(screen.getByTestId('fundamental-screen-table').querySelectorAll('svg[role="img"]').length).toBeGreaterThan(0);
  });

  it('exports five axis columns with real threshold metadata (R20/R38)', () => {
    renderPage();
    fireEvent.click(screen.getByTestId('fundamental-export'));
    expect(mockedDownload).toHaveBeenCalledTimes(1);
    const [base, table, meta] = mockedDownload.mock.calls[0]!;
    expect(base).toBe('غربالگری-بنیادی');
    expect(table.columns).toEqual(expect.arrayContaining([
      'نماد', 'رشد', 'سودآوری', 'حاشیه', 'پتانسیل سود', 'فروش/ارزش (شاهد)', 'صنعت', 'امتیاز', 'وضعیت',
    ]));
    expect(table.columns).toContain('صنعت شرکت');
    expect(meta).toEqual(expect.arrayContaining([
      ['آستانه رشد', '60'],
      // R107: گیتِ EPS در متادیتا می‌ماند، هرچند ستون نمایشی آخرین EPS + فلش است.
      ['آستانه EPS', '3'],
      ['آستانه حاشیه', '40'],
      ['آستانه پتانسیل', '40'],
      ['آستانه فروش/ارزش', '0.33'],
    ]));
    // R38: همان آستانه‌ها در هدر جدول هم دیده می‌شوند.
    expect(screen.getByRole('columnheader', { name: /رشد فروش/ }).textContent).toContain('≥ ۶۰٪');
  });

  it('keeps exactly one visible scan label in the page header (R35/R36)', () => {
    renderPage();
    expect(screen.getAllByTestId('fundamental-as-of')).toHaveLength(1);
    expect(screen.getAllByText(/زمان اسکن/)).toHaveLength(1);
    expect(screen.getByTestId('fundamental-screen-table').textContent).not.toContain('زمان اسکن');
    // S4b دست‌نخورده: جستجو، صنعت، خروجی، شمارش، راهنما و تنظیمات.
    expect(screen.getByTestId('fundamental-search')).toBeTruthy();
    expect(screen.getByLabelText('فیلتر صنعت')).toBeTruthy();
    expect(screen.getByTestId('fundamental-export')).toBeTruthy();
    expect(screen.getByTestId('fundamental-count')).toBeTruthy();
    expect(screen.getByTestId('fundamental-legend')).toBeTruthy();
    expect(screen.getByTestId('fts-settings-btn')).toBeTruthy();
  });

  it('omits the scan label entirely when as_of is null while the controls stay (R43)', () => {
    mockScreener({ data: { status: 'success', count: 1, data: rows, as_of: null, thresholds } });
    renderPage();
    // R43: بدون as_of هیچ متن/گرهٔ خالیِ «زمان اسکن» رندر نمی‌شود.
    expect(screen.queryByTestId('fundamental-as-of')).toBeNull();
    expect(screen.queryByText(/زمان اسکن/)).toBeNull();
    const page = screen.getByTestId('fundamental-page');
    expect(within(page).getByRole('group', { name: 'سطح داده' })).toBeTruthy();
    expect(within(page).getByTestId('fundamental-surface-paper').getAttribute('aria-pressed')).toBe('true');
    expect(within(page).getByTestId('fundamental-surface-ink')).toBeTruthy();
    expect(within(page).getByRole('group', { name: 'تراکم جدول' })).toBeTruthy();
    expect(within(page).getByTestId('fundamental-density-compact')).toBeTruthy();
    expect(within(page).getByTestId('fundamental-density-comfortable').getAttribute('aria-pressed')).toBe('true');
  });

  it('renders loading and error states inside the themed surface with exact --fd-* tokens (R44)', () => {
    mockScreener({ data: undefined, isLoading: true });
    renderPage();
    const page = screen.getByTestId('fundamental-page');
    const loading = within(page).getByTestId('fundamental-table-loading');
    expect(loading.className).toBe('p-3 t-95 text-[var(--fd-text-3)]');
    expect(page.getAttribute('data-fund-surface')).toBe('paper');
    cleanup();

    mockScreener({ data: undefined, isError: true });
    renderPage();
    const errorPage = screen.getByTestId('fundamental-page');
    const error = within(errorPage).getByTestId('fundamental-table-error');
    expect(error.className).toBe('t-10 text-[var(--fd-text-2)]');
    expect(errorPage.getAttribute('data-fund-surface')).toBe('paper');
    // R42: دکمهٔ تلاش دوباره هم داخل سطح می‌ماند و همان کلاس هدفِ استایل سطح را دارد.
    expect(within(errorPage).getByRole('button', { name: 'تلاش دوباره' }).className).toBe('tape-btn');
  });

  it('falls back to — for axis thresholds and CSV meta when thresholds are null (R45)', () => {
    mockScreener({ data: { status: 'success', count: 1, data: rows, as_of: 1793789441, thresholds: null } });
    renderPage();
    for (const name of [/رشد فروش/, /حاشیهٔ ناخالص/, /پتانسیل سود تا آخر سال/]) {
      const header = screen.getByRole('columnheader', { name });
      expect(within(header).getByText('—')).toBeTruthy();
    }
    for (const axis of ['growth', 'margin', 'sales']) {
      const cell = screen.getByTestId(`fundamental-cell-رنيك-${axis}`);
      // محورِ بی‌آستانه «—» را در خطِ آستانه/نشانِ مسیر نگه می‌دارد، نه مقدارِ ساختگی.
      expect(within(cell).getAllByText('—').length).toBeGreaterThan(0);
    }
    fireEvent.click(screen.getByTestId('fundamental-export'));
    const [, , meta] = mockedDownload.mock.calls[0]!;
    expect(meta).toEqual(expect.arrayContaining([
      ['آستانه رشد', '—'],
      ['آستانه EPS', '—'],
      ['آستانه حاشیه', '—'],
      ['آستانه پتانسیل', '—'],
      ['آستانه فروش/ارزش', '—'],
    ]));
  });
});
