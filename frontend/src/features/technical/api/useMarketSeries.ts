// features/technical/api/useMarketSeries.ts -- مسیر پایدار import برای لایهٔ واحد «کل بورس»
// منطق (اولویت شاخص کل TEDPIX و fallback به سری کلان) در useMarketMacro.ts متمرکز شد
// تا یک منبع حقیقت داشته باشیم؛ این ماژول فقط نام‌های عمومی را re-export می‌کند.
export {
  WHOLE_MARKET_SERIES_SOURCE,
  TEDPIX_SOURCE,
  TEDPIX_TITLE,
  TedpixSchema,
  buildMarketSeries,
  buildWholeMarket,
  fetchTedipx,
  useMarketSeries,
  useTedipxIndex,
  useWholeMarket,
} from './useMarketMacro';
export type { MarketSeries, MarketSeriesPoint, TedpixFeed, WholeMarket } from './useMarketMacro';
