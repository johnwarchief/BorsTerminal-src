// features/market/api/useIntradayVolume.ts -- توزیع حجم درون‌روزِ یک نماد
// قرارداد اندپوینت (نیازمند پیاده‌سازی در بک‌اند):
//   GET /api/market/intraday/{symbol}
//   → { status: string, day?: string, buckets: [{ t: 'HH:MM', vol: number, dir?: 'up'|'down'|null }] }
// نبود اندپوینت/داده ⇒ خطا/N/A صادقانه (بدون mock). کلید React Query: ['market-intraday', symbol]
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import { sessionPollMs } from '@shared/lib/marketHours';
import { SNAPSHOT_POLL_MS } from '../lib/intradayCache';

export const intradayVolumeUrl = (symbol: string): string =>
  `/api/market/intraday/${encodeURIComponent(symbol)}`;

const BucketSchema = z.object({
  t: z.string(),
  vol: z.number().nullish(),
  dir: z.enum(['up', 'down']).nullish(),
});
export type IntradayBucket = z.infer<typeof BucketSchema>;

const IntradaySchema = z.object({
  status: z.string(),
  day: z.string().nullish(),
  buckets: z.array(BucketSchema).nullish(),
});
export type IntradayFeed = z.infer<typeof IntradaySchema>;

export function useIntradayVolume(symbol: string) {
  return useQuery({
    queryKey: ['market-intraday', symbol],
    queryFn: ({ signal }) =>
      http<IntradayFeed>(intradayVolumeUrl(symbol), { schema: IntradaySchema, signal }),
    enabled: symbol.length > 0,
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    retry: false,
    // #173: دقایقِ درون‌روزه‌ی همین نماد هم در ساعتِ بازار عوض می‌شود
    refetchInterval: () => sessionPollMs(SNAPSHOT_POLL_MS),
    refetchOnWindowFocus: false,
  });
}
