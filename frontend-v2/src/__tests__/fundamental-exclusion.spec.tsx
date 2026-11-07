import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useScreenerCore, type ScreenerCoreRow } from '@features/fundamental/api/useScreenerCore';
import { FundamentalPage } from '@features/fundamental/routes/FundamentalPage';
import { resetExcludeAxes, setExcludeAxes, EXCLUDE_LABEL } from '@features/fundamental/lib/exclusionFilter';

vi.mock('@features/fundamental/api/useScreenerCore', () => ({ useScreenerCore: vi.fn() }));

const rows: ScreenerCoreRow[] = [
  {
    symbol: 'فولاد', sector_name: 'فلزات', score: 5, verdict: 'قبول',
    i1_pass: true, i2_pass: true, i3_pass: true, i4_pass: true, i5_pass: true,
    i1_na: false, i2_na: false, i3_na: false, i4_na: false,
  },
  {
    symbol: 'خساپا', sector_name: 'خودرو', score: 2, verdict: 'رد',
    i1_pass: false, i1_na: false, i2_pass: null, i2_na: true,
    i3_pass: null, i3_na: false, i4_pass: false, i4_na: false, i5_pass: false,
  },
  {
    symbol: 'شپنا', sector_name: 'پالایش', score: 3, verdict: 'بررسی',
    i1_pass: true, i1_na: false, i2_pass: true, i2_na: false,
    i3_pass: null, i3_na: false, gross_margin: 12,
    i4_pass: true, i4_na: false, i5_pass: true,
  },
];

beforeEach(() => {
  resetExcludeAxes();
  vi.mocked(useScreenerCore).mockReturnValue({
    data: { status: 'success', count: 3, data: rows, as_of: '2026-11-03' },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useScreenerCore>);
});

afterEach(() => {
  cleanup();
  resetExcludeAxes();
  vi.clearAllMocks();
});

describe('exclusion filter', () => {
  it('names axis 3 with the exact gross-margin label (R-P1-6)', () => {
    expect(EXCLUDE_LABEL['3']).toBe('حاشیه سود ناخالص (شاخص ۳)');
  });

  it('hides only rows rejected by an active axis', () => {
    setExcludeAxes(['1a']);
    render(<MemoryRouter initialEntries={['/fundamental']}><FundamentalPage /></MemoryRouter>);
    expect(screen.queryByTestId('fundamental-row-خساپا')).toBeNull();
    expect(screen.getByTestId('fundamental-row-فولاد')).toBeTruthy();
    expect(screen.getByTestId('fundamental-hidden-count').textContent).toContain('۱');
  });

  it('1b never hides rows', () => {
    setExcludeAxes(['1b']);
    render(<MemoryRouter initialEntries={['/fundamental']}><FundamentalPage /></MemoryRouter>);
    expect(screen.getByTestId('fundamental-row-خساپا')).toBeTruthy();
    expect(screen.queryByTestId('fundamental-hidden-count')).toBeNull();
  });

  it('hides incomplete axis data but keeps rows that have the data', () => {
    setExcludeAxes(['3']);
    render(<MemoryRouter initialEntries={['/fundamental']}><FundamentalPage /></MemoryRouter>);
    expect(screen.queryByTestId('fundamental-row-خساپا')).toBeNull();
    expect(screen.getByTestId('fundamental-row-شپنا')).toBeTruthy();
  });
});
