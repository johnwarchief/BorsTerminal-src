import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FtsCardSchema, useFtsCard } from '@features/fundamental/api/useFtsCard';
import { useSectorPe } from '@features/fundamental/api/useSectorPe';
import { FundamentalDetail } from '@features/fundamental/ui/FundamentalDetail';
import { cardStatus } from '@features/fundamental/lib/cardStatus';

vi.mock('@features/fundamental/api/useFtsCard', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@features/fundamental/api/useFtsCard')>()),
  useFtsCard: vi.fn(),
}));
vi.mock('@features/fundamental/api/useSectorPe', () => ({ useSectorPe: vi.fn() }));
vi.mock('@features/fundamental/api/useCodalHealth', () => ({
  useCodalHealth: () => ({ data: { status: 'success', queue: {}, dirty_symbols: 0, gap_flag: false }, isLoading: false, isError: false }),
}));
vi.mock('@features/fundamental/api/useCalendar', () => ({
  useSymbolCalendar: () => ({ data: { status: 'ok', events: [] }, isLoading: false, isError: false }),
}));

const details = Object.fromEntries(['۱', '۲', '۳', '۴', '۵'].map((d) => [d, {
  title: `عنوان ${d}`, formula: `فرمول ${d}`, source: `منبع ${d}`, calc: `محاسبه ${d}`, what: `توضیح ${d}`, subchecks: [],
}]));

const productionIndicators = {
  '1': { monetary: { monetary_pct: 56, threshold: 40, target_threshold: 60, pass: true, ytd_now_bt: 250942, ytd_prev_bt: 160873 }, volume: { applicable: true, real_pct: -2.5, pass: false } },
  '2': { eps_series: [1119, 1615, 1672], years_available: 3, years_required: 3 },
  '3': { margin_pct: 29.1, threshold: 20, optimal_threshold: 30, band: 'floor' },
  '4': { sales_to_mcap: 0.6, sales_threshold: 0.33, available: true, potential_pct: 17.6, potential_threshold: 40 },
  '5': { label: 'قیمت‌گذاری آزاد / بورس کالا', regime_label: 'سایر صنایع', sector: 'فلزات اساسي', pass: true, exclusion_active: false },
};

/** کارتِ بیمه: «خارج از غربال» ولی محور ۵ هنوز pass=true — همان حالتِ البرزِ زنده. */
const insuranceCard = {
  status: 'success', symbol: 'البرز', sector: 'بيمه وصندوق بازنشستگي به جزتامين اجتماعي',
  verdict: 'EXCLUDED', score: 3, applicable: true, excluded: true, exclusion_reasons: ['صنعت بیمه — حذف خودکار'],
  profile: { kind: 'production' }, details, freshness: { as_of: '2026-07-21', axes: {} },
  indicators: { ...productionIndicators, '2': { eps_series: [1, 2, 3], years_available: 3, years_required: 3, data_gap: true }, '3': { margin_pct: null, threshold: 20, na: true } },
  passes: { '1_growth': true, '2_eps_trend': null, '3_gross_margin': null, '4_sales_to_mcap': true, '5_industry': true },
} as Record<string, unknown>;

/** کارتِ هلدینگ: محور ۵ برایِ این طبقه سنجیده نمی‌شود (همان وسبحانِ زنده). */
const holdingCard = {
  status: 'success', symbol: 'وسبحان', sector: 'سرمايه گذاريها', verdict: 'WATCH', score: 3, applicable: true,
  profile: { kind: 'holding', margin_class: 'holding', label: 'هلدینگ / سرمایه‌گذاری' },
  details, freshness: { as_of: '2026-09-18', axes: {} },
  indicators: { ...productionIndicators, '3': { margin_pct: null, threshold: 20, na: true }, '4': { sales_to_mcap: null, available: true, na: true, exempt: true } },
  passes: { '1_growth': true, '2_eps_trend': true, '3_gross_margin': null, '4_sales_to_mcap': null, '5_industry': true },
} as Record<string, unknown>;

const mockedCard = vi.mocked(useFtsCard);

function serve(card: Record<string, unknown>) {
  mockedCard.mockReturnValue({
    data: card as never, isLoading: false, isError: false, refetch: vi.fn(),
  } as unknown as ReturnType<typeof useFtsCard>);
}

beforeEach(() => {
  vi.mocked(useSectorPe).mockReturnValue({
    data: { pe: 7.2, median: 6.9, peers: 73, sector: 'سایر' }, isLoading: false, isError: false,
  } as unknown as ReturnType<typeof useSectorPe>);
});

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe('وتویِ صنعتی و شمارشِ صادق (B-1/M-1/M-2)', () => {
  it('parses the exclusion fields and the axis-5 exclusion flag', () => {
    const parsed = FtsCardSchema.parse(insuranceCard) as Record<string, unknown>;
    expect(parsed.excluded).toBe(true);
    expect(parsed.exclusion_reasons).toEqual(['صنعت بیمه — حذف خودکار']);
    const ind5 = (parsed.indicators as Record<string, Record<string, unknown>>)['5'];
    expect(ind5.exclusion_active).toBe(false);
    // نبودِ این کلیدها کارت را نمی‌شکند (طبقهٔ عادی).
    const plain = FtsCardSchema.parse({ ...productionIndicators, ...holdingCard, excluded: undefined, exclusion_reasons: undefined });
    expect(plain).toBeTruthy();
  });

  it('a class-vetoed card fails axis 5 even though the backend passes it', () => {
    const card = FtsCardSchema.parse(insuranceCard);
    expect(cardStatus(card, 'industry')).toBe('fail');
    // بقیهٔ محورها قاعدهٔ خودشان را نگه می‌دارند.
    expect(cardStatus(card, 'growth')).toBe('pass');
  });

  it('a holding or bank does not score axis 5 at all', () => {
    const card = FtsCardSchema.parse(holdingCard);
    expect(cardStatus(card, 'industry')).toBe('na');
  });

  it('header names the exclusion reason and the ribbon counts only scored axes', () => {
    serve(insuranceCard);
    render(<FundamentalDetail symbol="البرز" onBack={vi.fn()} />);
    expect(screen.getByTestId('fundamental-exclusion-reason').textContent).toContain('صنعت بیمه — حذف خودکار');
    const ribbon = screen.getByTestId('fundamental-score-ribbon').textContent ?? '';
    expect(ribbon).toContain('از ۴');
    expect(ribbon).toContain('وتوی صنعتی');
    expect(ribbon).not.toContain('از ۵');
    const panel = screen.getByTestId('panel-industry');
    expect(panel.querySelector('[class*="fd-status--"]')?.textContent).toBe('رد');
  });

  it('a holding keeps an axis-5 panel with a class reason and an honest ribbon', () => {
    serve(holdingCard);
    render(<FundamentalDetail symbol="وسبحان" onBack={vi.fn()} />);
    const panel = screen.getByTestId('panel-industry');
    expect(panel.querySelector('[class*="fd-status--"]')?.textContent).toBe('بی‌نظر');
    expect(panel.textContent).toContain('برایِ این طبقه سنجیده نمی‌شود');
    const ribbon = screen.getByTestId('fundamental-score-ribbon').textContent ?? '';
    expect(ribbon).toContain('۴ محور سنجیده شد');
    expect(ribbon).not.toContain('از ۵');
    // پنلِ P/NAV سرِ جایش می‌ماند؛ دیگر جای پنلِ ۵ را نمی‌گیرد.
    expect(screen.getByTestId('holding-pnav-panel')).toBeTruthy();
  });

  it('a normal producer still counts five axes and shows no veto line', () => {
    serve({
      status: 'success', symbol: 'فولاد', sector: 'فلزات اساسي', verdict: 'WATCH', score: 3, applicable: true,
      profile: { kind: 'production' }, details, freshness: { as_of: '2026-09-01', axes: {} },
      indicators: productionIndicators,
      passes: { '1_growth': false, '2_eps_trend': true, '3_gross_margin': true, '4_sales_to_mcap': true, '5_industry': true },
    });
    render(<FundamentalDetail symbol="فولاد" onBack={vi.fn()} />);
    const ribbon = screen.getByTestId('fundamental-score-ribbon').textContent ?? '';
    expect(ribbon).toContain('از ۵');
    expect(ribbon).not.toContain('وتو');
    expect(ribbon).not.toContain('سنجیده شد');
    expect(screen.queryByTestId('fundamental-exclusion-reason')).toBeNull();
  });
});
