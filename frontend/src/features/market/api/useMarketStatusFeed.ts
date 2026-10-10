// features/market/api/useMarketStatusFeed.ts -- خواننده‌های «وضعیت بازار»
//
// چرا جدا از useMarketPulse: نبض بازار رأیِ «ورود/صبر/مخالف» می‌سازد و یک‌جا
// بار می‌کند؛ صفحۀ «وضعیت بازار» همان بانک را در نقشِ پخش‌شده می‌خواهد (توزیع
// درصد، تفکیک مشتری، فازهای نشست، نظارت اصلی) و هر بلوک سنجشِ خودش را دارد.
// هیچ عددی اینجا ساخته نمی‌شود: هر خانۀ null «بی‌داده» می‌ماند.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import { sessionPollMs } from '@shared/lib/marketHours';
import { toFaDigits } from '@shared/lib/fmt';
import { SNAPSHOT_POLL_MS } from '../lib/intradayCache';

const num = z.number().nullish();
const str = z.string().nullish();

/** لحظۀ اسنپ‌شاتِ خودِ موتور — برای «داده از کِی است» در هر بلوک */
export const AsOfSchema = z.object({
  d_even: num,
  h_even: num,
  client_d_even: num,
  client_lag_days: z.boolean().nullish(),
  depth: z.boolean().nullish(),
  top50: num,
  n: num,
});
export type AsOf = z.infer<typeof AsOfSchema>;

const bucket = z.object({
  key: z.string(),
  label: z.string(),
  color: z.string(),
  count: z.number(),
});

export const HistogramSchema = z.object({
  status: z.string(),
  asof: AsOfSchema.nullish(),
  group: str,
  basis: str,
  traded_only: z.boolean().nullish(),
  histo12: z.array(bucket).nullish(),
  histo7: z.array(bucket).nullish(),
  known: num,
  nodata: num,
  total: num,
  not_traded: num,
  source: str,
});
export type HistogramFeed = z.infer<typeof HistogramSchema>;

export function useMstatHistogram(group = 'all') {
  return useQuery({
    queryKey: ['mstat-histogram', group],
    queryFn: ({ signal }) =>
      http<HistogramFeed>(`/api/mstat/histogram?group=${encodeURIComponent(group)}`, {
        schema: HistogramSchema,
        signal,
      }),
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchInterval: () => sessionPollMs(SNAPSHOT_POLL_MS),
    refetchOnWindowFocus: false,
  });
}

const side = z.object({
  buy_count: num,
  buy_b_toman: num,
  buy_pct: num,
  sell_count: num,
  sell_b_toman: num,
  sell_pct: num,
});

export const ClientSplitSchema = z.object({
  status: z.string(),
  asof: AsOfSchema.nullish(),
  tab: str,
  symbols: num,
  retail: side.nullish(),
  institutional: side.nullish(),
  pc_buy_m_toman: num,
  pc_sell_m_toman: num,
  power: num,
  money_flow_b_toman: num,
  source: str,
});
export type ClientSplitFeed = z.infer<typeof ClientSplitSchema>;

export function useMstatClientSplit(tab = 'all') {
  return useQuery({
    queryKey: ['mstat-clientsplit', tab],
    queryFn: ({ signal }) =>
      http<ClientSplitFeed>(`/api/mstat/clientsplit?tab=${encodeURIComponent(tab)}`, {
        schema: ClientSplitSchema,
        signal,
      }),
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchInterval: () => sessionPollMs(SNAPSHOT_POLL_MS),
    refetchOnWindowFocus: false,
  });
}

const phase = z.object({ key: z.string(), label: z.string(), count: z.number() });

export const PhasesSchema = z.object({
  status: z.string(),
  points: num,
  ready: z.boolean().nullish(),
  red: z.array(phase).nullish(),
  green: z.array(phase).nullish(),
  source: str,
});
export type PhasesFeed = z.infer<typeof PhasesSchema>;

export function useMstatPhases() {
  return useQuery({
    queryKey: ['mstat-phases'],
    queryFn: ({ signal }) =>
      http<PhasesFeed>('/api/mstat/phases', { schema: PhasesSchema, signal }),
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchInterval: () => sessionPollMs(SNAPSHOT_POLL_MS),
    refetchOnWindowFocus: false,
  });
}

export const MainWatchRowSchema = z.object({
  symbol: z.string(),
  ins_code: str,
  name: str,
  industry: str,
  cls: str,
  kind: str,
  vol_b_shares: num,
  trades: num,
  val_b_toman: num,
  p_last: num,
  p_closing: num,
  pct_last: num,
  pct_close: num,
  clock_pct: num,
  pc_buy: num,
  pc_sell: num,
  power: num,
  flow_b_toman: num,
});
export type MainWatchRow = z.infer<typeof MainWatchRowSchema>;

export const MainWatchSchema = z.object({
  status: z.string(),
  asof: AsOfSchema.nullish(),
  group: str,
  industry: str,
  sort: str,
  sort_col: str,
  desc: z.boolean().nullish(),
  total: num,
  clock_hits: num,
  clock_rule: z
    .object({ min_pct: num, min_trades: num, min_price: num })
    .nullish(),
  rows: z.array(MainWatchRowSchema).nullish(),
  source: str,
});
export type MainWatchFeed = z.infer<typeof MainWatchSchema>;

export function useMstatMainwatch(group = 'eq_all', industry = '') {
  return useQuery({
    queryKey: ['mstat-mainwatch', group, industry],
    queryFn: ({ signal }) =>
      http<MainWatchFeed>(
        `/api/mstat/mainwatch?group=${encodeURIComponent(group)}&industry=${encodeURIComponent(industry)}`,
        { schema: MainWatchSchema, signal },
      ),
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchInterval: () => sessionPollMs(SNAPSHOT_POLL_MS),
    refetchOnWindowFocus: false,
  });
}

/** «۱۰:۲۳» از h_even، خودِ پاسخ. تاریخِ d_even قالبِ ثابتی ندارد
 *  (همان قیدِ WatchOrderBookPanel)، پس فقط ساعت نشان داده می‌شود و بی‌asof هیچ
 *  ساعتی وعده داده نمی‌شود. */
export function asOfText(a: AsOf | null | undefined): string | null {
  const h = a?.h_even;
  if (typeof h !== 'number' || h <= 0) return null;
  const s = String(h).padStart(6, '0');
  return toFaDigits(`${s.slice(0, 2)}:${s.slice(2, 4)}`);
}
