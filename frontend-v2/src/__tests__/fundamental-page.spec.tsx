import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useScreenerCore, type ScreenerCoreRow } from '@features/fundamental/api/useScreenerCore';
import { FundamentalPage } from '@features/fundamental/routes/FundamentalPage';

vi.mock('@features/fundamental/api/useScreenerCore', () => ({
  useScreenerCore: vi.fn(),
}));

const navigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => navigate };
});

const mockedUseScreener = vi.mocked(useScreenerCore);

const rows: ScreenerCoreRow[] = [
  {
    symbol: 'فولاد', symbol_norm: 'فولاد', name: 'فولاد مبارکه', sector_name: 'فلزات اساسی',
    score: 5, verdict: 'تایید کامل', excluded: false,
    i1_pass: true, i2_pass: true, i3_pass: true, i4_pass: true, i5_pass: true,
  },
  {
    symbol: 'خساپا', symbol_norm: 'خساپا', name: 'سایپا', sector_name: 'خودرو',
    score: 2, verdict: 'رد', excluded: true,
    i1_pass: false, i2_pass: true, i3_pass: false, i4_pass: null, i5_pass: false,
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
      expect(screen.getByTestId(`fundamental-chip-فولاد-${i}`).getAttribute('data-pass')).toBe('true');
    }
    expect(screen.getByTestId('fundamental-excluded-خساپا')).toBeTruthy();
    expect(screen.getByTestId('fundamental-as-of').textContent).toContain('۱۴۰۵');
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
});
