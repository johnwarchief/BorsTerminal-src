// #102 (رأیِ جزوه): «روند فصلی درآمد باید با سود ناخالص مقایسه بشه نه سود خالص».
// سه لایهٔ همین زنجیره پوشش داده می‌شود:
//   ۱) قرارداد API (useQuarters) — سود ناخالص نباید توسط zod دور ریخته شود؛
//      نبودش NULL است نه صفر.
//   ۲) لایهٔ محاسبه (fundMath) — حاشیه/روند از سود ناخالص؛ NULL ⇒ N/A.
//   ۳) نمایش (QuarterlyTrend / FtsDrillDown شاخص ۳) — هیچ‌جا سود خالص زیرِ
//      برچسب «سود ناخالص» رندر نمی‌شود و نبودِ داده میلهٔ صفر نمی‌سازد.
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { QuarterlyTrend } from '@features/fundamental/components/QuarterlyTrend';
import { FtsDrillDown } from '@features/fundamental/components/FtsDrillDown';
import { QuarterRowSchema, type QuarterRow } from '@features/fundamental/api/useQuarters';
import { deCumulateQuarters, profitYoY, type FiscalQuarter } from '@features/fundamental/lib/fundMath';
import type { FtsCard } from '@features/fundamental/api/useFtsCard';

/** پاسخ واقعیِ /api/fundamental/{sym}/quarters (تجمعیِ سال مالی) */
function apiRow(patch: Record<string, unknown> = {}): QuarterRow {
  return QuarterRowSchema.parse({
    period_end: '1404/06/31',
    period_months: 6,
    revenue: 250,
    gross_profit: 100,
    operating_profit: null,
    net_profit: 30,
    basic_eps: null,
    publish_date: '1404/07/05',
    ...patch,
  });
}

describe('#102 قراردادِ سری فصلی', () => {
  it('gross_profit از پاسخِ بک‌اند زنده می‌ماند (zod کلیدِ ناشناس را دور نمی‌ریزد)', () => {
    expect(apiRow().gross_profit).toBe(100);
  });

  it('NULL یعنی NULL — نه صفر و نه حذفِ کلید', () => {
    const row = apiRow({ gross_profit: null });
    expect(row.gross_profit).toBeNull();
    expect('gross_profit' in row).toBe(true);
  });
});

describe('#102 نمودار روند فصلی — مقایسه با سود ناخالص', () => {
  const rows = [
    apiRow({ period_end: '1404/03/31', period_months: 3, revenue: 100, gross_profit: 40, net_profit: 10 }),
    apiRow({ period_end: '1404/06/31', period_months: 6, revenue: 250, gross_profit: 100, net_profit: 30 }),
  ];
  const fiscal = deCumulateQuarters(rows);

  it('سربرگ و راهنما «سود ناخالص» می‌گویند، نه سود خالص', () => {
    render(<QuarterlyTrend quarters={fiscal} />);
    // #156 — پنل بسته است؛ نمودار را با کلیکِ نوار باز می‌کنیم
    fireEvent.click(screen.getByTestId('qtrend-toggle'));
    expect(screen.getByText('روند فصلی درآمد و سود ناخالص')).toBeInTheDocument();
    expect(screen.getByText('سود ناخالص', { exact: true })).toBeInTheDocument();
    expect(screen.queryByText('سود خالص')).toBeNull();
  });

  it('حاشیهٔ فصلی = ناخالص ÷ درآمد (۴۰٪) نه خالص ÷ درآمد (۱۰٪)', () => {
    expect(fiscal[0].margin).toBeCloseTo(40, 6);
    expect(fiscal[0].netProfit).toBe(10);
  });

  it('صندوقِ بی‌سودِ ناخالص: هیچ میله‌ای برای سری دوم کشیده نمی‌شود و N/A اعلام می‌شود', () => {
    const fund: FiscalQuarter[] = [
      { key: '1404-Q1', yearLabel: '1404', quarter: 1, revenue: 100, operatingProfit: null, netProfit: 10, grossProfit: null, margin: null },
      { key: '1404-Q2', yearLabel: '1404', quarter: 2, revenue: 150, operatingProfit: null, netProfit: 20, grossProfit: null, margin: null },
    ];
    render(<QuarterlyTrend quarters={fund} />);
    // #156 — پنل بسته است؛ نمودار را با کلیکِ نوار باز می‌کنیم
    fireEvent.click(screen.getByTestId('qtrend-toggle'));
    const chart = screen.getByTestId('quarterly-trend-chart');
    // فقط میلهٔ درآمد (۲ فصل) — میلهٔ سودِ صفرِ جعلی نداریم
    expect(chart.querySelectorAll('rect')).toHaveLength(2);
    expect(screen.getByTestId('qtrend-gross-na')).toBeInTheDocument();
    // «تغییر فصل» هم نمایش داده نمی‌شود (نه ۰، نه عددِ ساختگی)
    expect(screen.queryByText(/تغییر فصل/)).toBeNull();
    // و سود خالصِ موجود هرگز جایگزین نمی‌شود
    expect(profitYoY(fund)).toBeNull();
  });

  it('تغییر فصل وقتی سود ناخالص هر دو فصل هست نوشته می‌شود', () => {
    render(<QuarterlyTrend quarters={fiscal} />);
    // #156 — پنل بسته است؛ نمودار را با کلیکِ نوار باز می‌کنیم
    fireEvent.click(screen.getByTestId('qtrend-toggle'));
    expect(screen.getByText(/تغییر فصل/)).toBeInTheDocument();
  });
});

describe('#102 دریل‌دان شاخص ۳ — روندِ حاشیهٔ ناخالص', () => {
  const card = {
    status: 'success',
    symbol: 'گلدان',
    indicators: { '3': { margin_pct: null, na: true, band: 'not_applicable', pass: false } },
    metrics: {},
  } as unknown as FtsCard;

  const noGross: FiscalQuarter[] = [
    { key: '1405-Q1', yearLabel: '1405', quarter: 1, revenue: 900, operatingProfit: null, netProfit: 120, grossProfit: null, margin: null },
    { key: '1405-Q2', yearLabel: '1405', quarter: 2, revenue: 950, operatingProfit: null, netProfit: 130, grossProfit: null, margin: null },
  ];

  it('سود ناخالص نیست ⇒ نمودارِ «حاشیهٔ ناخالص» رسم نمی‌شود (سود خالص جانشین نمی‌شود)', () => {
    render(<FtsDrillDown card={card} active="3" quarters={noGross} physicalApplicable />);
    expect(screen.queryByTestId('drilldown-margin-chart')).toBeNull();
    expect(screen.getByTestId('drilldown-margin-no-trend')).toBeInTheDocument();
  });

  it('با سودِ ناخالصِ موجود، همان روند رسم می‌شود', () => {
    const withGross: FiscalQuarter[] = noGross.map((q, i) => ({
      ...q,
      grossProfit: i === 0 ? 300 : 320,
      margin: i === 0 ? 33.3 : 33.7,
    }));
    render(<FtsDrillDown card={card} active="3" quarters={withGross} physicalApplicable />);
    expect(screen.getByTestId('drilldown-margin-chart')).toBeInTheDocument();
    expect(screen.queryByTestId('drilldown-margin-no-trend')).toBeNull();
  });
});
