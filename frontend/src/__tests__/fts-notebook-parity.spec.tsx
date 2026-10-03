/** انطباقِ پنج شاخص با خودِ جزوۀ FTS (دورِ H) — هر ادّعا باید به صفحۀ جزوه
 *  برگردد، نه به کانفیگ:
 *   ص ۳  ۱الف = درصدِ رشد فروش نسبت به دورۀ مشابه؛ «۴۰٪ کفِ قبولی، ۶۰٪ هدف»
 *   ص ۴  ۲ = EPS سه سالِ متوالی صعودی؛ «صورتهایِ مالیِ تلفیقی مدنظر ما نیست»
 *   ص ۴  ۳ = حاشیۀ سود **ناخالص** = سود ناخالص ÷ درآمدهای عملیاتی × ۱۰۰
 *   ص ۵   = فروشِ سالانه  ارزش بازار و پتانسیلِ سود تا آخرِ سال
 *   ص ۶  ۵ = نوع نرخ‌گذاری/دلاری-ریالی/چشم‌انداز؛ ✗ فقط خودرو، نیروگاهی، لاستیک
 *  و قاعدۀ عرضی: N/A ≠ رد (رأیِ ۱۳ و ۱۶).
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

// jsdom اندازه ندارد؛ بدونِ این شبیه‌سازی هیچ ردیفِ جدول غربالگری رندر نمی‌شود
// (الگوی fts-screen.spec.tsx)
vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  return {
    ...mod,
    useVirtualizer: (opts: { count: number }) => ({
      getTotalSize: () => opts.count * 46,
      getVirtualItems: () =>
        Array.from({ length: Math.min(opts.count, 12) }, (_, i) => ({ key: i, index: i, start: i * 46 })),
    }),
  };
});

import { FtsCard } from '@features/fundamental/components/FtsCard';
import { FtsDrillDown } from '@features/fundamental/components/FtsDrillDown';
import { FtsScreenTable } from '@features/fundamental/ui/FtsScreenTable';
import { rejectedFor } from '@features/fundamental/lib/exclusionFilter';
import type { FtsCard as FtsCardType } from '@features/fundamental/api/useFtsCard';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';

const PASSES: Record<string, boolean> = {
  '1_growth': true, '2_eps_trend': true, '3_gross_margin': true,
  '4_sales_to_mcap': true, '5_industry': true,
  '1a_monetary_growth': true, '1b_volume_growth': true,
  '4a_sales_to_mcap': true, '4b_profit_potential': true,
};

function card(over: Partial<FtsCardType> = {}): FtsCardType {
  return {
    status: 'success', symbol: 'تست', sector: 'سیمان', score: 4, verdict: 'STRONG',
    applicable: true, pricing_mode: 'free', passes: PASSES,
    indicators: {
      '1': {
        monetary: {
          monetary_pct: 45.0, ytd_now_bt: 900, ytd_prev_bt: 620, period: '06/1405',
          months: 6, year: 1405, threshold: 40, target_threshold: 60, strong: false,
          pass: true, data_gap: false, reason: '',
        },
        volume: {
          quantity_verified: false, basis: 'price_effect_decomposition',
          confidence: 'medium', volume_pct: null, real_pct: 45, implied_price_pct: 0,
          price_benchmark_pct: 60, applicable: true, pass: true, data_gap: false,
          reason: '', note: '', breadth: { improved_months: 5, compared_months: 6, ratio: 0.83, min: 0.6 },
        },
        pass: true,
      },
      '2': {
        eps_series: [777, 1008, 145], period_slots: ['1402', '1403', '1404'],
        fiscal_years: ['1402', '1403', '1404'], years_required: 3, years_available: 3,
        strictly_rising: false, all_profitable: true, pass: true, partial: false,
        data_gap: false, evidence: ['audited_year_end', 'audited_year_end', 'audited_year_end'],
        evidence_tier: 'audited_year_end', strict_evidence: true, consolidated_used: false,
        eps_basis: 'سال‌پایانِ حسابرسی‌شدهٔ غیرتلفیقی', reason: '',
      },
      '3': {
        margin_pct: 58.0, gross_profit_bt: 212, revenue_bt: 321, period_end: '1404-12-29',
        basis: 'سالانهٔ حسابرسی‌شدهٔ شرکت اصلی', formula: 'GP ÷ Rev × ۱۰', pass: true,
        ideal: true, threshold: 20, ideal_threshold: 30, band: 'ideal', na: false, reason: '',
      },
      '4': {
        available: true, mcap_ht: 1200, annual_sales_bt: 900, months_used: 6,
        scale_factor: 2, annualize_basis: 'YTD × ۱۲÷۶', sales_to_mcap: 0.75,
        sales_threshold: 0.33, sales_pass: true, margin_used_pct: 58,
        margin_basis: 'gross_margin', est_gross_profit_bt: 522, potential_pct: 43.5,
        potential_threshold: 40, potential_pass: true, pass: true, na: false,
        exempt: false, reason: '',
      },
      '5': {
        verdict: 'free', label: 'قیمت‌گذاری آزاد / بورس کالا', sector: 'سیمان',
        matched_tokens: ['سیمان'], fts_top_industry: true, pass: true,
        exclusion_active: true, market_share_pct: 2.5, outlook: 'ساخت‌وساز',
        regime_label: 'آزاد / بورس کالا',
      },
    },
    thresholds: { growth_min: 40, v10_monetary_growth_min: 60, margin_min: 20, margin_ideal: 30 },
    metrics: {},
    ...over,
  } as unknown as FtsCardType;
}

function renderCard(c: FtsCardType, over: Record<string, unknown> = {}) {
  return render(
    <FtsCard
      score={c.score ?? null}
      passes={c.passes as Record<string, boolean>}
      indicators={c.indicators}
      thresholds={c.thresholds as Record<string, unknown>}
      physicalApplicable
      industryMode={c.pricing_mode ?? null}
      onDrill={vi.fn()}
      {...over}
    />,
  );
}

describe('شاخص ۱ — کفِ قبولی با هدفِ پوشش تورم قاطی نمی‌شود (ص ۳)', () => {
  it('رشد ۴۵٪ با کفِ ۴۰ قبول است و هدفِ ۶۰ جدا نشان داده می‌شود', () => {
    renderCard(card());
    const scale = screen.getByTestId('fts-growth-scale');
    const titles = Array.from(scale.querySelectorAll('[title]')).map((e) => e.getAttribute('title') ?? '');
    expect(titles.some((t) => t.startsWith('کفِ قبولی') && t.includes('۴۰'))).toBe(true);
    expect(titles.some((t) => t.startsWith('هدفِ پوشش تورم') && t.includes('۶۰'))).toBe(true);
    expect(screen.getByTestId('fts-verdict-1a_monetary_growth').textContent).toBeTruthy();
  });

  it('«پهنا» هیچ‌جا به‌عنوان شرطِ ≥ رندر نمی‌شود (دادهٔ نمایشی است، نه قانونِ جزوه)', () => {
    const { container } = renderCard(card());
    expect(container.textContent).not.toMatch(/پهنا\s*≥/);
    expect(container.textContent).toContain('از');  // «۵ از ۶ ماه بهتر» — فقط گزارش
  });

  it('محورِ «ب» قابل‌اعمال نیست ⇒ رأیِ لایه ۱ از موتور می‌آید، نه از وتوی «ب»', () => {
    const c = card();
    renderCard(c, {
      physicalApplicable: false,
      passes: { ...PASSES, '1b_volume_growth': false, '1_growth': true },
    });
    expect(screen.getByText(/محصول فیزیکی ندارد/)).toBeInTheDocument();
    // کارتِ ۱ باید «قبول» باشد: N/Aِ محورِ ب حقِ وتو ندارد (`axis1_pass` در بک‌اند)
    expect(screen.getByTestId('fts-card-cell-1_growth').className).toContain('emerald');
  });
});

describe('شاخص ۲ — مبنایِ غیرتلفیقی (ص ۴)', () => {

  it('سابقۀ مستقلِ صعودی: حکمِ موتور ✓ و مدرکِ غیرتلفیقی', () => {
    const c = card();
    renderCard(c);
    expect(screen.getByTestId('fts-card-cell-2_eps_trend').textContent).toContain('سال');
  });

  it('سابقه‌ای که یک اسلاتش تلفیقی است: N/A — نه ✓ و نه ✗', () => {
    const c = card();
    const i2 = {
      ...(c.indicators?.['2'] ?? {}),
      pass: false, data_gap: true, na: true, consolidated_used: true,
      consolidated_years: ['1402'], evidence_tier: 'consolidated_year_end',
      strict_evidence: false,
      reason: 'صورتهای مالی تلفیقی مدنظر نیست — سال‌های 1402 فقط تلفیقی منتشر شده‌اند',
    };
    render(
      <FtsDrillDown
        card={{ ...c, passes: { ...PASSES, '2_eps_trend': false },
                indicators: { ...c.indicators!, '2': i2 } } as FtsCardType}
        active="2"
        quarters={[]}
        physicalApplicable
      />,
    );
    expect(screen.getByTestId('drilldown-eps-na').textContent).toContain('N/A');
    expect(screen.getByTestId('drilldown-eps-na').textContent).toContain('تلفیقی');
    expect(screen.queryByText(/سه سالِ متوالی بالاتر ✓/)).toBeNull();
  });

  it('در جدول غربالگری هم همان ردیف N/A است، نه ✗', () => {
    const r = {
      symbol: 'خاور', symbol_norm: 'خاور', name: 'خاور', sector_name: 'سیمان',
      pricing_mode: 'free', rev_growth: 45, eps_series: [400, 500, 600], eps_last: 600,
      eps_data_gap: true, eps_consolidated: true, i2_na: true, i2_pass: null,
      gross_margin: 30, sales_to_mcap: 1, profit_potential_pct: 45, mcap: 1e13, score: 3,
      i1_pass: true, i3_pass: true, i4_pass: true, i5_pass: true, excluded: false,
    } as unknown as FtsScreenRow;
    render(<FtsScreenTable rows={[r]} onSelect={() => {}} />);
    expect(screen.getByTestId('fts-na-2_eps_trend').textContent).toContain('N/A (تلفیقی)');
    expect(rejectedFor(r as unknown as FtsScreenRow, '2')).toBeNull();
  });
});

describe('شاخص ۳ — واژگان: ناخالص، نه خالص (ص ۴)', () => {
  it('کارت و دریل‌دان «ناخالص» می‌گویند و «حاشیهٔ سود خالص» ندارند', () => {
    const { container } = renderCard(card());
    expect(container.textContent).toContain('ناخالص');
    expect(container.textContent).not.toContain('حاشیهٔ سود خالص');
    expect(container.textContent).not.toContain('حاشیه سود خالص');
  });
});

describe('شاخص ۴ — پتانسیل سود + شاهدِ فروش/ارزش (ص ۵)', () => {
  it('هر دو عدد در کارت می‌آیند: پتانسیل ٪ و نسبت فروش به ارزش بازار', () => {
    const { container } = renderCard(card());
    expect(container.textContent).toContain('پتانسیل');
    const i4 = card().indicators?.['4'];
    expect(i4?.potential_pct).toBeCloseTo(43.5, 1);
    expect(i4?.sales_to_mcap).toBeCloseTo(0.75, 2);
  });

  it('ارزش بازارِ غایب ⇒ N/A با علت، نه صفرِ مردود', () => {
    const c = card();
    const i4 = { ...(c.indicators?.['4'] ?? {}),
                  potential_pct: null, available: false, mcap_ht: null, na: true };
    render(
      <FtsDrillDown
        card={{ ...c, passes: { ...PASSES, '4_sales_to_mcap': false },
                indicators: { ...c.indicators!, '4': i4 } } as FtsCardType}
        active="4" quarters={[]} physicalApplicable
      />,
    );
    const panel = screen.getByTestId('drilldown-panel-4');
    // ارزشِ بازارِ غایب «صفرِ مردود» نمی‌شود: علت در جای خودش می‌آید و فرمول
    // تا همان متغیر سالم نمایش داده می‌شود.
    expect(panel.textContent).toContain('ارزش بازار در دسترس نیست');
    expect(panel.textContent).toContain('خروجی قابل محاسبه نیست');
    expect(panel.textContent).toContain('حاشیه ناخالص');
  });
});

describe('شاخص ۵ — حکمِ موتور، نه فهرستِ دست‌سازِ رابط (ص ۶)', () => {
  it('رابط «همهٔ دارویی/غذایی مردود» نمی‌گوید', () => {
    render(<FtsDrillDown card={card()} active="5" quarters={[]} physicalApplicable />);
    expect(screen.getByText(/جزوه \(ص ۶\)/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/دارو[^ی]*،[^·]*مردود/);
  });

  it('حکمِ «دستوری» از verdictِ بک‌اند می‌آید (Rank_Only هم اعلام می‌شود)', () => {
    const c = card();
    const i5 = { ...(c.indicators?.['5'] ?? {}),
                  verdict: 'mandatory', regime_label: 'دستوری', exclusion_active: false };
    render(
      <FtsDrillDown card={{ ...c, pricing_mode: 'mandatory',
                            indicators: { ...c.indicators!, '5': i5 } } as FtsCardType}
        active="5" quarters={[]} physicalApplicable />,
    );
    expect(document.body.textContent).toContain('در حالتِ «فقط رتبه‌بندی»');
  });
});
