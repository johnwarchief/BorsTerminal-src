// F-10 — تست ممیزیِ داده‌ایِ جدول غربالگری:
// ۱) حکمِ موتور بر «مقدار غایب» مقدم است (برچسب «داده نیست» برای ردیفِ دارای حکم دروغ است)
// ۲) EPS بدون گِردکردن بی‌صدا (۴۵۴.۶۷ نباید ۴۵۵ شود)
// ۳) قالب درصد با جداکنندهٔ هزارگان + هشدار برای اعداد غیرمعقول (بدون حذف/دستکاری عدد)
// ۴) علت حذف ردیف سرریز نمی‌کند و متن کامل در tooltip می‌ماند
// ۵) علتِ کارت ممیزی وقتی مقدار نیست، همان حقیقت را می‌گوید («حکمِ موتور اعمال شده»)
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FtsScreenTable } from '@features/fundamental/ui/FtsScreenTable';
import { screenAuditEvidence } from '@features/fundamental/lib/auditEvidence';
import { gapLabel } from '@features/fundamental/lib/gapReason';
import { fmtPctGrouped, fmtRatioGrouped, isAbsurdPct } from '@features/fundamental/lib/numFmt';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';

vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  const WINDOW = 12;
  return {
    ...mod,
    useVirtualizer: ({ count }: { count: number }) => ({
      getTotalSize: () => count * 46,
      getVirtualItems: () =>
        Array.from({ length: Math.min(count, WINDOW) }, (_, i) => ({ key: i, index: i, start: i * 46 })),
    }),
  };
});

function row(patch: Partial<FtsScreenRow> = {}): FtsScreenRow {
  return {
    symbol: 'نماد',
    symbol_norm: 'نماد',
    name: 'شرکت نمونه',
    sector_name: 'مواد و محصولات دارویی',
    pricing_mode: 'free',
    rev_growth: 45.2,
    eps_series: [100, 120, 150],
    eps_last: 150,
    eps_data_gap: false,
    gross_margin: 32.5,
    sales_to_mcap: 1.2,
    profit_potential_pct: 42.0,
    annual_sales_bt: 90.0,
    mcap: 5e13,
    score: 4,
    i1_pass: true,
    i2_pass: true,
    i3_pass: true,
    i4_pass: true,
    i5_pass: true,
    excluded: false,
    exclusion_reasons: '',
    m141: false,
    watchlist: true,
    ...patch,
  };
}

describe('F-10 — حکمِ موتور بر مقدار غایب مقدم است', () => {
  it('شاخص ۱: رشد null ولی حکم مردود ⇒ ✗ (نه برچسب «داده نیست»)', () => {
    render(<FtsScreenTable rows={[row({ symbol: 'الف', rev_growth: null, i1_pass: false })]} onSelect={() => {}} />);
    const cell = screen.getByTestId('fts-mark-1a_monetary_growth');
    expect(cell.textContent).toContain('✗');
    expect(screen.queryByText(gapLabel('1a_monetary_growth'))).toBeNull();
    // عدد جای «—» با tooltip صادقانه
    const value = screen.getByText('—', { selector: 'span.num' });
    expect(value.getAttribute('title')).toContain('حکمِ موتور FTS');
  });

  it('شاخص ۳: حاشیهٔ null ولی حکم مردود ⇒ ✗', () => {
    render(<FtsScreenTable rows={[row({ symbol: 'ب', gross_margin: null, i3_pass: false })]} onSelect={() => {}} />);
    expect(screen.getByTestId('fts-mark-3_gross_margin').textContent).toContain('✗');
    expect(screen.queryByText(gapLabel('3_gross_margin'))).toBeNull();
  });

  it('شاخص ۴: هر دو مقدار null ولی حکم قبول ⇒ ✓', () => {
    render(
      <FtsScreenTable
        rows={[row({ symbol: 'ج', profit_potential_pct: null, sales_to_mcap: null, i4_pass: true })]}
        onSelect={() => {}}
      />,
    );
    expect(screen.getByTestId('fts-mark-4_sales_to_mcap').textContent).toContain('✓');
    expect(screen.queryByText(gapLabel('4_sales_to_mcap'))).toBeNull();
  });

  it('شاخص ۲: eps_data_gap ولی حکم موجود ⇒ حکم اعمال می‌شود (نه برچسب شکاف)', () => {
    render(
      <FtsScreenTable
        rows={[row({ symbol: 'د', eps_data_gap: true, i2_pass: false, eps_series: [100, 120, 150] })]}
        onSelect={() => {}}
      />,
    );
    const cell = screen.getByTestId('fts-mark-2_eps_trend') ?? screen.getByTestId('eps-gap-reason');
    expect(cell.textContent).toContain('✗');
  });

  it('بدون پرچم (حالت نظری) هنوز «بدون داده» می‌آید — صادقانه', () => {
    render(<FtsScreenTable rows={[row({ symbol: 'ه', i5_pass: null, pricing_mode: 'free' })]} onSelect={() => {}} />);
    expect(screen.getByTestId('fts-gap-reason-5_industry')).toBeInTheDocument();
  });
});

describe('F-10 — قالب‌بندی و دقت اعداد', () => {
  it('EPS اعشاری بدون گِردکردن بی‌صدا نمایش داده می‌شود', () => {
    render(
      <FtsScreenTable
        rows={[row({ symbol: 'فسوژ', eps_series: [454.67, 219, 330.67] })]}
        onSelect={() => {}}
      />,
    );
    const cell = screen.getByTestId('fts-screen-row');
    expect(cell.textContent).toContain('۴۵۴.۶۷');
    expect(cell.textContent).toContain('۳۳۰.۶۷');
    expect(cell.textContent).not.toContain('۴۵۵');
  });

  it('درصد بزرگ با جداکنندهٔ هزارگان و نشان هشدار می‌آید (عدد حذف/کلیپ نمی‌شود)', () => {
    render(<FtsScreenTable rows={[row({ symbol: 'شپديس', rev_growth: 3885990000, i1_pass: true })]} onSelect={() => {}} />);
    const cell = screen.getByTestId('fts-screen-row');
    expect(cell.textContent).toContain('۳٬۸۸۵٬۹۹۰٬۰۰۰٪');
    expect(cell.textContent).toContain('⚠');
  });

  it('حاشیهٔ منفیِ بزرگ هم گروه‌بندی و هشدار می‌گیرد', () => {
    render(<FtsScreenTable rows={[row({ symbol: 'فولاد', gross_margin: -1885.9, i3_pass: false })]} onSelect={() => {}} />);
    const cell = screen.getByTestId('fts-screen-row');
    expect(cell.textContent).toContain('۱٬۸۸۵.۹٪');
    expect(cell.textContent).toContain('⚠');
  });

  it('توابع قالب‌بندی: گروه‌بندی، نسبت و آستانهٔ غیرمعقول', () => {
    expect(fmtPctGrouped(3885990000)).toBe('۳٬۸۸۵٬۹۹۰٬۰۰۰٪');
    expect(fmtPctGrouped(45.2)).toBe('۴۵.۲٪');
    expect(fmtPctGrouped(null)).toBeNull();
    expect(fmtRatioGrouped(25618.03)).toBe('۲۵٬۶۱۸.۰۳×');
    expect(isAbsurdPct(1000)).toBe(true);
    expect(isAbsurdPct(999.9)).toBe(false);
  });

  it('علت حذف ردیف بریده می‌شود ولی متن کامل در tooltip می‌ماند', () => {
    render(
      <FtsScreenTable
        rows={[row({ symbol: 'فولاد', excluded: true, exclusion_reasons: 'صنعت بیمه · نماد تعلیق · قیمت‌گذاری دستوری' })]}
        onSelect={() => {}}
      />,
    );
    // ردیف‌های حذف‌شده پیش‌فرض پنهان‌اند؛ برای دیدن علت، توگل نمایش را روشن می‌کنیم
    fireEvent.click(screen.getByRole('button', { name: /نمایش ردیف‌های حذف‌شده/ }));
    const span = screen.getByText('صنعت بیمه · نماد تعلیق · قیمت‌گذاری دستوری');
    expect(span.className).toContain('truncate');
    expect(span.getAttribute('title')).toContain('قیمت‌گذاری دستوری');
  });

  it('شاهدِ ممیزی وقتی مقدار نیست، دلیلش را صادقانه می‌گوید', () => {
    const ev = screenAuditEvidence('1a_monetary_growth', row({ rev_growth: null }), { growth_min: 30 });
    expect(String(ev.reason)).toContain('حکمِ موتور');
    expect(String(ev.reason)).toContain('کارت نماد');
  });
});
