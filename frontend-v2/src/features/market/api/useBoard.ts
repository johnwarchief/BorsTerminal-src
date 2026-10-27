import { useQuery } from '@tanstack/react-query';
import { getJson } from '@shared/api/http';
import { MarketFeedSchema, type MarketFeed } from '@shared/types/market';

/** خواندنِ کاملِ /api/market؛ دلتا/پولینگ در تسکِ بعدی روی همین کلید می‌نشیند. */
export function useBoard() {
  return useQuery<MarketFeed>({
    queryKey: ['board'],
    queryFn: ({ signal }) => getJson('/api/market', MarketFeedSchema, signal),
    staleTime: 60_000,
  });
}
