import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { downloadCsvWithMeta } from '@shared/lib/tableExport';
import { useScreenerCore, type ScreenerCoreRow } from '@features/fundamental/api/useScreenerCore';
import { FundamentalPage } from '@features/fundamental/routes/FundamentalPage';

vi.mock('@features/fundamental/api/useScreenerCore', () => ({
  useScreenerCore: vi.fn(),
}));
vi.mock('@shared/lib/tableExport', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@shared/lib/tableExport')>();
  return { ...actual, downloadCsvWithMeta: vi.fn() };
});

const navigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => navigate };
});

const mockedUseScreener = vi.mocked(useScreenerCore);
const mockedDownload = vi.mocked(downloadCsvWithMeta);

const rows: ScreenerCoreRow[] = [
  {
    symbol: 'فولاد', symbol_norm: 'فولاد', name: 'فولاد مبارکه', sector_name: 'فلزات اساسی',
    score: 5, verdict: 'تایید کامل', excluded: false,
    i1_pass: true, i2_pass: true, i3_pass: true, i4_pass: true, i5_pass: true,
    i1_na: false, i2_na: false, i3_na: false, i4_na: false,
  },
  {
    symbol: 'خساپا', symbol_norm: 'خساپا', name: 'سایپا', sector_name: 'خودرو',
    score: 2, verdict: 'رد', excluded: true,
    i1_pass: false, i1_na: false, i1_reason: 'رشد زیر کف است.',
    i2_pass: null, i2_na: true, i2_reason: 'شرکت مالی؛ EPS سنجیده نمی‌شود.',
    i3_pass: null, i3_na: false,
    i4_pass: false, i4_na: false, i4_reason: 'نسبت فروش به ارزش بازار کافی نیست.',
    i5_pass: false,
  },
];

beforeEach(() => {
  navigate.mockReset();
  mockedUseScreener.mockReturnValue({
    data: { status: 'success', count: 2, data: rows, as_of: '2026-11-03' },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useScreenerCore>);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('fundamental page', () => {
  it('renders the core table with pass chips and the excluded badge', () => {
    render(<MemoryRouter initialEntries={['/fundamental']}><FundamentalPage /></MemoryRouter>);
    expect(screen.getByTestId('fundamental-screen-table')).toBeTruthy();
    expect(screen.getByTestId('fundamental-row-فولاد')).toBeTruthy();
    expect(screen.getByTestId('fundamental-row-خساپا')).toBeTruthy();
    for (let i = 1; i <= 5; i++) {
      expect(screen.getByTestId(`fundamental-chip-فولاد-${i}`).getAttribute('data-state')).toBe('pass');
    }
    expect(screen.getByTestId('fundamental-excluded-خساپا')).toBeTruthy();
    expect(screen.getByTestId('fundamental-as-of').textContent).toContain('۱۴۰۵');
    expect(screen.getByTestId('fundamental-legend')).toBeTruthy();
  });

  it('distinguishes pass, fail, N/A and unknown chips', () => {
    render(<MemoryRouter initialEntries={['/fundamental']}><FundamentalPage /></MemoryRouter>);
    expect(screen.getByTestId('fundamental-chip-فولاد-1').getAttribute('data-state')).toBe('pass');
    const fail = screen.getByTestId('fundamental-chip-خساپا-1');
    expect(fail.getAttribute('data-state')).toBe('fail');
    expect(fail.getAttribute('title')).toContain('رشد زیر کف');
    const na = screen.getByTestId('fundamental-chip-خساپا-2');
    expect(na.getAttribute('data-state')).toBe('na');
    expect(na.textContent).toContain('N/A');
    expect(na.getAttribute('title')).toContain('EPS');
    const unknown = screen.getByTestId('fundamental-chip-خساپا-3');
    expect(unknown.getAttribute('data-state')).toBe('unknown');
    expect(unknown.textContent).toContain('—');
  });

  it('exports only filtered rows with the session date', () => {
    render(<MemoryRouter initialEntries={['/fundamental']}><FundamentalPage /></MemoryRouter>);
    fireEvent.change(screen.getByTestId('fundamental-search'), { target: { value: 'خساپا' } });
    fireEvent.click(screen.getByTestId('fundamental-export'));
    expect(mockedDownload).toHaveBeenCalledTimes(1);
    const [base, table, meta] = mockedDownload.mock.calls[0]!;
    expect(base).toBe('غربالگری-بنیادی');
    expect(table.rows).toHaveLength(1);
    expect(table.rows[0]![0]).toBe('خساپا');
    expect(meta).toContainEqual(['روز تابلو', '2026-11-03']);
  });

  it('navigates to the symbol route on row click', () => {
    render(<MemoryRouter initialEntries={['/fundamental']}><FundamentalPage /></MemoryRouter>);
    fireEvent.click(screen.getByTestId('fundamental-row-فولاد'));
    expect(navigate).toHaveBeenCalledWith('/fundamental/فولاد');
  });

  it('filters rows by symbol or name', () => {
    render(<MemoryRouter initialEntries={['/fundamental']}><FundamentalPage /></MemoryRouter>);
    fireEvent.change(screen.getByTestId('fundamental-search'), { target: { value: 'سایپا' } });
    expect(screen.getByTestId('fundamental-row-خساپا')).toBeTruthy();
    expect(screen.queryByTestId('fundamental-row-فولاد')).toBeNull();
  });

  it('shows the settings trigger in the table toolbar', () => {
    render(<MemoryRouter initialEntries={['/fundamental']}><FundamentalPage /></MemoryRouter>);
    expect(screen.getByTestId('fts-settings-btn')).toBeTruthy();
  });
});
