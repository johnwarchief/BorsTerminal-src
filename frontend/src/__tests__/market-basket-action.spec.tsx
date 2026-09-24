// تست اکشن «افزودن به سبد» روی ردیف‌های جدول بازار (TapeTable)
// مرز: market به portfolio وابسته نمی‌شود؛ دکمهٔ ردیف یک «قصد سبد» منتشر می‌کند
// و پوسته آن را به SymbolBasketAction ترجمه می‌کند. اسلات تزریقی هم تست می‌شود.
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { TapeTable } from '@features/market/components/TapeTable';
import { RowBasketAction } from '@features/market/components/RowBasketAction';
import {
  BASKET_INTENT_EVENT,
  emitBasketIntent,
  subscribeBasketIntent,
  type BasketIntentDetail,
} from '@features/market/lib/basketIntent';

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

describe('اکشن سبد و کامپوننت RowBasketAction', () => {
  it('کامپوننت RowBasketAction یک دکمهٔ «سبد+» با label شامل نماد رندر می‌کند', () => {
    render(
      <div>
        <RowBasketAction symbol="شپنا" />
        <RowBasketAction symbol="فولاد" />
      </div>,
    );
    expect(screen.getByTestId('row-basket-شپنا')).toHaveTextContent('سبد+');
    expect(screen.getByLabelText('افزودن شپنا به سبد')).toBeInTheDocument();
    expect(screen.getByLabelText('افزودن فولاد به سبد')).toBeInTheDocument();
  });

  it('در جدول تابلو ستون «افزودن به سبد» حذف شده و جدول خلوت‌تر است', () => {
    render(<TapeTable rows={[row()]} selected="" onSelect={() => {}} />);
    expect(screen.queryByText('افزودن به سبد')).not.toBeInTheDocument();
    expect(screen.queryByTestId('row-basket-شپنا')).not.toBeInTheDocument();
  });

  it('کلیک روی دکمهٔ RowBasketAction قصد سبد را منتشر می‌کند', () => {
    const seen: string[] = [];
    const onIntent = (e: Event) => seen.push((e as CustomEvent<BasketIntentDetail>).detail.symbol);
    window.addEventListener(BASKET_INTENT_EVENT, onIntent);
    try {
      render(<RowBasketAction symbol="خودرو" />);
      fireEvent.click(screen.getByTestId('row-basket-خودرو'));
      expect(seen).toEqual(['خودرو']);
    } finally {
      window.removeEventListener(BASKET_INTENT_EVENT, onIntent);
    }
  });

  it('کلیک روی بدنهٔ ردیف در جدول هنوز نماد را انتخاب می‌کند', () => {
    const onSelect = vi.fn();
    render(<TapeTable rows={[row({ symbol: 'شپنا' })]} selected="" onSelect={onSelect} />);
    fireEvent.click(screen.getByText('شپنا'));
    expect(onSelect).toHaveBeenCalledWith('شپنا');
  });
});

describe('پل قصد سبد (basketIntent)', () => {
  it('subscribeBasketIntent نماد منتشرشده را می‌گیرد و لغو اشتراک کار می‌کند', () => {
    const got: string[] = [];
    const unsub = subscribeBasketIntent((s) => got.push(s));
    emitBasketIntent('شپنا');
    expect(got).toEqual(['شپنا']);
    unsub();
    emitBasketIntent('فولاد');
    expect(got).toEqual(['شپنا']);
  });

  it('نماد خالی منتشر نمی‌شود', () => {
    const got: string[] = [];
    const unsub = subscribeBasketIntent((s) => got.push(s));
    emitBasketIntent('');
    unsub();
    expect(got).toEqual([]);
  });
});
