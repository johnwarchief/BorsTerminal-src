import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useCodalHealth } from '@features/fundamental/api/useCodalHealth';
import { useFtsCard } from '@features/fundamental/api/useFtsCard';
import { useSectorPe } from '@features/fundamental/api/useSectorPe';
import { FundamentalDetail } from '@features/fundamental/ui/FundamentalDetail';

vi.mock('@features/fundamental/api/useFtsCard', () => ({ useFtsCard: vi.fn() }));
vi.mock('@features/fundamental/api/useSectorPe', () => ({ useSectorPe: vi.fn() }));
vi.mock('@features/fundamental/api/useCodalHealth', () => ({ useCodalHealth: vi.fn() }));
vi.mock('@features/fundamental/api/useCalendar', () => ({
  useSymbolCalendar: () => ({ data: { status: 'ok', events: [] }, isLoading: false, isError: false }),
}));

const mockedCard = vi.mocked(useFtsCard);
const mockedSectorPe = vi.mocked(useSectorPe);
const mockedHealth = vi.mocked(useCodalHealth);

const details = Object.fromEntries(['۱', '۲', '۳', '۴', '۵'].map((digit) => [digit, {
  title: `عنوان ${digit}`,
  formula: `فرمول ${digit}`,
  source: `منبع ${digit}`,
  calc: `محاسبه ${digit}`,
  what: `توضیح ${digit}`,
  subchecks: [],
}]));

const indicators = {
  '1': { monetary: { monetary_pct: 10, threshold: 40, data_gap: false, reason: '' }, volume: { applicable: true } },
  '2': { eps_series: [1, 2, 3], years_available: 3, years_required: 3 },
  '3': { margin_pct: 25, threshold: 20, band: 'ok', optimal: false },
  '4': { sales_to_mcap: 0.4, sales_threshold: 0.33, available: true, na: false, exempt: false },
  '5': { label: 'آزاد', regime_label: 'آزاد', sector: 'فلزات' },
};

const passes = {
  '1_growth': true,
  '2_eps_trend': true,
  '3_gross_margin': true,
  '4_sales_to_mcap': true,
  '5_industry': true,
};

function card(overrides: Record<string, unknown> = {}) {
  return {
    data: {
      status: 'success',
      symbol: 'ویسا',
      sector: 'سرمایه‌گذاری‌ها',
      score: 3,
      verdict: 'WATCH',
      details,
      freshness: { as_of: '2026-08-23', axes: {} },
      indicators,
      passes,
      profile: { kind: 'production' },
      ...overrides,
    },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useFtsCard>;
}

beforeEach(() => {
  mockedSectorPe.mockReturnValue({
    data: { pe: 5, median: 6, sector: 'سرمایه‌گذاری‌ها', peers: 3 },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useSectorPe>);
  mockedHealth.mockReturnValue({
    data: { status: 'success', queue: {}, dirty_symbols: 0, gap_flag: false },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useCodalHealth>);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('P/NAV holding panel', () => {
  it('holding replaces sector P/E with an explicit N/A panel', () => {
    mockedCard.mockReturnValue(card({
      profile: { kind: 'holding', margin_class: 'holding', label: 'هلدینگ / سرمایه‌گذاری' },
      indicators: { ...indicators, '4': { ...indicators['4'], na: true, exempt: true } },
    }));
    render(<FundamentalDetail symbol="ویسا" onBack={vi.fn()} />);
    expect(screen.getByTestId('holding-pnav-panel')).toBeTruthy();
    // R-V1-5: پنلِ شاخص ۵ دیگر جای خود را به P/NAV نمی‌دهد؛ برایِ این طبقه «بی‌نظر» می‌ماند.
    expect(screen.getByTestId('panel-industry').textContent).toContain('بی‌نظر');
    expect(screen.getByTestId('holding-nav-na').textContent).toContain('NAV');
    expect(screen.queryByText(/P\/NAV ≈/)).toBeNull();
  });

  it('bank uses the bank wording', () => {
    mockedCard.mockReturnValue(card({
      profile: { kind: 'holding', margin_class: 'bank', label: 'بانک / مؤسسهٔ اعتباری' },
      indicators: { ...indicators, '4': { ...indicators['4'], na: true, exempt: true } },
    }));
    render(<FundamentalDetail symbol="وبملت" onBack={vi.fn()} />);
    expect(screen.getByTestId('holding-pnav-panel').textContent).toContain('بانک');
  });

  it('fund shows not applicable and no P/NAV panel', () => {
    mockedCard.mockReturnValue(card({ applicable: false, profile: { kind: 'fund' } }));
    render(<FundamentalDetail symbol="صندوق" onBack={vi.fn()} />);
    expect(screen.getByTestId('fundamental-not-applicable')).toBeTruthy();
    expect(screen.queryByTestId('holding-pnav-panel')).toBeNull();
  });

  it('normal symbol keeps the industry panel', () => {
    mockedCard.mockReturnValue(card({ profile: { kind: 'production' } }));
    render(<FundamentalDetail symbol="فولاد" onBack={vi.fn()} />);
    expect(screen.getByTestId('panel-industry')).toBeTruthy();
    expect(screen.queryByTestId('sector-pe-panel')).toBeNull();
  });
});
