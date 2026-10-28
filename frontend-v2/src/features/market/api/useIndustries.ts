import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';
import { sessionPollMs } from '@shared/lib/marketHours';

const num = z.number().nullish();

export const IndustryRowSchema = z.object({
  industry: z.string(),
  symbols: num,
  positive: num,
  negative: num,
  avg_pct: num,
  value_b_toman: num,
  flow_b_toman: num,
  flow_pct_of_value: num,
  buy_queue_b_toman: num,
  sell_queue_b_toman: num,
  rank_value: num,
  rank_flow: num,
  leader_score: num,
  leader: z.boolean().nullish(),
});
export type IndustryRow = z.infer<typeof IndustryRowSchema>;

const IndustriesSchema = z.object({
  status: z.string(),
  group: z.string().nullish(),
  rows: z.array(IndustryRowSchema).nullish(),
  leader: z.string().nullish(),
});
export type IndustriesFeed = z.infer<typeof IndustriesSchema>;

export function topIndustriesByFlow(rows: IndustryRow[] | null | undefined, n = 3): IndustryRow[] {
  return (rows ?? [])
    .filter((row) => typeof row.flow_b_toman === 'number' && Number.isFinite(row.flow_b_toman))
    .sort((a, b) => (b.flow_b_toman as number) - (a.flow_b_toman as number))
    .slice(0, n);
}

export function topIndustriesByPct(rows: IndustryRow[] | null | undefined, n = 3): IndustryRow[] {
  return (rows ?? [])
    .filter((row) => typeof row.avg_pct === 'number' && Number.isFinite(row.avg_pct))
    .sort((a, b) => (b.avg_pct as number) - (a.avg_pct as number))
    .slice(0, n);
}

export function useIndustries() {
  return useQuery({
    queryKey: ['market-industries'],
    queryFn: ({ signal }) => getJson('/api/mstat/industries', IndustriesSchema, signal),
    staleTime: 120_000,
    gcTime: 10 * 60_000,
    refetchInterval: () => sessionPollMs(30_000),
    refetchOnWindowFocus: false,
  });
}
