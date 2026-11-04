import { cleanup, fireEvent, render, screen } from '@testing-library/react';
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
  // R97: آستانهٔ هدفِ گیت (۶۰) جدا از threshold (۴۰) است؛ نمایش باید ۶۰ باشد.
  '1': {
    monetary: { monetary_pct: 45.9, threshold: 40, target_threshold: 60, pass: false, data_gap: false, reason: '' },
    volume: {
      applicable: false,
      real_pct: -8.8,
      volume_pct: null,
      pass: false,
      threshold: 0,
      data_gap: false,
      basis: 'price_effect_decomposition',
      note: 'این شرکت کالای وزن‌شدنی تولید نمی‌کند؛ چک فیزیکی روی مبنای متناسب است.',
    },
  },
  '2': { eps_series: [1119, 1615, 1672], years_available: 3, years_required: 3, evidence: 'تلفیقی', consolidated_used: true, data_gap: false, reason: '' },
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
    const ribbon = screen.getByTestId('fundamental-score-ribbon');
    expect(ribbon.textContent).toContain('۳ از ۵');
    // R94: شمارش رد با «·» از شمارش قبول جدا می‌شود («قبول۲ رد» نه).
    expect(ribbon.textContent).toContain('· ۲ رد');
    // R57: روبان هیچ رتبه‌بندی ساختگی از محورها اعلام نمی‌کند.
    expect(ribbon.textContent).not.toContain('قوی‌ترین');
    expect(ribbon.textContent).not.toContain('ضعیف‌ترین');
    // R97: کاشی و پنلِ رشد آستانهٔ هدفِ گیت (۶۰) را نشان می‌دهند، نه threshold=۴۰.
    const growthTile = screen.getByTestId('fundamental-quintet').querySelector('[data-axis="growth"]');
    expect(growthTile?.textContent).toContain('کف ۶۰٪');
    expect(growthTile?.textContent).not.toContain('کف ۴۰٪');
    expect(screen.getByTestId('panel-growth').textContent).toContain('کف ۶۰٪');
    expect(screen.getByTestId('panel-growth').textContent).not.toContain('کف ۴۰٪');
    const freshness = screen.getByTestId('fundamental-freshness').textContent ?? '';
    expect(freshness).toContain('دادهٔ بنیادی تا');
    expect(freshness).toContain('تیر');
    expect(freshness).not.toContain('2026-07-09');
    expect(freshness).not.toMatch(/[0-9]/);
    // R101: با محورهای fresh هیچ هشدارِ تازگی دیده نمی‌شود.
    expect(screen.queryByTestId('fundamental-freshness-attention')).toBeNull();
  });

  it('renders an ISO datetime freshness in Persian Jalali (R83)', () => {
    mockCard({ freshness: { as_of: '2026-06-30T18:50:20+03:30', axes: {} } });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const freshness = screen.getByTestId('fundamental-freshness').textContent ?? '';
    expect(freshness).toContain('دادهٔ بنیادی تا');
    expect(freshness).toContain('تیر');
    expect(freshness).toContain('۱۴۰۵');
    expect(freshness).not.toContain('2026-');
    expect(freshness).not.toContain('06-30');
    expect(freshness).not.toMatch(/[0-9]/);
  });

  it('keeps an unparseable freshness raw (R83)', () => {
    mockCard({ freshness: { as_of: 'نامعلوم', axes: {} } });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    expect(screen.getByTestId('fundamental-freshness').textContent).toContain('دادهٔ بنیادی تا نامعلوم');
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

  it('shows the last EPS with a trend arrow and the configured years in the panel and the quintet (R98)', () => {
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const epsPanel = screen.getByTestId('panel-eps');
    expect(epsPanel.textContent).toContain('۱۶۷۲ ↑');
    expect(epsPanel.textContent).toContain('سال‌های موجود');
    expect(epsPanel.textContent).toContain('۳/۳');
    const epsTile = screen.getByTestId('fundamental-quintet').querySelector('[data-axis="eps"]');
    expect(epsTile?.textContent).toContain('۱۶۷۲ ↑');
    expect(epsTile?.textContent).toContain('۳ سال');
  });

  it('does not turn missing EPS years into ۰/۳ (R30/R50)', () => {
    mockCard({
      indicators: { ...baseIndicators, '2': { ...baseIndicators['2'], years_available: null } },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const epsPanel = screen.getByTestId('panel-eps');
    expect(epsPanel.textContent).toContain('—/۳');
    expect(epsPanel.textContent).not.toContain('۰/۳');
    const epsQuintet = screen.getByTestId('fundamental-quintet').querySelector('[data-axis="eps"]');
    expect(epsQuintet?.textContent).not.toContain('۰/۳');
  });

  it('honors the EPS gate setting of 1 year in the panel and the quintet (R99)', () => {
    mockCard({
      thresholds: { growth_min: 60, margin_min: 40, v10_eps_years: 1 },
      indicators: { ...baseIndicators, '2': { ...baseIndicators['2'], years_required: null } },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const epsPanel = screen.getByTestId('panel-eps');
    expect(epsPanel.textContent).toContain('۳/۱');
    expect(epsPanel.textContent).toContain('۱ سال');
    expect(epsPanel.textContent).not.toContain('۳/۳');
    const epsTile = screen.getByTestId('fundamental-quintet').querySelector('[data-axis="eps"]');
    expect(epsTile?.textContent).toContain('۱ سال');
  });

  it('shows the 1b value and its status word, plus the growth note (R97)', () => {
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const growth = screen.getByTestId('panel-growth');
    expect(growth.textContent).toContain('۱ب');
    expect(growth.textContent).toContain('N/A');
    expect(growth.textContent).toContain('بی‌نظر');
    expect(growth.textContent).toContain('کالای وزن‌شدنی');
  });

  it('uses the real 1b percentage and pass word when volume is applicable (R97)', () => {
    mockCard({
      indicators: {
        ...baseIndicators,
        '1': {
          ...baseIndicators['1'],
          volume: { applicable: true, real_pct: -8.8, volume_pct: -3.1, pass: false, threshold: 0, data_gap: false },
        },
      },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const growth = screen.getByTestId('panel-growth');
    expect(growth.textContent).toContain('−۸٫۸٪');
    expect(growth.textContent).not.toContain('−۳٫۱٪');
    expect(growth.textContent).toContain('رد');
  });

  it('turns a growth data gap into نامشخص instead of a pass/fail claim (R97)', () => {
    mockCard({
      indicators: {
        ...baseIndicators,
        '1': { ...baseIndicators['1'], volume: { ...baseIndicators['1'].volume, data_gap: true } },
      },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const growthTile = screen.getByTestId('fundamental-quintet').querySelector('[data-axis="growth"]');
    expect(growthTile?.textContent).toContain('نامشخص');
    expect(growthTile?.textContent).not.toContain('رد');
    expect(screen.getByTestId('panel-growth').textContent).toContain('نامشخص');
  });

  it('surfaces the stale/missing freshness axes next to the date (R101)', () => {
    mockCard({
      freshness: {
        as_of: '2026-07-09',
        axes: {
          '1_growth': { state: 'stale', source: 'monthly_sales' },
          '2_eps_trend': { state: 'fresh', source: 'financial_statements' },
          '3_gross_margin': { state: 'quarantined', source: 'financial_statements' },
          '4_sales_to_mcap': { state: 'missing' },
          '5_industry': { state: 'fresh' },
        },
      },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const attention = screen.getByTestId('fundamental-freshness-attention');
    expect(attention.textContent).toContain('۳ محور نیازمند بررسی');
    expect(attention.getAttribute('title')).toContain('رشد فروش');
    expect(attention.getAttribute('title')).toContain('حاشیهٔ ناخالص');
    expect(attention.getAttribute('title')).toContain('فروش / ارزش');
    expect(attention.getAttribute('title')).not.toContain('سودآوری');
  });

  it('shows the margin and EPS reasons in the panels (R101)', () => {
    mockCard({
      indicators: {
        ...baseIndicators,
        '2': { ...baseIndicators['2'], data_gap: true, reason: '' },
        '3': { ...baseIndicators['3'], reason: 'حاشیه زیر کفِ ۴۰٪ است' },
      },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    expect(screen.getByTestId('panel-margin').textContent).toContain('حاشیه زیر کفِ ۴۰٪ است');
    expect(screen.getByTestId('panel-eps').textContent).toContain('شکاف دادهٔ EPS');
    const epsTile = screen.getByTestId('fundamental-quintet').querySelector('[data-axis="eps"]');
    expect(epsTile?.textContent).toContain('نامشخص');
  });

  it('maps the live margin tiers good/standard/floor/above_floor (R103)', () => {
    const cases: Array<[string, string]> = [
      ['good', 'خوب'],
      ['standard', 'استاندارد'],
      ['floor', 'کف'],
      ['above_floor', 'بالای کف'],
    ];
    for (const [token, word] of cases) {
      mockCard({ indicators: { ...baseIndicators, '3': { ...baseIndicators['3'], margin_tier: token } } });
      render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
      expect(screen.getByTestId('panel-margin').textContent).toContain(word);
      expect(screen.getByTestId('panel-margin').textContent).not.toContain(token);
      cleanup();
    }
  });

  it('maps the live EPS evidence tokens and the live market share (R103)', () => {
    mockCard({
      indicators: {
        ...baseIndicators,
        '2': {
          ...baseIndicators['2'],
          evidence: ['consolidated_unaudited', 'consolidated_audited', 'annualized_interim'],
        },
        '5': { ...baseIndicators['5'], market_share_pct: 0.025 },
      },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const eps = screen.getByTestId('panel-eps').textContent ?? '';
    expect(eps).toContain('تلفیقیِ حسابرسی‌نشده');
    expect(eps).toContain('تلفیقیِ حسابرسی‌شده');
    expect(eps).toContain('سال‌سازیِ میاندوره');
    expect(eps).not.toContain('consolidated_');
    expect(eps).not.toContain('annualized_interim');
    const industry = screen.getByTestId('panel-industry').textContent ?? '';
    // ۰٫۰۲۵٪ نباید «۰٫۰٪» شود.
    expect(industry).toContain('۰٫۰۲۵٪');
    expect(industry).not.toContain('۰٫۰٪');
    cleanup();
    mockCard({ indicators: { ...baseIndicators, '5': { ...baseIndicators['5'], market_share_pct: 4.2 } } });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    expect(screen.getByTestId('panel-industry').textContent).toContain('۴٫۲۰٪');
  });

  it('localizes evidence digits/commas and the Codal health strip (R103)', () => {
    mockCard({
      details: {
        ...details,
        '۳': {
          title: 'حاشیه',
          formula: 'x',
          source: 'کدال',
          subchecks: [{ key: '3a', label: 'حاشیه', state: 'pass', value: '1,234.5', threshold: '≥ 20', detail: 'سود 6,000 ریال' }],
        },
      },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const evidence = screen.getByTestId('panel-evidence');
    expect(evidence.textContent).toContain('۱٬۲۳۴٫۵');
    expect(evidence.textContent).not.toContain('1,234.5');
    expect(evidence.querySelector('[title="سود ۶٬۰۰۰ ریال"]')).toBeTruthy();
    const health = screen.getByTestId('codal-health').textContent ?? '';
    expect(health).toContain('همگام‌سازی موفق');
    expect(health).not.toContain('sync');
    expect(health).toContain('۲۰۲۶-۱۱-۰۴ ۱۰:۰۰:۰۰');
    expect(health).not.toContain('2026-11-04');
  });

  it('renders the loading state on the data surface with back, title and settings (R102)', () => {
    mockedCard.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof useFtsCard>);
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const loading = screen.getByTestId('fundamental-detail-loading');
    expect(loading.className).toContain('fundamental-surface');
    expect(loading.className).toContain('bg-[var(--fd-bg)]');
    expect(loading.className).toContain('text-[var(--fd-text)]');
    expect(loading.getAttribute('data-fund-surface')).toBe('paper');
    expect(screen.getByTestId('fundamental-back')).toBeTruthy();
    expect(screen.getByTestId('fundamental-title').textContent).toBe('رنيك');
    expect(screen.getByTestId('fts-settings-trigger')).toBeTruthy();
    expect(loading.textContent).toContain('در حال خواندن');
  });

  it('renders the error state on the data surface with back, title, settings and retry (R102)', () => {
    const refetch = vi.fn();
    mockedCard.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch,
    } as unknown as ReturnType<typeof useFtsCard>);
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const error = screen.getByTestId('fundamental-detail-error');
    expect(error.className).toContain('fundamental-surface');
    expect(error.className).toContain('bg-[var(--fd-bg)]');
    expect(error.getAttribute('data-fund-surface')).toBe('paper');
    expect(screen.getByTestId('fundamental-back')).toBeTruthy();
    expect(screen.getByTestId('fundamental-title').textContent).toBe('رنيك');
    expect(screen.getByTestId('fts-settings-trigger')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'تلاش دوباره' }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it('maps array evidence tokens to Persian and joins with «، » (R82/R88)', () => {
    mockCard({
      indicators: {
        ...baseIndicators,
        '2': {
          ...baseIndicators['2'],
          evidence: ['audited_year_end', 'audited_year_end', 'annualized_interim_short'],
        },
      },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const epsPanel = screen.getByTestId('panel-eps');
    expect(epsPanel.textContent).toContain('شواهد');
    expect(epsPanel.textContent).toContain('سال‌پایانِ حسابرسی‌شده، سال‌پایانِ حسابرسی‌شده، سال‌سازیِ میاندورهٔ کوتاه');
    expect(epsPanel.textContent).not.toContain('audited_year_end');
    expect(epsPanel.textContent).not.toContain('annualized_interim_short');
  });

  it('keeps unknown evidence tokens raw and a string evidence as-is (R88)', () => {
    mockCard({
      indicators: { ...baseIndicators, '2': { ...baseIndicators['2'], evidence: ['mystery_token'] } },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    expect(screen.getByTestId('panel-eps').textContent).toContain('mystery_token');
    cleanup();
    mockCard({
      indicators: { ...baseIndicators, '2': { ...baseIndicators['2'], evidence: 'شاهد یکتا' } },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    expect(screen.getByTestId('panel-eps').textContent).toContain('شاهد یکتا');
  });

  it('maps live margin tiers to Persian and keeps unknown raw (R89)', () => {
    mockCard({
      indicators: { ...baseIndicators, '3': { ...baseIndicators['3'], margin_tier: 'below_floor' } },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    expect(screen.getByTestId('panel-margin').textContent).toContain('زیر کف');
    cleanup();
    mockCard({
      indicators: { ...baseIndicators, '3': { ...baseIndicators['3'], margin_tier: 'acceptable' } },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    expect(screen.getByTestId('panel-margin').textContent).toContain('قابل قبول');
    cleanup();
    mockCard({
      indicators: { ...baseIndicators, '3': { ...baseIndicators['3'], margin_tier: 'odd_token' } },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    expect(screen.getByTestId('panel-margin').textContent).toContain('odd_token');
  });

  it('renders growth with an explicit +/− sign in the quintet and the panel (R91)', () => {
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const growthTile = () => screen.getByTestId('fundamental-quintet').querySelector('[data-axis="growth"]');
    expect(growthTile()?.textContent).toContain('+۴۵٫۹٪');
    expect(screen.getByTestId('panel-growth').textContent).toContain('+۴۵٫۹٪');
    cleanup();
    mockCard({
      indicators: {
        ...baseIndicators,
        '1': { ...baseIndicators['1'], monetary: { ...baseIndicators['1'].monetary, monetary_pct: -3.2 } },
      },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    expect(growthTile()?.textContent).toContain('−۳٫۲٪');
    expect(screen.getByTestId('panel-growth').textContent).toContain('−۳٫۲٪');
  });

  it('renders history dates in Persian digits (R58)', () => {
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const history = screen.getByTestId('panel-history');
    expect(history.textContent).toContain('۱۴۰۴/۱۲/۲۹');
    expect(history.textContent).not.toContain('1404/12/29');
  });

  it('shows بی‌نظر for an axis whose pass key is absent but whose indicator is na (R60)', () => {
    mockCard({
      passes: { '1_growth': false, '2_eps_trend': true, '3_gross_margin': false, '5_industry': true },
      indicators: { ...baseIndicators, '4': { ...baseIndicators['4'], na: true } },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const salesTile = screen.getByTestId('fundamental-quintet').querySelector('[data-axis="sales"]');
    expect(salesTile?.textContent).toContain('بی‌نظر');
    expect(salesTile?.textContent).not.toContain('رد');
  });

  it('shows نامشخص — never رد — when the pass key is absent and no na flag exists (R60)', () => {
    mockCard({
      passes: { '1_growth': false, '2_eps_trend': true, '3_gross_margin': false, '5_industry': true },
    });
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const salesTile = screen.getByTestId('fundamental-quintet').querySelector('[data-axis="sales"]');
    expect(salesTile?.textContent).toContain('نامشخص');
    expect(salesTile?.textContent).not.toContain('رد');
    expect(screen.getByTestId('panel-sales').textContent).toContain('نامشخص');
  });
});
