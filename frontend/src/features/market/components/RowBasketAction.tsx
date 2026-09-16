// features/market/components/RowBasketAction.tsx -- دکمهٔ سبک «سبد+» روی ردیف جدول بازار
// خودش به portfolio وابسته نیست: قصد را با emitBasketIntent منتشر می‌کند و پوسته
// (که اجازهٔ import از portfolio را دارد) آن را به SymbolBasketAction ترجمه می‌کند.
import { memo } from 'react';
import { emitBasketIntent } from '../lib/basketIntent';

export type RowBasketActionProps = {
  symbol: string;
  /** اگر پوسته یک handler بدهد، به‌جای انتشار رخداد همان صدا زده می‌شود. */
  onBasket?: (symbol: string) => void;
};

export const RowBasketAction = memo(function RowBasketAction({
  symbol,
  onBasket,
}: RowBasketActionProps) {
  if (!symbol) return null;
  return (
    <button
      type="button"
      data-testid={`row-basket-${symbol}`}
      aria-label={`افزودن ${symbol} به سبد`}
      title="افزودن / تصمیم سبد"
      onClick={(e) => {
        // کلیک نباید به ردیف برسد و نماد را انتخاب کند
        e.stopPropagation();
        (onBasket ?? emitBasketIntent)(symbol);
      }}
      onKeyDown={(e) => e.stopPropagation()}
      className="num shrink-0 rounded-full border border-border-c bg-bg-card/60 px-2 py-0.5 text-2xs font-bold text-text-secondary transition-colors duration-200 hover:border-border-accent hover:text-accent-green"
    >
      سبد+
    </button>
  );
});
