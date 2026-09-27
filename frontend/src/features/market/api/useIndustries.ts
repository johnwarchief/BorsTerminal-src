// features/market/api/useIndustries.ts -- جمع‌بندی صنایع برای اسکرینر صنعت داغ
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import { sessionPollMs } from '@shared/lib/marketHours';
import { SNAPSHOT_POLL_MS } from '../lib/intradayCache';

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

export const IndustriesSchema = z.object({
  status: z.string(),
  group: z.string().nullish(),
  rows: z.array(IndustryRowSchema).nullish(),
  leader: z.string().nullish(),
});
export type IndustriesFeed = z.infer<typeof IndustriesSchema>;

/**
 * سه صنعت داغ بر مبنای ورود پول حقیقی (flow_b_toman نزولی).
 * سنجهٔ غایب (null — مثلاً صنعتِ بی‌معامله) هرگز رتبه نمی‌گیرد: «بی‌داده» نه
 * صفر است و نه یک سیگنال سبز/قرمز.
 */
export function topIndustriesByFlow(rows: IndustryRow[] | null | undefined, n = 3): IndustryRow[] {
  return (rows ?? [])
    .filter((r) => typeof r.flow_b_toman === 'number' && Number.isFinite(r.flow_b_toman))
    .sort((a, b) => (b.flow_b_toman as number) - (a.flow_b_toman as number))
    .slice(0, n);
}

/**
 * سه صنعت داغ بر مبنای درصد (avg_pct نزولی)؛ avg_pct = میانگینِ تغییرِ قیمتِ
 * پایانی نسبت به دیروز در همان صنعت (ساختهٔ موتور، نه اینجا). صنعتی که هیچ
 * نمادِ دارای درصد ندارد avg_pct=null می‌گیرد و از رتبه‌بندی کنار می‌رود.
 */
export function topIndustriesByPct(rows: IndustryRow[] | null | undefined, n = 3): IndustryRow[] {
  return (rows ?? [])
    .filter((r) => typeof r.avg_pct === 'number' && Number.isFinite(r.avg_pct))
    .sort((a, b) => (b.avg_pct as number) - (a.avg_pct as number))
    .slice(0, n);
}

export function useIndustries() {
  return useQuery({
    queryKey: ['market-industries'],
    queryFn: ({ signal }) => http<IndustriesFeed>('/api/mstat/industries', { schema: IndustriesSchema, signal }),
    staleTime: 120_000,
    gcTime: 10 * 60_000,
    // #173: «صنایع داغ» هم مثلِ نبض بازار در ساعتِ معاملات عوض می‌شود؛ بی‌این
    // خط تا بستنِ صفحه در جای خودش می‌ماند.
    refetchInterval: () => sessionPollMs(SNAPSHOT_POLL_MS),
    refetchOnWindowFocus: false,
  });
}
