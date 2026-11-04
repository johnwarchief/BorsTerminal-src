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

const details = {
  '۱': {
    title: 'رشد',
    formula: 'رشد ریالی فروش ÷ فروش دورهٔ قبل',
    source: 'کدال — صورت‌های مالی',
    calc: '+45.9',
    what: 'رشد فروش ریالی در برابر کف',
    subchecks: [{ key: '1a', label: 'رشد ریالی', state: 'fail', value: '+45.9٪', threshold: '≥ ۶۰٪', detail: 'زیر کف', verified: true, confidence: 'متوسط' }],
  },
  '۲': {
    title: 'سودآوری',
    formula: 'EPS تلفیقی سه سال',
    source: 'کدال',
    calc: '۳ سال',
    what: 'سابقهٔ EPS',
    subchecks: [{ key: '1a', label: 'پایداری EPS', state: 'pass', value: '۳ سال', threshold: '≥ ۳', detail: 'کامل', verified: true, confidence: 'بالا' }],
  },
};

const baseIndicators = {
  '1': { monetary: { monetary_pct: 45.9, threshold: 60, data_gap: false, reason: 'کف ۶۰٪' }, volume: { applicable: true } },
  '2': { eps_series: [1119, 1615, 1672], years_available: 3, years_required: 3, evidence: 'تلفیقی', consolidated_used: true },
  '3': { margin_pct: 11.5, threshold: 40, optimal_threshold: 30, margin_tier: 'below', gross_profit_bt: 12.4, revenue_bt: 107.8, na: false },
  '4': { sales_to_mcap: 1.15, sales_threshold: 0.33, potential_pct: 13.2, potential_threshold: 40, annual_sales_bt: 5.5, months_used: 6, available: true, na: false },
  '5': { verdict: 'neutral', label: 'خنثی', sector: 'خدمات فنی و مهندسی', market_share_pct: 4.2, outlook: 'نیازمند بررسی موردی', regime_label: 'خنثی', pass: true },
};

function fixtureCard(overrides: Record<string, unknown> = {}) {
  return {
    status: 'success',
    symbol: 'رنيك',
    sector: 'خدمات فنی و مهندسی',
    score: 3,
    verdict: 'WATCH',
    passes: {
      '1_growth': false,
      '2_eps_trend': true,
      '3_gross_margin': false,
      '4_sales_to_mcap': true,
      '5_industry': true,
    },
    indicators: baseIndicators,
    history: [{ period_end: '1404/12/29', fiscal_year: '1404', revenue: 82657, gross_profit: 10500, net_profit: 9125, eps: 1615, audited: true, consolidated: false }],
    details,
    freshness: { as_of: '2026-07-09', axes: { '1_growth': { state: 'fresh', source: 'کدال' } } },
    profile: { kind: 'production', margin_class: 'production' },
    ...overrides,
  };
}

function mockCard(overrides: Record<string, unknown> = {}) {
  mockedCard.mockReturnValue({
    data: fixtureCard(overrides),
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useFtsCard>);
}

beforeEach(() => {
  mockCard();
  mockedSectorPe.mockReturnValue({
    data: { pe: 6.2, median: 7.5, sector: 'خدمات فنی و مهندسی', peers: 12 },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useSectorPe>);
  mockedHealth.mockReturnValue({
    data: {
      status: 'success',
      queue: { queued: 3, failed: 1, quarantined: 2 },
      dirty_symbols: 5,
      gap_flag: true,
      last_successful_sync: { at: '2026-11-04 10:00:00' },
      last_data_update: '2026-11-03 09:00:00',
    },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useCodalHealth>);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('fundamental cockpit', () => {
  it('renders quintet, five panels, history and evidence', () => {
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);

    expect(screen.getByTestId('fundamental-quintet').querySelectorAll('[data-axis]').length).toBe(5);
    expect(screen.getByTestId('panel-growth')).toBeTruthy();
    expect(screen.getByTestId('panel-eps')).toBeTruthy();
    expect(screen.getByTestId('panel-margin')).toBeTruthy();
    expect(screen.getByTestId('panel-sales')).toBeTruthy();
    expect(screen.getByTestId('panel-industry')).toBeTruthy();
    expect(screen.getByTestId('panel-history')).toBeTruthy();
    expect(screen.getByTestId('panel-evidence')).toBeTruthy();
    expect(screen.getByTestId('fundamental-score-ribbon').textContent).toContain('۳ از ۵');
    const freshness = screen.getByTestId('fundamental-freshness').textContent ?? '';
    expect(freshness).toContain('دادهٔ بنیادی تا');
    expect(freshness).not.toContain('2026-07-09');
  });

  it('keeps evidence keys unique across axes and shows the reasons', () => {
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const evidence = screen.getByTestId('panel-evidence');
    expect(evidence.textContent).toContain('رشد ریالی');
    expect(evidence.textContent).toContain('پایداری EPS');
  });

  it('renders holding N/A and no fake P/NAV', () => {
    mockCard({
      profile: { kind: 'holding', margin_class: 'holding', label: 'هلدینگ / سرمایه‌گذاری' },
      indicators: { ...baseIndicators, '4': { ...baseIndicators['4'], na: true, exempt: true } },
    });
    render(<FundamentalDetail symbol="ویسا" onBack={vi.fn()} />);
    expect(screen.getByTestId('holding-pnav-panel')).toBeTruthy();
    expect(screen.queryByTestId('panel-industry')).toBeNull();
    expect(screen.queryByText(/P\/NAV ≈/)).toBeNull();
  });

  it('shows the not-applicable notice and skips the cockpit for funds', () => {
    mockCard({ applicable: false, verdict: 'FTS ندارد', profile: { kind: 'fund' } });
    render(<FundamentalDetail symbol="صندوق" onBack={vi.fn()} />);
    expect(screen.getByTestId('fundamental-not-applicable').textContent).toContain('FTS ندارد');
    expect(screen.queryByTestId('fundamental-quintet')).toBeNull();
    expect(screen.queryByTestId('fundamental-score-ribbon')).toBeNull();
    expect(screen.getByTestId('corporate-calendar')).toBeTruthy();
    expect(screen.getByTestId('codal-health')).toBeTruthy();
  });

  it('does not turn missing EPS years into ۰/۳', () => {
    mockCard({
      indicators: { ...baseIndicators, '2': { ...baseIndicators['2'], years_available: null } },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const epsPanel = screen.getByTestId('panel-eps');
    expect(epsPanel.textContent).toContain('—/۳');
    expect(epsPanel.textContent).not.toContain('۰/۳');
    const epsQuintet = screen.getByTestId('fundamental-quintet').querySelector('[data-axis="eps"]');
    expect(epsQuintet?.textContent).toContain('—/۳');
    expect(epsQuintet?.textContent).not.toContain('۰/۳');
  });
});
