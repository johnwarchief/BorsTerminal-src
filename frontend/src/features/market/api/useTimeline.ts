// features/market/api/useTimeline.ts -- سری زمانی درون‌روز برای میکروچارت‌ها
// فقط حالت تجمعی امروز پشتیبانی می‌شود؛ بررسی زندهٔ بک‌اند (curl): هر ?mode= دیگری
// همان mode:"cum" را برمی‌گرداند، پس پنجرهٔ چندروزه «بدون داده» است (Circuit Breaker).
// دامنهٔ سری‌ها انعطاف‌پذیر است (عدد یا رشتهٔ عددی یا null)؛ coerce در
// lib/timelineMath.ts انجام می‌شود تا پاسخِ رشته‌ای باعث safeParse fail و
// «بدون داده» کاذب نگردد.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import { SNAPSHOT_POLL_MS, isMarketOpen } from '../lib/intradayCache';

const cell = z.union([z.number(), z.string(), z.null()]);
const arrCell = z.array(cell).nullish();

export const TimelineSchema = z.object({
  status: z.string(),
  mode: z.string().nullish(),
  ready: z.boolean().nullish(),
  points: z.number().nullish(),
  day: z.number().nullish(),
  series: z
    .object({
      val_bt: arrCell,
      flow_eq_bt: arrCell,
      flow_fixed_bt: arrCell,
      pos: arrCell,
      neg: arrCell,
      bq_bt: arrCell,
      sq_bt: arrCell,
      pc_buy: arrCell,
      pc_sell: arrCell,
      bq_n: arrCell,
      sq_n: arrCell,
      t: z.array(z.union([z.string(), z.number(), z.null()])).nullish(),
    })
    .nullish(),
  session_open: z.string().nullish(),
  session_close: z.string().nullish(),
  note: z.string().nullish(),
  source: z.string().nullish(),
});
export type Timeline = z.infer<typeof TimelineSchema>;

export function useMarketTimeline() {
  return useQuery({
    queryKey: ['market-timeline', 'cum'],
    queryFn: ({ signal }) => http<Timeline>('/api/mstat/timeline?mode=cum', { schema: TimelineSchema, signal }),
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    // پولینگ زنده در ساعات بازار (~۳۰ثانیه) برای ساخت نقاط t1,t2,…؛ خارج بازار خاموش
    refetchInterval: () => (isMarketOpen() ? SNAPSHOT_POLL_MS : false),
    refetchOnWindowFocus: false,
  });
}
