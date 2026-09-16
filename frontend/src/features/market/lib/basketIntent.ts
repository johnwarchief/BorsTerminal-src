// features/market/lib/basketIntent.ts -- پل سبک «افزودن به سبد» بدون وابستگی به ویژگی portfolio
//
// مرز (boundaries): `features/market` فقط می‌تواند از `shared` و `contracts` import کند،
// پس ردیف جدول بازار مستقیماً به `features/portfolio` وابسته نمی‌شود. به‌جای آن، دکمهٔ
// ردیف یک «قصد سبد» منتشر می‌کند و پوسته (widgets/app — که اجازهٔ import از portfolio را
// دارد) آن را به `SymbolBasketAction` ترجمه می‌کند. این ماژول کاملاً داخل قلمرو market است.
export const BASKET_INTENT_EVENT = 'bors:basket-intent';

export type BasketIntentDetail = { symbol: string };

/**
 * انتشار قصد «افزودن / تصمیم سبد» برای یک نماد.
 * مصرف‌کننده (پوسته) با `subscribeBasketIntent` یا `window.addEventListener(BASKET_INTENT_EVENT, ...)`
 * به این رخداد گوش می‌دهد و دیالوگ واقعی سبد را باز می‌کند.
 */
export function emitBasketIntent(symbol: string): void {
  if (!symbol || typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent<BasketIntentDetail>(BASKET_INTENT_EVENT, { detail: { symbol } }),
  );
}

/** اشتراک روی قصد سبد؛ خروجی، تابع لغو اشتراک است. */
export function subscribeBasketIntent(handler: (symbol: string) => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const listener = (e: Event): void => {
    const detail = (e as CustomEvent<BasketIntentDetail>).detail;
    if (detail && typeof detail.symbol === 'string' && detail.symbol) handler(detail.symbol);
  };
  window.addEventListener(BASKET_INTENT_EVENT, listener);
  return () => window.removeEventListener(BASKET_INTENT_EVENT, listener);
}
