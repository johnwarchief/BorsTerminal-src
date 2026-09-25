// تست Drill-Down تعاملی ۵ شاخص + سالانه‌سازی N ماهه + P/NAV هلدینگ + N/A رشد فیزیکی
// شفاف‌سازی محاسبات موتور FTS v10 بک‌اند — این تست فقط رندر را می‌سنجد.
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FtsCard } from '@features/fundamental/components/FtsCard';
import { FtsDrillDown, type DrillDownKey } from '@features/fundamental/components/FtsDrillDown';
import { DataGapBanner } from '@features/fundamental/components/DataGapBanner';
import type { FtsCard as FtsCardType } from '@features/fundamental/api/useFtsCard';
import type { FiscalQuarter } from '@features/fundamental/lib/fundMath';

const FTS_PASSES: Record<string, boolean> = {
  '1_growth': true,
  '2_eps_trend': true,
  '3_gross_margin': true,
  '4_sales_to_mcap': true,
  '5_industry': true,
  '1a_monetary_growth': true,
  '1b_volume_growth': true,
  '4a_sales_to_mcap': true,
  '4b_profit_potential': false,
};

function baseCard(patch: Partial<FtsCardType> = {}): FtsCardType {
  return {
    status: 'success',
    symbol: 'شفا',
    sector: 'محصولات شيميايي',
    score: 4,
    verdict: 'STRONG',
    pricing_mode: 'free',
    passes: FTS_PASSES,
    indicators: {
      '1': {
        monetary: {
          monetary_pct: 130.7,
          ytd_now_bt: 1533.7,
          ytd_prev_bt: 664.7,
          ytd_now_mrl: 15337020,
          ytd_prev_mrl: 6647272,
          period: '05/1405',
          months: 5,
          year: 1405,
          threshold: 60,
          pass: true,
          data_gap: false,
          reason: '',
        },
        volume: {
          quantity_verified: false,
          basis: 'price_effect_decomposition',
          confidence: 'medium',
          volume_pct: null,
          real_pct: 46,
          implied_price_pct: 58,
          price_benchmark_pct: 58,
          applicable: true,
          pass: true,
          data_gap: false,
          reason: '',
          note: '',
        },
        pass: true,
      },
      '2': {
        eps_series: [91, 96, 202],
        net_profit_series: [1089822, 1147879, 2410320],
        fiscal_years: ['1402', '1403', '1404'],
        period_ends: ['1402/12/29', '1403/12/30', '1404/12/29'],
        period_slots: ['1402', '1403', '1404'],
        years_required: 3,
        years_available: 4,
        consecutive_years: true,
        strictly_rising: true,
        all_profitable: true,
        pass: true,
        partial: false,
        reason: '',
        evidence_tier: 'audited_year_end',
        interim: {
          available: true,
          period_end: '1405/03/31',
          period_months: 3,
          eps_interim: 51,
          eps_projected_year: 204,
          interim_yoy_pct: null,
          continues_trend: false,
          annualize_label: 'EPS میاندوره × ۱۲÷3',
        },
      },
      '3': {
        margin_pct: 21.2,
        gross_profit_bt: 420.6,
        revenue_bt: 1986.1,
        period_end: '1404/12/29',
        basis: 'سالانهٔ حسابرسی‌شدهٔ شرکت اصلی',
        formula: '(سود ناخالص ÷ درآمدهای عملیاتی) × ۱۰۰',
        pass: true,
        optimal: false,
        threshold: 20,
        optimal_threshold: 30,
        band: 'acceptable',
        na: false,
        reason: '',
      },
      '4': {
        available: true,
        mcap_ht: 2.72,
        annual_sales_bt: 3680.9,
        months_used: 5,
        scale_factor: 2.4,
        annualize_basis: 'تجمیعی 05/1405 × ۱۲÷5 (=×2.40)',
        sales_to_mcap: 1.35,
        sales_threshold: 0.33,
        sales_pass: true,
        margin_used_pct: 21.2,
        margin_basis: 'gross_margin',
        est_gross_profit_bt: 780.3,
        potential_pct: 28.7,
        potential_threshold: 33,
        potential_pass: false,
        pass: false,
        annual: {
          annual_sales_mrl: 36808848,
          annual_sales_bt: 3680.9,
          months_used: 5,
          scale_factor: 2.4,
          basis: 'تجمیعی 05/1405 × ۱۲÷5 (=×2.40)',
          ytd_sales_bt: 1533.7,
          scale_table: [
            { months: 3, factor: 4 },
            { months: 4, factor: 3 },
            { months: 5, factor: 2.4 },
            { months: 6, factor: 2 },
            { months: 9, factor: 1.33 },
            { months: 12, factor: 1 },
          ],
        },
      },
      '5': {
        verdict: 'free',
        label: 'قیمت‌گذاری آزاد / بورس کالا',
        sector: 'محصولات شيميايي',
        matched_tokens: ['شیمیایی'],
        fts_top_industry: true,
        pass: true,
        market_share_pct: 0.004,
        outlook: 'قیمت‌گذاری آزاد / بورس کالا / صادرات‌محور',
        regime_label: 'آزاد / بورس کالا',
      },
    },
    profile: {
      kind: 'production',
      label: 'تولیدی / صادراتی',
      revenue_basis: 'تولیدی/عمرانی',
      volume_applicable: true,
      volume_note: '',
      pricing_note: '',
    },
    metrics: {
      eps_series: [91, 96, 202],
      eps_slots: ['1402', '1403', '1404'],
      eps_available: 3,
      eps_required: 3,
      eps_partial: false,
      gross_margin: 21.2,
      net_margin: null,
      profit_potential_pct: 28.7,
      sales_to_mcap: 1.35,
      roe: 4.4,
      mcap_stale: false,
      mcap: 27233894574000,
      mcap_hmt: 2.72,
      annual_sales_bt: 3680.9,
      months_used: 5,
      scale_factor: 2.4,
      real_growth_pct: 46,
      monetary_growth_pct: 130.7,
      volume_growth_pct: null,
      growth_pct: 130.7,
      eps_projected_year: 204,
    },
    data_gaps: [],
    history: [],
    fs_count: 4,
    excluded: false,
    exclusion_reasons: [],
    ...patch,
  };
}

const FISCAL: FiscalQuarter[] = [
  { key: '1404-Q1', yearLabel: '1404', quarter: 1, revenue: 3848, operatingProfit: 350, netProfit: 252, margin: 6.5 },
  { key: '1404-Q2', yearLabel: '1404', quarter: 2, revenue: 4752, operatingProfit: 540, netProfit: 375, margin: 7.9 },
  { key: '1404-Q3', yearLabel: '1404', quarter: 3, revenue: 5658, operatingProfit: 470, netProfit: 310, margin: 5.5 },
  { key: '1404-Q4', yearLabel: '1404', quarter: 4, revenue: 5601, operatingProfit: 1039, netProfit: 822, margin: 14.7 },
  { key: '1405-Q1', yearLabel: '1405', quarter: 1, revenue: 9956, operatingProfit: 856, netProfit: 604, margin: 6.1 },
];

describe('Drill-Down تعاملی ۵ شاخص FTS', () => {
  it('کلیک روی هر سلول کارت FTS پنل همان شاخص را باز می‌کند', () => {
    const opened: DrillDownKey[] = [];
    render(
      <FtsCard score={4} passes={FTS_PASSES} verdict="STRONG" activeDrill={null} onDrill={(k) => opened.push(k)} />,
    );
    fireEvent.click(screen.getByTestId('fts-card-cell-1a_monetary_growth'));
    fireEvent.click(screen.getByTestId('fts-card-cell-2_eps_trend'));
    fireEvent.click(screen.getByTestId('fts-card-cell-3_gross_margin'));
    fireEvent.click(screen.getByTestId('fts-card-cell-4_sales_to_mcap'));
    fireEvent.click(screen.getByTestId('fts-card-cell-5_industry'));
    expect(opened).toEqual(['1', '2', '3', '4', '5']);
  });

  it('سلول فعال هایلایت می‌شود (aria-pressed)', () => {
    render(
      <FtsCard
        score={4}
        passes={FTS_PASSES}
        verdict="STRONG"
        activeDrill="4"
        onDrill={() => {}}
      />,
    );
    expect(screen.getByTestId('fts-card-cell-4_sales_to_mcap').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('fts-card-cell-3_gross_margin').getAttribute('aria-pressed')).toBe('false');
  });
});

describe('پنل شاخص ۱ — رشد فروش و درآمد', () => {
  it('درآمد دوره امسال/سال قبل + درصد رشد + مبنای تورم رندر می‌شود', () => {
    render(<FtsDrillDown card={baseCard()} active="1" quarters={FISCAL} physicalApplicable />);
    const panel = screen.getByTestId('fts-drilldown-1');
    expect(within(panel).getAllByText(/۱۳۰٫۷٪|130.7%|۱۳۰\.۷٪/).length).toBeGreaterThan(0);
    expect(within(panel).getByTestId('inflation-control')).toBeInTheDocument();
    expect(within(panel).getByText('دوره جاری (امسال)')).toBeInTheDocument();
    expect(within(panel).getByText('دوره مشابه سال قبل')).toBeInTheDocument();
  });

  it('شرکت خدماتی/هلدینگ: کادر رشد فیزیکی کاملاً حذف می‌شود (نه کادر خالی/نه N/A)', () => {
    render(<FtsDrillDown card={baseCard()} active="1" quarters={FISCAL} physicalApplicable={false} />);
    const panel = screen.getByTestId('fts-drilldown-1');
    // نه برچسب N/A، نه متن توضیح — کادر تناژ اصلاً رندر نمی‌شود
    expect(within(panel).queryByText('N/A — غیرقابل اعمال')).toBeNull();
    expect(within(panel).queryByText(/تناژ فیزیکی/)).toBeNull();
    expect(within(panel).queryByText(/این شرکت تولیدی نیست/)).toBeNull();
    // داده‌های دیگر شاخص ۱ سرجایشان هستند
    expect(within(panel).getByText('دوره جاری (امسال)')).toBeInTheDocument();
    expect(within(panel).getByText('دوره مشابه سال قبل')).toBeInTheDocument();
  });

  it('تولیدی: رشد واقعی پس از کسر اثر نرخ نمایش می‌شود', () => {
    render(<FtsDrillDown card={baseCard()} active="1" quarters={FISCAL} physicalApplicable />);
    const panel = screen.getByTestId('fts-drilldown-1');
    expect(within(panel).getByText(/رشد واقعی پس از کسر اثر نرخ/)).toBeTruthy();
  });

  it('تغییر مبنای تورم به صورت پویا اثر و رشد واقعی را تغییر می‌دهد', () => {
    render(<FtsDrillDown card={baseCard()} active="1" quarters={FISCAL} physicalApplicable />);
    const panel = screen.getByTestId('fts-drilldown-1');
    const btn40 = within(panel).getByText('۴۰٪');
    fireEvent.click(btn40);
    expect(within(panel).getByText(/با مبنای تورم ۴۰٪/)).toBeInTheDocument();
  });
});

describe('پنل شاخص ۲ — نردبان EPS سه ساله', () => {
  it('نمودار پله‌ای EPS سه سال حسابرسی‌شده رندر می‌شود', () => {
    render(<FtsDrillDown card={baseCard()} active="2" quarters={FISCAL} physicalApplicable />);
    const chart = screen.getByTestId('drilldown-eps-chart');
    expect(chart.textContent).toContain('۹۱');
    expect(chart.textContent).toContain('۹۶');
    expect(chart.textContent).toContain('۲۰۲');
    expect(chart.textContent).toContain('۱۴۰۲');
    expect(chart.textContent).toContain('۱۴۰۴');
  });

  it('برچسب صعودی/غیرصعودی و شاهد حسابرسی‌شده نمایش می‌یابد', () => {
    render(<FtsDrillDown card={baseCard()} active="2" quarters={FISCAL} physicalApplicable />);
    expect(screen.getByText('صعودی ✓')).toBeInTheDocument();
    expect(screen.getByText('audited_year_end')).toBeInTheDocument();
  });

  it('سابقهٔ ناقص ۲ ساله: همان دو سال رندر + برچسب «مردود در شاخص ۲ — سابقهٔ ناقص»', () => {
    const card = baseCard();
    card.indicators!['2'] = {
      ...card.indicators!['2']!,
      eps_series: [100, 150, null],
      fiscal_years: ['1403', '1404', '1405'],
      period_slots: ['1403', '1404', '1405'],
      partial: true,
      strictly_rising: null,
    };
    render(<FtsDrillDown card={card} active="2" quarters={FISCAL} physicalApplicable />);
    // نمودار همان سال‌های موجود را نشان می‌دهد — داده حیف نمی‌شود
    const chart = screen.getByTestId('drilldown-eps-chart');
    expect(chart.textContent).toContain('۱۰۰');
    expect(chart.textContent).toContain('۱۵۰');
    expect(chart.textContent).toContain('۱۴۰۳');
    expect(chart.textContent).toContain('۱۴۰۴');
    // برچسب صریح مردودی
    const label = screen.getByTestId('eps-partial-rejected');
    expect(label.textContent).toContain('مردود در شاخص ۲');
    expect(label.textContent).toContain('۲ از ۳ سال');
  });

  it('سابقهٔ ناقص ۱ ساله: برچسب علت‌دار می‌گیرد — برچسب سابقهٔ ناقص نمی‌آید', () => {
    const card = baseCard();
    card.indicators!['2'] = {
      ...card.indicators!['2']!,
      eps_series: [150, null, null],
      partial: true,
      strictly_rising: null,
    };
    render(<FtsDrillDown card={card} active="2" quarters={FISCAL} physicalApplicable />);
    expect(screen.queryByTestId('eps-partial-rejected')).not.toBeInTheDocument();
    // برچسب علت‌دار + tooltip علت و راه‌حل — ۱ سالِ موجود صادقانه ذکر می‌شود
    expect(screen.getAllByText('سابقهٔ EPS کمتر از ۲ سال').length).toBeGreaterThanOrEqual(1);
    const hint = screen.getAllByTestId('gap-hint')[0];
    expect(hint.getAttribute('title')).toContain('فقط ۱ سال از ۳ سال');
  });
});

describe('پنل شاخص ۳ — حاشیه سود ناخالص', () => {
  it('فرمول شفاف + سه آستانه (مردود/مشروط/مطلوب) رندر می‌شود', () => {
    render(<FtsDrillDown card={baseCard()} active="3" quarters={FISCAL} physicalApplicable />);
    expect(screen.getByText(/زیر ۲۰٪ ← مردود/)).toBeInTheDocument();
    expect(screen.getByText(/۲۰–۳۰٪ ← مشروط/)).toBeInTheDocument();
    expect(screen.getByText(/بالای ۳۰٪ ← مطلوب/)).toBeInTheDocument();
    expect(screen.getByText(/حاشیه = \(سود ناخالص ÷ درآمدهای عملیاتی\) × ۱۰۰/)).toBeInTheDocument();
  });

  it('حاشیه ۲۱.۲٪ در باند «مشروط» برجسته می‌شود', () => {
    render(<FtsDrillDown card={baseCard()} active="3" quarters={FISCAL} physicalApplicable />);
    expect(screen.getByText(/۲۱\.۲٪ · مشروط/)).toBeInTheDocument();
  });

  it('روند خطی ۶ فصل حاشیه رندر می‌شود', () => {
    render(<FtsDrillDown card={baseCard()} active="3" quarters={FISCAL} physicalApplicable />);
    expect(screen.getByTestId('drilldown-margin-chart')).toBeInTheDocument();
  });
});

describe('پنل شاخص ۴ — سالانه‌سازی داینامیک N ماهه', () => {
  it('فرمول Annualized Sales = (Cumulative Sales / N) × 12 با N=5 رندر می‌شود', () => {
    render(<FtsDrillDown card={baseCard()} active="4" quarters={FISCAL} physicalApplicable />);
    const formula = screen.getByTestId('annualize-formula');
    expect(formula.textContent).toBe('Annualized Sales = (Cumulative Sales / 5) × 12');
  });

  it('N=12 سال کامل: فرمول ضریب ۱ دارد (رفع باگ تقسیم بر ۱۲×۰م)', () => {
    const card = baseCard();
    card.indicators!['4'] = { ...card.indicators!['4']!, months_used: 12, scale_factor: 1 };
    render(<FtsDrillDown card={card} active="4" quarters={FISCAL} physicalApplicable />);
    expect(screen.getByTestId('annualize-formula').textContent).toBe('Annualized Sales = (Cumulative Sales / 12) × 12');
  });

  it('برچسب مبنا: «سالانه‌شده از دورهٔ ۵ ماهه» + متن خام مبنا', () => {
    render(<FtsDrillDown card={baseCard()} active="4" quarters={FISCAL} physicalApplicable />);
    const basis = screen.getByTestId('annualize-basis').textContent || '';
    expect(basis).toContain('سالانه‌شده از دورهٔ ۵ ماهه');
    expect(basis).toContain('× ۱۲÷۵');
  });

  it('مبنای ۱۲ ماهه می‌گوید سال کامل است، نه سالانه‌شده', () => {
    const card = baseCard();
    card.indicators!['4'] = { ...card.indicators!['4']!, months_used: 12, scale_factor: 1 };
    render(<FtsDrillDown card={card} active="4" quarters={FISCAL} physicalApplicable />);
    expect(screen.getByTestId('annualize-basis').textContent).toContain('۱۲ ماه کاملِ سال مالی');
  });

  it('ناهمخوانی با فروش سالانهِ کدال صریحاً هشدار می‌دهد (reconciled=false)', () => {
    const card = baseCard();
    card.indicators!['4'] = {
      ...card.indicators!['4']!,
      annual: { ...card.indicators!['4']!.annual!, reconciled: false },
    };
    render(<FtsDrillDown card={card} active="4" quarters={FISCAL} physicalApplicable />);
    expect(screen.getByTestId('annualize-unreconciled')).toBeInTheDocument();
  });


  it('نسبت فروش/ارزش بازار با کف و پتانسیل سود هم‌زمان نمایش می‌یابد', () => {
    render(<FtsDrillDown card={baseCard()} active="4" quarters={FISCAL} physicalApplicable />);
    expect(document.body.textContent).toMatch(/فروش\/ارزش بازار ۱\.۳۵×/);
    expect(document.body.textContent).toMatch(/پتانسیل سود ۲۸\.۷٪/);
  });

  it('جدول ضرایب پویا نشان می‌دهد ضریب ثابت ۴ نیست (۳ماهه×4، ۵ماهه×2.4)', () => {
    render(<FtsDrillDown card={baseCard()} active="4" quarters={FISCAL} physicalApplicable />);
    expect(screen.getByText('۵ ماه ×۲٫۴')).toBeInTheDocument();
    expect(screen.getByText('۱۲ ماه ×۱')).toBeInTheDocument();
  });

  it('بلوک فرمول A×B÷D با اعداد واقعی رندر می‌شود (۳۶۸۱ × ۲۱.۲٪ ÷ ۲.۷۲ همت)', () => {
    render(<FtsDrillDown card={baseCard()} active="4" quarters={FISCAL} physicalApplicable />);
    const block = screen.getByTestId('potential-formula');
    expect(within(block).getByText(/فروش سالانه‌شده/).textContent).toContain('۳٬۶۸۱');
    expect(within(block).getByText(/حاشیه ناخالص/).textContent).toContain('۲۱.۲٪');
    expect(within(block).getByText(/مارکت‌کپ/).textContent).toContain('۲.۷۲');
    expect(block.textContent).toContain('۲۸.۷٪');
  });

  it('متغیر غایب فقط در جای خود علت‌دار می‌شود — بقیهٔ فرمول سالم می‌ماند', () => {
    const card = baseCard();
    const ind4 = card.indicators!['4']!;
    card.indicators!['4'] = { ...ind4, margin_used_pct: null, potential_pct: null };
    card.metrics = { ...card.metrics!, gross_margin: null, profit_potential_pct: null };
    render(<FtsDrillDown card={card} active="4" quarters={FISCAL} physicalApplicable />);
    const block = screen.getByTestId('potential-formula');
    // جای برچسب عمومی «بدون داده» / «شکاف داده»، علتِ همان متغیر می‌آید
    expect(within(block).getByText('حاشیهٔ ناخالص ثبت نشده')).toBeInTheDocument();
    expect(within(block).getByText('خروجی قابل محاسبه نیست')).toBeInTheDocument();
    expect(within(block).queryByText('بدون داده')).not.toBeInTheDocument();
    expect(within(block).getByText(/فروش سالانه‌شده/).textContent).toContain('۳٬۶۸۱');
    expect(within(block).getByText(/مارکت‌کپ/).textContent).toContain('۲.۷۲');
  });
});

describe('پنل شاخص ۵ — چشم‌انداز صنعت و نرخ‌گذاری', () => {
  it('ماتریس نوع قیمت‌گذاری/انرژی/ارزی رندر می‌شود', () => {
    render(<FtsDrillDown card={baseCard()} active="5" quarters={FISCAL} physicalApplicable />);
    expect(screen.getByText('نوع قیمت‌گذاری')).toBeInTheDocument();
    expect(screen.getByText('ریسک ناترازی انرژی')).toBeInTheDocument();
    expect(screen.getByText('پتانسیل ارزی')).toBeInTheDocument();
    expect(screen.getByText(/آزاد \/ بورس کالا — نرخ از بازار/)).toBeInTheDocument();
  });

  it('صنعت صادراتی: پتانسیل ارزی مثبت', () => {
    render(<FtsDrillDown card={baseCard()} active="5" quarters={FISCAL} physicalApplicable />);
    expect(screen.getByText(/صادراتی\/دلاری/)).toBeInTheDocument();
  });
});

describe('N/A رشد فیزیکی در کارت FTS', () => {
  it('کارت شرکت خدماتی: سلول ۱ب برچسب N/A می‌گیرد نه مردود', () => {
    render(<FtsCard score={3} passes={{ ...FTS_PASSES, '1b_volume_growth': false }} verdict="WATCH" physicalApplicable={false} />);
    const cell = screen.getByTestId('fts-card-cell-1b_volume_growth');
    expect(within(cell).getByText('N/A')).toBeInTheDocument();
  });

  it('کارت تولیدی: همان مقدار قبول/مردود می‌ماند', () => {
    render(<FtsCard score={4} passes={FTS_PASSES} verdict="STRONG" physicalApplicable />);
    const cell = screen.getByTestId('fts-card-cell-1b_volume_growth');
    expect(within(cell).getByText('قبول')).toBeInTheDocument();
  });
});

describe('DataGapBanner — پاک‌سازی متون خام موتور', () => {
  it('متن خام fts_engine در بنر نمی‌آید و پیام استاندارد جایگزین می‌شود', () => {
    render(
      <DataGapBanner
        gaps={[
          {
            layer: '۴',
            axis: '4_sales_to_mcap',
            why: 'سالانه‌سازی ×۱۲÷م با گیتِ fts_engine سازگار نشد؛ فروش سالانهٔ کدال جانشین شد.',
            fix: 'گزارش‌های ماهانهٔ کاملِ همان سال مالی لازم است.',
          },
          {
            layer: '۲',
            axis: '2_eps_trend',
            why: 'سابقه با میاندورهٔ کوتاهِ سالِ جاری تکمیل شده — نتیجه قابل استناد قطعی نیست',
            fix: 'با انتشار صورت ۱۲ماههٔ سال مالی جاری، داوری قطعی میشود.',
          },
        ]}
      />,
    );
    const banner = screen.getByTestId('data-gap-banner');
    // متن خام موتور (fts_engine، ×۱۲÷م، گیت) هرگز نمایش نمی‌یابد
    expect(banner.textContent).not.toContain('fts_engine');
    expect(banner.textContent).not.toContain('گیتِ');
    expect(banner.textContent).not.toContain('×۱۲÷م');
    expect(banner.textContent).toContain('شاخص ۴');
    expect(banner.textContent).toContain('گزارش‌های ماهانهٔ کدال برای سالانه‌سازی فروش کافی نیست');
    expect(banner.textContent).toContain('شاخص ۲');
    expect(banner.textContent).toContain('سابقهٔ EPS این نماد برای قضاوت سه‌ساله کامل نیست');
  });

  it('بدون شکاف، بنر رندر نمی‌شود', () => {
    render(<DataGapBanner gaps={[]} />);
    expect(screen.queryByTestId('data-gap-banner')).not.toBeInTheDocument();
  });

  it('hover روی آیتم بنر شکاف: علت و راه‌حل در title ظاهر می‌شود', () => {
    render(
      <DataGapBanner
        gaps={[
          {
            layer: '۲',
            axis: '2_eps_trend',
            why: 'سابقه با میاندورهٔ کوتاهِ سالِ جاری تکمیل شده — نتیجه قابل استناد قطعی نیست',
            fix: 'با انتشار صورت ۱۲ماههٔ سال مالی جاری، داوری قطعی میشود.',
          },
        ]}
      />,
    );
    const item = screen.getByTestId('data-gap-item');
    const title = item.getAttribute('title') ?? '';
    expect(title).toContain('سابقهٔ EPS این نماد برای قضاوت سه‌ساله کامل نیست');
    expect(title).toContain('راه‌حل');
    expect(title).toContain('همگام‌سازی کدال');
    // متن خام موتور در tooltip هم نمی‌آید
    expect(title).not.toContain('fts_engine');
  });
});
