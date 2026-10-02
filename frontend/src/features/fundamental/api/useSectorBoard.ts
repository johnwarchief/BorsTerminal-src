// features/fundamental/api/useSectorBoard.ts -- تابلوی سبک برای میانه صنعت
// جدا از useMarketFeed ایجنت تابلو تا مرز B1 حفظ شود (بدون پولینگ، کش بلند).
import { useMarketFeedShared } from '@shared/api/marketFeed';
import type { MarketFeed } from '@shared/types/marketRow';

export function useSectorBoard() {
  // میانهٔ صنعت از همان تابلو می‌آید؛ کوئریِ جدا یعنی یک ۴ مگابایتِ دوم.
  // select به‌جانِ خود هر ۵ ثانیه می‌دود (۳٬۹۵۹ سطرِ map ≈ صدمِ میلی‌ثانیه) و
  // عوضِ آن، هیچ درخواستِ شبکه‌ای درِ تبِ بنیادی نمی‌ماند.
  return useMarketFeedShared(
    (feed: MarketFeed) =>
        feed.data.map((r) => ({
          symbol: r.symbol,
          sector_name: r.sector_name ?? '',
          pe: r.pe ?? null,
        })),
    5 * 60_000,
  );
}
