// features/market/api/useHistory.ts -- تاریخچه حجم نماد برای پنل جریان
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

const HistorySchema = z.object({
  status: z.string(),
  candles: z
    .array(
      z.object({
        time: z.string(),
        open: z.number(),
        high: z.number(),
        low: z.number(),
        close: z.number(),
      }),
    )
    .nullish(),
  volumes: z
    .array(
      z.object({
        time: z.string(),
        value: z.number(),
        color: z.string().nullish(),
      }),
    )
    .nullish(),
});

export type HistoryFeed = z.infer<typeof HistorySchema>;

export function useHistory(symbol: string) {
  return useQuery({
    queryKey: ['history', symbol],
    queryFn: ({ signal }) =>
      http<HistoryFeed>(`/api/history/${encodeURIComponent(symbol)}`, { schema: HistorySchema, signal }),
    enabled: symbol.length > 0,
    staleTime: 60_000,
    gcTime: 10 * 60_000,
  });
}
