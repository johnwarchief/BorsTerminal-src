// F-08 — نگهبان بودجهٔ کارایی جدول غربالگری: جدول مجازی است، پس هزینهٔ DOM به «پنجرهٔ در دید»
// گره خورده نه به کل داده. این فایل با ۸۶۵ ردیف، سقف واقعی DOM را می‌سنجد تا اگر روزی مجازی‌سازی
// برداشته شود یا سلول‌ها سنگین شوند، تست قرمز شود.
// در jsdom ارتفاع وجود ندارد؛ پس پنجرهٔ ۱۲ ردیفی (معادل ~۷۰vh/۴۶px در مرورگر) شبیه‌سازی می‌شود.
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FtsScreenTable } from '@features/fundamental/ui/FtsScreenTable';
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
    i5_pass: false,
    excluded: false,
    exclusion_reasons: '',
    m141: false,
    watchlist: true,
    ...patch,
  };
}

describe('بودجهٔ کارایی جدول غربالگری (F-08)', () => {
  it('۸۶۵ ردیف ⇒ فقط پنجرهٔ در دید رندر می‌شود (قبل از مجازی‌سازی: ۸۶۵ ردیف/۴۳۲۵ بج/۳۲۰۳۱ گره)', () => {
    const rows = Array.from({ length: 865 }, (_, i) =>
      row({ symbol: 'نماد' + String(i), name: 'شرکت نمونه ' + String(i) }),
    );
    render(<FtsScreenTable rows={rows} onSelect={() => {}} thresholds={{ growth_min: 30 }} />);
    const rendered = document.querySelectorAll('[data-testid="fts-screen-row"]').length;
    const badges = document.querySelectorAll(
      '[data-testid^="fts-mark-"], [data-testid^="fts-gap-reason-"], [data-testid="eps-partial-rejected"]',
    ).length;
    const nodes = document.querySelectorAll('*').length;
    // پنجره + حاشیه: عدد ثابت و مستقل از اندازهٔ داده
    expect(rendered).toBeLessThanOrEqual(24);
    expect(badges).toBeLessThanOrEqual(150);
    expect(nodes).toBeLessThan(1200);
  });

  it('جدول کوچک هم کامل رندر می‌شود (رفتار قبلی حفظ شده)', () => {
    render(<FtsScreenTable rows={[row({ symbol: 'الف' }), row({ symbol: 'ب' })]} onSelect={() => {}} />);
    expect(document.querySelectorAll('[data-testid="fts-screen-row"]').length).toBe(2);
  });
});
