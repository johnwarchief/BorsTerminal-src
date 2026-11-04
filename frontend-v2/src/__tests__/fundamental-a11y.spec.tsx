import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useCodalHealth } from '@features/fundamental/api/useCodalHealth';
import { useFtsCard } from '@features/fundamental/api/useFtsCard';
import { useSectorPe } from '@features/fundamental/api/useSectorPe';
import { FundamentalDetail } from '@features/fundamental/ui/FundamentalDetail';
import { FundamentalScreenTable } from '@features/fundamental/ui/FundamentalScreenTable';
import { useFundamentalPrefs } from '@features/fundamental/stores/prefs';
import { resetExcludeAxes } from '@features/fundamental/lib/exclusionFilter';
import type { ScreenerCoreRow } from '@features/fundamental/api/useScreenerCore';

vi.mock('@features/fundamental/api/useFtsCard', () => ({ useFtsCard: vi.fn() }));
vi.mock('@features/fundamental/api/useSectorPe', () => ({ useSectorPe: vi.fn() }));
vi.mock('@features/fundamental/api/useCodalHealth', () => ({ useCodalHealth: vi.fn() }));
vi.mock('@features/fundamental/api/useCalendar', () => ({
  useSymbolCalendar: () => ({ data: { status: 'ok', events: [] }, isLoading: false, isError: false }),
}));

const mockedCard = vi.mocked(useFtsCard);
const mockedSectorPe = vi.mocked(useSectorPe);
const mockedHealth = vi.mocked(useCodalHealth);

const originalScrollIntoView = Element.prototype.scrollIntoView;
const scrollSpy = vi.fn();

/** R81: jsdom هیچ matchMedia ندارد؛ برای هر دو حالت حرکت، stub صریح می‌سازیم. */
function stubMatchMedia(reduceMotion: boolean) {
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation((query: string) => ({
    matches: reduceMotion && query.includes('prefers-reduced-motion'),
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })));
}

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

function fixtureCard() {
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
  };
}

beforeEach(() => {
  resetExcludeAxes();
  useFundamentalPrefs.setState({ density: 'comfortable', sortKey: 'score', sortDir: 'desc' });
  Element.prototype.scrollIntoView = scrollSpy;
  mockedCard.mockReturnValue({
    data: fixtureCard(),
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useFtsCard>);
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
  vi.unstubAllGlobals();
  Element.prototype.scrollIntoView = originalScrollIntoView;
});

describe('fundamental accessibility and motion', () => {
  it('exposes sort state and keyboard rows (R14/R32)', () => {
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    // R14: اگر نقشِ row نامِ ردیف را ندهد، testid منبعِ قطعیِ تست است.
    const row = screen.getByTestId('fundamental-row-رنيك');
    expect(row.getAttribute('tabindex')).toBe('0');
    expect(row.className).toContain('fd-row');
    expect(document.querySelector('[aria-sort]')).toBeTruthy();
    expect(document.querySelector('[aria-sort="descending"]')).toBeTruthy();
    // R73/R74: ردیف‌های جدول انیمیشنِ ورود نمی‌گیرند.
    expect(document.querySelector('.fd-in, .fd-draw')).toBeNull();
  });

  it('dips the table body once per density change (R78)', () => {
    vi.useFakeTimers();
    try {
      const { container } = render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
      const scroll = () => container.querySelector('.fd-scroll')!;
      // نصب اولیه هیچ dipی نمی‌گیرد.
      expect(scroll().className).not.toContain('is-fading');
      act(() => useFundamentalPrefs.setState({ density: 'compact' }));
      expect(scroll().className).toContain('is-fading');
      act(() => { vi.advanceTimersByTime(159); });
      expect(scroll().className).toContain('is-fading');
      act(() => { vi.advanceTimersByTime(1); });
      expect(scroll().className).not.toContain('is-fading');
      act(() => useFundamentalPrefs.setState({ density: 'comfortable' }));
      expect(scroll().className).toContain('is-fading');
      act(() => { vi.advanceTimersByTime(160); });
      expect(scroll().className).not.toContain('is-fading');
    } finally {
      vi.useRealTimers();
    }
  });

  it('skips the density dip when reduced motion is requested (R78)', () => {
    stubMatchMedia(true);
    vi.useFakeTimers();
    try {
      const { container } = render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
      act(() => useFundamentalPrefs.setState({ density: 'compact' }));
      expect(container.querySelector('.fd-scroll')!.className).not.toContain('is-fading');
    } finally {
      vi.useRealTimers();
    }
  });

  it('marks the app-theme surface on the detail root (R76)', () => {
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const detail = screen.getByTestId('fundamental-detail');
    expect(detail.dataset.fundSurface).toBeUndefined();
    expect(detail.className).toContain('fundamental-surface');
  });

  it('scrolls smoothly to and focuses the panel header after a quintet click (R75/R79/R81)', () => {
    stubMatchMedia(false);
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const tile = screen.getByTestId('fundamental-quintet').querySelector('[data-axis="margin"]')!;
    fireEvent.click(tile);
    expect(scrollSpy).toHaveBeenCalledTimes(1);
    expect(scrollSpy.mock.calls[0]![0]).toMatchObject({ block: 'start', behavior: 'smooth' });
    // R79: فوکوس روی سرصفحهٔ پنل است، نه ریشه.
    expect(document.activeElement?.id).toBe('panel-margin-title');
    expect(document.activeElement?.tagName).toBe('HEADER');
    expect(screen.getByTestId('panel-margin').getAttribute('tabindex')).toBe('-1');
    expect(document.getElementById('panel-margin-title')?.getAttribute('tabindex')).toBe('-1');
  });

  it('jumps with behavior auto instead of smooth under reduced motion (R76/R81)', () => {
    stubMatchMedia(true);
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const tile = screen.getByTestId('fundamental-quintet').querySelector('[data-axis="margin"]')!;
    fireEvent.click(tile);
    expect(scrollSpy).toHaveBeenCalledTimes(1);
    expect(scrollSpy.mock.calls[0]![0]).toMatchObject({ block: 'start', behavior: 'auto' });
    expect(document.activeElement?.id).toBe('panel-margin-title');
  });

  it('labels all five ribbon bars with the axis and the Persian status (R72/R81)', () => {
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const bars = Array.from(screen.getByTestId('fundamental-score-ribbon').querySelectorAll('[data-status]'));
    expect(bars.length).toBe(5);
    const labels = bars.map((bar) => bar.getAttribute('aria-label') ?? '');
    for (const [index, bar] of bars.entries()) {
      const label = labels[index]!;
      expect(label).toMatch(/قبول|رد|بی‌نظر|نامشخص/);
      expect(bar.getAttribute('title')).toBe(label);
      // R72: میله‌ها از AT پنهان نیستند و کلاسِ وضعیتِ بی‌اثر ندارند.
      expect(bar.getAttribute('aria-hidden')).toBeNull();
      expect(bar.className).not.toContain('fd-status--');
    }
    // R81: ترتیب میله‌ها = ترتیب محورها (رشد، سودآوری، حاشیه، پتانسیل، صنعت) و
    // data-status هر میله از همان وضعیتِ محورِ متناظر می‌آید.
    expect(bars.map((bar) => bar.getAttribute('data-status'))).toEqual(['fail', 'pass', 'fail', 'pass', 'pass']);
    const axisLabels = ['رشد فروش', 'سودآوری ۳ساله', 'حاشیهٔ ناخالص', 'پتانسیل سود تا آخر سال', 'نرخ‌گذاری صنعت'];
    for (const [index, axisLabel] of axisLabels.entries()) expect(labels[index]).toContain(axisLabel);
  });

  it('keeps panel roots focusable and staggers only detail wrappers (R73/R77)', () => {
    const { container } = render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    for (const axis of ['growth', 'eps', 'margin', 'sales', 'industry', 'history']) {
      const panel = screen.getByTestId(`panel-${axis}`);
      expect(panel.getAttribute('tabindex')).toBe('-1');
      expect(panel.id).toBe(`panel-${axis}`);
      expect(panel.className).toContain('fd-panel');
    }
    expect(screen.getByTestId('fundamental-quintet').className).toContain('fd-in');
    expect(screen.getByTestId('fundamental-score-ribbon').className).toContain('fd-in');
    // R80: دقیقاً ۹ wrapper جزئیات کلاس اختصاصی fd-enter دارند (نه fd-in).
    const wrappers = Array.from(container.querySelectorAll('.fd-enter'));
    expect(wrappers.length).toBe(9);
    for (const wrapper of wrappers) expect(wrapper.className).not.toContain('fd-in');
    // R73: نمودارِ پنل‌های جزئیات fd-draw دارد؛ ریشهٔ پنل انیمیشنِ ورود نمی‌گیرد.
    expect(screen.getByTestId('panel-margin').querySelector('.fd-draw')).toBeTruthy();
    expect(screen.getByTestId('panel-margin').className).not.toContain('fd-draw');
  });
});
