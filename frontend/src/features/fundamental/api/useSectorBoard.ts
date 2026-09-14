// features/fundamental/api/useSectorBoard.ts -- تابلوی سبک برای میانه صنعت
// جدا از useMarketFeed ایجنت تابلو تا مرز B1 حفظ شود (بدون پولینگ، کش بلند).
import { useQuery } from '@tanstack/react-query';
import { http } from '@shared/api/http';
import { MarketFeedSchema, type MarketFeed } from '@shared/types/marketRow';

export function useSectorBoard() {
  return useQuery({
    queryKey: ['sector-board'],
    queryFn: ({ signal }) =>
      http<MarketFeed>('/api/market', {
        schema: MarketFeedSchema,
        signal,
      }).then((feed) =>
        feed.data.map((r) => ({ symbol: r.symbol, sector_name: r.sector_name ?? '', pe: r.pe ?? null })),
      ),
    staleTime: 5 * 60_000,
    gcTime: 15 * 60_000,
    refetchOnWindowFocus: false,
  });
}
