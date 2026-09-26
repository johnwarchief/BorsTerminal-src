// جدولِ تابلو هیچ دکمهٔ «افزودن به سبد» روی ردیف‌ها ندارد (رأیِ مالک: تابلو خلوت است)
// «تصمیم سبد» فقط در پرتفوی و کارتِ نماد دیده می‌شود. پلِ رویدادیِ market هم حذف شد،
// چون پوسته هیچ‌وقت مشترکِ آن نشد و فقط تستش زنده بود.
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { TapeTable } from '@features/market/components/TapeTable';

function row(patch: Partial<MarketRow> = {}): MarketRow {
  return {
    symbol: 'شپنا',
    name: 'پالایش نفت اصفهان',
    percent_change: 2.5,
    tvol: 5_000_000,
    month_avg_vol: 1_000_000,
    vol_ratio: 5,
    buyer_power: 2.1,
    p_last: 1000,
    p_closing: 1025,
    z_tot_tran: 120,
    is_live: true,
    ...patch,
  } as MarketRow;
}

// jsdom اندازه ندارد -- virtualizer را به رندر کامل وادار می‌کنیم
vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  return {
    ...mod,
    useVirtualizer: ({ count }: { count: number }) => ({
      getTotalSize: () => count * 40,
      getVirtualItems: () => Array.from({ length: count }, (_, i) => ({ key: i, index: i, start: i * 40 })),
    }),
  };
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('جدول تابلو: بدونِ ستونِ سبد', () => {
  it('دکمهٔ «افزودن به سبد» در جدول نیست و جدول خلوت است', () => {
    render(<TapeTable rows={[row()]} selected="" onSelect={() => {}} />);
    expect(screen.queryByText('افزودن به سبد')).not.toBeInTheDocument();
    expect(screen.queryByTestId('row-basket-شپنا')).not.toBeInTheDocument();
  });

  it('کلیک روی بدنهٔ ردیف هنوز نماد را انتخاب می‌کند', () => {
    const onSelect = vi.fn();
    render(<TapeTable rows={[row({ symbol: 'شپنا' })]} selected="" onSelect={onSelect} />);
    fireEvent.click(screen.getByText('شپنا'));
    expect(onSelect).toHaveBeenCalledWith('شپنا');
  });
});
