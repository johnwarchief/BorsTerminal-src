import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useCodalHealth } from '@features/fundamental/api/useCodalHealth';
import { useFtsCard } from '@features/fundamental/api/useFtsCard';
import { useQuarters } from '@features/fundamental/api/useQuarters';
import { useSectorPe } from '@features/fundamental/api/useSectorPe';
import { FundamentalDetail } from '@features/fundamental/ui/FundamentalDetail';

vi.mock('@features/fundamental/api/useFtsCard', () => ({ useFtsCard: vi.fn() }));
vi.mock('@features/fundamental/api/useQuarters', () => ({ useQuarters: vi.fn() }));
vi.mock('@features/fundamental/api/useSectorPe', () => ({ useSectorPe: vi.fn() }));
vi.mock('@features/fundamental/api/useCodalHealth', () => ({ useCodalHealth: vi.fn() }));
vi.mock('@features/fundamental/api/useCalendar', () => ({
  useSymbolCalendar: () => ({ data: { status: 'ok', events: [] }, isLoading: false, isError: false }),
}));

const mockedCard = vi.mocked(useFtsCard);
const mockedQuarters = vi.mocked(useQuarters);
const mockedSectorPe = vi.mocked(useSectorPe);
const mockedHealth = vi.mocked(useCodalHealth);

const details = Object.fromEntries(['۱', '۲', '۳', '۴', '۵'].map((digit) => [digit, {
  title: `عنوان ${digit}`,
  formula: `فرمول ${digit}`,
  source: `منبع ${digit}`,
  calc: `محاسبه ${digit}`,
  what: `توضیح ${digit}`,
  subchecks: [{ key: `${digit}a`, label: `زیرچک ${digit}`, state: 'pass', value: '۱۰٪', threshold: '≥ ۵٪', detail: 'جزئیات' }],
}]));

beforeEach(() => {
  mockedCard.mockReturnValue({
    data: {
      status: 'success', symbol: 'فولاد', sector: 'فلزات اساسی', score: 4, verdict: 'WATCH',
      details,
      freshness: { as_of: '2026-08-23', axes: {} },
    },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useFtsCard>);
  mockedQuarters.mockReturnValue({
    data: { status: 'success', quarters: [
      { period_end: '1405/06/31', period_months: 6, revenue: 1000, net_profit: 200, basic_eps: 50 },
    ] },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useQuarters>);
  mockedSectorPe.mockReturnValue({
    data: { pe: 6.2, median: 7.5, sector: 'فلزات اساسی', peers: 20 },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useSectorPe>);
  mockedHealth.mockReturnValue({
    data: {
      status: 'success', queue: { queued: 3, failed: 1, quarantined: 2 }, dirty_symbols: 5,
      gap_flag: true, last_successful_sync: { at: '2026-11-04 10:00:00' },
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

describe('fundamental detail', () => {
  it('shows five drilldown tabs and switches to axis detail', () => {
    render(<FundamentalDetail symbol="فولاد" onBack={vi.fn()} />);
    for (const digit of ['۱', '۲', '۳', '۴', '۵']) {
      expect(screen.getByTestId(`axis-tab-${digit}`)).toBeTruthy();
    }
    fireEvent.click(screen.getByTestId('axis-tab-۳'));
    expect(screen.getByTestId('axis-calc').textContent).toContain('محاسبه ۳');
    expect(screen.getByTestId('axis-subcheck-۳-۳a').textContent).toContain('زیرچک ۳');
  });

  it('renders quarterly rows, sector PE and codal health', () => {
    render(<FundamentalDetail symbol="فولاد" onBack={vi.fn()} />);
    expect(screen.getByTestId('quarter-row-0').textContent).toContain('1405/06/31');
    expect(screen.getByTestId('sector-pe').textContent).toContain('۶٫۲');
    expect(screen.getByTestId('sector-pe-median').textContent).toContain('۷٫۵');
    expect(screen.getByTestId('codal-health-queued').textContent).toContain('۳');
    expect(screen.getByTestId('codal-health').textContent).toContain('شکاف فید');
    expect(screen.getByTestId('fts-settings-btn')).toBeTruthy();
  });
});
