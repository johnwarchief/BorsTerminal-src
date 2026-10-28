import { useQuery } from '@tanstack/react-query';
import { effectivePollMs } from '@shared/lib/marketHours';
import type { MarketFeed } from '@shared/types/market';
import { fetchBoard } from './boardFeed';

export function useBoard(pollMs = 5_000) {
  return useQuery<MarketFeed>({
    queryKey: ['board'],
    queryFn: ({ signal }) => fetchBoard(signal),
    refetchInterval: () => effectivePollMs(pollMs),
    staleTime: Math.min(Math.max(pollMs - 1_000, 1_000), 4_000),
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}
