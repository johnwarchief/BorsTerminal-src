// تست اصلاحات گزارش کاربر روی نماد واقعی «ویسا» (سرمایه‌گذاری/هلدینگ).
// داده از پاسخ واقعی GET /api/fundamental/ویسا گرفته شده (fixtures/fundamental-visa.json):
//   indicators['2'] = {years_available:3, eps_series:[742,1140,-8], strictly_rising:false,
//                      all_profitable:false, data_gap:false, partial:false, pass:false}
//   indicators['4'] = {months_used:12, scale_factor:1, sales_to_mcap:0.31, sales_threshold:0.33}
//   profile = {kind:'production', volume_applicable:true}  ← بک‌اند برای هلدینگ اشتباه می‌دهد
// محورهای تست: (۱) شاخص ۴، (۲) حذف P/NAV ساختگی + هلدینگ، (۳) علت ردِ شاخص ۲، (۴) اصلاحات بصری.
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FtsCard } from '@features/fundamental/components/FtsCard';
import { FtsDrillDown } from '@features/fundamental/components/FtsDrillDown';
import { DataGapBanner } from '@features/fundamental/components/DataGapBanner';
import { QuarterlyTrend } from '@features/fundamental/components/QuarterlyTrend';
import type { FtsCard as FtsCardType } from '@features/fundamental/api/useFtsCard';
import type { FiscalQuarter } from '@features/fundamental/lib/fundMath';
import { epsFailReason } from '@features/fundamental/lib/epsHistory';
import {
  industryGateLabel,
  industryGatePassLabel,
  industryGateTone,
} from '@features/fundamental/lib/industryGate';
import { isFinancialOrHolding, isPhysicalGrowthApplicable } from '@features/fundamental/lib/assetScope';

const visa = JSON.parse(
  readFileSync(path.resolve(import.meta.dirname, 'fixtures/fundamental-visa.json'), 'utf8'),
) as FtsCardType;

const FISCAL: FiscalQuarter[] = [
  // ویسا سرمایه‌گذاری/هلدینگ است: صورتِ سود و زیانش سطر «بهای تمام‌شده» ندارد،
  // پس سود ناخالص NULL است نه صفر (#102) — و margin هم null می‌ماند.
  { key: '1404-Q4', yearLabel: '1404', quarter: 4, revenue: 5_602_625, operatingProfit: null, netProfit: 1_474_154, grossProfit: null, margin: null },
  { key: '1405-Q1', yearLabel: '1405', quarter: 1, revenue: 9_955_592, operatingProfit: null, netProfit: 604_338, grossProfit: null, margin: null },
];

describe('ویسا — محور ۱: شاخص ۴ (سالانه‌سازی داینامیک)', () => {
  it('همان فیلدهای بک‌اند نمایش داده می‌شود: ضریب ×۱ برای ۱۲ ماه و نسبت فروش/ارزش بازار ۰.۳۱ برابر کف ۰.۳۳', () => {
    render(<FtsDrillDown card={visa} active="4" quarters={FISCAL} physicalApplicable={false} />);
    const panel = screen.getByTestId('drilldown-panel-4');
    expect(panel.textContent).toMatch(/م = ۱۲ ماه/);
    expect(panel.textContent).toMatch(/ضریب ×۱/);
    // نسبت و کف از خودِ بک‌اند می‌آید (۰.۳۱ در برابر کف ۰.۳۳)
    expect(panel.textContent).toMatch(/۰.۳۱×/);
    expect(panel.textContent).toMatch(/کف ۳۳٪/);
  });
});

describe('ویسا — محور ۲: هلدینگ و حذف P/NAV ساختگی', () => {
  it('ویسا (سرمایه‌گذاریها) به‌عنوان مالی/هلدینگ شناسایی می‌شود — حتی با املای عربی صنعت', () => {
    expect(isFinancialOrHolding({ name: 'سرمایه گذاری سینا', sector_name: 'سرمايه گذاريها' })).toBe(true);
    // growth فیزیکی برایش هرگز قابل اعمال نیست (حتی اگر پروفایل بک‌اند بگوید true)
    expect(isPhysicalGrowthApplicable({ name: 'سرمایه گذاری سینا', sector_name: 'سرمايه گذاريها' })).toBe(false);
    expect(isPhysicalGrowthApplicable({ name: 'بانک ملت', sector_name: 'بانكها و موسسات اعتباري' })).toBe(false);
    expect(isPhysicalGrowthApplicable({ name: 'پالایش نفت اصفهان', sector_name: 'فراورده‌هاي نفتي' })).toBe(true);
  });

  it('پروفایل تولیدیِ بک‌اند برای هلدینگ، رشد تولیدی را فعال نمی‌کند (کارت N/A)', () => {
    // پروفایل بک‌اند ویسا volume_applicable=true است — فرانت نباید آن را باور کند
    expect(visa.profile?.volume_applicable).toBe(true);
    render(
      <FtsCard
        score={visa.score ?? null}
        passes={visa.passes ?? {}}
        verdict={visa.verdict ?? null}
        physicalApplicable={false}
        industryMode={visa.pricing_mode ?? null}
      />,
    );
    const cell = screen.getByTestId('fts-card-cell-1b_volume_growth');
    expect(within(cell).getByText('N/A')).toBeInTheDocument();
    // #149 — کاشیِ N/A «نظر نمی‌دهد» می‌گیرد، نه «قبول»
    expect(within(cell).queryByText('قبول')).not.toBeInTheDocument();
  });

  it('کادر «رشد تولیدی (تناژ فیزیکی)» در drill-down شاخص ۱ برای هلدینگ وجود ندارد', () => {
    render(<FtsDrillDown card={visa} active="1" quarters={FISCAL} physicalApplicable={false} />);
    const panel = screen.getByTestId('fts-drilldown-1');
    expect(within(panel).queryByText(/تناژ فیزیکی/)).toBeNull();
    expect(within(panel).queryByText(/N\/A/)).toBeNull();
  });
});

describe('ویسا — محور ۳: علت واقعی ردِ شاخص ۲ (نه «داده ناقص»)', () => {
  it('علت از خودِ داده: سقوط سود به زیان در سال آخر', () => {
    const ind = visa.indicators?.['2'];
    const reason = epsFailReason({
      series: ind?.eps_series,
      slots: ind?.period_slots,
      strictlyRising: ind?.strictly_rising,
      allProfitable: ind?.all_profitable,
    });
    expect(reason).toBe('شکست روند سودآوری — سقوط سود به زیان در سال ۱۴۰۵ (-۸ ریال)');
  });

  it('بنر: وقتی هر ۳ سال داده هست، «دادهٔ کدال ناقص است» نمی‌آید و دلیل رد می‌آید', () => {
    render(<DataGapBanner gaps={visa.data_gaps ?? []} eps={visa.indicators?.['2']} />);
    // دلیل رد، جدا از بنر نقص داده
    const reject = screen.getByTestId('reject-reason-banner');
    expect(reject.textContent).toContain('شکست روند سودآوری');
    expect(reject.textContent).toContain('-۸ ریال');
    // ردیف شاخص ۲ از بنر نقص داده حذف شده؛ فقط شاخص ۴ می‌ماند
    const gap = screen.getByTestId('data-gap-banner');
    expect(gap.textContent).toContain('شاخص ۴');
    expect(gap.textContent).not.toContain('شاخص ۲');
    expect(gap.textContent).toContain('۱ شاخص');
  });

  it('drill-down شاخص ۲ دلیل رد را نشان می‌دهد', () => {
    render(<FtsDrillDown card={visa} active="2" quarters={FISCAL} physicalApplicable={false} />);
    const fail = screen.getByTestId('eps-fail-reason');
    expect(fail.textContent).toContain('سقوط سود به زیان در سال ۱۴۰۵');
    // برچسب «رشدِ متوالی ندارد» هم می‌ماند (سیگنال سریع)
    expect(screen.getByText(/رشدِ متوالی ندارد/)).toBeInTheDocument();
  });
});

describe('ویسا — محور ۴: یکدست‌سازی برچسب‌ها و واحدها', () => {
  it('سلول ۵ کارت هم طبقهٔ صنعت را می‌گوید و هم حکم غربالگری (از یک منبع)', () => {
    render(
      <FtsCard
        score={visa.score ?? null}
        passes={visa.passes ?? {}}
        verdict={visa.verdict ?? null}
        physicalApplicable={false}
        industryMode={visa.pricing_mode ?? null}
      />,
    );
    const cell = screen.getByTestId('fts-card-cell-5_industry');
    // صنعت ویسا neutral است: سلولِ کارت نامِ طبقه را می‌گوید و titleِ بجِ ممیزی
    // حکمِ غربالگری را — دو متنِ متفاوت، هر دو از یک منبع (lib/industryGate)
    const gate = within(cell).getByTestId('fts-cell-audit-5_industry');
    expect(within(cell).getByTestId('fts-card-label-5_industry').textContent)
      .toContain(industryGateLabel('neutral'));
    expect(gate.getAttribute('title')).toContain(industryGateLabel('neutral'));
    expect(gate.getAttribute('title')).toContain(industryGatePassLabel(true));
    expect(industryGateTone('neutral')).toBe('yellow');
    // #149 — حکمِ کاشی برچسبِ مستقل دارد؛ برچسبِ طبقهٔ صنعت جای دیگری است
    expect(within(cell).getByTestId('fts-verdict-5_industry').textContent).toContain('قبول');
    expect(within(cell).queryByText('نظر نمی‌دهد')).not.toBeInTheDocument();
  });

  it('نمودار فصلی: محور با واحد میلیارد تومان/همت برچسب می‌خورد', () => {
    render(<QuarterlyTrend quarters={FISCAL} />);
    // #156 — پنل بسته است؛ نمودار با کلیکِ نوار باز می‌شود
    fireEvent.click(screen.getByTestId('qtrend-toggle'));
    const svg = screen.getByTestId('quarterly-trend-chart');
    const labels = Array.from(svg.querySelectorAll('text')).map((t) => t.textContent ?? '');
    expect(labels.some((t) => t.includes('م.ت') || t.includes('همت'))).toBe(true);
    expect(labels.every((t) => !t.includes('م ر'))).toBe(true);
    expect(screen.getByTestId('qtrend-toggle').textContent).toContain('میلیارد تومان');
  });
});
