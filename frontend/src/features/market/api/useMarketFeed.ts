// features/market/api/useMarketFeed.ts -- خوراک تابلو با پولینگ
// اشتراک ساختاری پیش فرض TanStack Query ارجاع داده را نگه می دارد تا
// پولینگ 1 ثانیه ای وقتی داده عوض نشده رندر بیهوده نسازد.
import { useQuery } from '@tanstack/react-query';
import { http } from '@shared/api/http';
import { MarketFeedSchema, type MarketFeed } from '@shared/types/marketRow';
import { useMarketStore } from '@shared/stores/marketStore';
import { effectivePollMs } from '@shared/lib/marketHours';

export function useMarketFeed() {
  const refetchIntervalMs = useMarketStore((s) => s.refetchIntervalMs);
  const paused = useMarketStore((s) => s.paused);
  return useQuery({
    queryKey: ['market-feed'],
    queryFn: ({ signal }) => http<MarketFeed>('/api/market', { schema: MarketFeedSchema, signal }),
    // تابع باشد یعنی هر تیک دوباره سنجیده می‌شود: بازِ شدنِ بازار بدونِ remount
    // به ریتمِ سریع برمی‌گردد.
    refetchInterval: paused ? false : () => effectivePollMs(refetchIntervalMs),
    staleTime: 10_000,
    gcTime: 5 * 60_000,
  });
}
