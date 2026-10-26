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

function cardIndicators(
  patch: Partial<NonNullable<FtsCardIndicators['1']>> = {},
  ind2: Partial<NonNullable<FtsCardIndicators['2']>> = {},
  ind3: Partial<NonNullable<FtsCardIndicators['3']>> = {},
): FtsCardIndicators {
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
    '2': { eps_series: [], na: true, pass: false, reason: '', ...ind2 },
    '3': { margin_pct: null, na: true, pass: false, reason: '', ...ind3 },
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

// ── Task 5 — برچسبِ شاهدِ EPS رویِ جدول/کارت/دریل‌دان ───────────────────────
describe('برچسبِ شاهدِ EPS — ردیفِ غربالگری', () => {
  it('سالانهٔ حسابرسی‌شده: برچسب زیرِ سلول و هر سه مقدار سرِ جایشان', () => {
    const r = row({ eps_evidence_label: 'سالانهٔ حسابرسی‌شده' });
    renderRows([r]);
    const label = screen.getByTestId('fts-eps-evidence-label');
    expect(label.textContent).toBe('سالانهٔ حسابرسی‌شده');
    const tr = screen.getByTestId('fts-screen-row');
    expect(tr.textContent).toContain('۱۰۰');
    expect(tr.textContent).toContain('۱۲۰');
    expect(tr.textContent).toContain('۱۵۰');
    // فایلِ دانلودی هم همان برچسب را در سلولِ ۲ می‌نویسد.
    expect(screenRowCells(r)[2]).toContain('سالانهٔ حسابرسی‌شده');
  });

  it('فقط تلفیقی: «N/A (تلفیقی)» + «تلفیقی — نمایشی» و سریِ نمایشی می‌ماند', () => {
    renderRows([row({
      i2_na: true,
      i2_pass: false,
      eps_consolidated: true,
      eps_data_gap: true,
      eps_evidence_label: 'تلفیقی — نمایشی',
      eps_series: [100, 120, 150],
    })]);
    expect(screen.getByTestId('fts-na-2_eps_trend').textContent).toContain('N/A (تلفیقی)');
    expect(screen.getByTestId('fts-eps-evidence-label').textContent).toBe('تلفیقی — نمایشی');
    const tr = screen.getByTestId('fts-screen-row');
    expect(tr.textContent).toContain('۱۵۰');
    expect(within(tr).queryByText('✗')).toBeNull();
  });

  it('کمتر از سه سال: «دادهٔ ناکافی» زیرِ همان سلول', () => {
    renderRows([row({
      eps_series: [null, 120, 150],
      eps_years_available: 2,
      eps_data_gap: true,
      i2_pass: false,
      eps_evidence_label: 'دادهٔ ناکافی',
    })]);
    expect(screen.getByTestId('fts-eps-evidence-label').textContent).toBe('دادهٔ ناکافی');
  });
});

describe('برچسبِ شاهدِ EPS — کارتِ شاخص ۲', () => {
  const renderCard = (ind2: Partial<NonNullable<FtsCardIndicators['2']>>, pass2: boolean | null) =>
    render(
      <FtsCard
        score={0}
        passes={{ '1_growth': true, '2_eps_trend': pass2 }}
        physicalApplicable
        indicators={cardIndicators({}, ind2)}
        thresholds={{}}
      />,
    );

  it('سالانهٔ حسابرسی‌شده زیرِ نتیجه می‌نشیند و سری/نمودارک می‌مانند', () => {
    renderCard({
      eps_series: [100, 120, 150], na: false, pass: true, strictly_rising: true,
      years_required: 3, years_available: 3,
      evidence_label: 'سالانهٔ حسابرسی‌شده',
    }, true);
    expect(screen.getByTestId('fts-result-2_eps_trend').textContent).toContain('۳ سالِ رشد');
    expect(screen.getByTestId('fts-card-eps-evidence-label').textContent)
      .toBe('سالانهٔ حسابرسی‌شده');
    expect(screen.getByTestId('fts-spark-eps')).toBeTruthy();
  });

  it('فقط تلفیقی: «N/A (تلفیقی)» + برچسب، بدونِ ✗ سرخ', () => {
    renderCard({
      eps_series: [100, 120, 150], na: true, pass: false,
      consolidated_used: true, years_required: 3, years_available: 3,
      evidence_label: 'تلفیقی — نمایشی',
      reason: 'صورت‌های مالی تلفیقی مدنظر نیست.',
    }, null);
    expect(screen.getByTestId('fts-result-2_eps_trend').textContent).toContain('N/A (تلفیقی)');
    expect(screen.getByTestId('fts-card-eps-evidence-label').textContent).toBe('تلفیقی — نمایشی');
    expect(screen.getByTestId('fts-verdict-2_eps_trend').textContent).not.toContain('✗');
  });
});

describe('برچسبِ شاهدِ EPS — دریل‌دانِ شاخص ۲', () => {
  it('برچسبِ موتور (نه نقشهٔ قدیمی) کنارِ N/A و سریِ نمایشی دیده می‌شود', () => {
    const ind = cardIndicators({}, {
      eps_series: [100, 120, 150], na: true, pass: false,
      consolidated_used: true, years_required: 3, years_available: 3,
      evidence_label: 'تلفیقی — نمایشی',
      reason: 'صورت‌های مالی تلفیقی مدنظر نیست.',
    });
    render(
      <FtsDrillDown
        card={{
          status: 'success',
          symbol: 'وبملت',
          passes: { '1_growth': null, '2_eps_trend': null },
          indicators: ind,
        } as never}
        active="2"
        quarters={[]}
        physicalApplicable
      />,
    );
    expect(screen.getByTestId('drilldown-eps-na').textContent).toContain('N/A');
    expect(screen.getByTestId('drilldown-evidence-tier').textContent).toContain('تلفیقی — نمایشی');
    expect(screen.getByTestId('drilldown-eps-chart')).toBeTruthy();
  });

  it('برچسبِ «برآورد میان‌دوره» هم از خودِ موتور خوانده می‌شود', () => {
    const ind = cardIndicators({}, {
      eps_series: [300, 500, 800], na: false, pass: true, strictly_rising: true,
      years_required: 3, years_available: 3,
      evidence_label: 'برآورد میان‌دوره',
    });
    render(
      <FtsDrillDown
        card={{
          status: 'success',
          symbol: 'وبملت',
          passes: { '1_growth': null, '2_eps_trend': true },
          indicators: ind,
        } as never}
        active="2"
        quarters={[]}
        physicalApplicable
      />,
    );
    expect(screen.getByTestId('drilldown-evidence-tier').textContent)
      .toContain('برآورد میان‌دوره');
  });
});

// ── Task 6 — طبقهٔ نمایشیِ حاشیه: below_floor/floor/standard/good ────────────
describe('طبقهٔ نمایشیِ حاشیه — ردیفِ غربالگری', () => {
  it('۵۸٪: «خوب» کنارِ درصد، حکمِ ✓ و همان برچسب در فایلِ دانلودی', () => {
    const r = row({ gross_margin: 58, margin_tier: 'good', i3_pass: true });
    renderRows([r]);
    const tier = screen.getByTestId('fts-margin-tier');
    expect(tier.textContent).toBe('خوب');
    expect(tier.className).not.toContain('text-accent-red');
    expect(tier.getAttribute('title')).toContain('۵۰٪ فقط برچسب');
    expect(screen.getByTestId('fts-mark-3_gross_margin').textContent).toContain('✓');
    expect(screenRowCells(r)[3]).toContain('۵۸');
    expect(screenRowCells(r)[3]).toContain('خوب');
  });

  it('۲۵٪: «کف» — بدونِ برچسبِ «خوب» و بدونِ تغییرِ حکم', () => {
    renderRows([row({ gross_margin: 25, margin_tier: 'floor', i3_pass: true })]);
    expect(screen.getByTestId('fts-margin-tier').textContent).toBe('کف');
    expect(screen.getByTestId('fts-mark-3_gross_margin').textContent).toContain('✓');
  });

  it('N/A: هیچ برچسبی ساخته نمی‌شود و همان N/A خاکستری می‌ماند', () => {
    renderRows([row({
      gross_margin: null, margin_tier: null, i3_pass: null, i3_na: true,
    })]);
    expect(screen.queryByTestId('fts-margin-tier')).toBeNull();
    expect(screen.getByTestId('fts-na-3_gross_margin').textContent).toContain('N/A');
  });
});

describe('طبقهٔ نمایشیِ حاشیه — کارتِ شاخص ۳', () => {
  const renderMarginCard = (ind3: Partial<NonNullable<FtsCardIndicators['3']>>) =>
    render(
      <FtsCard
        score={3}
        passes={{ '1_growth': true, '2_eps_trend': true, '3_gross_margin': true }}
        physicalApplicable
        indicators={cardIndicators({}, {}, ind3)}
        thresholds={{}}
      />,
    );

  it('۵۸٪: «خوب» کنارِ درصد و حکمِ ایده‌آل دست‌نخورده', () => {
    renderMarginCard({
      margin_pct: 58, margin_tier: 'good', pass: true, optimal: true,
      band: 'ideal', threshold: 20, ideal_threshold: 30, na: false,
    });
    expect(screen.getByTestId('fts-card-margin-tier').textContent).toBe('خوب');
    expect(screen.getByTestId('fts-result-3_gross_margin').textContent).toContain('۵۸');
    expect(screen.getByTestId('fts-verdict-3_gross_margin').textContent).toBe('ایده‌آل');
  });

  it('۴۹٫۹٪: «استاندارد» — ۵۰٪ دروازه نیست و حکم هنوز قبول/ایده‌آل است', () => {
    renderMarginCard({
      margin_pct: 49.9, margin_tier: 'standard', pass: true, optimal: true,
      band: 'ideal', threshold: 20, ideal_threshold: 30, na: false,
    });
    expect(screen.getByTestId('fts-card-margin-tier').textContent).toBe('استاندارد');
    expect(screen.getByTestId('fts-verdict-3_gross_margin').textContent).not.toBe('رد');
  });

  it('N/A: بی‌برچسب و برچسبِ حکم «نظر نمی‌دهد»', () => {
    renderMarginCard({ margin_pct: null, margin_tier: null, na: true, pass: false });
    expect(screen.queryByTestId('fts-card-margin-tier')).toBeNull();
    expect(screen.getByTestId('fts-cell-gap-3_gross_margin').textContent).toContain('N/A');
  });
});

describe('طبقهٔ نمایشیِ حاشیه — دریل‌دانِ شاخص ۳', () => {
  const renderPanel3 = (ind3: Partial<NonNullable<FtsCardIndicators['3']>>) =>
    render(
      <FtsDrillDown
        card={{
          status: 'success',
          symbol: 'وبملت',
          passes: { '3_gross_margin': true },
          indicators: cardIndicators({}, {}, ind3),
        } as never}
        active="3"
        quarters={[]}
        physicalApplicable
      />,
    );

  it('۵۸٪: «خوب» کنارِ بجِ درصد؛ برچسبِ باند «مطلوب» هم می‌ماند', () => {
    renderPanel3({
      margin_pct: 58, margin_tier: 'good', pass: true, optimal: true,
      band: 'ideal', threshold: 20, ideal_threshold: 30, na: false,
    });
    expect(screen.getByTestId('drilldown-margin-tier').textContent).toContain('خوب');
    expect(screen.getByTestId('drilldown-margin-tier').getAttribute('title'))
      .toContain('۵۰٪ فقط برچسب');
    expect(screen.getByTestId('drilldown-margin-band').textContent).toContain('مطلوب');
  });

  it('N/A: بی‌برچسب و بجِ همان N/A', () => {
    renderPanel3({ margin_pct: null, margin_tier: null, na: true, pass: false });
    expect(screen.queryByTestId('drilldown-margin-tier')).toBeNull();
    expect(screen.getByText('N/A')).toBeTruthy();
  });
});
