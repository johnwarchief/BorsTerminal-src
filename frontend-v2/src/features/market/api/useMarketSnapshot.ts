import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { effectivePollMs } from '@shared/lib/marketHours';
import { getJson } from '@shared/api/http';

const num = z.number().nullish();

const IndexSchema = z.looseObject({
  d_even: z.number(),
  last: num, change: num, pct: num,
  ew_last: num, ew_change: num, ew_pct: num,
});

const PrevSchema = IndexSchema.extend({
  z_tot_tran: num, q_tot_cap: num, q_tot_tran: num,
});

export const MarketSnapshotSchema = z.looseObject({
  status: z.literal('ok'),
  asof: z.looseObject({ d_even: num }).optional(),
  index: IndexSchema.nullish(),
  prev: PrevSchema.nullish(),
  market: z.looseObject({
    trade_value_hemat: num, volume: num, trades: num, market_value_hemat: num,
  }).nullish(),
  retail: z.looseObject({
    value_hemat: num, state: z.string().nullish(), label: z.string().nullish(),
    basis: z.string().nullish(), cause: z.string().nullish(),
    good_min: num, bad_max: num, excellent_min: num,
  }).nullish(),
});

export type MarketSnapshot = z.infer<typeof MarketSnapshotSchema>;

export function parseSnapshot(payload: unknown): MarketSnapshot {
  return MarketSnapshotSchema.parse(payload);
}

export function useMarketSnapshot(pollMs = 5_000) {
  return useQuery<MarketSnapshot>({
    queryKey: ['market-snapshot'],
    queryFn: ({ signal }) => getJson('/api/mstat/market-snapshot', MarketSnapshotSchema, signal),
    refetchInterval: () => effectivePollMs(pollMs),
    staleTime: Math.min(Math.max(pollMs - 1_000, 1_000), 4_000),
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}
