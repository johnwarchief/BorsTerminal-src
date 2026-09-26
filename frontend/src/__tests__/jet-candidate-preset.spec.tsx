// __tests__/jet-candidate-preset.spec.tsx -- چیپ «نامزدهای ستاپ جت» باید ستاپِ جت را بشمارد
//
// پیش از این این چیپ `i1_pass === true && pricing_mode === 'free'` را می‌شمرد
// و نامش را «ستاپ جت» می‌گذاشت -- یعنی فهرستِ «نامزد» با فهرستِ شاخصِ رشدِ
// فروش یکی بود و کاربر نمادی را ستاپِ جت می‌دید که هیچ‌گاه مقاومت را نشکسته
// بود. ستاپِ واقعی (شکستِ پلکانِ [ih][2..59] با آخرینِ کندل) را موتورِ
// اسکرینر در `tech_jet` می‌گذارد.
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FtsScreenTable } from '@features/fundamental/ui/FtsScreenTable';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';

vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  return {
    ...mod,
    useVirtualizer: (opts: { count: number }) => ({
      getTotalSize: () => opts.count * 46,
      getVirtualItems: () =>
        Array.from({ length: Math.min(opts.count, 20) }, (_, i) => ({
          key: i, index: i, start: i * 46,
        })),
    }),
  };
});

function row(patch: Partial<FtsScreenRow> = {}): FtsScreenRow {
  return {
    symbol: 'شپنا', symbol_norm: 'شپنا', name: 'پالایش نفت اصفهان',
    sector_name: 'محصولات نفتی', pricing_mode: 'free',
    rev_growth: 45.2, eps_series: [100, 120, 150], eps_last: 150, eps_data_gap: false,
    gross_margin: 32.5, sales_to_mcap: 1.2, profit_potential_pct: 42,
    annual_sales_bt: 90, mcap: 5e13, score: 4,
    i1_pass: true, i2_pass: true, i3_pass: true, i4_pass: true, i5_pass: false,
    excluded: false, exclusion_reasons: '', m141: false, watchlist: false,
    tech_jet: false,
    ...patch,
  };
}

// دو ردیف که فقط در «ستاپ جت» فرق دارند: هر دو شاخص ۱ را پاس می‌کنند.
const ROWS = [
  row({ symbol: 'شپنا', symbol_norm: 'شپنا', tech_jet: true }),
  row({ symbol: 'فولاد', symbol_norm: 'فولاد', tech_jet: false }),
];

describe('چیپ نامزدهای ستاپ جت', () => {
  it('شمارشِ چیپ = تعدادِ tech_jet، نه تعدادِ شاخصِ ۱', () => {
    render(<FtsScreenTable rows={ROWS} onSelect={() => {}} />);
    // اگر i1_pass شمرده شود «۲» نشان می‌دهد؛ هر دو ردیف i1_pass دارند.
    expect(screen.getByText(/نامزدهای ستاپ جت/).textContent).toContain('۱');
  });

  it('با انتخابِ پرستِ جت، فقط نمادی که مقاومت را شکسته می‌ماند', () => {
    render(<FtsScreenTable rows={ROWS} onSelect={() => {}} />);
    fireEvent.click(screen.getByText(/نامزدهای ستاپ جت/));
    expect(screen.getByText('شپنا')).toBeInTheDocument();
    expect(screen.queryByText('فولاد')).not.toBeInTheDocument();
  });

  it('نمادِ باقیمتیادِ اجباری حتی با ستاپِ جت در فهرستِ معاملاتی نمی‌آید', () => {
    render(
      <FtsScreenTable
        rows={[row({ symbol: 'شپنا', symbol_norm: 'شپنا', tech_jet: true, pricing_mode: 'mandatory' })]}
        onSelect={() => {}}
      />,
    );
    fireEvent.click(screen.getByText(/نامزدهای ستاپ جت/));
    expect(screen.queryByText('شپنا')).not.toBeInTheDocument();
  });
});
