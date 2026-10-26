// src/__tests__/fts-fundamental-labels.spec.tsx
// Task 4 — N/A صادقانه: نشانِ خاکستری با دلیلِ ماشین، هرگز ✗ سرخ برایِ ردیفِ
// بی‌داده؛ کارت و دریل‌دان همان دلیل و مبنایِ رشد (ماهانه/صورتِ مالی) را می‌گویند.
import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FtsScreenTable, screenRowCells } from '@features/fundamental/ui/FtsScreenTable';
import { FtsCard } from '@features/fundamental/components/FtsCard';
import { FtsDrillDown } from '@features/fundamental/components/FtsDrillDown';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';
import type { FtsCardIndicators } from '@features/fundamental/api/useFtsCard';

vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  const WINDOW = 14;
  return {
    ...mod,
    useVirtualizer: (opts: { count: number }) => ({
      getTotalSize: () => opts.count * 46,
      getVirtualItems: () =>
        Array.from({ length: Math.min(opts.count, WINDOW) }, (_, i) => ({
          key: i, index: i, start: i * 46,
        })),
    }),
  };
});

function row(patch: Partial<FtsScreenRow> = {}): FtsScreenRow {
  return {
    symbol: 'شپنا',
    name: 'پالایش نفت اصفهان',
    sector_name: 'محصولات نفتي، كك و سوخت هسته اي',
    pricing_mode: 'free',
    rev_growth: 45.2,
    eps_series: [100, 120, 150],
    eps_years_available: 3,
    eps_years_required: 3,
    gross_margin: 32.4,
    sales_to_mcap: 1.2,
    profit_potential_pct: 42.0,
    score: 4,
    i1_pass: true,
    i1a_pass: true,
    i1b_pass: true,
    i1b_applicable: true,
    i2_pass: true,
    i3_pass: true,
    i4_pass: true,
    i5_pass: true,
    verdict: 'WATCH',
    excluded: false,
    applicable: true,
    ...patch,
  } as FtsScreenRow;
}

const renderRows = (rows: FtsScreenRow[]) =>
  render(<FtsScreenTable rows={rows} onSelect={() => {}} thresholds={{}} />);

describe('ردیفِ N/A شاخص ۱ — خاکستری با دلیل، نه ✗', () => {
  const gapReason = 'فروش تجمیعیِ همان دورۀ سال قبل در کدال ثبت نشده؛ مقایسهٔ سال‌به‌سال ممکن نیست.';

  it('i1_na=true: یک N/A خاکستری با title دلیل، بدون نشانِ الف/ب و بدون ✗', () => {
    renderRows([row({
      rev_growth: null,
      i1_pass: null,
      i1_na: true,
      i1_reason: gapReason,
      i1a_pass: false,
      i1b_pass: false,
      i1b_applicable: true,
    })]);
    const na = screen.getByTestId('fts-na-1_growth');
    expect(na.textContent).toContain('N/A');
    expect(na.getAttribute('title')).toBe(gapReason);
    expect(na.className).toContain('text-text-secondary');
    expect(na.className).not.toContain('text-accent-red');
    expect(na.className).not.toContain('text-accent-yellow');
    expect(screen.queryByTestId('fts-mark-1a_monetary_growth')).toBeNull();
    expect(screen.queryByTestId('fts-mark-1b_volume_growth')).toBeNull();
    const tr = screen.getByTestId('fts-screen-row');
    expect(within(tr).queryByText('✗')).toBeNull();
  });

  it('i1_na=false: حکمِ سنجیده‌شده همان ✓/✗ را می‌گیرد (N/A جای آن را نمی‌گیرد)', () => {
    renderRows([row({ i1_na: false, i1a_pass: true, i1b_pass: true })]);
    expect(screen.queryByTestId('fts-na-1_growth')).toBeNull();
    expect(screen.getByTestId('fts-mark-1a_monetary_growth').textContent).toContain('✓');
  });

  it('فایلِ دانلودی هم برایِ i1_na همان N/A را می‌نویسد', () => {
    const r = row({ rev_growth: null, i1_pass: null, i1_na: true, i1a_pass: false, i1b_pass: false });
    expect(screenRowCells(r)[1]).toBe('N/A');
    // و ردیفِ عادی هنوز حکمِ تفکیک‌شدهٔ الف/ب را دارد
    expect(screenRowCells(row({ i1a_pass: false, i1b_pass: true }))[1]).toContain('الف: ✗');
  });
});

describe('N/A شاخص‌های ۳ و ۴ — ماهیت مالی، نه رد', () => {
  it('i3_na/i4_na: هر دو N/A خاکستری با دلیلِ خودشان‌اند', () => {
    renderRows([row({
      i3_pass: null, i3_na: true, gross_margin: null,
      i4_pass: null, i4_na: true, sales_to_mcap: null, profit_potential_pct: null,
    })]);
    for (const id of ['fts-na-3_gross_margin', 'fts-na-4_sales_to_mcap']) {
      const el = screen.getByTestId(id);
      expect(el.textContent).toContain('N/A');
      expect(el.className).toContain('text-text-secondary');
      expect(el.className).not.toContain('text-accent-red');
      expect(el.getAttribute('title')).toBeTruthy();
    }
    const tr = screen.getByTestId('fts-screen-row');
    expect(within(tr).queryByText('✗')).toBeNull();
  });
});

// ── کارت و دریل‌دان ────────────────────────────────────────────────────────
const GAP_REASON = 'دورهٔ مشابهٔ سال قبل برای جدیدترین صورت مالی موجود نیست؛ از دورهٔ قدیمی‌تر استفاده نمی‌شود.';

function cardIndicators(patch: Partial<NonNullable<FtsCardIndicators['1']>> = {}): FtsCardIndicators {
  return {
    '1': {
      monetary: {
        monetary_pct: null, data_gap: true, reason: GAP_REASON, basis: 'fs_unavailable',
        pass: false,
      },
      volume: {
        applicable: true, pass: false, data_gap: true,
        reason: 'رشد ریالی محاسبه نشد؛ رشد تولیدی هم قابل بررسی نیست.',
      },
      pass: null,
      reason: GAP_REASON,
      ...patch,
    },
    '2': { eps_series: [], na: true, pass: false, reason: '' },
    '3': { margin_pct: null, na: true, pass: false, reason: '' },
    '4': { na: true, exempt: true, pass: false, reason: '' },
    '5': { pass: true },
  } as FtsCardIndicators;
}

describe('کارتِ شاخص ۱ — شکاف داده «نظر نمی‌دهد»، نه «رد»', () => {
  it('چیپ‌های ۱الف/۱ب خاکستری‌اند و دلیلِ موتور روی کارت می‌ماند', () => {
    render(
      <FtsCard
        score={0}
        passes={{
          '1_growth': null,
          '1a_monetary_growth': false,
          '1b_volume_growth': false,
        }}
        physicalApplicable
        indicators={cardIndicators()}
        thresholds={{}}
      />,
    );
    expect(screen.getByTestId('fts-verdict-1a_monetary_growth').textContent).toBe('نظر نمی‌دهد');
    expect(screen.getByTestId('fts-verdict-1b_volume_growth').textContent).toBe('نظر نمی‌دهد');
    expect(screen.getByTestId('fts-verdict-1a_monetary_growth').className).not.toContain('text-accent-red');
    expect(screen.getByTestId('fts-cell-gap-1a_monetary_growth').textContent).toContain(GAP_REASON);
    expect(screen.getByTestId('fts-card-growth-basis').textContent).toContain('صورت مالی — ناموجود');
  });

  it('مبنایِ رشدِ صورتِ مالی میاندوره‌ای روی کارت دیده می‌شود', () => {
    const ind = cardIndicators({
      monetary: {
        monetary_pct: 50, data_gap: false, reason: '', basis: 'fs_interim',
        pass: true, period: '1405/06/31', months: 6,
      },
      volume: { applicable: false, pass: true, data_gap: false, basis: 'not_applicable' },
      pass: true,
      reason: '',
    });
    render(
      <FtsCard
        score={1}
        passes={{ '1_growth': true, '1a_monetary_growth': true, '1b_volume_growth': true }}
        physicalApplicable={false}
        indicators={ind}
        thresholds={{}}
      />,
    );
    expect(screen.getByTestId('fts-card-growth-basis').textContent).toContain('صورت مالی میاندوره‌ای');
  });
});

describe('دریل‌دانِ شاخص ۱ — همان دلیل و همان مبنا', () => {
  const card = {
    status: 'success',
    symbol: 'وبملت',
    passes: { '1_growth': null, '1a_monetary_growth': false, '1b_volume_growth': false },
    indicators: cardIndicators(),
  };

  it('GapHint دلیلِ شکافِ صورت مالی را نشان می‌دهد، نه متنِ عمومیِ ماهانه', () => {
    render(
      <FtsDrillDown card={card as never} active="1" quarters={[]} physicalApplicable />,
    );
    expect(screen.getByTestId('gap-hint').getAttribute('title')).toBe(GAP_REASON);
    expect(screen.getByTestId('drilldown-growth-basis').textContent).toContain('صورت مالی — ناموجود');
  });
});
